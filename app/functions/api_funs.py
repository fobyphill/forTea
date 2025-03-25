import copy, json, re, datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, FloatField, Max, F, DateTimeField, DateField
from django.forms import model_to_dict
from app.other.global_vars import is_mysql
import app.functions.contract_funs
from app.functions import database_funs, reg_funs, convert_procedures, api_procedures, convert_funs, common_funs, \
    contract_funs, interface_funs, interface_procedures, convert_funs2, task_funs, session_procedures, \
    contract_procedures
from app.models import Dictionary, Designer, Contracts, Objects, DictObjects, ContractCells, TechProcess, \
    TechProcessObjects, Tasks
import pandas as pd


# Функции управления объектами и регистрации изменений в истории

# Создание объекта. Вход. ID класса, айди юзера, локация (table, contract, dict),
# источник (словарь с параметрами:айди класса, айди объекта, локация или строка "api"),
# параметры объекта - реквизиты.
# Выход - объект queryset или строка с ошибкой.
def create_object(class_id, user_id, location='table', source=None, *list_contracts, **params):
    user = None
    # определим родительскую транзакцию таймштамп
    if 'parent_transact' in params:
        parent_transact = params['parent_transact']
        del params['parent_transact']
    else:
        parent_transact = None

    if 'timestamp' in params:
        timestamp = params['timestamp']
        del params['timestamp']
    else:
        timestamp = datetime.datetime.now()
    str_ts = timestamp.strftime('%Y-%m-%dT%H:%M:%S')

    # данные регистрации
    output = {'class_id': class_id}
    # Определим менеджер класса
    if location == 'dict':
        manager_class = Dictionary.objects
        object_manager = DictObjects.objects
        object_create = DictObjects
    elif location == 'table':
        manager_class = Designer.objects
        object_manager = Objects.objects
        object_create = Objects
    elif location == 'contract':
        manager_class = Contracts.objects
        object_manager = ContractCells.objects
        object_create = ContractCells
        output['location'] = 'contract'
    else:
        return 'Ошибка. Некорректно задана локация класса. Укажите либо \'table\', \'contract\', или \'dict\''
    # Получим класс и его параметры
    try:
        current_class = manager_class.get(id=class_id)
    except ObjectDoesNotExist:
        return 'Ошибка. Некорректно задан ID класса'
    if current_class.formula not in ['table', 'contract', 'array', 'dict', 'tree']:
        return 'Ошибка. Некорректно задан ID класса'
    output['type'] = current_class.formula
    # определим пользовательскую локацию  - справочники / контракты
    if location == 'dict':
        output['location'] = current_class.default
    else:
        output['location'] = location
    is_contract = True if output['location'] == 'contract' else False
    all_params = manager_class.filter(parent_id=class_id).values()
    system_params = []
    class_params = []
    for ap in all_params:
        if location != 'dict' and ap['system']:
            system_params.append(ap)
        else:
            class_params.append(ap)
    if not class_params:
        return 'Ошибка. У указанного класса нет параметров. Работа с объектами данного класса невозможна'

    # валидация данных
    # Проверка типов данных
    result_valid_data = ''
    for k, v in params.items():
        result_valid_data += api_procedures.data_type_validation(k, v, class_params, current_class, is_contract)
    if result_valid_data:
        return result_valid_data

    code = database_funs.get_code(class_id, location) if current_class.formula != 'dict' else int(params['owner'])

    # Для массивов проверка обязательного поля - собственник
    if output['type'] == 'array':
        array_owner = next(str(cp['id']) for cp in class_params if cp['name'] == 'Собственник')
        if 'owner' in params:
            params[array_owner] = params['owner']
    # Для словарей проверим собственника
    elif output['type'] == 'dict':
        if not 'owner' in params:
            return 'Ошибка. У объекта типа \'словарь\' обязательно должен быть задан собственник в параметре \'owner\''
        else:
            parent_manager = ContractCells.objects if output['location'] == 'contract' else Objects.objects
            if not parent_manager.filter(parent_structure_id=current_class.parent_id, code=code):
                return 'Некорректно задан параметр "owner". Не найдет родительский объект'
            # Если существует объект с таким кодом - не создавать
            if DictObjects.objects.filter(parent_structure_id=class_id, code=code):
                return 'Некорректно задан параметр "owner". У родительского объекта уже имеется словарь класса ' + str(class_id)
    # для деревьев проверим обязательное поле - имя и родителя
    elif output['type'] == 'tree':
        param_name = next(cp for cp in class_params if cp['name'] == 'name')
        str_param_name_id = str(param_name['id'])
        if not 'name' in params or not params['name']:
            if not str_param_name_id in params or not params[str_param_name_id]:
                return 'Ошибка. Не заполнен параметр "name"'
            else:
                params['name'] = params[str_param_name_id]
        else:
            params[str_param_name_id] = params['name']
        header_parent = next(cp for cp in class_params if cp['name'] == 'parent')
        str_parent_id = str(header_parent['id'])
        if not 'parent' in params or not params['parent']:
            if str_parent_id in params:
                params['parent'] = params[str_parent_id]
            else:
                params['parent'] = None
                params[str_parent_id] = None
        else:
            params[str_parent_id] = params['parent']

    # Созидание кода объекта
    output['code'] = code
    json_object = output.copy()
    # Работа с источником
    if source:
        if type(source) is str:
            if source == 'api': json_object['source'] = 'api'
        elif type(source) is dict:
            json_object['source'] = source
    # Работа с параметрами объекта
    objs = []
    jsons = []
    delay_access = current_class.formula in ('table', 'contract', 'array')
    for cp in class_params:
        if cp['formula'] == 'eval':
            continue
        json_field = output.copy()
        json_field['name'] = cp['id']
        json_field['formula'] = cp['formula']
        cell = object_create(code=code, parent_structure_id=class_id, name_id=cp['id'])
        # для обязательных параметров в случае их отсутствия пропишем их значения из дефолта. А если дефолт отсутствует, то не сохраним
        str_id = str(cp['id'])
        if 'is_required' in cp and cp['is_required']:
            if not str_id in params or not params[str_id]:
                if cp['formula'] == 'enum':
                    params[str_id] = cp['value'][0] if current_class.formula != 'dict' else cp['default'][0]
                elif cp['default']:
                    params[str_id] = cp['default']
                elif cp['name'] in ('parent', 'parent_branch', 'system_data'):
                    pass
                else:
                    return 'Ошибка. Не задан обязательный параметр. ID: ' + str_id + '<br>'
        # Для делеев:
        if location == 'contract' and delay_access:
            is_delay = cp['delay'] and 'delay' in cp['delay'] and cp['delay']['delay']
        elif location == 'table' and delay_access:
            is_delay = cp['delay']
        else:
            is_delay = False
        if is_delay:
            key_delay = str_id + '_delay'
            key_date_delay = str_id + '_delay_date'
            # Если есть делей данного параметра
            if key_delay in params and key_date_delay in params:
                if not user:
                    try:
                        user = get_user_model().objects.get(id=user_id)
                    except ObjectDoesNotExist:
                        return 'Ошибка. Некорректно задан параметр "user_id". В системе нет пользователя с ID = ' + str(user_id)

                delay_date = params[key_date_delay]
                delay_date = api_procedures.validate_delay_date(delay_date)
                if delay_date < str_ts:  # delay PPA не предусматривается при создании объекта
                    delay_date = datetime.datetime.strftime(timestamp + datetime.timedelta(minutes=1), '%Y-%m-%dT%H:%M')


                handler = cp['delay']['handler'] if location == 'contract' else cp['delay_settings']['handler']
                robot_approve = True
                if not handler:
                    approve = True
                elif type(handler) is int:
                    approve = False
                else:
                    is_contract = (location == 'contract')
                    robot_approve = interface_procedures.rohatiw(params, current_class.id, None, cp,
                                                           class_params, [], user_id, is_contract)
                    approve = robot_approve

                if robot_approve:
                    delay_val = convert_procedures.cstdt(params[key_delay], cp['formula'])
                    cell.delay = [{'date_update': delay_date, 'value': delay_val, 'approve': approve}]
        # для контрактов - пропишем поле Системные данные
        if cp['name'] == 'system_data' and output['type'] == 'contract':
            cell.value = {'datetime_create': str_ts, 'is_done': False, 'handler': user_id}
        # Для дерева заполним параметр name
        elif cp['name'] == 'name':
            cell.value = params['name']
        # Если мы указали параметр его - конвертируем его из строки в нужный тип данных
        elif params and str_id in params and params[str_id]:
            cell.value = convert_procedures.cstdt(params[str_id], cp['formula'])
        # отдельно занесем параметр parent для дерева или объекта
        elif cp['name'] in ('parent_branch', 'parent'):
            cell.value = int(params['parent']) if 'parent' in params and params['parent'] else None
        if current_class.formula != 'dict' and not (cell.value or cell.delay) \
                and not cp['name'] in ('parent_branch', 'parent'):
            continue
        json_field['value'] = cell.value
        cell_valid = False
        if cell.value or cp['name'] in ('parent_branch', 'parent'):
            cell_valid = True
        if current_class.formula != 'dict':
            cell_valid = cell_valid or cell.delay
        if cell_valid:
            objs.append(cell)
            jsons.append(json_field)
    if objs:
        if current_class.formula == 'contract':
            obj_user = get_user_model().objects.get(id=user_id)
            tps = session_procedures.atic(class_id)
            new_obj = contract_funs.new_contract(current_class, class_params, system_params, objs, obj_user, timestamp,
                                                 tps, parent_transact, *list_contracts)
            header_system_data = next(cp for cp in class_params if cp['name'] == 'system_data')
            system_data_cell = next(o for o in new_obj if o.name_id == header_system_data['id'])
            cc = next(sp for sp in system_params if sp['name'] == 'completion_condition')
            interface_funs.do_cc(current_class, system_data_cell, cc, user_id, timestamp, parent_transact)
        else:
            object_manager.bulk_create(objs)
            new_obj = object_manager.filter(code=code, parent_structure_id=class_id)
            # Регистрация
            reg = {'json': json_object}
            transact_id = reg_funs.get_transact_id(class_id, code, location[0])
            reg_funs.simple_reg(user_id, 5, timestamp, transact_id, parent_transact, **reg)
            for j in jsons:
                reg = {'json': j}
                req = next(o for o in new_obj if o.name_id == reg['json']['name'])
                reg['json']['id'] = req.id
                reg_funs.simple_reg(user_id, 13, timestamp, transact_id, parent_transact, **reg)
                if location in ('table', 'contract') and req.delay:
                    del j['value']
                    date_update = datetime.datetime.strptime(req.delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
                    delay_ppa = date_update < timestamp
                    if delay_ppa:
                        req.delay[-1]['date_update'] = datetime.datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                        ts = date_update
                        req.save()
                    else:
                        ts = timestamp
                    j['delay'] = req.delay
                    reg_delay = {'json': j}
                    reg_funs.simple_reg(user_id, 22, ts, transact_id, parent_transact,  **reg_delay)
                    current_param = next(cp for cp in class_params if cp['id'] == req.name_id)
                    interface_procedures.make_task_4_delay(current_param, req, location[0], user, timestamp, delay_ppa, transact_id)
    else:
        return 'Ошибка. Не задан ни один параметр объекта. Объект не сохранен'
    return new_obj


def remove_object(class_id, code, user_id, location='table', source=None, forced=False, **params):
    # определим родительскую транзакцию и таймштамп

    if 'parent_transact' in params:
        parent_transact = params['parent_transact']
        del params['parent_transact']
    else:   parent_transact = None

    if 'timestamp' in params:
        timestamp = params['timestamp']
        del params['timestamp']
    else:
        timestamp = datetime.datetime.now()
    # Определим менеджер класса
    manager_class = Designer.objects
    object_manager = Objects.objects
    # данные регистрации
    incoming = {'class_id': class_id, 'code': code}
    if location == 'dict':
        manager_class = Dictionary.objects
        object_manager = DictObjects.objects
    elif location == 'table':
        pass
    elif location == 'contract':
        manager_class = Contracts.objects
        object_manager = ContractCells.objects
    elif location == 'tp':
        manager_class = TechProcess.objects
        object_manager = TechProcessObjects.objects
    else:
        return 'Ошибка. Некорректно задана локация класса. Укажите либо \'table\', \'contract\', или \'dict\''
    # Получим класс и его параметры
    try:
        current_class = manager_class.get(id=class_id)
    except ObjectDoesNotExist:
        return 'Ошибка. Некорректно задан ID класса'
    if current_class.formula not in ['table', 'contract', 'array', 'dict', 'tree', 'tp']:
        return 'Ошибка. Некорректно задан ID класса'
    incoming['type'] = current_class.formula
    # определим пользовательскую локацию  - справочники / контракты
    if location == 'dict':
        incoming['location'] = current_class.default
    elif location == 'tp':
        incoming['location'] = 'contract'
    else:
        incoming['location'] = location
    system_params = []; class_params = []
    all_params = list(manager_class.filter(parent_id=class_id).values())
    for ap in all_params:
        if current_class.formula == 'tp':
            if ap['settings']['system']:
                system_params.append(ap)
            else:
                class_params.append(ap)
        elif current_class.formula != 'dict' and ap['system']:
            system_params.append(ap)
        elif ap['formula'] not in ('array', 'contract', 'table'):
            class_params.append(ap)
    if not class_params:
        return 'Ошибка. У указанного класса нет параметров. Работа с объектами данного класса невозможна'

    if location == 'tp':
        delete_object = object_manager.filter(parent_structure_id=class_id, parent_code=code)
    else:
        # Проверка на детей
        res_check_4_children = api_procedures.fc4c(current_class, code, location)
        if res_check_4_children != 'ok' and not forced:
            return 'Ошибка. ' + res_check_4_children
        delete_object = object_manager.filter(code=code, parent_structure_id=class_id).select_related('name')
    if not delete_object:
        return 'Ошибка. Не найден объект класса ' + str(class_id) + ' с кодом ' + str(code)

    # для контрактов дополнительно проверим условие выполнения.
    if current_class.formula == 'contract' and not forced:
        system_data = next(cp for cp in class_params if cp['name'] == 'system_data')
        contract_is_done = next(do.value['is_done'] for do in delete_object if do.name_id == system_data['id'])
        if not contract_is_done:
            return 'Ошибка. Контракт не может быть удален, т.к. не выполняется "Условие завершения"'

    db_loc = 'p' if location == 'tp' else location[0]
    transact_id = reg_funs.get_transact_id(class_id, code, db_loc)

    # Для контрактов выполним линкмапы и триггер
    if current_class.formula == 'contract':
        lm = next(sp['value'] for sp in system_params if sp['name'] == 'link_map')
        tr = next(sp for sp in system_params if sp['name'] == 'trigger')
        del_obj = convert_funs.queryset_to_object(delete_object)[0]
        try:
            contract_funs.prepare_to_delete_object(lm, tr, del_obj, timestamp, transact_id, user_id)
        except Exception as ex:
            return str(ex)

    # Удалим техпроцессы, если таковые имеются
    if location == 'contract' and current_class.formula in ('contract', 'array'):
        tps = TechProcess.objects.filter(parent_id=class_id)
        list_regs = []
        for t in tps:
            tp = TechProcessObjects.objects.filter(parent_structure_id=t.id, parent_code=code)
            tp_transact = reg_funs.get_transact_id(t.id, code, 'p')
            for p in tp:
                inc = {'class_id': t.id, 'code': code, 'location': 'contract', 'type': 'tp', 'id': p.id,
                       'name': p.name_id, 'value': p.value}
                reg = {'json': inc}
                dict_reg = {'user_id': user_id, 'reg_id': 16, 'timestamp': timestamp, 'transact_id': tp_transact,
                            'parent_transact': transact_id, 'reg': reg}
                list_regs.append(dict_reg)
            tp.delete()
            # Удалим связанные с ТПсом задачи
            tasks = Tasks.objects.filter(kind='stage', data__tp_id=t.id, data__parent_code=code).values('code').distinct()
            for tt in tasks:
                task_funs.delete_stage_task(tt['code'], user_id, timestamp=timestamp, parent_transact=transact_id)
        reg_funs.paket_reg(list_regs)

    # удалим словари, если таковые имеются
    if current_class.formula in ('contract', 'table'):
        dicts = Dictionary.objects.filter(formula='dict', parent_id=class_id, default=location)
        for d in dicts:
            remove_object(d.id, code, user_id, 'dict', source, parent_transact=transact_id,
                              timestamp=timestamp)
        # Удалим связанные задачи
        tasks = Tasks.objects.filter(data__class_id=class_id, data__code=code)
        for t in tasks:
            task_funs.delete_simple_task(t, timestamp, user_id, parent_transact=transact_id)

    for do in delete_object:
        json_field = incoming.copy()
        json_field.update(model_to_dict(do))
        if location == 'tp':
            del json_field['parent_code']
            json_field['code'] = code
        reg = {'json_income': json_field}
        reg_funs.simple_reg(user_id, 16, timestamp, transact_id, parent_transact, **reg)
    delete_object.delete()
    reg = {'json_income': incoming}
    reg_funs.simple_reg(user_id, 8, timestamp, transact_id, **reg)

    # Если объект техпроцесса - удалим связанные с ним задачи
    tasks = Tasks.objects.filter(kind='stage', data__tp_id=class_id, data__parent_code=code).values('code').distinct()
    for tt in tasks:
        task_funs.delete_stage_task(tt['code'], user_id, timestamp=timestamp, parent_transact=transact_id)
    return 'Объект успешно удален. Код: ' + str(code) + '. ID класса:' + str(class_id) + '. Тип класса - ' + incoming['type']


# Редактирование объекта
def edit_object(class_id, code, user_id, location='table', source=None, *list_contracts, **params):
    list_contracts = list(list_contracts)
    # определим родительскую транзакцию и таймштамп
    if 'parent_transact' in params:
        parent_transact = params['parent_transact']
        del params['parent_transact']
    else:
        parent_transact = None
    if 'timestamp' in params:
        timestamp = params['timestamp']
        del params['timestamp']
    else:
        timestamp = datetime.datetime.now()

    # данные регистрации
    json_base = {'class_id': class_id, 'code': code}

    # Определим менеджер класса
    if location == 'dict':
        manager_class = Dictionary.objects
        object_manager = DictObjects.objects
        object_create = DictObjects
    elif location == 'table':
        manager_class = Designer.objects
        object_manager = Objects.objects
        object_create = Objects
    elif location == 'contract':
        manager_class = Contracts.objects
        object_manager = ContractCells.objects
        object_create = ContractCells
    elif location == 'tp':
        manager_class = TechProcess.objects
        object_manager = TechProcessObjects.objects
        object_create = TechProcessObjects
    else:
        return 'Ошибка. Некорректно задана локация класса. Укажите либо \'table\', \'contract\', или \'dict\'<br>'
    # Получим класс и его параметры
    try:
        current_class = manager_class.get(id=class_id)
    except ObjectDoesNotExist:
        return 'Ошибка. Некорректно задан ID класса<br>'
    if current_class.formula not in ['table', 'contract', 'array', 'dict', 'tree', 'tp']:
        return 'Ошибка. Некорректно задан ID класса<br>'
    # определим пользовательскую локацию  - справочники / контракты
    if location == 'dict':
        json_base['location'] = current_class.default
    elif location == 'tp':
        json_base['location'] = 'contract'
    else:
        json_base['location'] = location
    is_contract = True if json_base['location'] == 'contract' else False
    class_params = []
    system_params = []
    if location != 'tp':
        all_params = list(manager_class.filter(parent_id=class_id).exclude(formula='array').values())
        for ap in all_params:
            if location != 'dict' and ap['system']:
                system_params.append(ap)
            else:
                class_params.append(ap)
        object_params = object_manager.filter(parent_structure_id=class_id, code=code).select_related('name')
        if not class_params:
            return 'Ошибка. У указанного класса нет параметров. Работа с объектами данного класса невозможна<br>'
        # валидация данных
        result_no_valid_data = ''
        for k, v in params.items():
            result_no_valid_data += api_procedures.data_type_validation(k, v, class_params, current_class,
                                                                        is_contract)
        if result_no_valid_data:
            return result_no_valid_data
    else:
        object_params = None

    # зададим тип класса
    json_base['type'] = current_class.formula

    # Работа с источником
    if source:
        if type(source) is str:
            if source == 'api': json_base['source'] = 'api'
        elif type(source) is dict:
            json_base['source'] = source

    # для техпроцесса
    if location == 'tp':
        # Валидация данных ТПСов
        try:
            params = {pk: float(pv) for pk, pv in params.items()}
        except ValueError:
            return 'Ошибка. Параметры техпроцесса необходимо передавать в виде чисел<br>'
        tp_params = list(TechProcess.objects.filter(parent_id=class_id).values())
        my_tp = {'id': class_id, 'name': current_class.name, 'parent_id': current_class.parent_id,
                 'cf': current_class.value['control_field']}
        sys_params = []
        stages = []
        tp_data = {}
        for t_p in tp_params:
            if t_p['settings']['system']:
                sys_params.append(t_p)
            else:
                stages.append(t_p)
                str_tp_id = str(t_p['id'])
                if str_tp_id in params:
                    tp_data['i_stage_' + str_tp_id] = params[str_tp_id]
                else:
                    old_param = TechProcessObjects.objects.filter(parent_structure_id=class_id, parent_code=code,
                                                                  name_id=t_p['id'])
                    if old_param:
                        tp_data['i_stage_' + str_tp_id] = old_param[0].value['fact'] + \
                                                          sum(d['value'] for d in old_param[0].value['delay'])
                    else:
                        tp_data['i_stage_' + str_tp_id] = 0
        my_tp['system_params'] = sys_params
        my_tp['stages'] = stages
        tp_data, tps_change, tps_valid, tp_msg = interface_procedures.check_changes_tps((my_tp,), code,
                                                                                            tp_data)
        if not tps_valid:
            return tp_msg
        if not tps_change:
            return 'Вы не внесли изменений. Объект не сохранен'
        parent_class = Contracts.objects.get(id=my_tp['parent_id'])
        parent_headers = Contracts.objects.filter(parent_id=my_tp['parent_id'], system=False).exclude(name='array').values()
        try:
            contract_funs.edit_tp(my_tp, tp_data[my_tp['id']], code, parent_class, parent_headers, timestamp, parent_transact, user_id)
        except Exception as ex:
            return str(ex)
        else:
            return list(TechProcessObjects.objects.filter(parent_structure_id=my_tp['id'], parent_code=code).values())

    # Работа с параметрами объекта
    is_change = False
    loc = 'p' if location != 'tp' else location[0]
    transact_id = reg_funs.get_transact_id(class_id, code, loc)
    edit_params = {}

    error_msg = ''
    event_kind = []
    edit_objects = []
    new_objects = []
    for k, v in params.items():
        is_delay = False   #  поддерживает ли данный параметр делэй в принципе
        date_delay = None
        str_date_delay = None
        if k.lower() not in ('name', 'parent', 'owner'):
            try:
                k = int(k)
            except ValueError:
                if len(k) > 5 and k[-6:].lower() == '_delay':
                    continue
                elif len(k) > 10 and k[-10:].lower() == 'delay_date':
                    date_delay = params[k]
                    str_date_delay = api_procedures.validate_delay_date(date_delay)
                    key_delay = k[:-10] + 'delay'
                    v = params[key_delay]
                    k = int(k[:-11])
            try:
                cp = next(cp for cp in class_params if cp['id'] == k)
            except StopIteration:
                return 'Ошибка. Некорректно указан параметр с ID: ' + str(k) + \
                       '. У данного класса нет поля с указанным ID<br>'
            if type(v) is str:
                val = convert_procedures.cstdt(v, cp['formula'])
            else:
                val = v
            if location == 'contract':
                if cp['delay'] and cp['delay']['delay']:
                    is_delay = True
            elif location == 'table':
                is_delay = cp['delay']
            handler = None
            if is_delay and date_delay:
                handler = cp['delay']['handler'] if is_contract else cp['delay_settings']['handler']
            is_edit = True
            try:
                op = next(op for op in object_params if op.name_id == k)
            # Если параметра нет в системе - создадим его
            except StopIteration:
                is_change = True
                op = object_create(parent_structure_id=class_id, name_id=k, code=code)
                is_edit = False
            # Работаем с делэем
            if is_delay and date_delay:
                if op.delay == None:
                    op.delay = []
                new_delay = {'date_update': str_date_delay, 'value': val, 'approve': False}
                # Проверка хендлером
                if not handler:
                    new_delay['approve'] = True
                elif not type(handler) is int:
                    objs = [op]
                    if interface_procedures.rohatiw(params, class_id, code, cp, class_params, objs, user_id,
                                                    is_contract):
                        new_delay['approve'] = True
                    else:
                        error_msg += 'Ответственный (робот) отклонил отложенное изменение параметра ' + str(op.name_id) + '<br>'
                        continue
                # защита от дублирования
                if op.delay:
                    last_delay = op.delay[-1]
                    if last_delay == new_delay:
                        continue
                is_change = True
                if 'd' not in event_kind:
                    event_kind.append('d')

                if is_edit:
                    edit_obj = {'old_delay': copy.deepcopy(op.delay)}
                    op.delay.append(new_delay)
                    edit_obj['new_obj'] = op
                    edit_objects.append(edit_obj)
                else:
                    op.delay = [new_delay]
                    new_objects.append(op)
            else:
                if cp['formula'] == 'bool':
                    op.value = bool(op.value)
                if op.value != val:
                    is_change = True
                    if 'u' not in event_kind:
                        event_kind.append('u')
                    # Работаем со значением для редактирования параметра
                    if is_edit:
                        edit_obj = {'old_value': op.value}
                        op.value = val
                        edit_obj['new_obj'] = op
                        edit_objects.append(edit_obj)
                    # Работаем со значением для нового параметра
                    else:
                        op.value = val
                        new_objects.append(op)
        elif current_class.formula in ('tree', 'contract', 'table', 'array'):
            if current_class.formula == 'array':
                current_key = 'Собственник'
            elif current_class.formula != 'tree' and k.lower() == 'parent':
                current_key = 'parent_branch'
            else:
                current_key = k.lower()
            cp = next(cp for cp in class_params if cp['name'] == current_key)
            if k.lower() == 'name':
                val = v
            else:
                val = int(v) if v else None
            is_edit = True
            try:
                op = next(op for op in object_params if op.name_id == cp['id'])
            except StopIteration:
                op = object_create(code=code, name_id=cp['id'], parent_structure_id=class_id)
                is_edit = False
            if op.value != val:
                is_change = True
                if is_edit:
                    old_val = op.value
                    op.value = val
                    new_obj = {'old_value': old_val, 'new_obj': op}
                    edit_objects.append(new_obj)
                else:
                    op.value = val
                    new_objects.append(op)
        else:
            return 'Ошибка. Параметр "' + k + '" можно указывать только для типов данных "Дерево, Контракт, Справочник"<br>'
        # для массивов контрактов - нельзя изменять собственника
        if op.name.name == 'Собственник' and current_class.formula == 'array':
            return 'Ошибка. Нельзя изменять собственника у массива контракта'
        edit_params[k] = val

    if is_change:
        # если изменения были, то проверим обязательные поля
        if location != 'dict':
            excl_nms = ('parent', 'parent_branch', 'name', 'is_right_tree', 'link_map', 'trigger', 'busines_rule',
                        'completion_condition')
            str_errors_req_fields = ''
            for cp in class_params:
                if cp['name'] in excl_nms:
                    continue
                if cp['is_required'] and not cp['formula'] == 'eval':
                    # Если значение обязательного параметра не было передано или было передано, но пустое
                    str_cp_id = str(cp['id'])
                    if not str_cp_id in params:
                        try:
                            op = next(op for op in object_params if op.name_id == cp['id'])
                        except StopIteration:
                            str_errors_req_fields += 'Ошибка. Не задан обязательный параметр. ID: ' + str(cp['id']) + '<br>'
                        else:
                            if not type(op.value) in (float, int) and not op.value:
                                str_errors_req_fields += 'Ошибка. Не задан обязательный параметр. ID: ' + str(cp['id']) + '<br>'
                    elif cp['formula'] == 'float':
                        if not params[str_cp_id] and params[str_cp_id] != 0:
                            str_errors_req_fields += f'Ошибка. Не задан обязательный параметр. ID: {cp["id"]}<br>'
                    elif cp['formula'] == 'bool':
                        pass
                    elif not params[str_cp_id]:
                        str_errors_req_fields += 'Ошибка. Не задан обязательный параметр. ID: ' + str(cp['id']) + '<br>'
            if str_errors_req_fields:
                return str_errors_req_fields
        if is_contract:
            # Сохранение и выполнение бирулиматров
            object_user = get_user_model().objects.get(id=user_id)
            ec_params = {'event_kind': event_kind, 'tps_all': None, 'parent_transact': parent_transact}
            tps = session_procedures.atic(class_id)
            try:
                edited_object = contract_funs.edit_contract(current_class, code, class_params, system_params, tps,
                                                            edit_objects, new_objects, object_user, timestamp,
                                                            *list_contracts, **ec_params)
            except Exception as ex:
                edited_object = str(ex)

            # проверим условие выполнения
            if current_class.formula == 'contract':
                system_data_cell = next(op for op in object_params if op.name.name == 'system_data')
                cc = next(sp for sp in system_params if sp['name'] == 'completion_condition')
                interface_funs.do_cc(current_class, system_data_cell, cc, user_id, timestamp, parent_transact)

            # Если у данного класса есть ТПы, то проверим изменение контрольных полей
            for t in tps:
                cf = next(eo for eo in edited_object if eo.name_id == t['cf'])
                stages = TechProcessObjects.objects.filter(parent_structure_id=t['id'], parent_code=cf.code).order_by('name_id')
                old_cf_val = sum(s.value['fact'] + sum(d['value'] for d in s.value['delay']) for s in stages)
                if cf.value != old_cf_val:
                    delta = cf.value - old_cf_val
                    inc = {'class_id': current_class.id, 'code': cf.code, 'location': 'contract', 'type': 'tp',
                           'id': stages[0].id, 'name': stages[0].name_id, 'value': stages[0].value}
                    stages[0].value['fact'] += delta
                    stages[0].save()
                    outc = inc.copy()
                    outc['value'] = stages[0].value
                    reg = {'json_income': inc, 'json': outc}
                    tp_trans = reg_funs.get_transact_id(t['id'], cf.code, 'p')
                    reg_funs.simple_reg(user_id, 15, timestamp, tp_trans, transact_id, **reg)
            return edited_object
        else:
            # Изменение и регистрация
            general_reg_data = {'class_id': current_class.id, 'code': code, 'location': location, 'type': current_class.formula}
            edit_vals = [eo for eo in edit_objects if 'old_value' in eo]
            object_user = get_user_model().objects.get(id=user_id)
            if edit_vals:
                edited_values = [eo['new_obj'] for eo in edit_vals]
                object_manager.bulk_update(edited_values, ['value'])
                inc = general_reg_data.copy()
                for ev in edit_vals:
                    inc['id'] = ev['new_obj'].id
                    inc['name'] = ev['new_obj'].name_id
                    inc['value'] = ev['old_value']
                    outc = inc.copy()
                    outc['value'] = ev['new_obj'].value
                    reg = {'json': outc, 'json_income': inc}
                    reg_funs.simple_reg(user_id, 15, timestamp, transact_id, parent_transact, **reg)
            edit_delays = [eo for eo in edit_objects if 'old_delay' in eo]
            if edit_delays:
                inc = general_reg_data.copy()
                for ed in edit_delays:
                    last_delay = ed['new_obj'].delay[-1]
                    date_update = datetime.datetime.strptime(last_delay['date_update'], '%Y-%m-%dT%H:%M')
                    delay_plan = date_update > timestamp
                    if delay_plan:
                        date_delay = None
                    else:
                        date_delay = date_update
                        last_delay['date_update'] = datetime.datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                        ed['new_obj'].save()
                    inc['id'] = ed['new_obj'].id
                    inc['name'] = ed['new_obj'].name_id
                    inc['delay'] = ed['old_delay']
                    outc = inc.copy()
                    outc['delay'] = ed['new_obj'].delay
                    reg = {'json': outc, 'json_income': inc, 'date_delay': date_delay}
                    reg_funs.simple_reg(user_id, 22, timestamp, transact_id, parent_transact, **reg)

                    current_param = next(cp for cp in class_params if cp['id'] == ed['new_obj'].name_id)
                    interface_procedures.make_task_4_delay(current_param, ed['new_obj'], location[0], object_user, timestamp,
                                                           not delay_plan, transact_id)  # Создаем / регистрируем таск
                edited_delays = [ed['new_obj'] for ed in edit_delays]
                object_manager.bulk_update(edited_delays, ['delay'])

            if new_objects:
                outc = general_reg_data.copy()
                for no in new_objects:
                    no.save()
                    outc['id'] = no.id
                    outc['name'] = no.name_id
                    outc['value'] = no.value
                    reg = {'json': outc}
                    reg_funs.simple_reg(user_id, 13, timestamp, transact_id, parent_transact, **reg)
                    if no.delay:
                        del outc['value']
                        last_delay = no.delay[-1]
                        date_update = datetime.datetime.strptime(last_delay['date_update'], '%Y-%m-%dT%H:%M')
                        ppa = timestamp > date_update
                        if ppa:
                            date_delay = date_update
                            last_delay['date_update'] = datetime.datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                            no.save()
                        else:
                            date_delay = None
                        outc['delay'] = no.delay
                        reg = {'json': outc, 'date_delay': date_delay}
                        reg_funs.simple_reg(user_id, 22, timestamp, transact_id, parent_transact, **reg)
                        current_param = next(cp for cp in class_params if cp['id'] == no.name_id)
                        interface_procedures.make_task_4_delay(current_param, no, location[0], object_user, timestamp,
                                                               ppa, parent_transact)

            # Вызов сохраненного объекта
            edited_object = object_manager.filter(parent_structure_id=class_id, code=code)
        return edited_object

    else:
        if not error_msg:
            error_msg = 'Не задан или не изменен ни один параметр объекта<br>Объект не сохранен'
        return error_msg


def get_object(class_id, code, location='table'):
    if location == 'table':
        manager = Objects.objects
        class_manager = Designer.objects
    elif location == 'contract':
        manager = ContractCells.objects
        class_manager = Contracts.objects
    elif location == 'dict':
        manager = DictObjects.objects
        class_manager = Dictionary.objects
    elif location == 'tp':
        manager = TechProcessObjects.objects
        class_manager = TechProcess.objects
    else:
        return 'Ошибка. Некорректно указано расположение объекта. ' \
               'Необходимо указать значение для переменной location одно из следующих: table, contract, dict, tp'
    try:
        current_class = class_manager.get(id=class_id)
    except ObjectDoesNotExist:
        return 'Ошибка. Некорректно задан ID класса. Класс не найден'
    if location == 'tp':
        obj = manager.filter(parent_code=code, parent_structure_id=class_id)
    else:
        obj = manager.filter(code=code, parent_structure_id=class_id)
    if not obj:
        return 'Ошибка. Нет объекта с указанными параметрами'
    else:
        obj = convert_funs.queryset_to_object(obj)[0]
        # Получим дату последнего обновления элемента
        obj['date_update'] = reg_funs.get_last_update(class_id, code, current_class.formula)
        # Получим значения дочерних массивов
        header_arrays = None
        if location == 'table':
            header_arrays = Designer.objects
        elif location == 'contract':
            header_arrays = Contracts.objects
        if location in ('table', 'contract'):
            arrays = header_arrays.filter(parent_id=class_id, formula='array')
            if arrays:
                obj['arrays'] = {}
                for a in arrays:
                    # Получим список кодов дочерних элементов в текущем массиве
                    child_codes = [m['code'] for m in manager.filter(parent_structure_id=a.id,
                                                                     name__name__iexact='Собственник',
                                                                     value=code).values('code').distinct()]
                    children = manager.filter(code__in=child_codes, parent_structure_id=a.id)
                    if children:
                        obj['arrays'][a.id] = convert_funs.queryset_to_object(children)
            # Получим дочерние словари
            dict_headers = Dictionary.objects.filter(formula='dict', parent_id=class_id)
            if dict_headers:
                obj['dicts'] = {}
                for dh in dict_headers:
                    children = DictObjects.objects.filter(parent_structure_id=dh.id, parent_code=code)
                    if children:
                        obj['dicts'][dh.id] = convert_funs.queryset_to_object(children)[0]
        return obj


# Получить список объектов. вход: айди класса, локация, формат вывода - джейсон, html-таблица,
# знак (ИЛИ либо И) *список условий
def get_object_list(class_id, *conditions,  **params):
    result = True
    message = []

    output_type = params['output_type'] if 'output_type' in params else 'json'
    date_update = ('date_update' in params and params['date_update'])
    fields = params['fields'] if 'fields' in params and params['fields'] else []

    # валидация полей
    def valid_field(field):
        if type(field) is int:
            field = {'id': field, 'alias': None}
        elif not type(field) is dict:
            return False
        if not type(field['id']) is int:
            return False
        if not 'alias' in field:
            field['alias'] = None
        elif field['alias'] and not type(field['alias']) is str:
            return False
        if 'children' in field:
            if not type(field['children']) is list:
                return False
            for ch in field['children']:
                ind = field['children'].index(ch)
                field['children'][ind] = valid_field(ch)
        return field

    finish_fields = []
    for f in fields:
        vf = valid_field(f)
        if vf:
            finish_fields.append(vf)
        else:
            return False, 'Некорректно задан опциональный параметр "Fields"<br>'

    # проверка корректности данных
    if not 'location' in params:
        params['location'] = 'table'
    class_manager = None
    object_manager = None
    table_name = None
    if params['location'] == 'table':
        class_manager = Designer.objects
        object_manager = Objects.objects
        table_name = 'app_objects'
    elif params['location'] == 'contract':
        class_manager = Contracts.objects
        object_manager = ContractCells.objects
        table_name = 'app_contractcells'
    elif params['location'] == 'dict':
        class_manager = Dictionary.objects
        object_manager = DictObjects.objects
        table_name = 'app_dictobjects'
    else:
        result = False
        message.append('Ошибка. Некорректно задана локация объекта. Необходимо указать одно из следующих значений: '
                       'table, contract, dict')
    int_class_id = None
    try:
        int_class_id = int(class_id)
        class_id = str(class_id)
    except ValueError:
        result = False
        message.append('Ошибка. Некорректно указан параметр class_id. Параметр должен являться целым положительным числом')
    try:
        current_class = class_manager.get(id=int_class_id)
    except ObjectDoesNotExist:
        message.append('Ошибка. Некорретно задан ID класса. Не найден класс в заданной локации')
    if not 'logic_connector' in params:
        params['logic_connector'] = 'and'
    if params['logic_connector'] not in ('and', 'or'):
        result = False
        message.append('Ошибка. Некорректно передан параметр is_json. Необходимо указать одно из следующих значений: and, or')
    if not conditions:
        result = False
        message.append('Ошибка. Не задано ни одно условие')
    else:
        for c in conditions:
            if not re.match(r'^\d+[eqgtlnk]{2}.*$', c):
                result = False
                message.append('Ошибка. Некорректно задано условие. Задавайте условия по шаблону "Число",  "знак сравнения", "Результат"' \
                           ' Например: 18gt50 или 53neTrue')
                break
    if 'num_objects' in params:
        try:
            int(params['num_objects'])
        except ValueError:
            result = False
            message.append('Ошибка. Некорректно задан параметр "num_objects". необходимо указать целое число')
        if 'page' in params:
            try:
                int(params['page'])
            except ValueError:
                result = False
                message.append('Ошибка. Некорректно задан параметр "page". необходимо указать целое число')
    if result:
        # разбор условий
        dict_query_sign = {'gt': '>', 'lt': '<', 'ge': '>=', 'le': '<=', 'eq': '=', 'ne': '<>', 'lk': 'like'}
        json_extract = 'JSON_UNQUOTE(JSON_EXTRACT(value, "$"))' if is_mysql else 'JSON_EXTRACT(value, "$")'
        begin_query = 'select id, code from (select id, code, value, ' + json_extract + \
                           'AS val_str, Cast(JSON_EXTRACT(value, "$") as float) as val_float FROM ' + table_name \
                           + ' where parent_structure_id = ' + class_id + ' and '
        codes = []
        for c in conditions:
            result_query = begin_query
            list_c = re.search(r'^(\d+)([eglnqtk]{2})(.*)$', c)
            name_id = list_c[1]
            symb = list_c[2]
            val = list_c[3]
            result_query += ' name_id = ' + name_id + ') as subtable where'
            bool_var = [False, False]
            try:
                float(val)
                result_query += ' subtable.val_float'
            except ValueError:
                result_query += ' subtable.val_str'
                # Если работаем с булевыми переменными, то по признаку = true выполняем поиск напрямую,
                # но если = false, то находим все истинные значение, затем находим остальные коды
                if val.lower() in ('true', 'false'):
                    bool_var[0] = True
                    bool_var[1] = val.lower() == 'true' and symb == 'eq' or val.lower() == 'false' and symb == 'ne'
                elif symb == 'lk':
                    val = f'\"%{val}%\"'
                else:
                    val = '\"' + val + '\"'
            if bool_var[0]:
                result_query += ' = true'
            else:
                result_query += ' ' + dict_query_sign[symb] + ' ' + val

            # для второго и последующих условий добавим доп условие - работает с кодами предыдущих запросов
            if conditions.index(c):
                if params['logic_connector'] == 'and':
                    result_query += ' and code in (' + ','.join([str(c) for c in codes]) + ')'
                elif codes:
                    result_query += ' and code not in (' + ','.join([str(c) for c in codes]) + ')'
            query = object_manager.raw(result_query)
            # здесь конвертируем неистинные коды для булевого параметра
            if bool_var == [True, False]:
                objs = object_manager.filter(parent_structure_id=int_class_id).exclude(code__in=[q.code for q in query])
                if conditions.index(c):
                    if params['logic_connector'] == 'and':
                        objs = objs.filter(code__in=codes)
                    elif codes:
                        objs = objs.exclude(code__in=codes)
                objs = [o['code'] for o in objs.values('code').distinct()]
                if params['logic_connector'] == 'and':
                    codes = objs
                    if not codes:
                        break
                else:
                    codes += objs
            else:
                if params['logic_connector'] == 'and':
                    codes = [q.code for q in query]
                    if not codes:
                        break
                else:
                    codes += [q.code for q in query]

        if 'num_objects' in params:
            page = params['page'] if 'page' in params else 1
            q = object_manager.filter(parent_structure_id=int_class_id, code__in=codes).values('code').distinct()
            paginator = common_funs.paginator_object(q, params['num_objects'], page)
            codes = paginator['items_codes']
        list_reqs = object_manager.filter(parent_structure_id=int_class_id, code__in=codes)
        if finish_fields:
            hids = [ff['id'] for ff in finish_fields]
            list_reqs = list_reqs.filter(name__in=hids)
        else:
            hids = []
        # Полное структурирование полученных данных
        headers = class_manager.filter(parent_id=int_class_id).exclude(name='array')
        if params['location'] != 'dict':
            headers = headers.filter(system=False)
        if finish_fields:
            headers = headers.filter(id__in=hids)
        headers = list(headers.values())
        list_objects = []
        for c in codes:
            reqs_one_obj = [lr for lr in list_reqs if lr.code == c]
            object = convert_funs2.get_full_object(reqs_one_obj, current_class, headers, params['location'])
            list_objects.append(object)

        def structed_fields(field_list, list_object, lcm):
            for fl in field_list:
                if fl['alias']:
                    for lo in list_object:
                        if fl['id'] in lo:
                            lo[fl['id']]['name'] = fl['alias']
                if 'children' in fl:
                    header = lcm.get(id=fl['id'])
                    if header.formula == 'link':
                        if header.value[0] == 'c':
                            link_manager = ContractCells.objects
                            link_class_manager = Contracts.objects
                        else:
                            link_manager = Objects.objects
                            link_class_manager = Designer.objects
                        link_id = int(re.match(r'(?:table|contract)\.(\d+)', header.value)[1])
                        link_objects = link_manager.filter(parent_structure_id=link_id)
                        link_headers = link_class_manager.filter(parent_id=link_id, system=False).exclude(name='array')
                        if fl['children']:
                            chids = [ch['id'] for ch in fl['children']]
                            link_objects = link_objects.filter(name_id__in=chids)
                            link_headers = link_headers.filter(id__in=chids)
                        link_headers = list(link_headers.values())
                        for lo in list_object:
                            if fl['id'] in lo:
                                link_reqs = link_objects.filter(code=lo[fl['id']]['value'])
                                link_object = convert_funs2.get_full_object(link_reqs, current_class, link_headers, params['location'])
                                lo[fl['id']]['value'] = link_object
                                structed_fields(fl['children'], (link_object, ), link_class_manager)
        structed_fields(finish_fields, list_objects, class_manager)

        # добавим даты обновления объектов
        if date_update:
            for lo in list_objects:
                lo['date_update'] = reg_funs.get_last_update(int_class_id, lo['code'], current_class.formula)


        # Причешем выходные данные по формату
        if output_type == 'html':
            # Получим полный порядок полей:
            def sort_fields(list_fields):
                result_list = []
                for lf in list_fields:
                    if 'children' in lf:
                        result_list += sort_fields(lf['children'])
                    else:
                        result_list.append(lf['id'])
                return result_list
            # Распакуем детей
            def unpack_child(obj, k, v, param_name):
                if type(v) is dict and 'code' in v:
                    for kk in list(v.keys()):
                        if kk not in ('code', 'parent_structure', 'type', 'date_update'):
                            obj[kk] = v[kk]
                            obj[kk]['name'] = param_name + '.' + obj[kk]['name']
                            vv = v[kk]['value']
                            unpack_child(obj, kk, vv, obj[kk]['name'])
                    del obj[k]

            order_fields = sort_fields(finish_fields)
            for lo in list_objects:
                for k in list(lo.keys()):
                    if k not in ('code', 'parent_structure', 'type', 'date_update'):
                        v = lo[k]['value']
                        param_name = lo[k]['name']
                        unpack_child(lo, k, v, param_name)
            if not list_objects:
                return True, '<table></table>'
            df = pd.json_normalize(list_objects)
            df = df.loc[:, df.columns.str.contains("code|.name|.value")]
            df_cols = [list_objects[0][of]['name'] for of in order_fields]
            df_cols.insert(0, 'code')
            df = df.loc[:, df.columns.str.contains("code|.value")]
            order = [str(of) + '.value' for of in order_fields]
            order.insert(0, 'code')
            df = df[order]
            df.columns = df_cols
            list_objects = df.to_html(classes='table table-stripped', escape=False)
        elif output_type == 'json_min':
            def minimize_dict(dict_to_min):
                json_min = {}
                for k, v in dict_to_min.items():
                    if k in ('code', 'parent_structure', 'type', 'date_update'):
                        json_min[k] = v
                    elif type(v['value']) is dict and 'code' in v['value'] and 'parent_structure' in v['value']:
                        json_min[k] = minimize_dict(v['value'])
                    else:
                        json_min[k] = v['value']
                return json_min
            new_list_objects = []
            for lo in list_objects:
                json_min = minimize_dict(lo)
                new_list_objects.append(json_min)
            list_objects = new_list_objects
        elif output_type == 'json_name':
            def namemize_dict(dict_to_name):
                json_name = dict()
                for k, v in dict_to_name.items():
                    if k in ('code', 'parent_structure', 'type', 'date_update'):
                        json_name[k] = v
                    elif type(v['value']) is dict and 'code' in v['value'] and 'parent_structure' in v['value']:
                        json_name[v['name']] = namemize_dict(v['value'])
                    else:
                        json_name[v['name']] = v['value']
                return json_name
            new_list_objects = []
            for lo in list_objects:
                json_name = namemize_dict(lo)
                new_list_objects.append(json_name)
            list_objects = new_list_objects
        return result, list_objects
    else:   return result, message


# вход: params = {'location' = c / t, parent_transact = str, timestamp = datetime, link_map = str (или list для ТП),
# business_rule = str, trigger = str, stages = list, control_field = float}
# Выход: Массив из двух элементов. 1 - True / False, 2 - Текст
def create_class(user_id, class_type, class_types, class_name, parent_id=None, **params):
    # Парамеры
    location = params['location'] if 'location' in params else 't'
    parent_transact = params['parent_transact'] if 'parent_transact' in params and params['parent_transact'] else None
    timestamp = params['timestamp'] if 'timestamp' in params and params['timestamp'] else datetime.datetime.today()
    biznes_rule = params['business_rule'] if 'business_rule' in params and params['business_rule'] else None
    link_map = params['link_map'] if 'link_map' in params and params['link_map'] else None
    trigger = params['trigger'] if 'trigger' in params and params['trigger'] else None
    stages = params['stages'] if 'stages' in params and params['stages'] else ['Создан', ]
    control_field = params['control_field'] if 'control_field' in params else None

    loc = 'contract' if location == 'c' else 'table'
    is_valid = interface_funs.ccv(class_name, class_type, class_types, parent_id, location, link_map=link_map, stages=stages,
                                  control_field=control_field)
    if is_valid == 'ok':
        # создаем класс
        if class_type == 'dict':
            class_container = Dictionary
            class_manager = Dictionary.objects
        else:
            class_container = Contracts if location == 'c' else Designer
            class_manager = Contracts.objects if location == 'c' else Designer.objects
        new_class = class_container(name=class_name, formula=class_type, parent_id=parent_id, priority=0)
        if class_type == 'dict':
            new_class.default = loc
        else:
            new_class.is_visible = False
            new_class.is_required = False
            new_class.system = False
        new_class.save()
        # Регистрация
        outc = {'class_id': new_class.id, 'name': class_name, 'type': class_type, 'parent': parent_id, 'location': loc}
        reg = {'json': outc}
        transact_id = reg_funs.get_transact_id(new_class.id, 0, location)
        reg_funs.simple_reg(user_id, 1, timestamp, transact_id, parent_transact, **reg)

        # особенности разных типов классов
        def create_branch():
            if parent_id:
                parent_class = class_manager.get(id=parent_id)
                if parent_class.formula == 'tree':
                    class_container(name='parent_branch', formula='float', parent_id=new_class.id, is_required=True,
                                    is_visible=False, priority=0, system=False).save()

        if class_type == 'tree':
            new_class_params = []
            is_right_tree = class_container(name='is_right_tree', formula='bool', is_required=True, is_visible=False,
                                            parent_id=new_class.id, priority=0, value=False, system=True)
            new_class_params.append(is_right_tree)
            branch_name = class_container(name='name', formula='string', is_required=True, is_visible=False,
                                            parent_id=new_class.id, priority=0, system=False)
            new_class_params.append(branch_name)
            parent_branch = class_container(name='parent', formula='link', is_required=True, is_visible=False,
                                            parent_id=new_class.id, priority=0, system=False)
            new_class_params.append(parent_branch)
            class_manager.bulk_create(new_class_params)
        elif class_type == 'table':
            class_container(name='Наименование', formula='string', parent_id=new_class.id, is_required=True,
                            is_visible=True, priority=1, system=False).save()
            create_branch()
        elif class_type == 'contract':
            class_container(name='Дата и время записи', formula='datetime', parent_id=new_class.id, is_required=True,
                            is_visible=True, priority=1, system=False).save()
            create_branch()
            # ЛинкМап + триггер + бизнесРул
            list_reg = []
            bizness_params = []
            lm = class_container(name='link_map', formula='eval', parent_id=new_class.id, is_required=True,
                                 is_visible=True, priority=1, system=True, value=link_map)
            lm.save()
            bizness_params.append(lm)
            br = class_container(name='business_rule', formula='eval', parent_id=new_class.id, is_required=True,
                                is_visible=True, priority=1, system=True, value=biznes_rule)
            br.save()
            bizness_params.append(br)
            tr = class_container(name='trigger', formula='eval', parent_id=new_class.id, is_required=True,
                                 is_visible=True, priority=1, system=True, value=trigger)
            tr.save()
            bizness_params.append(tr)
            for bp in bizness_params:
                if 'parent' in outc:
                    del outc['parent']
                outc['name'] = bp.name
                outc['type'] = bp.formula
                outc['id'] = bp.id
                outc['value'] = bp.value
                reg = {'json': outc.copy()}
                dict_reg = {'user_id': user_id, 'reg_id': 9, 'timestamp': timestamp, 'transact_id': transact_id,
                            'parent_transact': parent_transact, 'reg': reg}
                list_reg.append(dict_reg)
            reg_funs.paket_reg(list_reg)
        elif class_type == 'array':
            val = loc + '.' + str(parent_id)
            class_container(name='Собственник', formula='link', parent_id=new_class.id, is_required=True, value=val,
                            is_visible=True, priority=1, system=False).save()
        elif class_type == 'techpro':
            list_params = []
            stages = class_container(name='stages', formula='enum', parent_id=new_class.id, is_required=True,
                            is_visible=False, priority=0, system=False, value=stages)
            stages.save()
            list_params.append(stages)
            cf = class_container(name='control_field', formula='float', parent_id=new_class.id, is_required=True,
                            is_visible=False, priority=0, system=False, value=control_field)
            cf.save()
            list_params.append(cf)
            pc = class_container(name='parent_code', formula='float', parent_id=new_class.id, is_required=True,
                            is_visible=False, priority=0, system=False)
            pc.save()
            lm = class_container(name='link_map', formula='eval', parent_id=new_class.id, is_required=True,
                                 is_visible=False, priority=0, system=True, value=link_map)
            lm.save()
            list_params.append(lm)
            list_regs = []
            for lp in list_params:
                outc['name'] = lp.name
                outc['type'] = lp.formula
                outc['id'] = lp.id
                outc['value'] = lp.value
                reg = {'json': outc.copy()}
                dict_reg = {'user_id': user_id, 'reg_id': 9, 'timestamp': timestamp, 'transact_id': transact_id,
                            'parent_transact': parent_transact, 'reg': reg}
                list_regs.append(dict_reg)
            reg_funs.paket_reg(list_regs)
        rus_loc = 'Контракты' if location == 'c' else 'Справочники'
        message = "Создан новый класс. ID: " + str(new_class.id) + ', название: "' + class_name + '", тип: "'\
        + class_type + '", расположение: "' + rus_loc + '"'
        return True, message
    else:
        return False, is_valid


# вход: обязательные параметры, опциональные: parent_transact, timestamp, class_name, parent_id
# выход - сообщение: ок / ошибка
def edit_class(user_id, class_id, class_type, location='t', **params):
    if class_type == 'dict':
        class_manager = Dictionary.objects
    else:
        class_manager = Contracts.objects if location == 'c' else Designer.objects
    try:
        current_class = class_manager.get(id=class_id, formula=class_type)
    except ObjectDoesNotExist:
        return 'Ошибка. Некорректно указаны данные класса. Не могу найти клас в системе'
    class_name = params['class_name'] if 'class_name' in params else current_class.name
    parent_id = params['parent_id'] if 'parent_id' in params else current_class.parent_id
    if class_name == current_class.name and parent_id == current_class.parent_id:
        return 'Вы не внесли изменений. Класс не был обновлен'
    valid = interface_funs.ecv(class_id, class_name, class_type, parent_id, location)
    if valid != 'ok':
        return valid
    else:
        full_location = 'contract' if location == 'c' else 'table'
        inc = {'class_id': class_id, 'location': full_location, 'type': class_type}
        outc = inc.copy()
        if class_name != current_class.name:
            inc['name'] = current_class.name
            outc['name'] = class_name
            current_class.name = class_name
        if parent_id != current_class.parent_id:
            inc['parent'] = current_class.parent_id
            outc['parent'] = parent_id
            current_class.parent_id = parent_id
        current_class.save()
        reg = {'json_income': inc, 'json': outc}
        parent_transact = params['parent_transact'] if 'parent_transact' in params else None
        timestamp = params['timestamp'] if 'timestamp' in params else datetime.datetime.today()
        transact_id = reg_funs.get_transact_id(class_id, 0, location)
        reg_funs.simple_reg(user_id, 3, timestamp, transact_id, parent_transact, **reg)
        return 'ok'


def create_class_param(user_id, class_id, class_type, param_name, param_type, location='t', **params):
    valid = interface_funs.ccpv(class_id, class_type, location, param_name, param_type, **params)
    if valid == 'ok':
        # чистим значения некоторых типов:
        if not param_type in ('link', 'enum', 'eval', 'const'):
            params['value'] = None
        # чистим дефолты некоторых типов
        if param_type in ('enum', 'eval', 'file') and class_type != 'dict':
            params['default'] = None
        value = params['value'] if 'value' in params and params['value'] else None
        default = params['default'] if 'default' in params and params['default'] else None
        if isinstance(default, datetime.datetime):
            default = datetime.datetime.strftime(default, '%Y-%m-%dT%H:%M:%S')
        elif isinstance(default, datetime.date):
            default = datetime.date.strftime(default, '%Y-%m-%d')
        is_required = True if 'is_required' in params and params['is_required'] else False
        is_visible = True if 'is_visible' in params and params['is_visible'] else False
        delay = True if 'delay' in params and params['delay'] else False
        if class_type == 'dict':
            class_container = Dictionary
        else:
            class_container = Contracts if location == 'c' else Designer
        max_priority = class_container.objects.filter(parent_id=class_id).aggregate(max=Max('priority'))['max']
        if not max_priority:
            max_priority = 0
        new_param = class_container(parent_id=class_id, formula=param_type, name=param_name, default=default,
                                    is_visible=is_visible, priority=max_priority + 1)
        if class_type != 'dict':
            new_param.is_required = is_required
            new_param.value = value
            if location == 't':
                new_param.delay = delay
        new_param.save()
        # регистрация
        full_location = 'contract' if location == 'c' else 'table'
        outc = {'class_id': class_id, 'type': class_type, 'location': full_location, 'name': param_name,
                'id': new_param.id, 'formula': new_param.formula,  'default': new_param.default, 'is_visible': is_visible}
        if class_type != 'dict':
            outc['is_required'] = is_required
            outc['value'] = new_param.value
            if location == 't':
                outc['delay'] = delay
        reg = {'json': outc}
        timestamp = params['timestamp'] if 'timestamp' in params else datetime.datetime.today()
        parent_transact = params['parent_transact'] if 'parent_transact' in params else None
        transact_id = reg_funs.get_transact_id(class_id, 0, location)
        reg_funs.simple_reg(user_id, 9, timestamp, transact_id, parent_transact, **reg)
        return 'Создан новый параметр класса. ID: ' + str(new_param.id) + ', тип данных - ' + param_type + ', название: "'\
            + param_name + '"'
    else:   return valid


def edit_class_param(user_id, class_type, param_id, **params):
    verify_result = api_procedures.vepoc(class_type, param_id, **params)
    if verify_result != 'ok':
        return verify_result
    location = 'c' if 'location' in params and params['location'] == 'c' else 't'
    full_location = 'contract' if location == 'c' else 'table'
    if class_type == 'dict':
        manager = Dictionary.objects
    else:
        manager = Contracts.objects if location == 'c' else Designer.objects
    current_param = manager.get(id=param_id)
    current_class = manager.get(id=current_param.parent_id)
    inc = {'class_id': current_param.parent_id, 'location': full_location, 'type': class_type}
    outc = inc.copy()
    is_change = False
    # Сохраняем имя
    if 'name' in params and params['name'] != current_param.name:
        is_change = True
        inc['name'] = current_param.name
        outc['name'] = params['name']
        current_param.name = params['name']
    # Сохраняем код значения
    if class_type != 'dict' and 'value' in params and params['value'] != current_param.value:
        if current_param.formula in ('eval', 'enum', 'const', 'link') or current_param.name == 'is_right_tree' \
                and current_class.formula == 'tree':
            is_change = True
            inc['value'] = current_param.value
            outc['value'] = params['value']
            current_param.value = params['value']
    # Сохраняем дефолт
    if 'default' in params:
        if current_param.formula in ('date', 'datetime') and params['default']:
            params['default'] = params['default'].strftime('%Y-%m-%dT%H:%M:%S') if current_param.formula == 'datetime'\
                else params['default'].strftime('%Y-%m-%d')
        if params['default'] != current_param.default:
            is_change = True
            inc['default'] = current_param.default
            outc['default'] = params['default']
            current_param.default = outc['default']
    # Сохраним видимость
    if 'is_visible' in params and params['is_visible'] != current_param.is_visible:
        is_change = True
        inc['is_visible'] = current_param.is_visible
        outc['is_visible'] = params['is_visible']
        current_param.is_visible = params['is_visible']
    # Сохраним обязательность
    if class_type != 'dict' and 'is_required' in params and params['is_required'] != current_param.is_required:
        is_change = True
        inc['is_required'] = current_param.is_required
        outc['is_required'] = params['is_required']
        current_param.is_required = params['is_required']
    # Сохраним отложенность
    if location == 't' and class_type != 'dict' and 'delay' in params and params['delay'] != current_param.delay:
        is_change = True
        inc['delay'] = current_param.delay
        outc['delay'] = params['delay']
        current_param.delay = params['delay']
    if is_change:
        current_param.save()
        # регистрация
        timestamp = params['timestamp'] if 'timestamp' in params else datetime.datetime.today()
        parent_transact = params['parent_transact'] if 'parent_transact' in params else None
        transact_id = reg_funs.get_transact_id(current_param.parent_id, 0, location)
        reg = {'json': outc, 'json_income': inc}
        reg_funs.simple_reg(user_id, 10, timestamp, transact_id, parent_transact, **reg)
        return 'ok'
    else:   return 'Вы ничего не изменили. Параметр класса не обновлен'


def remove_class_param(user_id, class_type, param_id, location='t', **params):
    if location not in ('t', 'c'):
        return 'Некорректно задан параметр "location". Задайте один из символов - [t, c]'
    manager = Dictionary.objects if class_type == 'dict' else Contracts.objects if location == 'c' else Designer.objects
    obj_manager = DictObjects.objects if class_type == 'dict' else ContractCells.objects if location == 'c' else Objects.objects
    try:
        current_param = manager.filter(id=param_id)
    except ValueError:
        return 'Некорректно задан один из параметров - class_type, param_id, location. Параметр не найден'
    if current_param:
        current_param = current_param[0]
    else:
        return 'Некорректно задан один из параметров - class_type, param_id, location. Параметр не найден'
    # Проверка, не задали ли мы случайно класс
    if current_param.formula in ('folder', 'table', 'tree', 'contract', 'dict', 'array', 'techpro'):
        return 'Нельзя указывать ID класса для удаления параметра класса'
    # проверка типа класса
    try:
        current_class = manager.get(id=current_param.parent_id, formula=class_type)
    except ObjectDoesNotExist:
        return 'Тип класса указан некорректно'

    # Если параметр системный - нелья удалять
    if class_type != 'dict' and current_param.system:
        return 'Нельзя удалять системные реквизиты класса'
    # Зашитые реквизиты - тоже нельзя удалять
    if class_type == 'table' and current_param.name == 'Наименование' \
            or class_type == 'contract' and current_param.name == 'Дата и время записи' \
            or class_type == 'array' and current_param.name == 'Собственник'\
            or class_type == 'tree' and current_param.name in ('name', 'parent')\
            or class_type == 'techpro':
        return 'Нельзя удалять зарезервированные реквизиты'
    # Если есть объекты с этим параметров - не убивать
    cells = obj_manager.filter(parent_structure_id=current_param.parent_id, name_id=current_param.id)\
        .exclude(value__isnull=True).exclude(value='')
    if cells:
        return 'Указанный параметр используется в объектах. Удалите все его использования в других объектах, затем повторите попытку'
    # регистрируем
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    timestamp = params['timestamp'] if 'timestamp' in params else datetime.datetime.today()
    transact_id = reg_funs.get_transact_id(current_param.parent_id, 0, location)
    full_location = 'contract' if location == 'c' else 'table'
    json_input = {'class_id': current_param.parent_id, 'location': full_location, 'type': class_type,
                  'formula': current_param.formula, 'id': current_param.id, 'name': current_param.name,
                  'default': current_param.default, 'is_visible': current_param.is_visible}
    if class_type != 'dict':
        json_input['is_required'] = current_param.is_required
        json_input['value'] = current_param.value
        if location == 't':
            json_input['delay'] = current_param.delay
    reg = {'json_income': json_input}
    reg_funs.simple_reg(user_id, 11, timestamp, transact_id, parent_transact, **reg)
    # Удаляем
    current_param.delete()
    return 'ok'


def remove_class(user_id, class_id, class_type, location='t', **params):
    if location not in ('t', 'c'):
        return 'некорректно указано расположение класса. Выберите один из двух символов: t  или c'
    if class_type == 'tp':
        manager = TechProcess.objects
    else:
        manager = Dictionary.objects if class_type == 'dict' else Contracts.objects if location == 'c' else Designer.objects
    try:
        current_class = manager.get(id=class_id, formula=class_type)
    except (ObjectDoesNotExist, ValueError):
        return 'некорректно заданы параметры: class_id, class_type, location. Класс не найден'
    # проверка на дочерние классы
    if class_type not in ('dict', 'alias', 'tp'):
        dict_children_classes = {'folder': ('folder', 'tree', 'table', 'contract'), 'tree': ('table', 'contract'),
                                 'table': ('array', ), 'contract': ('array', ), 'array': ('techpro', )}
        if manager.filter(parent_id=class_id, formula__in=dict_children_classes[current_class.formula]) or\
                current_class.formula in ('table', 'contract') and Dictionary.objects.filter(parent_id=class_id):
            return 'У удаляемого класса есть дочерние классы. Удаление невозможно'
    elif class_type == 'alias':
        is_contract = True if location == 'c' else False
        if not database_funs.chpoc(class_id, is_contract):
            return 'Нельзя удалить константу, у которой есть свойства'
    # Проверка на объекты (кроме техпроцессов, там валим вместе с объектами)
    if class_type == 'tp':
        object_manager = TechProcessObjects.objects
    else:
        object_manager = DictObjects.objects if class_type == 'dict' else ContractCells.objects if location == 'c' else Objects.objects
    transact_id = None
    timestamp = None

    if class_type == 'tp':
        db_loc = 'p'
    elif class_type == 'dict':
        db_loc = 'd'
    else:
        db_loc = location

    if class_type == 'tp':
        objs = object_manager.filter(parent_structure_id=class_id).values('parent_code').distinct()
        transact_id = reg_funs.get_transact_id(current_class.id, 0, 'p')
        timestamp = params['timestamp'] if 'timestamp' in params else datetime.datetime.today()
        for o in objs:
            remove_object(class_id, o['parent_code'], user_id, 'tp', timestamp=timestamp, parent_transact=transact_id)
    else:
        if object_manager.filter(parent_structure_id=class_id):
            return 'У удаляемого класса есть объекты. Удаление невозможно'
    # Регистрация удаления параметров
    class_params = manager.filter(parent_id=class_id).exclude(formula__in=('folder', 'tree', 'contract', 'table', 'array',
                                                                           'dict', 'tp'))
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    timestamp = params['timestamp'] if 'timestamp' in params else datetime.datetime.today() if not timestamp else timestamp
    transact_id = reg_funs.get_transact_id(current_class.id, 0, db_loc) if not transact_id else transact_id
    list_regs = []
    for cp in class_params:
        reg = {'json_income': model_to_dict(cp)}
        dict_reg = {'user_id': user_id, 'reg_id': 11, 'timestamp': timestamp, 'transact_id': transact_id,
                    'parent_transact_id': parent_transact, 'reg': reg}
        list_regs.append(dict_reg)
    reg_funs.paket_reg(list_regs)
    class_params.delete()  # И удаление параметров
    # регистрация удаления класса
    full_location = 'contract' if location == 'c' else 'table'
    inc = {'class_id': current_class.id, 'location': full_location, 'type': current_class.formula,
           'parent': current_class.parent_id, 'name': current_class.name}
    reg = {'json_income': inc}
    reg_funs.simple_reg(user_id, 4, timestamp, transact_id, parent_transact, **reg)
    current_class.delete()  # и удаление класса
    return 'ok'


def get_class(class_id, class_type, location='t'):
    if location not in ('t', 'c'):
        return False, 'Некорректно указана локация класса. Укажите один из двух символов: t или c'
    if class_type == 'dict':
        manager = Dictionary.objects
    else:
        manager = Contracts.objects if location == 'c' else Designer.objects
    try:
        current_class = manager.filter(id=class_id, formula=class_type).values()
    except ValueError:
        return False, 'Некорректно заданы параметры "class_id", "class_type", "location". Класс не найден'
    if not current_class:
        return False, 'Некорректно заданы параметры "class_id", "class_type", "location". Класс не найден'
    else:
        current_class = current_class[0]
    excluded_types = ('tree', 'folder', 'contract', 'table', 'array', 'dict', 'techpro')
    class_params = manager.filter(parent_id=current_class['id']).exclude(formula__in=excluded_types).values()
    for cp in class_params:
        cp_id = cp['id']
        del cp['id']
        current_class[cp_id] = cp
    return True, current_class


def get_class_list(parent_id=None, location='t'):
    if location not in ('c', 't'):
        return False, 'Некорректно задан параметр location. Укажите один из символов - t или c'
    if parent_id and not type(parent_id) is int:
        return False, 'Некорректно задан параметр parent_id. Укажите целое число'
    def do_eval(parent_id, location):
        manager = Contracts.objects if location == 'c' else Designer.objects
        types_list = ('folder', 'tree', 'table', 'contract', 'array', 'techpro', 'alias')
        classes = list(manager.filter(parent_id=parent_id, formula__in=types_list).annotate(type=F('formula'))
                       .values('id', 'parent_id', 'name', 'type'))
        list_result = classes.copy()
        for c in classes:
            list_result += do_eval(c['id'], location)
        list_result += list(Dictionary.objects.filter(formula='dict', parent_id=parent_id).annotate(type=F('formula'))
                            .values('id', 'parent_id', 'name', 'type'))
        return list_result
    return True, do_eval(parent_id, location)


# Удаляет объекты по списку или диапазону кодов. location = [t, c, d]
# Опциональные параметры: first_code, last_code, list_codes
# Возвращает список удаленных кодов и комментарий
def remove_object_list(class_id, user_id, **params):
    delete_codes = []
    # обработка опциональных параметров
    if 'interval_codes' in params:
        match_interval = re.match(r'^(\d*)\-(\d*)$', params['interval_codes'])
        if not match_interval:
            return delete_codes, 'Некорректно указан интервал кодов, укажите строку вида: 1-15 или 10- или -350'
        first_code = int(match_interval[1]) if match_interval[1] else None
        last_code = int(match_interval[2]) if match_interval[2] else None
        if first_code and last_code:
            if first_code > last_code:
                first_code, last_code = last_code, first_code
    if not 'list_codes' in params:
        params['list_codes'] = []
    if not 'source' in params:
        params['source'] = None
    if not 'forced' in params:
        params['forced'] = False
    if not 'timestamp' in params:
        params['timestamp'] = datetime.datetime.today()
    if not 'parent_transact' in params:
        params['parent_transact'] = None
    # Валидация данных
    if not 'location' in params:
        params['location'] = 't'
    elif params['location'] not in ('t', 'c', 'd'):
        return delete_codes, 'Некорректно указана локация. Укажите один из следующих символов: t, c, d'
    try:
        class_id = int(class_id)
    except ValueError:
        return delete_codes, 'Некорректно указан ID класса. Укажите целое число'
    if params['list_codes']:
        if not type(params['list_codes']) is list:
            return delete_codes, 'Некорректно указан список кодов. Задайте список целых чисел'
        if not all(isinstance(x, int) for x in params['list_codes']):
            return delete_codes, 'Некорректно указан список кодов. Задайте список целых чисел'

    object_manager = DictObjects.objects if params['location'] == 'd' else \
        ContractCells.objects if params['location'] == 'c' else Objects.objects
    del_objs = object_manager.filter(parent_structure_id=class_id)
    if 'interval_codes' in params or params['list_codes']:
        if 'interval_codes' in params:
            interval_codes_objs = del_objs
            if first_code:
                interval_codes_objs = interval_codes_objs.filter(code__gte=first_code)
            if last_code:
                interval_codes_objs = interval_codes_objs.filter(code__lte=last_code)
        else:
            interval_codes_objs = del_objs.none()
        interval_codes_objs = interval_codes_objs.values('code').distinct()
        if params['list_codes']:
            list_codes_objs = object_manager.filter(code__in=params['list_codes']).values('code').distinct()
        else:
            list_codes_objs = object_manager.none()

        del_objs = interval_codes_objs.union(list_codes_objs)
    else:
        del_objs = del_objs.values('code').distinct()

    if not del_objs:
        return delete_codes, 'Некорректно заданы данные: ID класса, либо локация'
    loc = 'dict' if params['location'] == 'd' else 'contract' if params['location'] == 'c' else 'table'
    result_comment = ''
    for do in del_objs:
        res = remove_object(class_id, do['code'], user_id, loc, params['source'], params['forced'],
                      parent_transact=params['parent_transact'], timestamp=params['timestamp'])
        if res[:6] == 'Ошибка':
            result_comment += 'Код объекта ' + str(do['code']) + '. ' + res + '<br>'
        else:
            delete_codes.append(do['code'])
    return delete_codes, result_comment








