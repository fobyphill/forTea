import json
import re
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.http import HttpResponse
from django.contrib import auth
from app.functions import api_funs, view_procedures, api_procedures, convert_procedures, interface_funs, api_funs2, \
    convert_funs


@view_procedures.is_auth
def create_object(request):
    if request.user.is_authenticated:
        location = request.GET['location'] if 'location' in request.GET else 'table'
        if 'class_id' in request.GET:
            class_id = int(request.GET['class_id'])
        else:
            return HttpResponse('Не указан обязательный параметр - class_id')
        params = {}
        for k, v in request.GET.items():
            if k not in ('class_id', 'location'):
                params[k] = v
        result = api_funs.create_object(class_id, request.user.id, location, 'api', **params)
        if not type(result) is str:
            rus_loc = {'table': 'Справочники', 'contract': 'Контракты', 'dict': 'Словари'}
            result = 'Создан объект класса. ID класса: ' + request.GET['class_id'] + '. Расположение: ' \
                     + rus_loc[location] + '. Код объекта: ' + str(result[0].code)
        return HttpResponse(result)
    else:
        return HttpResponse('Вы не авторизованы. Пожалуйста авторизуйтесь')


@view_procedures.is_auth
def remove_object(request):
    if request.user.is_authenticated:
        location = request.GET['location'] if 'location' in request.GET else 'table'
        if 'class_id' in request.GET:
            class_id = int(request.GET['class_id'])
        else:
            return HttpResponse('Не указан обязательный параметр - class_id')
        if 'code' in request.GET:
            code = request.GET['code']
        else:
            return HttpResponse('Не указан обязательный параметр - code')
        if 'forced' in request.GET:
            forced = True
        else:   forced = False

        result = api_funs.remove_object(class_id, code, request.user.id, location, 'api', forced)
        if not type(result) is str:
            rus_loc = {'table': 'Справочники', 'contract': 'Контракты', 'dict': 'Словари'}
            result = 'Удален объект класса. ID класса: ' + request.GET['class_id'] + '. Расположение: ' + rus_loc[location]\
            + '.<br>Код объекта: ' + str(result[0].code)
        return HttpResponse(result)
    else:
        return HttpResponse('Вы не авторизованы. Пожалуйста авторизуйтесь')


@view_procedures.is_auth
def edit_object(request):
    if request.user.is_authenticated:
        location = request.GET['location'] if 'location' in request.GET else 'table'
        if 'class_id' in request.GET:
            try:
                class_id = int(request.GET['class_id'])
            except ValueError:
                return HttpResponse('Параметр class_id указан некорректно. Задайте целое число в качестве ID класса')
        else:
            return HttpResponse('Не указан обязательный параметр - class_id')
        if 'code' in request.GET and request.GET['code']:
            try:
                code = int(request.GET['code'])
            except ValueError:
                return HttpResponse('Параметр code указан некорректно. Задайте целое число в качестве кода')
        else:
            return HttpResponse('Не указан обязательный параметр - code')
        params = {}
        for k, v in request.GET.items():
            if k not in ('class_id', 'location', 'code'):
                params[k] = v
        result = api_funs.edit_object(class_id, code, request.user.id, location, 'api', **params)
        if not type(result) is str:
            rus_loc = {'table': 'Справочники', 'contract': 'Контракты', 'dict': 'Словари', 'tp': 'Техпроцессы'}
            result = 'Изменен объект класса. ID класса: ' + request.GET['class_id'] + '. Расположение: ' + rus_loc[location]\
            + '.<br>Код объекта: ' + request.GET['code']
        return HttpResponse(result)
    else:
        return HttpResponse('Вы не авторизованы. Пожалуйста авторизуйтесь')


# Получить объект. Три обязательных параметра: class_id, code, location = ['table', 'contract', 'dict', 'tp']
@view_procedures.is_auth
def get_object(request):
    is_valid, message, class_id, code, location = interface_funs.valid_api_data(request)
    if is_valid:
        response_data = api_funs.get_object(class_id, code, location)
        return HttpResponse(json.dumps(response_data, ensure_ascii=False), content_type="application/json")
    else:
        return HttpResponse(message)

# Получить список объектов. Обязательный параметр - class_id. Список условий передается через параметр condition
# location = table, dict, contract. По умолчанию table Логическая связь между условиямим - ИЛИ либо И - logic_connector - OR | AND
# Пагинатор. ПО умолчанию выключен. Если нужно выводить часть объектов - то количество объектов определяет
# параметр num_objects, а номер страницы - page.
# Выход - массив объектов или массив ошибок
@view_procedures.is_auth
def get_object_list(request):
    error_message = []
    result = True
    params = {}
    # проверка параметров
    if not 'class_id' in request.GET:
        result = False
        error_message.append('Ошибка. Не указан ID класса')
    if 'location' in request.GET:
        params['location'] = request.GET['location']
    if 'logic_connector' in request.GET:
        params['logic_connector'] = request.GET['logic_connector']
    if 'num_objects' in request.GET:
        params['num_objects'] = request.GET['num_objects']
    if 'page' in request.GET:
        params['page'] = request.GET['page']
    if 'output_type' in request.GET:
        params['output_type'] = request.GET['output_type']
    params['date_update'] = ('date_update' in request.GET and request.GET['date_update'] == 'True')
    if 'fields' in request.GET:
        def parse_fields(str_fields):
            fields_list = []
            parsed_fields = re.findall(r'(?:(?:[\wа-яА-Я\s]+)|(?:\{.+\}))(?:\,|$)', str_fields)
            if not parsed_fields:
                return False
            for pf in parsed_fields:
                dict_field = dict()
                match_simple_field = re.match(r'\s*(\d+)(?:\s*as\s*([\wа-яА-Я\s]+)|)', pf)
                if match_simple_field:
                    dict_field['id'] = int(match_simple_field[1])
                    dict_field['alias'] = match_simple_field[2]
                else:
                    match_deep_field = re.match(r'\{\s*(\d+)(?:(?:\s*as\s*([\wа-яА-Я\s]+))|)\s*\:\s*\[(.*)\]\}', pf)
                    if not match_deep_field:
                        return False
                    dict_field['id'] = int(match_deep_field[1])
                    dict_field['alias'] = match_deep_field[2]
                    if match_deep_field[3]:
                        dict_field['children'] = parse_fields(match_deep_field[3])
                        if not dict_field['children']:
                            return False
                    else:
                        dict_field['children'] = []
                fields_list.append(dict_field)
            return fields_list
        fields = parse_fields(request.GET['fields'])
        if fields:
            params['fields'] = fields
    conditions = []
    if not 'condition' in request.GET:
        result = False
        error_message.append('Ошибка. Не указано ни одно условие')
    else:
        conditions = request.GET.getlist('condition')
    if result:
        list_object = api_funs.get_object_list(request.GET['class_id'], *conditions, **params)[1]
    else:   list_object = error_message
    return HttpResponse(json.dumps(list_object, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
def create_class(request):
    # Проверка основных параметров
    if not ('class_name' in request.GET and request.GET['class_name']):
        return HttpResponse('Ошибка. Не задано имя класса')
    if not ('class_type' in request.GET and request.GET['class_type']):
        return HttpResponse('Ошибка. Не задан тип класса')

    # Инциализация остальных параметров
    parent_id = request.GET['parent_id'] if 'parent_id' in request.GET else None
    params = {}
    if 'location' in request.GET:  params['location'] = request.GET['location']
    if 'parent_transact' in request.GET:    params['parent_transact'] = request.GET['parent_transact']
    if 'timestamp' in request.GET:  params['timestamp'] = request.GET['timestamp']
    if 'business_rule' in request.GET:  params['biznes_rule'] = request.GET['business_rule']
    if 'link_map' in request.GET:
        params['link_map'] = request.GET['link_map']
        if request.GET['class_type'] == 'techpro':
            try:
                params['link_map'] = [int(lm) if lm else None for lm in request.GET['link_map'].split(',')]
            except ValueError:
                return HttpResponse('Ошибка. Некорректно указан параметр "link_map". Укажите набор целых чисел через запятую')
    if 'trigger' in request.GET:    params['trigger'] = request.GET['trigger']
    if 'stages' in request.GET: params['stages'] = request.GET['stages'].split(',')
    if 'control_field' in request.GET:
        try:
            params['control_field'] = int(request.GET['control_field'])
        except ValueError:
            return HttpResponse('Ошибка. Некорректно указан параметр "conrtol_field". Укажите целое число')
    class_types = list(k for k in request.session['class_types'].keys())
    result = api_funs.create_class(request.user.id, request.GET['class_type'], class_types, request.GET['class_name'], parent_id, **params)
    if result[0]:
        return HttpResponse(result[1])
    else:
        return HttpResponse('Ошибка. ' + result[1])


@view_procedures.is_auth
def edit_class(request):
    if not ('class_id' in request.GET and 'class_type' in request.GET):
        return HttpResponse('Ошибка. Не заданы обязательные параметры - class_id, class_type')
    location = request.GET['location'] if 'location' in request.GET else 't'
    params = {}
    if 'parent_id' in request.GET:
        params['parent_id'] = request.GET['parent_id']
    if 'class_name' in request.GET:
        params['class_name'] = request.GET['class_name']
    if 'parent_transact' in request.GET:
        params['parent_transact'] = request.GET['parent_transact']
    if 'timestamp' in request.GET:
        params['timestamp'] = request.GET['timestamp']
    return HttpResponse(api_funs.edit_class(request.user.id, request.GET['class_id'], request.GET['class_type'],
                                            location, **params))


@view_procedures.is_auth
def create_class_param(request):
    if not ('class_id' in request.GET and 'class_type' in request.GET and 'param_name' in request.GET
            and 'param_type' in request.GET):
        return HttpResponse('Ошибка. Не заданы обязательные параметры - class_id, class_type')
    try:
        class_id = int(request.GET['class_id'])
    except ValueError:
        return HttpResponse('Ошибка. Некорректно задан параметр class_id. Класс не найден')
    location = request.GET['location'] if 'location' in request.GET else 't'
    is_params_done, params = api_procedures.copafroc(request)
    if not is_params_done:
        return HttpResponse(params)
    result = api_funs.create_class_param(request.user.id, class_id, request.GET['class_type'], request.GET['param_name'],
                                         request.GET['param_type'], location, **params)
    return HttpResponse(result)


@view_procedures.is_auth
def edit_class_param(request):
    if not ('param_id' in request.GET and 'class_type' in request.GET and 'param_type' in request.GET):
        return HttpResponse('Ошибка. Не заданы обязательные параметры - param_id, class_type, param_type')
    try:
        param_id = int(request.GET['param_id'])
    except ValueError:
        return HttpResponse('Ошибка. Некорректно задан параметр param_id. Укажите целое число')
    is_params_done, params = api_procedures.copafroc(request)
    if not is_params_done:
        return  HttpResponse(params)
    else:
        params['location'] = request.GET['location'] if 'location' in request.GET else 't'
        params['param_type'] = request.GET['param_type']
        if 'name' in request.GET:
            params['name'] = request.GET['name']
    result = api_funs.edit_class_param(request.user.id, request.GET['class_type'], param_id, **params)
    return HttpResponse(result)


@view_procedures.is_auth
def remove_class_param(request):
    if not ('class_type' in request.GET and 'param_id' in request.GET):
        return HttpResponse('Не переданы все обязательные параметры: class_type, param_id')
    location = 't' if not 'location' in request.GET else request.GET['location']
    if location not in ('t', 'c'):
        return HttpResponse('Некорректно указан параметр location. Укажите один из символов: t или c')
    return HttpResponse(api_funs.remove_class_param(request.user.id, request.GET['class_type'], request.GET['param_id'],
                                                    location))


@view_procedures.is_auth
def remove_class(request):
    if not ('class_id' in request.GET and 'class_type' in request.GET):
        return HttpResponse('Не переданы все обязательные параметры: class_type, class_id')
    location = 't' if not 'location' in request.GET else request.GET['location']
    return HttpResponse(api_funs.remove_class(request.user.id, request.GET['class_id'], request.GET['class_type'], location))


@view_procedures.is_auth
def get_class(request):
    if not ('class_id' in request.GET and 'class_type' in request.GET):
        return HttpResponse('Не заданы обязательные параметры: "class_id", "class_type"')
    location = request.GET['location'] if 'location' in request.GET else 't'
    is_done, result = api_funs.get_class(request.GET['class_id'], request.GET['class_type'], location)
    if is_done:
        return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")
    else:
        return HttpResponse(result)


@view_procedures.is_auth
def get_class_list(request):
    location = request.GET['location'] if 'location' in request.GET else 't'
    try:
        parent_id = int(request.GET['parent_id']) if 'parent_id' in request.GET and request.GET['parent_id'] else None
    except ValueError:
        return 'Некорректно указан параметр parent_id. Укажите целое число'
    is_done, result = api_funs.get_class_list(parent_id, location)
    content_type = "application/json" if is_done else 'text/html'
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type=content_type)


@view_procedures.is_auth
def run_eval(request):
    return HttpResponse(convert_funs.static_formula(request.GET['eval'], request.user.id))


def login(request):
    if request.user.is_authenticated:
        return HttpResponse(request.COOKIES['csrftoken'])
    else:
        if 'login' in request.GET and 'password' in request.GET:
            user = auth.authenticate(username=request.GET['login'], password=request.GET['password'])
            if user:
                auth.login(request, user)
                return HttpResponse(request.COOKIES['csrftoken'])
            else:
                return HttpResponse('Логин и пароль некорректны')
        else:
            return HttpResponse('Не указан логин или пароль')


def logout(request):
    if request.user.is_authenticated:
        auth.logout(request)
    return HttpResponse('ok')


@view_procedures.is_auth
def remove_object_list(request):
    if not 'class_id' in request.GET:
        return 'Не задан ID класса'
    if not 'location' in request.GET:
        location = 't'
    else:
        location = request.GET['location']
    list_codes = [int(lc) for lc in request.GET['list_codes'].split(',')] if 'list_codes' in request.GET else []
    interval_codes = request.GET['interval_codes'] if 'interval_codes' in request.GET else None
    source = request.GET['source'] if 'source' in request.GET else None
    forced = True if 'forced' in request.GET and request.GET['forced'] == 'true' else False
    timestamp = convert_procedures.parse_timestamp(request.GET['timestamp']) if 'timestamp' in request.GET else datetime.today()
    if not timestamp:
        return 'Некорректно задана временная метка. Укажите дату или дату-время в российской локали или формате ISO'
    parent_transact = request.GET['parent_transact'] if 'parent_transact' in request.GET else None
    result = api_funs.remove_object_list(request.GET['class_id'], request.user.id, location=location,
                                         interval_codes=interval_codes, list_codes=list_codes, source=source,
                                         forced=forced, timestamp=timestamp, parent_transact=parent_transact)
    return HttpResponse(str(result))


@view_procedures.is_auth
def get_object_hist(request):
    is_valid, message, class_id, code, location = interface_funs.valid_api_data(request)
    if 'children' in request.GET:
        children = False if request.GET['children'] in ('', 'false', 'False', '0') else True
    else:
        children = True
    if 'date_to' in request.GET and request.GET['date_to']:
        try:
            date_to = datetime.strptime(request.GET['date_to'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
                is_valid = False
                message += 'Некорректно указан параметр "date_to". Укажите дату в формате ГГГГ-ММ-ДДТчч:мм:сс<br>'
    else:
        date_to = datetime.today()
    if 'date_from' in request.GET and request.GET['date_from']:
        try:
            date_from = datetime.strptime(request.GET['date_from'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            is_valid = False
            message += 'Некорректно указан параметр "date_from". Укажите дату в формате ГГГГ-ММ-ДДТчч:мм:сс<br>'
    elif is_valid:
        date_from = date_to - relativedelta(months=1)
    if is_valid:
        response_data = api_funs2.get_object_hist(class_id, code, date_from, date_to, location=location, children=children)
    else:
        response_data = message
    return HttpResponse(json.dumps(response_data, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
def make_task(request):
    if not 'task_id' in request.GET or not request.GET['task_id']:
        return HttpResponse('Ошибка. Не задан параметр task_id')
    try:
        task_id = int(request.GET['task_id'])
    except ValueError:
        return HttpResponse('Ошибка. Параметр "task_id" должен быть целым числом')
    result = api_funs2.make_task(task_id, request.user.id)
    return HttpResponse(result)


