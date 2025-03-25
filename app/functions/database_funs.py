import json
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max
from app.functions import reg_funs, convert_procedures, database_procedures
from app.models import Objects, Designer, ContractCells, Contracts, Dictionary, DictObjects, TablesCodes, OtherCodes, \
    Tasks


# Функции базы данных - обеспечивающие безопасную эксплуатацию данными:
# обновление таблиц, операции с внешними ключами и т.д.


# Проверка объекта. Вход - код объекта и айди его класса (числа). Выход - Да/Нет
def check_object(code, class_id):
    class_type, parent_id = convert_procedures.slice_link_header(class_id)
    if class_type == 'table':
        obj = Objects.objects.filter(code=code, parent_structure_id=parent_id)
    else:
        obj = ContractCells.objects.filter(code=code, parent_structure_id=parent_id)
    if obj: return True
    else:   return  False


# Получить новый код объекта заданного класса
# Вход - айди класса. Выход - код нового объекта
def get_code(class_id, location):
    try:
        max_code = TablesCodes.objects.get(class_id=class_id, location=location)
        max_code.max_code += 1
        max_code.save()
        return max_code.max_code
    except ObjectDoesNotExist:
        dict_manager = {'table': Objects.objects, 'contract': ContractCells.objects, 'dict': DictObjects.objects,
                        'task': Tasks.objects}
        manager = dict_manager[location]
        if location == 'task':
            object = manager.filter(data__class_id=class_id)
        else:
            object = manager.filter(parent_structure_id=class_id)
        if object:
            max_code = object.aggregate(max_code=Max('code'))['max_code'] + 1
        else:
            max_code = 1
        TablesCodes(class_id=class_id, location=location, max_code=max_code).save()
        return max_code


def get_other_code(class_name):
    code = 1
    try:
        get_class = OtherCodes.objects.get(name=class_name)
    except ObjectDoesNotExist:
        OtherCodes(name=class_name, code=1).save()
        code = 1
    else:
        code = get_class.code + 1
        get_class.code = code
        get_class.save()
    finally:
        return code


# Проверка на детей. Вход - айди предка, тип_предка (), айди потомка, тип потомка. Все данные - строки. выход - Да/Нет
def is_child(class_id, class_type, child_id, child_type):
    if child_id:
        val = class_type + '.' + class_id
        children = list(Designer.objects.filter(formula='link', value=val))
        for c in children:
            if c.parent_id == int(child_id) and child_type == 'table':
                return True
            elif is_child(str(c.parent_id), 'table', child_id, child_type):
                return True
        children += list(Contracts.objects.filter(formula='link', value=val))
        for c in children:
            if c.parent_id == int(child_id) and child_type == 'contract':
                return True
            elif is_child(str(c.parent_id), 'contract', child_id, child_type):
                return True
    return False


# Изменить приоритет полей класса
def change_class_priority(class_id, param_id, move, formula):
    if formula == 'contract':
        header = Contracts.objects
    elif formula == 'dict':
        header = Dictionary.objects
    else:
        header = Designer.objects
    exclude_names = ('name', 'parent', 'is_right_tree', 'link_map', 'business_rule', 'trigger')
    params_4_order = header.filter(parent_id=class_id).exclude(formula__in=('table', 'contract'))\
        .exclude(name__in=exclude_names).order_by('priority', 'id')
    # Если не выствлены приоритеты - выставим отдельным циклом
    database_procedures.check_fix_priority(params_4_order, formula)
    # исправим приоритет, если он изменялся
    for i in range(len(params_4_order)):
        if params_4_order[i].id == param_id:
            if move == 'down':
                params_4_order[i].priority += 1
                params_4_order[i + 1].priority -= 1
            else:
                params_4_order[i].priority -= 1
                params_4_order[i - 1].priority += 1
            break
    header.bulk_update(params_4_order, ['priority'])


# Проверка, есть ли дети у даанного объекта. Локация - по базе данных - т.е. table, contract, dict
# Результат = False - нет детей, list_of_children - есть дети
def check_children(current_class, code, database_location):
    children = []
    if database_location not in ('table', 'contract'):
        return False
    class_manager = Contracts.objects if database_location == 'contract' else Designer.objects
    # Проверка ссылок
    managers = [ {'header': Designer.objects, 'objects': Objects.objects},
                 {'header': Contracts.objects, 'objects':ContractCells.objects}
                ]
    for m in managers:
        table_links = m['header'].filter(formula='link', value=database_location + '.' + str(current_class.id))
        for tl in table_links:
            child = m['objects'].filter(name_id=tl.id, parent_structure_id=tl.parent_id, value=str(code))
            if child:
                children.append(child)

    obj_manager = managers[0]['objects'] if database_location == 'table' else managers[1]['objects']
    # # Проверка дочерних массивов
    # if current_class.formula in ('table', 'contract'):
    #     arrays = class_manager.filter(formula='array', parent_id=class_id)
    #     if arrays:
    #         for a in arrays:
    #             obj_array = obj_manager.filter(parent_structure_id=a.id, name__name='Собственник', value=code)
    #             if obj_array:
    #                 children.append(obj_array)
    #  для дерева
    if current_class.formula == 'tree':
        # Проверка дочерних веток
        children_branches = obj_manager.filter(name__name='parent', parent_structure_id=current_class.id, value=code)
        if children_branches:
            children.append(children_branches)
        # Проверка дочерник объектов
        children_classes = class_manager.filter(parent_id=current_class.id, formula=database_location)
        for cc in children_classes:
            child_obj = obj_manager.filter(parent_structure_id=cc.id, name__name='parent_branch', value=code)
            if child_obj:
                children.append(child_obj)
    return children if children else False


# chpoc = check props of const
# выход: Есть свойства - Истина, нет свойств - ложь
def chpoc(alias_id, is_contract=False):
    manager = Contracts.objects if is_contract else Designer.objects
    props = manager.filter(parent_id=alias_id)
    if props:
        return True
    else:
        return False


# проверка, есть ли дочерние классы у данного ccc - check children classes. Ответ Да - есть дети, нет - детей нет
def ccc(class_id, is_contract):
    manager = Contracts.objects if is_contract else Designer.objects
    children_classes = manager.filter(parent_id=class_id, formula__in=('table', 'contract', 'array', 'folder', 'tree'))
    def_val = 'contract' if is_contract else 'table'
    children_dicts = Dictionary.objects. filter(parent_id=class_id, formula='dict', default=def_val)
    if children_classes or children_dicts:
        return True
    else:   return False