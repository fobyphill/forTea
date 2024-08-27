import datetime
import copy
import re

from django.db import transaction
from django.forms import model_to_dict

from app.functions import reg_funs, task_funs, contract_funs, interface_procedures, task_procedures, api_funs, \
    interface_funs, files_funs
from app.models import Tasks, ContractCells, Objects, Registrator, TechProcess, TechProcessObjects, Contracts, Designer, \
    ContractDrafts, TableDrafts


def run_delays(props=None):
    datetime_now = datetime.datetime.today()
    if not props:
        props = Tasks.objects.filter(kind='prop', date_done__isnull=False, date_delay__lte=datetime_now)\
            .order_by('date_delay', 'id')
    if props:
        for p in props:
            obj_manager = ContractCells.objects if p.data['location'] == 'c' else Objects.objects
            task_transact = reg_funs.get_transact_id('task', p.code)
            obj_transact = reg_funs.get_transact_id(p.data['class_id'], p.data['code'], p.data['location'])
            timestamp = p.date_done if p.date_delay < p.date_done else p.date_delay
            obj = obj_manager.get(parent_structure_id=p.data['class_id'], code=p.data['code'], name_id=p.data['name_id'])
            if obj.name.formula == 'float':
                obj_new_val = p.data['delay'] + obj.value if obj.value else p.data['delay']
            else:
                obj_new_val = p.data['delay']

            # для контрактов выполним системные функции - BR, LM, Tr
            res = 'ok'
            if p.data['location'] == 'c':
                headers = list(Contracts.objects.filter(parent_id=p.data['class_id'])\
                    .exclude(formula__in=('array', 'business_rule', 'link_map', 'trigger')).values())
                dict_object = {'code': p.data['code'], 'parent_structure': p.data['class_id'], obj.name_id: obj_new_val}

                if obj.parent_structure.formula == 'contract':
                    res = contract_funs.dcsp(p.data['class_id'], p.data['code'], headers, p.data['sender_id'], dict_object,
                                             {}, timestamp, obj_transact)

            date_delay = datetime.datetime.strftime(p.date_delay, '%Y-%m-%dT%H:%M')
            loc4hist = 'contract' if p.data['location'] == 'c' else 'table'
            inc = {'class_id': p.data['class_id'], 'location': loc4hist, 'code': p.data['code'], 'type': obj.name.parent.formula,
                   'name': p.data['name_id'], 'id': obj.id, 'value': obj.value}
            inc_delay = inc.copy()
            inc_delay['delay'] = obj.delay.copy()
            del inc_delay['value']
            if res == 'ok':
                obj.value = obj_new_val
                outc = inc.copy()
                outc['value'] = obj.value
                reg = {'json': outc, 'json_income': inc}
                reg_funs.simple_reg(p.data['sender_id'], 15, timestamp, obj_transact, task_transact, **reg)
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
                        reg_funs.simple_reg(p.data['sender_id'], 15, timestamp, obj_transact, task_transact, **reg)
            else:
                p.data['error'] = res
            obj.delay = [od for od in obj.delay if od['date_update'] != date_delay or od['value'] != p.data['delay']]
            obj.save()
            outc_delay = inc_delay.copy()
            outc_delay['delay'] = obj.delay
            reg_delay = {'json': outc_delay, 'json_income': inc_delay}
            reg_funs.simple_reg(p.data['sender_id'], 22, timestamp, obj_transact, task_transact, **reg_delay)
            task_funs.delete_simple_task(p, timestamp, task_transact=task_transact)
        upd_to_log(datetime_now)
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

# тестовый апдейт
def test_upd():
    today = datetime.datetime.today()
    Registrator(user_id=4, reg_name_id=14, date_update=today).save()
    upd_to_log(today)


def upd_to_log(today):
    with open("log.txt", "a") as myfile:
        myfile.write("Запись в БД " + datetime.datetime.strftime(today, '%d.%m.%Y %H:%M:%S') + '\n')