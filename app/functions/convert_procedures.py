import re, datetime


# процедура нахождения маркера юзера
from operator import itemgetter, or_, and_

from django.db.models import Sum, Avg, Max, Min, FloatField, Q, F
from django.db.models.functions import Cast

from app.functions import tree_funs, object_funs, hist_funs, convert_funs2, session_procedures
from app.functions.convert_funs import queryset_to_object
from app.models import Contracts, ContractCells, Objects, Designer, RegistratorLog


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
    formuls = re.findall(r'\[\[(?:(?!\[\[)(?:.|\n))*?\]\]', formula, flags=re.I)
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
        match = re.match(r'^\s*(table|contract|tp)', k)

        if match:
            sub = re.sub(r'(table|contract|tp)', '', k, re.S)
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
                re_pattern = r'\s*\.(\d+)\.(f(?:\d+[eqnltgk]{2}(?:\d+\+null|\d+|true|false|null|(?:\'.*?\'(?:\+null|))|' \
                             r'(?:\".*?\"(?:\+null|)))){1}' \
                             r'(?:\;\d+[eqnltgk]{2}(?:\d+\+null|\d+|true|false|null|(?:\'.*?\'(?:\+null|))|(?:\".*?\"(?:\+null|))))*)'
                match_filter = re.match(re_pattern, sub, flags=re.S | re.IGNORECASE)
                if match_filter:
                    parts = [match_filter[1], match_filter[2]]
                    sub = re.sub(re_pattern, '', sub, flags=re.IGNORECASE)
                    match_last = re.match(r'\s*\.(\d+)', sub)
                    if match_last:
                        parts.append(match_last[1])
            if parts:
                parts.insert(0, match[1])
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
    date_formats = ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                    '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M', '%d.%m.%Y')
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
    if not is_after:
        timestamp += datetime.timedelta(seconds=1)
    return timestamp


def do_logical_compare(left_val, sign, right_val):
    type_lv = type(left_val)
    type_rw = type(right_val)
    if not type_lv in (float, int, str, bool) or not type_rw in (float, int, str, bool):
        return False
    numbers = (float, int)
    if type_lv in numbers or type_rw in numbers:
        if type_rw in numbers and not type_lv in numbers or type_lv in numbers and type_rw not in numbers:
            return False
    elif type_lv != type_rw:
        return False
    if type_lv is str and sign == 'lk':
        if left_val.lower().find(right_val.lower()) != -1:
            return True
        else:
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


def do_agr_query(fun, queryset, field_name):
    if fun == 'sum':
        agr_val = queryset.aggregate(sum=Sum(field_name))['sum']
    elif fun == 'avg':
        agr_val = queryset.aggregate(avg=Avg(field_name))['avg']
    elif fun == 'max':
        agr_val = queryset.aggregate(fun=Max(field_name))['fun']
    elif fun == 'min':
        agr_val = queryset.aggregate(fun=Min(field_name))['fun']
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
            val = str_var.lower() == 'true'
        else:
            val = str_var
    else:
        val = None
    return val


# cdtts = convert data type to string
def cdtts(var, type):
    if var:
        if type == 'date':
            val = var[8:] + '.' + var[6:8] + '.' + var[:4]
        elif type == 'datetime':
            val = var[8:10] + '.' + var[6:8] + '.' + var[:4] + ' ' + var[11:]
        elif type == 'file':
            val = var[14:]
        elif type == 'string':
            val = var
        else:
            val = str(var)
    else:
        val = ''
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
            if type(objs[0][k]['value']) is dict:
                objs.sort(key=lambda x: x[k]['value']['datetime_create'])
            else:
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

# gaoc = get array of conds
def gaoc(str_conds):
    conds = re.findall(r'\d+[eqnltgk]{2}.+?(?:;|$)', str_conds, flags=re.IGNORECASE | re.S)
    array_conds = []
    for c in conds:
        match = re.match(r'(\d+)([eqnltgk]{2})(.+?)(?:;|$)', c)
        array_conds.append({'header_id': int(match[1]), 'sign': match[2], 'cmp_val': match[3]})
    return array_conds

# foblc = filter object by logical conds
def foblc(obj, headers, array_conds, logical_sign):
    result = False
    for ac in array_conds:
        try:
            header = next(h for h in headers if h['id'] == ac['header_id'])
        except StopIteration:
            return False
        if not header['id'] in obj:
            left_val = None
        else:
            left_val = obj[header['id']]['value']
        cmp_val = ac['cmp_val']
        is_done = False
        if cmp_val[-5:].lower() == '+null':
            if not left_val:
                result = True
                is_done = True
            else:
                cmp_val = cmp_val[:len(cmp_val) - 5]
        if not is_done:
            if header['formula'] in ('float', 'link'):
                right_val = float(cmp_val)
            elif header['formula'] == 'bool':
                right_val = cmp_val.lower() == 'true'
            else:
                right_val = cmp_val[1:len(cmp_val) - 1]
            result = do_logical_compare(left_val, ac['sign'], right_val)
        if result:
            if logical_sign == 'or':
                break
        elif logical_sign == 'and':
            break
    return result


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
    if h['formula'] == 'const' and not 'const' in h:
        if h['value'][0] == 'c':
            val = int(h['value'][9:])
            const_manager = Contracts.objects
        else:
            val = int(h['value'][6:])
            const_manager = Designer.objects
        h['const'] = list(const_manager.filter(parent_id=val).values('id', 'name', 'value'))


def str_datetime_to_rus(str_datetime):
    return str_datetime[8:10] + '.' + str_datetime[5:7] + '.' + str_datetime[:4] + ' ' + str_datetime[11:]


# gtfol = get totals from object list
def gtfol(objects, visible_headers, is_contract=False):
    manager = ContractCells.objects if is_contract else Objects.objects
    totals = {}
    dict_totals = {'max': 'Макс', 'min': 'Мин', 'sum': 'Сум', 'avg': 'СрЗнач',
                   'count': 'Колво' }
    for vh in visible_headers:
        if vh['formula'] == 'float' and vh['settings'] and 'totals' in vh['settings'] and vh['settings']['totals']:
            all_this_req = manager.filter(parent_structure_id=vh['parent_id'], name_id=vh['id'], value__isnull=False) \
                .annotate(val=Cast('value', output_field=FloatField()))
            page_list = [o[vh['id']]['value'] for o in objects if vh['id'] in o and o[vh['id']]['value'] != None]
            for tot in vh['settings']['totals']:
                rus_tot = dict_totals[tot]
                if not rus_tot in totals:
                    totals[rus_tot] = {}

                if tot == 'max':
                    full_tot = all_this_req.aggregate(tot=Max('val'))
                    page_tot = max(page_list) if page_list else 0
                elif tot == 'min':
                    full_tot = all_this_req.aggregate(tot=Min('val'))
                    page_tot = min(page_list) if page_list else 0
                elif tot == 'avg':
                    full_tot = all_this_req.aggregate(tot=Avg('val'))
                    page_tot = sum(page_list) / len(page_list) if page_list else 0
                elif tot == 'sum':
                    full_tot = all_this_req.aggregate(tot=Sum('val'))
                    page_tot = sum(page_list)
                else:
                    full_tot = {'tot': all_this_req.count()}
                    page_tot = len(page_list)
                full_tot = full_tot['tot'] if full_tot['tot'] else 0
                page_tot = page_tot if page_tot else 0
                totals[rus_tot][vh['id']] = {}
                totals[rus_tot][vh['id']]['full'] = f'Всего: {full_tot:,.2f}'.replace(',', ' ')
                totals[rus_tot][vh['id']]['page'] = f'На стр.: {page_tot:,.2f}'.replace(',', ' ')
    return totals


def dict_to_post(my_dict):
    class MyRequest:
        GET = {}
        POST = {}
        FILES = {}
        session = {}
        user = None
    my_request = MyRequest()
    for mk, mv in my_dict.items():
        my_request.POST[mk] = mv
    return my_request

# fitoop = filter to operation
# преобразование фильтра в логическую операцию
def fitoop(left_val, filter, right_val):
    if filter == 'eq':
        return left_val == right_val
    elif filter == 'ne':
        return left_val != right_val
    elif filter == 'gt':
        return left_val > right_val
    elif filter == 'lt':
        return left_val < right_val
    elif filter == 'ge':
        return left_val >= right_val
    elif filter == 'le':
        return left_val <= right_val
    elif filter == 'lk':
        return right_val.lower() in left_val.lower()


# renepreva = retreive next / previous value
def renepreva(base_query, code, timestamp, is_after, location, name_id, data_type):
    q = Q(date_update__gt=timestamp) if is_after else Q(date_update__lt=timestamp)
    order_by = 'date_update' if is_after else '-date_update'
    query = base_query.filter(q, json__location=location, json__code=code, json__name=name_id, reg_name__in=(13, 15)) \
              .values('json').order_by(order_by)[:1]
    if query:
        if query[0]['json']['value']:
            return query[0]['json']['value']
        else:
            return 0 if data_type == 'float' else ''
    elif is_after:
        return renepreva(base_query, code, timestamp, False, location, name_id, data_type)
    else:
        return 0 if data_type == 'float' else ''


# ficlubraco = filter_cluster_branch_codes
def ficlubraco(codes, base_query, timestamp, location, branch_id, cluster_branch_codes, future_codes=False):
    q = Q(date_update__gt=timestamp) if future_codes else Q(date_update__lt=timestamp)
    i = 0
    while i < len(codes):
        branch = base_query.filter(q, reg_name__in=(13, 15), json__location=location, json__name=branch_id,
                                   json__code=codes[i]['code']).order_by('-date_update')[:1]
        if not branch:
            codes.pop(i)
        elif branch[0].json['value'] not in cluster_branch_codes:
            codes.pop(i)
        else:
            i += 1
    return codes


# gvfo = get versions from objects
def gvfo(class_id, str_date, is_contract, is_after, user_id, source_codes=[]):
    version = parse_timestamp_for_hist(str_date, is_after)
    manager = ContractCells.objects if is_contract else Objects.objects
    path_info = '/contract' if is_contract else '/manage-object'
    loc = 'contract' if is_contract else 'table'
    tom = session_procedures.fill_tom(class_id, path_info, '', user_id, hide_tree=True)
    base_query = RegistratorLog.objects.filter(json_class=class_id)
    deleted_codes = base_query.filter(reg_name=16, date_update__lt=version, json_income__location=loc) \
        .annotate(code=F('json_income__code')).values('code').distinct()
    deleted_codes = [dc['code'] for dc in deleted_codes]
    exist_codes = base_query.filter(reg_name__in=(13, 15), date_update__lt=version, json__location=loc) \
                       .annotate(code=F('json__code')).values('code').distinct().exclude(code__in=deleted_codes)
    if source_codes:
        exist_codes = exist_codes.filter(code__in=source_codes)
    exist_codes = list(exist_codes)
    objects = []
    if not is_after:
        version -= datetime.timedelta(seconds=1)
    else:
        future_codes = list(base_query.filter(date_update__gt=version, reg_name=13) \
                            .annotate(code=F('json__code')).values('code').distinct())
        exist_codes += future_codes
    for ex_co in exist_codes:
        if is_after:
            next_change = base_query.filter(json__code=ex_co['code'], date_update__gt=version,
                                            reg_name__in=(13, 15, 8)).order_by('date_update')[:1]
            if next_change:
                if next_change[0].reg_name == 8:
                    continue
                obj = hist_funs.gov(class_id, ex_co['code'], loc, next_change[0].date_update, tom, user_id, children=False)
            else:
                obj = manager.filter(parent_structure_id=class_id, code=ex_co['code'])
                obj = convert_funs2.get_full_object(obj, tom['headers'], loc)
        else:
            obj = hist_funs.gov(class_id, ex_co['code'], loc, version, tom, user_id, children=False)
        if obj:
            objects.append(obj)
    return objects, tom


# Преобразовывает формулу вида [[user_data]] в html-теги
def userdata_to_interface(header, code, is_contract, is_main_page):
    dict_types = {'string': 'text', 'number': 'number', 'bool': 'checkbox', 'date': 'date',
                  'datetime': 'datetime-local', 'link': 'number'}
    user_data = re.findall(r'\[\[\s*\n*\s*user_data_\d+\s*\n*\s*(?:\{\{[\w\W]*?\}\}|)\s*\n*\s*\]\]', header['value'],
                           flags=re.M)
    val = ''
    if user_data:
        calc_button_label = 'Рассчитать'
        for ud in user_data:
            find_data = re.search(r'user_data_(\d+)\s*\n*\s*(?:\{\{([\w\W]*)\}\}|)', ud, flags=re.M)
            val += '<div class="input-group mb-3">'
            val += '<span class="input-group-text">'
            # Разберем опциональные параметры
            label = 'Пользовательская переменная №' + find_data[1]
            data_type = 'text'
            data_list = ''
            link_class = '0'
            link_location = 't'
            if find_data[2]:
                find_label = re.search(r'label\s*\n*\s*=\s*\n*\s*\'([\w\s\_]+)\'', find_data[2])
                if find_label:
                    label = find_label[1]
                find_type = re.search(r'type\s*\n*\s*=\s*\n*\s*(string|number|bool|datetime|date|link)', find_data[2])
                if find_type:
                    data_type = dict_types[find_type[1]]
                    if find_type[1] == 'link':
                        data_list = '<datalist id="dl_' + str(header['id']) + '_' + label + '"></datalist>'
                        find_link_class = re.search(r'link_class\s*\n*\s*=\s*\n*\s*(\d+)', find_data[2])
                        if find_link_class:
                            link_class = find_link_class[1]
                        find_link_location = re.search(r'link_location\s*\n*\s*=\s*\n*\s*([tc])', find_data[2])
                        if find_link_location:
                            link_location = find_link_location[1]
                find_button_label = re.search(r'button\s*\n*\s*=\s*\n*\s*\'([\w\s\_]+)\'', find_data[2])
                if find_button_label:
                    calc_button_label = find_button_label[1]
            val += label
            val += '</span>'
            val += '<input id="const_' + str(header['id']) + '_user_data_' + find_data[1] + '" class= "form-control" ' \
                                                                                        'type="' + data_type + '"'
            if data_type == 'number':
                val += ' step="any"'
            if data_list:
                val += ' list="dl_' + str(header['id']) + '_' + find_data[1] + '" oninput="promp_direct_link(this, \'' \
                       + link_location + '\', ' + link_class + ')"><datalist id="dl_' + str(header['id']) \
                       + '_' + find_data[1] + '"></datalist'
            val += '></div>'

        str_is_contract = str(is_contract).lower()
        fun_name = 'cmpf(' + str(header['id']) + ')' if is_main_page else 'calc_user_data(' + str(header['id']) + ', ' \
                    + str(code) + ', ' + str_is_contract + ')'
        val = val[
              :-6] + f'<div class="input-group-append"><button class="btn btn-outline-secondary" onclick="{fun_name}"' \
              + '>' + calc_button_label + '</button></div></div>'
        val += '<div id="div_const_' + str(header['id']) + '_result"></div>'
    return val

