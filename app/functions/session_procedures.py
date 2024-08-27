from app.models import TechProcess


# atic = add_tps_in_contract
def atic(contract_id):
    tpos = TechProcess.objects.filter(parent_id=contract_id, formula='tp')
    tpos_ids = [t.id for t in tpos]
    tpos_params = list(TechProcess.objects.filter(parent_id__in=tpos_ids).values())
    tps = []
    for t in tpos:
        my_params = [tp for tp in tpos_params if tp['parent_id'] == t.id]
        sys_params = []
        stages = []
        for mp in my_params:
            if mp['settings']['system']:
                sys_params.append(mp)
            else:
                stages.append(mp)
        tp = {'id': t.id, 'name': t.name, 'parent_id': t.parent_id, 'cf': t.value['control_field'],
              'system_params': sys_params, 'stages': stages}
        tps.append(tp)
    return tps