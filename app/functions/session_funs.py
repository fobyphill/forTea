from django.db.models import Subquery, OuterRef, Func, F
from django.forms import model_to_dict

from app.functions import convert_funs, tree_funs, convert_procedures, session_procedures
from app.models import Designer, Objects, Contracts, Dictionary, TableDrafts, ContractCells, ContractDrafts, Tasks, \
    DictObjects, TechProcess, DataTypesList, ClassTypesList, UserSets


def update_class_tree(request, is_contract=False):
    exclude_classes = ('table', 'tp', 'dict') if is_contract else ('contract', 'tp', 'dict')
    list_classes = list(k for k in request.session['class_types'].keys() if k not in exclude_classes)
    if is_contract:
        class_tree = Contracts.objects
    else:
        class_tree = Designer.objects
    class_tree = list(class_tree.filter(formula__in=list_classes).values())
    # Получим список словарей и добавим в общий список
    default = 'contract' if is_contract else 'table'
    dicts = list(Dictionary.objects.filter(formula='dict', default=default).values())
    class_tree += dicts
    # Получим список техпроцессов и добавим в общий
    if is_contract:
        tps = list(TechProcess.objects.filter(formula='tp').values())
        class_tree += tps

    # Преобразование в матрешку
    convert_funs.query_to_tree(class_tree, class_tree)

    if is_contract:
        request.session['contract_tree'] = class_tree
    else:
        request.session['class_tree'] = class_tree


def update_draft_tree(request, is_contract=False):
    draft_manager = ContractDrafts.objects if is_contract else TableDrafts.objects
    header_manager = Contracts.objects if is_contract else Designer.objects
    class_type = 'contract' if is_contract else 'table'
    count_drafts = draft_manager.filter(user_id=request.user.id, active=True, data__parent_structure=OuterRef('id'))\
        .annotate(count=Func(F('id'), function='Count')).values('count')
    drafts = list(header_manager.filter(formula__in=('folder', 'tree', 'array', class_type)) \
        .annotate(quantity=Subquery(count_drafts)).values('id', 'name', 'formula', 'parent_id', 'quantity'))
    # Уложим в дерево
    if is_contract:
        request.session['contract_draft_tree'] = draft_to_tree(drafts, drafts)
        request.session['contract_draft_quantity'] = sum([dt['quantity'] for dt in request.session['contract_draft_tree']])
        request.session['contract_draft_menu'] = update_draft_menu(request, request.session['contract_draft_tree'], True)
    else:
        request.session['draft_tree'] = draft_to_tree(drafts, drafts)
        request.session['draft_quantity'] = sum([dt['quantity'] for dt in request.session['draft_tree']])
        request.session['draft_menu'] = update_draft_menu(request, request.session['draft_tree'])


# Список классов превращаем в дерево черновиков
def draft_to_tree(tree, parents):
    sort_order = {'folder': 0, 'table': 1, 'contract': 2, 'alias': 3, 'array': 4, 'dict': 5, 'tree': 6, 'tp': 7,
                  'techprocess': 8}
    tree.sort(key=lambda x: sort_order[x['formula']])
    i = 0
    while i < len(parents):
        # 1. Найдем детей
        p = parents[i]
        j = 0
        while j < len(tree):
            c = tree[j]
            if c['parent_id'] == p['id']:
                tree = draft_to_tree(tree, (c,))
                if not 'children' in p.keys():
                    p['children'] = []
                q = c['quantity'] if c['quantity'] else 0
                p['quantity'] = 0 if not p['quantity'] else p['quantity']
                p['quantity'] += q
                p['children'].append(c)
                j = tree.index(c)
                del tree[j]
                i = parents.index(p)
            else:   j += 1
        i += 1
    return tree


# Обновляет меню справочников / контрактов / словарей
# Опциональные параметры params
# is_draft - True / False. Выбирается только если обновляем меню черновиков
def update_class_menu(request, tree, branch, parent=None, is_contract=False, **params):
    # Обработка опциональных параметров
    if 'is_draft' in params:
        is_draft = params['is_draft']
    else:   is_draft = False
    result_code = ''
    if is_draft:
        path = 'contract-draft' if is_contract else 'table-draft'
    else:
        path = 'contract' if is_contract else 'manage-object'
    icon_folder = '<img src="/static/img/pics/folder_opened_50.png" width=20px>'
    icon_table = '<img src="/static/img/pics/book_50.png" width=20px>'
    icon_alias = '<img src="/static/img/pics/home_50.png" width=20px>'
    icon_dict = '<img src="/static/img/pics/star_50.png" width=20px>'
    icon_contract = '<img src="/static/img/pics/pen_50.png" width=20px>'
    icon_tree = '<img src="/static/img/pics/tree_32_blue.png" width=20px>'
    array = '<img src="/static/img/pics/array_50.png" width=15px>'
    dict_icon = {'table': icon_table, 'folder': icon_folder, 'alias': icon_alias, 'array': array,
                 'dict': icon_dict, 'contract': icon_contract, 'tree': icon_tree}
    for b in branch:
        if b['formula'] == 'dict' or b['formula'] == 'alias' and is_draft or b['formula'] == 'tp'\
                or b['formula'] == 'array':
            continue
        dummies = ('folder',) if not is_draft else ('folder', 'tree')
        if b['formula'] in dummies:
            address = '#'
        # elif b['formula'] == 'dict':
        #     parent_type = parent['formula']
        #     address = 'dictionary?class_id=' + str(b['id']) + '&parent_id=' + str(b['parent_id']) + '&parent_type=' + parent_type
        elif b['formula'] == 'tree':
            loc = 'c' if is_contract else 't'
            address = 'tree?class_id=' + str(b['id']) + '&location=' + loc
        else:   address = path + '?class_id=' + str(b['id'])
        true_children = True if 'children' in b and next((True for ch in b['children']
                                                          if ch['formula'] not in ('tp', 'dict', 'array')), False) else False
        class_name = 'dropdown-item'
        if true_children:
            class_name += ' submenu'
        item = '<a class="' + class_name + '" href="' + address + '">' + dict_icon[b['formula']] + ' ' + b['name'] + '</a>'
        if true_children:
            item += '<div class="dropdown-menu">' + update_class_menu(request, tree, b['children'], b, is_contract,
                                                                      is_draft=is_draft) + '</div>'
        result_code += item
    return result_code


# Ообновляет меню черновиков
def update_draft_menu(request, branch, is_contract=False):
    result_code = ''
    path = 'contract-draft' if is_contract else 'table-draft'
    icon_folder = '<img src="/static/img/pics/folder_opened_50.png" width=20px>'
    icon_table = '<img src="/static/img/pics/book_50.png" width=20px>'
    icon_alias = '<img src="/static/img/pics/home_50.png" width=20px>'
    icon_dict = '<img src="/static/img/pics/star_50.png" width=20px>'
    icon_contract = '<img src="/static/img/pics/pen_50.png" width=20px>'
    icon_tree = '<img src="/static/img/pics/tree_32_blue.png" width=20px>'
    dict_icon = {'table': icon_table, 'folder': icon_folder, 'alias': icon_alias, 'array': '&#8983;',
                 'dict': icon_dict, 'contract': icon_contract, 'tree': icon_tree}
    branch_draft_quant = 0
    list_ids = []
    for b in branch:
        branch_draft_quant += b['quantity']
        if b['quantity']:
            list_ids.append(str(b['id']))
        if b['formula'] in ('dict', 'alias'):
            continue
        elif b['formula'] in ('folder', 'tree'):
            address = '#'
        else:   address = path + '?class_id=' + str(b['id'])
        if 'children' in b: class_name = 'dropdown-item submenu'
        else:   class_name = 'dropdown-item'
        q_class = ' class=text-red' if b['quantity'] else ''
        item = '<a class="' + class_name + '" href="' + address + '">' + dict_icon[b['formula']] + b['name'] + \
               ' <span' + q_class + '>(' + str(b['quantity']) + ')</span></a>'
        if 'children' in b:
            item += '<div class="dropdown-menu">' + update_draft_menu(request, b['children'], is_contract) + '</div>'
        result_code += item
    if branch_draft_quant:
        finish_item = '<a class="dropdown-item" href="' + path + '?del=' + ','.join(list_ids) + '">Удалить все черновики</a>'
        result_code += finish_item
    return result_code


# временные данные страницы объектов. стираются при переходе к другому классу
# omtd - object manager temp data
def update_omtd(request):
    updated = False
    class_id = int(request.GET['class_id'])
    loc = request.GET['location'] if 'location' in request.GET else ''
    if not 'temp_object_manager' in request.session or not request.session['temp_object_manager']:
        request.session['temp_object_manager'] = session_procedures.fill_tom(class_id, request.path,
                                                                             loc, request.user.id)
        updated = True
    elif 'class_id' in request.session['temp_object_manager']:
        if request.session['temp_object_manager']['class_id'] != class_id:
            request.session['temp_object_manager'] = session_procedures.fill_tom(class_id, request.path,
                                                                                 loc, request.user.id)
            updated = True
        elif request.session['temp_object_manager']['path'] != request.path \
                and request.path not in ('/roh', '/get-object-version'):
            request.session['temp_object_manager'] = session_procedures.fill_tom(class_id, request.path,
                                                                                 loc, request.user.id)
            updated = True
    return updated


# обнулить временные данные. Вход - реквест. Выход Да/нет. Обнулено / нет
def new_temp_data(request):
    if not 'temp_data' in request.session or request.session['temp_data']['path'] != request.path:
        request.session['temp_data'] = {}
        request.session['temp_data']['path'] = request.path
        request.session['temp_data']['data'] = {}
        return True
    else:   return False


# добавим в сессию типы данных
def add_data_types(request):
    if not 'data_types' in request.session:
        request.session['data_types'] = list(dtl['name'] for dtl in DataTypesList.objects.all().values('name'))


# добавим в сессию типы классов
def add_class_types(request):
    if not 'class_types' in request.session:
        class_types = list(ClassTypesList.objects.all().values())
        dict_ct = {}
        for ct in class_types:
            dict_ct[ct['name']] = ct['description']
        request.session['class_types'] = dict_ct


# добавим в сессию алиасы
def add_aliases(request):
    if not 'aliases' in request.session:
        request.session['aliases'] = [{'location': 'table', 'id': d['id'], 'name': d['name']} for d in
                                      Designer.objects.filter(formula='alias').values('id', 'name')]
        request.session['aliases'].extend([{'location': 'contract', 'id': c['id'], 'name': c['name']} for c in
                                           Contracts.objects.filter(formula='alias').values('id', 'name')])


# контрольный пересчет количества черновиков - control_recount_quantity_draft
def crqd(request, is_contract=False):
    manager = ContractDrafts. objects if is_contract else TableDrafts.objects
    dq = 'contract_draft_quantity' if is_contract else 'draft_quantity'
    drafts_control_sum = manager.filter(user_id=request.user.id).count()
    if drafts_control_sum != request.session[dq]:
        update_draft_tree(request, is_contract)


# контрольный пересчет количества заданий
def check_quant_tasks(request):
    # active_tasks = Tasks.objects.filter(user_id=request.user.id, date_done__isnull=True).values('code').distinct().count()
    tasks = list(Tasks.objects.filter(user_id=request.user.id).order_by('code'))
    tasks += list(Tasks.objects.filter(kind__in=('prop', 'stage'), data__sender_id=request.user.id))
    active_tasks = 0
    all_tasks = 0
    active_code = 0
    all_code = 0
    for t in tasks:
        if t.code != active_code and not t.date_done:
            active_code = t.code
            active_tasks += 1
        if all_code != t.code:
            all_code = t.code
            all_tasks += 1
    request.session['tasks_quant'] = {'at': active_tasks, 'alt': all_tasks}



