import json, datetime
import re

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, OuterRef, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.http import HttpResponse
from app.functions import convert_funs, convert_procedures, view_procedures, session_funs
from app.models import Objects, Designer, Contracts, ContractCells, Dictionary, RegistratorLog, DictObjects


@view_procedures.if_error_json
def query_link(request):
    if request.user.is_authenticated:
        try:
            class_type = request.GET['class_type']
            my_class = Contracts.objects if class_type == 'c' else Designer.objects if class_type == 't' else Dictionary.objects
            my_class = my_class.get(id=request.GET['header_id'])
            base_link = my_class.value if class_type != 'd' else re.match(r'(?:contract|table)\.\d+', my_class.default)[0]
            parent_class_type, parent_class_id = convert_procedures.slice_link_header(base_link)
            constructor = Designer.objects if parent_class_type == 'table' else Contracts.objects
            name = 'system_data' if parent_class_type == 'contract' else 'Наименование'
            parent_class_name_id = constructor.filter(parent_id=parent_class_id, is_required=True, name__iexact=name)[0].id
            records = Objects.objects if parent_class_type == 'table' else ContractCells.objects
            object = records.get(code=int(request.GET['link_code']), parent_structure_id=int(parent_class_id),
                                 name_id=int(parent_class_name_id))
            val = object.value['datetime_create'] if parent_class_type == 'contract' else object.value
            result = {'class_id': parent_class_id, 'object_code': int(request.GET['link_code']),
                      'object_name': val, 'location': class_type}
            result_string = json.dumps(result)
        except (ObjectDoesNotExist, ValueError):
            return HttpResponse('Объект не найден')

        return HttpResponse(result_string, content_type="application/json")
    else:   return HttpResponse('false')


def class_link(request):
    if request.user.is_authenticated:
        try:
            if request.GET['class_type'] == 'table':    my_class = Designer.objects
            else:   my_class = Contracts.objects
            my_link = my_class.filter(id=request.GET['link_id'], formula=request.GET['class_type'])
            if my_link:
                return HttpResponse(my_link[0].name)
            else:
                return HttpResponse('Объект не найден')
        except:
            return HttpResponse('Объект не найден')
    else:   return HttpResponse('false')


def default_link(request):
    if request.user.is_authenticated:
        try:
            if request.GET['class_type'] == 'table':
                my_class = Objects.objects.all()
                my_name = Designer.objects.get(parent_id=request.GET['parent_id'], name='Наименование')
            else:
                my_class = ContractCells.objects.all()
                my_name = Contracts.objects.get(parent_id=request.GET['parent_id'], name='system_data')
            my_link = my_class.get(code=request.GET['link_code'], name_id=my_name.id, parent_structure_id=request.GET['parent_id'])
            result = my_link.value if request.GET['class_type'] == 'table' else my_link.value['datetime_create']
            return HttpResponse(result)
        except Exception:
            return HttpResponse('Объект не найден')
    else:   return HttpResponse('false')


def get_alias_params(request):
    if request.user.is_authenticated:
        try:
            if request.GET['is_contract'] == 'true':
                params_alias = list(Contracts.objects.filter(parent_id=request.GET['alias_id']).values('id', 'name'))
            else:
                params_alias = list(Designer.objects.filter(parent_id=request.GET['alias_id']).values('id', 'name'))
            result_string = json.dumps(params_alias)
        except Exception:
            return HttpResponse('Объект не найден')
        else:
            return HttpResponse(result_string, content_type="application/json")
    else:   HttpResponse('Объект не найден')


# Получить классы. Подсказка для истории. Вызывается функцией prompt_classes
@view_procedures.is_auth
def get_classes(request):
    try:
        if request.GET['type_class'] == 'all':
            formula = request.session['class_types'].keys()
        else:
            formula = request.GET['type_class'],
        # Работаем с классами
        if request.GET['current_class']:
            dicts = Dictionary.objects.filter(formula='dict')
            tables = Designer.objects.filter(formula__in=formula)
            contracts = Contracts.objects.filter(formula__in=formula)
            try:
                class_id = int(request.GET['current_class'])
            except ValueError:
                dicts = dicts.filter(name__icontains=request.GET['current_class'])
                tables = tables.filter(name__icontains=request.GET['current_class'])
                contracts = contracts.filter(name__icontains=request.GET['current_class'])
            else:
                dicts = dicts.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_class']))
                tables = tables.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_class']))
                contracts = contracts.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_class']))
            if request.GET['location'] != 'all':
                dicts = dicts.filter(default=request.GET['location'])
            # Получим результирующий массив объектов
            result = []
            if request.GET['location'] in ('all', 'table'):
                result.extend(list(tables.values('id', 'name', 'formula')))
            if request.GET['location'] in ('all', 'contract'):
                result.extend(list(contracts.values('id', 'name', 'formula')))
            result.extend(list(dicts.values('id', 'name', 'formula')))
            if result:
                for r in result:
                    r['formula'] = request.session['class_types'][r['formula']]
            result = json.dumps(result, ensure_ascii=False)
        else:
            result = ''
        return HttpResponse(result, content_type="application/json")
    except Exception as ex:
        return HttpResponse('Ошибка' + str(ex))


# Получить заголовки. Подсказка для истории. Вызывается функцией prompt_name
@view_procedures.is_auth
def get_name(request):
    try:
        class_types = request.session['class_types'].keys()
        # Работаем с классами
        if request.GET['current_name']:
            dict_header = Dictionary.objects.filter(id=OuterRef('parent_id'))
            dicts = Dictionary.objects.exclude(formula='dict')\
            .annotate(parent_name=Subquery(dict_header.values('name')[:1]))\
            .annotate(parent_formula=Subquery(dict_header.values('formula')[:1]))\
            .annotate(parent_default=Subquery(dict_header.values('default')[:1]))
            tables = Designer.objects.exclude(formula__in=class_types).select_related('parent')
            contracts = Contracts.objects.exclude(formula__in=class_types).select_related('parent')
            try:
                class_id = int(request.GET['current_name'])
            except ValueError:
                dicts = dicts.filter(name__icontains=request.GET['current_name'])
                tables = tables.filter(name__icontains=request.GET['current_name'])
                contracts = contracts.filter(name__icontains=request.GET['current_name'])
            else:
                dicts = dicts.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_name']))
                tables = tables.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_name']))
                contracts = contracts.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_name']))
            if request.GET['location'] != 'all':
                dicts = dicts.filter(parent_default=request.GET['location'])
            # фильтруем по типу данных
            if request.GET['type_class'] != 'all':
                if request.GET['type_class'] == 'dict':
                    contracts = contracts.filter(id=0)
                    tables = tables.filter(id=0)
                else:
                    dicts = dicts.filter(id=0)
                    tables = tables.filter(parent__formula=request.GET['type_class'])
                    contracts = contracts.filter(parent__formula=request.GET['type_class'])
            # Получим результирующий массив объектов
            result = []
            if request.GET['location'] in ('all', 'table'):
                result.extend(list(tables.values('id', 'name', 'formula')))
            if request.GET['location'] in ('all', 'contract'):
                result.extend(list(contracts.values('id', 'name', 'formula')))
            result.extend(list(dicts.values('id', 'name', 'formula')))
            result = json.dumps(result, ensure_ascii=False)
        else:
            result = ''
        return HttpResponse(result, content_type="application/json")
    except Exception as ex:
        return HttpResponse('Ошибка' + str(ex))


# Вернуть константу. Возвращает в формате джейсон данные константы - id и имена
@view_procedures.is_auth
def retreive_const_list(request):
    try:
        manager = Contracts.objects if request.GET['is_contract'] == 'true' else Designer.objects
        const = [{'id': m.id, 'name': m.name} for m in manager.filter(parent_id=request.GET['alias_id'])]
        const = json.dumps(const, ensure_ascii=False)
        return HttpResponse(const, content_type="application/json")
    except Exception as ex:
        return HttpResponse('Ошибка' + str(ex))


# Подсказать ссылку
@view_procedures.is_auth
@view_procedures.if_error
def promp_link(request):
    manager = Contracts.objects if request.GET['is_contract'] == 'true' else Designer.objects
    header = manager.get(id=request.GET['header_id'])
    parent_type, parent_id = convert_procedures.slice_link_header(header.value)
    manager_parent_object = ContractCells.objects if parent_type == 'contract' else Objects.objects
    parent_object = manager_parent_object.filter(parent_structure_id=parent_id)
    manager_parent_header = Contracts.objects if parent_type == 'contract' else Designer.objects
    parent_name = 'system_data' if parent_type == 'contract' else 'Наименование'
    parent_name_id = manager_parent_header.get(parent_id=parent_id, name=parent_name).id
    if request.GET['link']:
        try:
            code = int(request.GET['link'])
        except ValueError:
            parent_object = parent_object.filter(value__icontains=request.GET['link'])
        else:
            parent_object = parent_object.filter(Q(code=code) | Q(value__icontains=request.GET['link']))
        finally:
            result_codes = parent_object.values('code').distinct()
    else:
        result_codes = [p['code'] for p in parent_object.values('code').distinct()[:10]]
    parent_names = list(parent_object.filter(code__in=result_codes, name_id=parent_name_id).values('code', 'value'))
    if parent_type == 'contract':
        parent_names = [{'code': pn['code'], 'value': pn['value']['datetime_create']} for pn in parent_names]
    result = json.dumps(parent_names, ensure_ascii=False)
    return HttpResponse(result, content_type="application/json")


# Подсказать хозяина для словаря
@view_procedures.is_auth
@view_procedures.if_error
def promp_owner(request):
    dictionary = Dictionary.objects.get(id=int(request.GET['class_id']))
    manager = Objects.objects if dictionary.default == 'table' else ContractCells.objects
    objects = manager.filter(parent_structure_id=dictionary.parent_id)
    objects = objects.filter(name__name__icontains='наименование') if dictionary.default == 'table'\
        else objects.filter(name__name__icontains='дата и время записи')
    if request.GET['link']:
        try:
            code = int(request.GET['link'])
        except ValueError:
            objects = objects.filter(value__icontains=request.GET['link'])
        else:
            objects = objects.filter(Q(code=code) | Q(value__icontains=request.GET['link']))
        result_codes = objects.values('code').distinct()
    else:
        result_codes = [o['code'] for o in objects.values('code').distinct()[:10]]

    parent_names = manager.filter(parent_structure_id=dictionary.parent_id)
    name_main_field = 'Наименование' if dictionary.default == 'table' else 'Дата и время записи'
    parent_names = parent_names.filter(code__in=result_codes, name__name__icontains=name_main_field)
    parent_names = list(parent_names.values('code', 'value'))
    result = json.dumps(parent_names, ensure_ascii=False)
    return HttpResponse(result, content_type="application/json")


# Вернуть список дат-пользователей
@view_procedures.is_auth
@view_procedures.if_error_json
def roh(request):
    class_id = int(request.GET['class_id'])
    session_funs.update_omtd(request)
    code = int(request.GET['code'])
    dict_loc = {'c': 'contract', 't': 'table', 'd': 'dict'}
    location = dict_loc[request.GET['location']]
    just_history = False  # Возвращает истину, если массив данных содержит только данные истории,
    if request.GET['timeline_from']:
        try:
            date_from = datetime.datetime.strptime(request.GET['timeline_from'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            date_from = datetime.datetime.strptime(request.GET['timeline_from'], '%Y-%m-%dT%H:%M')
    else: date_from = datetime.datetime.today()
    base_hist = RegistratorLog.objects.filter(reg_name_id__in=(13, 15, 22), json_class=class_id, json__code=code)
    if location in ('table', 'contract'):
        base_hist = base_hist.filter(json__location=location)
    elif location == 'dict':
        base_hist = base_hist.filter(json__type='dict')
    q_hist = base_hist.filter(date_update__gte=date_from)

    if request.GET['timeline_to']:
        try:
            date_to = datetime.datetime.strptime(request.GET['timeline_to'], '%Y-%m-%dT%H:%M:%S') + \
                      datetime.timedelta(seconds=1)
        except ValueError:
            date_to = datetime.datetime.strptime(request.GET['timeline_to'], '%Y-%m-%dT%H:%M') + \
                datetime.timedelta(seconds=1)
        q_hist = q_hist.filter(date_update__lte=date_to)
    else:
        date_to = datetime.datetime.today()
    q_hist = list(q_hist.select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct())

    last_date_object = base_hist.order_by('-date_update')[:1]  # последняя запись в истории данного объекта
    if last_date_object and last_date_object[0].date_update > date_to:
        just_history = True
    # Создадим массив с данными словарей, принадлежащих к данному объекту
    last_date_dicts = []
    if location != 'dict':
        for md in request.session['temp_object_manager']['my_dicts']:
            # Современное значение словаря
            list_history_dict_base = RegistratorLog.objects.filter(json__type='dict', json__parent_code=code,
                                                                   json_class=md['id'], json__location=location,
                                                                   reg_name_id__in=(13, 15))
            list_history_dict = list_history_dict_base.filter(date_update__gte=date_from, date_update__lte=date_to) \
            .select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct()
            q_hist += [lhd for lhd in list_history_dict if not lhd in q_hist]
            if not just_history:
                ldd = list_history_dict_base.order_by('-date_update')[:1]
                if ldd:
                    last_date_dicts.append(ldd[0])
        for ldd in last_date_dicts:
            if ldd.date_update > date_to:
                just_history = True
                break

    # Создадим список с подчиненными массивами
    last_date_arrays = []
    if 'arrays' in request.session['temp_object_manager']:
        for a in request.session['temp_object_manager']['arrays']:
            owner = next(h for h in a['headers'] if h['name'] == 'Собственник')
            array_codes = RegistratorLog.objects.filter(reg_name_id=13, json_class=a['id'],
                                                        json__location=location,
                                                        json__name=owner['id'], json__value=code)\
                .annotate(code=KeyTextTransform('code', 'json')).values('code').distinct()
            array_codes = [ac['code'] for ac in array_codes]
            list_hist_arr_base = RegistratorLog.objects.filter(reg_name_id__in=(13, 15), json_class=a['id'],
                                                               json__location=location,
                                                               json__code__in=array_codes)
            list_hist_arr = list_hist_arr_base.filter(date_update__gte=date_from, date_update__lte=date_to)\
            .select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct()
            q_hist += [lha for lha in list_hist_arr if not lha in q_hist]
            if not just_history:
                lha = list_hist_arr_base.order_by('-date_update')[:1]
                if lha:
                    last_date_arrays.append(lha[0])
        for lda in last_date_arrays:
            if lda.date_update > date_to:
                just_history = True
                break

    # ДОбавим список с техпроцессами
    last_date_tps = []
    if 'tps' in request.session['temp_object_manager'] and request.session['temp_object_manager']['tps']:
        for tp in request.session['temp_object_manager']['tps']:
            list_hist_tp_base = RegistratorLog.objects.filter(reg_name_id=15, json_class=tp['id'],
                                                               json__location=location, json__code=code, json__type='tp')
            lht = list_hist_tp_base.order_by('-date_update')[:1]
            if lht:
                if not just_history:
                    last_date_tps.append(lht[0])
                list_hist_tp = list_hist_tp_base.filter(date_update__gte=date_from, date_update__lte=date_to) \
                    .select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct()
                q_hist += [lht for lht in list_hist_tp if not lht in q_hist]
        for ldt in last_date_tps:
            if ldt.date_update > date_to:
                just_history = True
                break

    # Избавимся от нативной даты-времени
    timeline = []
    for qh in q_hist:
        du = datetime.datetime.strftime(qh['date_update'], '%Y-%m-%dT%H:%M:%S')
        user = qh['user__first_name'] + ' ' + qh['user__last_name']
        timeline.append({'date_update': du, 'user': user})
    timeline.sort(key=lambda x: x['date_update'])

    data = {'just_history': just_history, 'timeline': timeline}
    return HttpResponse(json.dumps(data, ensure_ascii=False), content_type="application/json")


# вернуть значение константы
@view_procedures.is_auth
@view_procedures.if_error
def retreive_const(request):
    manager = Contracts.objects if request.GET['is_contract'] == 'true' else Designer.objects
    header = manager.get(id=int(request.GET['header_id']))
    formula = '[[' + header.value + '.' + request.GET['val'] + ']]'
    result = convert_funs.static_formula(formula, request.user.id)
    return HttpResponse(str(result))