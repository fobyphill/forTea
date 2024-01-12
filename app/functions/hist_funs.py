from django.db.models.fields.json import KeyTextTransform

from app.functions import convert_funs
from app.models import RegistratorLog


def gov(class_id, code, location, timestamp, tom, user_id):
    base_hist = RegistratorLog.objects.filter(json_class=class_id, json__code=code, date_update__lte=timestamp)
    if location in ('table', 'contract'):
        base_hist = base_hist.filter(json__location=location)
    elif location == 'dict':
        base_hist = base_hist.filter(json__type='dict')

    # Заполним информацию об объекте
    headers = tom['headers']
    object = {'code': code, 'parent_structure': class_id, 'type': tom['current_class']['formula']}
    for h in headers:
        if h['formula'] != 'eval':
            hist_prop = base_hist.filter(reg_name_id__in=(13, 15), json__name=h['id']).order_by('-date_update')[:1]
            val = hist_prop[0].json['value'] if hist_prop and 'value' in hist_prop[0].json else None
            if 'delay' in h:
                if type(h['delay']) is bool and h['delay'] or type(h['delay']) is dict and h['delay']['delay']:
                    hist_delay = base_hist.filter(reg_name_id=22, json__name=h['id']).order_by('-date_update', '-id')[
                                 :1]
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
    if 'my_dicts' in tom and tom['my_dicts']:
        for md in tom['my_dicts']:
            dict_id = 'dict_' + str(md['id'])
            object[dict_id] = {}
            for ch in md['children']:
                hist_prop = RegistratorLog.objects.filter(json_class=md['id'], json__type='dict',
                                                          reg_name_id__in=(13, 15),
                                                          json__parent_code=code, json__name=ch['id'],
                                                          date_update__lte=timestamp).order_by('-date_update')[:1]
                if hist_prop:
                    object[dict_id][ch['id']] = {'type': ch['formula'], 'value': hist_prop[0].json['value'],
                                                 'name': ch['name']}
            if not object[dict_id]:
                object[dict_id] = None

    # добавим массивы
    if 'arrays' in tom:
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
                                                              date_update__lte=timestamp, json__name=ah['id']) \
                                    .order_by('-date_update')[:1]
                    if hist_prop:
                        array_obj[ah['id']] = {'type': ah['formula'], 'value': hist_prop[0].json['value']}
                if array_obj:
                    array_obj['code'] = ac['code']
                    array_obj['parent_structure'] = a['id']
                    object[a['id']]['objects'].append(array_obj)

    # Добавим список с техпроцессами
    if 'tps' in tom and tom['tps']:
        tps = tom['tps']
        objs = []
        for tp in tps:
            obj = {'id': tp['id'], 'stages': []}
            for s in tp['stages']:
                hist = RegistratorLog.objects.filter(json__code=code, json_class=tp['id'], reg_name_id__in=(13, 15),
                                                     json__type='tp', json__name=s['id'],
                                                     date_update__lte=timestamp).order_by('-id')[:1]
                if hist:
                    delay = hist[0].json['value']['delay']
                    fact = hist[0].json['value']['fact']
                elif tp['stages'].index(s) == 0:
                    control_field = RegistratorLog.objects.filter(json__code=code, json_class=tom['class_id'],
                                                                  reg_name_id__in=(13, 15),
                                                                  json__type__in=('contract', 'array'),
                                                                  json__name=tp['cf'],
                                                                  date_update__lte=timestamp) \
                                        .order_by('-date_update')[:1]
                    fact = control_field[0].json['value'] if control_field else 0
                    delay = []
                else:
                    fact = 0
                    delay = []
                obj['stages'].append({'id': s['id'], 'value': {'delay': delay, 'fact': fact}})
            objs.append(obj)
        object['new_tps'] = objs
    return object

