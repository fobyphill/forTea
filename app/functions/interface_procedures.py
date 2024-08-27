import json
import re
import copy
from datetime import datetime, date

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Subquery
from django.forms import model_to_dict

from app.functions import tree_funs, view_procedures, task_funs, reg_funs, update_funs, convert_funs, session_funs, \
    interface_funs
from app.models import Dictionary, Contracts, Designer, ContractCells, Objects, TechProcessObjects, RegistratorLog


# Причесать словарь черновика для сохранения
def convert_draft_dict(k, v):
    if re.match(r'chb', k):
        val = json.loads(v.lower())
    elif re.match(r'i_float', k):
        val = float(v) if v else None
    elif re.match(r'(i_link|s_alias)', k):
        val = int(v) if v else None
    elif re.match(r'dict_info', k):
        json_dict = json.loads(v) if v else None
        if json_dict:
            dict_id = json_dict['id']
            del json_dict['id']
            if json_dict:
                output_dict = {}
                dict_headers = Dictionary.objects.filter(parent_id=dict_id)
                for kk, vv in json_dict.items():
                    try:
                        kk = int(kk)
                    except ValueError:
                        continue
                    dh = next(dh for dh in dict_headers if dh.id == kk)
                    output_dict[kk] = {'value': vv}
                    output_dict[kk]['name'] = dh.name
                    output_dict[kk]['type'] = dh.formula
            else:
                output_dict = None
            json_dict = output_dict
        val = json_dict
    else:
        val = v
    return val


# валидация ветки
def valid_branch(request, tree_id, is_contract=False):
    message = ''
    is_valid = True
    branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
    if branch_code:
        tree = request.session['temp_object_manager']['tree']
        branch = tree_funs.find_branch(tree, 'code', branch_code)
        if not branch:
            class_id = request.session['temp_object_manager']['tree_headers'][0]['parent_id']
            branch = tree_funs.antt(branch_code, tree, class_id, request.session['temp_object_manager']['headers'],
                                    request.user.id, is_contract)
        # проверим корректность введенного кода ветки
        if not branch:
            is_valid = False
            message = 'Код ветки указан некорректно\n'
    else:
        branch = None
    manager = Contracts.objects if is_contract else Designer.objects
    is_right_tree = manager.get(parent_id=tree_id, formula='bool', name='is_right_tree')
    if is_right_tree.value:
        if not branch:
            is_valid = False
            message += 'В правильном дереве объект можно прикрепить только к ветвям нижнего уровня\n'
        elif 'children' in branch:
            is_valid = False
            message += 'В правильном дереве объект можно прикрепить только к ветвям нижнего уровня\n'
    return is_valid, branch, message


# Проверка корректности ветки. Если такой ветки в дереве нет, то сделать активной ветку активного объекта
def check_branch(request, is_contract=False):
    if 'i_branch' in request.POST:
        if request.POST['i_branch']:
            b_c = int(request.POST['i_branch'])  # код ветки
            # Проверим, есть ли ветка с таким кодом в дереве
            tree = request.session['temp_object_manager']['tree']
            branch = tree_funs.find_branch(tree, 'code', b_c)
            if not branch:
                manager = ContractCells.objects if is_contract else Objects.objects
                cur_obj = manager.filter(parent_structure_id=int(request.GET['class_id']), name__name='parent_branch',
                                         code=request.POST['i_code'])
                if cur_obj and cur_obj[0].value:
                    branch = {'code': cur_obj[0].value}
                else:
                    branch = {'code': 0}
        else:
            branch = {'code': 0}
    elif 'branch_code' in request.POST:
        branch = {'code': int(request.POST['branch_code'])}
    else:
        branch = {'code': 0}
    return branch


def ver_def(class_type, param_type, default, link_type=None, link_id=None):
    if (param_type == 'float' and not type(default) in (float, int)) or \
            (param_type == 'string' and not type(default) is str) or \
            (param_type == 'bool' and not type(default) is bool) or \
            (param_type in ('link', 'const') and not type(default) is int and class_type != 'dict') or \
            (param_type == 'datetime' and not isinstance(default, datetime)) or \
            (param_type == 'date' and not isinstance(default, date)):
        return 'Некорректно задано поле Default\n'
    if class_type == 'dict' and param_type == 'enum':
        if not type(default) is list:
            return 'Некорректно задано поле Default. Необходимо задать непустой список строк\n'
        else:
            for pd in default:
                if not type(pd) is str:
                    return 'Некорректно задано поле Default. Необходимо задать непустой список строк\n'
    # Отдельно проверим дефолт для константы
    if param_type == 'const':
        alias_manager = Contracts.objects if link_type == 'contract' else Designer.objects
        if not alias_manager.filter(parent_id=link_id, id=default, formula='eval'):
            return 'некорректно задано значение Default для типа данных "const". Укажите ID одного из параметров выбранной константы'
    # проверим дефолт для ссылки
    elif param_type == 'link' and class_type != 'dict':
        link_manager = ContractCells.objects if link_type == 'contract' else Objects.objects
        if not link_manager.filter(parent_structure_id=link_id, code=default):
            return 'некорректно задано значение Default для типа данных "link". Укажите код одного из объектов класса-родителя'
    elif param_type == 'link' and class_type == 'dict':
        if not cdl(default):
            return 'Некорректно задано поле Default для типа данных link словаря'
    return 'ok'


# cdl - check dict link
def cdl(str_link):
    array_link = re.match(r'^(table|contract)\.(\d+)\.(\d*)', str_link)
    if not array_link:
        return False
    try:
        link_id = int(array_link[2])
    except ValueError:
        return False
    if array_link[3]:
        try:
            code_default = int(array_link[3])
        except ValueError:
            return False
    # Проверим существование ссылочного класса
    manager = Designer.objects if array_link[1] == 'table' else Contracts.objects
    parent_class = manager.filter(id=link_id, formula=array_link[1])
    if not parent_class:
        return False
    else:
        parent_class = parent_class[0]
    # Проверим существование ссылочного объекта
    if array_link[3]:
        obj_manager = Objects.objects if array_link[1] == 'table' else ContractCells.objects
        obj = obj_manager.filter(parent_structure_id=link_id, code=code_default)
        if not obj:
            return False
    return True


# mtp = make TechProcess
# input: object_control_field - запись объекта со значением контрольного поля, stages - запись TechProcess
def mtp(object_control_field, stages):
    counter = 0
    for s in stages.value:
        if counter == 0:
            fact = object_control_field.value
        else:
            fact = 0
        counter += 1
        dict_value = {'fact': fact, 'delay': [], 'stage': s}
        TechProcessObjects(parent_code=object_control_field.code, parent_structure_id=stages.parent_id,
                           name_id=stages.id, value=dict_value).save()


def check_delay_value(request, field_id, k):  # Проверка делэйного значения
    delay_value = None
    date_delay_key = 'i_datetime_' + str(field_id) + '_delay_datetime'
    date_delay_value = None
    if date_delay_key in request.POST and request.POST[date_delay_key]:
        date_delay_value = request.POST[date_delay_key]
        delay_key = k + '_delay'
        try:
            delay_value = request.POST[delay_key]
        except KeyError:
            pass
        else:
            delay_value = view_procedures.convert_in_json(delay_key, delay_value)
    return delay_value, date_delay_value


def make_task_4_delay(class_param, object, loc, user, timestamp, delay_ppa=False, parent_transact=None, **params):
    delay = class_param['delay_settings'] if loc == 't' else class_param['delay']
    data = {'class_id': class_param['parent_id'], 'location': loc, 'code': object.code, 'name_id': object.name_id,
            'delay': object.delay[-1]['value'], 'sender_id': user.id,
            'sender_fio': user.first_name + ' ' + user.last_name}
    if 'cf' in params:
        data['cf'] = params['cf']
    handler = delay['handler'] if 'handler' in delay and delay['handler'] and type(delay['handler']) is int else None
    date_delay_datetime = datetime.strptime(object.delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
    task = task_funs.make_task4prop(user.id, data, handler, date_delay_datetime, timestamp=timestamp,
                                    parent_transact=parent_transact, **params)
    if delay_ppa and task.date_done:
        update_funs.run_delays([task, ])


# iscrh = if stage change rewrite history
# Если было переименование стадии техпроцесса - то изменим это название везде в объектах и истории
def iscrh(tp_id, old_lm, new_lm):
    index = 0
    for ol in old_lm:
        nl = new_lm[index]
        index += 1
        if ol['name'] != nl['name']:
            # Изменим объекты
            tps = TechProcessObjects.objects.filter(parent_structure_id=tp_id, value__stage=ol['name'])
            for tp in tps:
                tp.value['stage'] = nl['name']
            while(tps):
                tps4update = tps[:1000]
                tps = tps[1000:]
                TechProcessObjects.objects.bulk_update(tps4update, ('value',), 1000)
            # перепишем историю
            hist = RegistratorLog.objects.filter(reg_name_id=15, json__type='techprocess', json__location='contract',
                                                 json__value__stage=ol['name'])
            for h in hist:
                h.json['value']['stage'] = nl['name']
            while(hist):
                hist4upd = hist[:1000]
                hist = hist[1000:]
                RegistratorLog.objects.bulk_update(hist4upd, ('json',), 1000)
            hist = RegistratorLog.objects.filter(reg_name_id__in=(15,16), json_income__type='techprocess', json_income__location='contract',
                                                 json_income__value__stage=ol['name'])
            for h in hist:
                h.json_income['value']['stage'] = nl['name']
            while(hist):
                hist4upd = hist[:1000]
                hist = hist[1000:]
                RegistratorLog.objects.bulk_update(hist4upd, ('json_income',), 1000)

# rhwpd = rewrite history with ppa delay
def rhwpd(location, class_type, date_start, delay_event, req, user_id, transact_id):
    # 1. Создадим событие в истории с учетом существующих делеев
    base = RegistratorLog.objects.filter(json_class=req.parent_structure_id, json__code=req.code, json__location=location,
                                         reg_name_id=22)
    last_delay = base.filter(date_update__lte=date_start).order_by('-date_update', '-id')[:1]
    if last_delay:
        inc = last_delay[0].json
        outc = copy.deepcopy(inc)
        outc['delay'].append(delay_event)
    else:
        inc = {'class_id': req.parent_structure_id, 'code': req.code, 'location': location, 'delay': [], 'id': req.id,
               'name': req.name_id, 'type': class_type}
        outc = copy.deepcopy(inc)
        outc['delay'].append(delay_event)
    reg = {'json': outc, 'json_income': inc}
    reg_funs.simple_reg(user_id, 22, date_start, transact_id, **reg)

    # 2. Добавили событие делэя во все последующие события
    hist = base.filter(date_update__gt=date_start)
    if hist:
        for h in hist:
            if type(h.json_income['delay']) is list:
                h.json_income['delay'].append(delay_event)
            else:
                h.json_income['delay'] = [delay_event, ]
            if type(h.json['delay']) is list:
                h.json['delay'].append(delay_event)
            else:
                h.json['delay'] = [delay_event, ]
        RegistratorLog.objects.bulk_update(hist, ['json', 'json_income'])


# rohatiw = robot-handler talk its word
def rohatiw(dofr, class_id, code, current_param, class_params, object_params, user_id, is_contract=False):
    # dofr - dict object from request - современное значение объекта из реквеста еще не сохраненного объекта
    settings_name = 'delay' if is_contract else 'delay_settings'
    header = {'value': current_param[settings_name]['handler'],
              'id': current_param['id'] * -1, 'name': current_param['name'] + '_handler'}
    obj = mofr(code, class_id, class_params, dofr, object_params, is_contract)
    convert_funs.deep_formula(header, (obj,), user_id, is_contract)
    handler_result = obj[current_param['id'] * -1]['value']
    if handler_result and not (type(handler_result) is str and len(handler_result) > 6
                               and handler_result[:6] == 'Ошибка'):
        return True
    else:
        return False


# mofr = make object from request
# params = {'tps': [{'id'}]}
def mofr(code, class_id, headers, dict_object, old_object, is_contract=True, **params):

    def convert_data(header, var):
        if header['formula'] == 'bool':
            if not var:
                var = False
            elif type(var) is not bool:
                var = json.loads(var.lower())
        elif header['formula'] == 'float':
            var = float(var) if var else 0
        elif h['formula'] in ('link', 'const'):
            var = int(var) if var else None
        return var

    tps = params['tps'] if 'tps' in params else None
    presaved_object = {'code': code, 'parent_structure': class_id}
    dict_keys = {'string': 'ta_', 'link': 'i_link_', 'float': 'i_float_', 'datetime': 'i_datetime_',
                 'date': 'i_date_', 'bool': 'chb_', 'const': 's_alias_', 'enum': 's_enum_'}
    obj_model = ContractCells if is_contract else Objects
    for h in headers:
        if code:
            try:
                old_req = next(oo for oo in old_object if oo.name_id == h['id'])
            except StopIteration:
                old_req = obj_model(value=None, delay=[])
        else:
            old_req = obj_model(value=None, delay=[])
        if h['name'] == 'system_data' and is_contract:
            continue
        if h['formula'] in ('eval', 'file', 'array'):
            continue
        pure_key = str(h['id'])
        key = dict_keys[h['formula']] + pure_key
        # Работаем со значениями
        if key in dict_object:
            val = dict_object[key]
        elif pure_key in dict_object:
            val = dict_object[pure_key]
        else:
            val = old_req.value
        val = convert_data(h, val)

        # Работаем с делэем
        if is_contract:
            is_delay = h['delay']['delay'] if h['delay'] else False
        else:
            is_delay = h['delay'] if h['delay'] else False
        delay = old_req.delay.copy() if old_req.delay else []
        if is_delay:
            key_date_delay = 'i_datetime_' + pure_key + '_delay_datetime'
            api_key_dd = pure_key + '_delay_date'
            if key_date_delay in dict_object and dict_object[key_date_delay] \
                    or api_key_dd in dict_object and dict_object[api_key_dd]:
                key_delay = key + '_delay'
                pure_key_delay = pure_key + '_delay'
                new_delay = dict_object[key_delay] if key_delay in dict_object else dict_object[pure_key_delay]
                new_delay = convert_data(h, new_delay)
                new_date_delay = dict_object[key_date_delay] if key_date_delay in dict_object else dict_object[api_key_dd]
                new_delay = {'value': new_delay, 'date_update': new_date_delay}
                delay.append(new_delay)
        presaved_object[h['id']] = {'value': val, 'delay': delay}

    # добавим техпроцессы
    if tps:
        presaved_object['tps'] = {}
        for tp in tps:
            old_stages = TechProcessObjects.objects.filter(parent_structure_id=tp['id'], parent_code=code)
            presaved_object['tps'][tp['id']] = {}
            counter = 0
            for s in tp['stages']:
                stage_key = 'i_stage_' + str(s['id'])
                new_state = float(dict_object[stage_key]) if stage_key in dict_object and dict_object[stage_key] else 0
                try:
                    old_stage = next(os for os in old_stages if os.name_id == s['id'])
                except StopIteration:
                    old_fact = 0
                else:
                    old_fact = old_stage.value['fact'] if old_stage.value['fact'] else 0
                new_delay = new_state - old_fact
                presaved_object['tps'][tp['id']][s['id']] = {'state': new_state, 'fact': old_fact, 'delay': new_delay}
                counter += 1
    return presaved_object


# Техпроцессы. Валидация, проверка изменений
def check_changes_tps(tps, code, params):
    tps_all = {}
    message = ''
    tps_chng = False
    tps_valid = True
    def make_stages(list_stage):
        output_dict = {}
        for ls in list_stage:
            val = {'fact': 0, 'delay': []}
            output_dict[ls] = val
        return output_dict
    for tp in tps:
        dictp = {}

        # Формируем старые стадии
        if code:
            old_stages = list(TechProcessObjects.objects.filter(parent_structure_id=tp['id'], parent_code=code)
                              .values('name_id', 'value'))
            old_stages_dict = {}
            old_stages_ids = []
            if old_stages:
                for os in old_stages:
                    old_stages_dict[os['name_id']] = os['value']
                    old_stages_ids.append(os['name_id'])
            else:
                # Если по какой-то причине потеряны данные о техпроцессе - заполним его так: первая стадия = КП. Остальные пустые
                first_stage = tp['stages'][0]
                try:
                    cf_old = ContractCells.objects.get(parent_structure_id=tp['parent_id'], code=code,
                                                       name_id=tp['cf'])
                except ObjectDoesNotExist:
                    cf_old_val = 0
                else:
                    cf_old_val = cf_old.value
                old_stages_dict[first_stage['id']] = {'fact': cf_old_val, 'delay': []}
                old_stages_ids.append(first_stage['id'])
            absent_stages = [s['id'] for s in tp['stages'] if s['id'] not in old_stages_ids]
            old_stages_dict.update(make_stages(absent_stages))
        else:
            old_stages_dict = make_stages([s['id'] for s in tp['stages']])
        dictp['old_stages'] = old_stages_dict
        # формируем новые стадии
        new_stages = {}
        stages_ids = ['i_stage_' + str(s['id']) for s in tp['stages']]
        for k, v in params.items():
            if k in stages_ids:
                new_stages[int(k[8:])] = {'value': float(v) if v else 0}
        dictp['new_stages'] = new_stages
        dictp['changed'] = False
        for k, old_v in dictp['old_stages'].items():
            old_value = old_v['fact'] + sum([od['value'] for od in old_v['delay']])
            if k in dictp['new_stages']:
                if old_value != dictp['new_stages'][k]['value']:
                    dictp['changed'] = True
                    tps_chng = True
                    dictp['new_stages'][k]['delta'] = dictp['new_stages'][k]['value'] - old_value
                else:
                    dictp['new_stages'][k]['delta'] = 0
            else:
                dictp['new_stages'][k] = {'delta': 0, 'value': old_value}

        tps_all[tp['id']] = dictp
        # Вычисляем базовое ТП - все стадии = КП
        if dictp['changed']:
            cf_key = 'i_float_' + str(tp['cf'])
            if cf_key not in params:
                cf = ContractCells.objects.filter(parent_structure_id=tp['parent_id'], code=code, name_id=tp['cf'])
                if cf:
                    cf_fact = cf[0].value
                else:
                    cf_fact = 0
            else:
                cf_fact = float(params[cf_key]) if params[cf_key] else 0

            if cf_fact != sum([v['value'] for v in dictp['new_stages'].values()]):
                tps_valid = False
                message += 'Изменения в техпроцессе ' + str(tp['id']) + \
                           ' некорректны. Сумма всех этапов должна рваняться контрольному полю<br>'
            else:
                # Калькулятор маршрутизации
                is_first_stage = True
                cf_old_val = sum(ost['fact'] + sum(d['value'] for d in ost['delay']) for ost in dictp['old_stages'].values())
                cf_delta = cf_fact - cf_old_val
                dictp['cf_delta'] = cf_delta
                valid_delta = True
                for k, v in dictp['new_stages'].items():
                    if is_first_stage:
                        is_first_stage = False
                        if cf_delta:
                            v['valid_delta'] = True
                            v['delta'] -= cf_delta
                            continue
                    if not v['delta']:
                        v['valid_delta'] = True
                    if 'valid_delta' in v and v['valid_delta']:
                        continue
                    if v['delta'] < 0:
                        old_stage = next(ost['value'] for ost in old_stages if ost['name_id'] == k)
                        old_delay = sum(d['value'] for d in old_stage['delay'])
                        old_state = old_stage['fact'] + old_delay if old_delay < 0 else old_stage['fact']
                        if v['delta'] + old_state < 0:
                            valid_delta = False
                            break
                        partners = next(s['value']['children'] for s in tp['stages'] if s['id'] == k)
                    else:
                        partners = [s['id'] for s in tp['stages'] if k in s['value']['children']]
                    partners_deltas = sum(dictp['new_stages'][p]['delta'] for p in partners)
                    if partners_deltas * -1 == v['delta']:
                        v['valid_delta'] = True
                        for p in partners:
                            dictp['new_stages'][p]['valid_delta'] = True
                else:
                    for k, v in dictp['new_stages'].items():
                        if not 'valid_delta' in v:
                            valid_delta = False
                            break
                if not valid_delta:
                    message += 'Изменения в техпроцессе ' + str(tp['id']) + \
                               ' некорректны. Имеются нарушения целостности данных<br>'
                    tps_valid = False
    return tps_all, tps_chng, tps_valid, message


# Сохраним техпроцессы
def save_tps(tps, tps_all, code, user_data, timestamp, parent_trans):
    for ta_k, ta_v in tps_all.items():
        if ta_v['changed']:
            tp_info = next(t for t in tps if t['id'] == ta_k)
            stages = TechProcessObjects.objects.filter(parent_structure_id=ta_k, parent_code=code)
            if not stages:
                val = {'fact': 0, 'delay': []}
                stages_0 = TechProcessObjects(parent_structure_id=ta_k, parent_code=code,
                                              name_id=tp_info['stages'][0]['id'], value=val)
                stages = [stages_0]
            task_code = None;
            task_transact = None
            tp_trans = reg_funs.get_transact_id(ta_k, code, 'p')
            # Если было изменение контрольного поля - внесем изменение в первую стадию
            if ta_v['cf_delta']:
                stage_0 = stages[0]
                inc_val = copy.deepcopy(stage_0.value)
                inc = {'class_id': ta_k, 'type': 'tp', 'location': 'contract', 'code': code,
                       'name': stage_0.name_id, 'id': stage_0.id, 'value': inc_val}
                outc_val = copy.deepcopy(stage_0.value)
                outc_val['fact'] += ta_v['cf_delta']
                stage_0.value = outc_val
                stage_0.save()
                outc = inc.copy()
                outc['value'] = outc_val
                reg = {'json': outc, 'json_income': inc}
                reg_funs.simple_reg(user_data.id, 15, timestamp, tp_trans, parent_trans, **reg)
            for k, v in ta_v['new_stages'].items():
                if v['delta']:
                    stage_info = next(s for s in tp_info['stages'] if s['id'] == k)
                    stage = None
                    try:
                        stage = next(s for s in stages if s.name_id == k)
                    except StopIteration:
                        stage = TechProcessObjects(parent_structure_id=ta_k, parent_code=code, name_id=k,
                                                   value={'fact': 0, 'delay': []})
                    finally:
                        if not task_code:
                            task_code, task_transact = task_funs.reg_create_task(user_data.id, timestamp, parent_trans)
                        new_delay = {'value': v['delta'],
                                     'date_create': datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S')}
                        inc = {'class_id': ta_k, 'type': 'tp', 'location': 'contract', 'code': code,
                               'name': k, 'value': copy.deepcopy(stage.value)}
                        stage.value['delay'].append(new_delay)
                        stage.save()
                        # Регистрация изменений
                        outc = inc.copy()
                        outc['value'] = stage.value
                        reg = {'json': outc, 'json_income': inc}
                        reg_funs.simple_reg(user_data.id, 15, timestamp, tp_trans, parent_trans, **reg)
                        # Создаем таск
                        delay = sum(d['value'] for d in stage.value['delay'])
                        sender_fio = user_data.first_name + ' ' + user_data.last_name
                        task_funs.mt4s(code, stage_info['value']['handler'], user_data.id, sender_fio,
                                       stage.value['fact'], delay + stage.value['fact'], delay, v['delta'],
                                       stage.name_id, task_code, tp_info, timestamp, task_transact, parent_trans)
            if task_code:
                task_funs.do_task2(task_code, user_data.id, timestamp, task_transact, parent_trans)


# Упаковать видимые заголовки и список видимых айди для базового наполнения объектов
def pack_vis_headers(current_class, headers, is_contract=False):
    is_main_name = False
    visible_headers = []
    vhids = []
    if is_contract:
        main_name = 'system_data' if current_class.formula == 'contract' else 'Собственник'
    else:
        main_name = 'Наименование' if current_class.formula == 'table' else 'Собственник'
    for h in headers:
        if h['is_visible']:
            visible_headers.append(h)
            vhids.append(h['id'])
            if h['name'] == main_name:
                is_main_name = True
        if len(vhids) == 5:
            break
    if not is_main_name:
        vhids.append(next(h['id'] for h in headers if h['name'] == main_name))
    return visible_headers, vhids


# marefo =make request from object
def marefo(class_id, owner_code, parent_object_id, user_id, is_contract, **params):
    dict_key_types = {'float': 'i_float_', 'bool': 'chb_', 'string': 'ta_', 'link': 'i_link_', 'date': 'i_date_',
                      'datetime': 'i_datetime_', 'file': 'i_filename_', 'const': 's_alias_', 'enum': 's_enum_'}
    class_manager = Contracts.objects if is_contract else Designer.objects
    headers = list(class_manager.filter(parent_id=class_id, system=False).values())
    obj_manager = ContractCells.objects if is_contract else Objects.objects
    obj_codes = obj_manager.filter(parent_structure_id=class_id, name__name='Собственник', value=owner_code).values('code').distinct()
    objs = obj_manager.filter(parent_structure_id=class_id, code__in=Subquery(obj_codes))
    objs = convert_funs.queyset_to_object(objs)

    class MyRequest:
        POST = {}
        FILES = {}
        session = {}
    my_request = MyRequest()
    for o in objs:
        copy_request = copy.deepcopy(my_request)
        for ok, ov in o.items():
            if ok in ('parent_structure', 'code', 'type'):
                continue
            my_key = dict_key_types[ov['type']] + str(ok)
            if ov['name'] == 'Собственник':
                ov['value'] = parent_object_id
            copy_request.POST[my_key] = str(ov['value'])
        if 'tps_info' in params:
            tps = get_new_tps(o['code'], params['tps_info'])
            for tp in tps:
                for s in tp['stages']:
                    val = s['value']['fact'] + sum(d['value'] for d in s['value']['delay'])
                    copy_request.POST['i_stage_' + str(s['id'])] = val
        interface_funs.make_graft(copy_request, class_id, headers, o['code'], user_id, is_contract, False, **params)


# marefrod = make request from dict
def marefrod(class_id, is_contract, **params):
    dict_key_types = {'float': 'i_float_', 'bool': 'chb_', 'string': 'ta_', 'link': 'i_link_', 'date': 'i_date_',
                      'datetime': 'i_datetime_', 'file': 'i_filename_', 'const': 's_alias_', 'enum': 's_enum_'}
    class_manager = Contracts.objects if is_contract else Designer.objects
    headers = list(class_manager.filter(parent_id=class_id, system=False).values())

    class my_user:
        id = 0
    class MyRequest:
        POST = {}
        FILES = {}
        session = {}
        user = my_user()

    my_request = MyRequest()
    my_request.POST['class_id'] = str(class_id)

    for pk, pv in params.items():
        if pk in ('parent_structure', 'type', 'location'):
            continue
        elif pk == 'code':
            my_request.POST['i_code'] = str(pv)
        elif re.match(r'array', pk):
            continue
        elif pk[:9] == 'dict_info':
            my_request.POST[pk] = pv
        else:
            header = next(h for h in headers if h['id'] == int(pk))
            my_key = dict_key_types[header['formula']] + str(pk)
            my_request.POST[my_key] = str(pv)
        if pk == 'tps_info':
            tps = get_new_tps(int(my_request.POST['i_code']), pv)
            for tp in tps:
                for s in tp['stages']:
                    val = s['value']['fact'] + sum(d['value'] for d in s['value']['delay'])
                    my_request.POST['i_stage_' + str(s['id'])] = val
    return my_request


# atid = add tp in draft
def atid(draft, tps, field_id, val):
    is_change = False
    int_field_id = int(field_id)
    for tp in tps:
        for s in tp['stages']:
            if s['id'] == int_field_id:
                tp_id = tp['id']
                cf = str(tp['cf'])
                break
        else:
            continue
        break
    else:
        return False
    str_tp_id = 'tp_id' + str(tp_id)
    val = float(val) if val else 0
    if str_tp_id in draft[cf]:
        old_val = draft[cf][str_tp_id][field_id] if field_id in draft[cf][str_tp_id] else 0
        if old_val != val:
            draft[cf][str_tp_id][field_id] = val
            is_change = True
    else:
        draft[cf][str_tp_id] = {field_id: val}
        is_change = True
    return is_change


def get_new_tps(item_code, tps):
    list_tps = []
    def complete_stages(stages, exist_ids, output_list):
        for s in stages:
            if s['id'] not in exist_ids:
                val = {'fact': 0, 'delay': []}
                new_s = {'id': s['id'], 'parent_code': item_code, 'parent_structure_id': s['parent_id'], 'name': s['name'],
                         'value': val}
                output_list.append(new_s)
        return sorted(output_list, key=lambda x: x['id'])

    for t in tps:
        exist_stages = TechProcessObjects.objects.filter(parent_structure_id=t['id'], parent_code=item_code)\
                            .select_related('name')
        exist_stages_ids = []
        list_es = []
        for es in exist_stages:
            des = model_to_dict(es)
            des['id'] = es.name_id
            des['name'] = es.name.name
            list_es.append(des)
            exist_stages_ids.append(es.name.id)
        if list_es:
            # Если есть записи техпроцессов - дозаполним пустые записи
            complete_stages(t['stages'], exist_stages_ids, list_es)
        else:
            # Если записей ТП нет - заполним заново
            stage_0 = t['stages'][0]
            try:
                control_field_val = ContractCells.objects.get(parent_structure_id=t['parent_id'], code=item_code,
                                                                 name_id=t['cf'])
            except ObjectDoesNotExist:
                cf_val = 0
            else:
                cf_val = control_field_val.value
            first_stage = {'id': stage_0['id'], 'parent_code': item_code, 'parent_structure_id': stage_0['parent_id'],
                           'name': stage_0['name'], 'value': {'fact': cf_val, 'delay': []}}
            list_es.append(first_stage)
            complete_stages(t['stages'], [stage_0['id']], list_es)
        dict_tp = {'id': t['id'], 'stages': list_es, 'control_field': t['cf']}
        list_tps.append(dict_tp)
    return list_tps