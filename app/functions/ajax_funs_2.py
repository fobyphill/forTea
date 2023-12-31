from datetime import datetime, timedelta
import json
import operator
from functools import reduce

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db.models.fields.json import KeyTextTransform
from django.http import HttpResponse

import app.functions.contract_funs
import app.functions.interface_procedures
from app.functions import view_procedures, interface_funs, convert_funs, session_funs, contract_funs, hist_funs
from app.models import TableDrafts, Designer, ContractDrafts, Contracts, ContractCells, Objects, TechProcess, \
    RegistratorLog, TechProcessObjects, DictObjects, Dictionary
from django.contrib.auth import get_user_model


@view_procedures.is_auth
@view_procedures.if_error
def retreive_draft_versions(request):
    try:
        class_id = int(request.GET['class_id'])
        code = int(request.GET['code']) if request.GET['code'] else None
        all_drafts = TableDrafts.objects.filter(user_id=request.user.id, data__parent_structure=class_id,
                                                data__code=code).order_by('timestamp')
        all_drafts = all_drafts.select_related('user')

        json_object = {}
        json_object['code'] = code
        json_object['class_id'] = class_id
        json_object['timestamp'] = all_drafts[len(all_drafts) - 1].timestamp.strftime('%Y-%m-%d-%H-%M-%S')
        events = []
        json_object['events'] = events

        # Зададим стартовое состояние объекта
        header = Designer.objects.filter(parent_id=class_id).exclude(formula='eval').values('id')
        # зададим массив времени
        time_line = []
        if all_drafts:
            for ad in all_drafts:
                event = {}
                time_line.append(ad.timestamp.strftime('%Y-%m-%d %H:%M:%S'))
                for k, v in ad.data.items():
                    if k not in ('code', 'parent_structure'):
                        event[int(k)] = v['value']
                events.append(event)

        data = {}
        data['object'] = json_object
        data['time_line'] = time_line
        data['dicts'] = []
    except Exception as ex:
        data = str(ex)
    return HttpResponse(json.dumps(data, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error
def retreive_object_drafts(request):
    class_id = int(request.GET['class_id'])
    code = int(request.GET['code'])
    manager = TableDrafts.objects  if request.GET['location'] == 'table' else ContractDrafts.objects
    drafts = list(manager.filter(user_id=request.user.id, data__parent_structure=class_id,
                                             data__code=code).values())
    for d in drafts:
        d['timestamp'] = d['timestamp'].strftime('%d.%m.%Y %H:%M:%S')
    drafts = [d for d in drafts]
    return HttpResponse(json.dumps(drafts, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error
def get_users(request):
    User = get_user_model()
    user_data = request.GET['user_data']
    if user_data:
        try:
            user_id = int(request.GET['user_data'])
        except ValueError:
            user_id = None
            user_data = user_data.split(' ')
        else:
            user_data = (user_data, )
        q = Q(id=user_id) | reduce(operator.or_, (Q(username__icontains=x) | Q(first_name__icontains=x) |
                                                  Q(last_name__icontains=x) for x in user_data))
        recepients = list(User.objects.filter(q).values('id', 'username', 'first_name', 'last_name'))
    else:
        recepients = list(User.objects.filter(is_active=True).values('id', 'username', 'first_name', 'last_name'))[:10]
    return HttpResponse(json.dumps(recepients, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error
def get_user_by_id(request):
    User = get_user_model()
    result = {}
    try:
        user_id = int(request.GET['user_id'])
    except:
        result['error'] = 'Некорректно указан ID пользователя. Укажите целое число'
    else:
        try:
            user = User.objects.get(id=user_id)
        except ObjectDoesNotExist:
            result['error'] = 'Некорректно указан ID пользователя системы. Пользователь не найден'
        else:
            result = {'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error
def get_business_rule(request):
    code = int(request.GET['i_code']) if request.GET['i_code'] else None
    class_id = int(request.GET['class_id'])
    if class_id == int(request.session['temp_object_manager']['class_id']):
        headers = request.session['temp_object_manager']['headers']
    else:
        excl_names = ('business_rule', 'link_map', 'trigger')
        headers = Contracts.objects.filter(parent_id=class_id).exclude(name__in=excl_names).values()
    biz_rule = Contracts.objects.filter(parent_id=class_id, name='business_rule').values()[0]
    my_tps = request.session['temp_object_manager']['my_tps'] if 'my_tps' in request.session['temp_object_manager'] else None
    old_obj = ContractCells.objects.filter(parent_structure_id=class_id, code=code)
    presaved_object = app.functions.interface_procedures.mofr(code, class_id, headers, request.GET, old_obj, True)
    result = app.functions.contract_funs.do_business_rule(biz_rule, presaved_object, request.user.id)
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error
# gc4lp = get classes for link promp
def gc4lp(request):
    manager = Contracts.objects if request.GET['class_type'] == 'contract' else Designer.objects
    if request.GET['class_val']:
        classes = manager.filter(name__icontains=request.GET['class_val'], formula=request.GET['class_type'])
        try:
            class_id = int(request.GET['class_val'])
        except ValueError:
            pass
        else:
            classes = classes.union(manager.filter(id=class_id, formula=request.GET['class_type']))
    else:
        classes = manager.filter(formula=request.GET['class_type'])[:10]
    classes = list(classes.values('id', 'name'))
    return HttpResponse(json.dumps(classes, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error_json
# gon4d = get objects names for dicts
def gon4d(request):
    is_contract = True if request.GET['link_type'] == 'contract' else False
    manager = ContractCells.objects if is_contract else Objects.objects
    req_field = 'Дата и время записи' if is_contract else 'Наименование'
    objs = manager.filter(name__name=req_field, parent_structure_id=request.GET['link_id']).values('code', 'value')
    if request.GET['code']:
        try:
            code = int(request.GET['code'])
        except ValueError:
            objs = objs.filter(code=0)
        else:
            objs = objs.filter(code=code)
    else:
        objs = objs[:10]
    objs = list(objs)
    return HttpResponse(json.dumps(objs, ensure_ascii=False), content_type="application/json")


# gfob = get full object
@view_procedures.is_auth
@view_procedures.if_error_json
def gfob(request):
    tom = request.session['temp_object_manager']
    class_id = int(request.GET['class_id'])
    code = int(request.GET['code'])
    object_manager = ContractCells.objects if request.GET['location'] == 'c' else Objects.objects if \
        request.GET['location'] == 't' else DictObjects.objects
    object = object_manager.filter(parent_structure_id=class_id, code=code)
    object = convert_funs.queyset_to_object(object)
    is_contract = True if request.GET['location'] == 'c' else False
    formula_array_headers = [h for h in tom['headers'] if h['formula'] in ('array', 'eval')]
    convert_funs.prepare_table_to_template(formula_array_headers, object, request.user.id, is_contract)
    if 'my_dicts' in tom and tom['my_dicts']:
        convert_funs.add_dicts(object, tom['my_dicts'])
    if 'tps' in tom:
        object[0]['new_tps'] = interface_funs.get_new_tps(code, tom['tps'])
    return HttpResponse(json.dumps(object[0], ensure_ascii=False), content_type="application/json")


# gov = get object version
@view_procedures.is_auth
@view_procedures.if_error_json
def gov(request):
    session_funs.update_omtd(request)
    tom = request.session['temp_object_manager']
    class_id = int(request.GET['class_id'])
    code = int(request.GET['code'])
    location = 'contract' if request.GET['location'] == 'c' else 'table' if request.GET['location'] == 't' else 'dict'
    timestamp = datetime.strptime(request.GET['timestamp'], '%Y-%m-%dT%H:%M:%S') + timedelta(seconds=1)
    user_id = request.user.id
    object = hist_funs.gov(class_id, code, location, timestamp, tom, user_id)
    # Если в объекте есть массив - то причешем его поля-ссылки
    is_contract = (location == 'contract')
    for obj_k, obj_v in object.items():
        if obj_k in ('code', 'parent_structure', 'type'):
            continue
        if 'headers' in obj_v:
            headers = [h for h in obj_v['headers'] if h['formula'] == 'link']
            if headers:
                convert_funs.prepare_table_to_template(headers, obj_v['objects'], user_id, is_contract)
    return HttpResponse(json.dumps(object, ensure_ascii=False), content_type="application/json")


# выполнить формулу "Условие выполнения контракта"
@view_procedures.is_auth
@view_procedures.if_error_json
def do_cc(request):
    class_id = int(request.GET['class_id'])
    code = int(request.GET['code'])
    cc = list(Contracts.objects.filter(parent_id=class_id, name='completion_condition').values())[0]
    object = ContractCells.objects.filter(parent_structure_id=class_id, code=code)
    object = convert_funs.queyset_to_object(object)
    result = contract_funs.do_business_rule(cc, object[0], request.user.id)
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


# gaff = get all float fields
@view_procedures.is_auth
@view_procedures.if_error_json
def gaff(request):
    class_params = list(Contracts.objects.filter(parent_id=int(request.GET['class_id']), system=False, formula='float').values('id', 'name'))
    return HttpResponse(json.dumps(class_params, ensure_ascii=False), content_type="application/json")