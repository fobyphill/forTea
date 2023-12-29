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
def get_full_object(reqs, headers):
    object = dict()
    if reqs and headers:
        object['code'] = reqs[0].code
        object['parent_structure_id'] = reqs[0].parent_structure_id
        for h in headers:
            object[h['id']] = {'name': h['name'], 'type': h['formula']}
            try:
                req = next(r for r in reqs if r.name_id == h['id'])
            except StopIteration:
                object[h['id']]['value'] = None
                object[h['id']]['delay'] = None
            else:
                object[h['id']]['value'] = req.value
                object[h['id']]['delay'] = req.delay
    return object




