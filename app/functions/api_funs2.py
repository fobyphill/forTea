import copy
from datetime import datetime, timedelta

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from requests import auth

from app.functions import ajax_funs_2, session_funs, hist_funs, view_procedures, files_funs, reg_funs, object_funs
from app.models import Designer, Objects, Contracts, ContractCells, RegistratorLog, Dictionary, TechProcess


# location = [table, contract, dict, tp]
def get_object_hist(class_id, code,  date_from, date_to=datetime.today(), **params):
    location = params['location'] if 'location' in params else 'contract'
    children = bool(params['children']) if 'children' in params else True
    user_id = 6  # временное решение до оптимизации вызова формул. user_id нигде не используется, но его требует функция вычисления формулы
    if location == 'contract':
        class_manager = Contracts.objects
    elif location == 'table':
        class_manager = Designer.objects
    elif location == 'dict':
        class_manager = Dictionary.objects
    else:
        class_manager = TechProcess.objects
    if date_to < date_from:
        date_to, date_from = date_from, date_to
    current_class = class_manager.filter(id=class_id)
    if not current_class:
        return []
    else:
        current_class = current_class[0]
    name_ids = (15, 13) if current_class.formula == 'tp' else (13, 15, 22)
    three_lines_hist = False
    # для техпроцессов получим первое состояние объекта
    if location == 'tp':
        hist = RegistratorLog.objects.filter(json_class=class_id, json__code=code, reg_name_id__in=name_ids,
                                             date_update__gte=date_from, date_update__lte=date_to)\
            .values('date_update').distinct()
        if hist:
            timeline = [datetime.strftime(h['date_update'], '%Y-%m-%dT%H:%M:%S') for h in hist]
            str_first_date = timeline.pop(0)
            first_date = datetime.strptime(str_first_date, '%Y-%m-%dT%H:%M:%S')
        else:
            first_date = date_to
            str_first_date = datetime.strftime(first_date, '%Y-%m-%dT%H:%M:%S')
            timeline = []
        stages = class_manager.filter(parent_id=class_id).exclude(settings__system=True)
        obj = {'code': code, 'parent_structure': class_id, 'type': 'tp', 'date_update': str_first_date}
        for s in stages:
            hist_stage = RegistratorLog.objects.filter(json_class=class_id, reg_name_id__in=name_ids,
                                                       date_update__lte=first_date + timedelta(seconds=1),
                                                       json__code=code, json__location='contract', json__type='tp',
                                                       json__name=s.id).order_by('-date_update')[:1]
            if hist_stage:
                json_data = hist_stage[0].json
                val = json_data['value']
            else:
                val = {'fact': 0, 'delay': []}
            obj[s.id] = {'value': val}
    else:
        # Получим первое состояние объекта для остальных типов объектов
        if current_class.formula == 'tree':
            path_info = '/tree'
        elif current_class.formula == 'dict':
            path_info = '/dictionary'
        else:
            path_info = '/contract' if location[0] == 'c' else '/manage-object'
        tom = object_funs.get_tom(class_id, user_id, location, path_info)
        # добавим в ТОМ в субконтракты техпроцессы (при наличии оных)
        if tom['current_class']['formula'] == 'contract' and children and 'arrays' in tom:
            sub_tps = TechProcess.objects.filter(parent_id__in=[a['id'] for a in tom['arrays']], formula='tp').values()
            if sub_tps:
                for st in sub_tps:
                    st['cf'] = st['value']['control_field']
                    st['system_params'] = list(TechProcess.objects.filter(parent_id=st['id'],
                                                                          settings__system=True).values())
                    st['stages'] = list(TechProcess.objects.filter(parent_id=st['id'], settings__system=False).values())
                    parent_array = next(a for a in tom['arrays'] if a['id'] == st['parent_id'])
                    if not 'tps' in parent_array:
                        parent_array['tps'] = []
                    parent_array['tps'].append(st)
                three_lines_hist = True
        timeline = [t['date_update'] for t in
                    hist_funs.roh(class_id, code, location, date_from, date_to, tom,
                                  three_levels_hist=three_lines_hist, children=children)['timeline']]
        if timeline:
            str_first_date = timeline.pop(0)
            first_date = datetime.strptime(str_first_date, '%Y-%m-%dT%H:%M:%S')
        else:
            first_date = date_to
            str_first_date = datetime.strftime(first_date, '%Y-%m-%dT%H:%M:%S')
        obj = hist_funs.gov(class_id, code, location, first_date, tom, user_id, children=children, three_levels_hist=three_lines_hist)
        obj['date_update'] = str_first_date

    # Получим остальные состояния объекта
    # Процедура добавления к объекту техпроцесса
    def add_tps_2_obj(parent_object, tps):
        for tp in tps:
            try:
                current_tp = next(t for t in parent_object['new_tps'] if t['id'] == tp['id'])
            except StopIteration:
                current_tp = {'id': tp['id']}
                stages = [{'id': s['id'], 'value': {'delay': [], 'fact': 0}} for s in tp['stages']]
                current_tp['stages'] = stages
                parent_object['new_tps'].append(current_tp)
            hist_tp = RegistratorLog.objects.filter(json_class=tp['id'], json__type='tp', json__code=parent_object['code'],
                                                    date_update__gte=timestamp, date_update__lt=limit_time,
                                                    reg_name_id__in=(13, 15))
            for h_t in hist_tp:
                current_stage = next(s for s in current_tp['stages'] if s['id'] == h_t.json['name'])
                current_stage['value'] = h_t.json['value']

    list_hist = []
    list_hist.append(copy.deepcopy(obj))
    for t in timeline:
        timestamp = datetime.strptime(t, '%Y-%m-%dT%H:%M:%S')
        limit_time = timestamp + timedelta(seconds=1)
        hist = RegistratorLog.objects.filter(json_class=class_id, json__code=code, json__type=current_class.formula,
                                             date_update__gte=timestamp, date_update__lt=limit_time, reg_name_id__in=name_ids)
        for h in hist:
            if location == 'tp':
                data_type = 'value'
            else:
                data_type = 'delay' if h.reg_name_id == 22 else 'value'
            obj[h.json['name']][data_type] = h.json[data_type]
        obj['date_update'] = t

        if current_class.formula in ('table', 'contract') and children:
            # добавим данные о массивах
            if 'arrays' in tom:
                for array in tom['arrays']:
                    owner = next(h for h in array['headers'] if h['name'] == 'Собственник')
                    arrays_codes = RegistratorLog.objects.filter(json_class=array['id'], json__type='array',
                                                               json__name=owner['id'], reg_name_id=13,
                                                                 json__value=obj['code']).values('json')
                    hist_array = RegistratorLog.objects.filter(json_class=array['id'], json__type='array',
                                                               json__code__in=[c['json']['code'] for c in arrays_codes],
                                                               date_update__gte=timestamp, date_update__lt=limit_time,
                                                               reg_name_id__in=(13, 15, 22, 8))
                    current_array = obj[array['id']]['objects']
                    for ha in hist_array:
                        if ha.reg_name_id == 8:
                            obj[array['id']]['objects'] = [ca for ca in current_array if ca['code'] != ha.json['code']]
                        elif ha.reg_name_id == 13:
                            try:
                                new_obj_array = next(ca for ca in current_array if ca['code'] == ha.json['code'])
                            except StopIteration:
                                new_obj_array = {'code': ha.json['code'], 'parent_structure': array['id']}
                                current_array.append(new_obj_array)
                            finally:
                                new_obj_array[ha.json['name']] = {'value': ha.json['value']}
                        else:
                            data_type = 'delay' if ha.reg_name_id == 22 else 'value'
                            current_array_obj = next(ca for ca in current_array if ca['code'] == ha.json['code'])
                            if ha.json['name'] in current_array_obj:
                                current_array_obj[ha.json['name']][data_type] = ha.json[data_type]
                            else:
                                current_array_obj[ha.json['name']] = {data_type: ha.json[data_type]}
                    # добавим техпроцессы третьего уровня
                    if three_lines_hist and array['tps']:
                        for ca in current_array:
                            if not 'new_tps' in ca:
                                ca['new_tps'] = []
                            add_tps_2_obj(ca, array['tps'])
            # добавим словари
            if 'my_dicts' in tom and tom['my_dicts']:
                for my_dict in tom['my_dicts']:
                    hist_dict = RegistratorLog.objects.filter(json_class=my_dict['id'], json__type='dict',
                                                              date_update__gte=timestamp, date_update__lt=limit_time,
                                                              reg_name_id__in=(13, 15, 22, 8))
                    dict_key = 'dict_' + str(my_dict['id'])
                    if not dict_key in obj or not obj[dict_key]:
                        obj[dict_key] = {}
                    for hd in hist_dict:
                        obj[dict_key][hd.json['name']] = {'value': hd.json['value']}

        # добавим техпроцессы
        if current_class.formula in ('contract', 'array') and location == 'contract' and children:
            add_tps_2_obj(obj, tom['tps'])
        list_hist.append(copy.deepcopy(obj))
    return list_hist


# Загрузка файла через апи. Передаваемые переменные: code, header_id, location = [t, c], file
@view_procedures.is_auth
def upload_file(request):
    if 'code' not in request.POST:
        return HttpResponse('Не указан код объекта')
    try:
        code = int(request.POST['code'])
    except ValueError:
        return HttpResponse('Некорректно указан код объекта. Укажите целое число')
    if 'header_id' not in request.POST:
        return HttpResponse('Не указан заголовок реквизита')
    try:
        header_id = int(request.POST['header_id'])
    except ValueError:
        return HttpResponse('Некорректно указан заголовок реквизита. Укажите целое число')
    if not request.FILES:
        return HttpResponse('Не загружен файл')
    is_contract = 'location' in request.POST and request.POST['location'] == 'c'
    if is_contract:
        class_manager = Contracts.objects
        object_manager = ContractCells.objects
    else:
        class_manager = Designer.objects
        object_manager = Objects.objects
    header = class_manager.filter(id=header_id)
    if not header:
        return HttpResponse('Не найден в системе заголовок реквизита - header_id: ' + request.POST['header_id'])
    else:
        header = header[0]
    if header.formula != 'file':
        return HttpResponse('Некорректно задан заголовок реквизита - header_id: ' + request.POST['header_id'] \
                            + '. Необходимо указать тип данных - файл')
    result, file_name, msg = files_funs.upload_file(request, 'file', request.FILES['file'].name, str(header.parent_id),
                                                    is_contract)
    if result == 'o':
        obj = object_manager.filter(name_id=header_id, code=code)
        current_class = class_manager.get(id=header.parent_id)
        full_location = 'contract' if is_contract else 'table'
        if obj:
            obj = obj[0]
            inc = {'class_id': header.parent_id, 'code': code, 'location': full_location, 'type': current_class.formula,
                   'name': header_id, 'id': obj.id, 'value': obj.value}
            obj.value = file_name
            obj.save()
            outc = inc.copy()
            outc['value'] = obj.value
            reg_id = 15
        else:
            new_obj_manager = ContractCells if is_contract else Objects
            obj = new_obj_manager(parent_structure_id=current_class.id, name_id=header_id, code=code, value=file_name)
            obj.save()
            inc = None
            outc = {'class_id': header.parent_id, 'code': code, 'location': full_location, 'type': current_class.formula,
                   'name': header_id, 'id': obj.id, 'value': obj.value}
            reg_id = 13
        timestamp = datetime.today()
        transact_id = reg_funs.get_transact_id(current_class.id, code, full_location[0])
        reg = {'json': outc, 'json_income': inc}
        reg_funs.simple_reg(request.user.id, reg_id, timestamp, transact_id, **reg)
        return HttpResponse('Файл ' + request.FILES['file'].name + ' успешно загружен.')
    else:
        return HttpResponse(msg)



