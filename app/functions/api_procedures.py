import json
import re
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist

from app.functions import convert_procedures, interface_procedures, database_funs, convert_funs, contract_funs
from app.models import ContractCells, Objects, DictObjects, Designer, Contracts, Dictionary


# Проверка типов данных
# Вход - параметры - словарь. class_params - queryset - набор заголовков текущего класса.
# class_type - тип класса - контракт, справочник, словарь, массив
def data_type_validation(k, v, class_params, current_class, is_contract=False):
    def try_header(k):
        try:
            header_param = next(cp for cp in class_params if cp['id'] == k)
        except StopIteration:
            return False, 'Ошибка. Не найден параметр класса. ID параметра ' + str(k) + '\n'
        else:
            return True, header_param
    param_type = 'v'   # Зададим тип параметра - V - значение, d - отложенное, dd - дата отложенного
    if not (k in ('owner', 'parent', 'name') or len(k) > 6 and k[-5:] == 'delay' or len(k) > 11 and k[-10:] == 'delay_date'):
            try:
                k = int(k)
            except ValueError:
                return 'Ошибка. Некорректно указан параметр объекта - ' + k + '\n'
    header_param = None
    if type(k) is int:
        res, header_param = try_header(k)
        if not res:
            return header_param
    elif len(k) > 6 and k[-6:] == '_delay':
        param_type = 'd'
        k = int(k[:-6])
        res, header_param = try_header(k)
        if not res:
            return header_param
    elif len(k) > 11 and k[-11:] == '_delay_date':
        param_type = 'dd'
        k = int(k[:-11])
        res, header_param = try_header(k)
        if not res:
            return header_param
        # Проверка доступности делэя
        if not 'delay' in header_param or not header_param['delay']:
            return 'Ошибка. Нельзя задать отложенное значение для параметра ID: ' + header_param['name']
        elif type(header_param['delay']) is dict and not header_param['delay']['delay']:
            return 'Ошибка. Нельзя задать отложенное значение для параметра ID: ' + header_param['name']

    elif k.lower() == 'parent':
        # Зададим заголовок для объекта с родительской веткой
        if current_class.formula in ('table', 'contract'):
            try:
                header_param = next(cp for cp in class_params if cp['name'] == 'parent_branch')
            except StopIteration:
                return 'Ошибка. Некорректно задан ID родительской ветки. У данного класса нет родительского дерева.'
        elif current_class.formula == 'tree':
            header_param = next(cp for cp in class_params if cp['name'] == 'parent')
    elif k.lower() == 'owner':
        if current_class.formula in ('dict', 'array'):
            try:
                int(v)
            except ValueError:
                return 'Ошибка. Некорректно задан параметр "owner" - собственник. Укажите целое число'
            else:
                return ''
        else:
            return 'Ошибка. Собственника необходимо указывать только для классов с собственниками - массив, словарь'
    elif k.lower() == 'name':
        return ''

    if current_class.formula == 'dict':
        if not v:
            return ''
    elif not (current_class.formula == 'tp' or header_param['is_required'] or v):
        if param_type in ('v', 'd'):
            return ''

    # Проверка типа данных. Защита данных от делэя
    if param_type == 'd':
        if not current_class.formula in ('contract', 'table', 'array'):
            return 'Тип данных ' + current_class.formula + ' не поддерживает отложенные значения'
    # Проверка даты выполнения
    if param_type == 'dd':
        list_date_formats = ('%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d.%m.%YT%H:%M', '%d.%m.%Y %H:%M')
        for ldf in list_date_formats:
            try:
                v = datetime.strptime(v, ldf)
            except ValueError:
                pass
            else:
                break
        else:
            return 'Ошибка. Дата выполнения задана в недопустимом формате. Укажите ее пожалуйста в одном из следующих форматов:' \
                   'YYYY-mm-dd, YYYY-mm-ddTHH:MM, YYYY-mm-dd HH:MM, dd.mm.YYYYTHH:MM, dd.mm.YY HH:MM'
    # Проверка значения и делэя
    else:
        # Проверка типа данных
        base_types = ('owner', 'parent', 'name')
        if k in base_types:
            try:
                v = int(v) if v else None
            except ValueError:
                return 'Некорректно указано значение параметра "' + k + '"'
        elif header_param['formula'] == 'float':
            try:
                v = float(v) if v else None
            except ValueError:
                return 'Ошибка. Некорректное значение числового параметра. ID параметра: ' + str(k) + '. Значение: ' + v + '\n'
        elif header_param['formula'] == 'link':
            try:
                v = int(v) if v else  None
            except ValueError:
                return 'Ошибка. Некорректное значение ссылки. ID параметра: ' + str(k) + '. Значение: ' + v + '\n'
        elif header_param['formula'] == 'bool':
            if v.lower() not in ('true', 'false'):
                return 'Ошибка. Некорректное значение логического параметра ' + str(k) + ' = ' + v + \
                       '.Укажите значение True или False' + '\n'
        elif header_param['formula'] == 'date':
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                return 'Ошибка. Некорректное значение параметра ' + str(k) + ' в формате даты. Укажите дату в формате гггг-мм-дд' + '\n'
        elif header_param['formula'] == 'datetime':
            try:
                datetime.strptime(v, '%Y-%m-%dT%H:%M')
            except (ValueError, TypeError):
                try:
                    datetime.strptime(v, '%Y-%m-%dT%H:%M:%S')
                except (ValueError, TypeError):
                    return 'Ошибка. Некорректное значение параметра ' + str(k) + \
                           ' в формате даты-времени. Укажите дату в строковом формате гггг-мм-ддТчч:мм:cc' + '\n'
        elif header_param['formula'] == 'enum':
            enum = header_param['default'] if current_class.formula == 'dict' else header_param['value']
            if v not in enum:
                return 'Ошибка. Некорректное значение параметра ' + str(k) + \
                       ' в формате перечисления. Значение обязательно должно быть выбрано из списка перечисления. Значение: \'' \
                       + str(v) + '\'\n'
        elif header_param['formula'] == 'eval':
            return 'Ошибка. Некорректное значение параметра ' + str(k) + ' Нельзя задать данные для типа данных \'eval\'\n'
        elif header_param['formula'] == 'const':
            try:
                v = int(v)
            except ValueError:
                return 'Ошибка. Некорректное значение константы. ID параметра: ' + str(k) + '. Значение: ' + v + '\n'
            # Позже проверю константы. Их необходимо допилить
            const_loc, const_id = convert_procedures.slice_link_header(header_param['value'])
            const_manager = Designer.objects if const_loc == 'table' else Contracts.objects
            aliases_id = [c.id for c in const_manager.filter(parent_id=const_id)]
            if v not in aliases_id:
                return 'Ошибка. Некорректное значение параметра ' + str(k) + '. Ссылка ведет на несуществующий объект' + '\n'

        elif header_param['formula'] == 'file':
            return 'Ошибка. Некорректное значение параметра ' + str(k) + '. Тип данных \'file\' не поддерживается' + '\n'

        # Защита данных
        # Проверка ссылки на объект
        if header_param:
            if header_param['formula'] == 'link':
                if current_class.formula == 'tree' and header_param['name'] == 'parent':
                    obj_manager = ContractCells.objects if is_contract else Objects.objects
                    if v:
                        obj = obj_manager.filter(code=v, parent_structure_id=current_class.id).count()
                        if not obj:
                            return 'Ошибка. Некорректное значение параметра ' + str(k) + '. Ссылка ведет на несуществующий объект' + '\n'
                elif current_class.formula == 'dict':
                    str_link = re.match(r'(?:table|contract)\.\d+\.', header_param['default'])[0] + str(v)
                    if not interface_procedures.cdl(str_link):
                        return 'Ошибка. Некорректно задан параметр ID: ' + str(k) + '. Ссылка ведет на несуществующий объект\n'
                else:
                    parent_type, parent_structure_id = convert_procedures.slice_link_header(header_param['value'])
                    manager_parent = ContractCells.objects if parent_type == 'contract' else Objects.objects
                    parent = manager_parent.filter(parent_structure_id=parent_structure_id, code=v)
                    if not parent:
                        return 'Ошибка. Некорректное значение параметра ' + str(k) + '. Ссылка ведет на несуществующий объект' + '\n'
            # для контрактов защита от изменения или ручного задания "дата и время записи"
            if current_class.formula == 'contract' and header_param['name'] == 'Дата и время записи':
                return 'Ошибка. Нельзя задать значение параметру \"Дата и время записи\"\n'
            # Проверка родительской ветки объекта
            if header_param['name'] == 'parent_branch':
                parent_manager = ContractCells.objects if is_contract else Objects.objects
                parent_branch = parent_manager.filter(parent_structure_id=current_class.parent_id, code=v)
                if not parent_branch:
                    return 'Ошибка. Некорректно задан ID родительской ветки.'
        # Защита от дублирования словаря
        if k == 'owner' and current_class.formula == 'dict':
            if DictObjects.objects.filter(parent_code=v, parent_structure_id=current_class):
                return 'Ошибка. У выбранного собственника уже есть объект данного словаря. Данные не сохранены'
            else:
                # Проверим корректность заданного собственника словаря
                owner_manager = ContractCells.objects if current_class.default == 'contract' else Objects.objects
                owner = owner_manager.filter(parent_structure_id=current_class.parent_id, code=v)
                if not owner:
                    return 'Ошибка. Некорректно задан собственник словаря. Не найден объект с кодом ' + str(v)
    return ''


# pdor - prepare dict object request - подготовить объект словаря в стиле реквеста
def pdor(code, headers, params):
    dict_object = {}
    dict_keys = {'string': 'ta_', 'link': 'i_link_', 'float': 'i_float_', 'datetime': 'i_datetime_',
                 'date': 'i_date_', 'bool': 'chb_', 'const': 's_alias_', 'enum': 's_enum_'}
    if code:
        object = ContractCells.objects.filter(parent_structure_id=headers[0]['parent_id'], code=code)
    else:   object = None
    for h in headers:
        if h['formula'] in ('eval', 'file'):
            continue
        if code:
            try:
                key, val = next((k, v) for k, v in params.items() if k == str(h['id']))
            except StopIteration:
                try:
                    o = next(o for o in object if o.name_id == h['id'])
                except StopIteration:
                    val = None
                else:
                    val = o.value
                finally:
                    key = str(h['id'])
        else:
            try:
                key, val = next((k, v) for k, v in params.items() if k == str(h['id']))
            except StopIteration:
                key = str(h['id'])
                val = h['default']
        dict_object[dict_keys[h['formula']] + key] = val
    return dict_object


# vepoc = verify edited param of class
def vepoc(class_type, param_id, **params):
    if 'location' in params and not params['location'] in ('c', 't'):
        return "Некорректно задан параметр location. Значение должно равняться \"c\" или \"t\""
    location = 'c' if 'location' in params and params['location'] == 'c' else 't'
    if not type(param_id) is int:
        return "Некорректно указан ID редактируемого параметра. Укажите целое число"
    if class_type == 'dict':
        manager = Dictionary.objects
    else:
        manager = Contracts.objects if location == 'c' else Designer.objects
    current_param = manager.filter(id=param_id)
    if 'param_type' in params:
        current_param = current_param.filter(formula=params['param_type'])
    if not current_param:
        return 'Некорректно указан ID редактируемого параметра. Параметр не найден'
    else:
        current_param = current_param[0]
    try:
        current_class = manager.get(id=current_param.parent_id, formula=class_type)
    except ObjectDoesNotExist:
        return 'Некорректно задан ID параметра или тип класса. Класс не найден'
    # проверка типа класса
    data_types = [o.value for o in Objects.objects.filter(parent_structure_id=144, name_id=145)]
    if current_param.formula not in data_types:
        return 'Некорректно задан ID параметра. Нельзя указывать ID класса'
    # Проверка имени
    if 'name' in params:
        if not params['name']:
            return 'Некорректно задано имя параметра. Нельзя передавать пустое имя'
        if not type(params['name']) is str:
            return 'Некорректно задано имя параметра. Необходимо передать название в строковом формате'
        current_params = manager.filter(parent_id=current_param.parent_id)
        if class_type != 'dict':
            current_params = current_params.filter(system=False)
        params_names = [cp.name.lower() for cp in current_params]
        if current_param.formula == 'tree':
            params_names.append('наименование')
        if params['name'].lower() in params_names:
            return 'Некорректно задано имя параметра. Нельзя повторять имена реквизитов в рамках одного класса'
        reserved_names = ('link_map', 'business_rule', 'trigger', 'parent', 'parent_branch', 'is_right_tree',
                          'stages', 'parent_code', 'control_field')
        if params['name'] in reserved_names:
            return 'Некорректно задано имя параметра. Нельзя задавать имя из списка зарезервированных системных имен'
        if current_param.name in reserved_names:
            return 'Нельзя переименовывать зарезервированные имена'
        if class_type != 'dict' and current_param.system:
            return 'Нельзя редактировать название для системного параметра'
        if current_param.name == 'Дата и время записи' and class_type == 'contract':
            return 'Нельзя изменять название параметра "Дата и время записи"'
        elif current_param.name == 'Наименование' and class_type == 'table':
            return 'Нельзя изменять название параметра "Наименование"'
        elif current_param.name == 'Собственник' and class_type == 'array':
            return 'Нельзя изменять название параметра "Собственник"'

    # Проверка значения
    link_type = None
    link_id = None
    if 'value' in params and params['value']:
        if class_type == 'dict':
            return 'У типа данных "dict" нет поля "value"'
        elif current_param.formula in ('link', 'const'):
            if not params['value']:
                return 'Не задан параметр value'
            link_type, link_id = convert_procedures.slice_link_header(params['link'])
            if not link_type:
                return 'Некорректно задан параметр "value" для типа данных "' + current_param.formula + '"'
            if link_type not in ('contract', 'table'):
                return 'Некорректно задан параметр "value" для типа данных "' + current_param.formula + '"'
            link_manager = Contracts.objects if link_type == 'contract' else Designer.objects
            if class_type == 'const':
                link_type = 'alias'
            try:
                link_manager.get(id=link_id, formula=link_type)
            except ObjectDoesNotExist:
                return 'Некорректно задан параметр "value" для типа данных "' + current_param.formula + '"'
            # Проверка на потомка
            if database_funs.is_child(current_class, class_type, int(link_id), link_type):
                return 'Некорректно задан параметр "value" для типа данных "' + current_param.formula + '". ' \
                        'Нельзя в качестве родителя указывать потомка'
        elif current_param.formula == 'enum':
            if not type(params['value']) is list:
                return 'Некорректно задан параметр "value" для типа данных "enum". Необходимо передать данные в виде списка строк'
            for pv in params['value']:
                if not type(pv) is str:
                    return 'Некорректно задан параметр "value" для типа данных "enum". Необходимо передать данные в виде списка строк'
        elif current_param.formula == 'eval':
            if not type(params['value']) is str:
                return 'Некорректно задан параметр "value" для типа данных "eval". Необходимо передать данные в виде строки'

    # Проверка умолчания
    if 'default' in params and params['default']:
        if current_param.formula in ('eval', 'enum', 'file') and class_type != 'dict':
            return 'Нельзя изменять поле "default" для типов данных - "eval", "enum", "file"'
        if class_type != 'dict' and current_param.system:
            return 'Нельзя изменять поле "default" для системных полей'
        if not link_type and current_param.formula in ('link', 'const'):
            if class_type == 'dict':
                link_type, link_id = None, None
            else:
                link_type, link_id = convert_procedures.slice_link_header(current_param.value)
        ver_def = interface_procedures.ver_def(class_type, current_param.formula, params['default'], link_type, link_id)
        # для ссылок словарей дополнительная проверка. Должны отличаться только последние цифры
        old_match = re.match(r'(table|contract)\.(\d+)', current_param.default)
        old_link_type = old_match[1]
        old_link_id = old_match[2]
        new_match = re.match(r'(table|contract)\.(\d+)', params['default'])
        new_link_type = new_match[1]
        new_link_id = new_match[2]
        if old_link_id != new_link_id or old_link_type != new_link_type:
            return 'Некорректно задано значение default для типа данных link словаря. ' \
                   'Разрешается изменять только значение по умолчанию - т.е. второе число'
        if ver_def != 'ok':
            return ver_def

    # Проверка булевых полей
    if ('is_required' in params and not type(params['is_required']) is bool) or \
            ('is_visible' in params and not type(params['is_visible']) is bool):
        return ('Некорректно задано логическое поле - is_visible или is_required. '
                'Задайте логическое значение - True или False')
    if class_type == 'dict' and ('is_required' in params or 'delay' in params):
        return ('У типа класса "dict" нет полей "is_required" и "delay"')
    # проверка поля delay:
    if class_type != 'dict' and location == 't' and 'delay' in params and not type(params['delay']) is bool:
        return ('Некорректно задано поле Delay')
    if location == 'c' and 'delay' in params:
        return ('У классов, расположенных в меню контрактов всегда включены отложенные значения, нет возможности включить/отключить delay')
    # проверка таймштампа
    if 'timestamp' in params:
        if not params['timestamp']:
            return 'Нельзя передавать пустое значение временной метки. Укажите данные в формате дата-время'
        if not isinstance(params['timestamp'], datetime):
            return 'Некорректно указано значение временной метки. Укажите данные в формате дата-время'
    # Проверка родительской транзакции
    if 'parent_transact' in params:
        if not params['parent_transact'] or not type(params['parent_transact']) is str:
            return 'Некорректно указан параметр parent_transact. Укажите его в виде строки'

    # Проверка поля "Обязательный для полей название, собственник, дата и время записи"
    if 'is_required' in params:
        if current_class.formula == 'table' and current_param.name == 'Наименование' or\
            current_class.formula == 'contract' and current_param.name == 'Дата и время записи' or\
            current_class.formula == 'array' and current_param.name == 'Собственник' or\
            current_class.formula == 'tree' and current_param.name in ('name', 'parent') or\
            current_class.formula == 'techpro':
            return 'Нельзя изменить поле "is_required" у данного параметра'

    return ('ok')


# copafroc = collect params for requsite of class
def copafroc(request):
    params = {}
    is_done = True
    msg = ''
    if 'is_required' in request.GET:
        params['is_required'] = True if request.GET['is_required'].lower() == 'true' else False
    if 'is_visible' in request.GET:
        params['is_visible'] = True if request.GET['is_visible'].lower() == 'true' else False
    if 'delay' in request.GET:
        params['delay'] = True if request.GET['delay'].lower() == 'true' else False
    if 'value' in request.GET:
        params['value'] = request.GET['value'] if request.GET['value'] else None
        if params['value'] and request.GET['param_type'] == 'enum':
            try:
                params['value'] = params['value'].split(',')
            except:
                is_done = False
                msg += 'Некорректно указано значение для типа данных - "enum". Укажите список строк, разделяя значения запятой\n'
    if 'default' in request.GET:
        params['default'] = request.GET['default'] if request.GET['default'] else None
        if params['default']:
            if request.GET['param_type'] == 'float':
                try:
                    params['default'] = float(params['default'])
                except ValueError:
                    is_done = False
                    msg += 'Ошибка. Некорректно передано параметр реквизита "default". Укажите числовое значение\n'
            elif request.GET['param_type'] == 'bool':
                if not params['value'].lower() in ('true', 'false'):
                    is_done = False
                    msg = 'Ошибка. Некорректно передано параметр реквизита "default". Укажите значение, '\
                          'равное "true" либо "false"\n'
            elif request.GET['param_type'] == 'datetime':
                try:
                    params['default'] = datetime.strptime(params['default'], '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    is_done = False
                    msg = 'Ошибка. Некорректно передано параметр реквизита "default". Укажите дату-время в формате ГГГГ-ММ-ДДТЧЧ:ММ:СС\n'
            elif request.GET['param_type'] == 'date':
                try:
                    params['default'] = datetime.strptime(params['default'], '%Y-%m-%d')
                except ValueError:
                    is_done = False
                    msg = 'Ошибка. Некорректно передано параметр реквизита "default". Укажите дату в формате ГГГГ-ММ-ДД\n'
            elif request.GET['param_type'] in ('const', 'link') and request.GET['class_type'] != 'dict':
                try:
                    params['default'] = int(params['default'])
                except ValueError:
                    is_done = False
                    msg = 'Ошибка. Некорректно передано параметр реквизита "default". Укажите целое число\n'
    if 'timestamp' in request.GET:
        try:
            params['timestamp'] = datetime.strptime(request.GET['timestamp'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            is_done = False
            msg = 'Параметр "timestamp" указан некорректно. Укажите его в формате ГГГГ-ММ-ДДТчч:мм:сс\n'
    if 'parent_transact' in request.GET:
        params['parent_transact'] = request.GET['parent_transact']
    if not is_done:
        params = msg
    return is_done, params


# fc4c = full check for children
def fc4c(class_id, code, location):
    children = database_funs.check_children(class_id, code, location)
    if children:
        counter = 1
        str_objs = ''
        for ch in children:
            address = '/manage-object' if str(ch[0].parent_structure)[0] == 'D' else '/contract'
            for c in ch:
                str_objs += '<a target="_blank" href="' + address + '?class_id=' + str(
                    c.parent_structure_id) + '&object_code=' \
                            + str(c.code) + '">Объект ' + str(counter) + '</a>; '
                counter += 1
        return 'Указанный объект не может быть удален, т.к. есть объекты, ссылающиеся на него: ' + str_objs
    else:
        return 'ok'


def validate_delay_date(str_date):
    list_date_formats = ('%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d.%m.%YT%H:%M', '%d.%m.%Y %H:%M')
    valid_date = None
    for ldf in list_date_formats:
        try:
            valid_date = datetime.strptime(str_date, ldf)
        except ValueError:
            continue
        else:
            break
    return datetime.strftime(valid_date, '%Y-%m-%dT%H:%M')


# vadefoppa = validate_delay_for_PPA
def vadefoppa(new_delay, timestamp, current_class, object_params, location):
    date_delay = new_delay['date_update']
    str_timestamp = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
    if date_delay < str_timestamp:
        new_ts = datetime.strptime(date_delay, '%Y-%m-%dT%H:%M')
        if current_class.formula == 'contract':
            date_create = next(op.value['datetime_create'] for op in object_params if op.name.name == 'system_data')
            if date_delay < date_create:
                new_ts = datetime.strptime(date_create, '%Y-%m-%dT%H:%M:%S')

        elif current_class.formula == 'array' and location == 'contract':
            parent = next(op for op in object_params if op.name__name == 'Собственник')
            parent_date = ContractCells.objects.get(parent_structure_id=current_class.parent_id, code=parent.value,
                                                    name__name='system_data')
            if new_delay['date_update'] < parent_date.value['datetime_create']:
                new_ts = datetime.strptime(parent_date.value['datetime_create'], '%Y-%m-%dT%H:%M:%S')
        new_delay['date_update'] = str_timestamp
        timestamp = new_ts
    return new_delay, timestamp


# delete_object - кверисет - объект
def verify_cc(class_id, delete_object, user_id):
    cc = list(Contracts.objects.filter(parent_id=class_id, name='completion_condition', system=True).values())[0]
    objs = convert_funs.queryset_to_object(delete_object)
    if not contract_funs.do_business_rule(cc, objs[0], user_id):
        return False
    else:
        return True