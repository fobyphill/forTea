from datetime import datetime
import operator

from django.contrib.auth import get_user_model

from app.functions import reg_funs
from app.models import Designer, Contracts, DictObjects, Dictionary


# Получить тип класса - таблица, контракт, константа, массив, каталог.
def get_class_type(id, is_contract=True):
    my_class = Contracts.objects if is_contract else Designer.objects
    try:
        my_class = my_class.get(id=id)
    except:
        return False
    return my_class.formula

# Удалить все словари, связанные с объектом
# Вход - код родительского объекта, айдти родительского словаря
# Выход - Да/ Нет
def delete_dict_records(parent_code, parent_structure_id, user_id, timestamp=None, parent_transaction_id=None):
    dict_del = DictObjects.objects.filter(parent_structure_id=parent_structure_id,
                                          parent_code=parent_code)
    if dict_del:
        code = dict_del[0].code
        current_dict = Dictionary.objects.get(id=parent_structure_id)
        incoming = {'class_id': parent_structure_id, 'location': current_dict.default, 'type': 'dict',
                    'parent_code': parent_code, 'code': code}
        transaction_id = reg_funs.get_transact_id(parent_structure_id, code, 'd')
        if not timestamp:   timestamp = datetime.now()
        # регистрация удаления реквизитов
        for dd in dict_del:
            ic = incoming.copy()
            ic['id'] = dd.id
            ic['name'] = dd.name_id
            ic['value'] = dd.value
            reg = {'json_income': ic}
            reg_funs.simple_reg(user_id, 16, timestamp, transaction_id, parent_transaction_id, **reg)
        # регистрация удаления объекта
        reg = {'json_income': incoming}
        reg_funs.simple_reg(user_id, 8, timestamp, transaction_id, parent_transaction_id, **reg)
        dict_del.delete()  #  Удаление


# проверить приоритет полей класса (и исправить). Вход - кверисет с параметрами, тип - строка table, contract, dict
def check_fix_priority(params_4_order, type):
    is_change = False
    counter = 1
    params_sorted = sorted(params_4_order, key=operator.attrgetter('priority'))
    params_changed = []
    for ps in params_sorted:
        if ps.priority != counter:
            ps.priority = counter
            is_change = True
            params_changed.append(ps)
        counter += 1
    if is_change:
        type_dict = {'table': Designer.objects, 'contract': Contracts.objects, 'dict': Dictionary.objects}
        header = type_dict[type]
        header.bulk_update(params_changed, ['priority'])


def check_user(user_id):
    User = get_user_model()
    user = User.objects.filter(id=user_id).values()
    return user if user else False