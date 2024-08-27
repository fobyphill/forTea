import json
import operator
import re
from copy import deepcopy
from datetime import datetime
from functools import reduce

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, OuterRef, Subquery
from django.forms import model_to_dict
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
import app.functions.database_funs
import app.functions.reg_funs
from app.functions import convert_funs, common_funs, reg_funs, database_funs, session_funs, database_procedures, \
    interface_funs, tree_funs, interface_procedures, api_procedures, task_funs, convert_funs2, object_funs, \
    convert_procedures
from app.models import Designer, Objects, Dictionary, DictObjects, ContractCells, Contracts, TableDrafts, TechProcess, Tasks


def manage_object(request):
    if request.user.is_authenticated:
        if not ('class_id' in request.GET and request.GET['class_id']):
            first_class = Designer.objects.filter(formula='table').values('id')
            if first_class:
                first_id = str(first_class[0]['id'])
                return redirect('/manage-object?class_id=' + first_id)
            else:
                return render(request, 'handbooks/manage-object.html', {'current_class': None})
        # загрузить дерево классов в сессию
        if not 'class_tree' in request.session:
            session_funs.update_class_tree(request)
        # Загрузить меню справочников
        if not 'class_menu' in request.session:
            request.session['class_menu'] = session_funs.update_class_menu(request, request.session['class_tree'],
                                                                           request.session['class_tree'])
        # Загрузим меню черновиков
        if not 'draft_tree' in request.session:  # загрузить дерево черновиков в сессию
            session_funs.update_draft_tree(request)
        session_funs.update_omtd(request)  # проверим временные данные менеджера объектов в сессии
        tree = request.session['temp_object_manager']['tree'] if 'tree' in request.session['temp_object_manager'] else None

        # Проброска данных из гет в пост
        to_post_redirect = interface_funs.get_to_post(request, ('class_id', ))
        if to_post_redirect:
            return to_post_redirect

        message = request.POST['message'] if 'message' in request.POST else ''
        message_class = ''

        class_id = int(request.GET['class_id'])
        try:
            current_class = Designer.objects.get(id=class_id)
        except:
            return HttpResponse('не найден класс с ID = ' + request.GET['class_id'])
        if current_class.formula not in ('table', 'array', 'alias'):
            return HttpResponse('не найден справочник, массив или константа с ID = ' + request.GET['class_id'])
        headers = request.session['temp_object_manager']['headers']
        code = int(request.POST['i_code']) if 'i_code' in request.POST and request.POST['i_code'] else None
        timestamp = datetime.now()
        title = 'Справочник' if current_class.formula == 'table' else 'Массив'
        title += ' "' + current_class.name + '"'

        # Заполним собственников при необходимости
        if current_class.formula == 'array' and not 'owners' in request.session['temp_object_manager']:
            owner_name = Designer.objects.get(parent_id=current_class.parent_id, name='Наименование')
            owners = Objects.objects.filter(parent_structure_id=current_class.parent_id, name_id=owner_name.id)
            request.session['temp_object_manager']['owners'] = convert_funs.query_to_json(owners)

        # Если выводим алиасы - перенаправим
        if current_class.formula == 'alias':
            ctx = view_alias(request)
            return render(request, 'handbooks/view-alias.html', ctx)

        # Кнопка "Сохранить"
        if 'b_save' in request.POST:
            # запомним код ветки, если мы на дереве
            old_parent_branch = None
            if 'i_branch' in request.POST and code:
                old_parent_branch_obj = Objects.objects.filter(parent_structure_id=class_id, code=code, name__name='parent_branch')
                if old_parent_branch_obj:
                    old_parent_branch = old_parent_branch_obj[0].value

            is_saved, message, message_class, code, transact_id, timestamp = \
                interface_funs.save_object(request, class_id, code, current_class, headers)
            draft_ver = int(request.POST['s_draft_vers']) if 's_draft_vers' in request.POST and \
                                                             request.POST['s_draft_vers'] else None
            if is_saved and code and draft_ver:
                TableDrafts.objects.get(id=int(request.POST['s_draft_vers'])).delete()
                session_funs.update_draft_tree(request)
            # обновим свойства ветки
            if is_saved and 'i_branch' in request.POST:
                branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
                # если изменилась ветка объекта - пересчитаем старую ветку
                if branch_code != old_parent_branch:
                    old_branch = tree_funs.find_branch(tree, 'code', old_parent_branch)
                    if not old_branch and old_parent_branch:
                        old_branch = tree_funs.antt(old_parent_branch, tree, current_class.parent_id,
                                                    request.session['temp_object_manager']['tree_headers'], request.user.id)
                    while old_branch:
                        tree_funs.get_branch_props((old_branch,), current_class.parent_id,
                                                   request.session['temp_object_manager']['tree_headers'], request.user.id)
                        old_branch = tree_funs.find_branch(tree, 'code', old_branch['parent'])
                # В любом случае пересчитаем новую ветку
                branch = tree_funs.find_branch(tree, 'code', branch_code)
                if not branch and request.POST['i_branch']:
                    branch = tree_funs.antt(branch_code, tree,  current_class.parent_id,
                                            request.session['temp_object_manager']['tree_headers'], request.user.id)
                while branch:
                    tree_funs.get_branch_props((branch, ), current_class.parent_id,
                                               request.session['temp_object_manager']['tree_headers'], request.user.id)
                    branch = tree_funs.find_branch(tree, 'code', branch['parent'])
            # Если справочник новый - редиректим
            if is_saved and not request.POST['i_code']:
                request.POST._mutable = True
                if not 'input_owner' in request.POST:
                    request.POST['input_search'] = str(code)
                request.POST._mutable = False

        # Кновка "В черновик"
        elif 'b_draft' in request.POST:
            interface_funs.make_graft(request, current_class.id, headers, code, request.user.id, False)
            message += 'Черновик был создан<br>'

        # Кнопка "Скачать файл"
        elif 'b_save_file' in request.POST:
            response = interface_funs.download_file(request)
            if response:    return response

        # кнопка "Удалить файл"
        elif 'b_del_file' in request.POST:
            if not interface_funs.delete_file(request, headers):
                message += 'Нельзя удалить файл. Поле является обязательным.<br>'
                message_class = 'text-red'
            else:   message = 'Файл успешно удален<br>'

        # Кнопка "Удалить"
        elif 'b_delete' in request.POST:
            # Выделен ли объект
            if 'i_code' in request.POST and request.POST['i_code']:
                delete_valid = True
                # Проверка, нет ли дочерних объектов
                res_check_child = api_procedures.fc4c(class_id, code, 'table')

                if res_check_child != 'ok':
                    message = res_check_child
                    delete_valid = False

                objects_delete = Objects.objects.filter(code=request.POST['i_code'],
                                                        parent_structure_id=class_id).select_related('name')

                # Проверим, существует ли элемент
                if not objects_delete:
                    delete_valid = False
                    message += 'Объекта нет в базе данных. Удаление невозможно<br>'
                # Проверим, есть ли у объекта незавершенные отложенные значения
                if delete_valid:
                    # Подготовка к удалению
                    # Регистрация
                    incoming = {'class_id': class_id, 'location': 'table', 'type': current_class.formula,
                                'code': code}
                    # регистрируем удаление реквизитов
                    transaction_id = reg_funs.get_transact_id(class_id, code)
                    for od in objects_delete:
                        ic = incoming.copy()
                        ic['id'] = od.id
                        ic['name'] = od.name_id
                        ic['value'] = od.value
                        reg = {'json_income': ic, 'jsone_string_income': None}
                        reg_funs.simple_reg(request.user.id, 16, timestamp, transaction_id, **reg)
                    # регистрация удаления объекта
                    reg = {'json_income': incoming}
                    reg_funs.simple_reg(request.user.id, 8, timestamp, transaction_id, **reg)
                    # Удалим связанные таски
                    for task in Tasks.objects.filter(data__class_id=class_id, data__code=code, data__location='t'):
                        task_funs.delete_simple_task(task, timestamp, parent_transact=transaction_id)

                    # Удаляем
                    objects_delete.delete()
                    message = 'Объект успешно удален.<br>Код объекта: ' + request.POST['i_code'] + '<br>'

                    # Удалим связанные словари
                    for md in request.session['temp_object_manager']['my_dicts']:
                        database_procedures.delete_dict_records(int(request.POST['i_code']), md['id'], request.user.id,
                                                                timestamp, transaction_id)
                else:
                    message_class = 'text-red'
            else:
                message = 'Вы не выбрали объект для удаления<br>'

        # кнопка "удалить словарь"
        elif 'b_delete_dict' in request.POST and request.POST['delete_dict']:
            database_procedures.delete_dict_records(int(request.POST['i_code']), int(request.POST['delete_dict']),
                                                    request.user.id)
            message = 'Объект сохранен<br>'

        # Выделить ветку
        branch = None
        if tree:
            tree_id = request.session['temp_object_manager']['tree_headers'][0]['parent_id']
            if 'branch_code' in request.POST:
                branch_code = int(request.POST['branch_code'])
                branch = interface_funs.check_branch(request, tree_id, branch_code)
            elif 'branch' in request.POST and request.POST['branch']:
                branch_code = int(request.POST['branch'])
                branch = tree_funs.find_branch(tree, 'code', branch_code)

            # Перейти на страницу управления веткой
            elif 'edit_branch' in request.POST:
                address = '/tree?class_id=' + str(current_class.parent_id) + '&location=t' + '&input_search=' + \
                          request.POST['edit_branch']
                return redirect(address)

        # вывод
        query = Objects.objects.filter(parent_structure_id=class_id)
        query, search_filter = interface_funs.sandf(request, query, headers, tree, branch)

        # Пагинация и конвертация
        q_items = int(request.POST['q_items_on_page']) if 'q_items_on_page' in request.POST else 10
        page_num = int(request.POST['page']) if 'page' in request.POST and request.POST['page'] else 1
        paginator = common_funs.paginator_object(query, q_items, page_num)
        visible_headers, vhids = interface_procedures.pack_vis_headers(current_class, headers)
        objects = Objects.objects.filter(code__in=paginator['items_codes'],
                                         parent_structure_id=class_id, name_id__in=vhids)\
                .select_related('parent_structure', 'name')
        objects = convert_funs.queyset_to_object(objects)
        objects.sort(key=lambda x: x['code'], reverse=True)
        # Конвертнем поля
        convert_funs.prepare_table_to_template(visible_headers, objects, request.user.id)
        # добавим словари
        convert_funs.add_dicts(objects, request.session['temp_object_manager']['my_dicts'])
        session_funs.crqd(request)  # контрольный пересчет количества черновиков

        # Видимые заголовки дерева
        if tree:
            tree_visible_headers = []
            for th in request.session['temp_object_manager']['tree_headers']:
                if th['is_visible']:
                    tree_visible_headers.append(th)
                if len(tree_visible_headers) > 4:
                    break
        else:
            tree_visible_headers = None

        totals = convert_procedures.gtfol(objects, visible_headers)  # Итоги

        # Периоды таймлайна
        timeline_to = timestamp + relativedelta(minutes=1)
        timeline_from = timeline_to - relativedelta(months=1)
        ctx = {
            'title': title,
            'message': message,
            'message_class': message_class,
            'current_class': current_class,
            'paginator': paginator,
            'branch': branch,
            'headers': headers,
            'objects': objects,
            'tree_visible_headers': tree_visible_headers,
            'timeline_to': timeline_to.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeline_from': timeline_from.strftime('%Y-%m-%dT%H:%M:%S'),
            'is_contract': 'false',
            'db_loc': 't',
            'visible_headers': visible_headers,
            'totals': totals,
            'search_filter': search_filter
        }
        return render(request, 'handbooks/manage-object.html', ctx)
    else:
        return HttpResponseRedirect(reverse('login'))


def manage_class_tree(request):
    if request.user.is_authenticated:
        message = ''
        message_class = ''
        session_funs.add_aliases(request)  # добавим в сессию алиасы

        if not 'class_tree' in request.session:  # загрузить дерево классов в сессию
            session_funs.update_class_tree(request)
            if 'contract_tree' in request.session:
                del request.session['contract_tree']
        if not 'draft_tree' in request.session:  # загрузить дерево черновиков в сессию
            session_funs.update_draft_tree(request)
        if not 'class_menu' in request.session:  # Загрузить меню справочников
            request.session['class_menu'] = session_funs.update_class_menu(request, request.session['class_tree'],
                                                                           request.session['class_tree'])
            if 'contract_menu' in request.session:
                del request.session['contract_menu']

        # Редиректим из гет в пост
        to_post_redirect = interface_funs.get_to_post(request, ('i_id', ))
        if to_post_redirect:
            return to_post_redirect

        timestamp = datetime.now()
        class_manager = Dictionary.objects if 'is_dict' in request.POST or ('i_type' in request.POST and
                                                                            request.POST['i_type'] == 'Словарь') \
            else Designer.objects

        # Удалить поле класса и зарегать удаление
        def delete_field(df, delete_folder, timestamp, transact_id):
            try:
                # Извещение и удаление
                message = 'Удален параметр справочника.<br>ID справочника: ' + request.POST['i_id'] \
                          + '; Название справочника:' + delete_folder.name + '<br>' \
                          + 'ID параметра: ' + str(df.id) + '; Название параметра: ' + df.name
                # регистрация операции
                incoming = {'class_id': delete_folder.id, 'location': 'table', 'type': delete_folder.formula}

                json_del_field = model_to_dict(df)
                del json_del_field['priority']
                del json_del_field['parent']
                incoming.update(json_del_field)
                reg = {'json_income': incoming}
                reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
                # Удалим реквизиты объектов этого поля
                objects = Objects.objects.filter(name_id=df.id, parent_structure_id=delete_folder.id)
                if objects:
                    # регистрация удаления объекта
                    incoming = {'class_id': delete_folder.id, 'location': 'table', 'type': delete_folder.formula}
                    for o in objects:
                        json_inc = incoming.copy()
                        o = model_to_dict(o)
                        del o['parent_structure']
                        json_inc.update(o)
                        reg = {'json_income': json_inc}
                        transact_code = reg_funs.get_transact_id(delete_folder.id, o['code'])
                        reg_funs.simple_reg(request.user.id, 16, timestamp, transact_code, transact_id, **reg)
                objects.delete()
                df.delete()
                return True, message
            except Exception as ex:
                return False, 'Ошибка удаления - "' + str(ex) + '"'

        # Удалить поле алиаса и зарегать удаление
        def delete_alias(del_param, parent, timestamp, transact_id):
            # Регистрация
            incoming = {'class_id': parent.id, 'location': 'table', 'type': 'alias'}
            param_income = {'name': del_param.name, 'value': del_param.value, 'id': del_param.id}
            incoming.update(param_income)
            reg = {'json_income': incoming}
            reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
            # Известим
            message = 'Успешно удален параметр константы. ID: ' + str(del_param.id) + '<br>' + \
                'Название: "' + del_param.name + '"<br>' + \
                'ID константы: ' + str(del_param.parent_id) + '<br>' + \
                'Наименование константы: "' + parent.name + '"<br>'
            # Удалим
            del_param.delete()
            return message

        # Кнопка "Сохранить"
        if 'b_save' in request.POST:
            # Если редактируем
            if request.POST['i_id']:
                id = int(request.POST['i_id'])
                name = request.POST['i_name']
                edited_unit = Designer.objects.get(id=id) if request.POST['i_type'] != 'Словарь' else Dictionary.objects.get(id=id)
                parent_id = int(request.POST['i_parent']) if request.POST['i_parent'] else None
                res_valid = interface_funs.ecv(id, name, edited_unit.formula, parent_id)
                if res_valid == 'ok':
                    is_valid = True
                else:
                    is_valid = False
                    message += res_valid
                # регистрационные данные
                json_income = {'class_id': edited_unit.id, 'location': 'table', 'type': edited_unit.formula}
                json_outcome = json_income.copy()
                # Проверим, изменились ли данные
                is_change = False
                if name != edited_unit.name:
                    is_change = True
                    json_income['name'] = edited_unit.name
                    json_outcome['name'] = name
                    edited_unit.name = name
                # айди родителя
                old_parent_id = str(edited_unit.parent_id) if edited_unit.parent_id else ''
                is_change_parent = False
                if request.POST['i_parent'] != old_parent_id:
                    is_change = True
                    json_income['parent'] = edited_unit.parent_id
                    json_outcome['parent'] = parent_id
                    edited_unit.parent_id = parent_id
                    is_change_parent = True
                if is_change:
                    if is_valid:
                        edited_unit.save()
                        cat_class = {'folder': 'Каталог', 'table': 'Справочник', 'alias': 'Константа', 'array': 'Массив',
                                     'dict': 'Словарь', 'tree': 'Дерево'}
                        updated = {'folder': 'обновлен', 'table': 'обновлен', 'alias': 'обновлена', 'array': 'обновлен',
                                   'dict': 'обновлен', 'tree': 'обновлено'}
                        message = cat_class[edited_unit.formula] + ' "' + request.POST['i_name'] + '" ' + updated[edited_unit.formula]
                        # Правка сессии
                        session_funs.update_class_tree(request)
                        request.session['class_menu'] = session_funs.update_class_menu(request, request.session['class_tree'],
                                                                                        request.session['class_tree'])
                        request.session['draft_menu'] = session_funs\
                            .update_class_menu(request, request.session['class_tree'], request.session['class_tree'],
                                               is_draft=True)
                        # Если справочник перешел под управление деревом - внесем дополнительное поле
                        if edited_unit.formula == 'table' and edited_unit.parent_id and is_change_parent:
                            if Designer.objects.get(id=parent_id).formula == 'tree':
                                header_tree = Designer.objects.filter(parent_id=edited_unit.id, name='parent_branch')
                                if not header_tree:
                                    parent_branch = Designer(name='parent_branch', formula='float', priority=1,
                                                             parent_id=edited_unit.id, is_required=True, is_visible=False)
                                    parent_branch.save()

                        # регистрация
                        reg = {
                            'json': json_outcome,
                            'json_income': json_income,
                        }
                        transact_id = reg_funs.get_transact_id(id, 0)
                        reg_funs.simple_reg(request.user.id, 3, timestamp, transact_id, **reg)
                    else:
                        message_class = 'text-red'
                        message += 'Данные не сохранены'
                else:
                    message = 'Вы не внесли изменений. Данные не сохранены'
            # Если новый класс
            else:
                # Проверка валидности
                parent_id = int(request.POST['i_parent']) if request.POST['i_parent'] else None
                class_types = list(k for k in request.session['class_types'].keys())
                msg = interface_funs.ccv(request.POST['i_name'], request.POST['s_folder_class'], class_types, parent_id)
                if msg == 'ok':
                    parent_id = int(request.POST['i_parent']) if request.POST['i_parent'] else None
                    # создаем словарь
                    if request.POST['s_folder_class'] == 'dict':
                        new_unit = Dictionary(name=request.POST['i_name'], formula='dict', parent_id=parent_id,
                                              default='table')
                    # Создаем техпроцесс
                    elif request.POST['s_folder_class'] == 'techprocess':
                        new_unit = TechProcess(name=request.POST['i_name'], formula='techprocess', parent_id=parent_id)
                    # создаем класс
                    else:
                        new_unit = Designer(name=request.POST['i_name'], formula=request.POST['s_folder_class'],
                                            parent_id=parent_id, is_required=0)
                    new_unit.save()
                    # Добавим обязательные поля для соответствующих типов классов
                    new_unit_name = ''
                    val = ''
                    formula = ''
                    if request.POST['s_folder_class'] == 'table':
                        new_unit_name = 'Наименование'
                        formula = 'string'
                        val = ''
                    elif request.POST['s_folder_class'] == 'array':
                        new_unit_name = 'Собственник'
                        formula = 'link'
                        val = 'table.' + request.POST['i_parent']
                    elif request.POST['s_folder_class'] == 'tree':
                        new_unit_name = 'is_right_tree'
                        formula = 'bool'
                        val = True
                    elif request.POST['s_folder_class'] == 'techprocess':
                        TechProcess(name='business_rule', formula='eval', parent_id=new_unit.id).save()
                        TechProcess(name='link_map', formula='eval', parent_id=new_unit.id).save()
                        TechProcess(name='trigger', formula='eval', parent_id=new_unit.id).save()
                        TechProcess(name='stages', formula='enum', parent_id=new_unit.id).save()
                    if new_unit_name:
                        req_field = Designer(parent_id=new_unit.id, formula=formula, name=new_unit_name, value=val,
                                            is_required=True, is_visible=True, priority=1)
                        if req_field.formula == 'tree':
                            req_field.is_visible = False
                            req_field.system = True
                        req_field.save()
                        # для дерева добавим дополнительные поля - имя, родитель
                        if request.POST['s_folder_class'] == 'tree':
                            Designer(parent_id=new_unit.id, formula='string', name='name', is_required=True,
                                     is_visible=False, priority=1).save()
                            Designer(parent_id=new_unit.id, formula='link', name='parent', is_required=True,
                                     is_visible=False, priority=1).save()
                        # для справочника под деревом добавим свойство - родительская ветка
                        elif request.POST['s_folder_class'] == 'table' and parent_id:
                            if Designer.objects.get(id=parent_id).formula == 'tree':
                                Designer(name='parent_branch', formula='float', parent_id=new_unit.id, is_required=True,
                                         is_visible=False, priority=1).save()

                    # добавим в форму айди созданного класса
                    request.POST._mutable = True
                    request.POST['i_id'] = new_unit.id
                    if request.POST['s_folder_class'] == 'dict':
                        request.POST['is_dict'] = 'true'
                    request.POST._mutable = False
                    message = 'Успешно создан класс. Тип: "' + request.session['class_types'][request.POST['s_folder_class']] \
                              + '"<br>' + \
                    'ID: ' + str(new_unit.id) + '<br>Название: "' + new_unit.name + '"<br>'
                    # Правим сессию.
                    session_funs.update_class_tree(request)
                    request.session['class_menu'] = session_funs.update_class_menu(request, request.session['class_tree'],
                                                                                   request.session['class_tree'])
                    request.session['draft_menu'] = session_funs.update_class_menu(request,
                                                                                   request.session['class_tree'],
                                                                                   request.session['class_tree'],
                                                                                   is_draft=True)
                    session_funs.update_draft_tree(request)  # обновим меню черновиков
                    # Если класс - константа - сбросим список констант в сессии
                    if new_unit.formula == 'alias':
                        del request.session['aliases']
                    # Регистрация
                    outcoming = {'class_id': new_unit.id, 'name': new_unit.name, 'type': new_unit.formula,
                                   'location': 'table', 'parent': new_unit.parent_id}
                    reg = {
                        'json': outcoming,
                    }
                    data_type = 'd' if request.POST['s_folder_class'] == 'dict' else 't'
                    transact_id = reg_funs.get_transact_id(new_unit.id, 0, data_type)
                    reg_funs.simple_reg(request.user.id, 1, timestamp, transact_id, **reg)
                else:
                    message_class = 'text-red'
                    message += msg + 'Данные не сохранены'

        # кнопка "Удалить"
        elif 'b_delete' in request.POST:
            id = int(request.POST['i_id'])
            delete_folder = Designer.objects.filter(id=id) if request.POST['i_type'] != 'Словарь' else Dictionary.objects.filter(id=id)
            if not delete_folder:
                message = 'Выбран несуществующий класс. Удаление невозможно<br>'
                message_class = 'text-red'
            else:
                is_valid = True
                delete_folder = delete_folder[0]
                # Проверка типа
                if delete_folder.formula not in request.session['class_types'].keys():
                    is_valid = False
                    message += 'Невозможно удалить данный тип<br>'
                # Проверка дочерних классов
                children_classes = None
                if request.POST['i_type'] == 'Каталог':
                    children_classes = Designer.objects.filter(parent_id=id, formula__in=['alias', 'table', 'folder', 'tree'])
                elif request.POST['i_type'] == 'Дерево':
                    children_classes = Designer.objects.filter(parent_id=id, formula='table')
                elif request.POST['i_type'] == 'Справочник':
                    children_classes = list(Designer.objects.filter(parent_id=id, formula='array'))
                    children_classes += list(
                        Dictionary.objects.filter(parent_id=id, formula='dict', default='table'))
                elif request.POST['i_type'] == 'Константа':
                    is_valid = not database_funs.chpoc(id, True)
                    if not is_valid:
                        message += 'Нельзя удалить константу, у которой есть свойства. Удалите свойства, после повторите попытку<br>'
                if children_classes:
                    is_valid = False
                    message += 'Нельзя удалить класс с дочерними классами.<br>'
                # Проверка объектов
                children_objects = None
                if request.POST['i_type'] in ['Справочник', 'Массив']:
                    children_objects = Objects.objects.filter(parent_structure_id=id)
                elif request.POST['i_type'] == 'Словарь':
                    children_objects = DictObjects.objects.filter(parent_structure_id=id)
                if children_objects:
                    is_valid = False
                    message += 'Нельзя удалить класс, у которого есть объекты.<br>'
                # Удаление
                if is_valid:
                    transact_id = reg_funs.get_transact_id(delete_folder.id, 0)
                    # Удалим папку
                    if delete_folder.formula == 'folder':
                        message = 'Каталог "' + request.POST['i_name'] + '" успешно удален. ID: ' + str(delete_folder.id)
                        # регистрация
                        incoming = {'class_id': delete_folder.id, 'type': delete_folder.formula, 'location': 'table',
                                       'name': delete_folder.name, 'parent': delete_folder.parent_id}
                        reg = {'json_income': incoming}
                        result = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                        # Удаление
                        if result:
                            delete_folder.delete()
                        else:
                            message = 'Класс ' + str(delete_folder.id) + ' не удален. Ошибка регистратора<br>'
                            message_class = 'text-red'
                    # Удалим справочник или массив
                    elif delete_folder.formula in ['table', 'array']:
                        # Удалим все поля
                        del_fields = Designer.objects.filter(parent_id=id)
                        for df in del_fields:
                            del_result, msg = delete_field(df, delete_folder, timestamp, transact_id)
                            if not del_result:
                                message = msg
                                message_class = 'text-red'
                                break
                        message = 'Класс удален. ID: ' + str(
                            delete_folder.id) + '; название: "' + delete_folder.name + '"<br>'
                        # регистрация
                        outcoming = {'class_id': delete_folder.id, 'name': delete_folder.name, 'location': 'table',
                                       'type': delete_folder.formula, 'parent': delete_folder.parent_id}
                        reg = {'json_income': outcoming}
                        res = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                        # Удаление
                        if res:
                            delete_folder.delete()
                        else:
                            message = 'Класс ' + str(delete_folder.id) + ' не удален. Ошибка регистратора<br>'
                            message_class = 'text-red'
                    # Удалим алиас
                    elif delete_folder.formula == 'alias':
                        # Удалим все параметры
                        del_params = Designer.objects.filter(parent_id=id)
                        for dp in del_params:
                            delete_alias(dp, delete_folder, timestamp, transact_id)
                        # Регистрация удаления алиаса
                        outcoming = {'class_id': delete_folder.id, 'name': delete_folder.name, 'location': 'table',
                                        'type': delete_folder.formula, 'parent': delete_folder.parent_id}
                        reg = {'json_income': outcoming}
                        reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                        # извещение
                        message = 'Константа удалена. ID: ' + str(delete_folder.id) + '<br>Название: "' + delete_folder.name + '"<br>'
                        # Удаление
                        delete_folder.delete()
                    # Удалим дерево
                    elif delete_folder.formula == 'tree':
                        # Удалим ветки дерева
                        inc = {'class_id': id, 'location': 'table', 'type': 'tree'}
                        del_branches = Objects.objects.filter(parent_structure_id=id).order_by('code')
                        obj_code = None
                        transact_code = None
                        # Регистрируем удаление объектов
                        for db in del_branches:
                            if obj_code != db.code:
                                obj_code = db.code
                                i = inc.copy()
                                i['code'] = obj_code
                                transact_code = reg_funs.get_transact_id(id, db.code)
                                reg = {'json_income': i}
                                reg_funs.simple_reg(request.user.id, 8, timestamp, transact_code, transact_id, **reg)
                            i = inc.copy()
                            i['code'] = obj_code
                            i['name'] = db.name_id
                            i['value'] = db.value
                            reg = {'json_income': i}
                            reg_funs.simple_reg(request.user.id, 16, timestamp, transact_code, transact_id, **reg)
                        del_branches.delete() # Удалим объекты
                        # Удалим все поля дерева
                        del_fields = Designer.objects.filter(parent_id=id)
                        for df in del_fields:
                            i = inc.copy()
                            json_df = model_to_dict(df)
                            del json_df['parent']
                            del json_df['priority']
                            i.update(json_df)
                            reg = {'json_income': i}
                            reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
                        del_fields.delete()
                        # регистрация удаления класса
                        incoming = {'class_id': delete_folder.id, 'name': delete_folder.name, 'location': 'table',
                                     'type': delete_folder.formula, 'parent': delete_folder.parent_id}
                        reg = {'json_income': incoming}
                        res = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                        # Удаление класса
                        if res:
                            message = 'Класс ' + str(delete_folder.id) + ' успешно удален<br>'
                            delete_folder.delete()
                        else:
                            message = 'Класс ' + str(delete_folder.id) + ' не удален. Ошибка регистратора<br>'
                            message_class = 'text-red'
                    # Удалим словарь
                    else:
                        message += 'Словарь удален. ID: ' + str(delete_folder.id) + '<br>Название: ' + delete_folder.name
                        dict_fields_del = Dictionary.objects.filter(parent_id=id).exclude(formula='dict')
                        # регистрация удаленных полей словаря
                        outcoming = {'class_id': delete_folder.id, 'location': 'table', 'type': 'dict'}
                        result_reg = True
                        transact_id = reg_funs.get_transact_id(id, 0, 'd')
                        for dfd in dict_fields_del:
                            dict_dfd = model_to_dict(dfd)
                            del dict_dfd['priority']
                            inc = outcoming.copy()
                            inc.update(dict_dfd)
                            reg = {'json_income': inc}
                            if not reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg):
                                result_reg = False
                                break
                        if result_reg:
                            dict_fields_del.delete()  # Удаление полей словаря
                        else:
                            message = 'Параметр класса ' + str(delete_folder.id) + ' не удален. Ошибка регистратора<br>'
                            message_class = 'text-red'
                        # регистрация удаления словаря
                        outcoming['parent'] = delete_folder.parent_id
                        outcoming['name'] = delete_folder.name
                        reg = {'json_income': outcoming}
                        res = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                        if res and result_reg:
                            delete_folder.delete()
                        else:
                            message += 'Класс ' + str(delete_folder.id) + ' не удален. Ошибка регистратора'
                            message_class = 'text-red'
                    # Удалим из Поста параметр i_id
                    request.POST._mutable = True
                    del request.POST['i_id']
                    request.POST._mutable = False
                    # Правка сессии
                    session_funs.update_class_tree(request)
                    request.session['class_menu'] = session_funs.update_class_menu(request, request.session['class_tree'],
                                                                                   request.session['class_tree'])
                    request.session['draft_menu'] = session_funs.update_class_menu(request,
                                                                                   request.session['class_tree'],
                                                                                   request.session['class_tree'],
                                                                                   is_draft=True)
                    session_funs.update_draft_tree(request)  # обновим меню черновиков
                else:
                    message_class = 'text-red'

        # Сохранить параметр класса
        elif 'b_save_fields' in request.POST:
            if not 'i_id' in request.POST:
                message = 'Не выбран справочник. Изменения не сохранены<br>'
                message_class = 'text-red'
            else:
                class_id = int(request.POST['i_id'])
                params = json.loads(request.POST['b_save_fields'])
                # Редактируем сохраненные свойства класса
                header = Designer.objects.get(id=class_id)
                current_dict = Designer.objects.filter(parent_id=class_id).order_by('id').exclude(formula='table')
                names_params = [cc.name.lower() for cc in current_dict]
                if header.formula == 'tree':
                    names_params.append('наименование')
                # Проверка уникальности новых имен
                new_names_params = []
                # Валидация данных и приведение типов
                is_valid = True
                all_changes = False
                transact_id = reg_funs.get_transact_id(header.id, 0)
                for p in params:
                    if p['id']:
                        if p['type'] == 'array':
                            continue
                        try:
                            cp = next(cc for cc in current_dict if cc.id == p['id'])
                        except StopIteration:
                            continue
                        else:
                            is_change = False
                            required_change = False
                            if header.formula == 'tree' and p['name'] == 'is_right_tree':
                                all_changes = interface_funs.stpirt(cp, p['value'], request.user.id, timestamp)
                            else:
                                # данные регистрации
                                incoming = {'class_id': class_id, 'type': header.formula, 'location': 'table'}
                                outcoming = incoming.copy()
                                incoming['id'] = p['id']
                                outcoming['id'] = p['id']
                                if not p['name']:
                                    is_valid = False
                                    message += 'Название параметра с ID ' + str(p['id']) + ' пустое. Заполните пожалуйста<br>'
                                if cp.name != p['name']:
                                    # проверим измененное имя. Вдруг такое есть в данном класса
                                    if p['name'].lower() in names_params:
                                        is_valid = False
                                        message += 'Название параметра "' + p['name'] + '" уже есть у данного справочника<br>'
                                    else:
                                        # исправим список имен
                                        i = 0
                                        while (i < len(names_params)):
                                            if names_params[i] == cp.name.lower():
                                                del names_params[i]
                                                break
                                            i += 1
                                            names_params.append(p['name'].lower())
                                        # Регистрирую изменение
                                        incoming['name'] = cp.name
                                        outcoming['name'] = p['name']
                                        # Внесем изменения
                                        cp.name = p['name']
                                        is_change = True
                                # видимость
                                if cp.is_visible != p['visible']:
                                    # Регистрирую изменение
                                    incoming['is_visible'] = cp.is_visible
                                    outcoming['is_visible'] = p['visible']
                                    cp.is_visible = p['visible']
                                    is_change = True
                                # итоги
                                if 'totals' in p:
                                    if not cp.settings or 'totals' not in cp.settings \
                                            or sorted(cp.settings['totals']) != sorted(p['totals']):
                                        incoming['settings'] = deepcopy(cp.settings)
                                        if incoming['settings']:
                                            outcoming['settings'] = deepcopy(incoming['settings'])
                                            outcoming['settings']['totals'] = p['totals']
                                            cp.settings['totals'] = p['totals']
                                        else:
                                            outcoming['settings'] = {'totals': p['totals']}
                                            cp.settings = {'totals': p['totals']}
                                        is_change = True
                                if cp.is_required != p['is_required']:
                                    # проверка, есть ли дефолт для обязательных полей
                                    if p['is_required'] and cp.formula not in ('eval', 'enum', 'file', 'bool') and not p['default']:
                                        is_valid = False
                                        message += 'Для обязательных параметров заполните поле "По умолчанию"<br>'
                                    # Регистрирую изменение
                                    incoming['is_required'] = cp.is_required
                                    outcoming['is_required'] = p['is_required']
                                    cp.is_required = p['is_required']
                                    is_change = True
                                    required_change = True
                                # Работаем с полем "Значение"
                                # if p['value'] != cp.value:
                                # тип ссылка или формула
                                if p['type'] in ['eval', 'enum']:
                                # для перечислений предварительно конвертим строку в список
                                    if p['type'] == 'enum':
                                        p['value'] = p['value'].split('\n')
                                    if cp.value != p['value']:
                                        # Регистрирую изменение
                                        if cp.formula == 'enum':
                                            incoming['value'] = json.dumps(cp.value, ensure_ascii=False)
                                            outcoming['value'] = json.dumps(p['value'], ensure_ascii=False)
                                        else:
                                            incoming['value'] = cp.value
                                            outcoming['value'] = p['value']
                                        cp.value = p['value']
                                        is_change = True
                                # Работаем с умолчанием
                                # Если тип данных булевый - конвертим
                                if p['type'] in ('bool', 'link', 'float', 'const'):
                                    default = str(p['default'])
                                else:
                                    default = p['default']
                                if cp.default != default:
                                    # Регистрирую изменение
                                    incoming['default'] = cp.default
                                    outcoming['default'] = default
                                    cp.default = default
                                    is_change = True

                                # Delay
                                if cp.delay != p['delay']:
                                    # Регистрирую изменение
                                    incoming['delay'] = cp.delay
                                    outcoming['delay'] = p['delay']
                                    cp.delay = p['delay']
                                    is_change = True
                                # Если делэй включен, проверим его настройки
                                if p['delay'] and 'handler' in p and cp.delay_settings['handler'] != p['handler']:
                                    incoming['delay_settings'] = {}
                                    outcoming['delay_settings'] = {}
                                    if p['handler'] and type(p['handler']) is int and not database_procedures.check_user(p['handler']):
                                        is_valid = False
                                        message += 'Некорректно указан ответственный к отложенному значению параметра ID: ' + \
                                            str(p['id']) + '<br>'

                                    if cp.delay_settings['handler'] != p['handler']:
                                        incoming['delay_settings']['handler'] = cp.delay_settings['handler']
                                        outcoming['delay_settings']['handler'] = p['handler']
                                        cp.delay_settings['handler'] = p['handler']
                                        is_change = True
                                if is_change:
                                    if is_valid:
                                        all_changes = True
                                        cp.save()
                                        names_params = [cc.name for cc in Designer.objects.filter(parent_id=class_id)]
                                        message = 'Справочник "' + request.POST['i_name'] + '" ID:' \
                                                  + request.POST['i_id'] + ' обновлен<br>'
                                        # регистрация
                                        reg = {
                                            'json_income': incoming,
                                            'json': outcoming,
                                        }
                                        reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                                        # Если включился параметр "Обязательный" - то заполним дефолтом все отсутствующие объекты
                                        if required_change and cp.is_required:
                                            object_funs.avto(header, 't', cp, transact_id, request.user.id, timestamp)

                                    else:
                                        message_class = 'text-red'
                # Создаем новый параметр
                try:
                    p = next(p for p in params if not p['id'])
                except StopIteration:
                    pass
                else:
                    is_valid = True
                    if not p['name']:
                        is_valid = False
                        message += 'Не указано имя параметра справочника. Новый параметр не сохранен<br>'
                    if p['name'] in names_params:
                        is_valid = False
                        message += 'Названия параметров справочников не должны повторяться. Новый параметр не сохранен<br>'
                    # Проверка циркулярности детей
                    if p['type'] == 'link':
                        is_child = database_funs.is_child(request.POST['i_id'], 'table',
                                                          p['value'], request.POST['chb_link_type'])
                        if is_child:
                            is_valid = False
                            message += 'Некорректный тип значения нового параметра. ' \
                                        'Либо указан потомок в качестве родителя, либо не указан родительский класс<br>'
                        else:
                            is_contract = True if request.POST['chb_link_type'] == 'contract' else False
                            class_type = database_procedures.get_class_type(p['value'], is_contract)
                            if not (class_type and class_type in ['table', 'contract']):
                                is_valid = False
                                message += 'Некорректно указан ID родителя для ссылки.<br>'
                        p['value'] = request.POST['chb_link_type'] + '.' + p['value']
                    # Проверка корректности для алиаса
                    elif p['type'] == 'const':
                        try:
                            alias_manager = Contracts.objects if p['location'] == 'contract' else Designer.objects
                            alias_manager.get(id=p['value'], formula='alias')
                        except Exception:
                            is_valid = False
                            message += 'Некорректно указан ID константы. Новый параметр не сохранен<br>'
                    elif p['type'] == 'enum':
                        p['value'] = p['value'].split('\n')
                    # Проверка обязательности
                    if p['is_required'] and p['type'] not in ('file', 'enum', 'eval', 'bool') and not p['default']:
                        is_valid = False
                        message += 'Для обязательных параметров заполните поле "По умолчанию"<br>'
                    # Если все проверки пройдены - создаем параметр
                    if is_valid:
                        # зададим приоритет
                        database_procedures.check_fix_priority(current_dict, 'table')
                        max_priority = 0
                        for cd in current_dict:
                            if cd.priority and cd.priority > max_priority:  max_priority = cd.priority

                        val = p['location'] + '.' + p['value'] if 'location' in p else p['value']
                        # Проверка настроек делэя
                        if p['delay']:
                            if p['handler']:
                                if not type(p['handler']) is int:
                                    p['handler'] = None
                                elif not database_procedures.check_user(p['handler']):
                                    p['handler'] = None

                            delay_settings = {'handler': p['handler']}
                        else:
                            delay_settings = {'handler': None}
                        if 'totals' in p and p['totals']:
                            settings = {'totals': p['totals']}
                        else:
                            settings = None
                        new_field = Designer(name=p['name'], formula=p['type'], is_required=p['is_required'],
                                             parent_id=class_id, value=val, default=p['default'],
                                             is_visible=p['visible'], priority=max_priority + 1, delay=p['delay'],
                                             delay_settings=delay_settings, settings=settings)
                        new_field.save()
                        message += 'Создан новый параметр класса \"' + request.POST['i_name'] + '\"<br>'
                        all_changes = True
                        request.session['temp_object_manager'] = {}
                        # Регистрация
                        dict_field = {
                            'id': new_field.id, 'name': new_field.name, 'formula': new_field.formula,
                            'value': new_field.value, 'is_required': new_field.is_required, 'default': new_field.default,
                            'is_visible': new_field.is_visible, 'delay': new_field.delay, 'delay_settings': delay_settings,
                            'settings': settings
                        }
                        outcome = {'class_id': header.id, 'location': 'table', 'type': header.formula}
                        outcome.update(dict_field)
                        reg = { 'json': outcome}
                        reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
                        request.session['temp_object_manager'] = {} #  обнулим временные данные объекта
                        # Если параметр обязательный - то проставим всем ранее созданным записям значение по умолчанию
                        if p['is_required']:
                            object_funs.avto(header, 't', new_field, transact_id, request.user.id, timestamp)
                    else:   message_class = 'text-red'
                if all_changes:
                    request.session['temp_object_manager'] = {}
                else:   message += 'Объект не сохранен<br>'

        # Кнопка "Удалить параметр"
        elif 'b_del_field' in request.POST:
            class_id = int(request.POST['i_id'])
            try:
                del_field = Designer.objects.get(id=int(request.POST['b_del_field']))
            except ObjectDoesNotExist:
                message += 'Не найдено свойство класса с ID: ' + request.POST['b_del_field'] + '<br>'
                is_valid = False
                del_field = None
                header = None
            else:
                header = Designer.objects.get(id=class_id)
                is_valid = True
                # для дерева: нельзя удалять три обязательных параметра
                if del_field.formula == 'tree' and del_field.name in ('name', 'parent', 'is_right_tree'):
                    is_valid = False
                    message = 'Нельзя удалять обязательные параметры'
                # Нельзя удалять обязательные параметры
                elif del_field.is_required:
                    is_valid = False
                    message = 'Нельзя удалять обязательные параметры'
            if is_valid:
                transact_id = reg_funs.get_transact_id(del_field.id, 0)
                result, message = delete_field(del_field, header, datetime.now(), transact_id)
                # пересчет приоритетов
                if result:
                    current_params = Designer.objects.filter(parent_id=class_id)
                    database_procedures.check_fix_priority(current_params, 'table')
                    request.session['temp_object_manager'] = {}
            else:
                message_class = 'text-red'

        # Сохранить параметры алиаса
        elif 'b_save_alias' in request.POST:
            alias_id = int(request.POST['i_id'])
            array = json.loads(request.POST['b_save_alias'])
            current_alias = Designer.objects.filter(parent_id=alias_id)
            names = [ca.name for ca in current_alias]
            all_changes = False
            transact_id = reg_funs.get_transact_id(alias_id, 0)
            for a in array:
                # редактируем параметры алиаса
                if a['id']:
                    # регистрационные данные
                    incoming = {'class_id': alias_id, 'location': 'table', 'type': 'alias', 'id': a['id']}
                    outcoming = incoming.copy()
                    ca = next(ca for ca in current_alias if ca.id == a['id'])
                    is_change = False
                    is_valid = True
                    # проверка имени
                    if a['name'] != ca.name:
                        is_change = True
                        for n in names:
                            if n == a['name']:
                                is_valid = False
                                message += 'Названия параметров не должны повторяться. Параметр "' + a['name']\
                                 + '" не обновлен<br>'
                                break
                        else:
                            # регистрация
                            incoming['name'] = ca.name
                            outcoming['name'] = a['name']
                            ca.name = a['name']
                            names = [ca.name for ca in current_alias]
                    # Проверка значения
                    if a['value'] != ca.value:
                        is_change = True
                        # регистрация
                        incoming['value'] = ca.value
                        outcoming['value'] = a['value']
                        ca.value = a['value']
                    if is_change and is_valid:
                        all_changes = True
                        ca.save()
                        message = 'Параметр "' + ca.name + '" успешно обновлен<br>'
                        # регистрация
                        reg = {'json_income': incoming,
                               'json': outcoming}
                        reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                # Создаем новый параметр алиаса
                else:
                    all_changes = True
                    is_valid = True
                    if not a['name']:
                        message += 'Вы не указали имя нового параметра. Данные не сохранены<br>'
                        is_valid = False
                    if a['name'] in names:
                        message += 'имена параметров не должны повторяться. Новый параметр не сохранен<br>'
                    elif is_valid:
                        new_alias = Designer(parent_id=alias_id, name=a['name'], formula='eval', value=a['value'],
                                             is_required=False)
                        new_alias.save()
                        message += 'Новый параметр сохранен.'
                        # регистрация
                        outcoming = {'class_id': alias_id, 'location': 'table', 'type': 'alias', 'id': new_alias.id,
                                     'name': new_alias.name, 'value': new_alias.value}
                        reg = {
                            'json': outcoming,
                        }
                        reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
            if not all_changes: message += 'Вы ничего не изменили. Данные не сохранены<br>'

        # Удалить параметр алиаса
        elif 'b_del_alias' in request.POST:
            param = Designer.objects.get(id=int(request.POST['b_del_alias']))
            parent = Designer.objects.get(id=int(request.POST['i_id']))
            transact_id = reg_funs.get_transact_id(parent.id, 0)
            message = delete_alias(param, parent, datetime.now(), transact_id)

        # Сохранить параметры словаря
        elif 'b_save_fields_dict' in request.POST:
            message = interface_funs.save_dict_params(request, message)

        # Сохранить параметры дерева
        elif 'b_save_fields_tree' in request.POST:
            class_id = int(request.POST['i_id'])
            new_val = True if request.POST['b_save_fields_tree'] == 'true' else False
            is_saved, message = interface_funs.stpirt(class_id, new_val, request.user.id, timestamp)
            if not is_saved:    message_class = 'text-red'

        # Удалить параметр словаря
        elif 'b_del_field_dict' in request.POST:
            message = interface_funs.delete_dict_param(request, message)

        # Сменить порядок параметра
        elif 'move' in request.POST:
            formula = 'dict' if 'is_dict' in request.POST else 'table'
            database_funs.change_class_priority(int(request.POST['i_id']), int(request.POST['param_id']),
                                                request.POST['move'], formula)

        # Если указан айди товара - выводим его свойства
        current_class = None
        properties = None
        list_formula_exclude = ('table', 'dict')
        list_name_exclude = ('parent_branch', 'parent')
        if 'i_id' in request.POST and request.POST['i_id']:
            class_id = int(request.POST['i_id'])
            if 'i_type' in request.POST and request.POST['i_type'] == 'Словарь' or 'is_dict' in request.POST:
                properties_manager = Dictionary.objects
            else:
                properties_manager = Designer.objects
            try:
                current_class = properties_manager.get(id=class_id)
            except ObjectDoesNotExist:
                pass
            properties = list(properties_manager.filter(parent_id=class_id)
                              .exclude(formula__in=list_formula_exclude).exclude(name__in=list_name_exclude)
                              .order_by('priority', 'id').values())
        # Если не указан айди объекта, то проверим систему. Если в системе нет ни одной папки,
        # то укажем свойства первого справочника или алиаса из списка
        elif not len(Designer.objects.filter(formula='folder')):
            class_tree = request.session['class_tree']
            if class_tree:
                properties = list(Designer.objects.filter(parent_id=class_tree[0]['id'])
                                  .exclude(formula__in=list_formula_exclude).exclude(name__in=list_name_exclude)
                                  .order_by('priority', 'id').values())

        session_funs.crqd(request)  # контрольный пересчет количества черновиков

        ctx = {
            'title': 'Дерево справочников',
            'message': message,
            'message_class': message_class,
            'properties': properties,
            'current_class': current_class
        }
        return render(request, 'constructors/manage-class-tree.html', ctx)
    else:
        return HttpResponseRedirect(reverse('login'))


def view_alias(request):
    # загрузить дерево классов в сессию
    if not 'class_tree' in request.session:
        session_funs.update_class_tree(request)
    # Загрузить меню справочников
    if not 'class_menu' in request.session:
        request.session['class_menu'] = session_funs.update_class_menu(request, request.session['class_tree'])
    # Загрузим меню черновиков
    if not 'draft_tree' in request.session:
        session_funs.update_draft_tree(request)

    class_id = int(request.GET['class_id'])
    header = Designer.objects.get(id=class_id)
    alias = list(Designer.objects.filter(parent_id=class_id).values())
    convert_funs2.pati(alias, user_id=request.user.id)
    ctx = {
        'title': 'Константа "' + header.name + '"',
        'alias': alias,
        'header': header
    }
    return ctx


def dictionary(request):
    if request.user.is_authenticated:
        if not ('class_id' in request.GET and request.GET['class_id']): return HttpResponseRedirect(reverse('index'))

        message = ''
        message_class = ''

        # данные черновиков справочников
        if not 'draft_tree' in request.session:  # загрузить дерево черновиков в сессию
            session_funs.update_draft_tree(request)
        # Загрузим данные черновиков контрактовв
        if not 'contract_draft_tree' in request.session:
            session_funs.update_draft_tree(request, True)

        session_funs.update_omtd(request)  # проверим временные данные менеджера объектов в сессии

        # Редиректим из гет в пост
        to_post_redirect = interface_funs.get_to_post(request, ('class_id', ))
        if to_post_redirect:
            return to_post_redirect

        dict_id = int(request.GET['class_id'])
        current_dict = request.session['temp_object_manager']['current_class']
        code = int(request.POST['i_owner']) if 'i_owner' in request.POST and request.POST['i_owner'] else None
        timestamp = datetime.now()
        headers = request.session['temp_object_manager']['headers']

        # Валидация. Вход - реквест. Выход - да/нет, сообщение
        def validation(request, new=False):
            message = ''
            is_valid = True
            # Проверка собственника
            if not request.POST['i_owner']:
                is_valid = False
                message = 'Не указан собственник. Запись словаря не сохранена<br>'
            else:
                owner = int(request.POST['i_owner'])
                manager = Objects.objects if request.POST['parent_type'] == 'table' else ContractCells.objects
                if not manager.filter(code=owner):
                    is_valid = False
                    message = 'Собственника с кодом ' + request.POST['i_owner'] + ' не существует<br>'
                else:
                    # Проверим, не занят ли собственник
                    if new and DictObjects.objects.filter(code=owner, parent_structure_id=request.GET['class_id']):
                        is_valid = False
                        message = 'У выбранного собственника уже есть запись из данного словаря<br>'
            for k, v in request.POST.items():
                try:
                    field_id = int(re.search(r'^(ta|i|i_datetime|i_link|i_float)_(?P<id>\d+)$', k).group('id'))
                except AttributeError:
                    continue
                else:
                    current_field = next(h for h in headers if h['id'] == int(field_id))
                    # Проверяем только заполненные поля. Пустые игнорим
                    if v:
                        # 3. Проверка числового поля
                        if current_field['formula'] == 'float':
                            try:
                                float(v)
                            except ValueError:
                                is_valid = False
                                message += ' Некорректно указано значение поля \"' + current_field['name'] + '\".<br>'
                        # 4. Проверка формата ДатаВремя
                        elif current_field['formula'] == 'datetime':
                            try:
                                datetime.strptime(v, '%Y-%m-%dT%H:%M:%S')
                            except ValueError:
                                is_valid = False
                                message += ' Некорректно указано значение поля \"' + current_field['name'] + '\".<br>'
                        # 5. Проверка формата Дата
                        elif current_field['formula'] == 'date':
                            try:
                                datetime.strptime(v, '%Y-%m-%d')
                            except ValueError:
                                is_valid = False
                                message += ' Некорректно указано значение поля \"' + current_field['name'] + '\".<br>'
                        # 6/ Проверка ссылки
                        elif current_field['formula'] == 'link':
                            header_link = re.match(r'(?:table|contract)\.(\d+)\.', current_field['default'])[0] + v
                            link_valid = interface_procedures.cdl(header_link)
                            if not link_valid:
                                message += 'Некорректно указана ссылка<br>'
                                is_valid = False
            return is_valid, message

        # Кнопка "Сохранить"
        if 'b_save' in request.POST:
            # class_params = Dictionary.objects.filter(parent_id=request.GET['class_id'])
            transact_id = None
            # редактируем
            is_valid, message = validation(request)
            if is_valid:
                dict_objects = DictObjects.objects.filter(code=code, parent_structure_id=dict_id).select_related('name')
                general_data_reg = {'class_id': current_dict['id'], 'location': current_dict['default'], 'type': 'dict',
                                    'code': code}
                edit_objects = []
                new_objects = []
                # были ли внесены изменения
                for k, v in request.POST.items():
                    try:
                        field_id = int(re.search(r'^(ta|chb|i_datetime|i_date|i_float|s_enum|i_link)_(?P<id>\d+)$',
                                                 k).group('id'))
                    except AttributeError:
                        continue
                    else:
                        try:
                            o = next(o for o in dict_objects if o.name_id == field_id)
                        except StopIteration:
                            o = DictObjects(name_id=field_id, parent_structure_id=dict_id,
                                        code=code, value='')
                        if o.value != v:
                            old_value = o.value
                            o.value = v
                            if o.id:    edit_objects.append({'old_value': old_value, 'edited_req': o})
                            else:   new_objects.append(o)
                # Если изменения были, то внесем их
                is_save = False
                if edit_objects:
                    is_save = True
                    DictObjects.objects.bulk_update([eo['edited_req'] for eo in edit_objects], ['value'])
                    transact_id = app.functions.reg_funs.get_transact_id(dict_id, code, 'd')
                    # Регистрация
                    for eo in edit_objects:
                        ic = general_data_reg.copy()
                        ic['id'] = eo['edited_req'].id
                        ic['name'] = eo['edited_req'].name_id
                        ic['value'] = eo['old_value']
                        oc = ic.copy()
                        oc['value'] = eo['edited_req'].value
                        reg = {'json': oc, 'json_income': ic}
                        reg_funs.simple_reg(request.user.id, 15, timestamp, transact_id, **reg)
                if new_objects:
                    if not transact_id:
                        transact_id = app.functions.reg_funs.get_transact_id(dict_id, code, 'd')
                    is_save = True
                    DictObjects.objects.bulk_create(new_objects)
                    # регистрация
                    for no in new_objects:
                        oc = general_data_reg.copy()
                        new_req = DictObjects.objects.get(code=no.code, name_id=no.name_id,
                                                          parent_structure_id=no.parent_structure_id)
                        oc['id'] = new_req.id
                        oc['name'] = new_req.name_id
                        oc['value'] = new_req.value
                        reg = {'json': oc}
                        reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                if is_save:
                    message = 'Объект изменен'
                else:
                    message += ' Вы ничего не изменили. Объект не сохранен<br>'
            else:
                message_class = 'text-red'
                message += '<br>Объект не сохранен'

        # Создаем новый
        elif 'b_new_dict' in request.POST:
            is_valid, message = validation(request, True)
            if is_valid:
                code = int(request.POST['i_owner'])
                transact_id = app.functions.reg_funs.get_transact_id(dict_id, code, 'd')
                # регистрация создания объекта
                outcoming = {'class_id': dict_id, 'type': 'dict', 'location': current_dict['default'],
                             'code': code}
                reg = {'json': outcoming}
                reg_funs.simple_reg(request.user.id, 5, timestamp, transact_id, **reg)
                dict_objects = []
                # Сохраняем
                for k, v in request.POST.items():
                    try:
                        field_id = int(re.search(r'^(ta|i_datetime|i_float|chb|i_link|'
                                                 r'i_date|s_enum)_(?P<id>\d+)$', k).group('id'))
                    except AttributeError:
                        continue
                    else:
                        dict_objects.append(DictObjects(code=code, parent_structure_id=int(request.GET['class_id']),
                                            name_id=field_id, value=v))
                DictObjects.objects.bulk_create(dict_objects)
                message = 'Объект успешно создан. Код объекта: ' + str(code)
                # Регистрация создания реквизитов объекта
                new_object_params = DictObjects.objects.filter(code=code, parent_structure_id=dict_id)
                for nop in new_object_params:
                    oc = {}
                    oc.update(outcoming)
                    nop = model_to_dict(nop)
                    del nop['parent_structure']
                    oc.update(nop)
                    reg = {'json': oc}
                    reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                # Удаляем информацию о странице из реквеста
                request.POST._mutable = True
                del request.POST['page']
                request.POST['object_code'] = code
                request.POST._mutable = False
            else:
                message_class = 'text-red'
                message += '<br>Объект не сохранен'

        # Кнопка "Удалить"
        elif 'b_delete' in request.POST:
            # Выделен ли объект
            if code:
                objects_delete = DictObjects.objects.filter(code=code,parent_structure_id=dict_id)
                if objects_delete:
                    # Регистрация
                    incoming = {'class_id': dict_id, 'location': current_dict['default'], 'type': 'dict', 'code': code}
                    # регистрируем удаление реквизитов
                    transact_id = app.functions.reg_funs.get_transact_id(dict_id, code, 'dict')
                    for od in objects_delete:
                        ic = incoming.copy()
                        ic['id'] = od.id
                        ic['name'] = od.name_id
                        ic['value'] = od.value
                        reg = {'json_income': ic, 'jsone_string_income': None}
                        reg_funs.simple_reg(request.user.id, 16, timestamp, transact_id, **reg)
                    # регистрируем удаление объекта
                    reg = {'json_income': incoming}
                    reg_funs.simple_reg(request.user.id, 8, timestamp, transact_id, **reg)
                    # Удаляем
                    objects_delete.delete()
                    message = 'Объект успешно удален.<br>Код объекта: ' + request.POST['i_owner'] + '<br>'
                else:
                    message = 'Объекта с указанным кодом нет в системе<br>'
            else:
                message = 'Вы не выбрали объект для удаления<br>'

        # Вывод
        object_codes = DictObjects.objects.filter(parent_structure_id=dict_id)
        object_codes, search_filter = interface_funs.sandf(request, object_codes, headers, None, None)

        # Пагинация и конвертация
        q_items = int(request.POST['q_items_on_page']) if 'q_items_on_page' in request.POST else 10
        page_num = int(request.POST['page']) if 'page' in request.POST and request.POST['page'] else 1
        object_codes = object_codes.values('code').distinct().order_by('-code')
        paginator = common_funs.paginator_object(object_codes, q_items, page_num)
        dict_objects = DictObjects.objects.filter(code__in=paginator['items_codes'], parent_structure_id=dict_id)
        dict_objects = convert_funs.queyset_to_object(dict_objects)
        dict_objects.sort(key=lambda x: x['code'], reverse=True)

        for h in headers:
            if h['formula'] == 'link':
                match = re.match(r'^(table|contract)\.(\d+)\.(\d*)$', h['default'])
                h['array_default'] = (match[1], match[2], match[3])
        convert_funs.prepare_table_to_template([h for h in headers if h['is_visible']], dict_objects, request.user.id)
        # Заголовки
        url = common_funs.edit_url(request)
        # Период таймлайна
        timeline_to = timestamp + relativedelta(minutes=1)
        timeline_from = timeline_to - relativedelta(months=1)

        ctx = {
            'title': 'Словарь ' + current_dict['name'],
            'class_name': current_dict['name'],
            'objects': dict_objects,
            'headers': headers,
            'paginator': paginator,
            'path_without_page': url,
            'message': message,
            'message_class': message_class,
            'parent_type': current_dict['default'],
            'parent_id': current_dict['parent_id'],
            'timeline_to': timeline_to.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeline_from': timeline_from.strftime('%Y-%m-%dT%H:%M:%S'),
            'db_loc': 'd',
            'search_filter': search_filter,
        }
        return render(request, 'objects/dictionary.html', ctx)
    else:
        return HttpResponseRedirect(reverse('login'))