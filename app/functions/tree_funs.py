from django.db.models import OuterRef, Func, F, Subquery

from app.functions import convert_funs
from app.models import Objects, ContractCells, Contracts, Designer


# Найти ветку по заданному ключу
# branch - список. Возвращает объект - словарь
def find_branch(branch, key, value):
    for b in branch:
        if b[key] == value:
            return b
        if 'children' in b and b['children']:
            result = find_branch(b['children'], key, value)
            if result:
                return result
    return None

# Возвращает список всех потомков для указанной ветки. Ветка - объект
def retreive_branch_children(branch):
    list_children = []
    if 'children' in branch:
        for ch in branch['children']:
            list_children.append(ch['id'])
            list_children += retreive_branch_children(ch)
    return list_children


# удалить звено из ветки
def del_branch(branch, code):
    for b in branch:
        if b['code'] == code:
            branch.pop(branch.index(b))
            return True
        elif 'children' in b:
            result = del_branch(b['children'], code)
            if result:
                if not b['children']:
                    del branch[branch.index(b)]['children']
                    b['opened'] = False
                return True
    else:
        return False


# Фильтровать ветку. Результат - линейный список
# Опциональные параметры: is_part = True. Будет искать по части параметра
def filter_branches(branch, key, value, **params):
    # Обработка опциональных параметров
    is_part = True if 'is_part' in params and params['is_part'] else False
    result = []
    for b in branch:
        if is_part:
            if b[key].lower().find(value.lower()) != -1:
                b['opened'] = False
                result.append(b)
        elif b[key] == value:
            result.append(b)
        if 'children' in b and b['children']:
            result += filter_branches(b['children'], key, value, is_part=is_part)
    return result


# достать список значений параметра из ветки и ее детей
# rlpfb - retreive list params from branch
def rlpfb(branch, key):
    res_list = []
    res_list.append(branch[key])
    if 'children' in branch:
        for bc in branch['children']:
            res_list += rlpfb(bc, key)
    return res_list


# Найти дочерние объекты у ветки
def check_children_objects(branch, class_id, is_contract):
    class_manager = Contracts.objects if is_contract else Designer.objects
    location = 'contract' if is_contract else 'table'
    child_classes = class_manager.filter(parent_id=class_id, formula=location)
    if not child_classes:
        return False
    child_ids = [cc.id for cc in child_classes]
    parent_codes = rlpfb(branch, 'code')
    object_manager = ContractCells.objects if is_contract else Objects.objects
    children = object_manager.filter(parent_structure_id__in=child_ids, name__name='parent_branch', value__in=parent_codes).count()
    if children:
        return True
    else:   return False


# открыть всю ветку до узла
# Опциональные параметры: open = True / False. По умолчанию True
def open_branch(branch, tree, **params):
    open = False if 'open' in params and not params['open'] else True
    if branch['parent']:
        parent_branch = find_branch(tree, 'code', branch['parent'])
        parent_branch['opened'] = open
        open_branch(parent_branch, tree, open=open)


# возвращает список детей, но без свойств
def get_children_branches(code, class_id, is_contract=False):
    object_manager = ContractCells.objects if is_contract else Objects.objects
    grandchildren = object_manager.filter(parent_structure_id=class_id, name__name='parent',
                                          value=OuterRef('code')).annotate(count=Func(F('id'), function='Count')).values('count')
    child_names = object_manager.filter(parent_structure_id=class_id, name__name='name', code=OuterRef('code')).values('value')
    children_query = list(object_manager.filter(parent_structure_id=class_id, name__name='parent',
                                                value=code).values('code').annotate(q_g=Subquery(grandchildren))\
                          .annotate(name=Subquery(child_names[:1])))

    def make_branch(c, code):
        br = {'code': c['code'], 'name': c['name'], 'parent': code, 'opened': False}
        if c['q_g']:
            br['children'] = []
        return br

    children = list(map(lambda c: make_branch(c, code), children_query))
    return children


# Собрать свойства для ветки. Ветка - линейный список объектов-"веток" (как правило, принадлежащих одной ветке)
def get_branch_props(branch, class_id, headers, user_id, is_contract=False, **params):
    # Соберем свойства
    codes = [b['code'] for b in branch]
    prop_header_ids = [h['id'] for h in headers if h['name'] not in ('parent', 'is_right_tree')]

    object_manager = ContractCells.objects if is_contract else Objects.objects
    props_qs = object_manager.filter(parent_structure_id=class_id, name_id__in=prop_header_ids, code__in=codes)\
        .select_related('name').order_by('code', 'name__priority')
    # Успорядочим их в виде списка словарей
    list_props = []
    code = None
    prop = {}
    for pq in props_qs:
        if code != pq.code:
            if prop:
                list_props.append(prop)
                prop = {}
            code = pq.code
            prop['code'] = code
        prop[pq.name_id] = {'value': pq.value}
    if prop:  # вставили последний набор свойств
        list_props.append(prop)
    # Добавим специфические поля
    hwp = []
    for h in headers:
        if h['name'] != 'parent':
            copyh = h.copy()
            copyh['is_visible'] = True
            hwp.append(copyh)
    child_class = params['child_class'] if 'child_class' in params else None
    convert_funs.prepare_table_to_template(hwp, list_props, user_id, is_contract, child_class=child_class)
    # Вбросим их в ветку
    for b in branch:
        for i in range(len(list_props)):
            if b['code'] == list_props[i]['code']:
                prop = list_props.pop(i)
                del prop['code']
                b['props'] = prop
                break
        else:
            b['props'] = {}
    return branch


# antt - add node to tree
# Добавляет ветку, которой нет в дереве. Возвращает ссылку на ветку
def antt(code, tree, class_id, headers, user_id, is_contract=False):
    object_manager = ContractCells.objects if is_contract else Objects.objects
    class_manager = Contracts.objects if is_contract else Designer.objects
    list_codes = [code, ]
    its_done = False
    current_code = code
    # Получим список кодов изнутри наружу
    while not its_done:
        obj = object_manager.filter(parent_structure_id=class_id, code=current_code, name__name='parent')
        parent_code = None
        if obj:
            parent_code = obj[0].value
        if parent_code:
            list_codes.append(parent_code)
            current_code = parent_code
        else:
            its_done = True
    branch = None
    while list_codes:
        current_code = list_codes.pop()
        branch = find_branch(tree, 'code', current_code)
        if branch and 'children' in branch:
            branch['opened'] = True
            if not branch['children']:
                branch['children'] = get_children_branches(current_code, class_id, is_contract)
                branch['children'] = get_branch_props(branch['children'], class_id, headers, user_id, is_contract)
        if list_codes:
            tree = branch['children']
    return branch


# Получает список кодов всех потомков древовивной структуры из БД
def get_inheritors(code, class_id, is_contract=False):
    result_codes = []
    manager = ContractCells.objects if is_contract else Objects.objects
    objs = manager.filter(parent_structure_id=class_id, name__name='parent')
    if code:
        objs = objs.filter(value=code)
    else:
        objs = objs.filter(value__isnull=True)
    for o in objs:
        result_codes.append(o.code)
        result_codes += get_inheritors(o.code, class_id, is_contract)
    return result_codes


# glwt - get level without tree
def glwt(tree_id, code, is_contract=False):
    counter = 1
    is_over = False
    manager = ContractCells.objects if is_contract else Objects.objects
    while not is_over:
        cell = manager.get(parent_structure_id=tree_id, code=code, name__name='parent')
        if not cell.value:
            is_over = True
        else:
            counter += 1
            code = cell.value
    return counter
