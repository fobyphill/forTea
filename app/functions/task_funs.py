import copy
from copy import deepcopy
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import BooleanField, Value
from django.forms import model_to_dict
from app.functions import reg_funs, task_procedures, database_funs, update_funs, files_funs, api_funs, convert_funs, \
    contract_funs, contract_procedures, convert_funs2, session_procedures
from app.models import Tasks, ContractCells, TechProcessObjects, Objects, RegistratorLog, TaskClasses, TechProcess, \
    Contracts


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

@transaction.atomic()
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
        system_params_tp = TechProcess.objects.filter(parent_id=task_whole[0].data['tp_id'], settings__system=True)
        biz_rulz = None; link_map = None; triggers = None
        for spt in system_params_tp:
            if spt.name == 'business_rule':
                biz_rulz = spt
            elif spt.name == 'link_map':
                link_map = spt
            elif spt.name == 'trigger':
                triggers = spt

        tp_deltas = {}
        tp_data = {'new_stages': dict()}
        for tw in task_whole:
            t = next(t for t in tp if t.name_id == tw.data['stage_id'])

            inc = {'class_id': tw.data['tp_id'], 'location': 'contract', 'type': 'tp', 'id': t.id,
                   'name': t.name_id, 'value': deepcopy(t.value), 'code': t.parent_code}
            t.value['fact'] = tw.data['delta'] + t.value['fact'] if t.value['fact'] else tw.data['delta']
            t.value['delay'] = [d for d in t.value['delay'] if d['date_create'] != datetime.strftime(tw.date_create, '%Y-%m-%dT%H:%M:%S')]
            t.save()
            tp_deltas[t.name_id] = {'delta': tw.data['delta']}
            outc = inc.copy()
            outc['value'] = t.value
            reg = {'json_income': inc, 'json': outc}

            dict_reg = {'user_id': user_id, 'reg_id': 15, 'timestamp': timestamp, 'transact_id': transact_id,
                        'parent_transact_id': task_transact, 'reg': reg}
            list_regs.append(dict_reg)
            tp_data['new_stages'][t.name_id] = {'delta': tw.data['delta']}

        # Бирулиматоры
        if biz_rulz.value or link_map.value or triggers:
            current_tp = TechProcess.objects.get(id=task_whole[0].data['tp_id'])
            parent_class = Contracts.objects.get(id=current_tp.parent_id)
            parent_headers = Contracts.objects.filter(parent_id=parent_class.id, system=False).values()
            parent_queryset = ContractCells.objects.filter(parent_structure_id=current_tp.parent_id,
                                                           code=task_whole[0].data['parent_code'])
            parent_obj = convert_funs2.get_full_object(parent_queryset, parent_class, parent_headers, 'contract')
            # Проверим бизнес-правило
            if biz_rulz.value:
                if not contract_procedures.check_tp_biz_rulz(tp_data, biz_rulz.value, parent_obj, user_id, 'u'):
                    raise Exception(f'Не выполняется бизнес-правило техпроцесса ID: {task_whole[0].data["tp_id"]}')

            # Выполним ЛинкМапы
            if link_map.value:
               contract_funs.do_linkmap(link_map.value, parent_obj, ['u'], timestamp, transact_id, user_id, tp=tp_data['new_stages'])

            if triggers.value:
                if not contract_procedures.check_tp_biz_rulz(tp_data, triggers.value, parent_obj, user_id, 'u', False):
                    raise Exception(f'Не выполняется триггер техпроцесса ID: {task_whole[0].data["tp_id"]}')

        # регистрация изменений
        reg_funs.paket_reg(list_regs)
        # регистрация этапов таска
        task_procedures.tsdr(task_whole, timestamp, user_id, task_transact, parent_transact)
    return is_done


def change_task(user_id, task_rec, timestamp=datetime.today(), **params):
    # Опциональные параметры
    is_approve = 'is_approve' in params and params['is_approve']
    check_task = 'check_task' in params and params['check_task']
    if task_rec.kind != 'prop':
        # регистрация выполнения записи таска - редактирование записи задачи ID регистратора 20
        transact_id = params['transact_id'] if 'transact_id' in params else reg_funs.get_transact_id('task',
                                                                                                     task_rec.code)
        str_timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S')
        date_done_inc = str_timestamp if not is_approve else None
        date_done_outc = str_timestamp if is_approve else None
        inc = {'date_done': date_done_inc, 'code': task_rec.code, 'id': task_rec.id}
        outc = {'date_done': date_done_outc, 'code': task_rec.code, 'id': task_rec.id}
        reg = {'json_income': inc, 'json': outc}
        reg_funs.simple_reg(user_id, 20, timestamp, transact_id, **reg)
    else:
        transact_id = None
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
            if datetime.strptime(od['date_update'], '%Y-%m-%dT%H:%M') == task_rec.date_delay:
                od['approve'] = is_approve
                od['value'] = task_rec.data['delay']
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
        try:
            do_task2(task_rec.code, user_id, timestamp, transact_id)
        except Exception as ex:
            aaa = str(ex)
            pass


@transaction.atomic()
def change_stage(task, timestamp):
    tp_info = next(tp for tp in session_procedures.atic(task.data['class_id']) if tp['id'] == task.data['tp_id'])
    stages = TechProcessObjects.objects.filter(name_id__in=task.data['rout'][:2], parent_code=task.data['parent_code'])
    stage_transact = reg_funs.get_transact_id(tp_info['id'], task.data['parent_code'], 'p')
    count_approved = 0
    parent_class = Contracts.objects.get(id=task.data['class_id'])
    parent_headers = Contracts.objects.filter(parent_id=task.data['class_id'], system=False).values()
    for r in task.data['rout'][:2]:
        try:
            s = next(s for s in stages if s.name_id == r)
        except StopIteration:
            s = TechProcessObjects(parent_structure_id=task.data['tp_id'], parent_code=task.data['parent_code'],
                                   name_id=r, value={'fact': 0, 'delay': []})
        stage_info = next(si for si in tp_info['stages'] if si['id'] == s.name_id)
        my_delay = next(d for d in s.value['delay'] if d['date_create'] == task.data['date_create'])
        if stage_info['value']['handler'] == task.user_id:
            count_approved += 1
            if not my_delay['approve']:
                inc = {'class_id': tp_info['id'], 'location': 'contract', 'type': 'tp', 'code': s.parent_code,
                   'name': s.name_id, 'value': copy.deepcopy(s.value)}
                my_delay['approve'] = True
                s.save()
                tp_data = {'new_stages': {s.name_id: {'delta': task.data['quant']}}}
                outc = inc.copy()
                outc['value'] = s.value
                reg = {'json': outc, 'json_income': inc}
                reg_funs.simple_reg(task.user_id, 15, timestamp, stage_transact, **reg)
        elif my_delay['approve']:
            count_approved += 1

    # выпоним проверку - оба поля были подтверждены
    if count_approved == 2:
        # Обновляем таск по полной программе
        # 1. разделей текущего делэя
        tp_data = {'new_stages': {}}
        for s in stages:
            inc = {'class_id': tp_info['id'], 'location': 'contract', 'type': 'tp', 'code': s.parent_code,
                   'name': s.name_id, 'value': copy.deepcopy(s.value)}
            my_delay = next(d for d in s.value['delay'] if d['date_create'] == task.data['date_create'])
            s.value['fact'] += my_delay['value']
            s.value['delay'] = [d for d in s.value['delay'] if d != my_delay]
            s.save()
            tp_data['new_stages'][s.name_id] = {'delta': task.data['quant']}
            outc = inc.copy()
            outc['value'] = s.value
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(task.user_id, 15, timestamp, stage_transact, **reg)
        contract_funs.do_tp_birulimators(tp_info, parent_class, parent_headers, task.data['parent_code'], 'u', tp_data,
                                         task.user_id, timestamp, stage_transact)
        # 2. Продвижение таска
        task.data['rout'] = task.data['rout'][1:]
        # 3. Если таск не закончен, то Заделэй следующей порции
        if len(task.data['rout']) > 1:
            object_user = get_user_model().objects.get(id=task.user_id)
            matafost(parent_class, parent_headers, task.data['parent_code'], tp_info, task.data['rout'],
                     task.data['quant'], object_user, task=task, timestamp=timestamp, transact_id=stage_transact)
        else:
            task.delete()
    else:
        # локальные правки: правим ТП, изменяем таск (меняем юзера таска)
        stage_info = next(si for si in tp_info['stages'] if si['id'] == task.data['rout'][1])
        task.user_id = stage_info['value']['handler']
        task.save()


def make_task4prop(data, handler, date_delay, **params):
    timestamp = params['timestamp'] if'timestamp' in params else datetime.today()
    code = params['code'] if 'code' in params else database_funs.get_other_code('task')
    date_done = None if handler else timestamp
    task = Tasks(data=data, date_create=timestamp, date_done=date_done, user_id=handler, date_delay=date_delay,
                 code=code, kind='prop')
    task.save()
    return task


# mt4cotc = make task for completion of the contract
def mt4cotc(contract, sys_data_obj, user_id):
    data = {'class_id': contract.id, 'class_name': contract.name, 'code': sys_data_obj.code,
            'date_time_rec': sys_data_obj.value['datetime_create'], 'sender_id': user_id}
    task_code = database_funs.get_other_code('task')
    task = Tasks(data=data, date_create=datetime.today(), user_id=sys_data_obj.value['handler'], code=task_code, kind='cotc')
    task.save()


# mt4s = make task for stage
def mt4s(code, receiver, sender, sender_fio, fact, state, delay, delta, stage_id, task_code, tp_info, timestamp, partners,
         task_transact, parent_transact=None):
    stage = next(s for s in tp_info['stages'] if s['id'] == stage_id)
    data = {'tp_id': tp_info['id'], 'tp_name': tp_info['name'], 'parent_code': code, 'fact': fact,
            'state': state, 'delay': delay, 'delta': delta, 'stage': stage['name'], 'stage_id': stage_id,
            'sender_id': sender, 'sender_fio': sender_fio, 'partners': partners}
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
def delete_simple_task(task, timestamp, user_id, **params):
    transact_id = reg_funs.get_transact_id('task', task.id) if not 'task_transact' in params else params['task_transact']
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    if 'task_delete' in params:
        task_delete = params['task_delete']
    else:
        task_delete = True
    # Регаем уделение свойства
    inc = model_to_dict(task)
    inc['type'] = inc['kind']
    inc['class_id'] = inc['data']['class_id']
    del inc['kind']
    if inc['date_create']:
        inc['date_create'] = datetime.strftime(inc['date_create'], '%Y-%m-%dT%H:%M:%S')
    if inc['date_done']:
        inc['date_done'] = datetime.strftime(inc['date_done'], '%Y-%m-%dT%H:%M:%S')
    if inc['date_delay']:
        inc['date_delay'] = datetime.strftime(inc['date_delay'], '%Y-%m-%dT%H:%M:%S')
    if task.kind == 'custom':
        inc['location'] = 'task'
    reg = {'json_income': inc}
    reg_funs.simple_reg(user_id, 19, timestamp, transact_id, parent_transact, **reg)
    if task_delete:
        # Регаем удаление задачи
        inc = {'code': task.code}
        if task.kind == 'custom':
            inc['type'] = 'custom'
            inc['class_id'] = task.data['class_id']
            inc['location'] = 'task'
        reg = {'json_income': inc}
        reg_funs.simple_reg(user_id, 21, timestamp, transact_id, parent_transact, **reg)
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
                    stages = TechProcessObjects.objects.filter(parent_structure_id=td.data['tp_id'],
                                                         parent_code=td.data['parent_code'], name_id__in=td.data['rout'][:2])
                    parent_class = Contracts.objects.get(id=td.data['class_id'])
                    parent_headers = Contracts.objects.filter(parent_id=td.data['class_id'], system=False).values()
                    try:
                        result = undelay_stages(parent_class, parent_headers, stages, td.data['date_create'], user_id,
                                                timestamp, None)
                    except Exception as ex:
                        return 'Ошибка. ' + str(ex)
                    else:
                        td.delete()
                        return result

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

            if td.kind == 'prop':
                continue
            elif td.kind == 'stage':
                pass
            else:
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
        return 'ok'


def reg_create_task(user_id, timestamp, parent_transact):
    task_code = database_funs.get_other_code('task')
    task_transact_id = reg_funs.get_transact_id('task', task_code)
    reg = {'json': {'code': task_code}}
    reg_funs.simple_reg(user_id, 17, timestamp, task_transact_id, parent_transact, **reg)
    return task_code, task_transact_id


# ctdo = create_task_delay_object
def ctdo(date_delay, delay_object, user_id):
    timestamp = datetime.today()
    if date_delay < timestamp:
        timestamp, date_delay = date_delay, timestamp
    code, transact_id = reg_create_task(user_id, timestamp, None)
    task = Tasks(data=delay_object, user_id=user_id, date_create=timestamp, code=code, date_delay=date_delay, kind='do')
    task.save()
    # Регистрация создания записи задачи
    dict_task = model_to_dict(task)
    str_date_create = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S')
    str_date_delay = datetime.strftime(date_delay, '%Y-%m-%dT%H:%M:%S')
    dict_task['date_create'] = str_date_create
    dict_task['date_delay'] = str_date_delay
    reg = {'json': dict_task}
    reg_funs.simple_reg(user_id, 18, timestamp, transact_id, **reg)


def update_task_tree(source_tasks=[], task_tree=[]):
    if not source_tasks:
        source_tasks = list(TaskClasses.objects.all().annotate(opened=Value(False, output_field=BooleanField())).values())
    if not task_tree:
        task_tree = source_tasks
    i = 0
    while i < len(task_tree):
        my_task = task_tree[i]
        children = []
        j = 0
        while j < len(source_tasks):
            if source_tasks[j]['parent_id'] == my_task['id']:
                children.append(source_tasks[j])
                del source_tasks[j]
            else:
                j += 1
        if children:
            my_task['children'] = update_task_tree(source_tasks, children)
        i += 1
    return task_tree


@transaction.atomic()
def do_custom_task(task, **params):
    timestamp = params['timestamp'] if 'timestamp' in params else datetime.today()
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    # выполним бизнес-правило
    if task.data['br']:
        br = convert_funs.static_formula(task.data['br'], task.user_id)
        contract_procedures.rex(br)
        if not br:
            return False

    # выполним линкмапы
    parent_obj = {'code': 1}
    contract_funs.do_linkmap(task.data['lm'], parent_obj, ['u'], timestamp, parent_transact, task.user_id)

    if task.data['tr']:
        tr = convert_funs.static_formula(task.data['tr'], task.user_id)
        contract_procedures.rex(tr)
    return True



# matafost = make task for stage
@transaction.atomic()
def matafost(parent_class, parent_headers, code, tp_info, rout, quant, object_user=None, **params):
    timestamp = params['timestamp'] if 'timestamp' in params else datetime.today()
    str_timestamp = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S')
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    task = params['task'] if 'task' in params else None
    base_inc = {'class_id': tp_info['id'], 'location': 'contract', 'type': 'tp'}
    transact_id = params['transact_id'] if 'transact_id' in params else reg_funs.get_transact_id(tp_info['id'], code, 'p')
    # 0. Если все стадии без ответственных, то сразу вносим изминения в ТП без делэя
    approves = True

    while approves:
        tp_data = {'new_stages': {}}
        for r in rout[:2]:
            stage_info = next(si for si in tp_info['stages'] if si['id'] == r)
            if stage_info['value']['handler']:
                approves = False
                break
        if approves:
            for r in rout[:2]:
                try:
                    s = TechProcessObjects.objects.get(parent_structure_id=tp_info['id'], parent_code=code, name_id=r)
                except ObjectDoesNotExist:
                    val = {'fact': 0, 'delay': []}
                    s = TechProcessObjects(parent_structure_id=tp_info['id'], parent_code=code, name_id=r, value=val)
                val_fact = quant * -1 if s.name_id == rout[0] else quant
                tp_data['new_stages'][s.name_id] = {'delta': val_fact}
                inc = base_inc.copy()
                inc['name'] = s.name_id
                inc['code'] = s.parent_code
                outc = inc.copy()
                inc['value'] = deepcopy(s.value)
                s.value['fact'] += val_fact
                s.save()
                outc['value'] = s.value
                reg = {'json': outc, 'json_income': inc}
                reg_funs.simple_reg(object_user.id, 15, timestamp, transact_id, parent_transact, **reg)
            contract_funs.do_tp_birulimators(tp_info, parent_class, parent_headers, code, 'u', tp_data, object_user.id,
                                             timestamp, parent_transact)
            rout.pop(0)
            if (len(rout) == 1):
                break
    if not approves:
        tp_data = {'new_stages': {}}
        task_user = None
        # 1. Вносим изминения в ТП
        for r in rout[:2]:
            try:
                s = TechProcessObjects.objects.get(parent_structure_id=tp_info['id'], parent_code=code, name_id=r)
            except ObjectDoesNotExist:
                val = {'fact': 0, 'delay': []}
                s = TechProcessObjects(parent_structure_id=tp_info['id'], parent_code=code, name_id=r, value=val)
            val_delay = quant * -1 if s.name_id == rout[0] else quant
            tp_data['new_stages'][s.name_id] = {'delta': val_delay}
            inc = base_inc.copy()
            inc['name'] = s.name_id
            inc['code'] = s.parent_code
            outc = inc.copy()
            inc['value'] = deepcopy(s.value)
            stage_info = next(si for si in tp_info['stages'] if si['id'] == s.name_id)
            approve = not bool(stage_info['value']['handler'])
            if not approve and not task_user:
                task_user = stage_info['value']['handler']
            delay = {'date_create': str_timestamp, 'approve': approve, 'value': val_delay}
            s.value['delay'].append(delay)
            s.save()
            outc['value'] = s.value
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(object_user.id, 15, timestamp, transact_id, parent_transact, **reg)
        # 2. Выполняем бирулиматоры
        contract_funs.do_tp_birulimators(tp_info, parent_class, parent_headers, code, 'd', tp_data, object_user.id,
                                         timestamp, parent_transact)
        if task:
            task.data['rout'] = rout
            task.data['date_create'] = str_timestamp
            task.user_id = task_user
            task.save()
        else:
            # 3. Создаем таск
            data = {'class_id': parent_class.id, 'parent_code': code, 'tp_id': tp_info['id'], 'rout': rout, 'quant': quant,
                    'sender_fio': object_user.first_name + ' ' + object_user.last_name, 'sender_id': object_user.id,
                    'date_create': str_timestamp}
            task_code = database_funs.get_other_code('task')
            new_task = Tasks(data=data, date_create=timestamp, user_id=task_user, code=task_code, kind='stage')
            new_task.save()
    elif task:
        task.delete()



@transaction.atomic()
def undelay_stages(parent_class, parent_headers, stages, date_create, user_id, timestamp, parent_transact):
    tp_info = next(a for a in session_procedures.atic(parent_class.id) if a['id'] == stages[0].parent_structure_id)
    tp_data = {'new_stages': {}}
    trans_id = reg_funs.get_transact_id(stages[0].parent_structure_id, stages[0].parent_code, 'p')
    for s in stages:
        inc = {'class_id': s.parent_structure_id, 'location': 'contract', 'type': 'tp',
               'name': s.name_id, 'code': s.parent_code, 'value': deepcopy(s.value)}
        s.value['delay'] = [d for d in s.value['delay'] if d['date_create'] != date_create]
        tp_data['new_stages'][s.name_id] = {'delta': 1}
        s.save()
        # регистрация изменения объекта
        outc = inc.copy()
        outc['value'] = s.value
        reg = {'json': outc, 'json_income': inc}
        reg_funs.simple_reg(user_id, 15, timestamp, trans_id, parent_transact, **reg)
    return 'Задача удалена'