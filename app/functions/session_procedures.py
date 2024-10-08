from django.db.models import OuterRef, Func, Subquery, F
from django.forms import model_to_dict

from app.functions import convert_procedures, tree_funs
from app.models import TechProcess, Contracts, ContractCells, Designer, Objects, Dictionary, DictObjects


# atic = add_tps_in_contract
def atic(contract_id):
    tpos = TechProcess.objects.filter(parent_id=contract_id, formula='tp')
    tpos_ids = [t.id for t in tpos]
    tpos_params = list(TechProcess.objects.filter(parent_id__in=tpos_ids).values())
    tps = []
    for t in tpos:
        my_params = [tp for tp in tpos_params if tp['parent_id'] == t.id]
        sys_params = []
        stages = []
        for mp in my_params:
            if mp['settings']['system']:
                sys_params.append(mp)
            else:
                stages.append(mp)
        tp = {'id': t.id, 'name': t.name, 'parent_id': t.parent_id, 'cf': t.value['control_field'],
              'system_params': sys_params, 'stages': stages}
        tps.append(tp)
    return tps


def fill_tom(class_id, path, loc, user_id, **params):
    # при активации переменной не загружаем информацию о родительском дереве для класса
    hide_tree = True if 'hide_tree' in params and params['hide_tree'] else False
    tom = {}
    tom['class_id'] = class_id
    location = ''
    tom['path'] = path
    if path in ('/contract', '/contract-draft'):
        location = 'contract'
    elif path in ('/manage-object', '/table-draft'):
        location = 'table'
    elif path == '/path':
        location = 'table' if loc.lower() == 't' else 'contract'
    elif path == '/dictionary':
        location = 'dict'
    elif path == '/roh':
        location = 'contract' if loc == 'c' else 'table'
        tom['path'] = '/contract' if location == 'contract' else '/manage-object'

    # загрузим заголовки класса в сессию
    class_manager = None; obj_manager = None
    if location == 'contract':
        class_manager = Contracts.objects
        obj_manager = ContractCells.objects
    elif location == 'table':
        class_manager = Designer.objects
        obj_manager = Objects.objects
    elif path == '/tree':
        class_manager = Designer.objects if loc.lower() == 't' else Contracts.objects
        obj_manager = Objects.objects if loc.lower() == 't' else ContractCells.objects
    elif location == 'dict':
        class_manager = Dictionary.objects
        obj_manager = DictObjects.objects
    # загрузим в сессию заголовки класса
    headers = class_manager.filter(parent_id=class_id).values()
    if path == '/tree':
        headers = headers.exclude(formula__in=('table', 'contract'))
    exclude_names = ('parent_branch', 'business_rule', 'link_map', 'trigger', 'completion_condition')
    # if location != 'dict':
    headers = list(headers.exclude(name__in=exclude_names).order_by('priority', 'id'))
    # Если есть тип данных константа - добавим информацию о детях
    for h in headers:
        convert_procedures.ficoitch(h)
    tom['headers'] = list(headers)
    if location == 'dict':
        tom['current_class'] = class_manager.filter(id=class_id).values()[0]
        return False
    current_class = class_manager.filter(id=class_id).select_related('parent')
    if current_class:
        current_class = current_class[0]
    else:
        return False
    tom['current_class'] = model_to_dict(current_class)
    is_tree = False  # Параметр, являющийся истинной для класса, привязанного к дереву (но не само дерево.
    # Если работаем с деревом = False) если с объектом в дереве - True
    if current_class.parent_id and current_class.parent.formula == 'tree':
        is_tree = True
    # Загрузим в сессию информацию о заголовках всех словарей, привязанных к данному классу.
    headers_my_dicts = Dictionary.objects.filter(formula='dict', parent_id=class_id, default=location)
    my_dicts = []
    for hmd in headers_my_dicts:
        dict = list(Dictionary.objects.filter(parent_id=hmd.id).values())
        my_dicts.append({'id': hmd.id, 'name': hmd.name, 'children': dict})
    tom['my_dicts'] = my_dicts
    # Загрузим информацию о дереве
    if (path == '/tree' or is_tree) and not hide_tree:
        if is_tree:
            parent_id = current_class.parent_id
        else:
            parent_id = class_id
        codes_no_parent = [c.code for c in obj_manager.filter(value__isnull=True, name__name='parent',
                                                              parent_structure_id=parent_id)]
        children = obj_manager.filter(parent_structure_id=parent_id, name__name='parent',
                                      value=OuterRef('code')).annotate(count=Func(F('id'), function='Count')).values(
            'count')
        root_tree = list(obj_manager.filter(parent_structure_id=parent_id, code__in=codes_no_parent,
                                            name__name='name').values('code', 'value') \
                         .annotate(count_child=Subquery(children)))

        def make_branch(rt):
            br = {'code': rt['code'], 'name': rt['value'], 'parent': None, 'opened': False}
            if rt['count_child']:
                br['children'] = []
            return br

        tom['tree'] = list(map(lambda rt: make_branch(rt), root_tree))
        # Получим свойства дерева

        tree = tom['tree']
        if is_tree:  # Если тип данных Объект
            is_contract = True if location == 'contract' else False
            tree_headers = list(class_manager.filter(parent_id=parent_id).exclude(formula__in=('contract', 'table')) \
                                .exclude(name__in=('is_right_tree', 'parent')).values())
            for th in headers:
                convert_procedures.ficoitch(th)
            tom['tree_headers'] = tree_headers
            child_class = current_class.id
        else:  # для дерева получим свойства
            is_contract = True if loc.lower() == 'c' else False
            tree_headers = tom['headers']
            child_class = None
        tom['tree'] = tree_funs.get_branch_props(tree, parent_id, tree_headers, user_id, is_contract,
                                                 child_class=child_class)
        if is_tree:
            root = {'code': 0, 'name': current_class.parent.name, 'parent': None, 'opened': True,
                    'children': tom['tree']}
            tom['tree'] = (root,)
    # Загрузим массивы для контрактов и справочников
    if current_class.formula in ('table', 'contract'):
        arrays = class_manager.filter(parent_id=current_class.id, formula='array')
        if arrays:
            list_arrays = []
            for a in arrays:
                dict_array = {'id': a.id, 'name': a.name}
                headers = list(class_manager.filter(parent_id=a.id).exclude(formula='techpro').values())
                dict_array['headers'] = headers
                dict_array['vis_headers'] = []
                counter_header = 0
                for h in headers:
                    if h['is_visible'] and h['name'] != 'Собственник':
                        if counter_header > 3:
                            break
                        else:
                            counter_header += 1
                        dict_array['vis_headers'].append(h)

                list_arrays.append(dict_array)
            tom['arrays'] = list_arrays
    # загрузим техпроцессы (2.0) для контрактов и массивов
    if current_class.formula in ('contract', 'array') and location == 'contract':
        tom['tps'] = atic(current_class.id)
    return tom