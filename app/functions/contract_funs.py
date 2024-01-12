import operator
import re
from copy import deepcopy, copy
from datetime import datetime
from functools import reduce

from django.db import transaction
from django.db.models import F, Subquery, Q
from django.forms import model_to_dict

import app.functions.interface_funs
import app.functions.interface_procedures
from app.functions import api_funs, convert_funs, interface_procedures, convert_procedures, reg_funs, database_funs, \
    task_funs, convert_funs2
from app.models import ContractCells, Contracts, RegistratorLog, Tasks, TechProcessObjects, TechProcess


# Выполнить триггер
def do_trigger(array_linkmap, trigger, presaved_objs, user_id, timestamp, parent_transact, *list_contracts):
    # генерим ошибку, если вернулась строка с ошибкой
    def work_error(result):
        if type(result) is str and result[:6].lower() == 'ошибка':
            raise Exception(result)

    # отработаем штатный триггер
    if array_linkmap:
        for alm in array_linkmap:
            params = {}
            params['parent_transact'] = parent_transact
            params['timestamp'] = timestamp
            # для обычного триггера
            if alm['method'] == 'edit':
                if type(alm['code']) is int:
                    code = alm['code']
                    object = ContractCells.objects.filter(parent_structure_id=alm['contract'], code=alm['code'])
                    if not object:
                        return 'Ошибка. Некорректно указан код контракта ID: ' + str(alm['contract'])
                    headers = Contracts.objects.filter(parent_id=alm['contract']).exclude(system=True).values()
                    object = convert_funs2.get_full_object(object, headers)
                elif type(alm['code']) is list:
                    object = alm['code'][0]
                    code = object['code']
                else:   return 'Ошибка. Некорректно задана формула, определяющая формулу. ID контракта: ' + \
                               str(alm['contract'])
                for p in alm['params']:
                    try:
                        old_param = object[p['id']]
                    except KeyError:
                        return 'Ошибка. Некорректно указан ID реквизита в LinkMap. ID ' + str(p['id'])
                    else:
                        val = old_param['value']
                        if not val and old_param['type'] == 'float':
                            val = 0
                    if p['sign'] == '+':
                        val += p['value']
                    elif p['sign'] == '-':
                        val -= p['value']
                    else:
                        val = p['value']
                    params[str(p['id'])] = val
                result = api_funs.edit_object(alm['contract'], code, user_id, 'contract', None,
                                              *list_contracts, **params)
                if type(result) is str:
                    return result
            # для нового объекта
            elif alm['method'] == 'new':
                for p in alm['params']:
                    if p['sign'] == '-':    p['value'] *= -1
                    params[str(p['id'])] = p['value']
                result = api_funs.create_object(alm['contract'], user_id, 'contract', **params)
                if type(result) is str:
                    return result
            # для операции "Списание"
            elif alm['method'] == 'wo':
                # Попытка списать все параметры одной транзакцией
                objs = []
                if alm['wo_params']['lifo']:    alm['code'].reverse()
                old_params = alm['code']
                if not old_params:  return 'Ошибка. Некорректно задана формула для кода объекта списания. ' +\
                                               'ID контракта' + str(alm['contract'])
                for p in alm['params']:
                    match_limit = re.match(r'([ltegn]{2})((?:\-|)\d+)', p['limit'])
                    limit_sign = match_limit[1]
                    limit_val = int(match_limit[2])
                    if limit_sign == 'gt':
                        limit_val += 1
                    elif limit_sign == 'lt':
                        limit_val -= 1
                    # прямое списание
                    if p['value'] >= 0:
                        for op in old_params:
                            val = op[p['id']]['value']
                            if alm['wo_params']['sign'] == '+':
                                if val >= limit_val:
                                    continue
                                val += p['value']
                            else:
                                if val <= limit_val:
                                    continue
                                val -= p['value']
                            try:
                                obj = next(o for o in objs if o['code'] == op['code'])
                            except StopIteration:
                                obj = params.copy()
                                obj['code'] = op['code']
                                objs.append(obj)
                            # исчерпывающее списание
                            if convert_procedures.do_logical_compare(val, limit_sign, limit_val):
                                obj[str(p['id'])] = val
                                break
                            # недостаточное списание
                            else:
                                obj[str(p['id'])] = limit_val
                                if alm['wo_params']['sign'] == '+':
                                    p['value'] += op[p['id']]['value']
                                else:
                                    p['value'] -= op[p['id']]['value']
                        else:
                            return 'Ошибка. Недостаточное количество для списания. ID параметра ' + str(p['id'])
                    # Обратное списание
                    else:
                        pa_tr = 'c' + str(presaved_objs[0]['parent_structure']) + 'c' + str(presaved_objs[0]['code']) + 'id'
                        hist = list(RegistratorLog.objects.filter(parent_transact_id__startswith=pa_tr, reg_name=15,
                                                                  json__name=p['id'], json__class_id=alm['contract'])\
                                    .order_by('-id'))
                        if not hist:
                            return 'Ошибка. Нет истории списания. Возврат объекта невозможен'
                        # добавим в массив дельты
                        mnoj = 1 if alm['wo_params']['sign'] == '-' else -1
                        for h in hist:
                            h.delta = (h.json_income['value'] - h.json['value']) * mnoj
                        # Приведем историю к нормальному виду,
                        # т.е. избавимся от минусовых значений методом обратного списания (положи туда, где взял)
                        i = 0
                        while i < len(hist):
                            h = hist[i]
                            if h.delta < 0:
                                delta = h.delta
                                j = i + 1
                                while j < len(hist):
                                    if h.json['code'] == hist[j].json['code'] and hist[j].delta > 0:
                                        # исчерпывающее списание
                                        if delta + hist[j].delta >= 0:
                                            hist[j].delta += delta
                                            if hist[j].delta == 0:
                                                hist.pop(j)
                                            hist.pop(i)
                                            i -= 1
                                            break
                                        # неполное списание
                                        else:
                                            delta += hist[j].delta
                                            hist.pop(j)
                                            j -= 1
                                    j += 1
                            i += 1
                        # Вернем объекты на свои места хранения
                        for h in hist:
                            old_obj = ContractCells.objects.get(parent_structure_id=alm['contract'], code=h.json['code'],
                                                            name_id=h.json['name'])
                            try:
                                obj = next(o for o in objs if o['code'] == h.json['code'])
                            except StopIteration:
                                obj = params.copy()
                                obj['code'] = h.json['code']
                                objs.append(obj)
                            # полное начисление
                            pid = str(p['id'])
                            if p['value'] * -1 <= h.delta:
                                new_val = p['value'] * -1 * mnoj
                                if pid in obj:
                                    obj[pid] += new_val
                                else:   obj[pid] = new_val + old_obj.value
                                break
                            else:
                                new_val = h.delta * mnoj
                                if pid in obj:  obj[pid] += new_val
                                else:   obj[pid] = new_val + old_obj.value
                                p['value'] += h.delta

                # Занесем списанные значение в БД
                for o in objs:
                    code = o['code']
                    del o['code']
                    result = api_funs.edit_object(alm['contract'], code, user_id, 'contract', None,
                                                  *list_contracts, **o)
                    if type(result) is str:
                        return result
            else:
                return 'Ошибка в линкмапе'

    # Отработаем пользовательский  триггер
    if trigger['value'] and type(array_linkmap) is list:
        convert_funs.deep_formula(trigger, presaved_objs, user_id, True)
        res_trigger = presaved_objs[0][trigger['id']]['value']
        if type(res_trigger) is str and res_trigger[:6].lower() == 'ошибка':
            return res_trigger
    return 'ok'


# Упаковать линкМап. Собирает в массив данные из поля ЛинкМап
# kwargs = {mode: c/e (create/edit)}
def pack_linkmap(linkmap, objects, edit_objs, user_id):
    flags = re.IGNORECASE
    str_linkmap = re.sub('\n', '', linkmap['value'])
    array_trigger_params = re.findall(r'.+?(?:\;|$)', str_linkmap, flags=flags)
    list_triggers = []
    if not array_trigger_params:
        return list_triggers
    for atp in array_trigger_params:
        dict_trigger = {}
        dict_trigger['method'] = 'edit'
        contract_id = re.match(r'.*contract\s*=\s*(\d+)', atp, flags=flags)
        if not contract_id:
            return False
        contract_id = int(contract_id[1])
        dict_trigger['contract'] = contract_id
        code = re.match(r'.*code\s*=\s*(\d+)', atp, flags=flags)
        # Если код задан неявным образом - вычислим его
        if code:
            code = int(code[1])
        else:
            # Есть ли в коде параметр new
            if re.search(r'code\s*=\s*(?:\[\[.*\]\]\s*or|)\s+new', atp, re.S):
                dict_trigger['method'] = 'new'
            # Если в качестве кода задана формула, возвращающая массив данных
            match_formula = re.search(r'.*code\s*=\s*(\[\[(?:.*?(?:\[\[.*?\]\]|))+?\]\])', atp, re.S)
            if match_formula:
                linkmap['value'] = 'result = ' + match_formula[1]
                convert_funs.deep_formula(linkmap, objects, user_id, True)
                val = objects[0][linkmap['id']]['value']
                if not type(val) is list:
                    return False
                del objects[0][linkmap['id']]
                # Если не нашлось объектов по требуемым условиям и нет условия "Найти или создать", то вернуть ошибку
                if not val:
                    if dict_trigger['method'] != 'new':
                        return False
                else:
                    dict_trigger['method'] = 'edit'
                    code = val
            elif dict_trigger['method'] != 'new':
                return False
        dict_trigger['code'] = code
        # Списание
        match_wo = re.search(r'write-off(?:\s*=\s*\[(.*?)\]|)', atp, flags=flags)
        sign = '-'
        if match_wo:
            dict_trigger['method'] = 'wo'
            is_lifo = False
            if match_wo.lastindex > 0:
                match_lifo = re.search(r'(lifo|fifo)', match_wo[1], flags=flags)
                if match_lifo and match_lifo[1] == 'lifo':
                    is_lifo = True
                match_sign = re.search(r'[+-]', match_wo[1], flags=flags)
                if match_sign and match_sign[0] == '+':
                    sign = '+'
            dict_trigger['wo_params'] = {'lifo': is_lifo, 'sign': sign}

        dict_trigger['params'] = []
        params = re.match(r'.*params\s*=\s*\{(.*)\}', atp, flags=flags)
        if not params:
            return False
        array_params = re.findall(r'(.+?)(?:$|\,)', params[1], flags=flags)
        for ap in array_params:
            param = {}
            id = re.match(r'.*id\s*=\s*(\d+)', ap, flags=flags)
            if not id:
                return False
            param['id'] = int(id[1])
            if match_wo:
                param['sign'] = sign
            else:
                sign = re.match(r'.*sign\s*=\s*([+-e])', ap, flags=flags)
                param['sign'] = sign[1] if sign else 'e'
            val = re.match(r'.*value\s*=\s*(.+?)(:?\,|sign|id|write-off|limit|$)', ap, flags=flags)
            if not val:
                return False
            elif re.match(r'.*\[\[', val[1]):
                linkmap['value'] = 'result = ' + val[1]
                if param['sign'] == 'e':
                    convert_funs.deep_formula(linkmap, objects, user_id, True)
                    val = objects[0][linkmap['id']]['value']
                    del objects[0][linkmap['id']]
                else:
                    convert_funs.deep_formula(linkmap, edit_objs, user_id, True)
                    val = edit_objs[0][linkmap['id']]['value']
                    del edit_objs[0][linkmap['id']]
                if type(val) is str and val[:6].lower() == 'ошибка':
                    return False
            else:
                try:
                    val = float(val[1])
                except ValueError:
                    val = val[1]
            param['value'] = val
            match_limit = re.search(r'limit\s*=\s*([glten]{2}(?:\-|)\d+)', ap, flags=flags)
            param['limit'] = match_limit[1] if match_limit else 'gt0'
            dict_trigger['params'].append(param)
        list_triggers.append(dict_trigger)
    return list_triggers


# Отработака бизнес-правила. Вход айди контракта, словарь с данными
# Выход - Да/нет
def do_business_rule(biz_rule_header, presaved_object, user_id):
    biz_rule_done = True
    if biz_rule_header['value']:
        objs = [presaved_object, ]
        convert_funs.deep_formula(biz_rule_header, objs, user_id, True)
        result = presaved_object[biz_rule_header['id']]['value']
        if type(result) is str and result[:6].lower() == 'ошибка':
            biz_rule_done = False
        else:
            biz_rule_done = bool(result)
    return biz_rule_done


# dcsp - do_contract_system_params
# Возвращает строку. Если все ок - вернет ок. Если есть текст - это текст ошибки
def dcsp(contract_id, code, headers, user_id, dict_object, dict_edit_object, timestamp, parent_transact, *list_contracts, **params):
    def make_error(txt):
        raise Exception(txt)
    # Проверка цикличности
    if contract_id in list_contracts:
        return 'Ошибка. В цепочке триггеров наблюдается цикличная ссылочность. ' \
               'Проверьте поля link_map всех контрактов в цепочке<br>'
    else:
        list_contracts = list(list_contracts)
        list_contracts.append(contract_id)

    system_names = ('business_rule', 'link_map', 'trigger')
    system_params = Contracts.objects.filter(parent_id=contract_id, name__in=system_names).values()

    # 1. отработаем бизнес-правило
    biz_rule = next(sp for sp in system_params if sp['name'] == 'business_rule')
    old_obj = ContractCells.objects.filter(parent_structure_id=contract_id, code=code)
    tps = params['tps'] if "tps" in params else None
    presaved_object = app.functions.interface_procedures.mofr(code, contract_id, headers, dict_object, old_obj, True)
    if not do_business_rule(biz_rule, presaved_object, user_id):
        return 'Ошибка. Не выполняется бизнес-правило контракта<br>'

    # 2. Отработаем линкмап
    link_map = next(sp for sp in system_params if sp['name'] == 'link_map')
    array_link_map = []
    objs = (presaved_object, )
    if link_map['value']:
        presaved_edit_object = app.functions.interface_procedures.mofr(code, contract_id, headers, dict_edit_object,
                                                                       old_obj, True)
        edit_objs = (presaved_edit_object,)
        array_link_map = pack_linkmap(link_map, objs, edit_objs, user_id)
        if not array_link_map and type(array_link_map) is bool:
            return 'Ошибка. LinkMap задан некорректно<br>'

    @transaction.atomic()
    def atom_operation():
    # 3. Отработаем триггеры
        trigger = next(sp for sp in system_params if sp['name'] == 'trigger')
        res_trigger = do_trigger(array_link_map, trigger, objs, user_id, timestamp, parent_transact, *list_contracts)
        if res_trigger != 'ok':
            make_error(res_trigger)


    # Выполним атомарные функции
    try:
        atom_operation()
    except Exception as ex:
        return str(ex)
    return 'ok'


# Проверка объектов контракта на выполнение BR
# vocobru - verify objects contract on business rule
# вход - бизнес правило в виде объекта кверисета Выход - Да/нет
def vocobru(br, user_id):
    if not br.value:
        return True
    br = model_to_dict(br)
    obj_codes = ContractCells.objects.filter(parent_structure_id=br['parent']).values('code').distinct()
    for oc in obj_codes:
        obj = ContractCells.objects.filter(parent_structure_id=br['parent'], code=oc['code'])
        obj = convert_funs.queyset_to_object(obj)
        convert_funs.deep_formula(br, obj, user_id, True)
        val = obj[0][br['id']]['value']
        if not val:
            return False
        elif type(val) is str and val[:6].lower() == 'ошибка':
            return False
    else:
        return True


# ctp4s = check TP for stages
# Проверяет техпроцесс на стадии в работе
# tp_id - ID techpro, заголовков трех основных свойств: parent_code_id, stage_id, cf_id; список стадий для проверки - stages
# array_code - код объекта массива контракта
def ctp4s(array_code, tp_id, parent_code_id, stage_id, cf_id, stages):
    tp_codes = ContractCells.objects.filter(parent_structure_id=tp_id, name_id=parent_code_id, value=array_code) \
        .values('code').distinct()
    q = reduce(operator.or_, (Q(value=s) for s in stages))
    stage_vals = ContractCells.objects.filter(q, parent_structure_id=tp_id, code__in=Subquery(tp_codes),
                                              name_id=stage_id).values('code').distinct()
    control_fields = ContractCells.objects.filter(parent_structure_id=tp_id, code__in=Subquery(stage_vals),
                                                  name_id=cf_id, value__gt=0.0).count()
    if control_fields:
        return False
    # Проверка тасков на данный ТП
    if Tasks.objects.filter(data__tp_id=tp_id, data__parent_code=array_code):
        return False
    return True


# tps - список.
def save_edited_tps(tps, presaved_object, dict_edit, timestamp, user_id, parent_transact=None):

    def make_task(receiver, fact, state, delay, delta, stage_name, task_code):

        data = {'tp_id': tp_key, 'tp_name': tp_info['name'], 'parent_code': presaved_object['code'], 'fact': fact,
                'state': state,
                'delay': delay, 'delta': delta, 'stage': stage_name, 'sender_id': user_id}
        task = Tasks(date_create=timestamp, user_id=receiver, data=data, code=task_code, kind='stage')
        task.save()
        task = model_to_dict(task)
        task['date_create'] = datetime.strftime(task['date_create'], '%Y-%m-%dT%H:%M:%S')
        reg = {'json': task}
        reg_funs.simple_reg(user_id, 18, timestamp, task_transact_id, transact_id, **reg)

    def reg_create_task():
        task_code = database_funs.get_other_code('task')
        task_transact_id = reg_funs.get_transact_id('task', task_code)
        reg = {'json': {'code': task_code}}
        reg_funs.simple_reg(user_id, 17, timestamp, task_transact_id, transact_id, **reg)
        return task_code, task_transact_id

    for tp_key, tp_val in presaved_object['tps'].items():
        tp_info = next(tp for tp in tps if tp['id'] == tp_key)
        # Проверка бизнес-правила техпроцесса
        header_br = next(p for p in tp_info['system_params'] if p['name'] == 'business_rule')
        if not do_business_rule(header_br, presaved_object, user_id):
            return 'Ошибка. Не выполняется бизнес-правило техпроцесса ID ' + str(tp_info['id'])

        transact_id = reg_funs.get_transact_id(tp_key, presaved_object['code'], 'p')

        # Проверим, изменилось ли контрольное поле
        key_cf = 'i_float_' + str(tp_info['cf'])
        delta_cf = dict_edit[key_cf]
        if delta_cf:
            first_stage = TechProcessObjects.objects.get(parent_code=presaved_object['code'],
                                                         parent_structure_id=tp_info['id'],
                                                         name_id=tp_info['stages'][0]['id'])
            inc = {'class_id': tp_info['id'], 'code': presaved_object['code'],
                   'location': 'contract', 'type': 'tp', 'name': first_stage.name_id, 'id': first_stage.id,
                   'value': deepcopy(first_stage.value)}
            first_stage.value['fact'] += delta_cf
            first_stage.save()
            outc = inc.copy()
            outc['value'] = deepcopy(first_stage.value)
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(user_id, 15, timestamp, transact_id, parent_transact, **reg)

        old_stages = TechProcessObjects.objects.filter(parent_structure_id=tp_key, parent_code=presaved_object['code'])
        task_code = None
        task_transact_id = None
        is_anybody_handlers = False

        for stage_key, stage_val in tp_val.items():
            stage_info = next(hl for hl in header_linkmap['value'] if hl['name'] == stage_key)
            try:
                stage = next(os for os in old_stages if os.value['stage'] == stage_key)
            except StopIteration:
                if stage_info['handler']:
                    is_anybody_handlers = True
                if stage_val['state']:
                    delay = [{'date_create': datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S'),
                              'value': stage_val['state']}]
                    fact = 0
                    if not task_code:
                        task_code, task_transact_id = reg_create_task()
                    make_task(stage_info['handler'], fact, stage_val['state'], stage_val['state'],
                              stage_val['state'], stage_key, task_code)
                else:
                    delay = []
                    fact = stage_val['state']
                val = {'fact': fact, 'delay': delay, 'stage': stage_key}
                new_stage = TechProcessObjects(parent_structure_id=tp_info['id'], parent_code=presaved_object['code'],
                                               value=val, name_id=header_stages['id'])
                new_stage.save()
                outc = {'class_id': tp_info['id'], 'type': 'techprocess', 'location': 'contract',
                        'id': new_stage.id, 'code': presaved_object['code'], 'name': header_stages['id'],
                        'value': new_stage.value}
                reg = {'json': outc}
                reg_funs.simple_reg(user_id, 13, timestamp, transact_id, parent_transact, **reg)
            else:
                inc = {'class_id': tp_info['id'], 'type': 'techprocess', 'location': 'contract',
                       'id': stage.id, 'code': presaved_object['code'], 'name': header_stages['id'],
                       'value': deepcopy(stage.value)}
                old_delay = sum([d['value'] for d in stage.value['delay']])
                old_fact = stage.value['fact'] if stage.value['fact'] else 0
                old_stage = old_fact + old_delay
                if stage_val['state'] != old_stage:
                    delta = stage_val['state'] - old_stage
                    new_delay = {'value': delta,
                                 'date_create': datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S')}
                    stage.value['delay'].append(new_delay)
                    if not task_code:
                        task_code, task_transact_id = reg_create_task()
                    make_task(stage_info['handler'], stage_val['fact'], stage_val['state'], delta + old_delay,
                              delta, stage_key, task_code)
                    outc = inc.copy()
                    outc['value'] = stage.value.copy()
                    stage.save()
                    reg = {'json': outc, 'json_income': inc}
                    reg_funs.simple_reg(user_id, 15, timestamp, transact_id, parent_transact, **reg)
                    if stage_info['handler']:
                        is_anybody_handlers = True
        # Если изменения были, но ответственные не нашлись, значит сразу выполним таск
        if not is_anybody_handlers and task_code:
            task = Tasks.objects.filter(code=task_code)
            for t in task:
                check_task = True if task.index(t) == len(task) - 1 else False
                task_funs.change_task_stage(user_id, t, timestamp, check_task=check_task,
                                            is_approve=True)
    return 'ok'