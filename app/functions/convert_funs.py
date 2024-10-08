import copy
import re
import datetime as da_ti
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum, Q, FloatField, QuerySet, OuterRef, Subquery, Avg, Max, Min, F, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.forms import model_to_dict
import app.functions.tree_funs
import app.functions.tree_procedures
from app.functions import convert_procedures, files_procedures, tree_funs, hist_funs, api_funs2, object_funs
from app.models import Designer, Objects, Contracts, ContractCells, DictObjects, RegistratorLog, TechProcessObjects
from app.other.global_vars import is_mysql


# Преобразование объектов из формата Data_driven в формат ДЖейсон
# Вход. Массив объектов в формате дата драйвен, где каждый объект - массив объектов джанго.
# Массив должен быть упорядоченным по  code, name_id
# Выход - стандартный список словарей
def queryset_to_object(objects):
    if objects:
        name_code = 'code' if hasattr(objects[0], 'code') else 'parent_code'
        objects = objects.order_by(name_code, 'name_id')
    result_json = []
    for o in objects:
        code = o.code if hasattr(o, 'code') else o.parent_code
        try:
            dict = next(rj for rj in result_json if rj['code'] == code)
        except StopIteration:
            dict = {'code': code, 'parent_structure': o.parent_structure_id, 'type': o.parent_structure.formula}
            result_json.append(dict)
        dict[o.name_id] = {'id': o.id, 'name': o.name.name, 'type': o.name.formula, 'value': o.value}
        if hasattr(o, 'delay'):
            dict[o.name_id]['delay'] = o.delay
    return result_json


# Проверка, есть ли у данного объекта ссылающиеся на него объекты.
# вход: айди объекта, айди таблицы
# Выход - Да/нет
def find_links(code, parent_id):
    name_ids = Designer.objects.filter(formula='link', value=str(parent_id)).values_list('id')
    links = Objects.objects.filter(name_id__in=name_ids, value=str(code))
    return True if links else False


# Преобразование ссылки в объект, на который ведет ссылка.
# Вход - Список объектов в формате джейсон, айди поля со ссылкой, is_object - является ли структура объектом.
# По умолчанию да. Но если назначим - False,  то работаем как с контрактом
# Выход - джейсон, поле data с объектом
def select_related(json_object, header):
    # айди класса связанного объекта
    class_type, parent_id = convert_procedures.slice_link_header(header['value']) if 'value' in header \
        else convert_procedures.slice_link_header(re.match(r'^(?:contract|table)\.\d+', header['default'])[0])
    str_header = str(header['id'])
    object_ids = []
    for jo in json_object:
        if header['id'] in jo.keys() and jo[header['id']]['value']:
            object_ids.append(jo[header['id']]['value'])
        elif str_header in jo.keys() and jo[str_header]['value']:
            object_ids.append(jo[str_header]['value'])
    object_ids = set(object_ids) if 'value' in header else set([int(oi) for oi in object_ids])
    # Получили список объектов в формате data_driven
    related_objects = Objects.objects if class_type == 'table' else ContractCells.objects
    related_objects = related_objects.filter(code__in=object_ids, parent_structure_id=parent_id)
    json_related_objects = queryset_to_object(related_objects)  # Получили список объектов в формате джейсон
    # Загрузим связанные объекты
    for jo in json_object:
        if header['id'] in jo.keys() and jo[header['id']]['value']:
            try:
                jo[header['id']]['data'] = next(jro for jro in json_related_objects if jo[header['id']]['value'] and
                                              int(jo[header['id']]['value']) == jro['code'])
            except StopIteration:
                jo[header['id']]['data'] = []
        elif str_header in jo.keys() and jo[str_header]['value']:
            try:
                jo[str_header]['data'] = next(jro for jro in json_related_objects if jo[str_header]['value'] and
                                              int(jo[str_header]['value']) == jro['code'])
            except StopIteration:
                jo[str_header]['data'] = []
    return json_object


# Преобразование объектов из формата Data_driven в формат ДЖейсон.
# Вход - кверисет формата Дата драйвен
def query_to_json(objects):
    objects = objects.select_related('name').order_by('code', 'name_id')
    result_json = []
    for o in objects:
        try:
            dict = next(rj for rj in result_json if rj['code'] == o.code)
        except StopIteration:
            dict = {'code': o.code}
            result_json.append(dict)
        dict[o.name.name] = o.value
    return result_json


def deep_formula(header, objects, user_id, is_contract=False, *link_chain, **params):
    # Обработаем опциональные параметры
    is_draft = True if 'is_draft' in params and params['is_draft'] else False

    if not link_chain:
        link_chain = []
    else:   link_chain = list(link_chain)
    new_link = {'header_id': header['id'], 'is_contract': is_contract}
    if not new_link in link_chain:
        link_chain.append(new_link)
        is_circular = False
    else:
        is_circular = True

    # Объявим процедуры работы с переменными
    def last_var(object, var, value_type, is_contract=False):
        # Вернем код
        if var == 'code':
            try:
                res = object['code']
                return res
            except:
                return 'Ошибка. У данного объекта нет параметра \"Код\"'

        elif var == 'user_id':
            return str(user_id)
        else:
            try:
                var = int(var)
            except:
                return 'Ошибка. Некорректно указан адрес ссылки'
            else:
                try:
                    if is_contract:
                        deep_header = Contracts.objects.filter(id=var).values()[0]
                    else:
                        deep_header = Designer.objects.filter(id=var).values()[0]
                except:
                    return 'Ошибка. Некорректно указан путь к объекту'

            if not var in object or not object[var]:
                res = add_param_to_object(deep_header, object, var, user_id, is_contract, is_draft, *link_chain)
                if res != 'ok':
                    return res

            if deep_header['formula'] == 'const':
                if value_type == 'fact':
                    alias_id = object[deep_header['id']]['value']
                elif value_type == 'delay':
                    alias_id = object[deep_header['id']]['delay'][-1]['value'] if 'delay' in object[deep_header['id']]\
                        and object[deep_header['id']]['delay'] else None
                else:
                    alias_id = object[deep_header['id']]['delay'][-1]['value'] if 'delay' in object[deep_header['id']]\
                        and object[deep_header['id']]['delay'] else object[deep_header['id']]['value']
                val = Contracts.objects.get(id=alias_id).value if is_contract else Designer.objects.get(id=alias_id).value
                return static_formula(val, user_id, *link_chain)
            elif deep_header['formula'] == 'float':
                if value_type == 'fact':
                    val = object[var]['value']
                elif value_type == 'delay':
                    val = sum([d['value'] for d in object[var]['delay']]) if 'delay' in object[var] and object[var]['delay'] else 0
                else:
                    val = object[var]['value'] if object[var]['value'] else 0
                    if 'delay' in object[var] and object[var]['delay']:
                        val += sum([d['value'] for d in object[var]['delay']])
                return val
            elif deep_header['formula'] == 'eval':
                return object[var]['value']
            elif deep_header['formula'] in ['string', 'date', 'datetime', 'enum', 'bool', 'link']:
                if value_type == 'fact':
                    val = object[var]['value']
                elif value_type in 'delay':
                    val = object[var]['delay'][-1]['value'] if 'delay' in object[var] and object[var]['delay'] else ''
                else:
                    val = object[var]['delay'][-1]['value'] if 'delay' in object[var] and object[var]['delay'] else \
                    object[var]['value']
                return val
            elif deep_header['formula'] == 'file':
                location = 'contract' if is_contract else 'table'
                if value_type == 'fact':
                    val = object[var]['value']
                elif value_type == 'delay':
                    val = object[var]['delay'][-1]['value'] if 'delay' in object[var] and object[var]['delay'] else ''
                else:
                    val = object[var]['delay'][-1]['value'] if 'delay' in object[var] and object[var]['delay'] else object[var]['value']
                return files_procedures.get_file_path(val, str(deep_header['parent_id']),
                                                        is_draft=is_draft, location=location) if val else val
            else:   return 'Ошибка. Вероятно ссылка ведет на недопустимый тип данных'

    def link_var(object, var, is_contract=False):
        try:
            var_int = int(var)
            if not var_int in object or not object[var_int]:
                class_manager = Contracts.objects if is_contract else Designer.objects
                header = class_manager.filter(id=var_int).values()
                if not header:
                    return 'Ошибка. Ссылка указана некорректно', False
                else:
                    header = header[0]
                res = add_param_to_object(header, object, var_int, user_id, is_contract, is_draft, *link_chain)
                if res != 'ok':
                    return res, False
            if 'data' in object[var_int]:
                deep_object = object[var_int]['data']
                is_link_contract = True if deep_object['type'] == 'contract' else False
            else:
                class_manager = Contracts.objects if is_contract else Designer.objects
                header = class_manager.filter(id=var_int).values()
                if not header:
                    return 'Ошибка. Ссылка указана некорректно', False
                else:
                    header = header[0]
                deep_link = object[var_int]['value']
                type_class = re.match(r'(?P<name>table|contract)\.(?P<id>[\d]+)?', header['value'])
                is_link_contract = True if type_class.group('name') == 'contract' else False
                if is_link_contract:
                    deep_object = ContractCells.objects
                else:   deep_object = Objects.objects
                parent_structure = int(type_class.group('id'))
                deep_object = deep_object.filter(parent_structure_id=parent_structure, code=int(deep_link))
                deep_object = queryset_to_object(deep_object)[0]
        except:
            return '\'Ошибка. Ссылка некорректна\'', False
        return deep_object, is_link_contract

    def get_tp(obj, array, **opt_params):
        if len(array) != 4:
            return 'Ошибка. Некорректно задана формула техпроцесса'
        tp_id = int(array[1])
        code = int(array[2])
        name_id = int(array[3])
        data_kind = opt_params['type_value']
        if 'tps' in obj and obj['tps'] and obj['tps'] and tp_id in obj['tps'] and name_id in obj['tps'][tp_id]:
            my_tp = obj['tps'][tp_id][name_id]
            return my_tp[data_kind]
        else:
            try:
                my_tp = TechProcessObjects.objects.get(parent_structure_id=tp_id, name_id=name_id, parent_code=code)
            except ObjectDoesNotExist:
                return 'Ошибка. Данные техпроцесса некорректны. Не найден объект'
            if data_kind == 'fact':
                return my_tp.value['fact']
            elif data_kind == 'delay':
                return sum(d['value'] for d in my_tp.value['delay'])
            else:
                fact = my_tp.value['fact'] if my_tp.value['fact'] else 0
                return sum(d['value'] for d in my_tp.value['delay']) + fact


    # Получим все переменные в виде списка словарей
    dict_foreign_formuls = {}
    for o in objects:
        # Если поле еще не было вычислено, вычислим. В противном случае - игнорим
        if not header['id'] in o:
            if is_circular:
                r = 'Ошибка. Ссылка циклична'
            else:
                # Если применен код питон с переменной result - оставим в покое.
                if not header['value']: header['value'] = ''
                if re.search('result', header['value']):
                    formula = header['value']
                else:
                    formula = 'result = ' + header['value']
                # Отработаем вложенные теги
                control_sum_operations = 0
                quan_quots = 0
                ind_qq = 0
                while ind_qq < len(formula):
                    if formula[ind_qq] == '[' and formula[ind_qq + 1] == '[':
                        quan_quots += 1
                    ind_qq += 1
                while re.search(r'\[\[', formula):
                    # Защита от вечного цикла
                    if control_sum_operations >= quan_quots:
                        formula = 'result = \'Ошибка. Некорректно задана формула\''
                        break
                    json_vars = convert_procedures.retreive_tags(formula)
                    for jv in json_vars:
                        k = list(jv.keys())[0]
                        v = list(jv.values())[0]

                        value_var = convert_procedures.userdata_to_interface(header, o['code'], is_contract, False)
                        if value_var:
                            formula = 'result = \'' + value_var + '\''
                            break

                        opt_params = get_opt_params(k)  # получим опциональные параметры
                        if opt_params['node']:
                            if 'code' in o.keys():
                                opt_params['code'] = o['code']
                            else:
                                formula = 'result = \'Ошибка. Параметры branch и cluster можно задавать только в рамках типа данных tree\''
                                break
                        opt_params['type_value'] = v[-1]
                        v = v[:len(v) - 1]
                        if not v:
                            formula = 'result = \'Ошибка. Некорректно задана формула\''
                            break
                        # Если данная формула была вычислена - то укажем ее значение
                        if k in dict_foreign_formuls.keys():
                            value_var = dict_foreign_formuls[k]
                        # Если нет - проверим формулу на версионность
                        else:
                            value_var = wwh(k, v, o, is_contract, user_id, opt_params, *link_chain, **params)  # Если формула обращается к истории
                            # Если формула внешняя, то добавим ее в список внешних формул
                            if re.match(r'\s*table|contract', k) and value_var and not opt_params['node']:
                                dict_foreign_formuls[k] = value_var
                        if value_var or type(value_var) in (int, bool, list):
                            pass
                        # Если в формуле маркер class_id
                        elif re.search(r'\s*class_id\s*', k):
                            value_var = header['parent_id']
                        # Маркер user_id
                        elif re.search(r'user_id', k):
                            value_var = user_id
                        # Маркер child_class
                        elif re.search(r'child_class', k):
                            value_var = params['child_class'] if 'child_class' in params else None
                        # Маркер level
                        elif re.match(r'\s*level\s*', k):
                            for vv in o.values():
                                if type(vv) is dict and 'name' in vv:
                                    if vv['name'] == 'parent_branch':
                                        if not vv['value']:
                                            value_var = 0
                                        else:
                                            # найдем дерево
                                            header_manager = Contracts.objects if is_contract else Designer.objects
                                            current_class = header_manager.get(id=o['parent_structure'])
                                            value_var = tree_funs.glwt(current_class.parent_id, vv['value'], is_contract)
                                        break
                                    elif vv['name'] == 'parent':
                                        if not vv['value']:
                                            value_var = 0
                                        else:
                                            value_var = tree_funs.glwt(o['parent_structure'], vv['value'], is_contract)
                                        break
                            else:
                                header_manager = ContractCells.objects if is_contract else Objects.objects
                                parent_branch = header_manager.filter(parent_structure_id=header['parent_id'],
                                                                   name__name='parent', code=o['code'])
                                value_var = 0
                                if parent_branch:
                                    parent_branch = parent_branch[0]
                                    if parent_branch.value:
                                        value_var = tree_funs.glwt(header['parent_id'], parent_branch.value, is_contract)
                        # Если имеем дело с техпроцессом
                        elif v[0].lower() == 'tp':
                            value_var = get_tp(o, v, **opt_params)
                        # Если формула внешняя - получим  значение переменной
                        elif v[0].lower() in ('table', 'contract'):
                            value_var = foreign_link(v, user_id, *link_chain, is_draft=is_draft, **opt_params)
                            if not opt_params['node']:
                                dict_foreign_formuls[k] = value_var
                        elif len(v) >= 1:
                            deep_object = o
                            is_link_contract = is_contract
                            for i in range(len(v)):
                                if i < len(v) - 1:
                                    deep_object, is_link_contract = link_var(deep_object, v[i], is_link_contract)
                                else:
                                    if type(deep_object) is dict:
                                        value_var = last_var(deep_object, v[i], opt_params['type_value'], is_link_contract)
                                    else:
                                        value_var = 'Ошибка. Ссылка некорректна'

                        if type(value_var) is str:
                            value_var = re.sub(r'\'', '\"', value_var)
                            if re.search(r'\n', value_var):
                                value_var = '\'\'\'' + value_var + '\'\'\''
                            else:
                                value_var = '\'' + value_var + '\''
                        elif type(value_var) is bool:
                            value_var = 'True' if value_var else "False"
                        elif type(value_var) is list:
                            value_var = str(value_var) if value_var else '[]'
                            value_var = value_var.replace('[[', '[ [').replace(']]', '] ]')
                        elif not value_var:
                            value_var = '0'
                        else:   value_var = str(value_var)
                        escaped_k = convert_procedures.scfre(k)  # экранирование строки с формулой
                        formula = re.sub(r'\[\[' + escaped_k + r'\]\]', str(value_var), formula, re.S)
                    control_sum_operations += 1
                formula = condition(formula)  # Выполним блок условий
                try:
                    glob = {}
                    exec(formula, glob)
                    r = glob['result']
                except Exception as ex:
                    r = 'Ошибка - ' + str(ex) + ''
                # Защита от кверисета
                if isinstance(r, QuerySet):
                    r = list(r.values())
            o[header['id']] = {'name': header['name'], 'type': 'eval', 'value': r}


def static_formula(formula, user_id, *link_chain, **params):
    # Обработка опциональных параметров
    is_draft = True if 'is_draft' in params and params['is_draft'] else False
    # Получим все переменные в виде списка словарей
    json_vars = convert_procedures.retreive_tags(formula)
    if not re.search('result[\s+|]=', formula):
        formula = 'result = ' + formula
    for jv in json_vars:
        k = list(jv.keys())[0]
        v = list(jv.values())[0]
        opt_params = get_opt_params(k)  # получим опциональные параметры
        opt_params['value_type'] = v.pop()
        value_var = wwh(k, v, None, False, user_id, opt_params, *link_chain, **params)
        if not value_var:
            value_var = foreign_link(v, user_id, *link_chain, is_draft=is_draft, **opt_params)
        if type(value_var) is str:
            value_var = '\'' + value_var + '\''
        else:   value_var = str(value_var)
        k = convert_procedures.scfre(k)
        formula = re.sub('\[\[' + k + '\]\]', value_var, formula)
        formula = condition(formula)  # Выполним блок условий
    try:
        loc = {'result': None}
        exec(formula, {}, loc)
        r = loc['result']
    except Exception as ex:
        r = '\'Ошибка: ' + str(ex) + '\''
    else:
        if isinstance(r, QuerySet):
            r = list(r.values())
    return r


# Преобразование классов-папок в структуру-джейсон-матрешку дочерние классы и папки кладутся в родительские
# Вход - 1) основной кверисет, 2)итерируемый кверисет - т.н. родители
def query_to_tree(query, parents):
    sort_order = {'folder': 0, 'table': 1, 'contract': 2, 'alias': 3, 'array': 4, 'dict': 5, 'tree': 6, 'tp': 7,
                  'techprocess': 8}
    dict_parents = {'folder': ('folder', ), 'tree': ('folder', ), 'table': ('folder', 'tree'),
                    'contract': ('folder', 'tree'), 'array': ('contract', 'table'), 'dict': ('contract', 'table'),
                    'techprocess': ('contract', 'array'), 'alias': ('folder', ), 'tp': ('contract', 'array')}
    query.sort(key=lambda x: sort_order[x['formula']])
    i = 0
    while i < len(parents):
        children = []
        p = parents[i]
        j = 0
        while j < len(query):
            q = query[j]
            if p['id'] == q['parent_id'] and p['formula'] in dict_parents[q['formula']]:
                children.append(q)
                del query[j]
            else:
                j += 1
        if children:
            p['children'] = children
            query_to_tree(query, children)
            i = parents.index(p)
        i += 1


# Причесывание  объектов к выводу в шаблон
def prepare_table_to_template(headers, objects, user_id, is_contract=False, **params):
    fncbd = True if not 'fncbd' in params or params['fncbd'] else False  # fncbd = fill nulls consts by defaults
    for h in headers:
        # для алиасов
        if h['formula'] == 'const':
            for o in objects:
                # Заполним нулевые значения
                if not h['id'] in o or not o[h['id']]['value']:
                    if fncbd:
                        o[h['id']] = {}
                        o[h['id']]['value'] = int(h['default']) if h['default'] else h['const'][0]['id']
                    else:   continue
                val = o[h['id']]['value']
                try:
                    cc_val = next(cc['value'] for cc in h['const'] if cc['id'] == val)
                except StopIteration:
                    o[h['id']]['result'] = ''
                else:
                    o[h['id']]['result'] = static_formula(cc_val, user_id)
        # для ссылок
        if h['formula'] == 'link' and h['is_visible']:
            objects = select_related(objects, h)
        # для формул
        elif h['formula'] == 'eval':
            deep_formula(h, objects, user_id, is_contract, **params)
        # для массивов
        elif h['formula'] == 'array':
            owners = [o['code'] for o in objects]
            class_manager = Contracts.objects if is_contract else Designer.objects
            headers_array = list(class_manager.filter(parent_id=h['id']).order_by('priority').values())
            headers_ids = []
            vis_headers_array = []
            header_owner = None
            for ha in headers_array:
                if ha['name'] == 'Собственник':
                    header_owner = ha
                    headers_ids.append(ha['id'])
                    vis_headers_array.append(ha)
                if ha['is_visible']:
                    convert_procedures.ficoitch(ha)
                    headers_ids.append(ha['id'])
                    vis_headers_array.append(ha)
                if len(vis_headers_array) >= 6:
                    break
            object_manager = ContractCells.objects if is_contract else Objects.objects
            array_codes = object_manager.filter(parent_structure_id=h['id'], name_id=header_owner['id'],
                                                value__in=owners).values('code')
            array_children = object_manager.filter(parent_structure_id=h['id'], code__in=Subquery(array_codes),
                                                   name_id__in=headers_ids)
            array_children = queryset_to_object(array_children)
            for o in objects:
                o[h['id']] = {}
                o[h['id']]['objects'] = [ac for ac in array_children if o['code'] == int(ac[header_owner['id']]['value'])]
                o[h['id']]['headers'] = vis_headers_array
                prepare_table_to_template(headers_array, o[h['id']]['objects'], user_id, is_contract)


# добавим в массив словари
def add_dicts(objects, all_my_dicts):
    codes = [o['code'] for o in objects]
    for amd in all_my_dicts:
        dicts = DictObjects.objects.filter(code__in=codes, parent_structure_id=amd['id'])
        dicts = queryset_to_object(dicts)
        for o in objects:
            try:
                d = next(d for d in dicts if d['code'] == o['code'])
            except StopIteration:
                o['dict_' + str(amd['id'])] = None
            else:
                # добавим отсутствующие поля,заполненные умолчаниями
                amd_children = amd['children']
                for ac in amd_children:
                    if not ac['id'] in d.keys():
                        d[ac['id']] = {'id': None, 'name': ac['name'], 'type': ac['formula'], 'value': ac['default']}
                o['dict_' + str(amd['id'])] = d


# процедура выполнения блока условия
def condition(condition_string):
    find_condition = re.findall(r'if\s*\(.+?\;.*?\;.*?\)', condition_string, flags=re.DOTALL)
    for fc in find_condition:
        items_condition = re.search(
            r'if\s*\(\s*(?P<first>[\wа-яА-Я\+\-\*\/\,\.\'\"\s]+)'
            '(?P<sign><=|>=|<>|<|>|=)\s*(?P<last>[\wа-яА-Я\+\-\*\/\,\.\'\"\s]+?)\;', fc)
        results_condition = re.search(r'\;\s*(?P<true>.*)\s*\;\s*(?P<false>.*)\s*\)', fc)
        if items_condition and results_condition:
            dict_sign = {'<=': '<=', '>=': '>=', '<>': '!=', '<': '<', '>': '>', '=': '=='}
            code = 'if ' + items_condition['first'] + ' ' + dict_sign[items_condition['sign']] + ' ' \
                   + items_condition['last'] + ':\t' + 'result = ' + results_condition['true'] + '\nelse:\tresult = '\
                   + results_condition['false']
        else:
            return re.sub(r'if\(.+\;.*\;.*\)', '\'Ошибка синтаксиса условия\'', condition_string)
        try:
            exec(code, globals())
            r = result
        except Exception as ex:
            r = 'Ошибка: ' + str(ex)
        if not type(r) in (int, float, bool):
            r = '\'' + r + '\''
        # Заменим блок условия результатом
        condition_string = condition_string.replace(fc, str(r))
        # condition_string = re.sub(fc, str(r), condition_string, flags=re.DOTALL)
    return condition_string


def foreign_link(array, user_id, *link_chain, **params):
    # Получить запрос Q для выражения кода вида f18gt45. Вход - строковой код. Выход - Q или ложь
    # формат запроса f[0] - запрос [id поля класса][eq - равно]|[ne - не равно]|[gt - больше]
    # |[ge - больше или равно]|[lt - меньше]|[le - меньше или равно][id_поля]
    if array[0] not in ('table', 'contract'):
        return 'Ошибка. Формула задана некорректно'
    is_contract = True if array[0] == 'contract' else False
    head_manager = Contracts.objects if is_contract else Designer.objects
    manager = ContractCells.objects if is_contract else Objects.objects
    logical_sign = 'or' if 'logical_sign' in params and params['logical_sign'].lower() == 'or' else 'and'
    agr_fun = params['agr_fun'] if 'agr_fun' in params else 'sum'
    if not 'type_value' in params:
        params['type_value'] = 'state'
    try:
        parent_structure_id = int(array[1])
    except ValueError:
        return 'Ошибка. Некорректно указан ID класса'
    current_class = None
    # Получим текущий класс
    if len(array) > 2:
        try:
            current_class = head_manager.get(id=parent_structure_id)
        except ObjectDoesNotExist:
            return 'Ошибка. Указанного класса нет в системе'
        else:
            if current_class.formula not in ('table', 'contract', 'alias', 'array'):
                return 'Ошибка. Некорректно указан ID класса'

    def get_filtered_array():
        headers = head_manager.filter(parent_id=current_class.id)
        str_source_codes = ', '.join([str(c) for c in source_codes])
        dict_cmp_signs = {'eq': '=', 'ne': '<>', 'gt': '>', 'lt': '<', 'ge': '>=', 'le': '<=', 'lk': 'like'}
        table_name = 'app_contractcells' if is_contract else 'app_objects'
        filters = re.findall(r'\d+[eqngtlk]{2}.+?(?:;|$)', code)
        total_codes = []
        def work_with_null(total_codes, log_sign, is_bool):
            q = Q(value=True) if is_bool else Q(value__isnull=False)
            if log_sign == 'and':
                if filters.index(f) == 0:
                    query = manager.filter(q, name_id=field_id).values('code')
                    if source_codes:
                        query = query.filter(code__in=source_codes)
                    if null_val:
                        query = manager.filter(parent_structure_id=current_class.id) \
                            .exclude(code__in=Subquery(query)).values('code').distinct()
                    total_codes = [q['code'] for q in query]
                else:
                    query = manager.filter(q, name_id=field_id, code__in=total_codes).values('code')
                    operative_codes = [q['code'] for q in query]
                    if null_val:
                        total_codes = [tc for tc in total_codes if tc not in operative_codes]
                    else:
                        total_codes = operative_codes
            else:
                query = manager.filter(q, name_id=field_id).exclude(code__in=total_codes).values('code')
                if null_val:
                    query = manager.filter(parent_structure_id=current_class.id).exclude(code__in=total_codes) \
                        .exclude(code__in=Subquery(query)).values('code').distinct()
                total_codes += [q['code'] for q in query]
            return total_codes

        for f in filters:
            match_filter = re.match(r'(\d+)([eqngtlk]{2})(.*?)(?:;|$)', f)
            field_id = int(match_filter[1])
            header = next(h for h in headers if h.id == field_id)
            sign = match_filter[2].lower()
            cmp_val = match_filter[3]
            null_val = False
            if cmp_val[-5:] == '+null':
                cmp_val = cmp_val[:-5]
                null_val = True
            if header.formula in ('eval', 'const'):
                objs = manager.filter(parent_structure_id=parent_structure_id)
                if source_codes:
                    objs = objs.filter(code__in=source_codes)
                if filters.index(f):
                    if logical_sign == 'and':
                        if total_codes:
                            objs = objs.filter(code__in=total_codes)
                            total_codes = []
                        else:
                            break
                    else:
                        objs = objs.exclude(code__in=total_codes)
                objs = queryset_to_object(objs)
                dict_header = model_to_dict(header)
                if header.formula == 'eval':
                    deep_formula(dict_header, objs, user_id, is_contract, *link_chain)
                else:
                    convert_procedures.ficoitch(dict_header)
                    prepare_table_to_template((dict_header,), objs, user_id, is_contract)
                if cmp_val[0] not in ('\'\"') and cmp_val[len(cmp_val) - 1] not in ('\'\"'):
                    if cmp_val in ('true', 'false'):
                        cmp_val = cmp_val == 'true'
                    elif cmp_val == 'null':
                        cmp_val = 0
                    else:
                        try:
                            cmp_val = float(cmp_val)
                        except ValueError:
                            return 'Ошибка. Некорректно задан фильтр для агрегатной функции<br>'
                else:
                    cmp_val = cmp_val[1:len(cmp_val) - 1]
                value_location = 'value' if header.formula == 'eval' else 'result'
                for o in objs:
                    if null_val:
                        if not o[header.id][value_location]:
                            total_codes.append(o['code'])
                            continue
                    try:
                        if convert_procedures.fitoop(o[header.id][value_location], sign, cmp_val):
                            total_codes.append(o['code'])
                    except:
                        pass
                continue
            if header.formula == 'bool':
                cmp_val = cmp_val.lower()
            elif header.formula in ('string', 'enum', 'file'):
                if sign == 'lk':
                    if is_mysql:
                        cmp_val = ('"%%' + cmp_val[1:len(cmp_val) - 1] + '%%"').lower()
                    else:
                        cmp_val = cmp_val.lower()[1:len(cmp_val) - 1]
            # Работа с нулевыми значениями
            if header.formula == 'bool' or cmp_val == 'null':
                if header.formula == 'bool':
                    null_val = sign == 'eq' and cmp_val == 'false' or sign == 'ne' and cmp_val == 'true'
                else:
                    null_val = sign == 'eq' and cmp_val == 'null'
                total_codes = work_with_null(total_codes, logical_sign, header.formula == 'bool')
                continue
            # Если не работаем с нулями, продолжим
            q = 'select id, code from ' + table_name + ' where name_id = ' + match_filter[1]
            if header.formula in ('string', 'enum', 'file'):
                if is_mysql:
                    q += ' and LOWER(JSON_UNQUOTE(value)) '
                else:
                    q += ' and JSON_EXTRACT(value, "$") '
            elif header.formula in ('date', 'datetime') and is_mysql:
                q += ' and JSON_UNQUOTE(JSON_EXTRACT(value, "$")) '
            else:
                if is_mysql:
                    q += ' and value '
                else:
                    q += ' and JSON_EXTRACT(value, "$") '
            q += dict_cmp_signs[sign] + ' ' + cmp_val
            if filters.index(f) == 0:
                if source_codes:
                    q += ' and code in (' + str_source_codes + ')'
            elif total_codes:
                operand = 'not' if logical_sign == 'or' else ''
                q += ' and code ' + operand + ' in (' + ', '.join(str(tc) for tc in total_codes) + ')'
                if source_codes:
                    q += ' and code in (' + str_source_codes + ')'
                if logical_sign == 'and':
                    total_codes = []
            # если не первая итерация, то результаты предыдущих были нулевыми. знак И - не работаем. ИЛИ - продолжаем
            elif logical_sign == 'and':
                break
            # SQLite не работает с кириллицей. Поэтому запрашиваем все и обрабатываем запрос здесь
            if not is_mysql and header.formula == 'string' and sign == 'lk':
                all_query = manager.filter(name_id=int(field_id), value__isnull=False)
                if total_codes:
                    if logical_sign == 'and':
                        all_query = all_query.filter(code__in=total_codes)
                    else:
                        all_query = all_query.exclude(code__in=total_codes)
                reg_ex = ''.join('\\' + v if not v.isalpha() else v for v in cmp_val)
                total_codes += [aq.code for aq in all_query if re.search(reg_ex, aq.value, re.IGNORECASE)]
            else:
                for mor in manager.raw(q):
                    total_codes.append(mor.code)
            if null_val:
                total_codes = work_with_null(total_codes, 'or', False)
        return total_codes

    if len(array) < 2 or len(array) > 4:
        return 'Ошибка. Некорректно указан адрес ссылки'

    try:
        code = int(array[2])
    except:
        code = array[2]

    # Прямая внешняя ссылка - по ID ячейки
    if len(array) == 2:
        object_manager = ContractCells.objects if is_contract else Objects.objects
        current_object = object_manager.filter(id=array[1]).select_related('name')
        if current_object:
            current_object = current_object[0]
        else:
            return 'Ошибка. Некорректно указан ID прямой ссылки на ячейку'
        if current_object.name.formula == 'file':
            location = 'contract' if is_contract else 'table'
            if params['type_value'] == 'fact':
                val = current_object.value
            elif params['type_value'] == 'delay':
                val = current_object.delay[-1]['value'] if current_object.delay else ''
            else:
                val = current_object.delay[-1]['value'] if current_object.delay else current_object.value
            result = files_procedures.get_file_path(val, str(current_object.parent_structure_id), location=location) if val\
                else val
        elif current_object.name.formula == 'float':
            if params['type_value'] == 'fact':
                result = current_object.value
            elif params['type_value'] == 'delay':
                result = sum([d['value'] for d in current_object.delay]) if current_object.delay else 0
            else:
                result = sum([d['value'] for d in current_object.delay]) if current_object.delay else 0
                result += current_object.value if current_object.value else 0
        elif current_object.name.formula == 'const':
            if params['type_value'] == 'fact':
                val = current_object.value
            elif params['type_value'] == 'delay':
                val = current_object.delay[-1]['value'] if current_object.delay else None
            else:
                val = current_object.delay[-1]['value'] if current_object.delay else current_object.value
            manager = Contracts.objects if current_object.name.value[0] == 'c' else Designer.objects
            const = manager.filter(id=val)
            if const:
                result = static_formula(const[0].value, user_id, *link_chain, **params)
            else:
                result = None
        else:
            if params['type_value'] == 'fact':
                result = current_object.value
            elif params['type_value'] == 'delay':
                result = current_object.delay[-1]['value'] if current_object.delay else ''
            else:
                result = current_object.delay[-1]['value'] if current_object.delay else current_object.value
        return result
    # ссылка на параметр объекта
    elif len(array) == 4:
        try:
            name_id = int(array[3])
        except ValueError:
            return 'Ошибка. Некорректно задано ID выводимго поля. Поле обязательно должно быть целым числом'

        cell_type = head_manager.filter(id=name_id).values()
        if cell_type:   cell_type = cell_type[0]
        else:    return 'Ошибка. Не найден класс или его поле'

        # для конкретного объекта
        if type(code) is int:
            object = manager.filter(parent_structure_id=parent_structure_id, code=code, name_id=name_id)
            if object:
                object = object[0]
                fact = object.value
                if cell_type['formula'] == 'float':
                    delay = sum([d['value'] for d in object.delay]) if object.delay else 0
                else:
                    delay = sorted(object.delay, key=lambda x: x['date_update'])[0]['value'] if object.delay else None
            else:
                if cell_type['formula'] == 'eval':
                    obj = {}
                    deep_formula(cell_type, (obj,), user_id, is_contract, *link_chain)
                    fact = obj[cell_type['id']]['value']
                    delay = None
                else:
                    fact = 0 if cell_type['formula'] == 'float' else None
                    delay = 0 if cell_type['formula'] == 'float' else None
            if params['type_value'] == 'fact':
                val = fact
            elif params['type_value'] == 'state':
                if cell_type['formula'] == 'float':
                    val = fact + delay
                else:
                    val = delay if delay else fact
            else:
                val = delay
            return val
        # для агрегации нескольких объектов
        else:
            # Если вычисляем в рамках одной ветки - получаем список кодов объектов в данном ветке
            if params['node']:
                source_codes = convert_procedures.gc1b(current_class, params['code'], params['node'], is_contract)
            else:
                source_codes = []
            base_query = manager.filter(parent_structure_id=parent_structure_id)
            if str(code).lower() == 'all':  # агрегация всего
                if params['node']:
                    base_query = base_query.filter(code__in=source_codes)
            elif code.lower()[0] == 'f':
                total_codes = get_filtered_array()
                if type(total_codes) is str and total_codes.lower()[:6] == 'ошибка':
                    return total_codes
                base_query = base_query.filter(code__in=total_codes)
            else:
                return 'Ошибка. Некорректно задан код объекта или параметр фильтрации данных<br>'
            data_types_and_agr_funs = {
                'count': ('float', 'string', 'bool', 'date', 'datetime', 'link', 'enum', 'const', 'eval'),
                'max': ('float', 'date', 'datetime', 'eval', 'const'),
                'min': ('float', 'date', 'datetime', 'eval', 'const'),
                'avg': ('float', 'eval', 'const'),
                'sum': ('float', 'eval', 'const')}
            def get_current_val(type_val, data_type, cell):
                if type_val == 'delay':
                    if data_type == 'float':
                        current_val = sum(d['value'] for d in cell.delay) if cell.delay else 0
                    else:
                        current_val = next(d['value'] for d in cell.delay.sort(key=lambda x: x['date_update'])) \
                            if cell.delay else ''
                elif type_val == 'fact':
                    current_val = cell.value
                else:
                    if data_type == 'float':
                        fact = cell.value if cell.value else 0
                        delay = sum(d['value'] for d in cell['delay']) if cell.delay else 0
                        current_val = fact + delay
                    else:
                        delay = next(d['value'] for d in sorted(cell.delay, key=lambda x: x['date_update'])) \
                            if cell.delay else ''
                        current_val = delay if delay else cell.value
                return current_val

            def agr_from_eval(objs, agr_fun):
                if cell_type['formula'] == 'eval':
                    deep_formula(cell_type, objs, user_id, is_contract, *link_chain)
                    key_val = 'value'
                else:
                    convert_procedures.ficoitch(cell_type)
                    prepare_table_to_template((cell_type, ), objs, user_id, is_contract)
                    key_val = 'result'
                agr_val = 0
                if agr_fun == 'sum':
                    for o in objs:
                        try:
                            agr_val += o[cell_type['id']][key_val]
                        except:
                            pass
                else:
                    for o in objs:
                        if not agr_val:
                            agr_val = o[cell_type['id']][key_val]
                            continue
                        try:
                            if agr_val < o[cell_type['id']][key_val] and agr_fun == 'max' or \
                                    agr_val > o[cell_type['id']][key_val] and agr_fun == 'min':
                                agr_val = o[cell_type['id']][key_val]
                        except: continue
                return agr_val

            if cell_type['formula'] not in data_types_and_agr_funs[agr_fun]:
                return 'Ошибка. Невозможно вычислить функцию "' + agr_fun + '" для типа данных "' + cell_type['formula'] + '"<br>'
            if agr_fun == 'count':
                agr_val = base_query.values('code').distinct().count()
            elif agr_fun in ('max', 'min'):
                agr_val = None
                if cell_type['formula'] in ('float', 'date', 'datetime'):
                    base_query = base_query.filter(name_id=name_id)
                    for bq in base_query:
                        current_val = get_current_val(params['type_value'], cell_type['formula'], bq)
                        if current_val == None:
                            continue
                        if not agr_val:
                            agr_val = current_val
                            continue
                        if agr_val < current_val and agr_fun == 'max' or agr_val > current_val and agr_fun == 'min':
                            agr_val = current_val
                else:
                    objs = queryset_to_object(base_query)
                    agr_val = agr_from_eval(objs, agr_fun)
            else:
                agr_val = 0
                # вычислим для начала сумму
                if cell_type['formula'] == 'float':
                    query = base_query.filter(name_id=name_id)
                    for q in query:
                        agr_val += get_current_val(params['type_value'], cell_type['formula'], q)
                else:
                    objs = queryset_to_object(base_query)
                    agr_val = agr_from_eval(objs, 'sum')
                if agr_fun == 'avg':
                    if cell_type['formula'] == 'float':
                        quantity = base_query.values('code').distinct().count()
                    else:
                        quantity = len(objs)
                    agr_val = agr_val / quantity
            return agr_val
    # Ссылка на константу или вывод массива данных (массив длиной в 3)
    else:
        # goff - get objects from formula
        def goff(objects, class_id, user_id, is_contract):
            exclude_names = ('is_right_tree', 'business_rule', 'link_map', 'trigger')
            head_manager = Contracts.objects if is_contract else Designer.objects
            headers = head_manager.filter(parent_id=class_id).exclude(name__in=exclude_names).exclude(formula='array').values()
            if 'fields' in params:
                headers = headers.filter(id__in=params['fields'])
            objects = queryset_to_object(objects)
            prepare_table_to_template(headers, objects, user_id, is_contract)
            return objects

        # Вернем массив объектов
        if array[2] == 'all':
            # вытащив двумерный массив объектов, где каждый объект массива первого уровня - массив объектов второго уровня.
            # А каждый объект массива второго уровня - состояние объекта в конкретный момент времени
            if 'date_to' in params or 'date_from' in params:
                date_from = params['date_from'] if 'date_from' in params else da_ti.datetime(1970, 1, 1)
                date_to = params['date_to'] if 'date_to' in params else da_ti.datetime.today()
                object_codes = manager.filter(parent_structure_id=parent_structure_id).values('code').distinct()
                object_codes = [oc['code'] for oc in object_codes]
                loc = 'contract' if is_contract else 'table'
                delete_object_codes = RegistratorLog.objects.filter(json_class=parent_structure_id, json__location=loc,
                                                                    date_update__gte=date_from, reg_name=8)
                object_codes += [doc.json_income['code'] for doc in delete_object_codes]
                create_objs = RegistratorLog.objects.filter(json_class=parent_structure_id, date_update__gte=date_to,
                                                         reg_name=5, json__location=loc)
                if create_objs:
                    object_codes = [oc for oc in object_codes if oc not in create_objs]
                objects = []
                if object_codes:
                    path_info = '/contract' if is_contract else '/manage-object'
                    tom = object_funs.get_tom(parent_structure_id, user_id, loc, path_info)
                    for oc in object_codes:
                        hist = list(RegistratorLog.objects \
                                    .filter(json_class=parent_structure_id, json__code=oc, date_update__gte=date_from,
                                            date_update__lte=date_to, reg_name__in=(13, 15, 22)).order_by('date_update') \
                                    .values('transact_id', 'date_update').distinct())
                        obj_versions = []
                        if hist:
                            obj = {}
                            for h in hist:
                                date_update = da_ti.datetime.strftime(h['date_update'], '%Y-%m-%dT%H:%M:%S')
                                if hist.index(h) == 0:
                                    obj = hist_funs.gov(parent_structure_id, oc, loc, h['date_update'], tom, user_id,
                                                        children=False)
                                    obj['date_update'] = date_update
                                    obj_versions.append(obj)
                                else:
                                    one_change_hist = RegistratorLog.objects.filter(transact_id=h['transact_id'])
                                    for och in one_change_hist:
                                        type_val = 'delay' if och.reg_name == 22 else 'value'
                                        obj[och.json['name']][type_val] = och.json[type_val]
                                    obj['date_update'] = date_update
                                    obj_versions.append(copy.deepcopy(obj))
                        else:
                            obj = hist_funs.gov(parent_structure_id, oc, loc, date_from, tom, user_id, children=False)
                            if obj:
                                date_from += da_ti.timedelta(seconds=1)
                                obj['date_update'] = da_ti.datetime.strftime(date_from, '%Y-%m-%dT%H:%M:%S')
                                obj_versions.append(obj)
                        if obj_versions:
                            objects.append(obj_versions)
            # Вытащим массив объектов по состоянию на дату
            elif 'version' in params or 'version_after' in params:
                is_after = 'version_after' in params
                str_date = params['version_after'] if is_after else params['version']
                objects = convert_procedures.gvfo(parent_structure_id, str_date, is_contract, is_after, user_id)[0]
            elif 'version_number' in params:
                objects = 'Ошибка. Параметр "version_number" не применим к выводу массива объектов<br>'
            # вытащим современный массив всех объектов заданного класса
            else:
                objects = manager.filter(parent_structure_id=parent_structure_id)
                # Если есть маркер "ветка" или "кластер"
                if params['node']:
                    source_codes = convert_procedures.gc1b(current_class, params['code'], params['node'], is_contract)
                    objects = objects.filter(code__in=source_codes)
                objects = goff(objects, parent_structure_id, user_id, is_contract)
                # упорядочиваем
                if 'order' in params:
                    objects = convert_procedures.sobah(objects, params['order'])
            return objects
        # вернем массив данных по фильтрам
        elif array[2][0] == 'f':
            if 'date_to' in params or 'date_from' in params:
                date_from = params['date_from'] if 'date_from' in params else da_ti.datetime(1970, 1, 1)
                date_to = params['date_to'] if 'date_to' in params else da_ti.datetime.today()
                objects = []
                loc = 'contract' if is_contract else 'table'
                base_query = RegistratorLog.objects.filter(json_class=parent_structure_id, date_update__lte=date_to)
                delete_codes = base_query.filter(json_income__location=loc, reg_name__in=(8, 16))\
                    .annotate(code=F('json_income__code')).values('code').distinct()
                base_codes = base_query.filter(json__location=loc, reg_name__in=(5, 13, 15))\
                    .annotate(code=F('json__code')).values('code').distinct().exclude(code__in=[dc['code'] for dc in delete_codes])
                path_info = '/contract' if is_contract else '/manage-object'
                tom = object_funs.get_tom(parent_structure_id, user_id, loc, path_info)
                array_conds = convert_procedures.gaoc(array[2])
                for bc in base_codes:
                    obj = hist_funs.gov(parent_structure_id, bc['code'], loc, date_from, tom, user_id, children=False)
                    if convert_procedures.foblc(obj, tom['headers'], array_conds, logical_sign):
                        array_objs = []
                        date_from += da_ti.timedelta(seconds=1)
                        obj['date_update'] = da_ti.datetime.strftime(date_from, '%Y-%m-%dT%H:%M:%S')
                        array_objs.append(obj)
                        all_hist = RegistratorLog.objects\
                            .filter(json_class=parent_structure_id, json__code=bc['code'], json__location=loc,
                                    date_update__gte=date_from, date_update__lte=date_to, reg_name__in=(13, 15))\
                            .order_by('date_update')
                        if all_hist:
                            copy_obj = copy.deepcopy(obj)
                            transact_id = ''
                            index = 0
                            for ah in all_hist:
                                if ah.transact_id != transact_id:
                                    transact_id = ah.transact_id
                                    if index:
                                        array_objs.append(copy.deepcopy(copy_obj))
                                    copy_obj['date_update'] = da_ti.datetime.strftime(ah.date_update, '%Y-%m-%dT%H:%M:%S')
                                copy_obj[ah.json['name']]['value'] = ah.json['value']
                                index += 1
                            array_objs.append(copy.deepcopy(copy_obj))
                        objects.append(array_objs)
                return objects
            elif 'version' in params or 'version_after' in params:
                is_after = 'version_after' in params
                str_date = params['version_after'] if is_after else params['version']
                all_objs, tom = convert_procedures.gvfo(parent_structure_id, str_date, is_contract, is_after, user_id)
                array_conds = convert_procedures.gaoc(array[2])
                objects = []
                for ao in all_objs:
                    if convert_procedures.foblc(ao, tom['headers'], array_conds, logical_sign):
                        objects.append(ao)
            else:
                total_codes = get_filtered_array()
                if type(total_codes) is str and total_codes.lower()[:6] == 'ошибка':
                    return total_codes
                objects = manager.filter(parent_structure_id=parent_structure_id, code__in=total_codes)
                if 'fields' in params:
                    objects = objects.filter(name_id__in=params['fields'])
                objects = goff(objects, parent_structure_id, user_id, is_contract)
                # упорядочиваем
                if 'order' in params:
                    objects = convert_procedures.sobah(objects, params['order'])
                # выворачиваем
                if 'lifo' in params:
                    objects.sort(key=lambda x: x['code'], reverse=True)
            return objects
        # Вернем объект константы
        else:
            head_manager = Contracts.objects if is_contract else Designer.objects
            try:
               const_id = int(array[2])
            except ValueError:
                return 'Ошибка. Некорректно задана формула'
            try:
                header = head_manager.get(id=parent_structure_id)
                const = head_manager.get(parent_id=parent_structure_id, id=const_id)
            except:
                return 'Ошибка. Некорректно задан адрес статической ссылки'

            if header.formula != 'alias' or const.formula != 'eval':
               return 'Ошибка. Некорректно задан адрес статической ссылки'
            else:
               return static_formula(const.value, user_id, *link_chain, **params)


# work with history - работаем с историей. Если находит опциональные параметры, говорящие о работе в истории - возвращает значение.
# Если было найдено значение ячейки - возвращает его. Если была ошибка - возвращает текст ошибки.
# Если ошибки не было, но и данных в истории нет - возвращает пустую строку. Тогда алгоритм выполняется далее, будто бы параметра не было
def wwh(k, v, object, is_contract, user_id, opt_params, *link_chain, **params):
    # Зададим все переменные для поиска параметровв
    date_from = opt_params['date_from'] if 'date_from' in opt_params else None
    date_to = opt_params['date_to'] if 'date_to' in opt_params else None
    # Найдем параметры "версия", "версия после", "номер версии"
    if 'version' in opt_params or 'version_after' in opt_params or 'version_number' in opt_params:
        param_name = 'version' if 'version' in opt_params else 'version_after' if 'version_after' in opt_params else 'version_number'
        is_after = param_name == 'version_after'
        order_by_date_update = 'date_update' if is_after else '-date_update'
        version_value = opt_params[param_name]

        # парсинг таймштампа
        if param_name == 'version_number':
            timestamp = None
        else:
            timestamp = convert_procedures.parse_timestamp_for_hist(version_value, is_after)
            if not timestamp:
                return 'Ошибка. Некорректно указано значение параметра version'
        # Попытаемся достать параметр из истории
        name_id = None; formula = None
        if param_name == 'version_number':
            q_date_update = ~Q()
            res_slice = int(version_value)
        else:
            q_date_update = Q(date_update__gt=timestamp) if is_after else Q(date_update__lt=timestamp)
            res_slice = 0

        # Если формула - внешняя ссылка
        if v[0] in ('table', 'contract'):
            location = v[0]
            try:
                class_id = int(v[1])
            except ValueError:
                return 'Ошибка. Формула задана с ошибкой. Укажите корректный ID класса'
            header = Designer.objects if location == 'table' else Contracts.objects
            class_header = header.filter(id=class_id)
            if class_header:
                class_header = class_header[0]
            else:
                return 'Ошибка. Некорректно указан ID класса в формуле ' + k
            # Для полной ссылки
            if len(v) == 4:
                try:
                    name_id = int(v[3])
                except ValueError:
                    return 'Ошибка. Формула задана с ошибкой. Укажите корректный ID выводимого поля'
                name_header = header.filter(id=name_id).values()
                if name_header:
                    name_header = name_header[0]
                else:
                    return 'Ошибка. Ссылка задана некорректно'
                data_type = name_header['formula']
                try:
                    code = int(v[2])
                except ValueError:
                    code = v[2]
                    conds_sum = re.match(r'^f\d+[eqgtln]{2}.+', code)
                    agr_fun = opt_params['agr_fun'] if 'agr_fun' in opt_params else 'sum'
                    agr_funs_types = {'string': ('count', ), 'bool': ('count', ), 'link': ('count', ), 'eval': [],
                                      'float': ('count', 'sum', 'avg', 'max', 'min'), 'enum': ('count', ),
                                      'date': ('count', 'max', 'min'), 'datetime': ('count', 'max', 'min'), 'const': []}
                    if not agr_fun in agr_funs_types[data_type]:
                        return 'Ошибка. Невозможно вычислить агрегатную функцию "' + agr_fun + '" для типа данных "' +\
                        data_type + '"'

                    if param_name == 'version_number':
                        return 'Ошибка. Не имеет смысла суммировать разные версии объектов'

                    base_query = RegistratorLog.objects.filter(json_class=class_id)
                    def get_work_codes():
                        # соберем коды объектов, которые на момент даты версии удалены
                        delete_codes = base_query.filter(reg_name=8, json_income__location=location,
                                                         date_update__lt=timestamp) \
                            .annotate(code=F('json_income__code')).values('code').distinct()
                        delete_codes = [dc['code'] for dc in delete_codes]
                        exist_codes = list(
                            base_query.filter(date_update__lt=timestamp, json__location=location, reg_name__in=(13, 15)) \
                            .annotate(code=F('json__code')).values('code').distinct().exclude(code__in=delete_codes))

                        # для версии после
                        if is_after:
                            future_codes = list(
                                base_query.filter(reg_name=5, json__location=location, date_update__gt=timestamp) \
                                .annotate(code=F('json__code')).values('code'))
                        else:
                            future_codes = []
                        # Если указан бранч или кластер
                        if opt_params['node']:
                            parent_branch = header.get(parent_id=class_id, name='parent_branch')
                            cb_codes = [opt_params['code']]
                            if opt_params['node'] == 'c':
                                cb_codes += tree_funs.get_inheritors(opt_params['code'], class_header.parent_id,
                                                                     is_contract)
                            exist_codes = convert_procedures.ficlubraco(exist_codes, base_query, timestamp, location,
                                                                        parent_branch.id, cb_codes)
                            if future_codes:
                                future_codes = convert_procedures.ficlubraco(future_codes, base_query, timestamp,
                                                                             location,
                                                                             parent_branch.id, cb_codes, True)
                                exist_codes += future_codes
                        return exist_codes

                    if code == 'all':
                        exist_codes = get_work_codes()
                        exist_values = []
                        for ec in exist_codes:
                            exist_values.append(convert_procedures.renepreva(base_query, ec['code'], timestamp,
                            is_after, location, name_id, data_type))
                        return convert_procedures.do_agr_fun(agr_fun, exist_values)

                    # Накопление суммы с условием
                    elif conds_sum:
                        exist_codes = get_work_codes()
                        if not exist_codes:
                            return 0
                        str_date = opt_params['version_after'] if is_after else opt_params['version']
                        is_c = location == 'contract'
                        exist_codes = [ec['code'] for ec in exist_codes]
                        exist_objs, tom = convert_procedures.gvfo(class_id, str_date, is_c, is_after, user_id, exist_codes)
                        array_conds = convert_procedures.gaoc(code)
                        logic_sign = opt_params['logical_sign'] if 'logical_sign' in opt_params else 'and'
                        exist_values = []
                        for eo in exist_objs:
                            if convert_procedures.foblc(eo, tom['headers'], array_conds, logic_sign):
                                if eo[name_id]['value']:
                                    val = eo[name_id]['value']
                                else:
                                    val = 0 if name_header['formula'] == 'float' else ''
                                exist_values.append(val)
                        return convert_procedures.do_agr_fun(agr_fun, exist_values)


                        # старые мэмы
                        # try:
                        #     out_header = model_to_dict(header.get(id=name_id))
                        # except ObjectDoesNotExist:
                        #     return 'Ошибка. Поле name_id задано некорректно'
                        # match_logical_sign = opt_params['logical_sign'] if 'logical_sign' in opt_params else 'and'
                        # #  codes from all iterations
                        # if len(conds_sum) == 1 or match_logical_sign == 'or':
                        #     cfai = []
                        # else:
                        #     cfai = object_manager.filter(parent_structure_id=class_id)
                        #     if opt_params['node'] == 'b':
                        #         cfai = cfai.filter(code__in=source_codes)
                        #     cfai = [o['code'] for o in cfai.values('code').distinct()]
                        # for cs in conds_sum:
                        #     cs = re.match(r'(\d+)([eqgtln]{2})(\d+)', cs)
                        #     search_field = int(cs[1])
                        #     sign = cs[2]
                        #     comp_val = int(cs[3])
                        #     search_field_header = header.filter(id=search_field).values()
                        #     dict_q = {'eq': Q(value=comp_val), 'ne': ~Q(value=comp_val),
                        #               'gt': Q(value__gt=comp_val), 'lt': Q(value__lt=comp_val),
                        #               'ge': Q(value__gte=comp_val), 'le': Q(value__lte=comp_val)}
                        #     if search_field_header:
                        #         search_field_header = search_field_header[0]
                        #     else:   return 'Ошибка. Некорректно задана формула. Не найдено поле для фильтрации ' \
                        #                    'элементов по условию'
                        #     # если условие одно - идем по более быстрому алгоритму вычисления
                        #     if len(conds_sum) == 1:
                        #         if search_field_header['formula'] == 'float':
                        #             hist = RegistratorLog.objects.filter(q_date_update, json__class_id=class_id,
                        #                                                  json__location=location,
                        #                                                  json__name=search_field,
                        #                                                  json__code=OuterRef('code'))\
                        #                 .order_by(order_by_date_update)
                        #             # Получим запрос, собирающий данные, удовлетворяющий условиям
                        #             history_query = object_manager.filter(parent_structure_id=class_id)
                        #             if opt_params['node'] == 'b':
                        #                 history_query = history_query.filter(code__in=source_codes)
                        #             history_query = history_query.values('code')\
                        #                 .distinct().annotate(json=Subquery(hist.values('json')[:1]))
                        #             # Найдем объекты, соответствующие условию
                        #             codes_nodata = []
                        #             sorted_objs = []
                        #             list_vals = []
                        #             for hq in history_query:
                        #                 if hq['json']:
                        #                     if convert_procedures.do_logical_compare(hq['json']['value'], sign,
                        #                                                              comp_val):
                        #                         if search_field == name_id:
                        #                             list_vals.append(hq['json']['value'] if hq['json']['value'] else 0)
                        #                         else:
                        #                             sorted_objs.append(hq['code'])
                        #                 else:
                        #                     codes_nodata.append(hq['code'])
                        #             # проверим выполнение условия у объектов, у которых нет записей в истории
                        #             objects_no_hist = object_manager.filter(parent_structure_id=class_id,
                        #                                                     code__in=codes_nodata,
                        #                                                     name_id=search_field)\
                        #             .annotate(float_val=Cast('value', FloatField())).filter(dict_q[sign])
                        #             if search_field != name_id:
                        #                 sorted_objs.extend([onh.code for onh in objects_no_hist])
                        #             else:
                        #                 list_vals += list(map(lambda o: o.value if type(o.value) in
                        #                                       (float, int) else 0, objects_no_hist))
                        #             # Посчитаем агрегатную функцию параметра name_id
                        #             # * Если search_field = name_id
                        #             if search_field == name_id:
                        #                 agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        #             else:
                        #                 # 1.1. Если name_id - число
                        #                 if out_header['formula'] == 'float':
                        #                     # построим список значений, которые есть в истории
                        #                     hist_vals = RegistratorLog.objects.filter(q_date_update,
                        #                                                               json__class_id=class_id,
                        #                                                               json__location=location,
                        #                                                               json__name=name_id,
                        #                                                               json__code=OuterRef('code'))\
                        #                         .order_by(order_by_date_update)
                        #                     codes_hist = object_manager.filter(parent_structure_id=class_id, name_id=name_id,
                        #                                                        code__in=sorted_objs).values('code')\
                        #                         .annotate(json=Subquery(hist_vals.values('json')[0]))
                        #                     codes_nodata = []
                        #                     for ch in codes_hist:
                        #                         if ch['json']:
                        #                             list_vals.append(ch['json']['value'])
                        #                         else:
                        #                             codes_nodata.append(ch['code'])
                        #                     objs_now = object_manager.filter(parent_structure_id=class_id, name_id=name_id,
                        #                                                     code__in=codes_nodata)
                        #                     list_vals += list(map(lambda o: o.value if type(o.value) in
                        #                                            (float, int) else 0, objs_now))
                        #                     agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        #                 # 1/2 Если name_id - формула
                        #                 elif out_header['formula'] == 'eval':
                        #                     objects = object_manager.filter(parent_structure_id=class_id, code__in=sorted_objs)
                        #                     objects = queryset_to_object(objects)
                        #                     deep_formula(out_header, objects, user_id, is_contract)
                        #                     list_vals = list(map(lambda o: o[name_id]['value']
                        #                                         if type(o[name_id]['value']) in
                        #                                          (float, int) else 0, objects))
                        #                     agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        #                 # Остальные типы данных не суммируем
                        #                 else:
                        #                     agr_val = 'Ошибка. Формула ссылается на недопустимый для суммирования тип данных'
                        #         elif search_field_header['formula'] == 'eval':
                        #             objects = object_manager.filter(parent_structure_id=class_id)
                        #             if opt_params['node'] == 'b':
                        #                 objects = objects.filter(code__in=source_codes)
                        #             objects = queryset_to_object(objects)
                        #             deep_formula(search_field_header, objects, user_id, is_contract)
                        #             sorted_objs = []
                        #             list_vals = []
                        #             for o in objects:
                        #                 if convert_procedures.do_logical_compare(o[search_field]['value'],
                        #                                                          sign, comp_val):
                        #                     if name_id == search_field:
                        #                         list_vals.append(o[search_field]['value'])
                        #                     elif out_header['formula'] == 'float':
                        #                         sorted_objs.append(o['code'])
                        #                     elif out_header['formula'] == 'eval':
                        #                         sorted_objs.append(o)
                        #                     else:   break
                        #             # Если сравниваемое поле и выводимое на экран совпадает
                        #             if name_id == search_field:
                        #                 agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        #             else:
                        #                 # Если возвращаемое значение - число
                        #                 if out_header['formula'] == 'float':
                        #                     hist = RegistratorLog.objects.filter(q_date_update, json__class_id=class_id,
                        #                                                          json__name=name_id,
                        #                                                          json__code=OuterRef('code'),
                        #                                                          json__location=location).order_by(order_by_date_update)
                        #                     obj_codes = object_manager.filter(parent_structure_id=class_id, code__in=sorted_objs)\
                        #                     .values('code').distinct().annotate(json=Subquery(hist.values('json')[:1]))
                        #                     codes_nodata = []
                        #                     for oc in obj_codes:
                        #                         if oc['json']:
                        #                             list_vals.append(oc['json']['value'] if oc['json']['value'] else 0)
                        #                         else:
                        #                             codes_nodata.append(oc['code'])
                        #                     obj_nodata = object_manager.filter(parent_structure_id=class_id,
                        #                                                        name_id=name_id,
                        #                                                        code__in=codes_nodata)
                        #                     list_vals += list(map(lambda o: o.value if type(o.value) in
                        #                                          (float, int) else 0, obj_nodata))
                        #                     agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        #                 # Если возвращаемое значение - формула
                        #                 elif out_header['formula'] == 'eval':
                        #                     deep_formula(out_header, sorted_objs, user_id, is_contract)
                        #                     list_vals = list(map(lambda o: o[name_id]['value'] if o[name_id]['value']
                        #                                     and (type(o[name_id]['value']) is int or
                        #                                          type(o[name_id]['value']) is float) else 0, sorted_objs))
                        #                     agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        #                 else:   agr_val = 'Ошибка. Формула ссылается на недопустимый для суммирования тип данных'
                        #         else:
                        #             agr_val = 'Ошибка. Формула ссылается на недопустимый для суммирования тип данных'
                        #         return agr_val
                        #     # в противном случае не избежать более длинного пути
                        #     else:
                        #         codes = []
                        #         # а. Если сравниваемый параметр - формула: Нет в истории формул. Мы просто проверяем
                        #         if search_field_header['formula'] == 'eval':
                        #             objects = object_manager.filter(parent_structure_id=class_id)
                        #             if opt_params['node'] == 'b':
                        #                 objects = objects.filter(code__in=source_codes)
                        #             if match_logical_sign == 'and':
                        #                 objects = objects.filter(code__in=cfai)
                        #             else:
                        #                 objects = objects.exclude(code__in=cfai)
                        #             objects = queryset_to_object(objects)
                        #             deep_formula(search_field_header, objects, user_id, is_contract)
                        #             for o in objects:
                        #                 if convert_procedures.do_logical_compare(o[search_field]['value'],
                        #                                                          sign, comp_val):
                        #                     codes.append(o['code'])
                        #         # б. сравниваемое поле - число.
                        #         elif search_field_header['formula'] == 'float':
                        #             hist_subq = RegistratorLog.objects.filter(q_date_update,
                        #                                                       json__class_id=class_id,
                        #                                                       json__location=location,
                        #                                                       json__name=search_field,
                        #                                                       json__code=OuterRef('code'))\
                        #                 .order_by(order_by_date_update)
                        #             history_query = object_manager.filter(parent_structure_id=class_id)
                        #             if opt_params['node'] == 'b':
                        #                 history_query = history_query.filter(code__in=source_codes)
                        #             if match_logical_sign == 'and':
                        #                 history_query = history_query.filter(code__in=cfai)
                        #             else:
                        #                 history_query = history_query.exclude(code__in=cfai)
                        #             history_query = history_query.values('code').distinct()\
                        #                 .annotate(json=Subquery(hist_subq.values('json')[:1]))
                        #             codes_nodata = []
                        #             for hq in history_query:
                        #                 if hq['json']:
                        #                     if convert_procedures.do_logical_compare(hq['json']['value'], sign, comp_val):
                        #                         codes.append(hq['code'])
                        #                 else:
                        #                     codes_nodata.append(hq['code'])
                        #             # проверим выполнение условия у объектов, у которых нет записей в истории
                        #             objects_no_hist = object_manager.filter(dict_q[sign],
                        #                                                     parent_structure_id=class_id,
                        #                                                     code__in=codes_nodata,
                        #                                                     name_id=search_field).values('code')
                        #             codes += [o['code'] for o in objects_no_hist]
                        #         # c. Если константа
                        #         elif search_field_header['formula'] == 'const':
                        #             # Найдем алиас
                        #             alias_loc, alias_id = convert_procedures.slice_link_header(search_field_header['value'])
                        #             alias_id = int(alias_id)
                        #             alias_headers = Designer.objects if alias_loc == 'table' else Contracts.objects
                        #             alias_headers = alias_headers.filter(parent_id=alias_id).values()
                        #             dict_consts = {}
                        #             codes = []
                        #             # найдем объекты в истории
                        #             hist_subq = RegistratorLog.objects.filter(q_date_update,
                        #                                                       json__class_id=class_id,
                        #                                                       json__location=location,
                        #                                                       json__name=search_field,
                        #                                                       json__code=OuterRef('code')) \
                        #                 .order_by(order_by_date_update)
                        #             history_query = object_manager.filter(parent_structure_id=class_id)
                        #             if opt_params['node'] == 'b':
                        #                 history_query = history_query.filter(code__in=source_codes)
                        #             if match_logical_sign == 'and':
                        #                 history_query = history_query.filter(code__in=cfai)
                        #             else:
                        #                 history_query = history_query.exclude(code__in=cfai)
                        #             history_query = history_query.values('code').distinct()\
                        #                 .annotate(json=Subquery(hist_subq.values('json')[0]))
                        #             codes_nodata = []
                        #
                        #             for hq in history_query:
                        #                 if hq['json'] and  type(hq['json']['value']) in (float, int):
                        #                     # вычислим выполнение константы
                        #                     if eval_const(user_id, sign, hq['json']['value'], alias_headers,
                        #                                   dict_consts,
                        #                                   comp_val):
                        #                         codes.append(hq['code'])
                        #                     else:   codes_nodata.append(hq['code'])
                        #                 else:
                        #                     codes_nodata.append(hq['code'])
                        #             # вычислим функцию для объектов, не попавших в историю
                        #             objects = object_manager.filter(parent_structure_id=class_id,
                        #                                             name_id=search_field, code__in=codes_nodata)
                        #             for o in objects:
                        #                 if o.value and type(o.value) in (float, int):
                        #                     if eval_const(user_id, sign, o.value, alias_headers, dict_consts,
                        #                                   comp_val):
                        #                         codes.append(o.code)
                        #         else:
                        #             return 'Ошибка. Формула ссылается на недопустимый для вычисления тип данных'
                        #         # Складываем коды
                        #         if match_logical_sign == 'and':
                        #             cfai = codes
                        #         else:
                        #             cfai += codes
                        # # Вычисление агрегатной функции
                        # # а. если накапливаемое поле - формула
                        # if name_header['formula'] == 'eval':
                        #     objects = object_manager.filter(parent_structure_id=class_id, code__in=cfai)
                        #     objects = queryset_to_object(objects)
                        #     deep_formula(name_header, objects, user_id, is_contract)
                        #     list_vals = list(map(lambda x: x[name_id]['value'] if type(x[name_id]['value']) is int or
                        #                          type(x[name_id]['value']) in (float, int) else 0, objects))
                        #     agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        # # б. Если накапливаемое поле - число
                        # elif name_header['formula'] == 'float':
                        #     hist_subq = RegistratorLog.objects.filter(q_date_update, json__class_id=class_id,
                        #                                               json__location=location,
                        #                                               json__name=name_id,
                        #                                               json__code=OuterRef('code')) \
                        #         .order_by(order_by_date_update)
                        #     history_query = object_manager.filter(parent_structure_id=class_id, code__in=cfai)\
                        #         .values('code').distinct().annotate(json=Subquery(hist_subq.values('json')[:1]))
                        #     codes_nodata = []
                        #     list_vals = []
                        #     for hq in history_query:
                        #         if hq['json']:
                        #             list_vals.append(hq['json']['value'])
                        #         else:
                        #             codes_nodata.append(hq['code'])
                        #     objects_no_hist = object_manager.filter(parent_structure_id=class_id,
                        #                                             code__in=codes_nodata, name_id=name_id).values('value')
                        #     list_vals += list(map(lambda o: o['value'] if o['value'] and type(o['value']) in (float, int)
                        #                           else 0, objects_no_hist))
                        #     agr_val = convert_procedures.do_agr_fun(agr_fun, list_vals)
                        # else:
                        #     return 'Ошибка. Суммировать можно только поля типов FLOAT или EVAL'
                        # return agr_val
            # для массива данных или константы
            elif len(v) == 3:
                try:
                    const_id = int(v[2])
                except ValueError:
                    return ''  # вычислим массив объектов в функции foreign_link

                    # Комментим и пишем новый код
                    # # Для массива данных
                    # def filter_data():
                    #     if v[2] == 'all':
                    #         return objs
                    #     else:
                    #         log_sign = 'or' if 'logical_sign' in opt_params and opt_params['logical_sign'] == 'or' else 'and'
                    #         return convert_procedures.fobc(objs, v[2], log_sign)
                    #
                    # # Поправка времени на секунду с учетом предыдущей поправки в пройедуре parse_timestamp_for_hist
                    # timedelta = da_ti.timedelta(seconds=1)
                    # timestamp = timestamp + timedelta if is_after else timestamp - timedelta
                    # # Общие данные
                    # header_manager = Contracts.objects if is_contract else Designer.objects
                    # objs = []
                    # object_manager = ContractCells.objects if is_contract else Objects.objects
                    # objects = object_manager.filter(parent_structure_id=class_id)
                    # # ветка
                    # if opt_params['node'] == 'b':
                    #     objects = objects.filter(name__name='parent_branch', value=opt_params['code'])
                    # # кластер
                    # elif opt_params['node'] == 'c':
                    #     parent_codes = tree_funs.get_inheritors(opt_params['code'], class_header.parent_id, is_contract)
                    #     parent_codes.append(opt_params['code'])
                    #     objects = objects.filter(name__name='parent_branch', value__in=parent_codes)
                    # source_codes = [o['code'] for o in objects.values('code').distinct()]
                    #
                    # # для номера версий
                    # if param_name == 'version_number':
                    #     for sc in source_codes:
                    #         # Получим Id последней транзакции
                    #         ids = RegistratorLog.objects.filter(transact_id=OuterRef('transact_id'))
                    #         transacts = list(RegistratorLog.objects.filter(json__class_id=class_id,
                    #                                                        json__location=v[0],
                    #                                                         json__code=sc)\
                    #             .values('transact_id').distinct().annotate(id=Subquery(ids.values('id')[:1])))
                    #         transacts.reverse()
                    #         num = res_slice
                    #         if num < 0:  num = 0
                    #         elif num >= len(transacts):   num = len(transacts) - 1
                    #         actual_transact = transacts[num]
                    #         # собирем версию объекта
                    #         history = RegistratorLog.objects.filter(json__class_id=class_id, json__location=v[0],
                    #                                                 json__code=sc, json__name=OuterRef('id'),
                    #                                                 transact_id=actual_transact['transact_id'])
                    #         headers = header_manager.filter(parent_id=class_id).exclude(formula='eval')\
                    #         .values().annotate(json=Subquery(history.values('json')[:1]))\
                    #         .annotate(hist_id=Subquery(history.values('id')[:1]))
                    #         obj = {'code': sc, 'parent_structure': class_id}
                    #         empty_headers = []
                    #         for h in headers:
                    #             obj[h['id']] = {'id': h['id'], 'name': h['name'], 'type': h['formula']}
                    #             if h['json']:
                    #                 obj[h['id']]['value'] = h['json']['value']
                    #             else:
                    #                 empty_headers.append(h['id'])
                    #                 obj[h['id']]['value'] = None
                    #         # Заполним пустые заголовки
                    #         hist_param = RegistratorLog.objects\
                    #             .filter(json__class_id=class_id, json__code=sc, json__location=v[0],
                    #                     json__name__in=OuterRef('id'), id__lt=actual_transact['id']).order_by('-id')
                    #         em_heads = header_manager.filter(parent_id=class_id, id__in=empty_headers).values('id')\
                    #         .annotate(json=hist_param.values('json')[:1])
                    #         for eh in em_heads:
                    #             obj[eh['id']]['value'] = eh['json']['value'] if eh['json'] else None
                    #         objs.append(obj)
                    #     return filter_data()  # фильтруем данные
                    # # для параметров version  version_after
                    # else:
                    #     value_field = 'json' if is_after else 'json_income'
                    #     other_field = 'json_income' if is_after else 'json'
                    #     q_class_id = Q(Q(json__class_id=class_id) | Q(json_income__class_id=class_id))
                    #     q_loc = Q(Q(json__location=v[0]) | Q(json_income__location=v[0]))
                    #     q_nam = Q(Q(json__name=OuterRef('id')) | Q(json_income__name=OuterRef('id')))
                    #     for sc in source_codes:
                    #         q_cod = Q(Q(json__code=sc) | Q(json_income__code=sc))
                    #         history = RegistratorLog.objects.filter(q_class_id, q_loc, q_cod, q_nam,
                    #                                                 date_update__gte=timestamp).order_by('date_update')
                    #         headers = header_manager.filter(parent_id=class_id).exclude(formula='eval')\
                    #             .values().annotate(json=Subquery(history.values('json')[:1]))\
                    #         .annotate(json_income=Subquery(history.values('json_income')[:1]))
                    #         obj = {'code': sc, 'parent_structure': class_id}
                    #         obj_today = object_manager.filter(parent_structure_id=class_id, code=sc)
                    #         for h in headers:
                    #             obj[h['id']] = {'id': h['id'], 'name': h['name'], 'type': h['formula']}
                    #             # Если есть значение в необходимом поле
                    #             if h[value_field]:
                    #                 obj[h['id']]['value'] = h[value_field]['value']
                    #             # Если нет значения в нужном поле - не берем ничего
                    #             elif not h[value_field] and h[other_field]:
                    #                 obj[h['id']]['value'] = None
                    #             # Если нет обоих полей - берем современное значение
                    #             else:
                    #                 try:
                    #                     ot = next(ot.value for ot in obj_today if ot.name_id == h['id'])
                    #                     obj[h['id']] = {'id': h['id'], 'name': h['name'], 'type': h['formula'],
                    #                                 'value': ot}
                    #                 except StopIteration:
                    #                     obj[h['id']] = {'id': h['id'], 'name': h['name'], 'type': h['formula'],
                    #                                     'value': None}
                    #         objs.append(obj)
                    #     return filter_data()  # фильтруем данные

                # для константы
                history = RegistratorLog.objects.filter(q_date_update, json__class_id=v[1], json__location=v[0],
                                                        json__id=v[2]).order_by(order_by_date_update)
                if history:
                    res_slice = len(history) - 1 if res_slice >= len(history) else res_slice
                    result = static_formula(history[res_slice].json['value'], user_id, *link_chain, **params)
                    return result
                else:   return ''
            # для короткой внешней ссылки
            elif len(v) == 2:
                location = v[0]
                obj = Objects.objects if location == 'table' else ContractCells.objects
                try:
                    obj = obj.get(id=v[1])
                except ObjectDoesNotExist:
                    return 'Ошибка. Ссылка задана некорректна'
                class_id = obj.parent_structure_id
                code = obj.code
                name_id = obj.name_id
                header = Designer.objects if location == 'table' else Contracts.objects
                try:
                    formula = header.get(id=name_id).formula
                except ObjectDoesNotExist:
                    return 'Ошибка. Ссылка задана некорректна'
            else:   return 'Ошибка. Формула задана некорректно'
        # Если связный элемент или внутренняя ссылка
        else:
            class_id = object['parent_structure']
            code = object['code']
            location = 'contract' if is_contract else 'table'
            name_id = None
            for i in v:
                link_header = Designer.objects if location == 'table' else Contracts.objects
                try:
                    link_header = link_header.get(id=i)
                except ObjectDoesNotExist:
                    return 'Ошибка. Некорректно задан параметр формулы ' + k
                if link_header.parent_id != class_id:
                    return 'Ошибка. Некорректно задан параметр формулы ' + k
                if i == v[len(v) - 1]:
                    name_id = int(i)
                    formula = link_header.formula
                else:
                    if link_header.formula != 'link':
                        return 'Ошибка. Некорректно задан параметр формулы ' + k
                    deep_object = Objects.objects if location == 'table' else ContractCells.objects
                    try:
                        deep_object = deep_object.get(code=code, parent_structure_id=class_id, name_id=i)
                    except ObjectDoesNotExist:
                        return 'Ошибка. Некорректно задан параметр формулы ' + k
                    code = deep_object.value
                    location, class_id = convert_procedures.slice_link_header(link_header.value)
        history = RegistratorLog.objects.filter(q_date_update, json__class_id=class_id, json__code=code,
                                                json__name=name_id, json__location=location).order_by(order_by_date_update)
        if history:
            if res_slice >= len(history):
                res_slice = len(history) - 1
            result = history[res_slice].json['value']
            if formula == 'file':
                result = files_procedures.get_file_path(result, str(class_id), location=location)
            elif formula == 'const':
                link_header = Designer.objects if location == 'table' else Contracts.objects
                link_header = link_header.get(id=result)
                result = static_formula(link_header.value, user_id, *link_chain, **params)
            return result
        else:
            return ''

    # Найдем параметры "дата от" и "дата до"
    elif date_to or date_from:
        # проверка корректности параметров
        if not date_from:
            date_from = da_ti.datetime(1970, 1, 1)
        if not date_to:
            date_to = da_ti.datetime.now()
        # Базовые переменные
        name_id = None
        # 1. Внешняя ссылка
        if v[0] in ('table', 'contract'):
            # 1.1. Полная ссылка
            if len(v) == 4:
                location = v[0]
                try:
                    class_id = int(v[1])
                except ValueError:
                    return 'Ошибка. Некорректно задан параметр формулы. ID класса может быть только числом'
                try:
                    code = int(v[2])
                except ValueError:
                    return 'Ошибка. формула с параметрами date_from, date_to возможна только для одного объекта. ' \
                           'Укажите код объекта числом'
                try:
                    name_id = int(v[3])
                except ValueError:
                    return 'Ошибка. Некорректно задан параметр формулы. ID реквизита объекта может быть задан ' \
                           'только целым числом'
            # 1.2. Константа или массив данных
            elif len(v) == 3:
                try:
                    int(v[2])
                except ValueError:
                    # Если вычисляем массив объектов в историческом интервале - то выполним это в процедуре foreign_link
                    return ''
                else:
                    return 'Ошибка. Невозможно обработать формулу константы с параметрами date_from / date_to'
            # 1.2. Короткая ссылка
            elif len(v) == 2:
                try:
                    id = int(v[1])
                except ValueError:
                    return 'Ошибка. Некорректно задан параметр. ID ячейки объекта можно задать только целым числом'
                cell = Objects.objects if v[0] == 'table' else ContractCells.objects
                try:
                    cell = cell.get(id=id)
                except ObjectDoesNotExist:
                    return 'Ошибка. Указанного ID ячейки не существует'
                class_id = cell.parent_structure_id
                code = cell.code
                name_id = cell.name_id
                location = v[0]
            else:
                return 'Ошибка. Некорректно задан параметр ' + k
        # 2. Внутренняя ссылка
        else:
            location = 'contract' if is_contract else 'table'
            class_id = object['parent_structure']
            code = object['code']
            for i in v:
                try:
                    int_i = int(i)
                except ValueError:
                    return 'Ошибка. Формула некорректна. Во внутренних ссылках все элементы являются числами'
                link_header = Designer.objects if location == 'table' else Contracts.objects
                try:
                    link_header = link_header.get(id=int_i)
                except ObjectDoesNotExist:
                    return 'Ошибка. Некорректно задан параметр формулы ' + k
                if link_header.parent_id != class_id:
                    return 'Ошибка. Некорректно задан параметр формулы ' + k
                if v.index(i) == len(v) - 1:
                    name_id = int_i
                else:
                    if link_header.formula != 'link':
                        return 'Ошибка. Некорректно задан параметр формулы ' + k
                    deep_object = Objects.objects if location == 'table' else ContractCells.objects
                    try:
                        deep_object = deep_object.get(code=code, parent_structure_id=class_id, name_id=int_i)
                    except ObjectDoesNotExist:
                        return 'Ошибка. Некорректно задан параметр формулы ' + k
                    code = deep_object.value
                    location, class_id = convert_procedures.slice_link_header(link_header.value)
                    class_id = int(class_id)
        # Посчитаем сумму записей из фрагмента истории
        hist = RegistratorLog.objects.filter(date_update__gte=date_from, date_update__lte=date_to,
                                             json__class_id=class_id, json__location=location,
                                             json__code=code, json__name=name_id)
        if hist:
            hist = hist.annotate(float_val=Cast(KeyTextTransform('value', 'json'), FloatField()))
            agr_fun = opt_params['agr_fun'] if 'agr_fun' in opt_params else 'sum'
            agr_val = convert_procedures.do_agr_query(agr_fun, hist, 'float_val')
        else:   agr_val = 0
        return agr_val
    else:   return ''


# Подготовка к суммированию по условию. На вход - формула. На выход: Да/нет, список кодов объекта / текст ошибки
# опциональные параметры: список кодов - коды, ограничивающие поиск.
# Если Node Да, значит ограничиваем массив списком исходных кодов
def condition_sum_prepare(formula_array, user_id, logical_sign='and', *sourse_codes):
    header_manager = Designer.objects if formula_array[0] == 'table' else Contracts.objects
    object_manager = Objects.objects if formula_array[0] == 'table' else ContractCells.objects
    if sourse_codes:
        object_manager = object_manager.filter(code__in=sourse_codes)
    class_id = int(formula_array[1])
    conditions = formula_array[2][1:]
    find_conds = re.findall(r'(\d+[eqgtln]{2}\d+)', conditions)
    codes = []
    if find_conds:
        for i in range(len(find_conds)):
            match = re.match(r'(\d+)([eqgtln]{2})(\d+)', find_conds[i])
            comp_field = int(match[1])  # Получим сравниваемое поле
            sign = match[2]  # Знак
            comp_val = int(match[3])  # сравниваемое значение
            comp_field_header = header_manager.filter(id=comp_field).values()
            if comp_field_header:
                comp_field_header = comp_field_header[0]
            else:
                return False, 'Ошибка. Не найдено сравниваемое поле для условия отбора. ID: ' + match[1]
            codes_one_cond = []
            dict_cond = {'eq': Q(float_val=comp_val), 'ne': ~Q(float_val=comp_val), 'gt': Q(float_val__gt=comp_val),
                         'lt': Q(float_val__lt=comp_val), 'ge': Q(float_val__gte=comp_val), 'le': Q(float_val__lte=comp_val)}
            if comp_field_header['formula'] in ('float', 'link'):
                q_cond = dict_cond[sign]
                codes_one_cond = object_manager.filter(parent_structure_id=class_id, name_id=comp_field)\
                .annotate(float_val=Cast('value', FloatField())).filter(q_cond).values('code')
                if codes:
                    if logical_sign == 'and':
                        codes_one_cond = codes_one_cond.filter(code__in=codes)
                    else:
                        codes_one_cond = codes_one_cond.exclude(code__in=codes)
                codes_one_cond = [coc['code'] for coc in codes_one_cond]
            elif comp_field_header['formula'] == 'eval':
                objects = object_manager.filter(parent_structure_id=class_id)
                if logical_sign == 'and' and codes:
                    objects = objects.filter(code__in=codes)
                elif logical_sign == 'or':
                    objects = objects.exclude(code__in=codes)
                objects = queryset_to_object(objects)
                is_contract = True if formula_array[0] == 'contract' else False
                deep_formula(comp_field_header, objects, user_id, is_contract)
                for o in objects:
                    if convert_procedures.do_logical_compare(o[comp_field]['value'], sign, comp_val):
                        codes_one_cond.append(o['code'])
            elif comp_field_header['formula'] == 'const':
                alias_loc, alias_id = convert_procedures.slice_link_header(comp_field_header['value'])
                alias_id = int(alias_id)
                alias_headers = Designer.objects if alias_loc == 'table' else Contracts.objects
                alias_headers = alias_headers.filter(parent_id=alias_id).values()
                dict_consts = {}
                objects = object_manager.filter(parent_structure_id=class_id, name_id=comp_field)
                for o in objects:
                    if o.value and type(o.value) in (float, int):
                        if eval_const(user_id, sign, o.value, alias_headers, dict_consts, comp_val):
                            codes_one_cond.append(o.code)
            else:
                return False, 'Ошибка. Сравниваемое поле может быть только в формате float, eval или const'
            if logical_sign == 'and':
                codes = codes_one_cond
            else:
                codes += codes_one_cond
        return True, codes
    else:   return False, 'Ошибка. Некорректно задано условие'


# вычисление константы и сравнение результата с условием
def eval_const(user_id, sign, val, alias_headers, dict_consts, comp_val):
    try:
        const_header = next(ah for ah in alias_headers if ah['id'] == val)
    except StopIteration:
        return None
    if const_header['id'] not in dict_consts.keys():
        res = static_formula(const_header['value'], user_id)
        dict_consts[const_header['id']] = res
    else:
        res = dict_consts[const_header['id']]
    return convert_procedures.do_logical_compare(res, sign, comp_val)


def get_opt_params(formula):
    result = {}
    # Найдем логический знак
    match_logical_sign = re.search(r'\{\{.*logical_sign\s*=\s*\\?([andANDorOR]{2,3})\\?.*\}\}', formula, re.S)
    if match_logical_sign:
        result['logical_sign'] = match_logical_sign[1].lower()
        if result['logical_sign'] not in ('and', 'or'):
            del result['logical_sign']

    # Найдем агрегатную функцию
    find_agr_fun = re.search(r'\{\{.*agr_fun\s*=\s*([acginmostuvx]{3,5}).*\}\}', formula, flags=re.IGNORECASE | re.S)
    if find_agr_fun:
        if find_agr_fun[1].lower() in ('sum', 'avg', 'min', 'max', 'count'):
            result['agr_fun'] = find_agr_fun[1].lower()

    # Для формулы, возвращающей массив данных, позволим вернуть только требуемые поля
    find_fields = re.search(r'\{\{.*fields\s*=\s*([\d\,\s]+).*\}\}', formula, re.S)
    if find_fields:
        all_fields = re.findall(r'\d+', find_fields[1])
        result['fields'] = [int(af) for af in all_fields]
    # Найдем узловой параметр: node =  [c, b, None] - [cluster, branch, None]
    # Найдем кластер - ветка + все дети
    find_cluster = re.search(r'\{\{.*cluster.*\}\}', formula, flags=re.IGNORECASE | re.S)
    if find_cluster:
        result['node'] = 'c'
    else:
        # Найдем ветку
        find_branch = re.search(r'\{\{.*branch.*\}\}', formula, flags=re.IGNORECASE | re.S)
        if find_branch:
            result['node'] = 'b'
        else:
            result['node'] = None

    # Параметр - Order - Успорядочивание
    find_order = re.search(r'\{\{.*order\s*=\s*\[([\d,\s+\-]+)\].*\}\}', formula, re.S)
    if find_order:
        order_headers = re.findall(r'\d+(?:\+|\-|)', find_order[1])
        result['order'] = []
        for oh in order_headers:
            rev = False
            if oh[len(oh) - 1] == '-':
                rev = True
                oh = (int(oh[:len(oh) - 1]))
            elif oh[len(oh) - 1] == '+':
                oh = (int(oh[:len(oh) - 1]))
            else:
                oh = int(oh)
            result['order'].append((oh, rev))
    # Параметр LIFO
    if re.search(r'\{\{.*lifo.*\}\}', formula, re.S):
        result['lifo'] = True
    # Даты от и до
    fnd_dt_from = re.search(r'\{\{.*date_from\s*=\s*(?:\'|\")([\d\s.\-T:]{10,19})(?:\'|\")', formula)
    fnd_dt_to = re.search(r'\{\{.*date_to\s*=\s*(?:\'|\")([\d\s.\-T:]{10,19})(?:\'|\")', formula)
    if fnd_dt_from:
        date_from = convert_procedures.parse_timestamp_for_hist(fnd_dt_from[1], True)
        if not date_from:
            return 'Ошибка. Некорректно задан атрибут "date_from"<br>'
        else:
            result['date_from'] = date_from
    if fnd_dt_to:
        date_to = convert_procedures.parse_timestamp_for_hist(fnd_dt_to[1])
        if not date_to:
            return 'Ошибка. Некорректно задан атрибут "date_to"<br>'
        else:
            result['date_from'] = date_to

    # версия, версия после и версия номер
    match_version = re.search(r'\{\{.*(version|version_after)\s*=\s*(?:\'|\")([\d\-.\sT:]{10,19})(?:\'|\")', formula, flags=re.S | re.IGNORECASE)
    if match_version:
        result[match_version[1]] = match_version[2]
    else:
        match_version_number = re.search(r'\{\{.*version_number\s*=\s*(\d+)', formula)
        if match_version_number:
            result['version_number'] = int(match_version_number[1])
    return result


def add_param_to_object(header, object, var, user_id, is_contract, is_draft=False, *link_chain):
    if var in object:
        del object[var]
    if header['formula'] == 'eval':
        deep_objects = [object, ]
        deep_formula(header, deep_objects, user_id, is_contract, *link_chain, is_draft=is_draft)
        return 'ok'
    elif header['formula'] in ('float', 'bool', 'date', 'datetime', 'const', 'enum', 'string',
                                    'file', 'link'):
        object_manager = ContractCells.objects if is_contract else Objects.objects
        cell = object_manager.filter(parent_structure_id=object['parent_structure'], code=object['code'], name_id=var)
        cell_value = cell[0].value if cell else None
        cell_delay = cell[0].delay if cell else []
        object[var] = {'value': cell_value, 'delay': cell_delay}
        return 'ok'
    else:
        return 'Ошибка. Возможно имеется ошибка в базе данных'



