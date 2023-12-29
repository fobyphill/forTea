from datetime import datetime

from django.forms import model_to_dict

from app.functions import reg_funs


# регистрация удаления всех записей таска tsdr = task stage delete registrate
def tsdr(task_whole, timestamp, user_id, task_transact, parent_transact=None):
    list_task_del = []
    for tw in task_whole:
        date_create = tw.date_create.strftime('%Y-%m-%d %H:%M:%S') if tw.date_create else None
        date_done = tw.date_done.strftime('%Y-%m-%d %H:%M:%S') if tw.date_done else None
        inc = {'data': tw.data, 'date_create': date_create,
               'date_done': date_done, 'user_id': user_id, 'code': tw.code, 'id': tw.id}
        reg = {'json_income': inc}
        dict_reg = {'user_id': user_id, 'reg_id': 19, 'timestamp': timestamp, 'transact_id': task_transact,
                    'parent_transact': parent_transact, 'reg': reg}
        list_task_del.append(dict_reg)
    inc_task = {'code': task_whole[0].code}
    reg_task = {'json': inc_task}
    dict_reg_task = {'user_id': user_id, 'reg_id': 21, 'timestamp': timestamp, 'transact_id': task_transact,
                    'parent_transact': parent_transact, 'reg': reg_task}
    list_task_del.append(dict_reg_task)
    reg_funs.paket_reg(list_task_del)
    task_whole.delete()


# регистрация удаления таска tdr = task delete registrate
def tdr(code, timestamp, user_id, transact_id, parent_transact):
    inc = {'code': code}
    reg = {'json_income': inc}
    reg_funs.simple_reg(user_id, 21, timestamp, transact_id, parent_transact, **reg)

# comotatodi = convert model task to dict
def comotatodi(task):
    dict_task = model_to_dict(task)
    dict_task['date_create'] = datetime.strftime(dict_task['date_create'], '%Y-%m-%dT%H:%M:%S')
    dict_task['date_delay'] = datetime.strftime(dict_task['date_delay'], '%Y-%m-%dT%H:%M:%S') if dict_task['date_delay'] else None
    dict_task['date_done'] = datetime.strftime(dict_task['date_done'], '%Y-%m-%dT%H:%M:%S') if dict_task['date_done'] else None
    return dict_task