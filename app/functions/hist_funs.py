from datetime import datetime, timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Subquery
from django.db.models.fields.json import KeyTextTransform

from app.functions import convert_funs
from app.models import RegistratorLog, ContractCells, TechProcess


# gov = get object version
def gov(class_id, code, location, timestamp, tom, user_id, **params):
    three_level_hist = bool(params['three_level_hist=False']) if 'three_level_hist=False' in params else False
    children = bool(params['children']) if 'children' in params else True
    timestamp += timedelta(seconds=1)
    base_hist = RegistratorLog.objects.filter(json_class=class_id, json__code=code, date_update__lt=timestamp)
    if location in ('table', 'contract'):
        base_hist = base_hist.filter(json__location=location)
    elif location == 'dict':
        base_hist = base_hist.filter(json__type='dict')

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
                try:
                    sys_data_now = ContractCells.objects.get(parent_structure_id=class_id, code=code, name_id=h['id'])
                except ObjectDoesNotExist:
                    return {}
                val = sys_data_now.value
                delay = None
            else:
                hist_prop = base_hist.filter(reg_name_id__in=(13, 15), json__name=h['id']).order_by('-date_update')[:1]
                val = hist_prop[0].json['value'] if hist_prop and 'value' in hist_prop[0].json else None
                if 'delay' in h:
                    if type(h['delay']) is bool and h['delay'] or type(h['delay']) is dict and h['delay']['delay']:
                        hist_delay = base_hist.filter(reg_name_id=22, json__name=h['id']).order_by('-date_update', '-id')[:1]
                        delay = hist_delay[0].json['delay'] if hist_delay else None
                    else:
                        delay = None
                else:
                    delay = None
            object[h['id']] = {'type': h['formula'], 'value': val, 'delay': delay}
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
                hist_prop = RegistratorLog.objects.filter(json_class=md['id'], json__type='dict',
                                                          reg_name_id__in=(13, 15),
                                                          json__parent_code=code, json__name=ch['id'],
                                                          date_update__lt=timestamp).order_by('-date_update')[:1]
                if hist_prop:
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

    base_hist = RegistratorLog.objects.filter(reg_name_id__in=(13, 15, 22), json_class=class_id, json__code=code)
    if location in ('table', 'contract'):
        base_hist = base_hist.filter(json__location=location)
    elif location == 'dict':
        base_hist = base_hist.filter(json__type='dict')
    q_hist = list(base_hist.filter(date_update__lte=date_to, date_update__gte=date_from).select_related('user')\
                  .values('date_update', 'user__first_name', 'user__last_name').distinct())
    if q_hist:
        last_date_object = base_hist.order_by('-date_update')[:1]  # последняя запись в истории данного объекта
        if last_date_object and last_date_object[0].date_update > date_to:
            just_history = True
    # Создадим массив с данными словарей, принадлежащих к данному объекту
    last_date_dicts = []
    if location != 'dict' and children:
        for md in tom['my_dicts']:
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
    last_date_tps = []
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
