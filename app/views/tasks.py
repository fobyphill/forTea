from datetime import datetime
from django.contrib.auth import get_user_model
from django.shortcuts import render
from app.functions import session_funs, reg_funs, task_procedures, common_funs, view_procedures, files_funs, task_funs
from app.functions.task_funs import change_task_stage
from app.models import Tasks, ContractCells
from app.templatetags.my_filters import datetime_string_to_russian


@view_procedures.is_auth_app
def tasks(request):
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
        check_task = True if stage.kind == 'stage' else False
        change_task_stage(request.user.id, stage, timestamp, is_approve=True, check_task=check_task)

    elif 'b_cancel_stage' in request.POST:
        id = int(request.POST['b_cancel_stage'])
        transact_id = reg_funs.get_transact_id('task', id)
        task = Tasks.objects.filter(id=id)
        change_task_stage(request.user.id, task, timestamp, transact_id=transact_id)

    elif 'b_approve' in request.POST:
        recs = list(Tasks.objects.filter(code=request.POST['b_approve'], date_done__isnull=True))
        transact_id = reg_funs.get_transact_id('task', int(request.POST['b_approve']))
        for r in recs:
            check_task = True if recs.index(r) == len(recs) - 1 and r.kind == 'stage' else False
            change_task_stage(request.user.id, r, timestamp, is_approve=True, check_task=check_task, transact_id=transact_id)

    elif 'b_cancel' in request.POST:
        task_code = int(request.POST['b_cancel'])
        task_funs.task_full_delete(task_code, timestamp, request.user.id)

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

    to_me = False if 's_address' in request.POST and request.POST['s_address'] == 'from_me' else True # Адресация тасков
    phase_approved = True if 's_phase' in request.POST and request.POST['s_phase'] == 'approved' else False  #Фаза стадии таска

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
        tasks = list(Tasks.objects.filter(user_id=request.user.id, code__in=paginator['items_codes'],
                                          date_done__isnull=not phase_approved).values())
    else:
        tasks = list(Tasks.objects.filter(data__sender_id=request.user.id, code__in=paginator['items_codes'],
                                          date_done__isnull=not phase_approved).values())
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
        # dict_task = get_stage_task(tasks[0]) if tasks[0]['kind'] == 'stage' else get_prop_task(tasks[0])
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
                t['data'] = ' Пользователь ID:' + str(t['data']['sender_id']) + sender.first_name + ' ' + sender.last_name\
                            + ' запрашивает изменить стадию "' + t['data']['stage'] + '" на величину ' + str(t['data']['delta'])\
                            + '. fact = ' + str(t['data']['fact']) + ', state = ' + str(t['data']['state']) + ', delay = ' \
                            + str(t['data']['delay'])
            else:
                t['data'] = 'Пользователь ID: ' + str(t['data']['sender_id']) + ' ' + t['data']['sender_fio'] \
                            + ' запрашивает изменить свойство ID: ' + str(t['data']['name_id']) + ' на "' \
                            + str(t['data']['delay']) + '". Дата-время вступления изменений в силу: ' \
                            + datetime.strftime(t['date_delay'], '%d.%m.%Y %H:%M:%S')
            dict_task['recs'].append(t)
        list_tasks.append(dict_task)
    # сортируем по контракту-отправителю
    list_tasks = sorted(list_tasks, key=lambda x: x['parent_code'])
    session_funs.check_quant_tasks(request)
    ctx = {
            'title': "Мои задачи",
            'tasks': list_tasks,
            'paginator': paginator,
        }
    return render(request, 'tasks/task.html', ctx)