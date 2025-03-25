import copy
import json
import math
import plotly.graph_objects as go
import networkx as nx
from datetime import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.functions import Cast
from django.shortcuts import redirect
from django.db.models import Subquery, FloatField
from django.forms import model_to_dict
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from app.functions import session_funs, reg_funs, database_funs, convert_funs, common_funs, database_procedures, \
    interface_funs, tree_funs, interface_procedures, convert_funs2, contract_funs, view_procedures, api_procedures, \
    task_funs, object_funs, convert_procedures, contract_procedures, class_funs
from app.models import Contracts, ContractCells, Dictionary, DictObjects, Designer, ContractDrafts, Tasks, TechProcess, \
    TechProcessObjects


# Конструктор контрактов
@view_procedures.is_auth_app
def manage_contracts(request):
    message = ''
    message_class = ''
    timestamp = datetime.now()

    # Работа с сессией
    session_funs.add_aliases(request)  # добавим в сессию алиасы
    if not 'contract_tree' in request.session:  # загрузить дерево контрактов в сессию
        session_funs.update_class_tree(request, True)
        if 'class_tree' in request.session:
            del request.session['class_tree']
    # контрольный пересчет заданий
    session_funs.check_quant_tasks(request)
    if not 'contract_menu' in request.session:  # Загрузить меню контрактов
        request.session['contract_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                                           request.session['contract_tree'], None, True)
        if 'class_menu' in request.session:
            del request.session['class_menu']
    # Загрузим данные черновиков
    if not 'contract_draft_tree' in request.session:
        session_funs.update_draft_tree(request, True)
    # локация (физическая - таблица Контрактов, словарей или техпроцессов)
    location = 'c'
    if 'i_loc' in request.POST:
        location = request.POST['i_loc']
    elif 'location' in request.GET:
        location = request.GET['location']
    # Менеджер классов
    class_manager = Contracts.objects
    if location == 't':
        class_manager = TechProcess.objects
    elif location == 'd':
        class_manager = Dictionary.objects

    class_id = int(request.POST['i_id']) if 'i_id' in request.POST and request.POST['i_id']\
        else int(request.GET['i_id']) if 'i_id' in request.GET else None

    # Удалить поле класса и зарегать удаление
    def delete_field(df, delete_folder, timestamp, transact_id):
        try:
            # Извещение и удаление
            message = 'Удален параметр контракта.<br>ID контракта: ' + request.GET['i_id'] \
                      + '; Название контракта:' + delete_folder.name + '<br>' \
                      + 'ID параметра: ' + str(df.id) + '; Название параметра: ' + df.name
            # регистрация операции
            incoming = {'class_id': delete_folder.id, 'location': 'contract', 'type': delete_folder.formula, }
            json_del_field = model_to_dict(df)
            del json_del_field['priority']
            del json_del_field['parent']
            incoming.update(json_del_field)
            reg = {'json_income': incoming}
            reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
            df.delete()
            return True, message
        except Exception as ex:
            return False, str(ex)

    # Удалить поле алиаса и зарегать удаление
    def delete_alias(del_param, parent, timestamp, transact_id):
        # Регистрация
        incoming = {'class_id': parent.id, 'location': 'contract', 'type': 'alias', 'name': del_param.name,
                    'value': del_param.value, 'id': del_param.id}
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

    # Получить системные параметры класса
    list_formula_exclude = ('contract', 'dict')
    list_name_exclude = ['parent_branch', 'parent','name', 'business_rule', 'link_map', 'trigger', 'completion_condition']
    def get_sys_props(list_name_exclude, is_array=True):
        # if is_array:
        #     system_props = list(class_manager.filter(parent_id=request.GET['i_id'], formula='techpro').values())
        # else:
        system_props = list(class_manager.filter(parent_id=class_id, name__in=list_name_exclude)
                            .order_by('id').values())
        # if is_array:
        #     # для работы с массивами получим данные техпроцессов
        #     tech_process_params = list(class_manager.filter(parent_id__in=[sp['id'] for sp in system_props])
        #                                .order_by('parent_id', 'id').exclude(name='parent_code').values())
        # if tech_process_params:
        #     lc = []
        #     sp = system_props[0]
        #     for tpp in tech_process_params:
        #         if tpp['parent_id'] != sp['id']:
        #             sp['params'] = lc
        #             sp = next(sp for sp in system_props if sp['id'] == tpp['parent_id'])
        #             lc = []
        #         lc.append(tpp)
        #     sp['params'] = lc
        return system_props

    # Проверка линкмап техпроцесса clmftp - check linkMap for tech process
    def clmftp(array_lm, quan_stages):
        lm_valid = True
        message = ''
        User = get_user_model()
        users = list(u['id'] for u in User.objects.all().values('id'))
        for al in array_lm:
            if array_lm.index(al) >= quan_stages:
                break
            if al:
                try:
                    int_al = int(al)
                except ValueError:
                    lm_valid = False
                    message += 'Некорректно указан ЛинкМап. Необходимо в столбик указать числа - ID пользователей<br>'
                    break
                if int_al not in users:
                    lm_valid = False
                    message += 'Некорректно указан ЛинкМап. Некорректный ID пользователя: ' + al + '<br>'
        return lm_valid, message

    # Кнопка "Сохранить"
    if 'b_save' in request.POST:
        # Если редактируем
        if request.POST['i_id']:
            id = int(request.POST['i_id'])
            name = request.POST['i_name']
            edited_unit = class_manager.get(id=id)
            parent_id = int(request.POST['i_parent']) if request.POST['i_parent'] else None
            valid_res = interface_funs.ecv(id, name, edited_unit.formula, parent_id, 'c')
            if valid_res == 'ok':
                is_valid = True
            else:
                is_valid = False
                message += valid_res
            # регистрационные данные
            json_income = {'class_id': edited_unit.id, 'location': 'contract', 'type': edited_unit.formula}
            json_outcome = json_income.copy()
            # Проверим, изменились ли данные, и валидные ли они
            is_change = False
            # Имя
            if name != edited_unit.name:
                is_change = True
            if is_valid and is_change:
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
                    cat_class = {'folder': 'Каталог', 'contract': 'Контракт', 'alias': 'Константа',
                                 'array': 'Массив', 'dict': 'Словарь', 'tree': 'Дерево', 'techprocess': 'Техпроцесс'}
                    updated = {'folder': 'обновлен', 'contract': 'обновлен', 'alias': 'обновлена',
                               'array': 'обновлен', 'dict': 'обновлен', 'tree': 'обновлено', 'techprocess': 'обновлен'}
                    message = cat_class[edited_unit.formula] + ' "' + request.POST['i_name'] + '" ' + updated[edited_unit.formula]
                    # Правка сессии
                    session_funs.update_class_tree(request, True)
                    request.session['contract_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                                                      request.session['contract_tree'], None, True)
                    request.session['draft_menu'] = session_funs\
                        .update_class_menu(request, request.session['contract_tree'], request.session['contract_tree'],
                                           None, True, is_draft=True)
                    # Если контракт перешел под управление деревом - внесем дополнительное поле
                    if edited_unit.formula == 'contract' and edited_unit.parent_id and is_change_parent:
                        if Contracts.objects.get(id=parent_id).formula == 'tree':
                            header_tree = Contracts.objects.filter(parent_id=edited_unit.id, name='parent_branch')
                            if not header_tree:
                                parent_branch = Contracts(name='parent_branch', formula='float', priority=1,
                                                         parent_id=edited_unit.id, is_required=True,
                                                         is_visible=False)
                                parent_branch.save()
                    # регистрация
                    reg = {
                        'json': json_outcome,
                        'json_income': json_income,
                    }
                    loc = 'p' if location == 't' else location
                    transact_id = reg_funs.get_transact_id(id, 0, loc)
                    reg_funs.simple_reg(request.user.id, 3, timestamp, transact_id, **reg)
                else:
                    message_class = 'text-red'
                    message += 'Изменения не сохранены'
            else:
                message = 'Вы не внесли изменений. Данные не сохранены'
        # Если новый класс
        else:
            # Проверка валидности
            parent_id = int(request.POST['i_parent']) if request.POST['i_parent'] else None
            if request.POST['s_folder_class'] == 'tp':
                control_field = int(request.POST['s_control_field'])
            else:
                control_field = None
            params = {'control_field': control_field}
            class_types = list(k for k in request.session['class_types'].keys())
            msg = interface_funs.ccv(request.POST['i_name'], request.POST['s_folder_class'], class_types, parent_id, 'c', **params)
            if msg == 'ok':
                parent_id = int(request.POST['i_parent']) if request.POST['i_parent'] else None
                if request.POST['s_folder_class'] == 'dict':
                    location = 'd'
                    new_unit = Dictionary(name=request.POST['i_name'], formula=request.POST['s_folder_class'],
                                        parent_id=parent_id, default='contract')
                    class_manager = Dictionary.objects
                # Создаем техпроцесс
                elif request.POST['s_folder_class'] == 'tp':
                    location = 't'
                    class_manager = TechProcess.objects
                    new_unit = TechProcess(name=request.POST['i_name'], formula='tp', parent_id=parent_id,
                                           value={'control_field': control_field})

                else:
                    new_unit = Contracts(name=request.POST['i_name'], formula=request.POST['s_folder_class'],
                                        parent_id=parent_id, is_required=0)
                new_unit.save()
                class_id = new_unit.id
                # добавим в форму айди созданного класса

                request.POST._mutable = True
                request.POST['i_id'] = new_unit.id
                request.POST._mutable = False

                # для контракта создадим статические поля - BR, LM, T, CC
                if new_unit.formula == 'contract':
                    Contracts(name='business_rule', formula='eval', is_required=True, is_visible=False,
                              parent_id=new_unit.id, priority=0, system=True).save()
                    Contracts(name='link_map', formula='eval', is_required=True, is_visible=False,
                              parent_id=new_unit.id, priority=0, system=True).save()
                    Contracts(name='trigger', formula='eval', is_required=True, is_visible=False,
                              parent_id=new_unit.id, priority=0, system=True).save()
                    Contracts(name='completion_condition', formula='eval', is_required=True, is_visible=False,
                              parent_id=new_unit.id, priority=0, system=True).save()
                elif new_unit.formula == 'tp':
                    TechProcess(name='business_rule', formula='eval', parent_id=new_unit.id, settings={'system': True},
                                value=[]).save()
                    TechProcess(name='link_map', formula='eval', parent_id=new_unit.id, settings={'system': True},
                                value=[]).save()
                    TechProcess(name='trigger', formula='eval', parent_id=new_unit.id, settings={'system': True},
                                value=[]).save()
                    first_stage_val = {'handler': None, 'children': []}
                    first_stage = TechProcess(name='Создан', formula='float', parent_id=new_unit.id, value=first_stage_val)
                    first_stage.save()
                    # СОздадим первые стадии ТПса для всех объектов
                    codes = ContractCells.objects.filter(name_id=control_field,
                                                         parent_structure_id=parent_id).values('code', 'value')
                    new_stages = []
                    for c in codes:
                        stage_val = {'fact': c['value'], 'delay': []}
                        new_stage = TechProcessObjects(parent_structure_id=new_unit.id, name_id=first_stage.id,
                                                       parent_code=c['code'], value=stage_val)
                        new_stages.append(new_stage)
                    while new_stages:
                        q = 1000 if len(new_stages) >= 1000 else len(new_stages)
                        TechProcessObjects.objects.bulk_create(new_stages[:q], q)
                        new_stages = new_stages[q:]

                # Создание обязательного поля
                new_unit_name = ''
                formula = ''
                val = ''
                if request.POST['s_folder_class'] == 'contract':
                    new_unit_name = 'system_data'
                    formula = 'string'
                elif request.POST['s_folder_class'] == 'array':
                    new_unit_name = 'Собственник'
                    formula = 'link'
                    val = 'contract.' + request.POST['i_parent']
                elif request.POST['s_folder_class'] == 'tree':
                    new_unit_name = 'is_right_tree'
                    formula = 'bool'
                    val = True
                if new_unit_name:
                    Contracts(parent_id=new_unit.id, formula=formula, name=new_unit_name, value=val,
                              is_required=True, is_visible=False, priority=1, delay={'delay': False, 'handler': False}).save()
                    # для дерева добавим дополнительные поля - имя, родитель
                    if request.POST['s_folder_class'] == 'tree':
                        Contracts(parent_id=new_unit.id, formula='string', name='name', is_required=True,
                                 is_visible=False, priority=1).save()
                        Contracts(parent_id=new_unit.id, formula='link', name='parent', is_required=True,
                                 is_visible=False, priority=1).save()
                    # для контракта под деревом добавим свойство - родительская ветка
                    elif request.POST['s_folder_class'] == 'contract' and parent_id:
                        if Contracts.objects.get(id=parent_id).formula == 'tree':
                            Contracts(name='parent_branch', formula='float', parent_id=new_unit.id, is_required=True,
                                     is_visible=False, priority=1).save()

                message = 'Успешно создан класс. Тип: "' + request.session['class_types'][request.POST['s_folder_class']] \
                          + '"<br>' + \
                'ID: ' + str(new_unit.id) + '<br>Название: "' + new_unit.name + '"<br>'
                # добавим в форму айди созданного класса
                request.POST._mutable = True
                request.POST['i_id'] = new_unit.id
                if request.POST['s_folder_class'] == 'dict':
                    request.POST['is_dict'] = 'true'
                request.POST._mutable = False
                # Правим сессию.
                session_funs.update_class_tree(request, True)
                request.session['contract_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                        request.session['contract_tree'], None, True)
                request.session['draft_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                                               request.session['contract_tree'], None,
                                                                               True, is_draft=True)
                # Регистрация
                json_folder = {'class_id': new_unit.id, 'name': new_unit.name, 'type': new_unit.formula,
                               'location': 'contract', 'parent': new_unit.parent_id}
                reg = {'json': json_folder}
                loc = 'd' if request.POST['s_folder_class'] == 'dict' else 'c'
                transaction_id = reg_funs.get_transact_id(new_unit.id, 0, loc)
                reg_funs.simple_reg(request.user.id, 1, timestamp, transaction_id, **reg)

                # # редиректим
                # dict_loc = {'tp': 't', 'dict': 'd'}
                # loc = dict_loc[new_unit.formula] if new_unit.formula in ('tp', 'dict') else 'c'
                # url = f'manage-contracts?i_id={new_unit.id}&location={loc}'
                # if loc == 'd':
                #     url += 'is_dict='
                # HttpResponseRedirect(reverse(url))
            else:
                message_class = 'text-red'
                message += msg + 'Данные не сохранены'

    # кнопка "Удалить"
    if 'b_delete' in request.POST:
        # добавим в пост информацию о словаре, если имеем дело со словарем
        if request.POST['i_type'] == 'Словарь':
            request.POST._mutable = True
            request.POST['is_dict'] = 'true'
            request.POST._mutable = False
            id = class_id
        delete_folder = class_manager.get(id=class_id)
        if not delete_folder:
            message = 'Выбран несуществующий класс. Удаление невозможно<br>'
            message_class = 'text-red'
        else:
            is_valid = True
            # Проверка типа
            if delete_folder.formula not in request.session['class_types'].keys():
                is_valid = False
                message += 'Невозможно удалить данный тип<br>'
            # Проверка дочерних классов
            children_classes = None
            if request.POST['i_type'] == 'Каталог':
                children_classes = Contracts.objects.filter(parent_id=class_id, formula__in=['alias', 'contract', 'folder', 'tree'])
            elif request.POST['i_type'] == 'Контракт':
                children_classes = list(Contracts.objects.filter(parent_id=class_id, formula='array'))
                children_classes += list(Dictionary.objects.filter(parent_id=class_id, formula='dict', default='contract'))
            elif delete_folder.formula == 'tree':
                children_classes = Contracts.objects.filter(parent_id=class_id, formula='contract')
            elif delete_folder.formula == 'alias':
                is_valid = not database_funs.chpoc(class_id, True)
                if not is_valid:
                    message += 'Нельзя удалить константу, у которой есть свойства. Удалите свойства, после повторите попытку<br>'
            if children_classes:
                is_valid = False
                message += 'Нельзя удалить класс с дочерними классами.<br>'
            # Проверка объектов
            children_objects = None
            if request.POST['i_type'] in ['Контракт', 'Массив']:
                children_objects = ContractCells.objects.filter(parent_structure_id=class_id)
            elif request.POST['i_type'] == 'Словарь':
                children_objects = DictObjects.objects.filter(parent_structure_id=class_id)
            if children_objects:
                is_valid = False
                message += 'Нельзя удалить класс, у которого есть объекты.<br>'
            # Удаление
            if is_valid:
                deleted_id = class_id
                deleted_type = delete_folder.formula
                class_id = delete_folder.parent_id
                # Удалим папку
                if delete_folder.formula == 'folder':
                    message = 'Каталог "' + request.POST['i_name'] + '" успешно удален'
                    # регистрация
                    incoming = {'class_id': delete_folder.id, 'type': delete_folder.formula, 'location': 'contract',
                                'name': delete_folder.name, 'parent': delete_folder.parent_id}
                    reg = {'json_income': incoming}
                    transact_id = reg_funs.get_transact_id(delete_folder.id, 0, 'c')
                    result = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                    # Удаление
                    if result:
                        delete_folder.delete()
                    else:
                        message = 'Класс ' + str(delete_folder.id) + ' Не удален. Ошибка регистратора'
                        message_class = 'text-red'
                # Удалим контракт, дерево или массив
                elif delete_folder.formula in ['contract', 'array', 'tree']:
                    transact_id = reg_funs.get_transact_id(delete_folder.id, 0, 'c')
                    # Для дерева удалим все объекты
                    if delete_folder.formula == 'tree':
                        inc = {'class_id': delete_folder.id, 'location': 'contract', 'type': 'tree'}
                        del_branches = ContractCells.objects.filter(parent_structure_id=delete_folder.id).order_by('code')
                        obj_code = None
                        transact_code = None
                        for db in del_branches:
                            if obj_code != db.code:
                                obj_code = db.code
                                transact_code = reg_funs.get_transact_id(delete_folder.id, obj_code, 'c')
                                i = inc.copy()
                                i['code'] = db.code
                                reg = {'json_income': i}
                                reg_funs.simple_reg(request.user.id, 8, timestamp, transact_code, transact_id, **reg)
                            i = inc.copy()
                            i['code'] = db.code
                            i['id'] = db.id
                            i['name'] = db.name_id
                            i['value'] = db.value
                            reg = {'json_income': i}
                            reg_funs.simple_reg(request.user.id, 16, timestamp, transact_code, transact_id, **reg)
                        del_branches.delete()
                    # Удалим все поля
                    del_fields = Contracts.objects.filter(parent_id=delete_folder.id)
                    # регистрация удаления полей класса
                    incoming = {'class_id': delete_folder.id, 'location': 'contract', 'type': delete_folder.formula}
                    for df in del_fields:
                        json_del_field = model_to_dict(df)
                        del json_del_field['priority']
                        del json_del_field['parent']
                        inc = incoming.copy()
                        inc.update(json_del_field)
                        reg = {'json_income': inc}
                        reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
                    del_fields.delete()  # Удалим поля
                    # Удалим класс
                    dict_type = {'contract': 'Контракт', 'array': 'Массив', 'tree': 'Дерево'}
                    dict_del = {'contract': 'удален', 'array': 'удален', 'tree': 'удалено'}
                    message = dict_type[delete_folder.formula] + ' ' + dict_del[delete_folder.formula] + \
                              '. ID: ' + str(delete_folder.id) + '; название: "' + delete_folder.name + '"<br>'
                    # регистрация
                    incoming = {'class_id': delete_folder.id, 'name': delete_folder.name, 'location': 'contract',
                                'type': delete_folder.formula, 'parent': delete_folder.parent_id}
                    reg = {'json_income': incoming}
                    res = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                    # Удаление
                    if res:
                        delete_folder.delete()
                        delete_folder = None
                    else:
                        message = 'Класс ' + str(delete_folder.id) + ' не удален. Ошибка регистратора'
                        message_class = 'text-red'
                # Удалим словарь
                elif delete_folder.formula == 'dict':
                    location = 'c'
                    class_manager = Contracts.objects
                    transact_id = reg_funs.get_transact_id(delete_folder.id, 0, 'd')
                    # регистрация удаленных полей словаря
                    incoming = {'class_id': delete_folder.id, 'location': 'contract', 'type': 'dict'}
                    dict_fields_del = Dictionary.objects.filter(parent_id=delete_folder.id).exclude(formula='dict')
                    res_del_field = True
                    for dfd in dict_fields_del:
                        dict_dfd = model_to_dict(dfd)
                        del dict_dfd['priority']
                        inc = incoming.copy()
                        inc.update(dict_dfd)
                        reg = {'json_income': inc}
                        res_del_field = reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
                        if not res_del_field:   break
                    # Удалим поля
                    if res_del_field:
                        dict_fields_del.delete()
                        # регистрация удаления словаря
                        incoming['parent'] = delete_folder.parent_id
                        incoming['name'] = delete_folder.name
                        reg = {'json_income': incoming}
                        res_header = reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                        # Удалим заголовок
                        if res_header:
                            header_del = Dictionary.objects.get(id=id)
                            message = 'Удален словарь. ID: ' + str(header_del.id) + '<br>' + 'Название: ' + header_del.name
                            header_del.delete()
                        else:
                            message = 'Словарь не удален. Ошибка регистратора'
                    else:
                        message = 'Параметр словаря не удален. Ошибка регистратора'
                # Удалим алиас
                elif delete_folder.formula == 'alias':
                    transact_id = reg_funs.get_transact_id(delete_folder.id, 0, 'c')
                    # Удалим все параметры
                    del_params = Contracts.objects.filter(parent_id=delete_folder.id)
                    for dp in del_params:
                        delete_alias(dp, delete_folder, timestamp, transact_id)
                    # Регистрация удаления алиаса
                    incoming = {'class_id': delete_folder.id, 'location': 'contract', 'type': 'alias',
                                'name': delete_folder.name, 'parent': delete_folder.parent_id}
                    reg = {'json_income': incoming}
                    reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                    # извещение
                    message = 'Константа удалена. ID: ' + str(delete_folder.id) + '<br>Название: "' + delete_folder.name + '"<br>'
                    # Удаление
                    delete_folder.delete()
                # Удалим техпроцесс
                elif delete_folder.formula == 'tp':
                    location = 'c'
                    class_manager = Contracts.objects
                    transact_id = reg_funs.get_transact_id(delete_folder.id, 0, 'p')
                    # Удалим все объекты
                    objs = TechProcessObjects.objects.filter(parent_structure_id=delete_folder.id)
                    if objs:
                        list_regs = []
                        parent_code = None
                        trans_id = None
                        for o in objs:
                            if parent_code != o.parent_code:
                                parent_code = o.parent_code
                                trans_id = reg_funs.get_transact_id(delete_folder.id, o.parent_code, 'p')
                            inc = {'class_id': delete_folder.id, 'location': 'contract', 'type': 'tp', 'id': o.id,
                                   'name': o.name_id, 'code': o.parent_code, 'value': o.value}
                            reg = {'json_income': inc}
                            dict_reg = {'user_id': request.user.id, 'reg_id': 16, 'timestamp': timestamp,
                                        'transact_id': trans_id, 'parent_transact': transact_id, 'reg': reg}
                            list_regs.append(dict_reg)
                        reg_funs.paket_reg(list_regs)
                        objs.delete()

                    # Удалим все параметры
                    del_params = TechProcess.objects.filter(parent_id=delete_folder.id)
                    list_regs = []
                    for dp in del_params:
                        inc = {'class_id': dp.parent_id, 'type': 'tp', 'location': 'contract',
                               'name': dp.name, 'formula': dp.formula, 'id': dp.id, 'value': dp.value}
                        reg = {'json_income': inc}
                        dict_reg = {'user_id': request.user.id, 'reg_id': 11, 'timestamp': timestamp,
                                    'transact_id': transact_id, 'reg': reg}
                        list_regs.append(dict_reg)
                    reg_funs.paket_reg(list_regs)
                    del_params.delete()
                    # Регистрация удаления ТПса
                    incoming = {'class_id': delete_folder.id, 'location': 'contract', 'type': 'tp',
                                'name': delete_folder.name, 'parent': delete_folder.parent_id, 'value': delete_folder.value}
                    reg = {'json_income': incoming}
                    reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
                    # извещение
                    message = 'Техпроцесс удален. ID: ' + str(delete_folder.id) + '<br>Название: "' + delete_folder.name + '"<br>'
                    # Удаление
                    delete_folder.delete()

                # Правка сессии
                session_funs.update_class_tree(request, True)
                request.session['contract_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                                                  request.session['contract_tree'],
                                                                                  None, True)
                request.session['draft_menu'] = session_funs.update_class_menu(request,
                                                                               request.session['contract_tree'],
                                                                               request.session['contract_tree'], None,
                                                                               True, is_draft=True)
                # Перемещение данных из истории в архив
                class_funs.dndi_frohi_toarhiv(deleted_id, 'c', deleted_type)
            else:
                message_class = 'text-red'

    # Сохранить параметры класса
    elif 'b_save_fields' in request.POST:
        if not class_id:
            message = 'Не выбран контракт. Изменения не сохранены<br>'
            message_class = 'text-red'
        else:
            params = json.loads(request.POST['b_save_fields'])
            # Редактируем сохраненные свойства класса
            header = Contracts.objects.get(id=class_id)
            current_class = Contracts.objects.filter(parent_id=class_id)\
                .exclude(system=True).order_by('id')
            names_params = [cc.name.lower() for cc in current_class]
            if header.formula == 'tree':
                names_params.append('наименование')
            # Валидация данных и приведение типов
            is_valid = True
            all_changes = False
            transact_id = None
            for p in params:
                if p['id']:
                    if p['type'] == 'array':
                        continue
                    try:
                        cp = next(cc for cc in current_class if cc.id == p['id'])
                    except StopIteration:
                        continue
                    else:
                        is_change = False
                        change_required = False
                        if header.formula == 'tree' and p['name'] == 'is_right_tree':
                            all_changes = interface_funs.stpirt(cp, p['value'], request.user.id, timestamp)
                        else:
                            # данные регистрации
                            incoming = {'class_id': cp.parent_id, 'id': header.id, 'location': 'contract',
                                        'type': header.formula}
                            outcoming = incoming.copy()
                            incoming['id'] = p['id']
                            outcoming['id'] = p['id']
                            if not p['name']:
                                is_valid = False
                                message += 'Название параметра с ID ' + str(p['id']) + ' пустое. Заполните пожалуйста<br>'
                            if cp.name != p['name'] and cp.name != 'system_data':
                                # проверим измененное имя. Вдруг такое есть в данном классe
                                if p['name'].lower() in names_params:
                                    is_valid = False
                                    message += 'Название параметра "' + p['name'] + '" уже есть у данного контракта<br>'
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
                            if 'visible' in p and cp.is_visible != p['visible']:
                                # Регистрирую изменение
                                incoming['is_visible'] = cp.is_visible
                                outcoming['is_visible'] = p['visible']
                                cp.is_visible = p['visible']
                                is_change = True
                            # итоги
                            if 'totals' in p:
                                if not cp.settings or 'totals' not in cp.settings \
                                        or sorted(cp.settings['totals']) != sorted(p['totals']):
                                    incoming['settings'] = copy.deepcopy(cp.settings)
                                    if incoming['settings']:
                                        outcoming['settings'] = copy.deepcopy(incoming['settings'])
                                        outcoming['settings']['totals'] = p['totals']
                                        cp.settings['totals'] = p['totals']
                                    else:
                                        outcoming['settings'] = {'totals': p['totals']}
                                        cp.settings = {'totals': p['totals']}
                                    is_change = True
                            if 'is_required' in p and cp.is_required != p['is_required']:
                                # Регистрирую изменение
                                incoming['is_required'] = cp.is_required
                                outcoming['is_required'] = p['is_required']
                                cp.is_required = p['is_required']
                                is_change = True
                                change_required = True
                            # Работаем с полем "Значение"
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
                            if p['type'] in ('bool', 'link', 'const'):
                                default = str(p['default'])
                            else:
                                default = p['default']
                            if cp.default != default:
                                # Регистрирую изменение
                                incoming['default'] = cp.default
                                outcoming['default'] = default
                                cp.default = default
                                cp.default = default
                                is_change = True

                            # работаем с делэем
                            if p['delay']['delay'] and type(p['delay']['handler']) is int \
                                and not database_procedures.check_user(p['delay']['handler']):
                                is_valid = False
                                message += 'Некорректно указан отвветственный к отложенному значению параметра ID:' + str(p['id']) + '<br>'
                            elif cp.delay != p['delay']:
                                is_change = True
                                incoming['delay'] = cp.delay
                                outcoming['delay'] = p['delay']
                                cp.delay = p['delay']
                            if is_valid:
                                if is_change:
                                    all_changes = True
                                    cp.save()
                                    if not transact_id:
                                        transact_id = reg_funs.get_transact_id(header.id, 0, 'c')
                                    names_params = [cc.name for cc in Contracts.objects.filter(parent_id=class_id)]
                                    message = 'контракт "' + request.POST['i_name'] + '" ID:' \
                                              + request.POST['i_id'] + ' обновлен<br>'
                                    # регистрация
                                    reg = {
                                        'json_income': incoming,
                                        'json': outcoming,
                                    }
                                    reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                                    if change_required and cp.is_required:
                                        object_funs.avto(header, 'c', cp, transact_id, request.user.id, timestamp)
                            else:
                                message_class = 'text-red'
            if all_changes:
                request.session['temp_object_manager'] = {}
            # Создаем новый параметр
            try:
                p = next(p for p in params if not p['id'])
            except StopIteration:
                pass
            else:
                is_valid = True
                if not p['name']:
                    is_valid = False
                    message += 'Не указано имя параметра контракта. Новый параметр не сохранен<br>'
                if p['name'].lower() in names_params:
                    is_valid = False
                    message += 'Названия параметров контрактов не должны повторяться. Новый параметр не сохранен<br>'
                if p['type'] == 'link':
                    if not p['value']:
                        is_valid = False
                        message += 'У ссылки нет родителя.<br>'
                    else:
                        is_contract = True if request.POST['chb_link_type'] == 'contract' else False
                        class_type = database_procedures.get_class_type(p['value'], is_contract)
                        if not class_type or class_type not in ['table', 'contract']:
                            is_valid = False
                            message += 'Некорректно указан ID родителя для ссылки.<br>'
                        else:
                            is_child = database_funs.is_child(request.POST['i_id'], 'contract',
                                                              p['value'], request.POST['chb_link_type'])
                            if is_child:
                                is_valid = False
                                message += 'Некорректный тип значения нового параметра. ' \
                                           'Нельзя в качестве родительского контракта указывать потомка, ' \
                                           'это приводит к цикличным ссылкам<br>'
                            else:
                                p['value'] = request.POST['chb_link_type'] + '.' + p['value']
                # Проверка корректности для алиаса
                if p['type'] == 'const':
                    try:
                        alias_manager = Contracts.objects if p['location'] == 'contract' else Designer.objects
                        alias_manager.get(id=p['value'], formula='alias')
                    except Exception:
                        is_valid = False
                        message += 'Некорректно указан ID константы. Новый параметр не сохранен<br>'
                if p['type'] == 'enum':
                    p['value'] = p['value'].split('\n')
                # Если все проверки пройдены - создаем параметр
                if is_valid:
                    # зададим приоритет
                    database_procedures.check_fix_priority(current_class, 'contract')
                    max_priority = 0
                    for cc in current_class:
                        if cc.priority and cc.priority > max_priority:  max_priority = cc.priority
                    val = p['location'] + '.' + p['value'] if 'location' in p else p['value']
                    settings = {'totals': p['totals']} if 'totals' in p and p['totals'] else None
                    new_field = Contracts(name=p['name'], formula=p['type'], is_required=bool(p['is_required']),
                                         parent_id=class_id, value=val, default=p['default'],
                                         is_visible=p['visible'], priority=max_priority + 1, delay=p['delay'],
                                          settings=settings)
                    new_field.save()
                    message += 'Создан новый параметр класса \"' + request.POST['i_name'] + '\"<br>'
                    all_changes = True
                    # Регистрация
                    dict_field = {'id': new_field.id, 'name': new_field.name, 'formula': new_field.formula,
                                  'value': new_field.value, 'is_required': new_field.is_required,
                                  'default': new_field.default, 'is_visible': new_field.is_visible,
                                  'settings': settings}
                    outcome = {'class_id': header.id, 'location': 'contract', 'type': header.formula}
                    outcome.update(dict_field)
                    reg = {'json': outcome}
                    if not transact_id:
                        transact_id = reg_funs.get_transact_id(header.id, 0, 'c')
                    reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
                    # Если параметр обязательный - то проставим всем ранее созданным записям значение по умолчанию
                    if p['is_required']:
                        object_funs.avto(header, 'c', new_field, transact_id, request.user.id, timestamp)

                else:   message_class = 'text-red'
            if not all_changes: message += 'Контракт не сохранен<br>'
            else:   message += 'Контракт сохранен<br>'

    # Кнопка "Удалить параметр"
    elif 'b_del_field' in request.POST:
        current_class = Contracts.objects.get(id=class_id)
        try:
            del_header = Contracts.objects.get(id=int(request.POST['b_del_field']))
        except ObjectDoesNotExist:
            message += 'Не найден параметр с ID: + ' + request.POST['b_del_field'] + '<br>'
            is_valid = False
        else:
            is_valid = True
            # Нельзя удалять поле Обязательный параметр
            if del_header.is_required:
                is_valid = False
                message = 'Нельзя удалять обязательные параметры. Для удаление отключите свойство "Обязательный" и сохраните<br>'
            # для дерева: нельзя удалять параметр с именем - имя, родитель, правильное дерево
            if del_header.formula == 'tree' and del_header.name in ('name', 'parent', 'is_right_tree'):
                is_valid = False
                message = 'Нельзя удалять системные параметры<br>'
        if is_valid:
            # Извещение
            message = 'Удален параметр контракта.<br>ID контракта: ' + request.GET['i_id'] \
                      + '; Название контракта:' + request.POST['i_name'] + '<br>' \
                      + 'ID параметра: ' + request.POST[
                          'b_del_field'] + '; Название параметра: ' + del_header.name
            # регистрация операции
            incoming = {'class_id': current_class.id, 'location': 'contract', 'type': current_class.formula,
                        'id': del_header.id}
            incoming['name'] = del_header.name
            incoming['formula'] = del_header.formula
            incoming['value'] = del_header.value
            incoming['is_required'] = del_header.is_required
            incoming['default'] = del_header.default
            incoming['is_visible'] = del_header.is_visible
            reg = {'json_income': incoming}
            transact_id = reg_funs.get_transact_id(current_class.id, 0, 'c')
            reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
            # удаление
            # Если ссылаются объекты - удалим их
            children = ContractCells.objects.filter(name_id=request.POST['b_del_field'])
            if children:
                # регистрация удаления объекта
                incoming = {'class_id': current_class.id, 'location': 'contract', 'type': current_class.formula,
                            'name': del_header.id}
                for c in children:
                    json_inc = incoming.copy()
                    json_inc['id'] = c.id
                    json_inc['code'] = c.code
                    json_inc['value'] = c.value
                    reg = {'json_income': json_inc}
                    transact_code = reg_funs.get_transact_id(current_class.id, c.code, 'c')
                    reg_funs.simple_reg(request.user.id, 16, timestamp, transact_code, transact_id, **reg)
                children.delete()
            del_header.delete()  # удалим поле
            # пересчет приоритетов
            current_params = Contracts.objects.filter(parent_id=class_id)
            database_procedures.check_fix_priority(current_params, 'contract')
            request.session['temp_object_manager'] = {}
        else:
            message += 'Изменения не сохранены'
            message_class = 'text-red'

    # Сохранить параметры алиаса
    elif 'b_save_alias' in request.POST:
        alias_id = class_id
        array = json.loads(request.POST['b_save_alias'])
        current_alias = Contracts.objects.filter(parent_id=alias_id)
        names = [ca.name for ca in current_alias]
        all_changes = False
        transact_id = None
        for a in array:
            # редактируем параметры алиаса
            if a['id']:
                ca = next(ca for ca in current_alias if ca.id == a['id'])
                is_change = False
                is_valid = True
                # данные для регистратора
                # регистрационные данные
                incoming = {'class_id': alias_id, 'location': 'contract', 'type': 'alias', 'id': a['id']}
                outcoming = incoming.copy()
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
                    if not transact_id:
                        transact_id = reg_funs.get_transact_id(alias_id, 0, 'c')
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
                    new_alias = Contracts(parent_id=alias_id, name=a['name'], formula='eval', value=a['value'],
                                         is_required=False)
                    new_alias.save()
                    message += 'Новый параметр сохранен.<br>'
                    # регистрация
                    outcoming = {'class_id': alias_id, 'location': 'contract', 'type': 'alias', 'id': new_alias.id,
                                 'name': new_alias.name, 'value': new_alias.value}
                    reg = {'json': outcoming}
                    if not transact_id:
                        transact_id = reg_funs.get_transact_id(alias_id, 0, 'c')
                    reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
        if not all_changes: message += 'Вы ничего не изменили. Данные не сохранены<br>'

    # Удалить параметр алиаса
    elif 'b_del_alias' in request.POST:
        param = Contracts.objects.get(id=int(request.POST['b_del_alias']))
        parent = Contracts.objects.get(id=class_id)
        transact_id = reg_funs.get_transact_id(param.parent_id, 0, 'c')
        message = delete_alias(param, parent, timestamp, transact_id)

    # Сохранить параметры словаря
    elif 'b_save_fields_dict' in request.POST:
        message = interface_funs.save_dict_params(request, message)

    # Сохранить параметры дерева
    elif 'b_save_fields_tree' in request.POST:
        new_val = True if request.POST['b_save_fields_tree'] == 'true' else False
        is_saved, message = interface_funs.stpirt(class_id, new_val, request.user.id, timestamp, True)
        if not is_saved:    message_class = 'text-red'

    # Удалить параметр словаря
    elif 'b_del_field_dict' in request.POST:
        message = interface_funs.delete_dict_param(request, message)

    # Сохранить системные параметры контракта
    elif 'save_system_fields' in request.POST:
        sys_params = json.loads(request.POST['save_system_fields'])
        # Данные регистрации
        transact_id = reg_funs.get_transact_id(class_id, 0, 'c')
        def reg_sys_param(param, old_val):
            inc = {'class_id': class_id, 'type': 'contract', 'location': 'contract', 'id': param.id, 'value': old_val}
            outc = inc.copy()
            outc['value'] = param.value
            reg = {
                'json_income': inc,
                'json': outc,
            }
            reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
        is_change = False
        is_valid = True
        # Проверим бизнес правило
        br = Contracts.objects.get(parent_id=class_id, name='business_rule')
        old_br = br.value
        if old_br != sys_params['br']:
            is_change = True
            br.value = sys_params['br']
            br.save()
            reg_sys_param(br, old_br)
            # Проверка устарела. удалить после 15.04.2025
            # Проверим объекты на выполняемость нового BR
            # if contract_funs.vocobru(br, request.user.id):
            #     br.save()
            #     # Регистрация
            #     reg_sys_param(br, old_br)
            # # Если не выполнился хотя бы один объект
            # else:
            #     is_valid = False
            #     message += 'Не выполняется бизнес-правило<br>Системные параметры контракта не были сохранены'
            #     message_class = 'text-red'
        if is_valid:
            # Проверим линк мап
            lm = Contracts.objects.get(parent_id=class_id, name='link_map')
            old_val = copy.deepcopy(lm.value)
            lm_change = False
            if not sys_params['lm']:
                if sys_params['lm'] != old_val:
                    lm_change = True
            elif not old_val:
                lm_change = True
            elif len(old_val) != len(sys_params['lm']):
                lm_change = True
            else:
                for l in sys_params['lm']:
                    if not old_val:
                        lm_change = True
                        break
                    try:
                        find_old_l = next(ov for ov in old_val if ov['class_id'] == l['class_id'])
                    except StopIteration:
                        lm_change = True
                        break
                    if find_old_l != l:
                        lm_change = True
                        break
            if lm_change:
                is_change = True
                lm.value = sorted(sys_params['lm'], key=lambda x: x['class_id'])
                lm.save()
                reg_sys_param(lm, old_val)

            # Проверим триггер
            tr = Contracts.objects.get(parent_id=class_id, name='trigger')
            old_val = tr.value
            if old_val != sys_params['tr']:
                is_change = True
                tr.value = sys_params['tr']
                tr.save()
                reg_sys_param(tr, old_val)

            # Проверим условие выполнения
            cc = Contracts.objects.get(parent_id=class_id, name='completion_condition')
            old_val = cc.value
            if old_val != sys_params['cc']:
                is_change = True
                cc.value = sys_params['cc']
                cc.save()
                reg_sys_param(cc, old_val)
                # В случае обновления условия выполнения пересчитаем все объекты
                objs = ContractCells.objects.filter(parent_structure_id=class_id, name__name='system_data')
                current_class = class_manager.get(id=class_id)
                cc = model_to_dict(cc)
                for o in objs:
                    interface_funs.do_cc(current_class, o, cc, request.user.id, timestamp, transact_id)

        if is_valid:
            if is_change:
                message = 'Системные параметра контракта ID ' + request.POST['i_id'] + ' обновлены'
            else:
                message = 'Системные параметра контракта ID ' + request.POST['i_id'] + ' не были обновлены. Вы не внесли изменений'

    # Сохранить системные параметры техпроцесса
    elif 'save_sys_tp' in request.POST:
        params = json.loads(request.POST['save_sys_tp'])
        tp_params = TechProcess.objects.filter(parent_id=class_id, settings__system=True)
        params_saved = False
        for p in tp_params:
            if p.value != params[p.name]:
                inc = {'class_id': class_id, 'type': 'tp', 'location': 'contract', p.name: p.value}
                outc = inc.copy()
                outc[p.name] = params[p.name]
                reg = {'json': outc, 'json_income': inc}
                transact_id = reg_funs.get_transact_id(class_id, 0, 'p')
                reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                p.value = params[p.name]
                p.save()
                params_saved = True
        message = 'Системные параметры техпроцесса ID: ' + request.POST['i_id'] + ' были обновлены<br>' \
            if params_saved else 'Вы не внесли изменений. Данные не сохранены<br>'

    # Сохранить стадии техпроцесса
    elif 'save_tp' in request.POST:
        stages = json.loads(request.POST['save_tp'])
        # валидация данных
        is_valid = True
        old_stages = TechProcess.objects.filter(parent_id=class_id).exclude(settings__system=True)
        for s in stages:
            if s['handler']:
                try:
                    s['handler'] = int(s['handler'])
                except ValueError:
                    message += 'Некорректно задан ответственный для стадии ID: ' + s['id'] +\
                               ', Необходимо указать целое число - ID пользователя системы<br>'
                    is_valid = False
                else:
                    try:
                        get_user_model().objects.get(id=s['handler'])
                    except ObjectDoesNotExist:
                        message += 'Некорректно задан ответственный для стадии ID: ' + s['id'] +\
                               ', Необходимо указать целое число - ID пользователя системы<br>'
                        is_valid = False
            else:
                s['handler'] = None
            if s['children']:
                likely_children = [os.id for os in old_stages if os.id != s['id']]
                s['children'] = [int(c) for c in s['children']]
                for ch in s['children']:
                    if ch not in likely_children:
                        is_valid = False
                        message += 'Некорректно указан потомок для стадии ID: ' + s['id'] + '<br>'
        if is_valid:
            transact_id = None
            # При наличии новой стадии сохраним ее
            try:
                new_stage_data = next(s for s in stages if s['id'] == 'new')
            except StopIteration:
                pass
            else:
                stages = [s for s in stages if s['id'] != 'new']
                # Сохранение
                val = {'handler': new_stage_data['handler'], 'children': new_stage_data['children']}
                new_stage_rec = TechProcess(parent_id=class_id, formula='float', name=new_stage_data['name'], value=val)
                new_stage_rec.save()
                # регистрация
                outc = {'class_id': class_id, 'location': 'contract', 'type': 'tp', 'name': new_stage_data['name'],
                        'handler': new_stage_data['handler'], 'children': new_stage_data['children'], 'id': new_stage_rec.id}
                reg = {'json': outc}
                transact_id = reg_funs.get_transact_id(class_id, 0, 'p')
                reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
            all_saved = False
            for s in stages:
                s['id'] = int(s['id'])
                is_saved = False
                old_stage = next(os for os in old_stages if os.id == s['id'])
                inc = {'class_id': class_id, 'location': 'contract', 'type': 'tp', 'id': s['id']}
                outc = inc.copy()
                if s['name'] != old_stage.name:
                    is_saved = True
                    inc['name'] = old_stage.name
                    old_stage.name = s['name']
                    outc['name'] = old_stage.name
                if s['handler'] != old_stage.value['handler']:
                    is_saved = True
                    inc['handler'] = old_stage.value['handler']
                    old_stage.value['handler'] = s['handler']
                    outc['handler'] = old_stage.value['handler']
                s['children'].sort()
                if s['children'] != old_stage.value['children']:
                    is_saved = True
                    inc['children'] = old_stage.value['children']
                    old_stage.value['children'] = s['children']
                    outc['children'] = old_stage.value['children']
                vis_os = 'visible' in old_stage.settings and old_stage.settings['visible']
                if s['visible'] != vis_os:
                    is_saved = True
                    inc['visible'] = vis_os
                    old_stage.settings['visible'] = s['visible']
                    outc['visible'] = s['visible']
                if is_saved:
                    all_saved = True
                    old_stage.save()
                    reg = {'json': outc, 'json_income': inc}
                    if not transact_id:
                        transact_id = reg_funs.get_transact_id(class_id, 0, 'p')
                    reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
            if all_saved:
                message = 'Техпроцесс ID: ' + request.POST['i_id'] + ' обновлен<br>'
            else:
                message = 'Вы ничего не изменили. Данные не обновлены<br>'
        else:
            message_class = 'text-red'
            message += 'Данные не сохранены'

    # удалить стадию техпроцесса
    elif 'delete_stage' in request.POST:
        del_stage_id = int(request.POST['delete_stage'])
        stages = TechProcess.objects.filter(parent_id=class_id).exclude(settings__system=True)
        delete_stage = None
        is_valid = True
        for s in stages:
            if s.id == del_stage_id:
                delete_stage = s
            elif del_stage_id in s.value['children']:
                is_valid = False
                message = 'Нельзя удалить стадию техпроцесса, которая является дочерней для других стадий<br>'
        if TechProcessObjects.objects.filter(name_id=del_stage_id, parent_structure_id=class_id):
            is_valid = False
            message += 'Нельзя удалить стадию техпроцесса, у которой есть объекты<br>'

        if is_valid:
            inc = {'class_id': class_id, 'location': 'contract', 'type': 'tp', 'id': del_stage_id, 'name': delete_stage.name,
                    'value': delete_stage.value}
            reg = {'json_income': inc}
            transact_id = reg_funs.get_transact_id(class_id, 0, 'p')
            reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
            delete_stage.delete()
            message = 'Стадия техпроцесса ID: ' + str(inc['id']) + ' успешно удалена<br>'
        else:
            message_class = 'text-red'
            message += 'Изменения не сохранены<br>'

    # Сменить порядок параметра
    elif 'move' in request.GET:
        # добавим в пост сведение, что это словарь
        if 'is_dict' in request.POST:
            request.POST._mutable = True
            request.POST['is_dict'] = 'true'
            request.POST._mutable = False
        formula = 'dict' if 'is_dict' in request.POST else 'contract'
        database_funs.change_class_priority(class_id, int(request.GET['param_id']), request.GET['move'], formula)

    # Если были сохранены техпроцессы
    elif 'tps' in request.POST:
        input_data = json.loads(request.POST['tps'])
        # создание нового техпроцесса
        if 'new_tp' in input_data:
            is_valid = True
            # проверим имя
            if not input_data['new_tp']['name']:
                is_valid = False
                message += 'не задано название технического процесса<br>'
            else:
                # проверим, не дублируется ли техпроцесс
                if class_manager.filter(parent_id=class_id, name=input_data['new_tp']['name']):
                    is_valid = False
                    message += 'У данного массива уже есть технический процесс с таким именем<br>'
            # проверим стадии
            if not input_data['new_tp']['stages']:
                is_valid = False
                message += 'Не задана ни одна стадия технического процесса<br>'
            # проверим линкмап
            for lm in input_data['new_tp']['lm'].split('<br>'):
                if lm:
                    try:
                        int(lm)
                    except ValueError:
                        is_valid = False
                        message += 'ЛинкМап задан некорректно. Укажите целые числа в качестве ID пользователей'
                        break
            # проверим контрольное поле
            if not input_data['new_tp']['control_field']:
                is_valid = False
                message += 'Не задано контрольное поле. Укажите ID одного из полей массива в качестве контрольного<br>'
            else:
                control_field = class_manager.filter(parent_id=class_id, formula='float',
                                                     id=input_data['new_tp']['control_field'])
                if not control_field:
                    is_valid = False
                    message += 'Некорректно задано контрольное поле: ' + input_data['new_tp']['control_field'] +\
                               '. Необходимо указать ID числового поля данного массива<br>'
            # линкмап
            # проверка пользователей
            lm = [l for l in input_data['new_tp']['lm']]
            lm_valid, msg = clmftp(lm, len(input_data['new_tp']['stages'].split('<br>')))
            message += msg
            is_valid = is_valid and lm_valid
            if is_valid:
                # создаем техпроцесс
                tech_pro = Contracts(name=input_data['new_tp']['name'], formula='techpro', is_required=True,
                                     is_visible=False, parent_id=class_id, priority=0)
                tech_pro.save()
                # регистрация техпроцесса
                output = {'class_id': tech_pro.id, 'name': tech_pro.name, 'type': 'techpro', 'location': 'contract',
                       'parent': class_id}
                reg = {'json': output}
                transact_id = reg_funs.get_transact_id(tech_pro.id, 0, 'c')
                reg_funs.simple_reg(request.user.id, 1, timestamp, transact_id, **reg)
                message = 'Технический процесс "' + input_data['new_tp']['name'] + '" успешно создан'
                # Создаем параметры техпроцесса
                stages = Contracts(name='stages', formula='enum', is_required=True, is_visible=False,
                              parent_id=tech_pro.id, priority=0, value=input_data['new_tp']['stages'].split('<br>'))
                stages.save()
                output = {'class_id': tech_pro.id, 'name': stages.name, 'type': 'techpro', 'location': 'contract',
                       'id': stages.id, 'formula': 'enum', 'value': stages.value}
                reg = {'json': output}
                reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
                control_field = Contracts(name='control_field', formula='float', is_required=True, is_visible=False,
                              parent_id=tech_pro.id, priority=0, value=int(input_data['new_tp']['control_field']))
                control_field.save()
                output = {'class_id': tech_pro.id, 'name': control_field.name, 'type': 'techpro', 'location': 'contract',
                       'id': control_field.id, 'formula': 'float', 'value': control_field.value}
                reg = {'json': output}
                reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
                parent_code = Contracts(name='parent_code', formula='float', is_required=True, is_visible=False,
                                        parent_id=tech_pro.id, priority=0)
                parent_code.save()
                output = {'class_id': tech_pro.id, 'name': parent_code.name, 'type': 'techpro', 'location': 'contract',
                          'id': parent_code.id, 'formula': 'float', 'value': parent_code.value}
                reg = {'json': output}
                reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
                lm_val = [int(lm) if lm else None for lm in input_data['new_tp']['lm'].split('<br>')]
                lm = Contracts(name='link_map', formula='enum', is_required=True, is_visible=False,
                                   parent_id=tech_pro.id, priority=0,
                                   value=lm_val)
                lm.save()
                output = {'class_id': tech_pro.id, 'name': lm.name, 'type': 'techpro', 'location': 'contract',
                          'id': lm.id, 'formula': 'enum', 'value': lm.value}
                reg = {'json': output}
                reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
            else:
                message_class = 'text-red'
                message += "Технический процесс не был создан<br>"
        # Редактирование существующих
        if 'current_tps' in input_data:
            lne = [lne for lne in list_name_exclude if lne != 'parent_branch']
            old_tps = list(class_manager.filter(parent_id=class_id, name__in=list_name_exclude)
                            .order_by('id').values())
            transact_id = reg_funs.get_transact_id(class_id, 0, 'c')
            for ctp in input_data['current_tps']:
                is_change = False
                otp = next(otp for otp in old_tps if otp['id'] == ctp['id'])
                # Сравниваем имена
                if ctp['name'] != otp['name']:
                    # валидация (отсутствие, поваторяемость)
                    name_valid = True
                    if not ctp['name']:
                        name_valid = False
                        message += 'Технический процесс ID: ' + str(ctp['id']) + ' не обновлен. Поле "Название" обязательно для заполнения<br>'
                    if ctp['name'] in [o['name'] for o in old_tps]:
                        name_valid = False
                        message += 'Технический процесс ID: ' + str(ctp['id']) + ' не обновлен. Названия техпроцессов не должны повторяться<br>'
                    # изменение класса
                    if name_valid:
                        is_change = True
                        rtp = Contracts.objects.get(id=ctp['id'])
                        rtp.name = ctp['name']
                        rtp.save()
                        # регистрация
                        outcome = {'class_id': rtp.id, 'location': 'contract', 'type': 'techpro', 'name': rtp.name}
                        income = outcome.copy()
                        income['name'] = otp['name']
                        reg = {'json': outcome, 'json_income': income}
                        reg_funs.simple_reg(request.user.id, 3, timestamp, transact_id, **reg)
                        message += 'Технический процесс ID: ' + str(rtp.id) + ' обновлен<br>'
                    else:
                        message_class = 'text-red'
                # Сравниваем стадии
                valid_stage = True
                stages = next(p for p in ctp['params'] if p['name'] == 'stages')
                old_stages = next(p for p in otp['params'] if p['name'] == 'stages')
                if stages['value'] != old_stages['value']:
                    # валидация
                    # 1. Если Нет стадий
                    if not len(stages['value']):
                        valid_stage = False
                        message += 'Техпроцесс ID: ' + str(ctp['id']) + ' не сохранен. Необходима минимум одна стадия<br>'
                    # 2. Если количество стадий уменьшилось, найдем удаленные стадии и проверим, есть ли у них объекты
                    elif len(stages['value']) < len(old_stages['value']):
                        # проверка контрольной суммы. Если были только удалены стадии (без переименования), то контрольная сумма совпадет
                        control_sum = 0
                        for s in stages['value']:
                            if s in old_stages['value']:
                                control_sum += 1
                        if control_sum != len(stages['value']):
                            valid_stage = False
                            message += 'Техпроцесс ID: ' + str(ctp['id']) + 'не сохранен. Нельзя редактировать и удалять стадии в одном действии<br>'
                        else:
                            for os in old_stages['value']:
                                if not os in stages['value']:
                                    del_stage_obj_codes = ContractCells.objects.filter(parent_structure_id=old_stages['parent_id'],
                                                                                        name_id=old_stages['id'],
                                                                                       value=os).values('code')
                                    del_stages_obj_vals = ContractCells.objects.filter(parent_structure_id=old_stages['parent_id'],
                                                                                        name__name='control_field',
                                                                                        code__in=Subquery(del_stage_obj_codes))\
                                    .annotate(float_val=Cast('value', FloatField())).filter(float_val__gt=0)
                                    # Если есть такие объекты - то не удаляем стадию
                                    if del_stages_obj_vals:
                                        valid_stage = False
                                        message += 'Техпроцесс ID: ' + str(ctp['id']) + 'не сохранен. ' \
                                                   'Нельзя удалить стадию, у которой есть объекты. Стадия - ' + os + '<br>'
                                    else:
                                        # Проверим таски на эту стадию
                                        if Tasks.objects.filter(data__tp_id=ctp['id'], data__stage=os):
                                            valid_stage = False
                                            message += 'Техпроцесс ID: ' + str(ctp['id']) + 'не сохранен. ' \
                                                        'Нельзя удалить стадию, на которую поставлены задачи. Стадия - "' + os + '"<br>'

                                    # Если нет - перед удалением стадии, удаляем объекты в этой стадии
                                    if valid_stage:
                                        del_stages_objs = ContractCells.objects.filter(parent_structure_id=old_stages['parent_id'],
                                                                                       code__in=Subquery(del_stage_obj_codes)).order_by('code')
                                        # Регистрация удаления
                                        if del_stages_objs:
                                            def del_obj():
                                                income['code'] = del_code
                                                reg = {'json_income': income}
                                                reg_funs.simple_reg(request.user.id, 8, timestamp, child_transact,
                                                                    transact_id, **reg)
                                            del_code = del_stages_objs[0].code
                                            child_transact = reg_funs.get_transact_id(old_stages['parent_id'],
                                                                                      del_code, 'c')
                                            inc = {'class_id': old_stages['parent_id'], 'location': 'contract',
                                                   'type': 'techpro'}
                                            for dso in del_stages_objs:
                                                income = inc.copy()
                                                if dso.code != del_code:
                                                    # Удаление объекта
                                                    del_obj()
                                                    del_code = dso.code
                                                    child_transact = reg_funs.get_transact_id(old_stages['parent_id'],
                                                                                              del_code, 'c')
                                                # Удаление реквизита
                                                income['code'] = dso.code
                                                income['id'] = dso.id
                                                income['name'] = dso.name_id
                                                income['value'] = dso.value
                                                reg = {'json_income': income}
                                                reg_funs.simple_reg(request.user.id, 16, timestamp, child_transact,
                                                                    transact_id, **reg)
                                            # Удалим последний объект
                                            del_obj()
                                            del_stages_objs.delete()
                    # 3 Если количество стадий увеличилось, проверяем, все ли старые стадии остались на месте
                    elif len(stages['value']) > len(old_stages['value']):
                        for os in old_stages['value']:
                            if not os in stages['value']:
                                valid_stage = False
                                message += 'Техпроцесс ID: ' + str(ctp['id']) + \
                                           ' не сохранен. При добавлении стадий нельзя удалять или переименовывать ' \
                                           'существующие стадии<br>'
                                break
                    # 4. Если количество стадий осталось равным, то изменим все названия в измененных объектах
                    else:
                        for i in range(len(stages['value'])):
                            if stages['value'][i] != old_stages['value'][i]:
                                edit_stages_objs = ContractCells.objects.filter(parent_structure_id=old_stages['parent_id'],
                                                                      name_id=old_stages['id'], value=old_stages['value'][i])
                                inc = {'class_id': old_stages['parent_id'], 'location': 'contract',
                                       'type': 'techpro', 'name': old_stages['id']}
                                for eso in edit_stages_objs:
                                    income = inc.copy()
                                    income['id'] = eso.id
                                    income['value'] = eso.value
                                    eso.value = stages['value'][i]
                                    outcome = income.copy()
                                    outcome['value'] = eso.value
                                    reg = {'json': outcome, 'json_income': income}
                                    child_transact = reg_funs.get_transact_id(old_stages['parent_id'], eso.code, 'c')
                                    reg_funs.simple_reg(request.user.id, 15, timestamp, child_transact, transact_id, **reg)
                                ContractCells.objects.bulk_update(edit_stages_objs, ('value', ))

                    if valid_stage:
                        is_change = True
                        new_stages = Contracts.objects.get(id=stages['id'])
                        new_stages.value = stages['value']
                        new_stages.save()
                        # регистрация
                        income = {'class_id': new_stages.parent_id, 'location': 'contract', 'type': 'techpro',
                                  'id': new_stages.id, 'value': old_stages['value']}
                        outcome = income.copy()
                        outcome['value'] = new_stages.value
                        reg = {'json': outcome, 'json_income': income}
                        reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                        message += 'Параметр "Стадии" техпроцесса ID: ' + str(new_stages.parent_id) + ' обновлен<br>'
                    else:   message_class = 'text-red'
                # Сравниваем контрольное поле
                cf = next(p for p in ctp['params'] if p['name'] == 'control_field')
                ocf = next(p for p in otp['params'] if p['name'] == 'control_field')
                if cf['value'] != ocf['value']:
                    cf_valid = True
                    # валидация - проверка нового айди
                    # Если у ТП есть объекты (стадии), не сохранять новое контрольное поле
                    if ContractCells.objects.filter(parent_structure_id=old_stages['parent_id']).count():
                        cf_valid = False
                        message = 'Техпроцесс ID: ' + str(ctp['id']) + ' не сохранен. Нельзя менять ID контрольного ' \
                                              'поля при сущестующих записях техпроцесса<br>'
                    else:
                        # Проверка поля на наличие и числовой формат
                        new_cf = Contracts.objects.filter(id=cf['value'], parent_id=ctp['id'], formula='float')
                        if not new_cf:
                            cf_valid = False
                            message += 'Техпроцесс ID: ' + str(ctp['id']) + ' не сохранен. ID контрольного поля ' \
                                       + str(cf['value']) + ' задан некорректно. Необходимо указан ID числового поля текущего массива<br>'
                    if cf_valid:
                        is_change = True
                        new_cf = Contracts.objects.get(id=cf['id'])
                        new_cf.value = cf['value']
                        new_cf.save()
                        # регистрация
                        income = {'class_id': new_cf.parent_id, 'location': 'contract', 'type': 'techpro',
                                  'id': new_cf.id, 'value': ocf['value']}
                        outcome = income.copy()
                        outcome['value'] = new_cf.value
                        reg = {'json': outcome, 'json_income': income}
                        reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                        message += 'Параметр "Контрольное поле" для техпроцесса ID: ' + str(ctp['id']) + ' обновлен<br>'
                    else:
                        message_class = 'text-red'
                # Сравниваем линкмапы
                lm = next(p for p in ctp['params'] if p['name'] == 'link_map')
                olm = next(p for p in otp['params'] if p['name'] == 'link_map')
                try:
                    lm['value'] = [int(l) if l else None for l in lm['value'].split('<br>')]
                except ValueError:
                    message += 'Некорректно сформирован ЛинкМап для техпроцесса ID: ' + str(ctp['id'])
                    message_class = 'text-red'
                else:
                    if lm['value'] != olm['value']:
                        # валидация
                        lm_valid, msg = clmftp(lm['value'], len(stages['value']))  # проверка пользователей
                        message += msg
                        if lm_valid:
                            is_change = True
                            new_lm = Contracts.objects.get(id=lm['id'])
                            new_lm.value = lm['value']
                            new_lm.save()
                            # регистрация
                            income = {'class_id': new_lm.parent_id, 'location': 'contract', 'type': 'techpro',
                                      'id': new_lm.id, 'value': olm['value']}
                            outcome = income.copy()
                            outcome['value'] = new_lm.value
                            reg = {'json': outcome, 'json_income': income}
                            reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
                            message += 'Параметр "ЛинкМап" для техпроцесса ID: ' + str(ctp['id']) + ' обновлен<br>'
                        else:
                            message_class = 'text-red'

    # Удаление техпроцесса
    elif 'delete_tp' in request.POST:
        tp_id = int(request.POST['delete_tp'])
        del_tp = Contracts.objects.get(parent_id=class_id, id=tp_id)
        del_params_tp = Contracts.objects.filter(parent_id=tp_id)
        transact_id = reg_funs.get_transact_id(del_tp.id, 0, 'c')
        # Валидация. Если нет объектов - удаляем
        del_objs_tp = ContractCells.objects.filter(parent_structure_id=tp_id)
        if del_objs_tp:
            message = "Невозможно удалить техпроцесс. Id: " + request.POST['delete_tp'] + ' . У техпроцесса имеются записи<br>'
            message_class = 'text-red'
        else:
            # Удаление параметров
            income = {'class_id': del_tp.id, 'location': 'contract', 'type': 'techpro'}
            for dpt in del_params_tp:
                inc = income.copy()
                inc['name'] = dpt.name
                inc['formula'] = dpt.formula
                inc['value'] = dpt.value
                inc['id'] = dpt.id
                reg = {'json_income': inc}
                reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
            del_params_tp.delete()
            # Удаление техпроцесса
            inc = {'class_id': tp_id, 'location': 'contract', 'type': 'techpro', 'parent': del_tp.parent_id}
            reg = {'json_income': inc}
            reg_funs.simple_reg(request.user.id, 4, timestamp, transact_id, **reg)
            message = 'Технический процесс "' + del_tp.name + '" успешно удален<br>'
            del_tp.delete()

    try:
        current_class = class_manager.get(id=class_id)
    except ObjectDoesNotExist:
        current_class = None

    properties = None
    system_props = None
    lne = [lne for lne in list_name_exclude if lne != 'parent_branch']
    if current_class:
        if location == 't':  # для техпроцессов
            all_props = class_manager.filter(parent_id=class_id)
            system_props = {}
            properties = []
            for ap in all_props:
                if ap.name == 'business_rule':
                    system_props['business_rule'] = ap
                elif ap.name == 'link_map':
                    dict_methods_name = {'n': 'Создание', 'e': 'Редактирование', 'en': 'Редактирование или создание',
                                         'wo': 'Списание', 'pe': 'Пакетное редактирование'}
                    for lm in ap.value:
                        lm['method_name'] = dict_methods_name[lm['method']]
                    system_props['link_map'] = ap
                elif ap.name == 'trigger':
                    system_props['trigger'] = ap
                else:
                    properties.append(model_to_dict(ap))
            handlers = [p['value']['handler'] for p in properties if p['value']['handler']]
            handlers_users = get_user_model().objects.filter(id__in=handlers)
            for p in properties:
                if p['value']['handler']:
                    handler_id = p['value']['handler']
                    handler_user = next(hu for hu in handlers_users if hu.id == handler_id)
                    p['value']['handler'] = {'id': handler_id, 'fio': handler_user.username + ' ' \
                                                                   + handler_user.first_name + ' ' + handler_user.last_name}
                if p['value']['children']:
                    children = []
                    for ch in p['value']['children']:
                        child = next(p for p in properties if p['id'] == ch)
                        children.append({'id': ch, 'name': child['name']})
                    p['value']['children'] = children

        else:
            properties = list(class_manager.filter(parent_id=class_id).exclude(formula__in=list_formula_exclude)
                              .exclude(name__in=list_name_exclude).order_by('priority', 'id').values())
            system_props = list(class_manager.filter(parent_id=class_id, name__in=lne)
                            .order_by('id').values())
    # Если не указан айди объекта, то проверим систему. Если в системе нет ни одной папки,
    # то укажем свойства первого справочника или алиаса из списка
    elif not len(Contracts.objects.filter(formula='folder')):
        class_tree = request.session['contract_tree']
        if class_tree:
            properties = list(Contracts.objects.filter(parent_id=class_tree[0]['id'])
                              .exclude(formula__in=list_formula_exclude).exclude(name__in=list_name_exclude)
                              .order_by('priority', 'id').values())
            system_props = list(Contracts.objects.filter(parent_id=class_tree[0]['id'], name__in=lne)
                                .order_by('id').values())
    ctx = {
        'title': 'Дерево контрактов',
        'message': message,
        'message_class': message_class,
        'properties': properties,
        'system_props': system_props,
        'current_class': current_class,
        'location': location
    }
    return render(request, 'constructors/manage-contracts.html', ctx)


# Управление объектами контрактов
@view_procedures.is_auth_app
def contract(request):
    if not ('class_id' in request.GET and request.GET['class_id']):
        first_contract = Contracts.objects.filter(formula='contract').values('id')
        if first_contract:
            first_id = str(first_contract[0]['id'])
        else:
            return render(request, 'contracts/contract.html', {'current_class': None})
        return redirect('/contract?class_id=' + first_id)

    # загрузить дерево классов в сессию
    if not 'contract_tree' in request.session:
        session_funs.update_class_tree(request, True)

    # Загрузить меню контрактов
    if not 'contract_menu' in request.session:
        request.session['contract_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                                          request.session['contract_tree'], None, True)
    # Загрузим данные черновиков
    if not 'contract_draft_tree' in request.session:
        session_funs.update_draft_tree(request, True)

    # проверим временные данные менеджера объектов в сессии
    tom_updated = session_funs.update_omtd(request)
    tom = request.session['temp_object_manager']
    if not tom:
        return HttpResponse(f'Не найден класс с ID {request.GET["class_id"]}')
    headers = copy.deepcopy(tom['headers'])
    system_headers = copy.deepcopy(tom['system_headers'])
    tree = tom['tree'] if 'tree' in tom else None
    if tree and tom_updated:
        tree[0]['children'] = tree_funs.get_branch_props(tree[0]['children'], tom['current_class']['parent'],
                                                         tom['tree_headers'], request.user.id)
    # Редиректим из гет в пост
    to_post_redirect = interface_funs.get_to_post(request, ('class_id', ))
    if to_post_redirect:
        return to_post_redirect

    message = request.POST['message'] if 'message' in request.POST else ''
    message_class = ''
    timestamp = datetime.now()
    class_id = int(request.GET['class_id'])
    try:
        current_class = Contracts.objects.get(id=class_id)
    except:
        return HttpResponse('Не удается найти класс с ID ' + request.GET['class_id'])
    if current_class.formula not in ('contract', 'array', 'alias'):
        return HttpResponse('Не удается найти контракт, массив или константу с ID ' + request.GET['class_id'])
    code = int(request.POST['i_code']) if 'i_code' in request.POST and request.POST['i_code'] else None
    title = 'Контракт' if current_class.formula == 'contract' else 'Массив'
    title += ' "' + current_class.name + '"'
    branch = None
    tree = request.session['temp_object_manager']['tree'] if 'tree' in request.session['temp_object_manager'] else None

    # Заполним собственников при необходимости
    if current_class.formula == 'array' and not 'owners' in request.session['temp_object_manager']:
        owner_name = Contracts.objects.get(parent_id=current_class.parent_id, name='system_data')
        owners = ContractCells.objects.filter(parent_structure_id=current_class.parent_id, name_id=owner_name.id)
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
            old_parent_branch_obj = ContractCells.objects.filter(parent_structure_id=class_id, code=code,
                                                                 name__name='parent_branch')
            if old_parent_branch_obj:
                old_parent_branch = old_parent_branch_obj[0].value
        is_saved, message, message_class, code, transact_id, timestamp = \
            interface_funs.save_contract_object(request, code, current_class, headers, system_headers)
        draft_ver = int(request.POST['s_draft_vers']) if 's_draft_vers' in request.POST and request.POST['s_draft_vers'] else None
        if is_saved and code and draft_ver:
            ContractDrafts.objects.get(id=int(request.POST['s_draft_vers'])).delete()
            session_funs.update_draft_tree(request, True)
        # обновим свойства ветки
        if is_saved and 'i_branch' in request.POST:
            branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
            # если изменилась ветка объекта - пересчитаем старую ветку
            if branch_code != old_parent_branch:
                old_branch = tree_funs.find_branch(tree, 'code', old_parent_branch)
                if not old_branch and old_parent_branch:
                    old_branch = tree_funs.antt(old_parent_branch, tree, current_class.parent_id,
                                                request.session['temp_object_manager']['tree_headers'],
                                                request.user.id, True)
                if old_branch:
                    tree_funs.get_branch_props((old_branch,), current_class.parent_id,
                                               request.session['temp_object_manager']['tree_headers'],
                                               request.user.id, True)
            # В любом случае пересчитаем новую ветку
            branch = tree_funs.find_branch(tree, 'code', branch_code)
            if not branch and request.POST['i_branch']:
                branch = tree_funs.antt(branch_code, tree, current_class.parent_id,
                                        request.session['temp_object_manager']['tree_headers'],
                                        request.user.id, True)
            if branch:
                tree_funs.get_branch_props((branch,), current_class.parent_id,
                                           request.session['temp_object_manager']['tree_headers'], request.user.id, True)
        # Если контракт новый - редиректим
        if is_saved and not request.POST['i_code']:
            if current_class.formula == 'array':
                header_owner = next(h for h in headers if h['name'] == 'Собственник')
                owner = ContractCells.objects.get(code=code, parent_structure_id=current_class.id, name_id=header_owner['id'])
                url = '/contract?class_id=' + request.POST['class_id'] + '&input_owner=' + str(owner.value)\
                      + '&message=Новый объект создан'
            else:
                url = '/contract?class_id=' + request.POST['class_id'] + '&object_code=' + str(code) + '&message=Новый объект создан'
            return redirect(url)

    # кнопка "Скачать файл"
    elif 'b_save_file' in request.POST:
        response = interface_funs.download_file(request, True)
        if response:
            return response

    # Кнопка "Удалить"
    elif 'b_delete' in request.POST:
        # Выделен ли объект
        if 'i_code' in request.POST and request.POST['i_code']:
            class_id = int(request.GET['class_id'])
            code = int(request.POST['i_code'])
            is_valid = True
            # Проверка, нет ли дочерних объектов
            res_check_child = api_procedures.fc4c(current_class, code, 'contract')
            if res_check_child != 'ok':
                is_valid = False
                message += res_check_child
            objects_delete = 1
            if is_valid:
                # Проверка условия выполнения
                objects_delete = ContractCells.objects.filter(code=code, parent_structure_id=class_id).select_related('name')
                if current_class.formula == 'contract':
                    header_sysdata = next(h for h in headers if h['name'] == 'system_data')
                    sys_data = next(od for od in objects_delete if od.name_id == header_sysdata['id'])
                    if not sys_data.value['is_done']:
                        is_valid = False
                        message += 'Ошибка. Контракт не может быть удален, т.к. не выполняется "Условие завершения"<br>'
            transact_id = ''
            if is_valid:
                transact_id = reg_funs.get_transact_id(class_id, code, 'c')
                if current_class.formula == 'contract':
                    del_obj = convert_funs2.get_full_object(objects_delete, current_class, headers, 'contract')
                    # выполним линкМап
                    linkmap = next(sh for sh in system_headers if sh['name'] == 'link_map')
                    trigger = next(sh for sh in system_headers if sh['name'] == 'trigger')
                    try:
                        contract_funs.prepare_to_delete_object(linkmap['value'], trigger, del_obj, timestamp,
                                                               transact_id, request.user.id)
                    except Exception as ex:
                        is_valid = False
                        message += str(ex)

            if is_valid:
                # Регистрация
                incoming = {'class_id': class_id, 'location': 'contract', 'type': current_class.formula, 'code': code}
                # регистрируем удаление реквизитов
                for od in objects_delete:
                    ic = incoming.copy()
                    ic['id'] = od.id
                    ic['name'] = od.name_id
                    ic['value'] = od.value
                    reg = {'json_income': ic}
                    reg_funs.simple_reg(request.user.id, 16, timestamp, transact_id, **reg)
                # регистрация удаления объекта
                reg = {'json_income': incoming}
                reg_funs.simple_reg(request.user.id, 8, timestamp, transact_id, **reg)
                objects_delete.delete() # Удаляем
                message = 'Объект успешно удален. Код объекта: ' + request.POST['i_code'] + '<br>'
                # Удалим связанные словари
                for md in request.session['temp_object_manager']['my_dicts']:
                    database_procedures.delete_dict_records(int(request.POST['i_code']), md['id'], request.user.id,
                                                            timestamp, transact_id)
                # Удалим связанные техпроцессы
                for t in request.session['temp_object_manager']['tps']:
                    inc = {'class_id': t['id'], 'location': 'contract', 'type': 'tp', 'code': code}
                    stages = TechProcessObjects.objects.filter(parent_structure_id=t['id'], parent_code=code)
                    list_regs = []
                    tp_transact = reg_funs.get_transact_id(t['id'], code, 'p')
                    for s in stages:
                        inc['value'] = s.value
                        inc['name'] = s.name_id
                        inc['id'] = s.id
                        reg = {'json_income': copy.deepcopy(inc)}
                        dict_reg = {'user_id': request.user.id, 'reg_id': 16, 'timestamp': timestamp,
                                    'transact_id': tp_transact, 'parent_transact_id': transact_id, 'reg': reg}
                        list_regs.append(dict_reg)
                    reg_funs.paket_reg(list_regs)
                    stages.delete()
                    # Удалим связанные со стадиями задачи
                    tasks = Tasks.objects.filter(kind='stage', data__tp_id=t['id'], data__parent_code=code).order_by('code')
                    task_code = 0
                    task_transact = ''
                    for t in tasks:
                        if task_code != t.code:
                            task_code = t.code
                            task_transact = reg_funs.get_transact_id('task', task_code)
                            task_delete = True
                        else:
                            task_delete = False
                        task_funs.delete_simple_task(t, timestamp, request.user.id, task_transact=task_transact,
                                                     parent_transact=transact_id, task_delete=task_delete)
                # Удалим связанные задачи
                tasks = Tasks.objects.filter(data__class_id=class_id, data__code=code)
                for t in tasks:
                    task_funs.delete_simple_task(t, timestamp, request.user.id, parent_transact=transact_id)
                # Удалим связанные черновики
                ContractDrafts.objects.filter(data__parent_structure=class_id, data__code=code).delete()
            else:
                message_class = 'text-red'
        else:
            message = 'Вы не выбрали объект для удаления'

    # кнопка "удалить словарь"
    elif 'b_delete_dict' in request.POST:
        database_procedures.delete_dict_records(int(request.POST['i_code']), int(request.POST['delete_dict']),
                                                request.user.id)
        message = 'Объект обновлен<br>'

    # Кнопка "Удалить файл"
    elif 'b_del_file' in request.POST:
        if not interface_funs.delete_file(request, current_class, headers, True):
            message += 'Нельзя удалить файл. Поле является обязательным.<br>'
            message_class = 'text-red'
        else:   message = 'Объект сохранен<br>'

    # Кнопка "В черновик"
    elif 'b_draft' in request.POST:
        interface_funs.make_graft(request, current_class.id, headers, code, request.user.id, True,
                                             tps_info=request.session['temp_object_manager']['tps'])
        message += 'Черновик был создан<br>'

    # Кнопка "Сохранить ТПсы"
    elif 'save_tp' in request.POST:
        macrotask_info = json.loads(request.POST['save_tp'])
        my_tp = next(t for t in tom['tps'] if t['id'] == macrotask_info['tp_id'])
        for lm in macrotask_info['list_movs']:
            list_routs = contract_procedures.rtr(my_tp, lm['parent_id'], lm['offspring_id'])
            list_routs.sort(key=len)
            my_rout = list_routs[lm['rout_num']]
            try:
                task_funs.matafost(current_class, headers, code, my_tp, my_rout, lm['quant'], request.user, timestamp=timestamp)
            except Exception as ex:
                message += str(ex) + '<br>'
                message_class = 'text-red'
            else:
                message += f'Параметры техпроцесса ID: {macrotask_info["tp_id"]} были обновлены'
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
            address = '/tree?class_id=' + str(current_class.parent_id) + '&location=c' + '&input_search=' \
                      + request.POST['edit_branch']
            return redirect(address)

    # Вывод
    query = ContractCells.objects.filter(parent_structure_id=class_id)
    query, search_filter = interface_funs.sandf(request, query, headers, tree, branch)

    # Пагинация и конвертация
    q_items = int(request.POST['q_items_on_page']) if 'q_items_on_page' in request.POST else request.session['pagination']
    page_num = int(request.POST['page']) if 'page' in request.POST and request.POST['page'] else 1
    paginator = common_funs.paginator_object(query, q_items, page_num)
    visible_headers, vhids = interface_procedures.pack_vis_headers(current_class, headers, True)
    objects = ContractCells.objects.filter(code__in=paginator['items_codes'], parent_structure_id=class_id,
                                           name_id__in=vhids)
    objects = convert_funs.queryset_to_object(objects)
    objects.sort(key=lambda x: x['code'], reverse=True)

    # Конвертнем поля
    convert_funs.prepare_table_to_template(visible_headers, objects, request.user.id, True)
    # # добавим техпроцессы
    lcf2 = []
    if 'my_tps' in request.session['temp_object_manager']:
        # convert_funs2.atptc(objects, request.session['temp_object_manager']['my_tps'])
        for mt in request.session['temp_object_manager']['my_tps']:
            if not mt['control_field'] in lcf2:
                lcf2.append(mt['control_field'])

    lcf = [t['cf'] for t in request.session['temp_object_manager']['tps']]

    # Видимые заголовки для деревьев
    if tree:
        tree_visible_headers = []
        for th in request.session['temp_object_manager']['tree_headers']:
            if th['is_visible']:
                tree_visible_headers.append(th)
            if len(tree_visible_headers) > 4:
                break
    else:
        tree_visible_headers = None
    # итоги
    totals = convert_procedures.gtfol(objects, visible_headers, True)
    session_funs.check_quant_tasks(request)
    # Периоды таймлайна
    ctx = {
        'title': title,
        'current_class': current_class,
        'objects': objects,
        'headers': headers,
        'paginator': paginator,
        'message': message,
        'message_class': message_class,
        'branch': branch,
        'tree_visible_headers': tree_visible_headers,
        'lcf': lcf,
        'lcf2': lcf2,
        'is_contract': 'true',
        'db_loc': 'c',
        'visible_headers': visible_headers,
        'totals': totals,
        'search_filter': search_filter
    }
    return render(request, 'contracts/contract.html', ctx)


# просмотреть алиасы
def view_alias(request):
    # загрузить дерево классов в сессию
    if not 'contract_tree' in request.session:
        session_funs.update_class_tree(request, True)

    # Загрузить меню справочников
    if not 'contract_menu' in request.session:
        request.session['contract_menu'] = session_funs.update_class_menu(request, request.session['contract_tree'],
                                                                          request.session['contract_tree'], None, True)

    # Загрузим данные черновиков
    if not 'contract_draft_tree' in request.session:
        session_funs.update_draft_tree(request, True)

    session_funs.check_quant_tasks(request)  # контрольный пересчет заданий

    class_id = int(request.GET['class_id'])
    header = Contracts.objects.get(id=class_id)
    alias = list(Contracts.objects.filter(parent_id=class_id).values())
    convert_funs2.pati(alias, user_id=request.user.id, is_contract=True)
    ctx = {
        'title': 'Константа "' + header.name + '"',
        'alias': alias,
        'header': header
    }
    return ctx


# открыть маршрутизатор техпроцесса
@view_procedures.is_auth_app
def tp_routing(request):
    try:
        tp_id = int(request.GET['tp'])
    except ValueError:
        return HttpResponse('Не указан ID техпроцесса')
    try:
        tp = TechProcess.objects.get(id=tp_id)
    except ObjectDoesNotExist:
        return HttpResponse('ID техпроцесса указан некорректно')
    stages = list(TechProcess.objects.filter(parent_id=tp_id).exclude(settings__system=True))
    array_nums = []
    for s in stages:
        new_dict = {}
        new_dict['num'] = stages.index(s)
        new_dict['id'] = s.id
        new_dict['children'] = [stages.index(next(ss for ss in stages if ss.id == ch)) for ch in s.value['children']]
        array_nums.append(new_dict)

    G = nx.Graph()
    for i in range(len(array_nums)):
        G.add_node(i)
    pos = nx.circular_layout(G)

    # Соединялки
    arrows_array = []
    for n in G.nodes:
        get_my_node = next(an for an in array_nums if an['num'] == n)
        xfrom, yfrom = pos[n]
        for ch in get_my_node['children']:
            xto, yto = pos[ch]
            # вычислим приращение для стрелки
            katet_a = abs(xto - xfrom)
            katet_b = abs(yto - yfrom)
            tan = katet_b / katet_a
            alpha = math.atan(tan)
            sin = math.sin(alpha)
            cos = math.cos(alpha)
            r = 0.05
            deltax = r * cos
            deltay = r * sin
            if xfrom < xto:
                deltax *= -1
            if yfrom < yto:
                deltay *= -1
            dict_arrow = {'xfrom': xfrom - deltax, 'xto': xto + deltax, 'yfrom': yfrom - deltay, 'yto': yto + deltay}
            arrows_array.append(dict_arrow)
    # Узлы
    node_x = []
    node_y = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            showscale=False,
            colorscale='YlGnBu',
            reversescale=True,
            color='white',
            size=30,
            colorbar=dict(
                thickness=15,
                title='Node Connections',
                xanchor='left',
                titleside='right'
            ),
            line_width=2))

    node_adjacencies = []
    node_text = []
    for node, adjacencies in enumerate(G.adjacency()):
        node_adjacencies.append(len(adjacencies[1]))
        node_text.append('# of connections: ' + str(len(adjacencies[1])))

    # node_trace.marker.color = node_adjacencies
    node_trace.text = node_text

    fig = go.Figure(data=[node_trace],
                    layout=go.Layout(
                        title='Маршрутизация техпроцесса "' + tp.name + '", ID: ' + request.GET['tp'],
                        titlefont_size=16,
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        annotations=[dict(
                            text="",
                            showarrow=False,
                            xref="paper", yref="paper",
                            x=0.005, y=-0.002)],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                    )
    # annotate your figure
    node_text = [s.name for s in stages]
    for n in G.nodes():
        x, y = pos[n]
        # G.nodes[n]['pos']
        fig.add_annotation(x=x, y=y, text=node_text[n], showarrow=False, yshift=35)
    for aa in arrows_array:
        fig.add_annotation(ax=aa['xfrom'], axref='x', ay=aa['yfrom'], ayref='y',
                           x=aa['xto'], arrowcolor='black', xref='x', y=aa['yto'], yref='y',
                           arrowwidth=1, arrowside='end', arrowsize=2, arrowhead=3)

    title = 'МТП ID: ' + request.GET["tp"] + ' ' + tp.name
    output_html = f'<head><title>{title}</title></head><body>' + fig.to_html(full_html=False) + '</body>'
    return HttpResponse(output_html)