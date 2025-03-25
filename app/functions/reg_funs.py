import json
import re
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.forms import model_to_dict

from app.functions import server_funs, database_funs
from app.models import Registrator, RegistratorLog, ErrorsLog, RegName


# Создать запись в простом регистраторе. т.е. без отложенных значений
# Вход - пользователь, айди регистратора, таймштамп(датавремя операции), айди транзакции и родительской транзакции,
# словарь с параметрами
# Если заданы пустые поля json_string и json_string_income - конвертируем джейсон и джейсон инкам
def simple_reg(user_id, reg_id, timestamp, transact_id, parent_transact_id=None, **reg):
    try:
        # Сбор данных
        if not 'state_income' in reg:    reg['state_income'] = None
        if not 'state' in reg:    reg['state'] = None
        if not 'fact_income' in reg:    reg['fact_income'] = None
        if not 'fact' in reg:    reg['fact'] = None
        if not 'delay_income' in reg:    reg['delay_income'] = None
        if not 'delay' in reg:    reg['delay'] = None
        if not 'json_income' in reg: reg['json_income'] = None
        if not 'json' in reg: reg['json'] = None
        if not 'date_delay' in reg:  reg['date_delay'] = None

        # Запись в истории
        log = RegistratorLog(reg_name_id=reg_id)
        log.state_income = reg['state_income']
        log.state = reg['state']
        log.fact_income = reg['fact_income']
        log.fact = reg['fact']
        log.delay_income = reg['delay_income']
        log.delay = reg['delay']
        log.json_income = reg['json_income']
        log.json = reg['json']
        log.transact_id = transact_id
        log.parent_transact_id = parent_transact_id
        log.date_update = timestamp
        log.date_delay = reg['date_delay']
        log.user_id = user_id
        class_id = None
        if reg['json'] and 'class_id' in reg['json']:
            class_id = reg['json']['class_id']
        elif reg['json_income'] and 'class_id' in reg['json_income']:
            class_id = reg['json_income']['class_id']
        log.json_class = class_id
        log.save()
        return True
    except Exception as e:
        error = ErrorsLog()
        error.name = 'Ошибка выполнения простого регистратора. ' + str(e)
        error.date_time_error = datetime.today()
        error.save()
        text_letter = error.name + '. Дата и время выполнения: ' + error.date_time_error.strftime('%d.%m.%Y %H:%M:%S')\
        + '. ID регистратора: ' + str(reg_id) + '. ID пользователя: ' + str(user_id)
        server_funs.send_mail('pricepro@f-trade.ru', 'ошибка простого регистратора', text_letter)
        return False


# Создать регистратор. Создает заголовой регистратора и пустую запись регистратора со ссылкой на заголовок.
# Вход - строка-заголовок. Выход. Айди регистратора
def make_reg_console():
    input_name = input("Задайте имя регистратора: ")
    new_reg_name = RegName(name=input_name)
    try:
        new_reg_name.save()
    except ValueError:
        return 'Некорректно указаны данные. Регистратор не создан'
    registrator = Registrator(user_id=6, reg_name_id=new_reg_name.id)
    registrator.save()
    return 'Регистратор создан. Имя - ' + input_name + '. Номер регистратора = ' + str(new_reg_name.id)


def make_reg(reg_name, user_id):
    new_reg_name = RegName(name=reg_name)
    new_reg_name.save()
    registrator = Registrator(user_id=user_id, reg_name_id=new_reg_name.id)
    registrator.save()
    return new_reg_name.id


# Получить текущую ID транзации истории для конкретного кода конкретного класса
# Вход: class_id, code, location = [t, c, d, p, z] - table, contract, dict, tp, task(z)
def get_transact_id(class_id, code, location='t'):
    if class_id == 'task':
        template_transact = class_id + str(code) + 'id'
        last_transact = RegistratorLog.objects.filter(transact_id__contains=template_transact).values('transact_id')\
            .distinct().order_by('-id')[:1]
        if last_transact:
            last_id = re.match('task\d+id(\d+)', last_transact[0]['transact_id'])[1]
            trans_id = str(int(last_id) + 1)
        else:   trans_id = '1'
        result = template_transact + trans_id
    else:
        str_transact = location + str(class_id) + 'c' + str(code) + 'id'
        last_transact = [int(re.match(r'^' + str_transact + r'(\d+)$', r['transact_id'])[1])
                         for r in RegistratorLog.objects.filter(transact_id__contains=str_transact)
                             .values('transact_id').distinct()]
        if last_transact:
            result = str_transact + str(max(last_transact) + 1)
        else:
            result = str_transact + '1'
    return result


# Пакетная регистрация
# Вход - список словарей вида {user_id, reg_id, timestamp, transact_id, parent_transact_id=None, reg}
def paket_reg(list_regs):
    list_save = []
    for lr in list_regs:
        # Сбор данных
        if not 'state_income' in lr['reg']:    lr['reg']['state_income'] = None
        if not 'state' in lr['reg']:    lr['reg']['state'] = None
        if not 'fact_income' in lr['reg']:    lr['reg']['fact_income'] = None
        if not 'fact' in lr['reg']:    lr['reg']['fact'] = None
        if not 'delay_income' in lr['reg']:    lr['reg']['delay_income'] = None
        if not 'delay' in lr['reg']:    lr['reg']['delay'] = None
        if not 'json_income' in lr['reg']: lr['reg']['json_income'] = None
        if not 'json' in lr['reg']: lr['reg']['json'] = None
        if not 'parent_transact_id' in lr: lr['parent_transact_id'] = None

        # Запись в истории
        log = RegistratorLog(reg_name_id=['reg_id'])
        log.state_income = lr['reg']['state_income']
        log.state = lr['reg']['state']
        log.fact_income = lr['reg']['fact_income']
        log.fact = lr['reg']['fact']
        log.delay_income = lr['reg']['delay_income']
        log.delay = lr['reg']['delay']
        log.json_income = lr['reg']['json_income']
        log.json = lr['reg']['json']
        log.transact_id = lr['transact_id']
        log.parent_transact_id = lr['parent_transact_id']
        log.date_update = lr['timestamp']
        log.user_id = lr['user_id']
        log.reg_name_id = lr['reg_id']
        class_id = None
        if lr['reg']['json'] and 'class_id' in lr['reg']['json']:
            class_id = lr['reg']['json']['class_id']
        elif lr['reg']['json_income'] and 'class_id' in lr['reg']['json_income']:
            class_id = lr['reg']['json_income']['class_id']
        log.json_class = class_id
        list_save.append(log)
    RegistratorLog.objects.bulk_create(list_save)


def get_last_update(class_id, code, hist_type='table'):
    q_income = Q(json_class=class_id, json_income__code=code, json_income__type=hist_type)
    q_outcome = Q(json_class=class_id, json__code=code, json__type=hist_type)
    last_update = RegistratorLog.objects.filter(q_income | q_outcome).order_by('-id').values('date_update')[:1]
    if last_update:
        result = datetime.strftime(last_update[0]['date_update'], '%Y-%m-%dT%H:%M:%S')
    else:
        result = None
    return result
