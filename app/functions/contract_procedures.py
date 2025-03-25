import copy

from app.functions import convert_funs2, convert_funs
from app.models import ContractCells


def rex(result):
    if type(result) is str and result[:6].lower() == 'ошибка':
        raise Exception(result)



def check_tp_biz_rulz(tp_data, biz_rulz, parent_obj, user_id, event_kind, is_br=True):
    brs = copy.deepcopy(biz_rulz)
    for nsk, nsv in tp_data['new_stages'].items():
        if nsv['delta']:
            for br in brs:
                if not 'do' in br or not br['do']:
                    br['do'] = nsk in br['stages'] and br['code'] and event_kind in br['event_kind']

    for br in brs:
        if br['do']:
            header = {'id': 0, 'name': 'bizrule', 'formula': 'eval', 'value': br['code']}
            convert_funs.deep_formula(header, [parent_obj], user_id, True)
            val = copy.deepcopy(parent_obj[0]['value'])
            del parent_obj[0]
            if is_br and not bool(val) or type(val) is str and val[:6].lower() == 'ошибка':
                return False
    return True


# rtr = retreive_tp_rout
def rtr(tp_info, current_stage_id, offspring, parents=[]):
    list_routs = []
    current_stage_info = next(s for s in tp_info['stages'] if s['id'] == current_stage_id)
    children = current_stage_info['value']['children']
    for ch in children:
        if ch in parents:
            continue
        if ch == offspring:
            rout = [current_stage_id, offspring]
            list_routs.append(rout)
        else:
            deep_parents = parents.copy()
            deep_parents.append(current_stage_id)
            children_routs = rtr(tp_info, ch, offspring, deep_parents)
            if children_routs:
                for chr in children_routs:
                    chr.insert(0, current_stage_id)
                    list_routs.append(chr)
    return list_routs


