from app.functions import reg_funs, session_funs
from app.models import ContractCells, Objects


# avto = add_value_to_objects
# добавляет значение реквизита во все объекты, где его нет
def avto(current_class, location, header, parent_transact, user_id, timestamp):
    if header.formula in ('file', 'eval'):
        return False
    elif header.formula == 'enum':
        default = header.value[0]
    else:
        default = header.default
    manager = ContractCells.objects if location == 'c' else Objects.objects
    new_req_manager = ContractCells if location == 'c' else Objects
    exist_reqs = manager.filter(parent_structure_id=current_class.id, name_id=header.id)
    new_reqs = []
    edit_reqs = []
    full_location = 'table' if location == 't' else 'contract'
    list_regs = []
    def pack_to_reg(req, old_val, reg_id):
        inc = {'class_id': current_class.id, 'code': req.code, 'location': full_location,
                   'type': current_class.formula, 'name': header.id, 'id': req.id, 'value': old_val}
        outc = inc.copy()
        outc['value'] = req.value
        reg = {'json': outc}
        if reg_id == 15:
            reg['json_income'] = inc
        transact_id = reg_funs.get_transact_id(current_class.id, req.code, location)
        new_reg = {'user_id': user_id, 'reg_id': reg_id, 'timestamp': timestamp, 'transact_id': transact_id,
                   'parent_transact': parent_transact, 'reg': reg}
        list_regs.append(new_reg)
    # Прочешем существующие записи на предмет пустых. Если запись пустая - заполним ее дефолтом
    exclude_codes = []
    for er in exist_reqs:
        if not er.value:
            er.value = default
            edit_reqs.append(er)
            pack_to_reg(er, '', 15)
        exclude_codes.append(er.code)
    # Создадим реквизиты отсутствующие в других объектах
    objs = manager.filter(parent_structure_id=current_class.id).exclude(code__in=exclude_codes).values('code').distinct()
    for o in objs:
        new_req = new_req_manager(parent_structure_id=current_class.id, name_id=header.id, code=o['code'], value=default)
        new_reqs.append(new_req)
    while edit_reqs:
        manager.bulk_update(edit_reqs[:1000], ['value'])
        edit_reqs = edit_reqs[1000:]
    while new_reqs:
        manager.bulk_create(new_reqs[:1000])
        new_reqs = new_reqs[1000:]
    new_reqs = manager.filter(parent_structure_id=current_class.id, name_id=header.id,
                              code__in=[o['code'] for o in objs]).exclude(code__in=exclude_codes)
    for nr in new_reqs:
        pack_to_reg(nr, None, 13)
    reg_funs.paket_reg(list_regs)


def get_tom(class_id, user_id, location, path_info):
    class ReqUser:
        id = 0

    class Request:
        GET = dict()
        session = dict()
        path = path_info
        user = ReqUser()

    sr = Request()  # sr - subrequest
    sr.GET['class_id'] = class_id
    sr.user.id = user_id
    sr.GET['location'] = location
    session_funs.update_omtd(sr)
    return sr.session['temp_object_manager']



