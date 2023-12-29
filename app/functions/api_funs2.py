import copy
from datetime import datetime

from app.functions import ajax_funs_2, session_funs, hist_funs
from app.models import Designer, Objects, Contracts, ContractCells, RegistratorLog, Dictionary, TechProcess


def get_object_hist(class_id, code,  date_from, date_to=datetime.today(), **params):
    location = params['location'] if 'location' in params else 'c'
    user_id = 6  # временное решение до оптимизации вызова формул. user_id нигде не используется, но его требует функция вычисления формулы
    if location == 'c':
        class_manager = Contracts.objects
        # object_manager = ContractCells.objects
    elif location == 't':
        class_manager = Designer.objects
        # object_manager = Objects.objects
    elif location == 'd':
        class_manager = Dictionary.objects
    else:
        class_manager = TechProcess.objects

    current_class = class_manager.get(id=class_id)
    # для техпроцессов получим первое состояние объекта
    if location == 'p':
        stages = class_manager.get(parent_id=class_id, name='stages')
        object = {'code': code, 'parent_structure': class_id, 'type': 'techprocess', stages.id: []}
        for s in stages.value:
            hist_stage = RegistratorLog.objects.filter(json_class=class_id, reg_name_id=15, date_update__lt=date_from,
                                                       json__code=code, json__location='contract', json__type='techprocess',
                                                       json__vale__stage=s).order_by('-date_update')[:1]
            if hist_stage:
                json_data = hist_stage[0].json_data
                object[json_data['name']].append(json_data['value'])
            else:
                val = {'fact': 0, 'delay': [], 'stage': s}
                if stages.value.index(s) == 0:
                    parent_contract_cf = ContractCells.objects.get(parent_structure_id=current_class.parent_id, code=code,
                                                                   name_id=current_class.value['control_field'])
                    val['fact'] = parent_contract_cf.value
                object[stages.id].append(val)
    else:
    # Получим первое состояние объекта для остальных типов объектов
        if current_class.formula == 'tree':
            path_info = '/tree'
        elif current_class.formula == 'dict':
            path_info = '/dictionary'
        else:
            path_info = '/contract' if location == 'c' else '/manage-object'


        class ReqUser:
            id = 0
        class Request:
            GET = dict()
            session = dict()
            path = path_info
            user = ReqUser()
        sr = Request()  #sr - subrequest
        sr.GET['class_id'] = class_id
        sr.GET['code'] = code
        sr.user.id = user_id
        if current_class.formula in ('table', 'contract', 'dict'):
            location = current_class.formula
        elif current_class.formula == 'tree':
            pass
        elif location == 'c':
            location = 'contract'
        elif location == 'd':
            location = 'dict'
        else:
            location = 'table'
        sr.GET['location'] = location
        sr.GET['timestamp'] = datetime.strftime(date_from, '%Y-%m-%dT%H:%M:%S')
        session_funs.update_omtd(sr)
        tom = sr.session['temp_object_manager']
        object = hist_funs.gov(class_id, code, location, date_from, tom, user_id)

        # Временно! Почистим все дочерние объекты данного объекта
        if current_class.formula in ('table', 'contract'):
            # чистим словари и массивы
            for k, v in list(object.items()):
                if type(k) is str and len(k) > 5 and k[:5] == 'dict_':
                    del object[k]
                elif 'headers' in v:
                    del object[k]
        # чистим техпроцессы
        if 'tps' in object:
            del object['tps']

    # Получим остальные состояния объекта
    list_hist = []
    name_ids = (15, ) if current_class.formula == 'techprocess' else (13, 15, 22)
    hist = RegistratorLog.objects.filter(json_class=class_id, json__code=code, json__type=current_class.formula,
                                         date_update__gte=date_from, reg_name_id__in=name_ids,
                                         date_update__lte=date_to).order_by('date_update')
    if not hist:
        return list()
    transact_id = hist[0].transact_id
    date_update = datetime.strftime(hist[0].date_update, '%Y-%m-%dT%H:%M:%S')
    is_change = False
    for h in hist:
        if transact_id != h.transact_id:
            object['date_update'] = date_update
            object['transact_id'] = transact_id
            date_update = datetime.strftime(h.date_update, '%Y-%m-%dT%H:%M:%S')
            if is_change:
                list_hist.append(copy.deepcopy(object))
            is_change = False
            transact_id = h.transact_id
        if not h.json['name'] in object:
            continue
        if 'delay' in h.json:
            object[h.json['name']]['delay'] = h.json['delay']
            is_change = True
        elif 'value' in h.json:
            if current_class.formula == 'techprocess':
                current_stage = next(s for s in object[h.json['name']] if s['stage'] == h.json['value']['stage'])
                current_stage['fact'] = h.json['value']['fact']
                current_stage['delay'] = h.json['value']['delay']
            else:
                object[h.json['name']]['value'] = h.json['value']
            is_change = True
    object['date_update'] = date_update
    object['transact_id'] = transact_id
    if is_change:
        list_hist.append(object)
    return list_hist