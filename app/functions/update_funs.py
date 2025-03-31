import datetime
import copy
import os
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms import model_to_dict

from app.functions import reg_funs, task_funs, contract_funs, interface_procedures, task_procedures, api_funs, \
    interface_funs, files_funs, convert_funs, convert_funs2, session_procedures, hist_funs
from app.models import Tasks, ContractCells, Objects, Registrator, TechProcess, TechProcessObjects, Contracts, Designer, \
    ContractDrafts, TableDrafts

from app.other.global_vars import root_folder


def run_delays(props=None):
    datetime_now = datetime.datetime.today()
    upd_to_log('азаза',  datetime_now)
    if not props:
        props = Tasks.objects.filter(kind='prop', date_done__isnull=False, date_delay__lte=datetime_now)\
            .order_by('date_delay', 'id')
    for p in props:
        obj_manager = ContractCells.objects if p.data['location'] == 'c' else Objects.objects
        # task_transact = reg_funs.get_transact_id('task', p.code)
        obj_transact = reg_funs.get_transact_id(p.data['class_id'], p.data['code'], p.data['location'])
        timestamp = p.date_done if p.date_delay < p.date_done else p.date_delay
        obj = obj_manager.get(parent_structure_id=p.data['class_id'], code=p.data['code'], name_id=p.data['name_id'])
        if obj.name.formula == 'float':
            obj_new_val = p.data['delay'] + obj.value if obj.value else p.data['delay']
        else:
            obj_new_val = p.data['delay']
        date_delay = datetime.datetime.strftime(p.date_delay, '%Y-%m-%dT%H:%M')
        old_val = obj.value
        old_delay = copy.deepcopy(obj.delay)
        now_delay = {'approve': True, 'date_update': date_delay, 'value': p.data['delay']}
        new_delay = [od for od in old_delay if od != now_delay]
        obj.value = obj_new_val
        obj.delay = new_delay

        # для контрактов выполним системные функции - BR, LM, Tr
        res = 'ok'
        if obj.parent_structure.formula == 'contract':
                class_manager = Contracts.objects if p.data['location'] == 'c' else Designer.objects
                current_class = class_manager.get(id=p.data['class_id'])
                all_params = list(Contracts.objects.filter(parent_id=p.data['class_id']).exclude(formula='array').values())
                headers = []
                system_params = []
                for ap in all_params:
                    if ap['system']:
                        system_params.append(ap)
                    else:
                        headers.append(ap)
                edit_obj = {'new_obj': obj, 'old_delay': old_delay, 'old_value': old_val}
                object_user = get_user_model().objects.get(id=p.data['sender_id'])
                try:
                    edit_objs = [edit_obj]
                    contract_funs.edit_contract(current_class, p.data['code'], headers, system_params, [], edit_objs,
                                                [], object_user, timestamp, transact_id=obj_transact)
                except Exception as ex:
                    res = str(ex)
        else:
            location = 'contract' if p.data['location'] == 'c' else 'table'
            inc = {'class_id': p.data['class_id'], 'location': location, 'type': obj.parent_structure.formula,
                   'code': p.data['code'], 'name': p.data['name_id']}
            outc = inc.copy()
            inc_delay = inc.copy()
            outc_delay = inc.copy()
            inc['value'] = old_val
            outc['value'] = obj_new_val
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(p.data['sender_id'], 15, timestamp, obj_transact, **reg)
            inc_delay['delay'] = old_delay
            outc_delay['delay'] = new_delay
            reg = {'json': outc_delay, 'json_income': inc_delay}
            reg_funs.simple_reg(p.data['sender_id'], 22, timestamp, obj_transact, **reg)
            obj.save()

        if res == 'ok':
            # Изменим первые стадии всех подчиненных ТПсов
            if 'cf' in p.data and p.data['cf']:
                tps = TechProcess.objects.filter(formula='tp', parent_id=p.data['class_id'], value__control_field=p.data['name_id'])
                for t in tps:
                    header_stage_0 = TechProcess.objects.filter(parent_id=t.id).exclude(settings__system=True)[0]
                    stage_0 = TechProcessObjects.objects.filter(parent_structure_id=t.id, name_id=header_stage_0.id,
                                                                parent_code=p.data['code'])[0]
                    inc = {'class_id': t.id, 'location': 'contract', 'type': 'tp', 'id': stage_0.id,
                           'name': header_stage_0.id, 'value': copy.deepcopy(stage_0.value)}
                    outc = inc.copy()
                    stage_0.value['fact'] += p.data['delay']
                    stage_0.save()
                    outc['value'] = stage_0.value
                    reg = {'json': outc, 'json_income': inc}
                    reg_funs.simple_reg(p.data['sender_id'], 15, timestamp, obj_transact, **reg)
            p.delete()
        else:
            p.data['error'] = res
            task_funs.delete_simple_task(p, timestamp, 1)

    # Запустим отложенные объекты
    delay_object_tasks = Tasks.objects.filter(kind='do', date_delay__lte=datetime_now)
    for dot in delay_object_tasks:
        is_contract = dot.data['location'] == 'contract'
        obj_manager = ContractCells.objects if is_contract else Objects.objects
        obj_create = ContractCells if is_contract else Objects
        class_manager = Contracts.objects if is_contract else Designer.objects
        task_transact = reg_funs.get_transact_id('task', dot.code)
        timestamp = dot.date_delay
        params = {'parent_transact': task_transact, 'timestamp': timestamp}
        draft_arrays = []
        draft_ids = [dot.data.pop('draft_id')]
        files = []
        dict_post = {}
        new_objs = []
        tps = []
        for dk, dv in dot.data.items():
            if dk[:10] == 'i_filename':
                files.append({'header': int(dk[11:]), 'value': dv, 'class': dot.data['parent_structure'],
                              'type': dot.data['location'], 'code': dot.data['code'], 'draft_id': draft_ids[0]})
            elif re.match(r'array\d+', dk):
                array_id = int(dk[5:])
                draft_arrays.append({'array_id': array_id, 'value': dv})
                draft_ids += [d['draft_id'] for d in dv]
            elif dk == 'branch':
                params['parent'] = dv
            elif dk[:8] == 'draft_id':
                continue
            elif dk[:9] == 'dict_info':
                dict_post[dk] = dv
            elif dk[:3] == 'tp_':
                tps.append({'id': int(dk[3:]), 'stages': dv})
            elif dk not in ('parent_structure', 'location', 'type', 'code'):
                params[dk] = dv
        # Сохраним все атомарно
        @transaction.atomic
        def save_all():
            is_error = False
            if dot.data['code']:
                result = api_funs.edit_object(dot.data['parent_structure'], dot.data['code'], dot.user_id,
                                              dot.data['location'], **params)
            else:
                result = api_funs.create_object(dot.data['parent_structure'], dot.user_id, dot.data['location'], **params)

            if type(result) is str and result.lower()[:6] == 'ошибка':
                is_error = True
            else:
                if not dot.data['code']:
                    code = result[0].code
                    # для всех новых объектов добавим связь между кодом и черновиком его породившим
                    new_obj = {'draft_id': draft_ids[0], 'code': code}
                    new_objs.append(new_obj)
                else:
                    code = dot.data['code']
                for da in draft_arrays:
                    owner_id = str(class_manager.get(parent_id=da['array_id'], name='Собственник').id)
                    files_ids = [str(cm.id) for cm in class_manager.filter(parent_id=da['array_id'], formula='file')]
                    for el in da['value']:
                        el_params = {'parent_transact': task_transact, 'timestamp': timestamp}
                        tps = []
                        for elk, elv in el.items():
                            if elk == owner_id:
                                if el['code']:
                                    continue
                                else:
                                    el_params['owner'] = dot.data['code']
                            elif elk in ('branch', 'draft_id'):
                                continue
                            elif elk in files_ids:
                                fileval = elv['value'] if elv else ''
                                files.append({'header': int(elk), 'value': fileval, 'class': da['array_id'],
                                              'type': 'array', 'code': el['code'], 'draft_id': el['draft_id']})
                            elif elk not in ('parent_structure', 'location', 'type', 'code'):
                                if elv:
                                    for ek, ev in elv.items():
                                        if ek[:5] == 'tp_id':
                                            tps.append({'id': int(ek[5:]), 'value': ev})
                                    el_params[elk] = elv['value']
                                else:
                                    el_params[elk] = None
                            elif elk[:3] == 'tp_':
                                tps.append({'id': int(elk[5:]), 'value': elv})
                        if el['code']:
                            array_result = api_funs.edit_object(da['array_id'], el['code'], dot.user_id, dot.data['location'],
                                                          **el_params)
                        else:
                            array_result = api_funs.create_object(da['array_id'], dot.user_id, dot.data['location'], **el_params)
                        if type(array_result) is str and array_result.lower()[:6] == 'ошибка':
                            is_error = True
                            break
                        elif not el['code']:
                            # для всех новых объектов добавим связь между кодом и черновиком его породившим
                            new_obj = {'draft_id': el['draft_id'], 'code': array_result[0].code}
                            new_objs.append(new_obj)
                        # Техпроцессы на объекте массива
                        for tp in tps:
                            tp_res = api_funs.edit_object(tp['id'], el['code'], dot.user_id, 'tp',
                                                          parent_transact=task_transact, timestamp=timestamp, **tp['value'])
                            if type(tp_res) is str and tp_res.lower()[:6] == 'ошибка':
                                is_error = True
                                break
                        else:
                            continue
                        break
                    else:
                        continue
                    break
            if is_error:
                raise Exception()
            return result

        draft_manager = ContractDrafts.objects if is_contract else TableDrafts.objects
        try:
            obj = save_all()
        except Exception as ex:
            # Включим черновики
            drafts = draft_manager.filter(id__in=draft_ids)
            for d in drafts:
                d.active = True
            draft_manager.bulk_update(drafts, ['active'])
        else:
            # Загрузим словари. У словарей нет противоречий. Их загружаем безусловно, если все остальное загрузилось
            obj_code = dot.data['code'] if dot.data['code'] else obj[0].code
            if dict_post:
                my_request = interface_procedures.marefrod(dot.data['parent_structure'], is_contract, **dict_post)
                my_request.user.id = dot.user_id
                interface_funs.save_dict(my_request, obj_code, task_transact, timestamp)
            # Загрузим файлы
            for f in files:
                obj_file = obj_manager.filter(parent_structure_id=f['class'], code=f['code'], name_id=f['header'])
                if obj_file:
                    obj_file = obj_file[0]
                    if obj_file.value != f['value']:
                        if f['value']:
                            new_val = files_funs.cffdth(f['value'], f['class'], location=dot.data['location'])
                        else:
                            new_val = ''
                        income = {'class_id': f['class'], 'code': f['code'], 'location': dot.data['location'],
                                  'type': f['type'], 'id': obj_file.id, 'name': obj_file.name_id,
                                  'value': obj_file.value}
                        outcome = income.copy()
                        outcome['value'] = new_val
                        reg = {'json_income': income, 'json': outcome}
                        transact_id = reg_funs.get_transact_id(f['class'], f['code'], dot.data['location'][0])
                        reg_funs.simple_reg(dot.user_id, 15, timestamp, transact_id, task_transact, **reg)
                        obj_file.value = new_val
                        obj_file.save()
                elif f['value']:
                    my_code = f['code'] if f['code'] else next(no['code'] for no in new_objs if no['draft_id'] == f['draft_id'])
                    new_val = files_funs.cffdth(f['value'], f['class'], location=dot.data['location'])
                    obj_file = obj_create(parent_structure_id=f['class'], code=my_code, name_id=f['header'], value=new_val)
                    obj_file.save()
                    outcome = {'class_id': f['class'], 'code': my_code, 'location': dot.data['location'],
                               'type': f['type'], 'id': obj_file.id, 'name': obj_file.name_id, 'value': obj_file.value}
                    reg = {'json': outcome}
                    transact_id = reg_funs.get_transact_id(f['class'], obj_code, dot.data['location'][0])
                    reg_funs.simple_reg(dot.user_id, 13, timestamp, transact_id, task_transact, **reg)
            # Удалим черновики
            draft_manager.filter(id__in=draft_ids).delete()
        obj = model_to_dict(dot)
        obj['date_create'] = datetime.datetime.strftime(obj['date_create'], '%Y-%m-%dT%H:%M:%S')
        obj['date_delay'] = datetime.datetime.strftime(obj['date_delay'], '%Y-%m-%dT%H:%M:%S')
        reg = {'json_income': obj}
        reg_funs.simple_reg(obj['user'], 19, timestamp, task_transact, **reg)
        reg = {'json_income': {'code': obj['code']}}
        reg_funs.simple_reg(obj['user'], 21, timestamp, task_transact, **reg)
        dot.delete()
    # Запустим кастомные таски
    customs = Tasks.objects.filter(kind='custom')
    for c in customs:
        task_transact = reg_funs.get_transact_id(c.data['class_id'], c.code, 'z')
        try:
            result = task_funs.do_custom_task(copy.deepcopy(c), timestamp=datetime_now, parent_transact=task_transact)
        except Exception as ex:
            result = True
        if result:
            task_funs.delete_simple_task(c, datetime_now, 1, task_transact=task_transact)


def run_clean_hist(date_from, date_to):
    time_start = datetime.datetime.today()
    result = ''
    try:
        list_objs = hist_funs.get_all_objs(date_from, date_to)
        for lo in list_objs:
            hist_funs.clean_object_hist(lo['json_class'], lo['code'], lo['location'][0], date_from, date_to)
        time_end = datetime.datetime.today()
        time_delta = time_end - time_start
    except Exception as ex:
        result = 'Ошибка' + str(ex)
        time_delta = None
    else:
        date_from = date_from.strftime('%d.%m.%Y %H:%M:%S')
        date_to = date_to.strftime('%d.%m.%Y %H:%M:%S')
        result = f'ok. Очищена история в ' + str(len(list_objs)) + f' объектах. а период с {date_from} по {date_to}. '

    format_timedelta = ''
    if time_delta.days:
        format_timedelta = '%d дней '
    format_timedelta += '%H:%M:%S'
    str_run_time = (datetime.datetime(1, 1, 1) + time_delta).strftime(format_timedelta)
    result += f'Время выполнения операции - {str_run_time} \n'
    with open(os.path.join(root_folder, 'log.txt'), "a") as myfile:
        myfile.write(result)


# тестовый апдейт
def test_upd(a):
    print(a)


def upd_to_log(text, today):
    log_path = os.path.join(root_folder, 'log.txt')
    with open(log_path, "a") as myfile:
        myfile.write(text + ' ' + datetime.datetime.strftime(today, '%d.%m.%Y %H:%M:%S') + '\n')