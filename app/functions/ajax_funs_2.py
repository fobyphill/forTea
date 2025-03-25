import re
from datetime import datetime, timedelta
import json
import operator
from functools import reduce

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db.models.fields.json import KeyTextTransform
from django.forms import model_to_dict
from django.http import HttpResponse

import app.functions.contract_funs
import app.functions.interface_procedures
from app.functions import view_procedures, interface_funs, convert_funs, session_funs, contract_funs, hist_funs, \
    convert_procedures, convert_funs2
from app.models import TableDrafts, Designer, ContractDrafts, Contracts, ContractCells, Objects, TechProcess, \
    RegistratorLog, TechProcessObjects, DictObjects, Dictionary, MainPageConst
from django.contrib.auth import get_user_model
from app.other.global_vars import is_mysql


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
        if is_mysql:
            q = Q(id=user_id) | reduce(operator.or_, (Q(username__icontains=x) | Q(first_name__icontains=x) |
                                                      Q(last_name__icontains=x) for x in user_data))
            recepients = list(User.objects.filter(q).values('id', 'username', 'first_name', 'last_name'))
        else:
            user_data = user_data.lower()
            recepients = [u for u in User.objects.all().values('id', 'username', 'first_name', 'last_name') \
                          if u['id'] == user_id or user_data in u['username'].lower() \
                          or user_data in u['first_name'].lower() or user_data in u['last_name'].lower()]
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
        biz_rule = next(sh for sh in request.session['temp_object_manager']['system_headers'] if sh['name'] == 'business_rule')
    else:
        headers = Contracts.objects.filter(parent_id=class_id, system=False).values()
        biz_rule = Contracts.objects.filter(parent_id=class_id, name='business_rule').values()[0]
    my_tps = request.session['temp_object_manager']['tps'] if 'tps' in request.session['temp_object_manager'] else None
    old_obj = ContractCells.objects.filter(parent_structure_id=class_id, code=code)
    presaved_object = app.functions.interface_procedures.mofr(code, class_id, headers, request.GET, old_obj, True, tps=my_tps)
    result = app.functions.contract_funs.do_business_rule(biz_rule, presaved_object, request.user.id)
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error
# gc4lp = get classes for link promp
def gc4lp(request):
    manager = Contracts.objects if request.GET['class_type'] == 'contract' else Designer.objects
    base_classes = manager.filter(formula=request.GET['class_type'])
    if request.GET['class_val']:
        if is_mysql:
            classes = base_classes.filter(name__icontains=request.GET['class_val']).values('id', 'name')
            try:
                class_id = int(request.GET['class_val'])
            except ValueError:
                pass
            else:
                classes = list(classes.union(base_classes.filter(id=class_id).values('id', 'name')))
        else:
            class_id = 0
            try:
                class_id = int(request.GET['class_val'])
            except ValueError:
                pass
            val = request.GET['class_val'].lower()
            classes = [bc for bc in base_classes.values('id', 'name') if bc['id'] == class_id or val in bc['name'].lower()]
    else:
        classes = list(base_classes.values('id', 'name')[:10])
    return HttpResponse(json.dumps(classes, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error_json
# gon4d = get objects names for dicts
def gon4d(request):
    is_contract = True if request.GET['link_type'] == 'contract' else False
    manager = ContractCells.objects if is_contract else Objects.objects
    req_field = 'system_data' if is_contract else 'Наименование'
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
    if is_contract:
        objs = [{'code': o['code'], 'value': o['value']['datetime_create']} for o in objs]
    else:
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
    object = convert_funs.queryset_to_object(object)
    is_contract = True if request.GET['location'] == 'c' else False
    if 'arrays' in tom and tom['arrays']:
        convert_funs2.aato(tom['arrays'], object[0], request.user.id)
    formula_array_headers = [h for h in tom['headers'] if h['formula'] == 'eval']
    convert_funs.prepare_table_to_template(formula_array_headers, object, request.user.id, is_contract, tps4arrays=True)
    if 'my_dicts' in tom and tom['my_dicts']:
        convert_funs.add_dicts(object, tom['my_dicts'])
    if 'tps' in tom:
        object[0]['new_tps'] = app.functions.interface_procedures.get_new_tps(code, tom['tps'])
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
    timestamp = datetime.strptime(request.GET['timestamp'], '%Y-%m-%dT%H:%M:%S')
    user_id = request.user.id
    object = hist_funs.gov(class_id, code, location, timestamp, tom, user_id)
    # Если в объекте есть массив - то причешем его поля-ссылки
    is_contract = (location == 'contract')
    for obj_k, obj_v in object.items():
        if obj_k in ('code', 'parent_structure', 'type'):
            continue
        if type(obj_v) is dict and 'headers' in obj_v:
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
    object = convert_funs.queryset_to_object(object)
    result = contract_funs.do_business_rule(cc, object[0], request.user.id)
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


# gaff = get all float fields
@view_procedures.is_auth
@view_procedures.if_error_json
def gaff(request):
    class_params = list(Contracts.objects.filter(parent_id=int(request.GET['class_id']), system=False, formula='float').values('id', 'name'))
    return HttpResponse(json.dumps(class_params, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
@view_procedures.if_error_json
def calc_user_formula(request):
    list_params = json.loads(request.POST['list_params'])
    const_id = int(request.POST['const_id'])
    is_contract = (request.POST['is_contract'] == 'true')
    manager = Contracts.objects if is_contract else Designer.objects
    our_const = manager.get(id=const_id)
    our_const = model_to_dict(our_const)
    for lp in list_params:
        if type(lp['value']) is list:
            lp['value'] = str(lp['value'])
        our_const['value'] = re.sub(r'\[\[\s*\n*\s*user_data_' + lp['id'] + r'\D{1}.*?\]\]', lp['value'],
                                    our_const['value'], flags=re.DOTALL)
        if lp['value'][:17] == "datetime.strptime":
            our_const['value'] = 'from datetime import datetime\n' + our_const['value']
    code = int(request.POST['code']) if 'code' in request.POST else 0
    obj = {'parent_structure': our_const['parent'], 'code': code}
    convert_funs.deep_formula(our_const, (obj, ), request.user.id, is_contract)
    return HttpResponse(json.dumps(obj[our_const['id']]['value'], ensure_ascii=False), content_type="application/json")


# cmpf = calc main page formula
@view_procedures.if_error_json
def cmpf(request):
    list_params = json.loads(request.GET['list_params'])
    const_id = int(request.GET['const_id'])
    our_const = MainPageConst.objects.get(id=const_id)
    our_const = model_to_dict(our_const)
    if not request.user.id and our_const['user_login']:
        result = ''
    else:
        for lp in list_params:
            our_const['value'] = re.sub(r'\[\[\s*\n*\s*user_data_' + lp['id'] + '\D{1}[\w\W]*?\]\]', lp['value'],
                                        our_const['value'], flags=re.M)
        convert_funs.deep_formula(our_const, (our_const, ), request.user.id)
        result = our_const[our_const['id']]['value']
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
def uch(request):
    header_id = int(request.GET['header_id'])
    manager = Contracts.objects if request.GET['loc'] == 'c' else Designer.objects
    header = manager.get(id=header_id)
    child_manager = Contracts.objects if header.value[0] == 'c' else Designer.objects
    const_id = re.search(r'(?:contract|table)\.(\d+)', header.value)[1]
    const = list(child_manager.filter(parent_id=int(const_id)).values('id', 'name'))
    return HttpResponse(json.dumps(const, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
def draft_link(request):
    val = request.GET['value']
    is_contract = request.GET['is_contract'] == 'true'
    class_manager = Contracts.objects if is_contract else Designer.objects
    current_class = class_manager.get(id=int(request.GET['class_id']))
    headers = list(class_manager.filter(parent_id=current_class.parent_id, system=False).values('id', 'name', 'formula'))
    object_manager = ContractDrafts.objects if is_contract else TableDrafts.objects
    objs = object_manager.filter(data__parent_structure=current_class.parent_id, user_id=request.user.id)
    try:
        parent_id = int(request.GET['value'])
    except ValueError:
        parent_id = None
    if parent_id:
        objs = objs.filter(id=parent_id)
    result = []
    for o in objs:
        dict_res = {'id': o.id, 'timestamp': datetime.strftime(o.timestamp, '%d.%m.%Y %H:%M:%S')}
        object_filtred = False
        data = ''
        for dk, dv in o.data.items():
            if dk == 'code':
                data += 'Код: ' + str(dv)
                continue
            elif dk in ('parent_structure', 'branch') or 'dict' in dk:
                continue
            header = next(h for h in headers if h['id'] == int(dk))
            str_dv = convert_procedures.cdtts(dv['value'], header['formula'])
            if str_dv:
                if header['formula'] == 'string' and type(str_dv) is str:
                    str_dv = '\'' + str_dv + '\''
                if header['name'] == 'system_data':
                    if str_dv['datetime_create']:
                        data += ' от ' + str_dv['datetime_create']
                else:
                    data += ' ' + header['name'] + ': ' + str_dv
            if parent_id:
                object_filtred = True
            elif type(dv['value']) is str and val.lower() in dv['value'].lower():
                object_filtred = True
        dict_res['data'] = data
        if object_filtred:
            result.append(dict_res)
    return HttpResponse(json.dumps(result, ensure_ascii=False), content_type="application/json")


@view_procedures.is_auth
def get_tps(request):
    array_id = int(request.GET['array_id'])
    array_codes = json.loads(request.GET['array_codes'])
    my_tps = []
    tps = TechProcess.objects.filter(parent_id=array_id)
    timestamp = request.GET['timestamp'] if request.GET['timestamp'] == 'now' else\
        datetime.strptime(request.GET['timestamp'], '%Y-%m-%dT%H:%M:%S') + timedelta(seconds=1)
    for t in tps:
        tp_objects = []
        stages = list(TechProcess.objects.filter(parent_id=t.id, settings__system=False, settings__visible=True).values())
        my_tp = {s['id']: s['name'] for s in stages}
        my_tp['id'] = t.id
        my_tp['name'] = t.name
        for ac in array_codes:
            tp_object = {'code': ac}
            if request.GET['timestamp'] == 'now':
                q_tp = TechProcessObjects.objects.filter(parent_structure_id=t.id, parent_code=ac)
                for q in q_tp:
                    val = q.value['fact'] + sum(d['value'] for d in q.value['delay'])
                    tp_object[q.name_id] = val
            else:
                tp_object = {'code': ac}
                for s in stages:
                    hist = RegistratorLog.objects.filter(json__type='tp', reg_name__in=(13, 15), json__name=s['id'],
                                                         json_class=t.id, json__code=ac,
                                                         date_update__lte=timestamp).order_by('-date_update')[:1]
                    if hist:
                        value = hist[0].json['value']
                        val = value['fact'] + sum(d['value'] for d in value['delay'])
                    else:
                        val = 0
                    tp_object[s['id']] = val
            tp_objects.append(tp_object)
        my_tp['objects'] = tp_objects
        my_tps.append(my_tp)
    return HttpResponse(json.dumps(my_tps, ensure_ascii=False), content_type="application/json")

