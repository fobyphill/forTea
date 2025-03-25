import operator
import re
from copy import deepcopy, copy
from datetime import datetime
from functools import reduce

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Subquery, Q
from django.forms import model_to_dict

import app.functions.interface_funs
import app.functions.interface_procedures
from app.functions import api_funs, convert_funs, interface_procedures, convert_procedures, reg_funs, database_funs, \
    task_funs, convert_funs2, api_procedures, contract_procedures, session_procedures
from app.functions.contract_procedures import rex
from app.models import ContractCells, Contracts, RegistratorLog, Tasks, TechProcessObjects, TechProcess, Designer, \
    Objects


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
                    object = ContractCells.objects.filter(parent_structure_id=alm['class_id'], code=alm['code'])
                    if not object:
                        return 'Ошибка. Некорректно указан код контракта ID: ' + str(alm['class_id'])
                    headers = Contracts.objects.filter(parent_id=alm['class_id']).exclude(system=True).values()
                    current_class = Contracts.objects.get(id=alm['class_id'])
                    object = convert_funs2.get_full_object(object, current_class, headers, 'contract')
                elif type(alm['code']) is list:
                    object = alm['code'][0]
                    code = object['code']
                else:   return 'Ошибка. Некорректно задана формула, определяющая формулу. ID контракта: ' + \
                               str(alm['class_id'])
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
                result = api_funs.edit_object(alm['class_id'], code, user_id, 'contract', None,
                                              *list_contracts, **params)
                if type(result) is str and result.lower()[:6] == 'ошибка':
                    return result
            # для нового объекта
            elif alm['method'] == 'new':
                for p in alm['params']:
                    if p['sign'] == '-':    p['value'] *= -1
                    params[str(p['id'])] = p['value']
                result = api_funs.create_object(alm['class_id'], user_id, 'contract', **params)
                if type(result) is str:
                    return result
            # для операции "Списание"
            elif alm['method'] == 'wo':
                # Попытка списать все параметры одной транзакцией
                objs = []
                old_params = alm['code']
                if not old_params:  return 'Ошибка. Некорректно задана формула для кода объекта списания. ' +\
                                               'ID контракта' + str(alm['class_id'])
                for p in alm['params']:
                    # прямое списание
                    if p['value'] >= 0:
                        for op in old_params:
                            old_val = op[p['id']]['value'] if op[p['id']]['value'] else 0
                            val = old_val
                            if val <= p['limit']:
                                continue
                            val -= p['value']
                            try:
                                obj = next(o for o in objs if o['code'] == op['code'])
                            except StopIteration:
                                obj = params.copy()
                                obj['code'] = op['code']
                                objs.append(obj)
                            # исчерпывающее списание
                            if val >= p['limit']:
                                obj[str(p['id'])] = val
                                break
                            # недостаточное списание
                            else:
                                obj[str(p['id'])] = p['limit']
                                p['value'] -= old_val - p['limit']
                        else:
                            return 'Ошибка. Недостаточное количество для списания. ID параметра ' + str(p['id'])
                    # Обратное списание
                    else:
                        pa_tr = 'c' + str(presaved_objs[0]['parent_structure']) + 'c' + str(presaved_objs[0]['code']) + 'id'
                        hist = list(RegistratorLog.objects.filter(parent_transact_id__startswith=pa_tr, reg_name=15,
                                                                  json__name=p['id'], json__class_id=alm['class_id'])\
                                    .order_by('-id'))
                        if not hist:
                            return 'Ошибка. Нет истории списания. Возврат объекта невозможен'
                        # добавим в массив дельты
                        for h in hist:
                            h.delta = (h.json_income['value'] - h.json['value'])
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
                            old_obj = ContractCells.objects.get(parent_structure_id=alm['class_id'], code=h.json['code'],
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
                                new_val = p['value'] * -1
                                if pid in obj:
                                    obj[pid] += new_val
                                else:   obj[pid] = new_val + old_obj.value
                                break
                            else:
                                if pid in obj:  obj[pid] += h.delta
                                else:   obj[pid] = h.delta + old_obj.value
                                p['value'] += h.delta

                # Занесем списанные значение в БД
                for o in objs:
                    code = o['code']
                    del o['code']
                    result = api_funs.edit_object(alm['class_id'], code, user_id, 'contract', None,
                                                  *list_contracts, **o)
                    if type(result) is str and result.lower()[:6] == 'ошибка':
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
def pack_linkmap(linkmap, objects, edit_objs, user_id, event_kind):
    list_triggers = []
    for lm in linkmap['value']:
        # Проверка выполнения линкмапа в соответствии с типом события
        for ek in lm['event_kind']:
            if ek in event_kind:
                break
        else:
            continue
        dict_trigger = {}
        dict_trigger['method'] = 'edit'
        dict_trigger['class_id'] = lm['class_id']
        code = None
        if lm['new_code']:
            dict_trigger['method'] = 'new'
        try:
            code = int(lm['code'])
        except ValueError:
            # Если в качестве кода задана формула, возвращающая массив данных
            match_formula = re.search(r'(\[\[(?:.*?(?:\[\[.*?\]\]|))+?\]\])', lm['code'], re.S)
            if match_formula:
                header = deepcopy(linkmap)
                header['value'] = 'result = ' + match_formula[1]
                convert_funs.deep_formula(header, objects, user_id, True)
                code = objects[0][linkmap['id']]['value']
                if not type(code) is list:
                    return False
                del objects[0][linkmap['id']]
                # Если не нашлось объектов по требуемым условиям и нет условия "Найти или создать", то вернуть ошибку
                if not code:
                    if dict_trigger['method'] != 'new':
                        return False
                else:
                    dict_trigger['method'] = 'edit'
            elif dict_trigger['method'] != 'new':
                return False
        dict_trigger['code'] = code

        # Списание
        if lm['writeoff']:
            dict_trigger['method'] = 'wo'
            if not dict_trigger['code'] or type(dict_trigger['code']) is not list:
                return False
            # допилить код. если нет или не список - вернуть ложь
        dict_trigger['params'] = []
        for lmp in lm['params']:
            dict_params = {'id': lmp['id']}
            if 'sign' in lmp:
                dict_params['sign'] = lmp['sign']
            elif lm['writeoff']:
                dict_params['sign'] = '-'
            else:
                dict_params['sign'] = 'e'
            if 'limit' in lmp:
                dict_params['limit'] = lmp['limit']
            header = deepcopy(linkmap)
            header['value'] = lmp['value']
            objs = objects if dict_params['sign'] == 'e' else edit_objs
            convert_funs.deep_formula(header, objs, user_id, True)
            dict_params['value'] = objs[0][linkmap['id']]['value']
            del objs[0][linkmap['id']]
            dict_trigger['params'].append(dict_params)
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

# Проверка объектов контракта на выполнение BR
# vocobru - verify objects contract on business rule
# вход - бизнес правило в виде объекта кверисета Выход - Да/нет
# Устарела. Удалить после 15.04.2025
def vocobru(br, user_id):
    if not br.value:
        return True
    br = model_to_dict(br)
    obj_codes = ContractCells.objects.filter(parent_structure_id=br['parent']).values('code').distinct()
    for oc in obj_codes:
        obj = ContractCells.objects.filter(parent_structure_id=br['parent'], code=oc['code'])
        obj = convert_funs.queryset_to_object(obj)
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


@transaction.atomic()
def edit_contract(current_class, code, class_params, system_params, tps, edit_objects, new_objects, object_user, timestamp,
                   *list_contracts, **params):
    if current_class.id in list_contracts:
        rex('Ошибка. Наблюдается циклическая ссылочность в цепочке линкмапов контрактов')
    else:
        list_contracts = list(list_contracts)
        list_contracts.append(current_class.id)
    tps_all = params['tps_all'] if 'tps_all' in params else None
    general_reg_data = {'class_id': current_class.id, 'code': code, 'location': 'contract',
                        'type': current_class.formula}
    control_fields = [t['cf'] for t in tps]
    transact_id = params['transact_id'] if 'transact_id' in params else reg_funs.get_transact_id(current_class.id, code, 'c')
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    if edit_objects:
        ContractCells.objects.bulk_update([eo['new_obj'] for eo in edit_objects if 'old_value' in eo], ['value'])
        ContractCells.objects.bulk_update([eo['new_obj'] for eo in edit_objects if 'old_delay' in eo], ['delay'])
        # регистрация редактирования создание тасков для делеев
        for eo in edit_objects:
            ic = general_reg_data.copy()
            ic['id'] = eo['new_obj'].id
            ic['name'] = eo['new_obj'].name_id
            oc = ic.copy()
            if 'old_value' in eo:
                ic_val = ic.copy()
                ic_val['value'] = eo['old_value']
                oc_val = oc.copy()
                oc_val['value'] = eo['new_obj'].value
                reg_val = {'json_income': ic_val, 'json': oc_val}
                reg_funs.simple_reg(object_user.id, 15, timestamp, transact_id, parent_transact, **reg_val)
            if 'old_delay' in eo:
                make_delay = len(eo['new_obj'].delay) > len(eo['old_delay'])
                last_delay = eo['new_obj'].delay[-1] if make_delay else eo['old_delay'][-1]
                date_update = datetime.strptime(last_delay['date_update'], '%Y-%m-%dT%H:%M')
                ic_del = ic.copy()
                ic_del['delay'] = eo['old_delay']
                oc_del = oc.copy()
                if date_update < timestamp and make_delay:
                    delay_ppa = True
                    date_delay = last_delay['date_update']
                    date_update = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                    last_delay['date_update'] = date_update
                    eo['new_obj'].save()
                else:
                    delay_ppa = False
                    date_delay = None
                oc_del['delay'] = eo['new_obj'].delay
                reg_del = {'json': oc_del, 'json_income': ic_del, 'date_delay': date_delay}
                reg_funs.simple_reg(object_user.id, 22, timestamp, transact_id, parent_transact, **reg_del)
                current_param = next(cp for cp in class_params if cp['id'] == eo['new_obj'].name_id)
                prms = {}
                if 'task_code' in eo:
                    prms['code'] = eo['task_code']
                if 'task_transact' in eo:
                    prms['task_transact'] = eo['task_transact']
                if eo['new_obj'].name_id in control_fields:
                    prms['cf'] = True
                if make_delay:  # Создаем / регистрируем таск
                    interface_procedures.make_task_4_delay(current_param, eo['new_obj'], 'c', object_user, timestamp,
                                                           delay_ppa, transact_id, **prms)

    if new_objects:
        ContractCells.objects.bulk_create(new_objects)
        new_objects = ContractCells.objects.filter(parent_structure_id=current_class.id, code=code,
                                                   name_id__in=[no.name_id for no in new_objects])
        for no in new_objects:
            # Регистрация создания реквизитов
            oc = general_reg_data.copy()
            oc['id'] = no.id
            oc['name'] = no.name_id
            oc['value'] = no.value
            reg = {'json': oc}
            reg_funs.simple_reg(object_user.id, 13, timestamp, transact_id, parent_transact, **reg)
            if no.delay:
                del oc['value']
                oc['delay'] = no.delay
                date_update = datetime.strptime(no.delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
                delay_ppa = True if date_update < timestamp else False
                if delay_ppa:
                    date_delay = date_update
                    no.delay[-1]['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                    no.save()
                else:
                    date_delay = None
                ic = oc.copy()
                ic['delay'] = []
                reg = {'json': oc, 'json_income': ic, 'date_delay': date_delay}
                reg_funs.simple_reg(object_user.id, 22, timestamp, transact_id, **reg)
                current_param = next(cp for cp in class_params if cp['id'] == no.name_id)
                interface_procedures.make_task_4_delay(current_param, no, 'c', object_user, timestamp, delay_ppa,
                                                       transact_id)  # Создаем / регистрируем таск

    saved_queryset = ContractCells.objects.filter(parent_structure_id=current_class.id, code=code)
    saved_obj = None
    if tps_all:
        # Проверим бизнес-правила и LinkMapы ТПсов
        for tak, tav in tps_all.items():
            if tav['changed']:
                my_tp = next(tp for tp in tps if tp['id'] == tak)
                edit_tp(my_tp, tav, code, current_class, class_params, timestamp, parent_transact, object_user.id)

    # для контрактов отработаем системные поля
    if current_class.formula == 'contract':
        event_kind = params['event_kind'] if 'event_kind' in params else ['u']
        if not saved_obj:
            saved_obj = convert_funs2.get_full_object(saved_queryset, current_class, class_params, 'contract')

        # 1. отработаем бизнес-правило
        if event_kind != ['r']:
            biz_rule = next(sp for sp in system_params if sp['name'] == 'business_rule')
            if not do_business_rule(biz_rule, saved_obj, object_user.id):
                raise Exception('Ошибка. Не выполняется бизнес-правило контракта<br>')

        # 2. выполним линкМап
        linkmap = next(sp for sp in system_params if sp['name'] == 'link_map')
        if linkmap['value']:
            do_linkmap(linkmap['value'], saved_obj, event_kind, timestamp, transact_id, object_user.id, *list_contracts)

        # выполним триггер
        trigger = next(sp for sp in system_params if sp['name'] == 'trigger')
        if trigger['value']:
            objs = [saved_obj]
            convert_funs.deep_formula(trigger, objs, object_user.id, True)
            rex(saved_obj[trigger['id']]['value'])
    return saved_queryset


@transaction.atomic()
def new_contract(current_class, class_params, system_params, objects, object_user, timestamp, tps, parent_transact, *list_contracts):
    if current_class.id in list_contracts:
        rex('Ошибка. Наблюдается циклическая ссылочность в цепочке линкмапов контрактов')
    else:
        list_contracts = list(list_contracts)
        list_contracts.append(current_class.id)
    code = objects[0].code
    transact_id = app.functions.reg_funs.get_transact_id(current_class.id, code, 'c')
    ContractCells.objects.bulk_create(objects)
    new_reqs = ContractCells.objects.filter(parent_structure_id=current_class.id, code=code)
    # для контрактов отработаем системные поля
    if current_class.formula == 'contract':
        saved_obj = convert_funs2.get_full_object(new_reqs, current_class, class_params, 'contract')

        # 1. отработаем бизнес-правило
        biz_rule = next(sp for sp in system_params if sp['name'] == 'business_rule')
        if biz_rule['value'] and not do_business_rule(biz_rule, saved_obj, object_user.id):
            raise Exception('Ошибка. Не выполняется бизнес-правило контракта<br>')

        # 2. выполним линкМап
        linkmap = next(sp for sp in system_params if sp['name'] == 'link_map')
        if linkmap['value']:
            do_linkmap(linkmap['value'], saved_obj, ('m', ), timestamp, transact_id, object_user.id, *list_contracts)

        # выполним триггер
        trigger = next(sp for sp in system_params if sp['name'] == 'trigger')
        objs = [saved_obj]
        if trigger['value']:
            convert_funs.deep_formula(trigger, objs, object_user.id, True)
            rex(saved_obj[trigger['id']]['value'])

    # # регистрация создания объекта
    outcoming = {'class_id': current_class.id, 'location': 'contract', 'type': current_class.formula, 'code': code}
    reg = {'json': outcoming}
    reg_funs.simple_reg(object_user.id, 5, timestamp, transact_id, parent_transact, **reg)
    control_fields = [t['cf'] for t in tps]

    # Регистрация реквизитов объекта
    for nr in new_reqs:
        outcom = model_to_dict(nr)
        del outcom['code']
        del outcom['parent_structure']
        outcom.update(outcoming)
        if nr.delay:
            outcom_delay = deepcopy(outcom)
            del outcom_delay['value']
            reg_delay = {'json': outcom_delay}
            reg_funs.simple_reg(object_user.id, 22, timestamp, transact_id, **reg_delay)
            current_param = next(cp for cp in class_params if cp['id'] == nr.name_id)
            # Создаем / регистрируем таск
            prms = {}
            if nr.name_id in control_fields:
                prms['cf'] = True
            interface_procedures.make_task_4_delay(current_param, nr, 'c', object_user, timestamp, False, transact_id, **prms)
        del outcom['delay']
        reg = {'json': outcom}
        reg_funs.simple_reg(object_user.id, 13, timestamp, transact_id, parent_transact, **reg)
    # cохраним техпроцессы
    for tp in tps:
        try:
            control_field = next(nop for nop in new_reqs if nop.name_id == tp['cf'])
        except StopIteration:
            val = {'fact': 0, 'delay': []}
        else:
            val = control_field.value if control_field.value else 0
            val = {'fact': val, 'delay': []}
        first_stage = TechProcessObjects(parent_structure_id=tp['id'], parent_code=code,
                                         name_id=tp['stages'][0]['id'], value=val)
        first_stage.save()
        outc = model_to_dict(first_stage)
        outc['class_id'] = outc['parent_structure']
        del outc['parent_structure']
        outc['code'] = outc['parent_code']
        del outc['parent_code']
        outc['location'] = 'contract'
        outc['type'] = 'tp'
        reg = {'json': outc}
        trans_tp = reg_funs.get_transact_id(tp['id'], code, 'p')
        reg_funs.simple_reg(object_user.id, 13, timestamp, trans_tp, transact_id, **reg)

    return new_reqs


@transaction.atomic()
def prepare_to_delete_object(lm, tr, del_obj, ts, parent_transact, user_id):
    if lm:
        do_linkmap(lm, del_obj, ['r'], ts, parent_transact, user_id)
    if tr['value']:
        convert_funs.deep_formula(tr, [del_obj], user_id, True)
        trigger_res = del_obj[tr['id']]['value']
        rex(trigger_res)


def do_linkmap(linkmap, parent_obj, event_kind, timestamp, parent_transact, user_id, *list_contracts, **params):
    objs = [parent_obj]
    list_contracts = list(list_contracts)
    tp = params['tp'] if 'tp' in params else None
    for lm in linkmap:
        # Проверка выполнения линкмапа в соответствии с типом события
        for ek in lm['event_kind']:
            if ek in event_kind:
                break
        else:
            continue
        # для техпроцессов. Проверка соответствия стадии
        if tp:
            for tpk, tpv in tp.items():
                if tpk in lm['stages'] and tpv['delta']:
                    break
            else:
                continue

        is_contract = not 'loc' in lm or lm['loc'] == 'c'
        location = 'contract' if is_contract else 'table'
        child_objs = []
        if not lm['code'] and lm['method'] != 'n':
            rex('Ошибка. Некорректно задан код объекта в ЛинкМап<br>')
        try:
            code = int(lm['code'])
        except ValueError:
            if lm['code']:
                header = {'id': 0, 'name': 'my_name', 'value': lm['code']}
                convert_funs.deep_formula(header, objs, user_id, is_contract)
                res = parent_obj[0]['value']
                parent_obj.pop(0)
                try:
                    code = int(res)
                except ValueError:
                    formula = f'[[{location}.{lm["class_id"]}.{lm["code"]}]]'
                    header = {'id': 0, 'name': 'my_name', 'value': formula}
                    convert_funs.deep_formula(header, objs, user_id, is_contract)
                    child_objs = parent_obj[0]['value']
                    rex(child_objs)
                    parent_obj.pop(0)
                    if not child_objs and not lm['method'] in ['n', 'en']:
                        rex('Ошибка. Некорректно указан код объекта в ЛинкМап<br>')
                    code = None
            else:
                code = None
        if code:
            object_manager = ContractCells.objects if is_contract else Objects.objects
            class_manager = Contracts.objects if is_contract else Designer.objects
            child_obj = object_manager.filter(parent_structure_id=lm['class_id'], code=code)
            headers = class_manager.filter(parent_id=lm['class_id'], system=False).values()
            current_class = class_manager.get(id=lm['class_id'])
            child_obj = convert_funs2.get_full_object(child_obj, current_class, headers, location)
            child_objs.append(child_obj)
        # Вычислим значение параметров - мапирование
        if lm['method'] != 'n':
            for p in lm['params']:
                header = {'id': 0, 'name': 'my_name', 'value': p['value']}
                convert_funs.deep_formula(header, objs, user_id, True)
                p['result'] = parent_obj[0]['value']
                rex(p['result'])
                parent_obj.pop(0)
        if lm['method'] in ['n', 'en']:
            for p in lm['create_params']:
                header = {'id': 0, 'name': 'my_name', 'value': p['value']}
                convert_funs.deep_formula(header, objs, user_id, True)
                p['result'] = parent_obj[0]['value']
                rex(p['result'])
                parent_obj.pop(0)
        params = {'timestamp': timestamp, 'parent_transact': parent_transact}

        def method_new():
            for p in lm['create_params']:
                params[str(p['id'])] = p['result']
            return api_funs.create_object(lm['class_id'], user_id, location, None, *list_contracts, **params)

        def method_edit(child_obj):
            for p in lm['params']:
                if p['sign'] == 'e':
                    val = p['result']
                elif p['sign'] == '+':
                    old_val = child_obj[p['id']]['value'] if child_obj[p['id']]['value'] else 0
                    val = old_val + p['result']
                else:
                    old_val = child_obj[p['id']]['value'] if child_obj[p['id']]['value'] else 0
                    val = old_val - p['result']
                params[str(p['id'])] = val
            return api_funs.edit_object(lm['class_id'], child_obj['code'], user_id, location, None, *list_contracts, **params)

        if lm['method'] == 'n':
            result = method_new()
            rex(result)
        elif lm['method'] == 'e':
            result = method_edit(child_objs[0])
            rex(result)
        elif lm['method'] == 'en':
            if child_objs:
                result = method_edit(child_objs[0])
                rex(result)
            else:
                result = method_new()
                rex(result)
        elif lm['method'] == 'wo':
            for p in lm['params']:
                is_wo = False
                for co in child_objs:
                    delta = co[p['id']]['value'] - p['result']
                    prms = params.copy()
                    if delta >= p['limit']:
                        prms[str(p['id'])] = delta
                        is_wo = True
                    else:
                        p['result'] -= co[p['id']]['value']
                        prms[str(p['id'])] = p['limit']
                    result = api_funs.edit_object(lm['class_id'], co['code'], user_id, location, None, *list_contracts, **prms)
                    rex(result)
                    if is_wo:
                        break
                if not is_wo and p['value'] > 0:
                    rex('Ошибка. ЛинкМап не может выполнить списание. На объектах-потомках недостаточно данных<br>')

        # пакетное редактирование
        else:
            for co in child_objs:
                result = method_edit(co)
                rex(result)


# Устарела Удалить после 01.05.2025
@transaction.atomic()
def edit_tp(tp_info, tp_data, code, parent_class, parent_headers, timestamp, parent_transact, user_id):
    user_data = get_user_model().objects.get(id=user_id)

    interface_procedures.save_tp(tp_info, tp_data, code, user_data, timestamp, parent_transact)

    biz_ruls = None; link_map = None; triggers = None
    for sp in tp_info['system_params']:
        if sp['name'] == 'business_rule':
            biz_ruls = deepcopy(sp['value'])
        elif sp['name'] == 'link_map':
            link_map = deepcopy(sp['value'])
        elif sp['name'] == 'trigger':
            triggers = deepcopy(sp['value'])

    # БиРуЛиМаТры
    if biz_ruls or link_map or triggers:
        parent_queryset = ContractCells.objects.filter(parent_structure_id=tp_info['parent_id'], code=code)
        parent_obj = convert_funs2.get_full_object(parent_queryset, parent_class, parent_headers, 'contract')
        if biz_ruls:
            if not contract_procedures.check_tp_biz_rulz(tp_data, biz_ruls, parent_obj, user_id, 'd'):
                raise Exception(f'Не выполняется бизнес-правило техпроцесса ID: {tp_info["id"]}')
        if link_map:
            do_linkmap(link_map, parent_obj, 'd', timestamp, parent_transact, user_id, tp=tp_data['new_stages'])
        if triggers:
            if not contract_procedures.check_tp_biz_rulz(tp_data, triggers, parent_obj, user_id, 'd', False):
                raise Exception(f'Не выполняется триггер техпроцесса ID: {tp_info["id"]}')


def do_tp_birulimators(tp_info, parent_class,  parent_headers, code, event_type, tp_data, user_id, timestamp, parent_transact):
    # 2. Выполняем бирулиматоры
    biz_ruls = None
    link_map = None
    triggers = None
    for sp in tp_info['system_params']:
        if sp['name'] == 'business_rule':
            biz_ruls = deepcopy(sp['value'])
        elif sp['name'] == 'link_map':
            link_map = deepcopy(sp['value'])
        elif sp['name'] == 'trigger':
            triggers = deepcopy(sp['value'])

    if biz_ruls or link_map or triggers:
        parent_queryset = ContractCells.objects.filter(parent_structure_id=tp_info['parent_id'], code=code)
        parent_obj = convert_funs2.get_full_object(parent_queryset, parent_class, parent_headers, 'contract')
        if biz_ruls:
            if not contract_procedures.check_tp_biz_rulz(tp_data, biz_ruls, parent_obj, user_id, event_type):
                raise Exception(f'Не выполняется бизнес-правило техпроцесса ID: {tp_info["id"]}')
        if link_map:
            do_linkmap(link_map, parent_obj, event_type, timestamp, parent_transact, user_id, tp=tp_data['new_stages'])
        if triggers:
            if not contract_procedures.check_tp_biz_rulz(tp_data, triggers, parent_obj, user_id, event_type, False):
                raise Exception(f'Не выполняется триггер техпроцесса ID: {tp_info["id"]}')