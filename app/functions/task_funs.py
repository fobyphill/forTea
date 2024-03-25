from copy import deepcopy
from datetime import datetime

from django.forms import model_to_dict

from app.functions import reg_funs, task_procedures, database_funs, update_funs, files_funs, api_funs
from app.models import Tasks, ContractCells, TechProcessObjects, Objects, RegistratorLog


# Выполнить таск для техпроцессов - проверить на выполненность, если оба выполнены - то выполнить, зарегать, удалить
def do_task(task_code, task_transact, user_id, timestamp=datetime.today(), **params):
    task_whole = Tasks.objects.filter(code=task_code)
    if 'exclude_id' in params:
        task_whole = task_whole.exclude(id=params['exclude_id'])
    if not task_whole:
        return True
    is_done = True
    for tw in task_whole:
        if not tw.date_done and tw.user_id:
            is_done = False
            break
    if is_done:
        transact_id = reg_funs.get_transact_id(task_whole[0].data['tp_id'], task_whole[0].data['parent_code'], 'p')
        list_regs = []
        for tw in task_whole:
            tp = TechProcessObjects.objects.get(parent_structure_id=tw.data['tp_id'], parent_code=tw.data['parent_code'],
                                                value__stage=tw.data['stage'])
            inc = {'class_id': tw.data['tp_id'], 'location': 'contract', 'type': 'techprocess', 'id': tp.id,
                   'name': tp.name_id, 'value': deepcopy(tp.value), 'code': tp.parent_code}
            tp.value['fact'] = tw.data['delta'] + tp.value['fact'] if tp.value['fact'] else tw.data['delta']
            tp.value['delay'] = [d for d in tp.value['delay'] if d['date_create'] != datetime.strftime(tw.date_create, '%Y-%m-%dT%H:%M:%S')]
            tp.save()

            outc = inc.copy()
            outc['value'] = tp.value
            reg = {'json_income': inc, 'json': outc}

            dict_reg = {'user_id': user_id, 'reg_id': 15, 'timestamp': timestamp, 'transact_id': transact_id,
                        'parent_transact_id': task_transact, 'reg': reg}
            list_regs.append(dict_reg)

        # регистрация изменений
        reg_funs.paket_reg(list_regs)
        # регистрация этапов таска
        task_procedures.tsdr(task_whole, timestamp, user_id, task_transact)
    return is_done


def do_task2(task_code, user_id, timestamp, task_transact, parent_transact=None, **params):
    task_whole = Tasks.objects.filter(code=task_code)
    if 'exclude_id' in params:
        task_whole = task_whole.exclude(id=params['exclude_id'])
    if not task_whole:
        return True
    is_done = True
    for tw in task_whole:
        if not tw.date_done and tw.user_id:
            is_done = False
            break
    if is_done:
        transact_id = reg_funs.get_transact_id(task_whole[0].data['tp_id'], task_whole[0].data['parent_code'], 'p')
        tp = TechProcessObjects.objects.filter(parent_structure_id=task_whole[0].data['tp_id'],
                                               parent_code=task_whole[0].data['parent_code'])
        list_regs = []
        for tw in task_whole:
            t = next(t for t in tp if t.name_id == tw.data['stage_id'])
            inc = {'class_id': tw.data['tp_id'], 'location': 'contract', 'type': 'tp', 'id': t.id,
                   'name': t.name_id, 'value': deepcopy(t.value), 'code': t.parent_code}
            t.value['fact'] = tw.data['delta'] + t.value['fact'] if t.value['fact'] else tw.data['delta']
            t.value['delay'] = [d for d in t.value['delay'] if d['date_create'] !=
                                datetime.strftime(tw.date_create, '%Y-%m-%dT%H:%M:%S') or d['value'] != tw.data['delta']]
            t.save()

            outc = inc.copy()
            outc['value'] = t.value
            reg = {'json_income': inc, 'json': outc}

            dict_reg = {'user_id': user_id, 'reg_id': 15, 'timestamp': timestamp, 'transact_id': transact_id,
                        'parent_transact_id': task_transact, 'reg': reg}
            list_regs.append(dict_reg)

        # регистрация изменений
        reg_funs.paket_reg(list_regs)
        # регистрация этапов таска
        task_procedures.tsdr(task_whole, timestamp, user_id, task_transact, parent_transact)
    return is_done


def change_task_stage(user_id, task_rec, timestamp=datetime.today(), **params):
    # Опциональные параметры
    is_approve = True if 'is_approve' in params and params['is_approve'] else False
    check_task = True if 'check_task' in params and params['check_task'] else False
    # регистрация выполнения записи таска - редактирование записи задачи ID регистратора 20
    transact_id = params['transact_id'] if 'transact_id' in params else reg_funs.get_transact_id('task', task_rec.code)
    str_timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S')
    date_done_inc = str_timestamp if not is_approve else None
    date_done_outc = str_timestamp if is_approve else None
    inc = {'date_done': date_done_inc, 'code': task_rec.code, 'id': task_rec.id}
    outc = {'date_done': date_done_outc, 'code': task_rec.code, 'id': task_rec.id}
    reg = {'json_income': inc, 'json': outc}
    reg_funs.simple_reg(user_id, 20, timestamp, transact_id, **reg)
    # для тасков типа "контракт выполнен" - complete of the contract
    if task_rec.kind == 'cotc':
        # Зарегаем удаление параметра таска
        inc = task_procedures.comotatodi(task_rec)
        reg = {'json_income': inc}
        reg_funs.simple_reg(user_id, 19, timestamp, transact_id, **reg)
        # Зарегаем удаление таска
        reg = {'inc': {'code': task_rec.code}}
        reg_funs.simple_reg(user_id, 21, timestamp, transact_id, **reg)
        api_funs.remove_object(task_rec.data['class_id'], task_rec.data['code'], user_id, 'contract',
                               parent_transact=transact_id, timestamp=timestamp)  # Удалим контракт
        task_rec.delete()  # Удалим таск
    else:
        task_rec.date_done = timestamp if is_approve else None
        task_rec.save()
        # внесение изменений в объект - добавляем / удаляем подтверждение только в объектах. А это возможно, если таск имеет тип
        # prop или тип cf, но с указанным дейт делеем. Если тип cf, но дейт делэй не указан - значит это таск на стадию ТП
        # А его не надо изменять в объектах
        if task_rec.kind == 'prop' or task_rec.kind == 'cf' and task_rec.date_delay:
            object_manager = ContractCells.objects if task_rec.data['location'] == 'c' else Objects.objects
            object = object_manager.get(parent_structure_id=task_rec.data['class_id'], code=task_rec.data['code'],
                                            name_id=task_rec.data['name_id'])
            loc = 'table' if task_rec.data['location'] == 't' else 'contract'
            inc = {'class_id': task_rec.data['class_id'], 'location': loc, 'type': object.parent_structure.formula,
                   'code': task_rec.data['code'], 'id': object.id, 'name': object.name_id, 'delay': deepcopy(object.delay)}
            delay_ppa = False
            for od in object.delay:
                if datetime.strptime(od['date_update'], '%Y-%m-%dT%H:%M') == task_rec.date_delay and \
                        od['value'] == task_rec.data['delay']:
                    od['approve'] = is_approve
                    if task_rec.date_delay < timestamp:
                        delay_ppa = True
                    break
            outc = inc.copy()
            outc['delay'] = object.delay
            object.save()
            reg = {'json': outc, 'json_income': inc}
            child_transact = reg_funs.get_transact_id(object.parent_structure_id, object.code, task_rec.data['location'])
            reg_funs.simple_reg(user_id, 22, timestamp, child_transact, transact_id, **reg)
            if delay_ppa and is_approve:
                update_funs.run_delays([task_rec])
        # Если имеем дело с типом  СФ и подтверждаем последнюю стадию - то запустим крон
        elif task_rec.kind == 'cf' and not task_rec.date_delay:
            all_stage = Tasks.objects.filter(code=task_rec.code)
            excluded_stage = None
            all_stages_done = True
            for als in all_stage:
                if not als.date_done:
                    all_stages_done = False
                    break
                if als.date_delay:
                    excluded_stage = als
            # Если все стадии подтверждены, то выполним стадии кроме исключительной(do_task).
            # А если успешно выполнилились и таймштамп ниже даты делэя, то еще и крон запустим
            if all_stages_done:
                if do_task(task_rec.code, transact_id, user_id, timestamp, exclude_id=excluded_stage.id) \
                    and excluded_stage.date_delay < timestamp:
                    update_funs.run_delays((excluded_stage,))
        # Проверка и выполнение задания для стадии
        if check_task:
            do_task2(task_rec.code, user_id, timestamp, transact_id)



# params = {timestamp, parent_transact}
def make_task4prop(user_id, data, handler, date_delay, **params):
    timestamp = params['timestamp'] if'timestamp' in params else datetime.today()
    parent_transact = params['parent_transact'] if'parent_transact' in params else None
    code = params['code'] if 'code' in params else database_funs.get_other_code('task')
    transact_id = params['task_transact'] if 'task_transact' in params else reg_funs.get_transact_id('task', code)
    if not 'code' in params:
        reg = {'json': {'code': code}}
        reg_funs.simple_reg(user_id, 17, timestamp, transact_id, parent_transact, **reg)
    date_done = None if handler else timestamp
    task = Tasks(data=data, date_create=timestamp, date_done=date_done, user_id=handler, date_delay=date_delay,
                 code=code, kind='prop')
    task.save()
    outc = task_procedures.comotatodi(task)
    reg = {'json': outc}
    reg_funs.simple_reg(user_id, 18, timestamp, transact_id, parent_transact, **reg)
    return task


# mt4cotc = make task for completion of the contract
def mt4cotc(contract, sys_data_obj, user_id):
    data = {'class_id': contract.id, 'class_name': contract.name, 'code': sys_data_obj.code,
            'date_time_rec': sys_data_obj.value['datetime_create'], 'sender_id': user_id}
    task_code = database_funs.get_other_code('task')
    task = Tasks(data=data, date_create=datetime.today(), user_id=sys_data_obj.value['handler'], code=task_code, kind='cotc')
    task.save()


# mt4s = make task for stage
def mt4s(code, receiver, sender, sender_fio, fact, state, delay, delta, stage_id, task_code, tp_info, timestamp,
         task_transact, parent_transact=None):
    stage = next(s for s in tp_info['stages'] if s['id'] == stage_id)
    data = {'tp_id': tp_info['id'], 'tp_name': tp_info['name'], 'parent_code': code, 'fact': fact,
            'state': state, 'delay': delay, 'delta': delta, 'stage': stage['name'], 'stage_id': stage_id,
            'sender_id': sender, 'sender_fio': sender_fio}
    task = Tasks(date_create=timestamp, user_id=receiver, data=data, code=task_code, kind='stage')
    if not receiver:
        task.date_done = timestamp
    task.save()
    task = model_to_dict(task)
    task['date_create'] = datetime.strftime(task['date_create'], '%Y-%m-%dT%H:%M:%S')
    if not receiver:
        task['date_done'] = datetime.strftime(task['date_done'], '%Y-%m-%dT%H:%M:%S')
    reg = {'json': task}
    reg_funs.simple_reg(sender, 18, timestamp, task_transact, parent_transact, **reg)


# Удаление простого таска - один таск - одна запись
def delete_simple_task(task, timestamp, **params):
    transact_id = reg_funs.get_transact_id('task', task.id) if not 'task_transact' in params else params['task_transact']
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    if 'task_delete' in params:
        task_delete = params['task_delete']
    else:
        task_delete = True
    # Регаем уделение свойства
    inc = model_to_dict(task)
    if inc['date_create']:
        inc['date_create'] = datetime.strftime(inc['date_create'], '%Y-%m-%dT%H:%M:%S')
    if inc['date_done']:
        inc['date_done'] = datetime.strftime(inc['date_done'], '%Y-%m-%dT%H:%M:%S')
    if inc['date_delay']:
        inc['date_delay'] = datetime.strftime(inc['date_delay'], '%Y-%m-%dT%H:%M:%S')
    reg = {'json_income': inc}
    reg_funs.simple_reg(task.data['sender_id'], 19, timestamp, transact_id, parent_transact, **reg)
    if task_delete:
        # Регаем удаление задачи
        inc = {'code': task.code}
        reg = {'json_income': inc}
        reg_funs.simple_reg(task.data['sender_id'], 21, timestamp, transact_id, parent_transact, **reg)
        # Удалим-с
    task.delete()


# Удаление таска типа Stage. Откат значений на объектах не производится
def delete_stage_task(task_code, user_id, **params):
    timestamp = params['timestamp'] if 'timestamp' in params else datetime.today()
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    transact_id = reg_funs.get_transact_id('task', task_code)
    list_regs = []
    # Регистрация удаления таска
    inc = {'code': task_code}
    reg_task = {'json_income': inc}
    dict_del_task = {'user_id': user_id, 'reg_id': 21, 'timestamp': timestamp, 'transact_id': transact_id,
                     'parent_transact': parent_transact, 'reg': reg_task}
    list_regs.append(dict_del_task)
    stages = Tasks.objects.filter(kind='stage', code=task_code)
    for s in stages:
        inc_stage = model_to_dict(s)
        if inc_stage['date_create']:
            inc_stage['date_create'] = datetime.strftime(inc_stage['date_create'], '%Y-%m-%dT%H:%M:%S')
        if inc_stage['date_done']:
            inc_stage['date_done'] = datetime.strftime(inc_stage['date_done'], '%Y-%m-%dT%H:%M:%S')
        if inc_stage['date_delay']:
            inc_stage['date_delay'] = datetime.strftime(inc_stage['date_delay'], '%Y-%m-%dT%H:%M:%S')
        reg_stage = {'json_income': inc_stage}
        dict_del_stage = {'user_id': user_id, 'reg_id': 19, 'timestamp': timestamp, 'transact_id': transact_id,
                     'parent_transact': parent_transact, 'reg': reg_stage}
        list_regs.append(dict_del_stage)
    stages.delete()
    reg_funs.paket_reg(list_regs)




# Полное удаление таска с откатом прежних значений на объектах
def task_full_delete(task_code, timestamp, user_id):
    task_del = Tasks.objects.filter(code=task_code)
    if task_del:
        task_trans_id = reg_funs.get_transact_id('task', task_code)
        list_regs = []
        for td in task_del:
            if td.kind != 'cotc':
                # Работаем с объектом
                if td.kind == 'stage':
                    tps = TechProcessObjects.objects.get(parent_structure_id=td.data['tp_id'],
                                                         parent_code=td.data['parent_code'], name_id=td.data['stage_id'])
                    inc = {'class_id': tps.parent_structure_id, 'location': 'contract', 'type': 'tp',
                           'name': tps.name_id, 'id': tps.id, 'code': tps.parent_code, 'value': deepcopy(tps.value)}
                    # Разделэивание
                    tps.value['delay'] = [d for d in tps.value['delay'] if d['date_create'] !=
                                          datetime.strftime(td.date_create, '%Y-%m-%dT%H:%M:%S') or d['value'] != td.data['delta']]
                    tps.save()
                    # регистрация изменения объекта
                    outc = inc.copy()
                    outc['value'] = tps.value
                    trans_id = reg_funs.get_transact_id(tps.parent_structure_id, tps.parent_code, 'p')
                    reg_id = 15
                else:
                    object_manager = ContractCells.objects if td.data['location'] == 'c' else Objects.objects
                    prop = object_manager.get(parent_structure_id=td.data['class_id'], name_id=td.data['name_id'],
                                              code=td.data['code'])
                    loc = 'contract' if td.data['location'] == 'c' else 'table'
                    inc = {'class_id': prop.parent_structure_id, 'location': loc, 'type': prop.name.parent.formula,
                           'name': prop.name_id, 'id': prop.id, 'code': prop.code, 'delay': deepcopy(prop.delay)}
                    # для файлов: удалим файл физически
                    if prop.name.formula == 'file':
                        filename = next(d['value'] for d in prop.delay if
                                        d['date_update'] == datetime.strftime(td.date_delay, '%Y-%m-%dT%H:%M'))
                        if filename:
                            files_funs.delete_file(prop.parent_structure_id, filename, folder=loc)
                    prop.delay = [d for d in prop.delay if
                                  d['date_update'] != datetime.strftime(td.date_delay, '%Y-%m-%dT%H:%M') or d['value'] != td.data['delay']]
                    prop.save()
                    outc = inc.copy()
                    outc['delay'] = prop.delay
                    trans_id = reg_funs.get_transact_id(prop.parent_structure_id, prop.code, td.data['location'])
                    reg_id = 22
                reg = {'json': outc, 'json_income': inc}
                dict_reg = {'user_id': user_id, 'reg_id': reg_id, 'timestamp': timestamp, 'transact_id': trans_id,
                            'parent_transact_id': task_trans_id, 'reg': reg}
                list_regs.append(dict_reg)

            # зарегаем удаление стадии таска
            inc = model_to_dict(td)
            if inc['date_create']:
                inc['date_create'] = datetime.strftime(inc['date_create'], '%Y-%m-%dT%H:%M:%S')
            if inc['date_done']:
                inc['date_done'] = datetime.strftime(inc['date_done'], '%Y-%m-%dT%H:%M:%S')
            if inc['date_delay']:
                inc['date_delay'] = datetime.strftime(inc['date_delay'], '%Y-%m-%dT%H:%M:%S')
            reg = {'json_income': inc}
            reg_dict = {'reg_id': 19, 'user_id': user_id, 'timestamp': timestamp,
                        'transact_id': task_trans_id, 'reg': reg}
            list_regs.append(reg_dict)

        reg_funs.paket_reg(list_regs)  # зарегаем изменения объектов и записей таска
        task_del.delete()  # Удалим таск
        # Зарегаем удаление таска
        inc = {'code': task_code}
        reg = {'json_income': inc}
        reg_funs.simple_reg(user_id, 21, timestamp, task_trans_id, **reg)


def reg_create_task(user_id, timestamp, parent_transact):
    task_code = database_funs.get_other_code('task')
    task_transact_id = reg_funs.get_transact_id('task', task_code)
    reg = {'json': {'code': task_code}}
    reg_funs.simple_reg(user_id, 17, timestamp, task_transact_id, parent_transact, **reg)
    return task_code, task_transact_id