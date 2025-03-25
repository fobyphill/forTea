import re
import time
from datetime import datetime, timedelta
from functools import reduce
from operator import or_

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Subquery, Q, Value, F, CharField
from django.db.models.fields.json import KeyTextTransform

from app.functions import convert_funs, reg_funs
from app.models import RegistratorLog, ContractCells, TechProcess, TechProcessObjects, DictObjects, Dictionary, \
    Designer, Objects, Contracts


# gov = get object version
def gov(class_id, code, location, timestamp, tom, user_id, **params):
    three_level_hist = bool(params['three_level_hist=False']) if 'three_level_hist=False' in params else False
    children = bool(params['children']) if 'children' in params else True
    timestamp += timedelta(seconds=1)
    base_hist = RegistratorLog.objects.filter(json_class=class_id, json__code=code)
    base_hist = base_hist.filter(json__location=location, json__type=tom['current_class']['formula'])
    base_hist_ppa = base_hist.filter(date_delay__isnull=False, date_delay__lte=timestamp, date_update__gt=timestamp)
    base_hist = base_hist.filter(date_update__lt=timestamp)

    # Функция добавляет техпроцессы в объект
    def add_tps_to_obj(parent_obj, tps):
        objs = []
        for tp in tps:
            obj = {'id': tp['id'], 'stages': []}
            for s in tp['stages']:
                hist = RegistratorLog.objects.filter(json__code=parent_obj['code'], json_class=tp['id'], reg_name_id__in=(13, 15),
                                                     json__type='tp', json__name=s['id'],
                                                     date_update__lt=timestamp).order_by('-id')[:1]
                if hist:
                    delay = hist[0].json['value']['delay']
                    fact = hist[0].json['value']['fact']
                elif tp['stages'].index(s) == 0:
                    control_field = RegistratorLog.objects.filter(json__code=parent_obj['code'], json_class=tom['class_id'],
                                                                  reg_name_id__in=(13, 15),
                                                                  json__type__in=('contract', 'array'),
                                                                  json__name=tp['cf'],
                                                                  date_update__lt=timestamp) \
                                        .order_by('-date_update')[:1]
                    fact = control_field[0].json['value'] if control_field else 0
                    delay = []
                else:
                    fact = 0
                    delay = []
                obj['stages'].append({'id': s['id'], 'value': {'delay': delay, 'fact': fact}})
            objs.append(obj)
        parent_obj['new_tps'] = objs

    # Заполним информацию об объекте
    headers = tom['headers']
    object = {'code': code, 'parent_structure': class_id, 'type': tom['current_class']['formula']}
    for h in headers:
        if h['formula'] != 'eval':
            if h['name'] == 'system_data' and location == 'contract':
                create_sys_data = base_hist.filter(reg_name=13, json__name=h['id']).order_by('id')[:1]
                if create_sys_data:
                    val = create_sys_data[0].json['value']
                else:
                    val = {}
                delay = None
            else:
                hist_prop = base_hist.filter(reg_name_id__in=(13, 15), json__name=h['id']).order_by('-date_update')[:1]
                if hist_prop and 'value' in hist_prop[0].json:
                    val = hist_prop[0].json['value']
                elif h['formula'] == 'bool':
                    val = False
                else:
                    val = None
                if 'delay' in h:
                    if type(h['delay']) is bool and h['delay'] or type(h['delay']) is dict and h['delay']['delay']:
                        hist_delay = base_hist.filter(reg_name_id=22, json__name=h['id']).order_by('-date_update', '-id')[:1]
                        delay = hist_delay[0].json['delay'] if hist_delay else []
                        ppa = base_hist_ppa.filter(reg_name=22, json__name=h['id']).order_by('date_delay', 'id')
                        for p in ppa:
                            new_ppa = p.json['delay'][-1]
                            delay.append(new_ppa)
                    else:
                        delay = None
                else:
                    delay = None
            object[h['id']] = {'type': h['formula'], 'value': val, 'delay': delay}
            if location in ('tp', 'dict'):
                del object[h['id']]['delay']
    # заполним информацию о константах
    is_contract = True if location == 'contract' else False
    convert_funs.prepare_table_to_template([h for h in headers if h['formula'] == 'const'], (object,), user_id,
                                           is_contract)

    # добавим словари
    if 'my_dicts' in tom and tom['my_dicts'] and children:
        for md in tom['my_dicts']:
            dict_id = 'dict_' + str(md['id'])
            object[dict_id] = {}
            for ch in md['children']:
                q_exist = Q(json_class=md['id'], json__type='dict', reg_name_id__in=(13, 15),
                            json__code=code, json__name=ch['id'], date_update__lt=timestamp)
                q_delete = Q(json_class=md['id'], json_income__type='dict', reg_name_id=16, json_income__code=code,
                             json_income__name=ch['id'], date_update__lt=timestamp)
                hist_prop = RegistratorLog.objects.filter(q_exist | q_delete).order_by('-date_update')[:1]
                if hist_prop:
                    if hist_prop[0].reg_name_id == 16:
                        break
                    object[dict_id][ch['id']] = {'type': ch['formula'], 'value': hist_prop[0].json['value'],
                                                 'name': ch['name']}
            if not object[dict_id]:
                object[dict_id] = None

    # добавим массивы
    if 'arrays' in tom and children:
        for a in tom['arrays']:
            object[a['id']] = {'headers': a['vis_headers'], 'objects': []}
            owner = next(h for h in a['headers'] if h['name'] == 'Собственник')
            array_codes = RegistratorLog.objects.filter(reg_name_id=13, json_class=a['id'],
                                                        json__location=location, json__name=owner['id'],
                                                        json__value=code) \
                .annotate(code=KeyTextTransform('code', 'json')).values('code').distinct()
            for ac in array_codes:
                array_obj = {}
                for ah in a['vis_headers']:
                    hist_prop = RegistratorLog.objects.filter(reg_name_id__in=(13, 15), json_class=a['id'],
                                                              json__location=location, json__code=ac['code'],
                                                              date_update__lt=timestamp, json__name=ah['id']) \
                                    .order_by('-date_update')[:1]
                    if hist_prop:
                        array_obj[ah['id']] = {'type': ah['formula'], 'value': hist_prop[0].json['value']}
                if array_obj:
                    array_obj['code'] = ac['code']
                    array_obj['parent_structure'] = a['id']
                    object[a['id']]['objects'].append(array_obj)
                    if three_level_hist and a['tps']:
                        add_tps_to_obj(array_obj, a['tps'])

    # Добавим список с техпроцессами
    if 'tps' in tom and tom['tps'] and children:
        add_tps_to_obj(object, tom['tps'])
    return object


def roh(class_id, code, location, date_from, date_to, tom, **params):
    children = bool(params['children']) if 'children' in params else True
    three_levels_hist = bool(params['three_levels_hist']) if 'three_levels_hist' in params else False

    just_history = False  # Возвращает истину, если массив данных содержит только данные истории,

    base_hist = RegistratorLog.objects.filter(reg_name_id__in=(13, 15, 22), json_class=class_id, json__code=code,
                                              json__type=tom['current_class']['formula'])
    if location in ('table', 'contract'):
        base_hist = base_hist.filter(json__location=location)
    q_hist = list(base_hist.filter(date_update__lte=date_to, date_update__gte=date_from, date_delay__isnull=True).select_related('user')\
                  .values('date_update', 'user__first_name', 'user__last_name').distinct())
    last_date_object = base_hist.order_by('-date_update')[:1]  # последняя запись в истории данного объекта
    if last_date_object and last_date_object[0].date_update > date_to:
        just_history = True
    # добавим делэй ППА
    q_ppa = list(base_hist.filter(date_delay__lte=date_to, date_delay__gte=date_from, date_delay__isnull=False).select_related('user')\
                 .values('date_delay', 'user__first_name', 'user__last_name').distinct())
    for qp in q_ppa:
        new_rec = {'date_update': qp['date_delay'], 'user__first_name': qp['user__first_name'],
                       'user__last_name': qp['user__last_name']}
        if new_rec not in q_ppa:
            q_hist.append(new_rec)

    # Создадим массив с данными словарей, принадлежащих к данному объекту
    last_date_dicts = []
    if location != 'dict' and children:
        for md in tom['my_dicts']:
            query_create_edit = Q(json__type='dict', json__code=code, json_class=md['id'], json__location=location,
                                   reg_name_id__in=(13, 15))
            query_delete = Q(json_income__type='dict', json_income__code=code, json_class=md['id'],
                             json_income__location=location, reg_name_id=8)
            # Современное значение словаря
            list_history_dict_base = RegistratorLog.objects.filter(query_create_edit | query_delete)
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
    if 'arrays' in tom and children:
        for a in tom['arrays']:
            owner = next(h for h in a['headers'] if h['name'] == 'Собственник')
            array_codes = RegistratorLog.objects.filter(reg_name_id=13, json_class=a['id'],
                                                        json__location=location,
                                                        json__name=owner['id'], json__value=code) \
                .annotate(code=KeyTextTransform('code', 'json')).values('code').distinct()
            array_codes = [ac['code'] for ac in array_codes]
            list_hist_arr_base = RegistratorLog.objects.filter(reg_name_id__in=(13, 15), json_class=a['id'],
                                                               json__location=location,
                                                               json__code__in=array_codes)
            list_hist_arr = list_hist_arr_base.filter(date_update__gte=date_from, date_update__lte=date_to) \
                .select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct()
            q_hist += [lha for lha in list_hist_arr if not lha in q_hist]
            if not just_history:
                lha = list_hist_arr_base.order_by('-date_update')[:1]
                if lha and lha[0].date_update > date_to:
                    just_history = True
            # для трехуровневой истории (контракт / субконтракт / техпроцесс)
            if three_levels_hist and location == 'contract':
                sub_tps_ids = [t['id'] for t in a['tps']]
                list_hist_sub_tps_base = RegistratorLog.objects.filter(reg_name_id__in=(13, 15),
                                                                       json_class__in=sub_tps_ids,
                                                                       json__type='tp', json__code__in=array_codes)
                if not just_history:
                    lhst = list_hist_sub_tps_base.order_by('-date_update')[:1]
                    if lhst and lhst[0].date_update > date_to:
                        just_history = True
                    list_hist_sub_tps = list_hist_sub_tps_base.filter(date_update__gte=date_from, date_update__lte=date_to) \
                        .select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct()
                    q_hist += [lhst for lhst in list_hist_sub_tps if not lhst in q_hist]

    # ДОбавим список с техпроцессами
    if 'tps' in tom and tom['tps'] and children:
        for tp in tom['tps']:
            list_hist_tp_base = RegistratorLog.objects.filter(reg_name_id=15, json_class=tp['id'],
                                                              json__location=location, json__code=code, json__type='tp')
            lht = list_hist_tp_base.order_by('-date_update')[:1]
            if lht:
                if not just_history and lht[0].date_update > date_to:
                    just_history = True
            list_hist_tp = list_hist_tp_base.filter(date_update__gte=date_from, date_update__lte=date_to) \
                .select_related('user').values('date_update', 'user__first_name', 'user__last_name').distinct()
            q_hist += [lht for lht in list_hist_tp if not lht in q_hist]

    # Избавимся от нативной даты-времени
    timeline = []
    for qh in q_hist:
        du = datetime.strftime(qh['date_update'], '%Y-%m-%dT%H:%M:%S')
        if du not in [t['date_update'] for t in timeline]:
            user = qh['user__first_name'] + ' ' + qh['user__last_name']
            timeline.append({'date_update': du, 'user': user})
    timeline.sort(key=lambda x: x['date_update'])

    return {'just_history': just_history, 'timeline': timeline}


# чистит выбранный объект в указанный период, собирает последние изменения об объекте и помещает их в последний момент
# времени периода - date_to. Можно указывать объекты типов - справочник, контракт, массив, дерево
# loc = [t, c]
def clean_object_hist(class_id, code, loc, date_from, date_to):
    try:
        class_manager = Contracts.objects if loc == 'c' else Designer.objects
        current_class = class_manager.filter(id=class_id)
        if current_class:
            current_class = current_class[0]
        else:
            full_clean_hist(class_id, code, loc, date_from, date_to)
            return False
        headers = class_manager.filter(parent_id=class_id, system=False)
        dict_location = {'t': 'table', 'c': 'contract'}
        def do_cleaning(current_class, headers, db_loc):
            if db_loc != 'p':
                hist_del = RegistratorLog.objects.filter(json_class=current_class.id, json_income__code=code,
                                                      json_income__location=dict_location[loc], reg_name_id=8,
                                                      date_update__lte=date_to, json_income__type=current_class.formula).values('id')
            else:
                hist_del = None
            copatrids  = []  # contract parent transact ids
            tapatrids = []
            list_regs = []
            if not hist_del:
                transact_id = reg_funs.get_transact_id(current_class.id, code, db_loc)
                base_inc = {'class_id': current_class.id, 'location': dict_location[loc], 'code': code, 'type': current_class.formula}
                query_set = ''
                str_date_to = datetime.strftime(date_to, '%Y-%m-%dT%H:%M:%S')
                header_counter = 1
                # Собираем данные для запроса
                for h in headers:
                    query_set += f'''(select * from app_registratorlog where date_update <="{str_date_to}" and 
                    json_class = {current_class.id} and reg_name_id in (13, 15) and json_extract(json, "$.code") = {code} 
                    and json_extract(json, "$.name") = {h.id} order by date_update desc limit 1)'''
                    if header_counter < len(headers):
                        query_set += ' union '
                    header_counter += 1
                last_hist_object = RegistratorLog.objects.raw(query_set)
                # Сохраним последнюю версию объекта
                for h in headers:
                    try:
                        last_hist_val = next(lho for lho in last_hist_object if lho.json['name'] == h.id)
                    except StopIteration:
                        continue
                    inc = base_inc.copy()
                    inc['name'] = h.id
                    outc = inc.copy()
                    inc['value'] = last_hist_val.json_income['value'] if last_hist_val.reg_name_id == 15 else None
                    outc['value'] = last_hist_val.json['value']
                    reg = {'json': outc, 'json_income': inc}
                    hist_rec = {'user_id': 1, 'reg_id': 15, 'timestamp': date_to, 'transact_id': transact_id, 'reg': reg}
                    list_regs.append(hist_rec)
                    if db_loc == 'p':
                        if last_hist_val.parent_transact_id:
                            if last_hist_val.parent_transact_id[:1] == 'c':
                                copatrids.append(last_hist_val.parent_transact_id)
                            elif last_hist_val.parent_transact_id[:4] == 'task':
                                tapatrids.append(re.match(r'(task\d+)', last_hist_val.parent_transact_id)[1])
            # Удалим изменения, имевшие место в заданый период
            RegistratorLog.objects.filter(json_class=current_class.id, json__code=code, date_update__gte=date_from,
                                          date_update__lte=date_to, json__location=dict_location[loc],
                                          reg_name_id__in=[13, 15, 22], json__type=current_class.formula).delete()
            if not hist_del:
                reg_funs.paket_reg(list_regs)
            # для тпсов найдем таски - stage
            if db_loc == 'p':
                task_hist_base = RegistratorLog.objects.filter(reg_name_id__in=(17, 18, 19, 20, 21), date_update__lte=date_to,
                                                               date_update__gt=date_from)
                if copatrids:
                    transact_ids = task_hist_base.filter(parent_transact_id=copatrids).values('transact_id').distinct()
                    tapatrids += [re.match(r'(task\d+)id', ti['transact_id'])[1] for ti in transact_ids]
                    if tapatrids:
                        tapatrids = list(set(tapatrids))
                        query = reduce(or_, (Q(transact_id__startswith=t) for t in tapatrids))
                        task_hist_base.filter(query).delete()

        # Чистим объект
        do_cleaning(current_class, headers, loc)
        # Если у объекта есть словари
        if current_class.formula in ('table', 'contract'):
            my_dicts = Dictionary.objects.filter(parent_id=class_id, formula='dict', default=dict_location[loc])
            for myd in my_dicts:
                dict_headers = Dictionary.objects.filter(parent_id=myd.id)
                do_cleaning(myd, dict_headers, 'd')
        # Если у объекта есть техпроцессы
        if loc == 'c' and current_class.formula in ('contract', 'array'):
            my_tps = TechProcess.objects.filter(parent_id=class_id, formula='tp')
            for myt in my_tps:
                tp_headers = TechProcess.objects.filter(parent_id=myt.id, settings__system=False)
                do_cleaning(myt, tp_headers, 'p')
    except Exception as ex:
        return str(ex)
    else:
        return True


def get_all_objs(date_from, date_to, **params):
    types = ['tree', 'array']
    if 'loc' in params:
        if params['loc'] == 'c':
            types.append('contract')
        else:
            types.append('table')
    else:
        types += ['table', 'contract']

    all_objs = RegistratorLog.objects.filter(date_update__gte=date_from, date_update__lte=date_to,
                                             reg_name_id__in=[13, 15], json__type__in=types)
    if 'loc' in params:
        location = 'contract' if params['loc'] == 'c' else 'table'
        all_objs = all_objs.filter(json__location=location)
    if 'class_id' in params:
        all_objs = all_objs.filter(json_class=params['class_id'])
    all_objs = all_objs.annotate(code=F('json__code')).annotate(location=F('json__location')).values('json_class', 'code', 'location')\
        .distinct().order_by('location', 'json_class', 'code')
    return list(all_objs)


# Удаление сведений об объекте, если был удален класс данного объекта
def full_clean_hist(class_id, code, loc, date_from, date_to):
    types = ['tree', 'array']
    if loc == 'c':
        types.append('contract')
        location = 'contract'
    else:
        types.append('table')
        location = 'table'
    hist = RegistratorLog.objects.filter(date_update__gt=date_from, date_update__lte=date_to, json_class=class_id)
    q_code = Q(json__code=code) | Q(json_income__code=code)
    q_loc = Q(json__location=location) | Q(json_income__location=location)
    q_types = Q(json__type__in=types) | Q(json_income__types__in=types)
    hist = hist.filter(q_loc, q_code, q_types)
    hist.delete()


def clean_objects_wo_code(class_id, loc):
    types = ['tree', 'array']
    if loc == 'c':
        types.append('contract')
        location = 'contract'
    else:
        types.append('table')
        location = 'table'
    hist = RegistratorLog.objects.filter(json_class=class_id, reg_name__in=[13, 15])
    hist_to_del = []
    for h in hist:
        if 'code' not in h.json:
            hist_to_del.append(h.id)
    RegistratorLog.objects.filter(id__in=hist_to_del).delete()






