from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import render
from app.functions import view_procedures, session_funs, database_funs, reg_funs, tree_funs, interface_funs, \
    convert_procedures, convert_funs, hist_funs
from app.models import Contracts, Designer, ContractCells, Objects, RegistratorLog


@view_procedures.is_auth_app
@view_procedures.is_class_id
def tree(request):
    message = ''
    message_class = ''
    class_id = int(request.GET['class_id'])
    is_contract = True if 'location' in request.GET and request.GET['location'].lower() == 'c' else False
    location = 'contract' if is_contract else 'table'
    class_manager = Contracts.objects if is_contract else Designer.objects
    current_class = class_manager.filter(id=class_id)
    object_manager = ContractCells.objects if is_contract else Objects.objects
    if current_class:
        current_class = current_class[0]
    else:
        return HttpResponse('Не найдено дерево с ID:' + request.GET['class_id'])
    title = 'Дерево "' + current_class.name + '"'

    # загрузить дерево классов в сессию
    class_tree = 'contract_tree' if is_contract else 'class_tree'
    if not class_tree in request.session:
        session_funs.update_class_tree(request, is_contract)
    # Загрузить меню справочников
    class_menu = 'contract_menu' if is_contract else 'class_menu'
    if not class_menu in request.session:
        request.session[class_menu] = session_funs.update_class_menu(request, request.session[class_tree],
                                                                       request.session[class_tree], None, is_contract)
    if not 'draft_tree' in request.session:  # загрузить дерево черновиков в сессию
        session_funs.update_draft_tree(request, is_contract)
    # проверим временные данные менеджера объектов в сессии
    updated = session_funs.update_omtd(request)
    tree = request.session['temp_object_manager']['tree']
    headers = request.session['temp_object_manager']['headers']
    if updated:
        tree = tree_funs.get_branch_props(tree, class_id, headers, request.user.id, is_contract)

    # Загрузим параметры из GET в POST
    to_post_redirect = interface_funs.get_to_post(request, ('class_id', 'location'))
    if to_post_redirect:
        return to_post_redirect

    if 'branch_code' in request.POST:
        code = int(request.POST['branch_code'])
    else:
        code = int(request.POST['i_code']) if 'i_code' in request.POST and request.POST['i_code'] else None
    if 'i_parent' in request.POST and request.POST['i_parent']:
        try:
            parent = int(request.POST['i_parent'])
        except ValueError:
            parent = int(float(request.POST['i_parent']))
    else:   parent = None
    timestamp = datetime.now()
    if code:
        branch = tree_funs.find_branch(tree, 'code', code)
        if not branch:
            branch = tree_funs.antt(code, tree, class_id, headers, request.user.id, is_contract)
    elif tree:
        branch = tree[0]
    else:
        branch = None


    # Кнопка "Сохранить"
    if 'b_save' in request.POST:
        dict_params = {'string': 'ta_', 'float': 'i_float_', 'link': 'i_link_', 'datetime': 'i_datetime_',
                       'date': 'i_date_', 'enum': 's_enum_', 'const': 's_alias_'}

        def validation():
            message = ''
            is_valid = True
            if not request.POST['i_name']:
                is_valid = False
                message = 'Нельзя сохранить ветку без названия\n'

            for h in headers:
                if h['name'] =='is_right_tree':
                    continue
                elif h['name'] == 'name':
                    if not request.POST['i_name']:
                        is_valid = False
                        message += 'Поле \"Название\" обязательно должно быть заполнено\n'
                elif h['name'] == 'parent':
                    # проверка родителя
                    parent = None
                    if request.POST['i_parent']:
                        try:
                            parent = int(request.POST['i_parent'])
                        except ValueError:
                            is_valid = False
                            message += 'Некорректно указан ID родителя. Необходимо указать целое число - код родителя\n'
                    if parent:
                        codes = [o['code'] for o in object_manager.filter(parent_structure_id=class_id).values('code')
                            .distinct()]
                        if not parent in codes:
                            is_valid = False
                            message += 'Некорректно указан ID родителя. Нет родителя с таким кодом\n'
                elif h['formula'] == 'link':
                    # проверка корректности ссылки
                    val = request.POST['i_link_' + str(h['id'])]
                    if val:
                        link_type, class_link_id = convert_procedures.slice_link_header(h['value'])
                        manager = ContractCells.objects if link_type == 'contract' else Objects.objects
                        linked_object = manager.filter(parent_structure_id=class_link_id, code=val)
                        if not linked_object:
                            is_valid = False
                            message += 'Ссылка ведет на несуществующий объект\n'
                elif h['is_required']:
                    if h['formula'] in ('bool', 'enum', 'const'):
                        continue
                    # проверка обязательных параметров
                    param = request.POST[dict_params[h['formula']] + str(h['id'])]
                    if not param:
                        is_valid = False
                        message += 'Параметр "' + h['name'] + '" ID: ' + str(h['id']) \
                                   + ' является обязательным. Пожалуйста заполните его\n'
            return is_valid, message

        # Проверка поля "имя". Да - пройдена валидация. Нет - соответственно нет
        def valid_name(header):
            names = object_manager.filter(name_id=header['id'], parent_structure_id=class_id,
                                          value__iexact=request.POST['i_name'])
            if names:
                return False
            else:
                return True

        def save_const_param(name, val):
            header_name = next(h for h in headers if h['name'] == name)
            param_name = object_manager.filter(parent_structure_id=class_id, name_id=header_name['id'], code=code)
            if param_name:
                param_name = param_name[0]
                reg_id = 15
            else:
                create_manager = ContractCells if is_contract else Objects
                param_name = create_manager(parent_structure_id=class_id, name_id=header_name['id'], code=code)
                reg_id = 13
            old_name = param_name.value
            param_name.value = val
            param_name.save()
            # регистрация
            location = 'contract' if is_contract else 'table'
            incoming = {'class_id': class_id, 'code': code, 'location': location, 'type': 'tree', 'id': param_name.id,
                        'name': header_name['id'], 'value': old_name}
            outcoming = incoming.copy()
            outcoming['value'] = param_name.value
            if reg_id == 15:
                reg = {'json': outcoming, 'json_income': incoming}
            else:
                reg = {'json': outcoming}
            reg_funs.simple_reg(request.user.id, reg_id, timestamp, transact_id, **reg)
        # если редактируем
        if request.POST['i_code']:
            is_valid, msg = validation()
            is_change = False
            transact_id = None
            if is_valid:
                transact_id = reg_funs.get_transact_id(class_id, code, location[0])
                # редактируем имя:
                if branch['name'] != request.POST['i_name']:
                    is_change = True
                    # проверим имя на предмет повтора
                    header_name = next(h for h in headers if h['name'] == 'name')
                    is_valid = valid_name(header_name)
                    if is_valid:
                        save_const_param('name', request.POST['i_name'])
                        branch['name'] = request.POST['i_name']
                    else:
                        message += 'Имя ветки задано некорректно. У данного дерева уже имеется одноименная ветка\n'
            if is_valid:
                # проверим родителя
                if branch['parent'] != parent:
                    is_change = True
                    save_const_param('parent', parent)
                    if parent:
                        parent_branch = tree_funs.find_branch(tree, 'code', parent)
                    else:
                        parent_branch = tree
                    if parent_branch:
                        old_parent_code = branch['parent']
                        branch['parent'] = parent
                        # копируем во внутренний узел
                        if parent:
                            if not 'children' in parent_branch:
                                parent_branch['children'] = [branch.copy(), ]
                            else:
                                parent_branch['children'].append(branch)
                        # копируем в корень
                        else:   tree.append(branch)
                        # Удалим из внутреннего узла
                        if old_parent_code:
                            old_parent_branch = tree_funs.find_branch(tree, 'code', old_parent_code)
                            old_branch = tree_funs.find_branch(old_parent_branch['children'], 'code', code)
                            del old_parent_branch['children'][old_parent_branch['children'].index(old_branch)]
                            if not old_parent_branch['children']:
                                del old_parent_branch['children']
                                old_parent_branch['opened'] = False
                        # Удалим из корня
                        else:
                            old_branch = tree_funs.find_branch(tree, 'code', code)
                            del tree[tree.index(old_branch)]
                        tree_funs.open_branch(branch, tree)  # открыть ветку
                    else:
                        tree_funs.del_branch(tree, branch['code'])
                        tree_funs.antt(parent, tree, class_id, headers, request.user.id, is_contract)
                # Проверим динамические параметры
                for h in headers:
                    if h['formula'] == 'eval' or h['name'] in ('is_right_tree', 'name', 'parent'):
                        continue
                    elif h['formula'] == 'bool':
                        val = True if 'chb_bool_' + str(h['id']) in request.POST else False
                    else:
                        val = request.POST[dict_params[h['formula']] + str(h['id'])]
                        if h['formula'] == 'float':
                            val = float(val) if val else None
                        elif h['formula'] in ('link', 'const'):
                            val = int(val) if val else None
                    # Получим текущее свойство в ветке
                    if h['id'] in branch['props'].keys():
                        old_val = branch['props'][h['id']]['value']
                    elif str(h['id']) in branch['props'].keys():
                        old_val = branch['props'][str(h['id'])]['value']
                    else:
                        old_val = None
                    if val != old_val:
                        is_change = True
                        is_new_param = False
                        try:
                            param = object_manager.get(parent_structure_id=class_id, code=code, name_id=h['id'])
                            param.value = val
                        except ObjectDoesNotExist:
                            param = ContractCells if is_contract else Objects
                            param = param(parent_structure_id=class_id, code=code, name_id=h['id'], value=val)
                            is_new_param = True
                        param.save()
                        # регистрация
                        inc = {'class_id': class_id, 'location': location, 'type': 'tree', 'name': h['id'], 'code': code,
                               'id': param.id, 'value': old_val}
                        out = inc.copy()
                        out['value'] = val
                        if is_new_param:
                            reg = {'json': out}
                            reg_id = 13
                        else:
                            reg = {'json': out, 'json_income': inc}
                            reg_id = 15
                        reg_funs.simple_reg(request.user.id, reg_id, timestamp, transact_id, None, **reg)
                        # внесем его в ветку
                        if h['id'] in branch['props'].keys():
                            branch['props'][h['id']] = {'value': val}
                        else:
                            branch['props'][str(h['id'])] = {'value': val}
                        if h['formula'] == 'link':
                            object = branch['props']
                            branch['props'] = convert_funs.select_related((object, ), h)[0]
                        elif h['formula'] == 'const':
                            formula = next(hc['value'] for hc in h['const'] if hc['id'] == val)
                            result = convert_funs.static_formula(formula, request.user.id)
                            if h['id'] in branch['props'].keys():
                                branch['props'][h['id']]['result'] = result
                            else:
                                branch['props'][str(h['id'])]['result'] = result
            if is_valid:
                if is_change:
                    message = 'Ветка успешно изменена\n'
                else:
                    message = 'Вы ничего не изменили. Ветка не сохранена\n'
            else:
                message += msg
                message += 'Изменения не сохранены\n'
                message_class = 'text-red'
        # если новая ветка
        else:
            is_valid, msg = validation()
            if is_valid:
                # Проверим поле "имя"
                header_name = next(h for h in headers if h['name'] == 'name')
                is_valid = valid_name(header_name)
                if not is_valid:    msg += 'Имя ветки задано некорректно. В данном дереве уже есть ветка с таким именем\n'
            if is_valid:
                new_obj_manager = ContractCells if is_contract else Objects
                location = 'contract' if is_contract else 'table'
                new_code = database_funs.get_code(class_id, location)
                # регистрируем объект
                outcoming = {'class_id': class_id, 'code': new_code, 'type': 'tree', 'location': location}
                reg = {'json': outcoming}
                transact_id = reg_funs.get_transact_id(class_id, new_code, request.GET['location'])
                reg_funs.simple_reg(request.user.id, 5, timestamp, transact_id, **reg)
                new_obj = []
                new_name = None
                for h in headers:
                    if h['name'] == 'is_right_tree' or h['formula'] == 'eval':
                        continue
                    elif h['name'] == 'name':
                        val = request.POST['i_name']
                        new_name = val
                    elif h['name'] == 'parent':
                        val = int(request.POST['i_parent']) if request.POST['i_parent'] else None
                    elif h['formula'] == 'bool':
                        if 'chb_bool_' + str(h['id']) in request.POST:
                            val = True
                        else:   val = False
                    elif h['formula'] in ('float', 'link', 'const'):
                        val = request.POST[dict_params[h['formula']] + str(h['id'])]
                        if val:
                            val = int(val)
                    else:
                        val = request.POST[dict_params[h['formula']] + str(h['id'])]
                    if val or  h['name'] == 'parent':
                        new_prop = new_obj_manager(parent_structure_id=class_id, name_id=h['id'], code=new_code,
                                                    value=val)
                        new_prop.save()
                        new_obj.append(new_prop)
                        # регистрируем свойство объекта
                        outcoming['id'] = new_prop.id
                        outcoming['name'] = new_prop.name_id
                        outcoming['value'] = new_prop.value
                        reg = {'json': outcoming}
                        reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                message = 'Ветка успешно создана. code: ' + str(new_code) + ', Имя: ' + request.POST['i_name']
                # обновление сессии
                branch = {'code': new_code, 'name': new_name, 'parent': parent, 'opened': False}
                props = {}
                exclude_ids = [h['id'] for h in headers if h['name'] in ('is_right_tree', 'name', 'parent')]
                for no in new_obj:
                    if no.name_id in exclude_ids:
                        continue
                    props[no.name_id] = {'value': no.value}
                branch['props'] = props
                if parent:
                    parent_branch = tree_funs.find_branch(tree, 'code', parent)
                    if not 'children' in parent_branch:
                        parent_branch['children'] = []
                    parent_branch['children'].append(branch)
                else:
                    tree.append(branch)
                tree_funs.open_branch(branch, tree) # открыть ветку
            else:
                message += msg
                message += 'Изменения не сохранены'
                message_class = 'text-red'

    # Выделить ветку
    elif 'branch_code' in request.POST:
        if branch:
            if 'children' in branch:
                if not branch['opened']:
                    branch['opened'] = True
                else:
                    branch['opened'] = False
                if not branch['children']:
                    branch['children'] = tree_funs.get_children_branches(code, class_id, is_contract)
                    branch['children'] = tree_funs.get_branch_props(branch['children'], class_id, headers, request.user.id, is_contract)
            # Если ткнули в отфильтрованный список - очистим поиск и выведем дерево
            if 'input_search' in request.POST and request.POST['input_search']:
                tree_funs.open_branch(branch, tree)
                request.POST._mutable = True
                del request.POST['input_search']
                request.POST._mutable = False

    # Кнопка "Удалить"
    elif 'b_delete' in request.POST:
    # Выделен ли объект
        is_valid = True
        if 'i_code' in request.POST and request.POST['i_code']:
            # Проверим, существует ли ветка
            if not branch:
                is_valid = False
                message = 'Ветки не существует\n'
            # Проверка, нет ли дочерних объектов - справочников, контрактов
            elif tree_funs.check_children_objects(branch, class_id, is_contract):
                is_valid = False
                message = 'У данной ветки есть объекты\n'
        else:
            is_valid = False
            message = 'Ветка не выделена\n'
        if is_valid:
            transaction_id = None
            # Каскадное удаление ветки
            delete_codes = tree_funs.rlpfb(branch, 'code')
            delete_objects = object_manager.filter(parent_structure_id=class_id, code__in=delete_codes)\
                .select_related('name').order_by('code')
            code = None
            location = 'contract' if is_contract else 'table'
            incoming = {'class_id': class_id, 'location': location, 'type': 'tree'}
            for do in delete_objects:
                # Если код сменился - удалим объект
                if code != do.code:
                    code = do.code
                    inc = incoming.copy()
                    inc['code'] = code
                    transaction_id = reg_funs.get_transact_id(class_id, code, location[0])
                    reg = {'json_income': inc}
                    reg_funs.simple_reg(request.user.id, 8, timestamp, transaction_id, **reg)
                # Удалим реквизит
                inc = incoming.copy()
                inc['code'] = code
                inc['id'] = do.id
                inc['name'] = do.name_id
                inc['value'] = do.value
                reg = {'json_income': inc}
                reg_funs.simple_reg(request.user.id, 16, timestamp, transaction_id, **reg)
            delete_objects.delete()
            tree_funs.del_branch(tree, branch['code'])
            message = 'Ветка успешно удалена\n'
        else:
            message_class = 'text-red'
            message += 'Удаление невозможно'

    # Фильтрация
    fnd_tree = []
    show_find_result = False
    if 'input_search' in request.POST and request.POST['input_search']:
        try:
            search_code = int(request.POST['input_search'])
        except:
            search_code = None
        # Если введено целое число - ищем по коду ветки
        if search_code:
            is_done = False
            parent = search_code
            codes = []
            while not is_done:
                find_branch = tree_funs.find_branch(tree, 'code', parent)
                if find_branch:
                    is_done = True
                    branch = find_branch
                    while codes:
                        branch['opened'] = True
                        cur_code = codes.pop()
                        branch['children'] = tree_funs.get_children_branches(branch['code'], class_id, is_contract)
                        branch = next(b for b in branch['children'] if b['code'] == cur_code)
                    tree_funs.open_branch(branch, tree)
                else:
                    find_object = object_manager.filter(parent_structure_id=class_id, code=parent, name__name='parent')
                    if find_object:
                        parent = find_object[0].value
                        codes.append(find_object[0].code)
                    else:
                        is_done = True
                        branch = None
        else:
            show_find_result = True
            fnd_tree += tree_funs.filter_branches(tree, 'name', request.POST['input_search'], is_part=True)
    # Добавим Заголовки первых четырех видимых параметров
    visible_headers = [h for h in request.session['temp_object_manager']['headers'] if h['is_visible']][:4]

    # данные для таймлайна
    if 'date_to' in request.POST and request.POST['date_to']:
        str_date_to = request.POST['date_to']
        date_to = datetime.strptime(str_date_to, '%Y-%m-%dT%H:%M')
    else:
        date_to = timestamp
        str_date_to = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
    if 'date_from' in request.POST and request.POST['date_from']:
        str_date_from = request.POST['date_from']
        date_from = datetime.strptime(str_date_from, '%Y-%m-%dT%H:%M')
    else:
        date_from = date_to - relativedelta(months=1)
        str_date_from = datetime.strftime(date_from, '%Y-%m-%dT%H:%M')
    if date_to < date_from:
        date_to, date_from = date_from, date_to
    if branch:
        timeline = hist_funs.roh(class_id, branch['code'], location, date_from, date_to, request.session['temp_object_manager'])
        if timeline['timeline']:
            last_event = convert_procedures.str_datetime_to_rus(timeline['timeline'][-1]['date_update']) + \
                         ' ' + timeline['timeline'][-1]['user']
        else:
            last_rec = RegistratorLog.objects.filter(reg_name_id__in=(13, 15), json_class=class_id,
                                                     json__code=branch['code'],
                                                     json__type='tree', json__location=location).order_by('-date_update') \
                           .select_related('user').values('date_update', 'user__first_name', 'user__last_name')[:1]
            last_event = datetime.strftime(last_rec[0]['date_update'], '%d.%m.%Y %H:%M:%S') + ' ' + \
                         last_rec[0]['user__first_name'] + ' ' + last_rec[0]['user__last_name'] if last_rec else ''
        page_quantity = int(int(len(timeline['timeline']) - 1) / 10 + 1)
        max_pos = 9 if page_quantity > 1 else len(timeline['timeline']) - 1
    else:
        last_event = None; str_date_from = None; str_date_to = None; timeline = None; page_quantity = None; max_pos = None
    timeline_data = {'last_event': last_event, 'date_from': str_date_from, 'date_to': str_date_to,
                     'timeline_array': timeline, 'page_quantity': page_quantity, 'max_pos': max_pos}
    session_funs.crqd(request, is_contract)  # контрольный пересчет количества черновиков
    ctx = {
        'title': title,
        'message': message,
        'message_class': message_class,
        'branch': branch,
        'fnd_tree': fnd_tree,
        'show_find_result': show_find_result,
        'tree_visible_headers': visible_headers,
        'is_contract': is_contract,
        'db_loc': location[0],
        'timeline_data': timeline_data
    }
    return render(request, 'objects/tree.html', ctx)