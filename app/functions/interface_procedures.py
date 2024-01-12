import json
import re
import copy
from datetime import datetime, date

from app.functions import tree_funs, view_procedures, task_funs, reg_funs, update_funs, convert_funs
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
            output_dict = {}
            dict_headers = Dictionary.objects.filter(parent_id=json_dict['id'])
            for kk, vv in json_dict.items():
                try:
                    kk = int(kk)
                except ValueError:
                    continue
                dh = next(dh for dh in dict_headers if dh.id == kk)
                output_dict[kk] = {'value': vv}
                output_dict[kk]['name'] = dh.name
                output_dict[kk]['type'] = dh.formula
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
def mofr(code, class_id, headers, dict_object, old_object, is_contract=True):
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
        if key in dict_object and dict_object[key]:
            val = dict_object[key]
        elif pure_key in dict_object and dict_object[pure_key]:
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
            if key_date_delay in dict_object and dict_object[key_date_delay]:
                new_delay = dict_object[key + '_delay']
                new_delay = convert_data(h, new_delay)
                new_delay = {'value': new_delay, 'date_update': dict_object[key_date_delay]}
                delay.append(new_delay)
        presaved_object[h['id']] = {'value': val, 'delay': delay}

    # добавим техпроцессы
    # if tps:
    #     presaved_object['tps'] = {}
    #     for tp in tps:
    #
    #         old_stages = TechProcessObjects.objects.filter(parent_structure_id=tp['id'], parent_code=code)
    #         presaved_object['tps'][tp['id']] = {}
    #         counter = 0
    #         for s in tp['stages']:
    #             stage_key = 'i_stage_' + str(s['id'])
    #             new_state = float(dict_object[stage_key]) if stage_key in dict_object and dict_object[stage_key] else 0
    #             try:
    #                 old_stage = next(os for os in old_stages if os.name_id == s['id'])
    #             except StopIteration:
    #                 old_fact = 0
    #             else:
    #                 old_fact = old_stage.value['fact'] if old_stage.value['fact'] else 0
    #             new_delay = new_state - old_fact
    #             presaved_object['tps'][tp['id']][s['id']] = {'state': new_state, 'fact': old_fact, 'delay': new_delay}
    #             counter += 1
    return presaved_object