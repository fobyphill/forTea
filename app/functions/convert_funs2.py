import re

from django.forms import model_to_dict

from app.functions import convert_funs, convert_procedures
from app.models import TechProcessObjects, ContractCells, Objects


# atptc = add_TechProcesses_to_contract
def atptc(objects, tps):
    codes = [o['code'] for o in objects]
    for t in tps:
        tp_cells = list(TechProcessObjects.objects.filter(parent_structure_id=t['id'], parent_code__in=codes).values())
        for o in objects:
            if t['control_field'] in o:
                control_field = o[t['control_field']]
                if not 'tps' in control_field:
                    control_field['tps'] = []
                stages = [tc['value'] for tc in tp_cells if tc['parent_code'] == o['code']]
                dict_tp = {'id': t['id'], 'stages': stages}
                control_field['tps'].append(dict_tp)


# Получаем объект в виде словаря. Вход - кверисет существующих реквизитов объекта, список заголовков
# Получает только объекты следующих типов - словари, контракты, массивы, деревья
def get_full_object(reqs, headers, location='table'):
    object = dict()
    if reqs and headers:
        object['code'] = reqs[0].code
        object['parent_structure_id'] = reqs[0].parent_structure_id
        for h in headers:
            object[h['id']] = {'name': h['name'], 'type': h['formula']}
            try:
                req = next(r for r in reqs if r.name_id == h['id'])
            except StopIteration:
                val = False if h['formula'] == 'bool' else None
                object[h['id']]['value'] = val
                if location not in ('tp', 'dict'):
                    object[h['id']]['delay'] = None
            else:
                object[h['id']]['value'] = req.value
                if location not in ('tp', 'dict'):
                    object[h['id']]['delay'] = req.delay
    return object

# pati = prepare_alias_to_interface
def pati(alias, **params):
    user_id = params['user_id'] if 'user_id' in params else None
    is_contract = params['is_contract'] if 'is_contract' in params else False
    is_main_page = params['main_page'] if 'main_page' in params else False
    for a in alias:
        val = convert_procedures.userdata_to_interface(a, 0, is_contract, is_main_page)
        if val:
            a[a['id']] = {'value': val}
        else:
            a['code'] = 0
            convert_funs.deep_formula(a, [a, ], user_id, is_contract)





