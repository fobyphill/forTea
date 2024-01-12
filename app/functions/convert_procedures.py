import re, datetime


# процедура нахождения маркера юзера
from operator import itemgetter, or_, and_

from django.db.models import Sum, Avg, Max, Min

from app.functions import tree_funs
from app.models import Contracts, ContractCells, Objects, Designer


def find_user(formula, user_id):
    return re.findall(r'\[\[(user_id)\]\]', user_id, formula)


# Процедура разбивания ссылки на две части. на вход - ссылка их заголовка. На выходе тип класса и айди класса-родителя
def slice_link_header(link):
    try:
        array = re.search(r'^(?P<type>\w+)\.(?P<id>\d+)$', link)
        class_type = array.group('type')
        parent_id = array.group('id')
        return class_type, parent_id
    except AttributeError:
        return None, None


# вернуть теги. Вход - строка. Выход  - список словарей, ключи которых - это формулы, а значения - списки строк
def retreive_tags(formula):
    if not formula: formula = ''
    json_parts = []
    formuls = re.findall(r'\[\[(?:(?!\[\[).)*?\]\]', formula, re.I)
    for f in formuls:
        f = f[2:len(f) - 2]
        # Найдем тип данных - state, fact, delay
        value_kind = re.search(r'\d+\.(state|fact|delay)', f, re.S)
        if value_kind:
            k = re.sub(r'\.' + value_kind[1], '', f, re.S)
        else:
            k = f
        parts = []
        # Если есть опциональные параметры, вырежем их из массива значений
        k = re.sub(r'\{\{.*?\}\}', '', k, re.S)
        # найдем внешнюю ссылку
        match = re.match(r'^\s*(table|contract)', k)
        # найдем стадию техпроцесса
        match_stage = re.match(r'^\s*tp\.(\d+)\.\'(.+)\'(?:\.(fact|delay|state)|)\s*$', k)

        if match:
            sub = re.sub(r'(table|contract)', '', k, re.S)
            # Найдем внешнюю ссылку из чисел  contract.33.44.55
            if re.match(r'\s*(?:\.\d+)+\s*$', sub, re.S):
                parts = re.findall(r'\.(\d+)', sub, re.S)
            # Внешняя ссылка с all
            if not parts:
                match_all = re.search(r'\.(\d+)\.all', sub)
                if match_all:
                    parts = [match_all[1], 'all']
                    sub = re.sub(r'\.\d+\.all', '', sub)
                    match_last = re.search(r'\.(\d+)', sub)
                    if match_last:
                        parts.append(match_last[1])
            # внешняя ссылка с фильтрами
            if not parts:
                re_pattern = '\s*\.(\d+)\.(f(?:\d+[eqnltg]{2}(?:\d+|(?:\'.*\')|(?:\".*\"))){1}(?:\;\d+[eqnltg]{2}(?:\d+|(?:\'.*\')|(?:\".*\")))*)'
                match_filter = re.match(re_pattern, sub, re.S)
                if match_filter:
                    parts = [match_filter[1], match_filter[2]]
                    sub = re.sub(re_pattern, '', sub)
                    match_last = re.match(r'\s*\.(\d+)', sub)
                    if match_last:
                        parts.append(match_last[1])
            if parts:
                parts.insert(0, match[1])
        elif match_stage:
            for i in range(1, len(match_stage.groups()) + 1):
                parts.append(match_stage[i])
        else:
            # найдем элемент / внутреннюю ссылку
            parts = re.findall(r'(\d+)(?:\.|)', k, re.S)
            # Если не нашелся массив данных - то все содержимое бросаем в первый элемент parts
            if not parts:
                parts.append(f)
        if value_kind:
            parts.append(value_kind[1])
        else:
            parts.append('state')
        json_parts.append({f: parts})
    return json_parts


# парсит датувремя строку в разных форматах
def parse_timestamp(str_datetime):
    date_formats = ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y')
    for df in date_formats:
        try:
            timestamp = datetime.datetime.strptime(str_datetime, df)
        except ValueError:
            continue
        else:
            return timestamp
    else:
        return False

# распознает строковую датувремя. В зависимости от направления движения по времени прибавляет или отнимает одну секунду
# Возвращает таймштамп в формате дата-время или ложь
def parse_timestamp_for_hist(str_datetime, is_after=False):
    timestamp = parse_timestamp(str_datetime)
    if not timestamp:
        return False
    timedelta = datetime.timedelta(seconds=1)
    timestamp = timestamp - timedelta if is_after else timestamp + timedelta
    return timestamp


def do_logical_compare(left_val, sign, right_val):
    if not type(left_val) in (float, int) or not type(right_val) in (float, int):
        return False
    if (left_val == right_val and sign == 'eq') or \
       (left_val != right_val and sign == 'ne') or \
       (left_val > right_val and sign == 'gt') or \
       (left_val < right_val and sign == 'lt') or \
        (left_val >= right_val and sign == 'ge') or \
        (left_val <= right_val and sign == 'le'):
            return True
    else:   return False


def do_agr_fun(fun, list_vals):
    agr_fun = 0
    if list_vals:
        if fun == 'max':
            agr_fun = max(list_vals)
        elif fun == 'min':
            agr_fun = min(list_vals)
        elif fun == 'sum':
            agr_fun = sum(list_vals)
        elif fun == 'avg':
            agr_fun = sum(list_vals) / len(list_vals)
        elif fun == 'count':
            agr_fun = len(list_vals)
        else:
            agr_fun = 'Ошибка. Агрегатная функция не определена'
    return agr_fun


def do_agr_query(fun, queryset):
    if fun == 'sum':
        agr_val = queryset.aggregate(sum=Sum('float_val'))['sum']
    elif fun == 'avg':
        agr_val = queryset.aggregate(avg=Avg('float_val'))['avg']
    elif fun == 'max':
        agr_val = queryset.aggregate(fun=Max('float_val'))['fun']
    elif fun == 'min':
        agr_val = queryset.aggregate(fun=Min('float_val'))['fun']
    elif fun == 'count':
        agr_val = queryset.count()
    else:
        agr_val = 'Ошибка. Агрегатная функция не определена'
    return agr_val


# cstdt - convert string to data type
def cstdt(str_var, type):
    if str_var:
        if type == 'float':
            val = float(str_var)
        elif type in ('link', 'const'):
            try:
                val = int(str_var) if str_var else 0
            except ValueError:
            # У словарей в дефолте лежат все данные ссылки. Поэтому если число не распарсилось - забираем второе число из формулы ссылки
                val = re.match(r'(?:table|contract)\.\d+\.(\d*)', str_var)[1]
        elif type == 'bool':
            val = True if str_var == 'True' else False
        else:
            val = str_var
    else:
        val = None
    return val


# Упорядочить объекты по заданному набору заголовков
# sobah - sort objects by array headers
# objs - объекты в формате json, где ключи объектов являются ID заголовков класса
# header - список кортежей (id, is_reverse) - (Айди, направление сортировки)
def sobah(objs, array_headers):
    # проверка ключей
    if objs:
        obj_keys = objs[0].keys()
        array_headers = [ah for ah in array_headers if ah[0] in obj_keys]
        for k, r in reversed(array_headers):
            objs.sort(key=lambda x: x[k]['value'], reverse=r)
    return objs

# gc1b - get codes one branch
def gc1b(class_header, code, node, is_contract,):
    manager = ContractCells.objects if is_contract else Objects.objects
    source_codes = []
    parent_codes = []
    if node == 'c':
        parent_codes.append(code)
        parent_codes += tree_funs.get_inheritors(code, class_header.parent_id, is_contract)
    elif node == 'b':
        parent_codes.append(code)
    if parent_codes:
        source_codes = [c['code'] for c in manager.filter(parent_structure_id=class_header.id, name__name='parent_branch',
                               value__in=parent_codes).values('code').distinct()]
    return source_codes

# fobc = filter objects by conds
def fobc(objs, conds, logical_sign):
    filtred_objs = []
    find_conds = re.findall(r'(\d+[eqgtln]{2}\d+)', conds)
    array_conds = []
    logical_sign = or_ if logical_sign == 'or' else and_
    for fc in find_conds:
        exer = re.match(r'^(\d+)([eqgtln]{2})(\d+)', fc, re.S)
        field = int(exer[1])
        sign = exer[2]
        val = int(exer[3])
        array_conds.append({'field': field, 'sign': sign, 'val': val})
    for o in objs:
        logical_results = []
        for ac in array_conds:
            comp_field = o[ac['field']]['value']
            res = do_logical_compare(comp_field, ac['sign'], ac['val'])
            logical_results.append(res)
        log_res = logical_results[0]
        for i in range(1, len(logical_results)):
            log_res = logical_sign(log_res, logical_results[i])
        if log_res:
            filtred_objs.append(o)
    return filtred_objs

# Защитить символы для дальнейшего использования в регулярке
# scfre = screen chars for reg exp
def scfre(str):
    screened_str = ''
    for ch in str:
        if ch in '|[]+-':
            screened_str += '\\'
        screened_str += ch
    return screened_str


# Добавить в заголовок детей при условии, что заголовок типа CONST
# ficoitch = fill const its children
def ficoitch(h):
    if h['formula'] == 'const':
        if h['value'][0] == 'c':
            val = int(h['value'][9:])
            const_manager = Contracts.objects
        else:
            val = int(h['value'][6:])
            const_manager = Designer.objects
        h['const'] = list(const_manager.filter(parent_id=val).values('id', 'name', 'value'))