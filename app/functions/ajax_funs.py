import json, datetime
import re

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, OuterRef, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.http import HttpResponse
from app.functions import convert_funs, convert_procedures, view_procedures, session_funs, hist_funs
from app.models import Objects, Designer, Contracts, ContractCells, Dictionary, RegistratorLog, DictObjects
from app.other.global_vars import is_mysql


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
                      'object_name': val, 'location': parent_class_type[0]}
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
            class_id = 0
            try:
                class_id = int(request.GET['current_class'])
            except ValueError:
                pass
            finally:
                if request.GET['location'] != 'all':
                    dicts = dicts.filter(default=request.GET['location'])
                if is_mysql:
                    dicts = dicts.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_class']))
                    dicts = list(dicts.values('id', 'name', 'formula'))
                    tables = list(tables.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_class']))\
                                  .values('id', 'name', 'formula'))
                    contracts = list(contracts.filter(Q(id=class_id) | Q(name__icontains=request.GET['current_class']))\
                                     .values('id', 'name', 'formula'))
                else:
                    current_class = request.GET['current_class'].lower()
                    dicts = [{'id': d.id, 'name': d.name, 'formula': d.formula} for d in dicts if d.id == class_id or
                             current_class in d.name.lower()]
                    tables = [{'id': t.id, 'name': t.name, 'formula': t.formula} for t in tables if t.id == class_id or
                             current_class in t.name.lower()]
                    contracts = [{'id': c.id, 'name': c.name, 'formula': c.formula} for c in contracts if c.id == class_id or
                             current_class in c.name.lower()]

            # Получим результирующий массив объектов
            result = []
            if request.GET['location'] in ('all', 'table'):
                result.extend(tables)
            if request.GET['location'] in ('all', 'contract'):
                result.extend(contracts)
            result.extend(dicts)
            if result:
                for r in result:
                    r['formula'] = request.session['class_types'][r['formula']]
            result = json.dumps(result, ensure_ascii=False)
        else:
            result = '[]'
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
            name_id = 0
            try:
                name_id = int(request.GET['current_name'])
            except ValueError:
                pass
                # dicts = dicts.filter(name__icontains=request.GET['current_name'])
                # tables = tables.filter(name__icontains=request.GET['current_name'])
                # contracts = contracts.filter(name__icontains=request.GET['current_name'])
            finally:
                if request.GET['location'] != 'all':
                    dicts = dicts.filter(parent_default=request.GET['location'])
                if request.GET['type_class'] != 'all':
                    if request.GET['type_class'] == 'dict':
                        contracts = contracts.filter(id=0)
                        tables = tables.filter(id=0)
                    else:
                        dicts = dicts.filter(id=0)
                        tables = tables.filter(parent__formula=request.GET['type_class'])
                        contracts = contracts.filter(parent__formula=request.GET['type_class'])
                if is_mysql:
                    dicts = list(dicts.filter(Q(id=name_id) | Q(name__icontains=request.GET['current_name']))\
                                 .values('id', 'name', 'formula'))
                    tables = list(tables.filter(Q(id=name_id) | Q(name__icontains=request.GET['current_name']))\
                                  .values('id', 'name', 'formula'))
                    contracts = list(contracts.filter(Q(id=name_id) | Q(name__icontains=request.GET['current_name']))\
                                     .values('id', 'name', 'formula'))
                else:
                    part_name = request.GET['current_name'].lower()
                    dicts = [{'id': d.id, 'name': d.name, 'formula': d.formula} for d in dicts if d.id == name_id or \
                             part_name in d.name.lower()]
                    tables = [{'id': t.id, 'name': t.name, 'formula': t.formula} for t in tables if t.id == name_id or\
                              part_name in t.name.lower()]
                    contracts = [{'id': c.id, 'name': c.name, 'formula': c.formula} for c in contracts \
                                 if c.id == name_id or part_name in c.name.lower()]
            # Получим результирующий массив объектов
            result = []
            if request.GET['location'] in ('all', 'table'):
                result.extend(tables)
            if request.GET['location'] in ('all', 'contract'):
                result.extend(contracts)
            result.extend(dicts)
            result = json.dumps(result, ensure_ascii=False)
        else:
            result = '[]'
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
    code = 0
    if request.GET['link']:
        try:
            code = int(request.GET['link'])
        except ValueError:
            pass
        finally:
            if is_mysql:
                parent_object = parent_object.filter(Q(code=code) | Q(value__icontains=request.GET['link']))\
                    .values('code').distinct()
                result_codes = [p['code'] for p in parent_object]
            else:
                q_link = request.GET['link'].lower()
                result_codes = list(set([po.code for po in parent_object if q_link in po.value.lower()]))
    else:
        result_codes = [p['code'] for p in parent_object.values('code').distinct()[:10]]
    parent_names = list(parent_object.filter(code__in=result_codes, name_id=parent_name_id).values('code', 'value'))
    if parent_type == 'contract':
        parent_names = [{'code': pn['code'], 'value': pn['value']['datetime_create']} for pn in parent_names]
    result = json.dumps(parent_names, ensure_ascii=False)
    return HttpResponse(result, content_type="application/json")


# Подсказывать непосредственную ссылку
@view_procedures.is_auth
@view_procedures.if_error
def promp_direct_link(request):
    class_manager = Contracts.objects if request.GET['location'] == 'c' else Designer.objects
    object_manager = ContractCells.objects if request.GET['location'] == 'c' else Objects.objects
    class_id = int(request.GET['class_id'])
    col_name = 'system_data' if request.GET['location'] == 'c' else 'Наименование'
    name_id = class_manager.filter(name=col_name, parent_id=class_id)
    if not name_id:
        return HttpResponse('[]', content_type="application/json")
    name_id = name_id[0]
    link_objects = object_manager.filter(parent_structure_id=class_id, name_id=name_id.id)

    if request.GET['user_data']:
        try:
            obj_code = int(request.GET['user_data'])
        except ValueError:
            if request.GET['location'] == 'c':
                link_objects = link_objects.filter(value__datetime_create__icontains=request.GET['user_data'])
            else:
                if is_mysql:
                    link_objects = link_objects.filter(value__icontains=request.GET['user_data'])
                else:
                    user_data = request.GET['user_data'].lower()
                    link_objects = [lo for lo in link_objects if user_data in lo.value.lower()]
        else:
            link_objects = link_objects.filter(code=obj_code)
    else:
        link_objects = link_objects[:10]
    list_objs = []
    for lo in link_objects:
        val = lo.value['datetime_create'] if request.GET['location'] == 'c' else lo.value
        dict_obj = {'code': lo.code, 'value': val}
        list_objs.append(dict_obj)
    result = json.dumps(list_objs, ensure_ascii=False)
    return HttpResponse(result, content_type="application/json")


# Подсказать хозяина для словаря
@view_procedures.is_auth
@view_procedures.if_error
def promp_owner(request):
    dictionary = Dictionary.objects.get(id=int(request.GET['class_id']))
    manager = Objects.objects if dictionary.default == 'table' else ContractCells.objects
    objects = manager.filter(parent_structure_id=dictionary.parent_id)
    objects = objects.filter(name__name__icontains='Наименование') if dictionary.default == 'table'\
        else objects.filter(name__name__icontains='Дата и время записи')
    if request.GET['link']:
        code = 0
        try:
            code = int(request.GET['link'])
        except ValueError:
            pass
        finally:
            if is_mysql:
                objects = objects.filter(Q(code=code) | Q(value__icontains=request.GET['link']))
                result_codes = objects.values('code').distinct()
            else:
                my_link = request.GET['link'].lower()
                result_codes = list(set([o.code for o in objects if o.code == code or my_link in o.value.lower()]))
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
    tom = request.session['temp_object_manager']
    code = int(request.GET['code'])
    dict_loc = {'c': 'contract', 't': 'table', 'd': 'dict'}
    location = dict_loc[request.GET['location']]
    if 'timeline_from' in request.GET and request.GET['timeline_from']:
        try:
            date_from = datetime.datetime.strptime(request.GET['timeline_from'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            date_from = datetime.datetime.strptime(request.GET['timeline_from'], '%Y-%m-%dT%H:%M')
    else:
        date_from = datetime.datetime.today()
    if 'timeline_to' in request.GET and request.GET['timeline_to']:
        try:
            date_to = datetime.datetime.strptime(request.GET['timeline_to'], '%Y-%m-%dT%H:%M:%S') + \
                      datetime.timedelta(seconds=1)
        except ValueError:
            date_to = datetime.datetime.strptime(request.GET['timeline_to'], '%Y-%m-%dT%H:%M') + \
                      datetime.timedelta(seconds=1)
    else:
        date_to = date_from - relativedelta(month=1)
    data = hist_funs.roh(class_id, code, location, date_from, date_to, tom)
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