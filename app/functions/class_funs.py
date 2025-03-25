import re

from django.db.models import Q

from app.models import RegistratorLog, Arhiv


# drag and drop info from hist to arhiv
def dndi_frohi_toarhiv(class_id, loc, class_type):
    arhiv = []
    dict_locs = {'t': 'table', 'c': 'contract', 'z': 'task'}
    location = dict_locs[loc]
    q_location = Q(json__location=location, json__type=class_type) | Q(json_income__location=location, json_income__type=class_type)
    base_query = RegistratorLog.objects.filter(q_location, json_class=class_id)
    # Переместим данные о классе
    create_edit_del = base_query.filter(reg_name__in=(1, 3, 4))
    for ced in create_edit_del:
        value_inc = {}
        if ced.json_income:
            for ek, ev in ced.json_income.items():
                if ek in ['class_id', 'location', 'type']:
                    continue
                value_inc[ek] = ev
        value_outc = {}
        if ced.json:
            for ek, ev in ced.json.items():
                if ek in ['class_id', 'location', 'type']:
                    continue
                value_outc[ek] = ev
        new_rec_arhiv = Arhiv(reg_id=ced.reg_name_id, transact_id=ced.transact_id, parent_transact=ced.parent_transact_id,
                              date_update=ced.date_update, class_id=class_id, location=loc, type=class_type,
                              value_outc=value_outc, value_inc=value_inc, user_id=ced.user_id)
        arhiv.append(new_rec_arhiv)
    create_edit_del.delete()

    # Переместим данные о параметрах класса
    class_params_hist = base_query.filter(reg_name__in=(9, 10, 11))
    for cph in class_params_hist:
        value_inc = {}
        header_id = None
        if cph.json_income:
            for ek, ev in cph.json_income.items():
                if ek in ['class_id', 'location', 'type']:
                    continue
                elif ek == 'id':
                    header_id = ev
                elif ek == 'delay':
                    if loc == 'c':
                        delay_inc = False
                        handler_inc = None
                        if ev:
                            if 'delay' in ev:
                                delay_inc = ev['delay']
                            if 'handler' in ev:
                                handler_inc = ev['handler']
                        delay_outc = False
                        handler_outc = None
                        if cph.json and cph.json['delay']:
                            if 'delay' in cph.json['delay']:
                                delay_outc = cph.json['delay']['delay']
                            if 'handler' in cph.json['delay']:
                                handler_outc = cph.json['delay']['handler']
                        if delay_inc != delay_outc:
                            value_inc['delay'] = delay_inc
                        if handler_inc != handler_outc:
                            value_inc['handler'] = handler_inc
                    else:
                        value_inc['delay'] = ev
                elif ek == 'delay_settings':
                    value_inc['handler'] = ev['handler']
                else:
                    value_inc[ek] = ev
        value_outc = {}
        if cph.json:
            for ek, ev in cph.json.items():
                if ek in ['class_id', 'location', 'type']:
                    continue
                elif ek == 'id':
                    header_id = ev
                elif ek == 'delay':
                    if loc == 'c':
                        delay_inc = False
                        handler_inc = None
                        if cph.json and cph.json_income['delay']:
                            if 'delay' in cph.json_income['delay']:
                                delay_inc = cph.json_income['delay']['delay']
                            if 'handler' in cph.json_income['delay']:
                                handler_inc = cph.json_income['delay']['handler']
                        delay_outc = False
                        handler_outc = None
                        if ev:
                            if 'delay' in ev:
                                delay_outc = ev['delay']
                            if 'handler' in ev:
                                handler_outc = ev['handler']
                        if delay_inc != delay_outc:
                            value_outc['delay'] = delay_outc
                        if handler_inc != handler_outc:
                            value_outc['handler'] = handler_outc
                    else:
                        value_outc['delay'] = ev
                elif ek == 'delay_settings':
                    value_outc['handler'] = ev['handler']
                else:
                    value_outc[ek] = ev
        new_rec_arhiv = Arhiv(reg_id=cph.reg_name_id, transact_id=cph.transact_id, parent_transact=cph.parent_transact_id,
                              header_id=header_id, date_update=cph.date_update, class_id=class_id, location=loc,
                              type=class_type, value_outc=value_outc, value_inc=value_inc, user_id=cph.user_id)
        arhiv.append(new_rec_arhiv)
    class_params_hist.delete()

    # Переместим данные об объектах
    task_list = []
    objs = base_query.filter(reg_name__in=(5, 8, 13, 15, 16, 22))
    for o in objs:
        header_id = None; code = None; value_inc = None; value_outc = None
        if o.json_income:
            header_id = o.json_income['name'] if 'name' in o.json_income else None
            code = o.json_income['code'] if 'code' in o.json_income else None
            if o.reg_name_id == 22:
                value_inc = o.json_income['delay']
            else:
                value_inc = o.json_income['value'] if 'value' in o.json_income else None
        if o.json:
            if not code and  'code' in o.json:
                code = o.json['code']
            if not header_id and 'name' in o.json:
                header_id = o.json['name']
            if o.reg_name_id == 22:
                value_outc = o.json['delay']
            else:
                value_outc = o.json['value'] if 'value' in o.json else None
        new_rec_arhiv = Arhiv(reg_id=o.reg_name_id, transact_id=o.transact_id, parent_transact=o.parent_transact_id,
                              header_id=header_id, code=code, date_update=o.date_update, class_id=class_id, location=loc,
                              type=class_type, value_outc=value_outc, value_inc=value_inc, user_id=o.user_id)
        arhiv.append(new_rec_arhiv)
        if class_type == 'tp' and o.reg_name_id == 15 and o.parent_transact_id:
            match_prop = re.match(r'task(\d+)id(\d+)', o.parent_transact_id)
            if match_prop:
                task_id = int(match_prop[1])
                if not task_id in task_list:
                    task_list.append(task_id)
    objs.delete()

    # Перенесем таски stage
    if class_type == 'tp':
        q_income = Q(reg_name_id__in=(19, 21), json_income__code__in=task_list)
        q_outcome = Q(reg_name_id__in=(17, 18, 20), json__code__in=task_list)
        task_hist = RegistratorLog.objects.filter(Q(q_income | q_outcome), )
        for th in task_hist:
            code = None; value_inc = None; value_outc = None
            if th.json_income:
                code = th.json_income['code']
                if th.reg_name_id == 19:
                    value_inc = {'data': th.json_income['data'], 'date_create': th.json_income['date_create'],
                                 'date_done': th.json_income['date_done']}
                elif th.reg_name_id == 20:
                    value_inc = {'date_done': th.json_income['date_done']}
            if th.json:
                if not code:
                    code = th.json['code']
                if th.reg_name_id == 18:
                    value_outc = {'data': th.json['data'], 'date_create': th.json['date_create'],
                                  'date_done': th.json['date_done']}
                elif th.reg_name_id == 20:
                    value_outc = {'date_done': th.json['date_done']}
            new_rec_arhiv = Arhiv(reg_id=th.reg_name_id, transact_id=th.transact_id, parent_transact=th.parent_transact_id,
                                  header_id=None, code=code, date_update=th.date_update, class_id=0, location='z',
                                  type='stage', value_outc=value_outc, value_inc=value_inc, user_id=th.user_id)
            arhiv.append(new_rec_arhiv)
        task_hist.delete()
    Arhiv.objects.using('arhiv').bulk_create(arhiv)


# dndi task fta = drag and drop info about tasks from history to arhiv
def dndi_task_fta(task_id, kind):
    arhiv = []
    q = Q(json__location='task', json__type=kind) | Q(json_income__location='task', json_income__type=kind)
    base_query = RegistratorLog.objects.filter(q, json_class=task_id)
    class_transacts = base_query.filter(reg_name__in=(1, 3, 4))
    for ct in class_transacts:
        value_inc = {}; value_outc = {}
        if ct.json_income:
            if 'parent' in ct.json_income:
                value_inc['parent'] = ct.json_income['parent']
            if 'name' in ct.json_income:
                value_inc['name'] = ct.json_income['name']
            if 'business_rule' in ct.json_income:
                value_inc['br'] = ct.json_income['business_rule']
            if 'link_map' in ct.json_income:
                value_inc['lm'] = ct.json_income['link_map']
            if 'trigger' in ct.json_income:
                value_inc['tr'] = ct.json_income['trigger']
        if ct.json:
            if 'parent' in ct.json:
                value_outc['parent'] = ct.json['parent']
            if 'name' in ct.json:
                value_outc['name'] = ct.json['name']
            if 'business_rule' in ct.json:
                value_outc['br'] = ct.json['business_rule']
            if 'link_map' in ct.json:
                value_outc['lm'] = ct.json['link_map']
            if 'trigger' in ct.json:
                value_outc['tr'] = ct.json['trigger']
        arhiv_new_rec = Arhiv(reg_id=ct.reg_name_id, transact_id=ct.transact_id, parent_transact=ct.parent_transact_id,
                              date_update=ct.date_update, class_id=ct.json_class, code=None, location='z',
                              type=kind, header_id=None, value_inc=value_inc, value_outc=value_outc, user_id=ct.user_id)
        arhiv.append(arhiv_new_rec)
    class_transacts.delete()
    if kind == 'custom':
        object_transacts = base_query.filter(reg_name__in=(17, 18, 19, 21))
        for ot in object_transacts:
            value_inc = {}; value_outc = {}; code = None
            if ot.json_income:
                code = ot.json_income['code']
                if ot.reg_name_id == 19:
                    value_inc['br'] = ot.json_income['data']['br']
                    value_inc['lm'] = ot.json_income['data']['lm']
                    value_inc['tr'] = ot.json_income['data']['tr']
                    value_inc['date_create'] = ot.json_income['date_create']
            if ot.json:
                code = ot.json['code']
                if ot.reg_name_id == 18:
                    value_outc['br'] = ot.json['data']['br']
                    value_outc['lm'] = ot.json['data']['lm']
                    value_outc['tr'] = ot.json['data']['tr']
                    value_outc['date_create'] = ot.json['date_create']
            new_reg = Arhiv(reg_id=ot.reg_name_id, transact_id=ot.transact_id, parent_transact=ot.parent_transact_id,
                            date_update=ot.date_update, class_id=ot.json_class, code=code, location='z', type='custom',
                            value_inc=value_inc, value_outc=value_outc, user_id=ot.user_id)
            arhiv.append(new_reg)
        object_transacts.delete()
    Arhiv.objects.using('arhiv').bulk_create(arhiv)


