import copy
import json
from datetime import datetime
from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms import model_to_dict
from django.shortcuts import render
from app.functions import session_funs, reg_funs, task_procedures, common_funs, view_procedures, files_funs, task_funs, \
    tree_funs, database_funs, convert_funs2, interface_funs, class_funs, api_funs, contract_funs, session_procedures
from app.functions.task_funs import change_task
from app.models import Tasks, ContractCells, TaskClasses, Contracts, Designer, TechProcess, TechProcessObjects
from app.templatetags.my_filters import datetime_string_to_russian


@view_procedures.is_auth_app
def tasks(request):
    message = ''; message_class = ''
    timestamp = datetime.today()
    dict_kind = {'prop': 'Свойство', 'stage': 'Стадия', 'cf': 'Контрольное поле', 'cotc': 'Завершение контракта',
                 'do': 'Отложенный объект'}

    def get_stage_task(t):
        parent_code = t['data']['parent_code'] if 'parent_code' in t['data'] else None
        return {'code': t['code'], 'parent_code': parent_code, 'kind': dict_kind[t['kind']], 'loc': 'Техпроцесс',
         'class_id': t['data']['tp_id'], 'recs': []}

    dict_loc = {'t': 'Справочник', 'c': 'Контракт', 'p': 'Техпроцесс', 'd': 'Словарь'}

    def get_prop_task(t):
        return {'code': t['code'], 'parent_code': t['data']['code'], 'kind': dict_kind[t['kind']],
                'loc': dict_loc[t['data']['location']], 'class_id': t['data']['class_id'], 'recs': []}

    def get_cotc_task(t):
        return {'code': t['code'], 'parent_code': t['data']['code'], 'kind': dict_kind[t['kind']], 'loc': 'Контракт',
                'class_id': t['data']['class_id'], 'recs': []}

    if 'b_approve_stage' in request.POST:
        id = int(request.POST['b_approve_stage'])
        stage = Tasks.objects.get(id=id)
        check_task = stage.kind in ('stage', 'cotc')
        is_valid = True
        # Изменим данные свойства
        if not check_task:
            manager = Contracts.objects if stage.data['location'] == 'c' else Designer.objects
            header = manager.get(id=stage.data['name_id'])
            if header.formula != 'file':
                key_val = 'tag_' + str(stage.code)
                if header.formula == 'bool':
                    new_val = key_val in request.POST
                elif header.formula in ['link', 'const']:
                    new_val = int(request.POST[key_val])
                elif header.formula == 'float':
                    new_val = float(request.POST[key_val])
                    if new_val > stage.data['delay']:
                        new_val = stage.data['delay']
                else:
                    new_val = request.POST[key_val]
                stage.data['delay'] = new_val
        else:
            # для стадий проверим изменена ли дельта
            new_stage = float(request.POST[f'i_stage_{id}'])
            if new_stage != stage.data['quant']:
                # калькулятор стадий
                if abs(new_stage) > abs(stage.data['quant']):
                    is_valid = False
                    message = 'Нельзя увеличивать величину дельты<br>'
                    message_class = 'text-red'
                elif new_stage < 0:
                    is_valid = False
                    message = 'Нельзя задать дельту ниже нуля<br>'
                    message_class = 'test-red'
                else:

                    @transaction.atomic()
                    def change_delta(stage):
                    # зарегали изменение дельты
                        stage.data['quant'] = new_stage
                        stage.save()
                        # изменяем дельту на стадиях ТПса
                        tp_stages = TechProcessObjects.objects.filter(parent_code=stage.data['parent_code'],
                                                                      name_id__in=stage.data['rout'][:2]).select_related('name')
                        base_inc = {'class_id': stage.data['tp_id'], 'type': 'tp', 'location': 'contract',
                                    'code': stage.data['parent_code']}

                        tp_data = {'new_stages': {}}
                        stage_transact = reg_funs.get_transact_id(stage.data['tp_id'], stage.data['parent_code'], 'p')
                        for ts in tp_stages:
                            inc = base_inc.copy()
                            inc['name_id'] = ts.name_id
                            inc['value'] = copy.deepcopy(ts.value)
                            current_delay = next(d for d in ts.value['delay'] if d['date_create'] == stage.data['date_create'])
                            val_delay = new_stage if current_delay['value'] > 0 else new_stage * -1
                            tp_data['new_stages'][ts.name_id] = {'delta': val_delay}
                            current_delay['value'] = val_delay
                            ts.save()
                            outc = inc.copy()
                            outc['value'] = ts.value
                            reg = {'json': outc, 'json_income': inc}
                            reg_funs.simple_reg(request.user.id, 15, timestamp, stage_transact, **reg)
                        tp_info = next(tp for tp in session_procedures.atic(stage.data['class_id']) if tp['id'] == stage.data['tp_id'])
                        parent_class = Contracts.objects.get(id=stage.data['class_id'])
                        parent_headers = Contracts.objects.filter(parent_id=stage.data['class_id'], system=False).values()
                        contract_funs.do_tp_birulimators(tp_info, parent_class, parent_headers, stage.data['parent_code'],
                                                         tp_data, request.user.id, timestamp, stage_transact)

                    try:
                        change_delta(stage)
                    except Exception as ex:
                        is_valid = False
                        message = str(ex) + '<br>'
                        message_class = 'text-red'

        if is_valid:
            if stage.kind == 'stage':
                try:
                    task_funs.change_stage(stage, timestamp)
                except Exception as ex:
                    message = str(ex)
                    message_class = 'text-red'
            else:
                change_task(request.user.id, stage, timestamp, is_approve=True, check_task=check_task)

    elif 'b_cancel_stage' in request.POST:
        id = int(request.POST['b_cancel_stage'])
        transact_id = reg_funs.get_transact_id('task', id)
        task = Tasks.objects.get(id=id)
        change_task(request.user.id, task, timestamp, transact_id=transact_id)

    elif 'b_cancel' in request.POST:
        task_code = int(request.POST['b_cancel'])
        message = task_funs.task_full_delete(task_code, timestamp, request.user.id)
        if message.lower()[:6] == 'ошибка':
            message_class = 'text-red'

    # активация задачи
    elif 'b_active' in request.POST:
        code = int(request.POST['b_active'])
        task_active = Tasks.objects.filter(code=code)
        if task_active:
            list_tasks = []
            list_regs = []
            list_delay_cells = []
            inc = {'code': code, 'date_create': None}
            outc = inc.copy()
            outc['date_create'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            task_trans_id = reg_funs.get_transact_id('task', code)
            for ta in task_active:
                # изменим стадию таска
                ta.date_create = timestamp
                list_tasks.append(ta)
                # Регаем стадию таска
                income = inc.copy()
                income['id'] = ta.id
                outcome = outc.copy()
                outcome['id'] = ta.id
                task_reg = {'json_income': income, 'json': outcome}
                reg_dict_task = {'user_id': request.user.id, 'reg_id': 20, 'timestamp': timestamp, 'transact_id': task_trans_id,
                            'reg': task_reg}
                list_regs.append(reg_dict_task)
                # Заделеим стадию техпроцесса
                cf = ContractCells.objects.get(id=ta.data['control_field_id'])
                old_delay = cf.delay.copy()
                if type(cf.delay) is type(None):
                    cf.delay = []
                cf.delay.append({'value': ta.data['delay'], 'date_create': timestamp.strftime('%Y-%m-%d %H:%M:%S')})
                # регистрация изменения объекта
                obj_inc = {'class_id': cf.parent_structure_id, 'location': 'contract', 'type': 'techpro',
                       'name': cf.name_id, 'id': cf.id, 'code': cf.code, 'delay': old_delay}
                obj_outc = inc.copy()
                obj_outc['delay'] = cf.delay
                obj_reg = {'json': obj_outc, 'json_income': obj_inc}
                trans_id = reg_funs.get_transact_id(cf.parent_structure_id, cf.code, 'c')
                dict_reg_obj = {'user_id': request.user.id, 'reg_id': 15, 'timestamp': timestamp, 'transact_id': trans_id,
                            'parent_transact_id': task_trans_id, 'reg': obj_reg}
                list_regs.append(dict_reg_obj)
                list_delay_cells.append(cf)

            Tasks.objects.bulk_update(list_tasks, ('date_create',))
            ContractCells.objects.bulk_update(list_delay_cells, ('delay', ))
            reg_funs.paket_reg(list_regs)

    # Удаление задачи
    elif 'b_remove' in request.POST:
        code = int(request.POST['b_remove'])
        task_del = Tasks.objects.filter(code=code)
        task_trans_id = reg_funs.get_transact_id('task', code)
        task_procedures.tsdr(task_del, timestamp, request.user.id, task_trans_id)
        task_procedures.tdr(code, timestamp, request.user.id, task_trans_id)

    # Удаление пользовательской задачи
    elif 'b_cancel_custom' in request.POST:
        del_custom = Tasks.objects.get(id=int(request.POST['b_cancel_custom']))
        task_transact = reg_funs.get_transact_id(del_custom.data['class_id'], del_custom.code, 'z')
        task_funs.delete_simple_task(del_custom, timestamp, request.user.id, task_transact=task_transact)

    # Скачать файл
    elif 'b_save_file' in request.POST:
        my_task = Tasks.objects.get(code=int(request.POST['b_save_file']))
        file_name = my_task.data['delay']
        class_id = str(my_task.data['class_id'])
        is_contract = my_task.data['location'] == 'c'
        response = interface_funs.download_file(request, is_contract, file_name=file_name, class_id=class_id)
        if response:
            return response

    # Загрузить файл
    elif 'b_load_file' in request.POST:
        task_code = int(request.POST['b_load_file'])
        my_task = Tasks.objects.get(code=task_code)
        file_key = 'i_file_' + request.POST['b_load_file']
        file_name = request.FILES[file_key]
        res, v, msg = files_funs.upload_file(request, file_key, file_name, str(my_task.data['class_id']))
        if res == 'o':
            my_task.data['delay'] = v
            my_task.save()

    # Завершить контракт
    elif 'b_cotc' in request.POST:
        task_id = int(request.POST['b_cotc'])
        task_rec = Tasks.objects.get(id=task_id)
        class_id = task_rec.data['class_id']
        code = task_rec.data['code']
        task_rec.delete()  # Удалим таск
        # Удалим контракт
        api_funs.remove_object(class_id, code, request.user.id, 'contract', timestamp=timestamp)

    to_me = False if 's_address' in request.POST and request.POST['s_address'] == 'from_me' else True  # Адресация тасков
    phase_approved = 's_phase' in request.POST and request.POST['s_phase'] == 'approved'  #Фаза стадии таска

    # 1. Обращение к пагинатору
    q_items = int(request.POST['q_items_on_page']) if 'q_items_on_page' in request.POST else 10
    page_num = int(request.POST['page']) if 'page' in request.POST and request.POST['page'] else 1

    if to_me:
        codes = Tasks.objects.filter(user_id=request.user.id, date_create__isnull=False).values('code').distinct()
    else:
        codes = Tasks.objects.filter(data__sender_id=request.user.id, date_create__isnull=False).values('code').distinct()

    codes = codes.filter(date_done__isnull=not phase_approved)  # Фильтр по аппруву

    paginator = common_funs.paginator_object(codes, q_items, page_num)
    if to_me:
        customs = []
        tasks = list(Tasks.objects.filter(user_id=request.user.id, code__in=paginator['items_codes'],
                                          date_done__isnull=not phase_approved).exclude(kind='custom').values())
    else:
        tasks = list(Tasks.objects.filter(data__sender_id=request.user.id, code__in=paginator['items_codes'],
                                          date_done__isnull=not phase_approved).exclude(kind='custom').values())
        customs = list(Tasks.objects.filter(kind='custom', user_id=request.user.id).values())
        for c in customs:
            task_class = TaskClasses.objects.get(id=c['data']['class_id'])
            c['class_name'] = task_class.name
    list_tasks = []
    user_ids = list(dict.fromkeys([t['data']['sender_id'] for t in tasks]))
    users = get_user_model().objects.filter(id__in=user_ids)
    if tasks:
        if tasks[0]['kind'] == 'cotc':
            dict_task = get_cotc_task(tasks[0])
        elif tasks[0]['kind'] == 'stage' or tasks[0]['kind'] == 'cf' and not tasks[0]['date_delay']:
            dict_task = get_stage_task(tasks[0])
        else:
            dict_task = get_prop_task(tasks[0])
        for t in tasks:
            if t['code'] != dict_task['code']:
                list_tasks.append(dict_task.copy())
                if t['kind'] == 'cotc':
                    dict_task = get_cotc_task(t)
                elif t['kind'] == 'stage':
                    dict_task = get_stage_task(t)
                else:
                    dict_task = get_prop_task(t)
            sender = next(u for u in users if u.id == t['data']['sender_id'])
            if t['kind'] == 'cotc':
                t['data'] = 'Контракт класса ID: ' + str(t['data']['class_id']) + ', название: "' + t['data']['class_name'] \
                            +'" с кодом ' + str(t['data']['code']) + ' от ' + datetime_string_to_russian(t['data']['date_time_rec']) + \
                  ' был выполнен после изменения пользователем ID: ' + str(t['data']['sender_id']) + '. Теперь контракт можно удалить'
            elif t['kind'] == 'stage':
                t['info'] = {'delta': t['data']['quant'], 'partners': t['data']['rout'][:2]}
                object_stages = TechProcessObjects.objects.filter(name_id__in=t['data']['rout'][:2],
                                                                  parent_code=t['data']['parent_code']).select_related('name')
                val = None
                for r in t['data']['rout'][:2]:
                    os = next(os for os in object_stages if os.name_id == r)
                    current_delay = next(d for d in os.value['delay'] if d['date_create'] == t['data']['date_create'])
                    if not current_delay['approve']:
                        val = os.value
                        break
                delay = sum(d['value'] for d in val['delay'])
                state = delay + val['fact']
                up_down = 'увеличить' if current_delay['value'] > 0 else 'уменьшить'
                t['data'] = ' Пользователь ID:' + str(t['data']['sender_id']) + sender.first_name + ' ' + sender.last_name\
                            + f' запрашивает {up_down} стадию "' + str(t['data']['rout'][0]) + '" на величину ' + str(t['data']['quant'])\
                            + '. fact = ' + str(val['fact']) + ', state = ' + str(state) + ', delay = ' + str(delay)
            else:
                t['data'] = 'Пользователь ID: ' + str(t['data']['sender_id']) + ' ' + t['data']['sender_fio'] \
                            + ' запрашивает изменить свойство ID: ' + str(t['data']['name_id']) + ' на "' \
                            + str(t['data']['delay']) + '". Дата-время вступления изменений в силу: ' \
                            + datetime.strftime(t['date_delay'], '%d.%m.%Y %H:%M:%S') \
                            + convert_funs2.tadatoda(t['data']['location'], t['data']['name_id'], t['code'],
                                                     t['data']['delay'], t['user_id'])
            dict_task['recs'].append(t)
        list_tasks.append(dict_task)
    # сортируем по контракту-отправителю
    list_tasks = sorted(list_tasks, key=lambda x: x['parent_code'])
    session_funs.check_quant_tasks(request)
    ctx = {
            'title': "Мои задачи",
            'tasks': list_tasks,
            'customs': customs,
            'paginator': paginator,
            'message': message,
            'message_class': message_class
        }
    return render(request, 'tasks/task.html', ctx)


@view_procedures.is_auth_app
def manage_tasks(request):
    message = ''
    message_class = ''
    if not 'task_tree' in request.session:
        request.session['task_tree'] = task_funs.update_task_tree()
    my_unit = {}
    tree = []
    is_search = False
    search_field = request.POST['i_search'] if 'i_search' in request.POST else ''
    if 'select_node' in request.POST:
        my_unit = tree_funs.find_branch(request.session['task_tree'], 'id', int(request.POST['select_node']))
        if my_unit['kind'] == 'folder':
            my_unit['opened'] = not my_unit['opened']
        else:
            tree_funs.open_branch(my_unit, request.session['task_tree'], parent_name='parent_id', code_or_id='id')
        search_field = ''
    elif 'b_save' in request.POST:
        timestamp = datetime.today()
        parent = int(request.POST['i_parent']) if request.POST['i_parent'] else None
        if parent and not TaskClasses.objects.filter(id=parent, kind='folder'):
            message = 'Некорректно указан ID родителя. Укажите ID класса с видом "каталог"<br>'
            message_class = 'text-red'
        else:
            link_map = json.loads(request.POST['i_linkmap'])
            # Редактируем класс
            if request.POST['i_task_id']:
                task_id = int(request.POST['i_task_id'])
                task = TaskClasses.objects.get(id=task_id)
                is_change = False
                inc = {'class_id': task_id, 'location': 'task', 'type': task.kind}
                outc = inc.copy()
                if task.name != request.POST['i_name']:
                    is_change = True
                    inc['name'] = task.name
                    outc['name'] = request.POST['i_name']
                    task.name = request.POST['i_name']
                if parent != task.parent_id:
                    is_change = True
                    inc['parent'] = task.parent_id
                    outc['parent'] = parent
                    task.parent_id = parent
                if task.br != request.POST['ta_br']:
                    is_change = True
                    inc['business_rule'] = task.br
                    outc['business_rule'] = request.POST['ta_br']
                    task.br = request.POST['ta_br']
                if task.lm != link_map:
                    is_change = True
                    inc['link_map'] = task.lm
                    outc['link_map'] = link_map
                    task.lm = link_map
                if task.tr != request.POST['ta_tr']:
                    is_change = True
                    inc['trigger'] = task.tr
                    outc['trigger'] = request.POST['ta_tr']
                    task.tr = request.POST['ta_tr']
                if is_change:
                    task.save()
                    reg = {'json_income': inc, 'json': outc}
                    transact_id = reg_funs.get_transact_id(task_id, 0, 'z')
                    reg_funs.simple_reg(request.user.id, 3, timestamp, transact_id, **reg)
                    message = 'Класс ID: ' + request.POST['i_task_id'] + ' был изменен. Изменения сохранены'
                    request.session['task_tree'] = task_funs.update_task_tree()
                else:
                    message = 'Вы не внесли изменений. Класс не сохранен'
            # Создаем новый
            else:
                kind = 'custom' if request.POST['sel_kind'] == 'task' else 'folder'
                task = TaskClasses(name=request.POST['i_name'], kind=kind, parent_id=parent,
                                    br=request.POST['ta_br'], lm=link_map, tr=request.POST['ta_tr'])
                task.save()
                outc = {'class_id': task.id, 'name': task.name, 'type': task.kind, 'location': 'task',
                        'parent': task.parent_id, 'link_map': task.lm, 'business_rule': task.br,
                        'trigger': task.tr}
                reg = {'json': outc}
                transact_id = reg_funs.get_transact_id(task.id, 0, 'z')
                reg_funs.simple_reg(request.user.id, 1, timestamp, transact_id, **reg)
                request.session['task_tree'] = task_funs.update_task_tree()
                message = 'Создан новый класс. ID: ' + str(task.id) + '<br>' + \
                    'Вид: "' + task.kind + '"<br>' + \
                    'Наименование: "' + task.name + '"'
            my_unit = tree_funs.find_branch(request.session['task_tree'], 'id', task.id)
            tree_funs.open_branch(my_unit, request.session['task_tree'], parent_name='parent_id', code_or_id='id')
    elif 'b_delete' in request.POST:
        task_id = int(request.POST['i_task_id'])
        task = tree_funs.find_branch(request.session['task_tree'], 'id', task_id)
        is_valid = True
        if task['kind'] == 'folder':
            if tree_funs.retreive_branch_children(task):
                is_valid = False
                message += 'Нельзя удалить каталог, у которого есть дочерние классы - каталоги, задачи<br>'
        # проверим, может есть задания, ждущие выполнения
        if Tasks.objects.filter(kind='custom', data__class_id=task_id):
            message += 'Нельзя удалить задачу, поскольку есть ее экземпляры в работе<br>'
            is_valid = False
        if not is_valid:
            message_class = 'text-red'
            my_unit = task
        else:
            timestamp = datetime.today()
            kind = task['kind']
            inc = {'class_id': task['id'], 'location': 'task', 'type': task['kind'], 'parent': task['parent_id'],
                   'business_rule': task['br'], 'link_map': task['lm'], 'trigger': task['tr'], 'name': task['name']}
            reg = {'json_income': inc}
            transact_id = reg_funs.get_transact_id(task_id, 0, 'z')
            reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
            del_task = TaskClasses.objects.get(id=task_id)
            parent = del_task.parent_id
            del_task.delete()
            tree_funs.del_branch(request.session['task_tree'], task_id, param_name='id')
            if parent:
                my_unit = tree_funs.find_branch(request.session['task_tree'], 'id', parent)
                tree_funs.open_branch(my_unit, request.session['task_tree'], parent_name='parent_id', code_or_id='id')
            message = 'Класс ID: ' + request.POST['i_task_id'] + ' успешно удален'
            class_funs.dndi_task_fta(task_id, kind)
    elif 'b_make_object' in request.POST:
        timestamp = datetime.today()
        task_id = int(request.POST['i_task_id'])
        my_unit = tree_funs.find_branch(request.session['task_tree'], 'id', task_id)
        code = database_funs.get_code(task_id, 'task')
        data = {'class_id': task_id, 'br': my_unit['br'], 'lm': my_unit['lm'], 'tr': my_unit['tr']}
        task_object = Tasks(date_create=timestamp, user_id=request.user.id, code=code, kind='custom', data=data)
        task_object.save()
        # Регистрация таска
        outc = {'code': code, 'location': 'task', 'type': 'custom', 'class_id': task_id}
        reg = {'json': outc}
        transact_id = reg_funs.get_transact_id(task_id, code, 'z')
        reg_funs.simple_reg(request.user.id, 17, timestamp, transact_id, **reg)
        # регистрация записи таска
        outc['id'] = task_object.id
        outc['data'] = data
        outc['date_create'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S')
        outc['user_id'] = request.user.id
        reg_funs.simple_reg(request.user.id, 18, timestamp, transact_id, **reg)
        message = 'Поставлена задача. Код: ' + str(code) + '. Класс ID: ' + request.POST['i_task_id']
    # не использую щас. Удалить после 15.12.2024
    # elif 'b_delete_object' in request.POST:
    #     timestamp = datetime.today()
    #     task_id = int(request.POST['i_task_id'])
    #     my_unit = tree_funs.find_branch(request.session['task_tree'], 'id', task_id)
    #     task_object = Tasks.objects.filter(data__class_id=task_id)
    #     if task_object:
    #         task_object = task_object[0]
    #         # Регистрация удаления таска
    #         outc = {'code': task_object.code, 'class_id': task_id, 'location': 'task', 'type': 'custom'}
    #         reg = {'json': outc}
    #         transact_id = reg_funs.get_transact_id(task_id, task_object.code, 'z')
    #         reg_funs.simple_reg(request.user.id, 21, timestamp, transact_id, **reg)
    #         # регистрация удаления записи таска
    #         outc['id'] = task_object.id
    #         outc['data'] = task_object.data
    #         reg_funs.simple_reg(request.user.id, 19, timestamp, transact_id, **reg)
    #         message = 'Удалена задача. Код: ' + str(task_object.code) + '. Класс ID: ' + request.POST['i_task_id']
    #         task_object.delete()
    elif 'b_search' in request.POST and request.POST['i_search']:
        is_search = True
        search_result = tree_funs.filter_branches(request.session['task_tree'], 'name', request.POST['i_search'], is_part=True)
        try:
            task_id = int(request.POST['i_search'])
        except ValueError:
            pass
        else:
            search_result += tree_funs.filter_branches(request.session['task_tree'], 'id', task_id)
        for sr in search_result:
            copy_sr = sr.copy()
            if 'children' in copy_sr:
                copy_sr.pop('children')
            tree.append(copy_sr)
    if not is_search:
        tree = request.session['task_tree']
    if not my_unit and tree and not is_search:
        my_unit = tree[0]
    ctx = {
        'message': message,
        'message_class': message_class,
        'my_unit': my_unit,
        'tree': tree,
        'search_field': search_field
    }
    session_funs.check_quant_tasks(request)
    return render(request, 'constructors/manage-tasks.html', ctx)