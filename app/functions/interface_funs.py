import copy
import json, shutil
import operator
import os
import re
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import Q, OuterRef, Subquery, F
from django.forms import model_to_dict
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.encoding import iri_to_uri

import app.functions.files_funs
import app.functions.reg_funs
from app.functions import database_funs, files_funs, database_procedures, reg_funs, interface_procedures, convert_funs, \
    view_procedures, session_funs, tree_funs, contract_funs, convert_procedures, task_funs
from app.functions.files_funs import cffdth, upload_file
from app.functions.interface_procedures import mofr
from app.models import Dictionary, DictObjects, Objects, ContractCells, Contracts, Designer, RegistratorLog, \
    TableDrafts, ContractDrafts, Tasks, TechProcess, TechProcessObjects, ClassTypesList


# Управление словарем на странице конструктора
def save_dict_params(request, message):
    # добавим в пост сведение, что это словарь
    request.POST._mutable = True
    request.POST['is_dict'] = 'true'
    request.POST._mutable = False
    if not 'i_id' in request.GET:
        message = 'Не выбран справочник. Изменения не сохранены<br>'
        message_class = 'text-red'
    else:
        params = json.loads(request.POST['b_save_fields_dict'])
        # Редактируем сохраненные свойства класса
        current_dict = Dictionary.objects.filter(parent_id=request.POST['i_id']).order_by('id')
        dict_header = Dictionary.objects.get(id=int(request.POST['i_id']))
        names_params = [cd.name for cd in current_dict]
        # Валидация данных и приведение типов
        is_valid = True
        all_changes = False
        # Редактируем параметры
        timestamp = datetime.now()
        transact_id = reg_funs.get_transact_id(dict_header.id, 0, 'd')
        for p in params:
            if p['id']:
                try:
                    cp = next(cd for cd in current_dict if cd.id == p['id'])
                except StopIteration:
                    continue
                else:
                    # Регистрационные данные
                    incoming = {'class_id': dict_header.id, 'id': p['id'], 'type': dict_header.formula,
                                'location': dict_header.default}
                    outcoming = incoming.copy()
                    is_change = False
                    if cp.name != p['name']:
                        # проверим измененное имя. Вдруг такое есть в данном класса
                        if p['name'] in names_params:
                            is_valid = False
                            message += 'Название параметра "' + p['name'] + '" уже есть у данного словаря<br>'
                        else:
                            # исправим список имен
                            i = 0
                            while (i < len(names_params)):
                                if names_params[i] == cp.name:
                                    del names_params[i]
                                    break
                                i += 1
                                names_params.append(p['name'])
                            # Регистрируем
                            incoming['name'] = cp.name
                            outcoming['name']  = p['name']
                            # Внесем изменения
                            cp.name = p['name']
                            is_change = True
                    # видимость
                    if cp.is_visible != p['visible']:
                        # Регистрируем
                        incoming['is_visible'] = cp.is_visible
                        outcoming['is_visible'] = p['visible']
                        cp.is_visible = p['visible']
                        is_change = True
                    # Работаем с полем "Умолчание"
                    # Если тип данных булевый - конвертим
                    is_def_change = False
                    if p['type'] == 'bool':
                        if cp.default != p['default']:
                            # Регистрируем
                            incoming['default'] = cp.default
                            outcoming['default'] = str(p['default'])
                            cp.default = str(p['default'])
                            is_change = True
                    elif p['type'] == 'enum':
                        new_enum = p['default'].split('\n')
                        if new_enum != cp.default:
                            # Регистрируем
                            incoming['default'] = cp.default
                            outcoming['default'] = new_enum
                            cp.default = new_enum
                            is_change = True
                    elif p['type'] == 'link':
                        re_find_def = re.match(r'^(?:table|contract)\.\d+\.(\d*)', cp.default)
                        old_default_object_code = re_find_def[1] if re_find_def else ''
                        if old_default_object_code != p['default']:
                            p['default'] = re.match(r'^(?:table|contract)\.\d+\.', cp.default)[0] + p['default']
                            is_valid = interface_procedures.cdl(p['default'])
                            if is_valid:
                                # Регистрируем
                                incoming['default'] = cp.default
                                outcoming['default'] = p['default']
                                cp.default = p['default']
                                is_change = True
                    else:
                        if p['default'] != cp.default:
                            # Регистрируем
                            incoming['default'] = cp.default
                            outcoming['default'] = p['default']
                            cp.default = p['default']
                            is_change = True
                    if is_change:
                        if is_valid:
                            all_changes = True
                            cp.save()
                            # Удалили сведения о словаре из сессии
                            if 'temp_object_manager' in request.session:
                                del request.session['temp_object_manager']
                            message = 'Словарь "' + request.POST['i_name'] + '" ID:' \
                                      + request.GET['i_id'] + ' обновлен<br>'
                            # регистрация
                            reg = {
                                'json_income': incoming,
                                'json': outcoming,
                            }
                            reg_funs.simple_reg(request.user.id, 10, timestamp, transact_id, **reg)
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
                message += 'Не указано имя параметра параметра словаря. Новый параметр не сохранен<br>'
            if p['name'] in names_params:
                is_valid = False
                message += 'Названия параметров словаря не должны повторяться. Новый параметр не сохранен<br>'
            if p['type'] == 'enum':
                p['default'] = p['default'].split('\n')
            elif p['type'] == 'link':
                # Проверка ссылки
                is_valid = interface_procedures.cdl(p['default'])
            # Если все проверки пройдены - создаем параметр
            if is_valid:
                # зададим приоритет
                database_procedures.check_fix_priority(current_dict, 'dict')
                max_priority = 0
                for cd in current_dict:
                    if cd.priority and cd.priority > max_priority:  max_priority = cd.priority
                new_field = Dictionary(name=p['name'], formula=p['type'], parent_id=int(request.POST['i_id']),
                                       default=p['default'], is_visible=str(p['visible']), priority=max_priority + 1)
                new_field.save()
                message += 'Создан новый параметр словаря \"' + request.POST['i_name'] + '\"<br>'
                all_changes = True
                # Удалили сведения о словаре из сессии
                if 'temp_object_manager' in request.session:
                    del request.session['temp_object_manager']
                # Регистрация
                json_new_field = model_to_dict(new_field)
                del json_new_field['priority']
                del json_new_field['parent_id']
                outcoming = {'class_id': dict_header.id, 'location': dict_header.default, 'type': dict_header.formula}
                outcoming.update(json_new_field)
                reg = {
                    'json': outcoming,
                }
                reg_funs.simple_reg(request.user.id, 9, timestamp, transact_id, **reg)
                # пропишем значения по умолчанию во все существующие объекты
                codes = DictObjects.objects.filter(parent_structure_id=int(request.POST['i_id']))\
                    .values('code', 'parent_code').distinct()
                new_records = []
                for c in codes:
                    if new_field.formula == 'enum':
                        val = p['default'][0]
                    elif new_field.formula == 'link':
                        val = re.match(r'^(?:table|contract)\.\d+.(\d*)', p['default'])[1]
                        val = int(val) if val else None
                    else:
                        val = p['default']
                    new_records.append(DictObjects(code=c['code'], parent_code=c['parent_code'], value=val,
                                                   name_id=new_field.id,
                                                   parent_structure_id=new_field.parent_id))
                DictObjects.objects.bulk_create(new_records)
                # Регистрируем изменения в существующих объектах
                outcoming = {'class_id': dict_header.id, 'location': dict_header.default, 'type': dict_header.formula}
                params = DictObjects.objects.filter(parent_structure_id=request.POST['i_id'], name_id=new_field.id)
                for p in params:
                    json_out = outcoming.copy()
                    p = model_to_dict(p)
                    del p['parent_structure']
                    json_out.update(p)
                    reg = {'json': json_out}
                    transact_object = reg_funs.get_transact_id(dict_header.id, p['code'], 'd')
                    reg_funs.simple_reg(request.user.id, 13, timestamp, transact_object, transact_id, **reg)
            else:
                message_class = 'text-red'
        if not all_changes: message += 'Объект не сохранен<br>'
    return message


def delete_dict_param(request, message):
    # добавим в пост сведение, что это словарь
    request.POST._mutable = True
    request.POST['is_dict'] = 'true'
    request.POST._mutable = False
    del_field = Dictionary.objects.get(id=int(request.POST['b_del_field_dict']))
    dict_header = Dictionary.objects.get(id=request.POST['i_id'])
    # Извещение
    message = 'Удален параметр справочника.<br>ID словаря: ' + request.GET['i_id'] \
              + '; Название словаря:' + request.POST['i_name'] + '<br>' \
              + 'ID параметра: ' + request.POST['b_del_field_dict'] + '; Название параметра: ' + del_field.name
    # регистрация операции
    json_del_field = model_to_dict(del_field)
    del json_del_field['priority']
    incoming = {'class_id': dict_header.id, 'location': dict_header.default, 'type': 'dict'}
    incoming.update(json_del_field)
    reg = {'json_income': incoming}
    transact_id = reg_funs.get_transact_id(dict_header.id, 0, 'd')
    timestamp = datetime.now()
    reg_funs.simple_reg(request.user.id, 11, timestamp, transact_id, **reg)
    # удаление
    # связанные поля объектов
    object_fields = DictObjects.objects.filter(name_id=int(request.POST['b_del_field_dict']))
    if object_fields:
        # Регистрация удаления полей объектов
        incoming = {'class_id': dict_header.id, 'location': dict_header.default, 'type': 'dict'}
        for of in object_fields:
            json_inc = incoming.copy()
            json_dict = model_to_dict(of)
            del json_dict['parent_structure']
            json_inc.update(json_dict)
            reg = {'json_income': json_inc}
            transact_code = reg_funs.get_transact_id(dict_header.id, 0, 'd')
            reg_funs.simple_reg(request.user.id, 16, timestamp, transact_code, transact_id, **reg)
        object_fields.delete()
    del_field.delete()  # удалил объект
    # Почистил о нем сведения в сессии
    if 'temp_object_manager' in request.session:
        del request.session['temp_object_manager']
    # пересчет приоритетов
    current_params = Dictionary.objects.filter(parent_id=request.GET['i_id'])
    database_procedures.check_fix_priority(current_params, 'dict')
    return message


# Обновить / создать словарь. Выход Да - были изменения. Нет - не сохранено.
def save_dict(request, parent_code, parent_transact_id=None, timestamp=None):
    is_save = False
    for k, v in request.POST.items():
        if re.match(r'^dict_info.+$', k) and v:
            json_dict = json.loads(v)
            if len(json_dict) <= 1:
                continue
            parent_id = int(re.search(r'^dict_info(?P<id>\d+)$', k).group('id'))
            dict_objects = DictObjects.objects.filter(parent_structure_id=parent_id, parent_code=parent_code).select_related('name')
            dict_header = Dictionary.objects.get(id=parent_id)
            dict_objects_upd = []
            reg_general_data = {'class_id': parent_id, 'type': 'dict', 'location': dict_header.default,
                                'parent_code': parent_code}
            if not timestamp:   timestamp = datetime.now()
            if dict_objects:
                code = dict_objects[0].code
                transact_id = reg_funs.get_transact_id(parent_id, code, 'd')
                for do in dict_objects:
                    if do.value != json_dict[str(do.name_id)]:
                        # Проверка данных типа ссылка
                        if do.name.formula == 'link':
                            str_link = re.match(r'(?:table|contract)\.\d+\.', do.name.default)[0] + json_dict[str(do.name_id)]
                            if not interface_procedures.cdl(str_link):
                                dict_objects_upd = []
                                json_dict = {}
                                break
                        old_value = do.value
                        do.value = json_dict[str(do.name_id)]
                        dict_objects_upd.append({'edited_object': do, 'old_value': old_value})
                    del json_dict[str(do.name_id)]
                if dict_objects_upd:
                    is_save = True
                    DictObjects.objects.bulk_update([dou['edited_object'] for dou in dict_objects_upd], ['value'])
                    # регистрация изменений реквизитов
                    reg_general_data['code'] = code
                    for dou in dict_objects_upd:
                        ic = reg_general_data.copy()
                        ic['id'] = dou['edited_object'].id
                        ic['name'] = dou['edited_object'].name_id
                        ic['value'] = dou['old_value']
                        oc = ic.copy()
                        oc['value'] = dou['edited_object'].value
                        reg = {'json': oc, 'json_income': ic}
                        reg_funs.simple_reg(request.user.id, 15, timestamp,transact_id, parent_transact_id, **reg)

                # Если есть поля, которых пока нет в БД - добавим
                if len(json_dict) > 1:
                    is_save = True
                    del json_dict['id']

                    for k, v in json_dict.items():
                        new_req = DictObjects(value=v, code=code, parent_code=parent_code, name_id=int(k),
                                              parent_structure_id=parent_id)
                        new_req.save()
                        # Регистрация
                        oc = reg_general_data.copy()
                        oc['id'] = new_req.id
                        oc['name'] = new_req.name_id
                        oc['value'] = new_req.value
                        reg = {'json': oc}
                        reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, parent_transact_id, **reg)
            # Новый словарь
            else:
                code = database_funs.get_code(parent_id, 'dict')
                transact_id = reg_funs.get_transact_id(parent_id, code, 'd')
                # регистрация создания словаря
                outcoming = reg_general_data.copy()
                outcoming['code'] = code
                reg = {'json': outcoming}
                reg_funs.simple_reg(request.user.id, 5, timestamp, transact_id, parent_transact_id, **reg)
                for kk, vv in json_dict.items():
                    if kk != 'id':
                        new_dict_rec = DictObjects(name_id=int(kk), parent_code=parent_code, parent_structure_id=parent_id,
                                                   code=code, value=vv)
                        dict_objects_upd.append(new_dict_rec)
                if dict_objects_upd:
                    is_save = True
                    DictObjects.objects.bulk_create(dict_objects_upd)
                    new_dict_params = DictObjects.objects.filter(code=code, parent_code=parent_code,
                                                                 parent_structure_id=parent_id)
                    for ndp in new_dict_params:
                        oc = outcoming.copy()
                        ndp = model_to_dict(ndp)
                        del ndp['parent_structure']
                        oc.update(ndp)
                        reg = {'json': oc}
                        reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, parent_transact_id, **reg)
    return is_save


# Переброска: гет - сессия - пост.
# вход - реквест, именя исключений - список. Имя исключения - это название параметра, который не будет переброшен в пост.
# Выход - либо ответ редиректа или ничего
def get_to_post(request, names_ext):
    # Перебросим в пост параметры из сесси
    if 'old_GET' in request.session:
        request.POST._mutable = True
        for k, v in request.session['old_GET'].items():
            request.POST[k] = v
        del request.session['old_GET']
        request.POST._mutable = False
    else:
        # Перебросим все параметры из гет в сессию для дальнейшей переброски в пост, кроме айди класса
        for k, v in request.GET.items():
            if k not in names_ext:
                if not 'old_GET' in request.session:
                    request.session['old_GET'] = {}
                request.session['old_GET'][k] = v
            elif not k in request.POST:
                request.POST._mutable = True
                request.POST[k] = v
                request.POST._mutable = False
        # Если был переброшен из гет хотя бы 1 параметр, значит перебрасывает и из пост и редиректим
        if 'old_GET' in request.session:
            # Перебросим все параметры из пост в историю. Сохраняем
            for k, v in request.POST.items():
                if not 'old_GET' in request.session:
                    request.session['old_GET'] = {}
                request.session['old_GET'][k] = v
            # редиректим
            url = request.path
            is_first = True
            for ne in names_ext:
                if ne in request.POST:
                    if is_first:
                        sign = '?'
                    else:
                        sign = '&'
                    is_first = False
                    url += sign + ne + '=' + request.POST[ne]
                elif names_ext in request.GET:
                    if is_first:
                        sign = '?'
                    else:
                        sign = '&'
                    url += sign + ne + '=' + request.GET[ne]
            return redirect(url)
    return None


# скачать файл
def download_file(request, is_contract=False):
    def get_file(file):
        fp = open(file, "rb")
        response = HttpResponse(fp.read(), content_type='application/adminupload', charset='utf-8')
        response['Content-Disposition'] = 'attachment; filename={}'.format(iri_to_uri(file_name[14:]))
        fp.close()
        return response
    # Найдем
    id = request.POST['b_save_file']
    file_name = request.POST['i_filename_' + id]
    files_date = file_name[4:8] + '-' + file_name[2:4] + '-' + file_name[:2]
    class_folder = 'contract_' if is_contract else 'table_'
    file = os.path.join('database_files_history', class_folder + request.GET['class_id'], files_date, file_name)
    if os.path.exists(file):
        return get_file(file)
    else:
        file = os.path.join('database_files_draft', class_folder + request.GET['class_id'], files_date, file_name)
        if os.path.exists(file):
            return get_file(file)
        else:
            return None


# Удалить файл из БД
def delete_file(request, class_params, is_contract=False):
    current_header = next(cp for cp in class_params if cp['id'] == int(request.POST['b_del_file']))
    if current_header['is_required']:
        return False
    else:
        class_manager = Contracts.objects if is_contract else Designer.objects
        current_class = class_manager.get(id=current_header['parent_id'])
        manager = ContractCells.objects if is_contract else Objects.objects
        del_file = manager.get(code=request.POST['i_code'], parent_structure_id=current_header['parent_id'],
                                       name_id=current_header['id'])
        # Регистрация удаления
        location = 'contract' if is_contract else 'table'
        incoming = {'class_id': current_class.id, 'location': location, 'type': current_class.formula,
                    'code': del_file.code, 'id': del_file.id, 'name': del_file.name_id, 'value': del_file.value}
        outcoming = incoming.copy()
        outcoming['value'] = ''
        reg = {'json_income': incoming, 'json': outcoming}
        transact_id = reg_funs.get_transact_id(current_header['parent_id'], request.POST['i_code'], location[0])
        timestamp = datetime.now()
        reg_funs.simple_reg(request.user.id, 15, timestamp, transact_id, **reg)
        del_file.value = ''
        del_file.save()
        return True


# Создать черновик
def make_graft(request, code, is_contract=False):
    message = ''
    class_id = int(request.GET['class_id'])

    draft = {'parent_structure': class_id, 'code': code, 'branch': None}
    # Если черновик контракта, то создадим пустое поле "Дата и время записи"
    if is_contract:
        datetime_record_head = Contracts.objects.get(parent_id=class_id, name='Дата и время записи')
        if code:
            datetime_record = ContractCells.objects.filter(parent_structure_id=class_id, code=code,
                                                           name__id=datetime_record_head.id).get()
            val = datetime_record.value
        else:
            val = None
        draft[datetime_record_head.id] = {'value': val}
    if 'i_branch' in request.POST and request.POST['i_branch']:
        draft['branch'] = int(request.POST['i_branch'])
    for k, v in request.POST.items():
        try:
            field_id = int(re.search(r'^(ta|i|i_datetime|i_link|i_float|s_enum|chb|i_date|i_filename|s_alias)_(?P<id>\d+)$',
                                     k).group('id'))
        except AttributeError:
            field_id = re.match(r'dict_info(\d+)', k)
            if field_id:
                field_id = 'dict_' + field_id[1]
            else:
                continue
        if re.match(r'dict_info', k):
            draft[field_id] = interface_procedures.convert_draft_dict(k, v)
        else:
            # Если есть имя файла, но нет файла в загрузчике, то скопируем файл из хранилища истории в черновики
            if re.match(r'i_filename_', k) and 'i_file_' + str(field_id) in request.POST and \
                    request.POST['i_filename_' + str(field_id)]:
                location = 'contract' if is_contract else 'table'
                files_funs.cffdth(v, request.GET['class_id'], reverse=True, location=location)
            draft[field_id] = {'value': interface_procedures.convert_draft_dict(k, v)}
    # Загрузим файлы в черновик
    for k, v in request.FILES.items():
        res, filename, msg = upload_file(request, k, v, is_contract, root_folder='database_files_draft')
        if res == 'o':
            draft[int(k[7:])] = {'value': filename}
        else:
            draft[int(k[7:])] = {'value': ''}
            message = msg
    # Сохраним черновик
    manager = ContractDrafts if is_contract else TableDrafts
    manager(data=draft, timestamp=datetime.now(), user_id=request.user.id).save()
    # Пересчитаем соответствующее дерево и меню
    session_funs.update_draft_tree(request, is_contract)
    return draft, message


# Редактировать черновик
def draft_edit(request, draft_id, is_contract=False):
    message = ''
    draft_manager = ContractDrafts.objects if is_contract else TableDrafts.objects
    draft = draft_manager.get(id=draft_id)
    is_change = False
    # проверим, изменилась ли ветка
    if 'i_branch' in request.POST:
        new_branch = int(request.POST['i_branch']) if request.POST['i_branch'] else None
        if new_branch != draft.data['branch']:
            draft.data['branch'] = new_branch
            is_change = True
    for k, v in request.POST.items():
        is_dict = False
        try:
            field_id = re.search(r'^(ta|i|i_datetime|i_link|i_float|s_enum|chb|i_date|i_filename|s_alias)_(?P<id>\d+)$',
                                 k).group('id')
        except AttributeError:
            field_id = re.match(r'dict_info(\d+)', k)
            if field_id:
                field_id = 'dict_' + field_id[1]
                is_dict = True
            elif re.match(r'i_code', k):
                if not v:
                    draft.data['code'] = None
                    is_change = True
                continue
            else:
                continue
        val = interface_procedures.convert_draft_dict(k, v)
        if is_dict:
            old_val = {}
            if draft.data[field_id]:
                for kk in draft.data[field_id]:
                    old_val[int(kk)] = draft.data[field_id][kk]
        else:
            old_val = draft.data[field_id]['value']
        if val != old_val:
            if is_dict:
                draft.data[field_id] = val
                is_change = True
            else:
                # Если был изменен файл
                if re.match(r'i_filename', k):
                    # загрузим файл на сервер
                    file_key = 'i_file_' + str(field_id)
                    res, val, msg = upload_file(request, file_key, v, is_contract, root_folder='database_files_draft')
                    if res == 'o':
                        # физически удалим старый файл
                        if old_val:
                            app.functions.files_funs.delete_draft_file(old_val, request.GET['class_id'], is_contract)
                        draft.data[field_id]['value'] = val
                        is_change = True
                    else:
                        message += msg
                else:
                    draft.data[field_id]['value'] = val
                    is_change = True
    if is_change:
        draft.timestamp = datetime.now()
        draft.save()
        message += 'Черновик изменен'
    else:   message += 'Вы не внесли изменений. Черновик не был сохранен'
    return is_change, message


# Валидация объекта. Вход - реквест. Выход - да/нет, сообщение
def object_validation(class_params, request, current_class, objects=None, **params):
    message = ''
    is_valid = True
    code = int(request.POST['i_code']) if request.POST['i_code'] else 0
    object = {'code': code, 'parent_structure': current_class.id}
    # Если класс подчинен дереву - проверим, является ли дерево правильным
    if 'i_branch' in request.POST:
        is_valid, branch, message = interface_procedures.valid_branch(request, current_class.parent_id)

    if not 'csrt_token' in request.session['temp_object_manager']:
        request.session['temp_object_manager']['pool_post'] = dict()
    pool_post = request.session['temp_object_manager']['pool_post']
    # Корректность вводимых данных
    def ctf(cf, val):  # ctf - check the field
        msg = ''; is_valid = True
        # 1. Обязательные поля
        if cf['formula'] != 'file' and cf['is_required'] and not val:
            is_valid = False
            msg += ' Не заполнено обязательное поле \"' + cf['name'] + '\"<br>'
        # 2. Проверяем только заполненные поля. Пустые игнорим
        elif val:
            # 3. Проверка числового поля
            if cf['formula'] == 'float':
                try:
                    val = float(val)
                except ValueError:
                    is_valid = False
                    msg += ' Некорректно указано значение поля \"' + cf['name'] + '\"<br>'
            # 4. Проверка ссылочного поля
            elif cf['formula'] == 'link':
                try:
                    val = int(val)
                except ValueError:
                    is_valid = False
                    msg += ' Некорректно указано значение поля \"' + cf['name'] + '\"<br>'
                else:
                    if not database_funs.check_object(int(val), cf['value']):
                        is_valid = False
                        msg += ' Некорректно указано значение поля \"' + cf['name'] + '\".'
            # 5. Проверка формата ДатаВремя
            elif cf['formula'] == 'datetime':
                try:
                    datetime.strptime(val, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try:
                        datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        is_valid = False
                        msg += ' Некорректно указано значение поля \"' + current_field['name'] + '\".'
            # Добавление параметра в словарь
            object[field_id] = {}
            object[field_id]['value'] = val
        return is_valid, msg

    is_double_save = True  # защита от повторного сохранения

    for k, v in request.POST.items():
        # защита от повторного сохранения
        if k == 'csrfmiddlewaretoken':
            if not 'csrf_token' in request.session['temp_object_manager'] or v != request.session['temp_object_manager']['csrf_token']:
                request.session['temp_object_manager']['csrf_token'] = v
                is_double_save = False
                break
            continue
        # валидация данных
        try:
            field_id = int(re.search(r'^(ta|i|i_datetime|i_link|i_float|s_enum|chb|i_date)_(?P<id>\d+)$',
                                     k).group('id'))
        except AttributeError:
            continue
        else:
            current_field = next(cc for cc in class_params if cc['id'] == field_id)
            is_valid, msg = ctf(current_field, v)
            if not is_valid:
                message += msg
            # Проверим делэйное значение, если делэй задан
            if current_field['delay']:
                key_delay_date = k + '_delay_datetime'
                if key_delay_date in request.POST and request.POST[key_delay_date]:
                    is_valid, msg = ctf(current_field, request.POST[k + '_delay'])
    if is_double_save:
        return False, ''
    dict_keys_request = dict_keys = {'string': 'ta_', 'link': 'i_link_', 'float': 'i_float_', 'datetime': 'i_datetime_',
                 'date': 'i_date_', 'bool': 'chb_', 'const': 's_alias_', 'enum': 's_enum_'}
    # Проверка обязательных параметров
    for cp in class_params:
        if cp['formula'] == 'file' and cp['is_required']:
            file_key = 'i_filename_' + str(cp['id'])
            if not (file_key in request.POST and request.POST[file_key]):
                is_valid = False
                message += 'Не заполнено обязательное поле - "' + cp['name'] + '"<br>'
        # Проверка корректности формул
        elif cp['formula'] == 'eval' and cp['is_required']:
            convert_funs.deep_formula(cp, [object, ], request.user.id)
            result = object[cp['id']]['value']
            if type(result) is str and result[:6].lower() == 'ошибка':
                is_valid = False
                message += 'Формула в поле "' + cp['name'] + '" ID: ' + str(cp['id']) + ' задана некорректно<br>'
        elif cp['is_required']:
            my_key = dict_keys[cp['formula']] + str(cp['id'])
            my_val = request.POST[my_key]
            if not my_val:
                if code:
                    try:
                        obj = next(o for o in objects if o.name_id == cp['id'])
                    except StopIteration:
                        is_valid = False
                        message += 'Не заполнено обязательное поле - "' + cp['name'] + '"<br>'
                    else:
                        if not cp['formula'] == 'bool' and not obj.value:
                            is_valid = False
                            message += 'Не заполнено обязательное поле - "' + cp['name'] + '"<br>'
                else:
                    is_valid = False
                    message += 'Не заполнено обязательное поле - "' + cp['name'] + '"<br>'


    return is_valid, message


# Сохранение объекта
# Опциональные параметры: source = [draft]
def save_object(request, class_id, code, current_class, class_params, **params):
    # Обработаем опциональные параметры
    if not 'source' in params:  params['source'] = None
    is_saved = False
    transact_id = None
    timestamp = datetime.now()
    message_class = ''

    # редактируем
    if code:
        objects = Objects.objects.filter(code=code, parent_structure_id=class_id).select_related('name')
        is_valid, message = object_validation(class_params, request, current_class, objects)
        if is_valid:

            json_edit_objects = []
            new_objects = []
            # были ли внесены изменения
            # проверим ветку, если она есть
            if 'i_branch' in request.POST:
                branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
                try:
                    o = next(o for o in objects if o.name.name == 'parent_branch')
                except StopIteration:
                    parent_branch = Designer.objects.get(formula='float', parent_id=class_id, name='parent_branch')
                    o = Objects(name_id=parent_branch.id, parent_structure_id=class_id, code=code, value=branch_code)
                if o.id:
                    if o.value != branch_code:
                        old_value = o.value
                        o.value = branch_code
                        json_edit_objects.append({'old_value': old_value, 'new_obj': o})
                else:
                    new_objects.append(o)
            # проверим остальные параметры объекта
            for k, v in request.POST.items():
                try:
                    field_id = int(re.search(r'^(ta|chb|i_datetime|i_date|i_link|i_float|s_enum|s_alias|i_filename)'
                                             r'_(?P<id>\d+)$', k).group('id'))
                except AttributeError:
                    continue
                else:
                    try:
                        o = next(o for o in objects if o.name_id == field_id)
                    except StopIteration:
                        o = Objects(name_id=field_id, parent_structure_id=class_id,
                                    code=code, value=None)
                    v = view_procedures.convert_in_json(k, v)  # Конвертация формата
                    delay_value, date_delay_value = interface_procedures.check_delay_value(request, field_id, k)  # Проверим делэйные значения
                    json_edit_dict = {}
                    if o.value != v or date_delay_value:
                        current_param = next(cp for cp in class_params if cp['id'] == field_id)
                        is_change = False
                        is_handler = bool(current_param['delay_settings']['handler'] and current_param['delay'])
                        if o.value != v and not is_handler:
                            is_change = True
                            # Если тип данных файл - попробуем загрузить его
                            if re.match(r'i_filename_\d+$', k):
                                if v:
                                    res, v, msg = upload_file(request, 'i_file_' + str(field_id), v)
                                    if res == 'f':
                                        message += msg
                                        message_class = 'text-red'
                                        continue
                                    # Если файл не был загружен, попробуем загрузить его из черновика
                                    elif res == 'm' and not cffdth(v, request.GET['class_id']):
                                        message += 'Произошла ошибка во время загрузки файла<br>'
                                        message_class = 'text-red'
                                        continue
                            old_value = o.value
                            o.value = v
                            json_edit_dict['old_value'] = old_value
                        if date_delay_value:
                            # если тип данных - файл - попробуем загрузить его
                            if re.match(r'^i_filename_.\d+$', k):
                                try:
                                    v_file = request.POST['i_filename_' + str(field_id) + '_delay']
                                except KeyError:
                                    continue
                                if v_file:
                                    res, delay_value, msg = upload_file(request, 'i_file_' + str(field_id) + '_delay', v_file)
                                    if res == 'f':
                                        message += msg
                                        message_class = 'text-red'
                                        continue
                                    # Если файл не был загружен, попробуем загрузить его из черновика
                                    elif res == 'm' and not cffdth(v_file, request.GET['class_id']):
                                        message += 'Произошла ошибка во время загрузки файла<br>'
                                        message_class = 'text-red'
                                        continue
                            new_delay = {'date_update': date_delay_value, 'value': delay_value, 'approve': False}
                            robot_approve = True
                            if current_param['delay']:
                                if not current_param['delay_settings']['handler']:
                                    new_delay['approve'] = True
                                elif not type(current_param['delay_settings']['handler']) is int:
                                    # Ответственный-робот говорит свое слово
                                    robot_approve = interface_procedures.rohatiw(request.POST, class_id, code, current_param,
                                                                                 class_params, objects, request.user.id)
                                    if robot_approve:
                                        new_delay['approve'] = True
                            if robot_approve:
                                if o.delay:
                                    json_edit_dict['old_delay'] = o.delay.copy()
                                    o.delay.append(new_delay)
                                else:
                                    json_edit_dict['old_delay'] = []
                                    o.delay = [new_delay]
                            else:
                                message += 'Ответственный (робот) отклонил заявку на отложенное значение реквизита ID: ' \
                                        + str(current_param['id']) + '<br>'
                            is_change = is_change or robot_approve
                        if is_change:
                            json_edit_dict['new_obj'] = o
                            if o.id:
                                json_edit_objects.append(json_edit_dict)
                            else:
                                new_objects.append(o)

            # Если изменения были, то внесем их
            incoming = {'class_id': class_id, 'code': code, 'location': 'table', 'type': current_class.formula}
            if json_edit_objects:
                is_saved = True
                # Сохранение редактирования
                edit_values = [jeo['new_obj'] for jeo in json_edit_objects if 'old_value' in jeo]
                Objects.objects.bulk_update(edit_values, ['value'])
                edit_delays = [jeo['new_obj'] for jeo in json_edit_objects if 'old_delay' in jeo]
                Objects.objects.bulk_update(edit_delays, ['delay'])
                transact_id = reg_funs.get_transact_id(class_id, code)
                # регистрация редактирования
                for jeo in json_edit_objects:
                    if 'old_value' in jeo:
                        ic = incoming.copy()
                        ic['id'] = jeo['new_obj'].id
                        ic['name'] = jeo['new_obj'].name_id
                        ic['value'] = jeo['old_value']
                        oc = ic.copy()
                        oc['value'] = jeo['new_obj'].value
                        reg = {'json_income': ic, 'json': oc}
                        reg_funs.simple_reg(request.user.id, 15, timestamp, transact_id, **reg)
                    if 'old_delay' in jeo:
                        icd = incoming.copy()
                        icd['id'] = jeo['new_obj'].id
                        icd['name'] = jeo['new_obj'].name_id
                        icd['delay'] = jeo['old_delay']
                        delay = jeo['new_obj'].delay[-1]
                        date_update = datetime.strptime(delay['date_update'], '%Y-%m-%dT%H:%M')
                        delay_ppa = date_update < timestamp
                        if delay_ppa:
                            delay['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                            jeo['new_obj'].save()
                            interface_procedures.rhwpd('table', current_class.formula, date_update, delay, jeo['new_obj'],
                                                       request.user.id, transact_id)
                        else:
                            ocd = icd.copy()
                            ocd['delay'] = jeo['new_obj'].delay
                            reg = {'json_income': icd, 'json': ocd}
                            reg_funs.simple_reg(request.user.id, 22, timestamp, transact_id, **reg)
                        # Создаем / регистрируем таск
                        current_param = next(cp for cp in class_params if cp['id'] == jeo['new_obj'].name_id)
                        interface_procedures.make_task_4_delay(current_param, jeo['new_obj'], 't', request.user,
                                                               timestamp, delay_ppa, transact_id)

            if new_objects:
                is_saved = True
                if not transact_id: transact_id = reg_funs.get_transact_id(class_id, code)
                Objects.objects.bulk_create(new_objects)
                for no in new_objects:
                    # Регистрация создания реквизитов
                    new_req = Objects.objects.get(parent_structure_id=class_id, name_id=no.name_id, code=no.code)
                    oc = incoming.copy()
                    oc['id'] = new_req.id
                    oc['name'] = new_req.name_id
                    oc['value'] = new_req.value
                    reg = {'json': oc}
                    reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                    if new_req.delay:
                        oc['delay'] = new_req.delay
                        date_update = datetime.strptime(new_req.delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
                        delay_ppa = date_update < timestamp
                        if delay_ppa:
                            new_req.delay[-1]['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                            ts = date_update
                            new_req.save()
                        else:
                            ts = timestamp
                        del oc['value']
                        reg = {'json': oc}
                        reg_funs.simple_reg(request.user.id, 22, ts, transact_id, **reg)
                        # Создаем таск
                        current_param = next(cp for cp in class_params if cp['id'] == no.name_id)
                        interface_procedures.make_task_4_delay(current_param, new_req, 't', request.user, timestamp, delay_ppa, transact_id)


        elif message:
            message_class = 'text-red'
            message += '<br>Объект не сохранен'
            if params['source'] != 'draft' and current_class.formula == 'table':
                draft = make_graft(request, code)[0]
    # Создаем новый
    else:
        is_valid, message = object_validation(class_params, request, current_class)
        if is_valid:
            is_saved = True
            code = database_funs.get_code(int(request.GET['class_id']), 'table')
            transact_id = app.functions.reg_funs.get_transact_id(class_id, code)
            # регистрация создания объекта
            outcoming = {'class_id': class_id, 'location': 'table', 'type': current_class.formula, 'code': code}
            reg = {'json': outcoming}
            reg_funs.simple_reg(request.user.id, 5, timestamp, transact_id, **reg)
            objects = []
            # Сохраним ветку при ее наличии
            if 'i_branch' in request.POST:
                branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
                parent_branch = Designer.objects.get(formula='float', parent_id=class_id, name='parent_branch')
                objects.append(Objects(code=code, parent_structure_id=class_id, name_id=parent_branch.id, value=branch_code))
            # Сохраняем остальные реквизиты
            for k, v in request.POST.items():
                try:
                    field_id = int(re.search(r'^(ta|i_datetime|i_link|i_float|chb|'
                                             r'i_date|s_enum|s_alias|i_filename)_(?P<id>\d+)$', k).group('id'))
                except AttributeError:
                    continue
                delay_value, date_delay_value = interface_procedures.check_delay_value(request, field_id, k)  # Проверим делэйные значения
                if v or date_delay_value:
                    # Конвертация формата
                    v = view_procedures.convert_in_json(k, v)
                    current_param = next(cp for cp in class_params if cp['id'] == field_id)
                    is_handler = bool(current_param['delay'] and current_param['delay_settings']['handler'])
                    new_prop = Objects(code=code, parent_structure_id=class_id, name_id=field_id)
                    if v:
                        # Если реквизит типа "файл" - предварительно загрузим его
                        if re.match(r'^i_filename_.\d+$', k):
                            res, v, msg = upload_file(request, 'i_file_' + str(field_id), v)
                            if res == 'f':
                                message += msg
                                message_class = 'text-red'
                                continue
                            # Если файл не был загружен, попробуем загрузить его из черновика
                            elif res == 'm' and not cffdth(v, request.GET['class_id']):
                                message += 'Произошла ошибка во время загрузки файла<br>'
                                message_class = 'text-red'
                                continue
                    new_prop.value = v
                    if date_delay_value:
                        # Если реквизит типа "файл" - предварительно загрузим его
                        if re.match(r'^i_filename_.\d+$', k):
                            try:
                                v_file = request.POST[k + '_delay']
                            except KeyError:
                                continue
                            if v_file:
                                res, delay_value, msg = upload_file(request, 'i_file_' + str(field_id) + '_delay', v_file)
                                if res == 'f':
                                    message += msg
                                    message_class = 'text-red'
                                    continue
                                # Если файл не был загружен, попробуем загрузить его из черновика
                                elif res == 'm' and not cffdth(v_file, request.GET['class_id']):
                                    message += 'Произошла ошибка во время загрузки файла<br>'
                                    message_class = 'text-red'
                                    continue
                        new_delay = [{'date_update': date_delay_value, 'value': delay_value, 'approve': False}]
                        if current_param['delay']:
                            if not current_param['delay_settings']['handler']:
                                new_delay[0]['approve'] = True
                            elif not type(current_param['delay_settings']['handler']) is int:
                                # Ответственный робот говорит свое слово
                                approve = interface_procedures.rohatiw(request.POST, class_id, code, current_param,
                                                                       class_params, objects, request.user.id)
                                if not approve:
                                    message += 'Ответственный (робот) отклонил заявку на отложенное значение реквизита ID: ' \
                                               + str(current_param['id']) + '<br>'
                                    new_delay = []
                                else:
                                    new_delay[0]['approve'] = True
                        new_prop.delay = new_delay
                    objects.append(new_prop)
            Objects.objects.bulk_create(objects)
            message += 'Объект успешно создан. Код объекта: ' + str(code) + '<br>'
            new_object_params = Objects.objects.filter(code=code, parent_structure_id=int(request.GET['class_id'])).select_related('name')
            for nop in new_object_params:
                outcom = model_to_dict(nop)
                del outcom['code']
                del outcom['parent_structure']
                delay = None
                if nop.delay:
                    delay = outcom['delay']
                del outcom['delay']
                outcom.update(outcoming)
                reg = {'json': outcom}
                reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                if nop.delay:
                    del outcom['value']
                    date_update = datetime.strptime(delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
                    delay_ppa = date_update < timestamp
                    if delay_ppa:
                        delay[-1]['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                        ts = date_update
                        nop.save()
                    else:
                        ts = timestamp
                    outcom['delay'] = delay
                    reg = {'json': outcom}
                    reg_funs.simple_reg(request.user.id, 22, ts, transact_id, **reg)

                    current_param = next(cp for cp in class_params if cp['id'] == nop.name_id)
                    interface_procedures.make_task_4_delay(current_param, nop, 't', request.user,
                                                           timestamp, delay_ppa, transact_id)
            # Удаляем информацию о странице из реквеста
            request.POST._mutable = True
            del request.POST['page']
            request.POST._mutable = False
        else:
            code = None
            message_class = 'text-red'
            message += 'Объект не сохранен'
            if params['source'] != 'draft':
                draft = make_graft(request, None)[0]

    if code and is_valid:
        # Сохраним словарь
        is_saved_dict = save_dict(request, code, transact_id, timestamp)
        is_saved = is_saved or is_saved_dict
    if is_saved:
        message += 'Объект сохранен<br>'
    elif is_valid and not is_saved and not message:
        message += 'Вы ничего не изменили. Объект не сохранен<br>'

    return is_saved, message, message_class, code, transact_id, timestamp


# stpirt = save_tree_params_is_right_tree
def stpirt(prop, new_val, user_id, timestamp, is_contract=False):
    if prop.value != new_val:
        location = 'contract' if is_contract else 'table'
        incoming = {'id': prop.id, 'location': location, 'type': 'tree', 'value': prop.value,
                    'class_id': prop.parent_id}
        outcoming = {'id': prop.id, 'location': location, 'type': 'tree', 'value': new_val,
                     'class_id': prop.parent_id}
        prop.value = new_val
        prop.save()
        # регистрация
        reg = {
            'json_income': incoming,
            'json': outcoming
        }
        transact_id = reg_funs.get_transact_id(prop.parent_id, 0, 'c')
        reg_funs.simple_reg(user_id, 10, timestamp, transact_id, **reg)
        is_saved = True
    else:
        is_saved = False
    return is_saved


def check_branch(request, tree_id, is_contract=False):
    branch_code = int(request.POST['branch_code'])
    tree = request.session['temp_object_manager']['tree']
    branch = tree_funs.find_branch(tree, 'code', branch_code)
    request.session['temp_object_manager']['active_branch'] = branch
    object_manager = ContractCells.objects if is_contract else Objects.objects

    if branch:
        if branch_code == 0:
            pass
        elif branch['opened']:
            branch['opened'] = False
        else:
            branch['opened'] = True
            if 'children' in branch and not branch['children']:
                branch['children'] = []
                name_branch = object_manager.filter(parent_structure_id=tree_id, name__name='name',
                                                     code=OuterRef('code'))
                children_branch = object_manager.filter(parent_structure_id=tree_id, name__name='parent',
                                                         value=branch_code) \
                    .annotate(name_branch=Subquery(name_branch.values('value')[:1]))
                for cb in children_branch:
                    child_branch = {'code': cb.code, 'name': cb.name_branch, 'opened': False, 'parent': branch_code}
                    sub_children = object_manager.filter(parent_structure_id=tree_id, name__name='parent',
                                                          value=cb.code)
                    if sub_children:
                        child_branch['children'] = []
                    branch['children'].append(child_branch)
                # Забросим свойства детям
                branch['children'] = tree_funs.get_branch_props(branch['children'], tree_id,
                                                                request.session['temp_object_manager']['tree_headers'],
                                                                request.user.id, is_contract, child_class=int(request.GET['class_id']))
    return branch_code, tree, branch


def branch_objects_codes(branch, class_id, is_contract=False):
    class_manager = Contracts.objects if is_contract else Designer.objects
    object_manager = ContractCells.objects if is_contract else Objects.objects
    parent_branch = class_manager.get(parent_id=class_id, name='parent_branch')
    if not branch or branch['code'] == 0:
        non_codes = object_manager.filter(parent_structure_id=class_id, name_id=parent_branch.id, value__isnull=False)\
        .values('code')
        codes = object_manager.filter(parent_structure_id=class_id).exclude(code__in=Subquery(non_codes))\
            .values('code').distinct()
    else:
        codes = object_manager.filter(parent_structure_id=class_id, name_id=parent_branch.id, value=branch['code']).values('code')
    return codes.order_by('-code')


def save_contract_object(request, code, current_class, class_params, **params):
    # Обработаем опциональные параметры
    if not 'source' in params:  params['source'] = None
    is_saved = False
    transact_id = None
    timestamp = datetime.now()
    message = ''
    message_class = ''
    is_valid = True
    # Проверим базовые бизнес-правила для техпроцессов
    change_tps = False
    my_tps = None
    tps_all = {}
    tps = request.session['temp_object_manager']['tps']
    control_fields = [t['cf'] for t in tps]
    system_data_id = next(cp['id'] for cp in class_params if cp['name'] == 'system_data') if current_class.formula == 'contract' else None

    # Техпроцессы. Валидация, проверка изменений
    def check_changes_tps():
        tps_all = {}
        message = ''
        tps_chng = False
        tps_valid = True
        def make_stages(list_stage):
            output_dict = {}
            for ls in list_stage:
                val = {'fact': 0, 'delay': []}
                output_dict[ls] = val
            return output_dict
        for tp in tps:
            dictp = {}

            # Формируем старые стадии
            if code:
                old_stages = list(TechProcessObjects.objects.filter(parent_structure_id=tp['id'], parent_code=code)
                                  .values('name_id', 'value'))
                old_stages_dict = {}
                old_stages_ids = []
                if old_stages:
                    for os in old_stages:
                        old_stages_dict[os['name_id']] = os['value']
                        old_stages_ids.append(os['name_id'])
                else:
                    # Если по какой-то причине потеряны данные о техпроцессе - заполним его так: первая стадия = КП. Остальные пустые
                    first_stage = tp['stages'][0]
                    try:
                        cf_old = ContractCells.objects.get(parent_structure_id=current_class.id, code=code,
                                                           name_id=tp['cf'])
                    except ObjectDoesNotExist:
                        cf_old_val = 0
                    else:
                        cf_old_val = cf_old.value
                    old_stages_dict[first_stage['id']] = {'fact': cf_old_val, 'delay': []}
                    old_stages_ids.append(first_stage['id'])
                absent_stages = [s['id'] for s in tp['stages'] if s['id'] not in old_stages_ids]
                old_stages_dict.update(make_stages(absent_stages))
            else:
                old_stages_dict = make_stages([s['id'] for s in tp['stages']])
            dictp['old_stages'] = old_stages_dict
            # формируем новые стадии
            new_stages = {}
            stages_ids = ['i_stage_' + str(s['id']) for s in tp['stages']]
            for k, v in request.POST.items():
                if k in stages_ids:
                    new_stages[int(k[8:])] = {'value': float(v) if v else 0}
            dictp['new_stages'] = new_stages
            dictp['changed'] = False
            for k, old_v in dictp['old_stages'].items():
                old_value = old_v['fact'] + sum([od['value'] for od in old_v['delay']])
                if old_value != dictp['new_stages'][k]['value']:
                    dictp['changed'] = True
                    tps_chng = True
                    dictp['new_stages'][k]['delta'] = dictp['new_stages'][k]['value'] - old_value
                else:
                    dictp['new_stages'][k]['delta'] = 0

            tps_all[tp['id']] = dictp
            # Вычисляем базовое ТП - все стадии = КП
            if dictp['changed']:
                cf_key = 'i_float_' + str(tp['cf'])
                cf_fact = float(request.POST[cf_key]) if request.POST[cf_key] else 0
                # cf_ddt_key = 'i_datetime_' + str(tp['cf']) + '_delay_datetime'
                # if cf_ddt_key in request.POST and request.POST[cf_ddt_key] and request.POST[cf_key + + '_delay']:
                #     cf_delay = float(request.POST[cf_key + '_delay'])
                # else:
                #     cf_delay = 0
                # cf_val = cf_fact + cf_delay
                if cf_fact != sum([v['value'] for v in dictp['new_stages'].values()]):
                    tps_valid = False
                    message += 'Изменения в техпроцессе ' + str(tp['id']) + \
                               ' некорректны. Сумма всех этапов должна рваняться контрольному полю<br>'
                else:
                # Калькулятор маршрутизации
                    is_first_stage = True
                    cf_old_val = sum(ov['fact'] + sum(d['value'] for d in ov['delay']) for ov in dictp['old_stages'].values())
                    cf_delta = cf_fact - cf_old_val
                    dictp['cf_delta'] = cf_delta
                    for k, v in dictp['new_stages'].items():
                        if is_first_stage:
                            is_first_stage = False
                            if cf_delta:
                                v['valid_delta'] = True
                                v['delta'] -= cf_delta
                                continue
                        if not v['delta'] or ('valid_delta' in v and v['valid_delta']):
                            v['valid_delta'] = True
                            continue
                        if v['delta'] < 0:
                            partners = next(s['value']['children'] for s in tp['stages'] if s['id'] == k)
                        else:
                            partners = [s['id'] for s in tp['stages'] if k in s['value']['children']]
                        partners_deltas = sum(dictp['new_stages'][p]['delta'] for p in partners)
                        if partners_deltas * -1 == v['delta']:
                            v['valid_delta'] = True
                            for p in partners:
                                dictp['new_stages'][p]['valid_delta'] = True
                        else:
                            dictp['new_stages'][k]['valid_delta'] = False
                    all_delta_valid = True
                    for v in dictp['new_stages'].values():
                        all_delta_valid = all_delta_valid and v['valid_delta']
                    if not all_delta_valid:
                        tps_valid = False
                        message += 'Изменения в техпроцессе ' + str(tp['id']) + ' некорректны. Имеются нарушения целостности данных<br>'
        return tps_all, tps_chng, tps_valid, message

    # редактируем
    if request.POST['i_code']:
        if is_valid:
            objects = ContractCells.objects.filter(code=code, parent_structure_id=current_class.id).select_related('name')
            is_valid, message = contract_validation(class_params, current_class, request, objects)
            tps_all, change_tps, tps_valid, msg = check_changes_tps()
            is_valid = is_valid and tps_valid

            if msg:
                message += msg
        edit_objects = []
        new_objects = []
        if is_valid:
            edit_dict = {}
            # проверим ветку, если она есть
            if 'i_branch' in request.POST:
                branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
                try:
                    o = next(o for o in objects if o.name.name == 'parent_branch')
                except StopIteration:
                    parent_branch = Contracts.objects.get(formula='float', parent_id=current_class.id,
                                                          name='parent_branch')
                    o = ContractCells(name_id=parent_branch.id, parent_structure_id=current_class.id, code=code, value='')
                if o.id:
                    if o.value != branch_code:
                        old_value = o.value
                        o.value = branch_code
                        edit_objects.append({'old_value': old_value, 'new_obj': o})
                else:
                    o.value = branch_code
                    new_objects.append(o)

            # были ли внесены изменения
            for k, v in request.POST.items():
                try:
                    field_id = int(re.search(r'^(ta|chb|i_datetime|i_date|i_link|i_float|s_enum|s_alias|'
                                             r'i_filename|i_stage_)_(?P<id>\d+)$', k).group('id'))
                except AttributeError:
                    continue
                else:
                    try:
                        o = next(o for o in objects if o.name_id == field_id)
                    except StopIteration:
                        o = ContractCells(name_id=field_id, parent_structure_id=current_class.id,
                                          code=code)
                    # Проверим делэйные значения
                    delay_value, date_delay_value = interface_procedures.check_delay_value(request, field_id, k)
                    v = view_procedures.convert_in_json(k, v)  # Конвертация формата
                    edit_dict[k] = 0 if type(v) in (float, int) else v
                    is_change = False
                    if o.value != v or date_delay_value:
                        # Для массива не будем сохранять изменение собственника
                        if o.name.name == 'Собственник' and current_class.formula == 'array':
                            continue
                        current_param = next(cp for cp in class_params if cp['id'] == field_id)
                        json_object = {}
                        is_handler = current_param['delay'] and 'handler' in current_param['delay'] \
                                             and current_param['delay']['handler']
                        if o.value != v and not is_handler:
                            is_change = True
                            # Если тип данных файл, сравним имена файлов, а затем попробуем загрузить его
                            if re.match(r'^i_filename_.\d+$', k):
                                res, v, msg = app.functions.files_funs.upload_file(request, 'i_file_'
                                                                                   + str(field_id), v, True)
                                if res == 'f':
                                    message += msg
                                    message_class = 'text-red'
                                    continue
                            old_value = o.value
                            o.value = v
                            # добавим в словарь редактирования не новое значение, а дельту
                            if type(v) in (float, int):
                                if not old_value:    old_value = 0
                                edit_dict[k] = v - old_value
                            json_object['old_value'] = old_value

                        valid_delay = True
                        if date_delay_value:
                           # если тип данных - файл - попробуем загрузить его
                            if re.match(r'^i_filename_.\d+$', k):
                                try:
                                    v_file = request.POST['i_filename_' + str(field_id) + '_delay']
                                except KeyError:
                                    continue
                                if v_file:
                                    res, delay_value, msg = upload_file(request, 'i_file_' + str(field_id) + '_delay',
                                                                        v_file)
                                    if res == 'f':
                                        message += msg
                                        message_class = 'text-red'
                                        continue
                                    # Если файл не был загружен, попробуем загрузить его из черновика
                                    elif res == 'm' and not cffdth(v_file, request.GET['class_id']):
                                        message += 'Произошла ошибка во время загрузки файла<br>'
                                        message_class = 'text-red'
                                        continue
                            # Если время выполнения меньше даты создания контракта - скорректировать время выполнения
                            if datetime.strptime(date_delay_value, '%Y-%m-%dT%H:%M') < timestamp:
                                if current_class.formula == 'contract':
                                    date_create_param = next(cp for cp in class_params if cp['name'] == 'system_data')
                                    date_create = next(o for o in objects if o.name_id == date_create_param['id'])
                                else:
                                    header_owner = next(cp for cp in class_params if cp['name'] == 'Собственник')
                                    owner = next(o for o in objects if o.name_id == header_owner['id'])
                                    date_create = ContractCells.objects.get(parent_structure_id=current_class.parent_id,
                                                                            code=owner.value, name__name='system_data')
                                if date_delay_value < date_create.value['datetime_create']:
                                    date_delay_value = date_create.value['datetime_create']
                            new_delay = {'date_update': date_delay_value, 'value': delay_value, 'approve': False}
                            last_delay = o.delay[-1] if o.delay else {}
                            # Если последний делэй изменился - тогда сохраним
                            if not last_delay or last_delay['date_update'] != new_delay['date_update'] \
                                    or last_delay['value'] != new_delay['value']:
                                is_change = True
                                json_object['old_delay'] = copy.deepcopy(o.delay)
                                if current_param['delay']['delay']:
                                    if not current_param['delay']['handler']:
                                        new_delay['approve'] = True
                                    elif not type(current_param['delay']['handler']) is int:
                                        # Ответственный робот говорит свое слово
                                        valid_delay = interface_procedures\
                                            .rohatiw(request.POST, current_class.id, code, current_param, class_params,
                                                     objects, request.user.id, True)
                                        if valid_delay:
                                            new_delay['approve'] = True
                                if valid_delay:
                                    if o.delay:
                                        json_object['old_delay'] = o.delay.copy()
                                        o.delay.append(new_delay)
                                    else:
                                        json_object['old_delay'] = []
                                        o.delay = [new_delay]
                                else:
                                    message += 'Ответственный (робот) отклонил заявку на отложенное значение реквизита ID: ' \
                                       + str(current_param['id']) + '<br>'
                        if is_change:
                            if o.id:
                                json_object['new_obj'] = o
                                edit_objects.append(json_object)
                            else:
                                new_objects.append(o)
            general_reg_data = {'class_id': current_class.id, 'code': code, 'location': 'contract',
                                'type': current_class.formula}
            # Если изменения были, то внесем их
            if edit_objects or new_objects or change_tps:
                if edit_objects or new_objects:
                    transact_id = reg_funs.get_transact_id(current_class.id, code, 'c') if not transact_id else transact_id
                else:
                    transact_id = None
                # для контрактов: Если были изменения, то перед сохранением проверим системные параметры:
                if current_class.formula == 'contract':
                    msg = contract_funs.dcsp(current_class.id, code, class_params, request.user.id,
                                             request.POST, edit_dict, timestamp, transact_id, tps=my_tps)
                    if msg != 'ok':
                        is_valid = False
                        message += msg
                    else:
                        is_saved = True

        if is_valid:
            if edit_objects:
                is_saved = True
                ContractCells.objects.bulk_update([eo['new_obj'] for eo in edit_objects if 'old_value' in eo], ['value'])
                ContractCells.objects.bulk_update([eo['new_obj'] for eo in edit_objects if 'old_delay' in eo], ['delay'])
                # регистрация редактирования
                for eo in edit_objects:
                    ic = general_reg_data.copy()
                    ic['id'] = eo['new_obj'].id
                    ic['name'] = eo['new_obj'].name_id
                    oc = ic.copy()
                    if 'old_value' in eo:
                        ic_val = ic.copy()
                        ic_val['value'] = eo['old_value']
                        oc_val = oc.copy()
                        oc_val['value'] = eo['new_obj'].value
                        reg_val = {'json_income': ic_val, 'json': oc_val}
                        reg_funs.simple_reg(request.user.id, 15, timestamp, transact_id, **reg_val)
                    if 'old_delay' in eo:
                        last_delay = eo['new_obj'].delay[-1]
                        date_update = datetime.strptime(last_delay['date_update'], '%Y-%m-%dT%H:%M')
                        delay_ppa = True if date_update < timestamp else False
                        if not delay_ppa:
                            ic_del = ic.copy()
                            ic_del['delay'] = eo['old_delay']
                            oc_del = oc.copy()
                            oc_del['delay'] = eo['new_obj'].delay
                            reg_del = {'json': oc_del, 'json_income': ic_del}
                            reg_funs.simple_reg(request.user.id, 22, timestamp, transact_id, **reg_del)
                        else:
                            last_delay['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                            interface_procedures.rhwpd('contract', current_class.formula, date_update, last_delay, eo['new_obj'],
                                                       request.user.id, transact_id)
                            eo['new_obj'].save()
                        current_param = next(cp for cp in class_params if cp['id'] == eo['new_obj'].name_id)
                        prms = {}
                        if 'task_code' in eo:
                            prms['code'] = eo['task_code']
                        if 'task_transact' in eo:
                            prms['task_transact'] = eo['task_transact']
                        if eo['new_obj'].name_id in control_fields:
                            prms['cf'] = True
                        interface_procedures.make_task_4_delay(current_param, eo['new_obj'], 'c', request.user, timestamp,
                                                               delay_ppa, transact_id, **prms)  # Создаем / регистрируем таск
            if new_objects:
                is_saved = True
                ContractCells.objects.bulk_create(new_objects)
                new_objects = ContractCells.objects.filter(parent_structure_id=current_class.id, code=code,
                                                           name_id__in=[no.name_id for no in new_objects])
                for no in new_objects:
                    # Регистрация создания реквизитов
                    oc = general_reg_data.copy()
                    oc['id'] = no.id
                    oc['name'] = no.name_id
                    oc['value'] = no.value
                    reg = {'json': oc}
                    reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                    if no.delay:
                        del oc['value']
                        oc['delay'] = no.delay
                        date_update = datetime.strptime(no.delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
                        delay_ppa = True if date_update < timestamp else False
                        if delay_ppa:
                            no.delay[-1]['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                            ts = date_update
                            no.save()
                        else:
                            ts = timestamp
                        ic = oc.copy()
                        ic['delay'] = []
                        reg = {'json': oc, 'json_income': ic}
                        reg_funs.simple_reg(request.user.id, 22, ts, transact_id, **reg)
                        current_param = next(cp for cp in class_params if cp['id'] == no.name_id)
                        interface_procedures.make_task_4_delay(current_param, no, 'c', request.user, timestamp, delay_ppa,
                                                               transact_id)  # Создаем / регистрируем таск
            # Сохраним техпроцессы
            if change_tps:
                is_saved = True
                for ta_k, ta_v in tps_all.items():
                    if ta_v['changed']:
                        tp_info = next(t for t in tps if t['id'] == ta_k)
                        stages = TechProcessObjects.objects.filter(parent_structure_id=ta_k, parent_code=code)
                        if not stages:
                            val = {'fact': 0, 'delay': []}
                            stages_0 = TechProcessObjects(parent_structure_id=ta_k, parent_code=code,
                                                          name_id=tp_info['stages'][0]['id'], value=val)
                            stages = [stages_0]
                        task_code = None; task_transact = None
                        tp_trans = reg_funs.get_transact_id(ta_k, code, 'p')
                        # Если было изменение контрольного поля - внесем изменение в первую стадию
                        if ta_v['cf_delta']:
                            stage_0 = stages[0]
                            inc_val = copy.deepcopy(stage_0.value)
                            inc = {'class_id': ta_k, 'type': 'tp', 'location': 'contract', 'code': code,
                                   'name': stage_0.name_id, 'id': stage_0.id, 'value': inc_val}
                            outc_val = copy.deepcopy(stage_0.value)
                            outc_val['fact'] += ta_v['cf_delta']
                            stage_0.value = outc_val
                            stage_0.save()
                            outc = inc.copy()
                            outc['value'] = outc_val
                            reg = {'json': outc, 'json_income': inc}
                            reg_funs.simple_reg(request.user.id, 15, timestamp, tp_trans, transact_id, **reg)
                        for k, v in ta_v['new_stages'].items():
                            if v['delta']:
                                stage_info = next(s for s in tp_info['stages'] if s['id'] == k)
                                stage = None
                                try:
                                    stage = next(s for s in stages if s.name_id == k)
                                except StopIteration:
                                    stage = TechProcessObjects(parent_structure_id=ta_k, parent_code=code, name_id=k,
                                                               value={'fact': 0, 'delay': []})
                                finally:
                                    if not task_code:
                                        task_code, task_transact = task_funs.reg_create_task(request.user.id, timestamp,
                                                                                             transact_id)
                                    new_delay = {'value': v['delta'], 'date_create': datetime.strftime(timestamp, '%Y-%m-%dT%H:%M:%S')}
                                    inc = {'class_id': ta_k, 'type': 'tp', 'location': 'contract', 'code': code,
                                           'name': k, 'value': copy.deepcopy(stage.value)}
                                    stage.value['delay'].append(new_delay)
                                    stage.save()
                                    # Регистрация изменений
                                    outc = inc.copy()
                                    outc['value'] = stage.value
                                    reg = {'json': outc, 'json_income': inc}
                                    reg_funs.simple_reg(request.user.id, 15, timestamp, tp_trans, transact_id, **reg)
                                    # Создаем таск
                                    delay = sum(d['value'] for d in stage.value['delay'])
                                    sender_fio = request.user.first_name + ' ' + request.user.last_name
                                    task_funs.mt4s(code, stage_info['value']['handler'], request.user.id, sender_fio,
                                                   stage.value['fact'], delay + stage.value['fact'], delay, v['delta'],
                                                   stage.name_id, task_code, tp_info, timestamp, task_transact, transact_id)
                        if task_code:
                            task_funs.do_task2(task_code, request.user.id, timestamp, task_transact, transact_id)

        else:
            message_class = 'text-red'
            # if params['source'] != 'draft' and current_class.formula == 'contract':
            #     message += make_graft(request, code, True)[1]
    # Создаем новый
    else:
        if is_valid:
            is_valid, message = contract_validation(class_params, current_class, request)
        if is_valid:
            code = database_funs.get_code(int(request.GET['class_id']), 'contract')
            transact_id = app.functions.reg_funs.get_transact_id(current_class.id, code, 'c')

            # регистрация создания объекта
            outcoming = {'class_id': current_class.id, 'location': 'contract', 'type': current_class.formula, 'code': code}
            reg = {'json': outcoming}
            reg_funs.simple_reg(request.user.id, 5, timestamp, transact_id, **reg)
            objects = []
            # Сохраняем
            if current_class.formula == 'contract':
                val = {'datetime_create': datetime.today().strftime('%Y-%m-%dT%H:%M:%S'), 'is_done': False,
                       'handler': request.user.id}
                system_data_cell = ContractCells(code=code, parent_structure_id=int(request.GET['class_id']),
                                                 name_id=system_data_id, value=val)
                objects.append(system_data_cell)
            # Сохраним ветку при ее наличии
            if 'i_branch' in request.POST:
                branch_code = int(request.POST['i_branch']) if request.POST['i_branch'] else None
                parent_branch = Contracts.objects.get(formula='float', parent_id=current_class.id,
                                                      name='parent_branch')
                objects.append(ContractCells(code=code, parent_structure_id=current_class.id, name_id=parent_branch.id,
                                             value=branch_code))
            for k, v in request.POST.items():
                try:
                    field_id = int(re.search(r'^(ta|i_datetime|i_link|i_float|chb|'
                                             r'i_date|s_enum|s_alias|i_filename)_(?P<id>\d+)$', k).group('id'))
                except AttributeError:
                    continue
                v = view_procedures.convert_in_json(k, v)  # Конвертация формата
                # Проверим делэйные значения
                delay_value, date_delay_value = interface_procedures.check_delay_value(request, field_id, k)
                if v or date_delay_value:
                    current_param = next(cp for cp in class_params if cp['id'] == field_id)
                    # Если есть ответственный - то не сохраняем непосредственное значение (факт)
                    handler = current_param['delay']['handler'] \
                        if current_param['delay'] and 'handler' in current_param['delay'] \
                           and current_param['delay']['handler'] else False
                    if handler:
                        v = None
                    if re.match(r'^i_filename_.\d+$', k) and v:
                        res, v, msg = app.functions.files_funs.upload_file(request, 'i_file_'
                                                                           + str(field_id), v, True)
                        if res == 'f':
                            message += msg
                            message_class = 'text-red'
                            continue
                        # Если файл не был загружен, попробуем загрузить его из черновика
                        elif res == 'm' and not cffdth(v, request.GET['class_id'], location='contract'):
                            message += 'Произошла ошибка во время загрузки файла<br>'
                            message_class = 'text-red'
                            continue

                    if date_delay_value:
                        # если тип данных - файл - попробуем загрузить его
                        if re.match(r'^i_filename_.\d+$', k):
                            try:
                                v_file = request.POST['i_filename_' + str(field_id) + '_delay']
                            except KeyError:
                                continue
                            if v_file:
                                res, delay_value, msg = upload_file(request, 'i_file_' + str(field_id) + '_delay', v_file)
                                if res == 'f':
                                    message += msg
                                    message_class = 'text-red'
                                    continue
                                # Если файл не был загружен, попробуем загрузить его из черновика
                                elif res == 'm' and not cffdth(v_file, request.GET['class_id']):
                                    message += 'Произошла ошибка во время загрузки файла<br>'
                                    message_class = 'text-red'
                                    continue
                        new_delay = [{'value': delay_value, 'date_update': date_delay_value, 'approve': False}]
                        if not handler:
                            new_delay[0]['approve'] = True
                        elif not type(handler) is int:
                                # Ответственный-робот говорит свое слово
                                approve = interface_procedures.rohatiw(request.POST, current_class.id, code, current_param,
                                                                       class_params, objects, request.user.id, True)
                                if approve:
                                    new_delay[0]['approve'] = True
                                else:   new_delay = []
                    else:
                        new_delay = []
                    objects.append(ContractCells(code=code, parent_structure_id=int(request.GET['class_id']),
                                                 name_id=field_id, value=v, delay=new_delay))
            if current_class.formula == 'contract':
                # Проверка системных параметров
                msg = contract_funs.dcsp(current_class.id, code, class_params, request.user.id, request.POST,
                                                   request.POST, timestamp, transact_id, tps=my_tps)
                if msg != 'ok':
                    is_valid = False
                    message += msg
                else:
                    is_saved = True
            else:
                is_saved = True
            if is_saved:
                ContractCells.objects.bulk_create(objects)
                message = 'Запись контракта успешно создана. Код записи: ' + str(code) + '<br>'
                # Регистрация реквизитов объекта
                new_object_params = ContractCells.objects.filter(code=code, parent_structure_id=current_class.id)
                list_task_info = []
                for nop in new_object_params:
                    outcom = model_to_dict(nop)
                    del outcom['code']
                    del outcom['parent_structure']
                    outcom.update(outcoming)
                    if nop.delay:
                        outcom_delay = copy.deepcopy(outcom)
                        delay = outcom_delay['delay']
                        date_update = datetime.strptime(delay[-1]['date_update'], '%Y-%m-%dT%H:%M')
                        delay_ppa = date_update < timestamp
                        if delay_ppa:
                            delay[-1]['date_update'] = datetime.strftime(timestamp, '%Y-%m-%dT%H:%M')
                            ts = date_update
                            nop.save()
                        else:
                            ts = timestamp
                        del outcom_delay['value']
                        reg_delay = {'json': outcom_delay}
                        reg_funs.simple_reg(request.user.id, 22, ts, transact_id, **reg_delay)
                        current_param = next(cp for cp in class_params if cp['id'] == nop.name_id)
                        # Создаем / регистрируем таск
                        prms = {}
                        if nop.name_id in control_fields:
                            prms['cf'] = True
                        interface_procedures.make_task_4_delay(current_param, nop, 'c', request.user, timestamp, delay_ppa,
                                                               transact_id, **prms)
                    del outcom['delay']
                    reg = {'json': outcom}
                    reg_funs.simple_reg(request.user.id, 13, timestamp, transact_id, **reg)
                # cохраним техпроцессы
                for tp in tps:
                    try:
                        control_field = next(nop for nop in new_object_params if nop.name_id == tp['cf'])
                    except StopIteration:
                        val = {'fact': 0, 'delay': []}
                    else:
                        val = control_field.value if control_field.value else 0
                        val = {'fact': val, 'delay': []}
                    first_stage = TechProcessObjects(parent_structure_id=tp['id'], parent_code=code,
                                                     name_id=tp['stages'][0]['id'], value=val)
                    first_stage.save()

        else:
            message_class = 'text-red'
            if current_class.formula == 'contract':
                message += make_graft(request, None, True)[1]
    # Создание словаря
    if is_valid:
        dict_saved = save_dict(request, code, transact_id, timestamp)
        is_saved = is_saved or dict_saved

    if is_saved:
        message += 'Объект сохранен'
        # проверим условие выполнения
        if current_class.formula == 'contract':
            system_data_cell = next(o for o in objects if o.name_id == system_data_id)
            do_cc(current_class, system_data_cell, code, request.user.id)

    else:
        if is_valid:
            message += 'Вы ничего не изменили. '
        else:
            message_class = 'text-red'
        message += 'Объект не сохранен'
    return is_saved, message, message_class, code, transact_id, timestamp


def do_cc(current_contract, system_data_cell, code, user_id):
    object = {'parent_structure': current_contract.id, 'code': code}
    completion_condition = Contracts.objects.get(parent_id=current_contract.id, system=True, name='completion_condition')
    completion_condition = model_to_dict(completion_condition)
    is_done = contract_funs.do_business_rule(completion_condition, object, user_id)
    if system_data_cell.value['is_done'] != is_done:
        system_data_cell.value['is_done'] = is_done
        system_data_cell.save()
        is_task = Tasks.objects.filter(kind='cotc', user_id=system_data_cell.value['handler'],
                                       data__class_id=current_contract.id, data__code=code)
        if is_done:
            if not is_task:
                task_funs.mt4cotc(current_contract, system_data_cell, user_id)
        else:
            if is_task:
                is_task.delete()


# Валидация. Вход - реквест. Выход - да/нет, сообщение
def contract_validation(class_params, current_class, request, objects=[]):
    dict_keys = {'string': 'ta_', 'link': 'i_link_', 'float': 'i_float_', 'datetime': 'i_datetime_',
                 'date': 'i_date_', 'bool': 'chb_', 'const': 's_alias_', 'enum': 's_enum_'}
    message = ''
    is_valid = True
    required_fields = [cp['id'] for cp in class_params if cp['is_required'] and cp['name'] != 'Дата и время записи']
    code = int(request.POST['i_code']) if request.POST['i_code'] else 0
    object = {'code': code, 'parent_srtucture': current_class.id}
    # проверка родительской ветки при ее наличии
    if 'i_branch' in request.POST:
        is_valid, branch, message = interface_procedures.valid_branch(request, current_class.parent_id, True)
    # Корректность вводимых данных
    for k, v in request.POST.items():
        try:
            field_id = int(re.search(r'^(ta|i|i_datetime|i_link|i_float|s_enum|chb|i_date)_(?P<id>\d+)$', k).group('id'))
        except AttributeError:
            continue
        else:
            current_field = next(cp for cp in class_params if cp['id'] == int(field_id))
            # 1. Обязательные поля
            if field_id in required_fields and not v:
                dv = interface_procedures.check_delay_value(request, field_id, k)
                if not dv[0]:
                    is_valid = False
                    message += ' Не заполнено обязательное поле \"' + current_field['name'] + '\"<br>'
            # 2. Проверяем только заполненные поля. Пустые игнорим
            elif v:
                # 3. Проверка числового поля
                if current_field['formula'] == 'float':
                    try:
                        float(v)
                    except ValueError:
                        is_valid = False
                        message += ' Некорректно указано значение поля \"' + current_field['name'] + '\"<br>'
                # 4. Проверка ссылочного поля
                elif current_field['formula'] == 'link':
                    try:
                        int(v)
                    except ValueError:
                        is_valid = False
                        message += ' Некорректно указано значение поля \"' + current_field['name'] + '\"<br>'
                    else:
                        if not database_funs.check_object(int(v), current_field['value']):
                            is_valid = False
                            message += ' Некорректно указано значение поля \"' + current_field['name'] + '\"<br>'
                # 5. Проверка формата ДатаВремя
                elif current_field['formula'] == 'datetime':
                    try:
                        datetime.strptime(v, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        try:
                            datetime.strptime(v, '%Y-%m-%dT%H:%M:%S')
                        except ValueError:
                            is_valid = False
                            message += ' Некорректно указано значение поля \"' + current_field['name'] + '\"<br>'
                # Добавление параметра в словарь
                object[field_id] = {}
                object[field_id]['value'] = v
    # Проверим обязательные поля
    for cp in class_params:
        # Проверка обязательных файлов
        if cp['formula'] == 'file' and cp['is_required']:
            code = request.POST['i_code'] if 'i_code' in request.POST else None
            rec = None
            if code:
                rec = ContractCells.objects.filter(code=code, parent_structure_id=current_class.id, name_id=cp['id'])
            if not code or not rec or not rec[0].value:
                for k in request.FILES.keys():
                    if int(k[7:]) == cp['id']:
                        break
                else:
                    is_valid = False
                    message += 'Не заполнено обязательное поле - "' + cp['name'] + '"<br>'
                    # Проверка корректности формул
        elif cp['formula'] == 'eval' and cp['is_required']:
            convert_funs.deep_formula(cp, [object, ], request.user.id, True)
            result = object[cp['id']]['value']
            if type(result) is str and result[:6].lower() == 'ошибка':
                is_valid = False
                message += 'Формула в поле "' + cp['name'] + '" ID: ' + str(cp['id']) + \
                         ' задана некорректно<br>'
        elif cp in required_fields:
            my_key = dict_keys[cp['formula']] + str(cp['id'])
            if not my_key in request.POST or not request.POST[my_key]:
                if code:
                    try:
                        obj = next(o for o in objects if o.name_id == cp['id'])
                    except StopIteration:
                        is_valid = False
                        message += ' Не заполнено обязательное поле \"' + cp['name'] + '\"<br>'
                    else:
                        if cp['formula'] != 'bool' and not obj.value:
                            is_valid = False
                            message += ' Не заполнено обязательное поле \"' + cp['name'] + '\"<br>'
                else:
                    is_valid = False
                    message += ' Не заполнено обязательное поле \"' + cp['name'] + '\"<br>'

    return is_valid, message


def get_new_tps(item_code, tps):
    list_tps = []
    def complete_stages(stages, exist_ids, output_list):
        for s in stages:
            if s['id'] not in exist_ids:
                val = {'fact': 0, 'delay': []}
                new_s = {'id': s['id'], 'parent_code': item_code, 'parent_structure_id': s['parent_id'], 'name': s['name'],
                         'value': val}
                output_list.append(new_s)
        return sorted(output_list, key=lambda x: x['id'])

    for t in tps:
        exist_stages = TechProcessObjects.objects.filter(parent_structure_id=t['id'], parent_code=item_code)\
                            .select_related('name')
        exist_stages_ids = []
        list_es = []
        for es in exist_stages:
            des = model_to_dict(es)
            des['id'] = es.name_id
            des['name'] = es.name.name
            list_es.append(des)
            exist_stages_ids.append(es.name.id)
        if list_es:
            # Если есть записи техпроцессов - дозаполним пустые записи
            complete_stages(t['stages'], exist_stages_ids, list_es)
        else:
            # Если записей ТП нет - заполним заново
            stage_0 = t['stages'][0]
            try:
                control_field_val = ContractCells.objects.get(parent_structure_id=t['parent_id'], code=item_code,
                                                                 name_id=t['cf'])
            except ObjectDoesNotExist:
                cf_val = 0
            else:
                cf_val = control_field_val.value
            first_stage = {'id': stage_0['id'], 'parent_code': item_code, 'parent_structure_id': stage_0['parent_id'],
                           'name': stage_0['name'], 'value': {'fact': cf_val, 'delay': []}}
            list_es.append(first_stage)
            complete_stages(t['stages'], [stage_0['id']], list_es)
        dict_tp = {'id': t['id'], 'stages': list_es, 'control_field': t['cf']}
        list_tps.append(dict_tp)
    return list_tps



# ccv - create_class_validation
# вход: message. Если все ок. то message = ok. если нет - текст ошибки.
def ccv(class_name, class_type, class_types, parent_id, location='t', **params):
    # опциональные параметры
    link_map = params['link_map'] if 'link_map' in params and params['link_map'] else None
    stages = params['stages'] if 'stages' in params and params['stages'] else None
    control_field = params['control_field'] if 'control_field' in params and params['control_field'] else None

    if not location in ('c', 't'):
        return 'Некорректно указано расположение класса<br>'

    class_manager = Designer.objects if location == 't' else Contracts.objects
    object_manager = Objects.objects if location == 't' else ContractCells.objects
    container_types = ('folder', 'tree')
    object_types = ('contract', 'table')
    dict_parent_types = {'folder': ('folder',), 'tree': ('folder',), 'contract': container_types, 'alias': ('folder',),
                         'table': container_types, 'array': object_types, 'dict': object_types, 'tp': ('contract', 'array')}
    root_types = ('contract', 'table', 'folder', 'tree', 'alias')
    indep_types = ('contract', 'table', 'tree', 'alias', 'folder')

    # Проверка типа класса
    if class_type not in class_types:
        return 'Некорректно указан тип класса. Укажите один из следующих типов: ' + ', '.join(class_types) + '<br>'

    # Проверка родителя
    parent_class = None
    if parent_id:
        my_types = dict_parent_types[class_type]
        parent_class = class_manager.filter(id=parent_id, formula__in=my_types)
        if not parent_class:
            return 'Некорректно указан ID родительского класса. Для типа ' + class_type +\
                   ' в качестве родителя необходимо указать класс одного из следующих типов: ' + ', '.join(my_types) + '<br>'
        else:
            parent_class = parent_class[0]
    else:
        if not class_type in root_types:
            return 'Некорректно указан тип класса. В корне структуры классов могут быть только следующие типы: ' \
                   + ', '.join(root_types) + '<br>'
        elif parent_id == 0:
            return  'Некорректно указан родительский каталог. Необходимо либо указать ID реально существующего класса, ' \
                    'либо оставить поле пустым<br>'

    # Наличие имени
    if not class_name:
        return 'Нельзя создать класс без имени<br>'

    # Проверка уникальности имени в рамках своей области видимости
    if not parent_id:
        if class_manager.filter(name=class_name, parent_id=None):
            return 'Класс с таким же именем уже есть в данной области видимости<br>'
    elif parent_class.formula == 'folder':
        if class_manager.filter(parent_id=parent_id, formula__in=indep_types, name=class_name):
            return 'Класс с таким же именем уже есть в данной области видимости<br>'
    elif parent_class.formula == 'tree':
        if class_manager.filter(parent_id=parent_id, formula__in=object_types, name=class_name):
            return 'Класс с таким же именем уже есть в данной области видимости<br>'
    elif parent_class.formula in object_types:
        arrays = class_manager.filter(parent_id=parent_id, formula='array', name=class_name)
        dicts = Dictionary.objects.filter(parent_id=parent_id, formula='dict', name=class_name)
        if dicts or arrays:
            return 'Класс с таким же именем уже есть в данной области видимости<br>'
    # Проверим, есть ли техпроцесс
    elif parent_class.formula in ('contract', 'array') and location == 'c':
        if TechProcess.objects.filter(parent_id=parent_id, formula='tp', name=class_name):
            return 'Класс с таким же именем уже есть в данной области видимости<br>'

    # Проверка на противоречие типа класса и локации
    if (class_type == 'contract' and location != 'c') or (class_type == 'table' and location != 't'):
        return 'Локация и тип класса противоречат друг другу'

    # Для новых техпроцессов
    if class_type == 'tp':
        if location != 'c':
            return 'Невозможно использовать техпроцессы в справочниках<br>'
        cf_header = Contracts.objects.filter(parent_id=parent_id, formula='float', id=control_field,
                                           is_required=True)
        if not cf_header:
            return 'Контрольное поле для техпроцесса должно быть числовым полем с включенным атрибутом "Обязательный"<br>'
        # Если есть объекты, у которых в контрольном поле есть делэй - не создавайте класс техпроцесса
        cf_cell = object_manager.filter(parent_structure_id=parent_id, name_id=control_field).exclude(delay=[])\
            .exclude(delay__isnull=True).values('delay')
        if cf_cell:
            return 'Невозможно создать техпроцесс, есть существуют объекты, у которых в контрольном поле есть отложенные значения<br>'
    return 'ok'


# ecv - edit class validation
# входные данные - см. ccv
# выход - строка. Если данные валидные - ok. Если нет - текст ошибки
def ecv(class_id, class_name, class_type, parent_id, location='t'):
    if location not in ('t', 'c'):
        return 'Некорректно задана переменная location. Выберите один из двух возможных вариантов - t, c<br>'
    parent_manager = Designer.objects if location == 't' else Contracts.objects
    if class_type == 'dict':
        class_manager = Dictionary.objects
    elif class_type == 'techprocess':
        class_manager = TechProcess.objects
    else:
        class_manager = parent_manager
    root_types = ('contract', 'table', 'folder', 'tree', 'alias')
    container_types = ('folder', 'tree')
    object_types = ('contract', 'table')

    # Проверка класса
    current_class = class_manager.filter(id=class_id)
    if not current_class:
        return 'ID класса задан некорректно<br>'
    else:
        current_class = current_class[0]

    # проверка типа класса
    class_types = [ctl['name'] for ctl in ClassTypesList.objects.all().values('name')]
    if not class_type in class_types:
        return 'Указан некорректный тип данных. Выберите один из существующих типов классов: ' + ', '.join(class_types) + '<br>'

    # Проверка родителя
    if parent_id:
        if parent_id == class_id:
            return 'Нельзя указывать собственный ID в качестве родителя<br>'
        if class_type in ('dict', 'array'):
            if not parent_manager.filter(id=parent_id, formula__in=object_types):
                return 'Некорректно указан ID родительского класса<br>'
        elif class_type in object_types:
            if not parent_manager.filter(id=parent_id, formula__in=container_types):
                return 'Некорректно указан ID родительского класса<br>'
        elif class_type in container_types:
            if not parent_manager.filter(id=parent_id, formula='folder'):
                return 'Некорректно указан ID родительского класса<br>'
    elif class_type not in root_types:
        return 'Некорректно указан ID родительского класса<br>'

    # Наличие имени
    if not class_name:
        return 'У класса обязательно должно быть наименование<br>'

    # Проверка уникальности имени в рамках своей новой области видимости
    if not parent_id:
        if parent_manager.filter(name=class_name, parent_id=None):
            return 'Класс с таким же именем уже есть в данной области видимости<br>'
    else:
        if parent_manager.filter(parent_id=parent_id, formula__in=class_types, name=class_name) or \
                class_manager.filter(parent_id=parent_id, formula__in=('dict', 'techprocess'),
                                     name=class_name).exclude(id=class_id):
            return 'Класс с таким же именем уже есть в данной области видимости<br>'

    # Защита от переноса словарей,техпроцессов и массивов другому родителю
    if class_type in ('array', 'dict', 'techprocess') and current_class.parent_id != parent_id:
        return 'Типы "Массив" и "Словарь" нельзя переадресовывать другому родителю<br>'

    # Проверка на противоречие типа класса и локации
    if (class_type == 'contract' and location != 'c') or (class_type == 'table' and location != 't'):
        return 'Локация и тип класса противоречат друг другу'
    
    return 'ok'


# ccpv = create class param validation
# опциональные параметры {value, default, is_reuired, is_vidible, delay}
def ccpv(class_id, class_type, location, param_name, param_type, **params):
    if class_type in ('folder', 'techpro'):
        return 'Нельзя создавать реквизиты у каталогов и технических процессов'
    if class_type == 'dict':
        class_manager = Dictionary.objects
    else:
        class_manager = Contracts.objects if location == 'c' else Designer.objects
    try:
        class_manager.get(id=class_id, formula=class_type)
    except ObjectDoesNotExist:
        return 'Некорректно заданы параметры класса. Класс не найден'
    # Проверка имени
    if not param_name:
        return 'Не указано имя параметра'
    class_params = class_manager.filter(parent_id=class_id)
    if class_type != 'dict':
        class_params = class_params.filter(system=False)
    exist_names = [cp.name.lower() for cp in class_params]
    if class_type == 'tree':
        exist_names.append('наименование')
    if param_name.lower() in exist_names:
        return 'Названия параметров контрактов не должны повторяться'
    # Проверка типов
    parent_type = None; parent_id = None
    data_types = [o.value for o in Objects.objects.filter(parent_structure_id=144, name__name='Наименование')]
    if not param_type or param_type not in data_types:
        return 'Тип параметра указан некорректно'
    # Проверка типа "Ссылка" или "константа"
    elif param_type in ('link', 'const'):
        if (not 'value' in params or not params['value']) and class_type != 'dict' or\
                (not 'default' in params or not params['default']) and class_type == 'dict':
            return 'У ссылки нет родителя.<br>'
        else:
            # проверка корректности value для ссылки
            if class_type != 'dict':
                parent_type, parent_id = convert_procedures.slice_link_header(params['value'])
            else:
                if 'default' not in params:
                    return 'Не указан обязательный параметр для типа данных link словаря'
                match = re.match(r'(table|contract)\.(\d+)\.(\d*)', params['default'])
                if not match:
                    return 'Ссылка указана некорректно'
                parent_type = match[1]
                parent_id = match[2]
            if not parent_type or class_type not in ['table', 'contract', 'dict', 'array', 'tree']:
                return 'Некорректно задан код значения ссылки. Необходимо указать тип класса - contract или table, ' \
                          'затем поставить точку и написать айди внешнего класса'
            else:
                is_contract = True if parent_type == 'contract' else False
                verify_type = database_procedures.get_class_type(parent_id, is_contract)
                if (verify_type != parent_type and param_type == 'link') or (verify_type != 'alias' and param_type == 'const'):
                    return 'Некорректно задан код значения ссылки. Необходимо указать тип класса - contract или table, ' \
                          'затем поставить точку и написать айди внешнего класса'
                elif parent_type == 'link':
                    # Проверка на потомка
                    is_child = database_funs.is_child(int(parent_id), parent_type, class_id, class_type)
                    if is_child:
                        return 'Некорректный тип значения нового параметра. ' \
                                   'Нельзя в качестве родительского контракта указывать потомка, ' \
                                   'это приводит к цикличным ссылкам'
    elif param_type == 'enum' and class_type != 'dict':
        if not ('value' in params and params['value'] and type(params['value']) is list):
            return 'Некорректно задано значение для типа данных enum. необходимо задать непустой список строк'
        else:
            for pv in params['value']:
                if not type(pv) is str:
                    return 'Некорректно задано значение для типа данных enum. необходимо задать непустой список строк'
    elif param_type == 'eval':
        if 'value' in params and params['value'] and not type(params['value']) is str:
            return 'Некорректно задание поле "value"'
    # отдельно проверим поле для константы
    if class_type == 'alias' and param_type != 'eval':
        return 'Для параметра константы тип данных должен быть "eval"'
    # Проверка поля default
    if 'default' in params and params['default']:
        ver_def = interface_procedures.ver_def(class_type, param_type, params['default'], parent_type, parent_id)
        if ver_def != 'ok':
            return ver_def
    return 'ok'


# spot = save params of tp
def spot(tp_id, user_id, **params):
    # верификация
    try:
        tp = TechProcess.objects.get(id=tp_id)
    except ObjectDoesNotExist:
        return 'Некорректно указано ID техпроцесса<br>'
    # проверим контрольное поле
    change_cf = False  # переменная включается один раз. Во время инициализации контрольного поля техпроцессов
    # Изменить контрольное поле можно, но один раз - с пустого на непустой
    if not tp.value['control_field'] and 'control_field' in params and params['control_field']:
        change_cf = True
        try:
            Contracts.objects.get(parent_id=tp.parent_id, id=params['control_field'], formula='float')
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            return 'Некорректно указан ID контрольного поля<br>'
    # проверим стадии
    change_stages = False
    if 'stages' in params:
        old_stages = TechProcess.objects.get(name='stages', parent_id=tp_id)
        if old_stages.value != params['stages']:
            change_stages = True
            if not type(params['stages']) is list:
                return 'Некорректно заданы стадии техпроцесса. Укажите стадии в виде списка строк<br>'
    if 'link_map' in params:
        old_lm = TechProcess.objects.get(name='link_map', parent_id=tp_id)
        if old_lm.value != params['link_map']:
            interface_procedures.iscrh(tp_id, old_lm.value, params['link_map'])
            err_text = 'Некорректно заданы ЛинкМап. Укажите в виде списка словарей, ' \
                       'где у словаря следующая структура: {name: str, handler: int, children: list}. ' \
                       'Названия стадий не должны повторяться. Handler - это ID ответственного пользователя,' \
                       ' children - список стадий, в которые возможно движение с данной стадии<br>'
            for lm in params['link_map']:
                # Проверка структуры
                if not ('name' in lm and 'handler' in lm and 'children' in lm):
                    return err_text
                # Проверка повторимости имен
                if lm['name'] in [lmlm['name'] for lmlm in params['link_map'] if params['link_map'].index(lmlm) !=
                                                                                 params['link_map'].index(lm)]:
                    return err_text
                # Проверка ответственных
                if lm['handler'] and not type(lm['handler']) is int:
                    return err_text
                if lm['handler'] and not get_user_model().objects.filter(id=lm['handler']):
                    return err_text
                # Проверка детей
                if not type(lm['children']) is list:
                    return err_text
                lnwc = [s for s in params['stages'] if s != lm['name']]  # list names without current
                for c in lm['children']:
                    if c not in lnwc:
                        return  err_text

    timestamp = params['timestamp'] if 'timestamp' in params else datetime.today()
    transact_id = reg_funs.get_transact_id(tp_id, 0, 'p')
    parent_transact = params['parent_transact'] if 'parent_transact' in params else None
    # Сохраним изменения
    is_change = False
    if change_cf:
        is_change = True
        inc = {'class_id': tp_id, 'location': 'contract', 'type': 'techprocess', 'control_field': tp.value['control_field']}
        outc = inc.copy()
        outc['control_field'] = params['control_field']
        tp.value['control_field'] = params['control_field']
        tp.save()
        reg = {'json': outc, 'json_income': inc}
        reg_funs.simple_reg(user_id, 3, timestamp, transact_id, parent_transact, **reg)
    if change_stages:
        is_change = True
        inc = {'class_id': tp_id, 'location': 'contract', 'type': 'techprocess', 'id': old_stages.id, 'name': 'stages',
               'value': old_stages.value}
        outc = inc.copy()
        outc['value'] = params['stages']
        old_stages.value = params['stages']
        old_stages.save()
        reg = {'json': outc, 'json_income': inc}
        reg_funs.simple_reg(user_id, 10, timestamp, transact_id, parent_transact, **reg)
    if 'business_rule' in params:
        old_br = TechProcess.objects.get(name='business_rule', parent_id=tp_id)
        if old_br.value != params['business_rule']:
            is_change = True
            inc = {'class_id': tp_id, 'location': 'contract', 'type': 'techprocess', 'id': old_br.id,
                   'name': 'business_rule', 'value': old_br.value}
            outc = inc.copy()
            outc['value'] = params['business_rule']
            old_br.value = params['business_rule']
            old_br.save()
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(user_id, 10, timestamp, transact_id, parent_transact, **reg)
    if 'link_map' in params:
        old_lm = TechProcess.objects.get(name='link_map', parent_id=tp_id)
        if old_lm.value != params['link_map']:
            is_change = True
            # Если имя было изменено, исправим это имя везде в истории

            inc = {'class_id': tp_id, 'location': 'contract', 'type': 'techprocess', 'id': old_lm.id,
                   'name': 'link_map', 'value': old_lm.value}
            outc = inc.copy()
            outc['value'] = params['link_map']
            old_lm.value = params['link_map']
            old_lm.save()
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(user_id, 10, timestamp, transact_id, parent_transact, **reg)
    if 'trigger' in params:
        old_tr = TechProcess.objects.get(name='trigger', parent_id=tp_id)
        if old_tr.value != params['trigger']:
            is_change = True
            inc = {'class_id': tp_id, 'location': 'contract', 'type': 'techprocess', 'id': old_tr.id,
                   'name': 'trigger', 'value': old_tr.value}
            outc = inc.copy()
            outc['value'] = params['trigger']
            old_tr.value = params['trigger']
            old_tr.save()
            reg = {'json': outc, 'json_income': inc}
            reg_funs.simple_reg(user_id, 10, timestamp, transact_id, parent_transact, **reg)
    result = 'ok' if is_change else 'Вы ничего не изменили<br>'
    # Если была инициализация контрольного поля техпроцесса - заполним объекты техпроцессов для всех объектов контрактов
    if change_cf:
        cells = ContractCells.objects.filter(parent_structure_id=tp.parent_id, name_id=tp.value['control_field'])
        for c in cells:
            interface_procedures.mtp(c, old_stages)
    return result