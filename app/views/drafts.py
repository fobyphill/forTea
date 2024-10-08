import json
import re

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q, Subquery
from django.forms import model_to_dict

import app.functions.contract_funs
import app.functions.files_funs

from datetime import datetime
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from app.functions import view_procedures, session_funs, interface_funs, convert_funs, common_funs, draft_funs, \
    api_funs, convert_procedures, interface_procedures, session_procedures, task_funs
from app.models import Designer, TableDrafts, Contracts, ContractDrafts, ContractCells, Objects
from django.contrib.auth import get_user_model


@view_procedures.is_auth_app
def table_draft(request):
    is_contract = request.path[1] == 'c'
    type_menu = 'contract_menu' if is_contract else 'class_menu'
    type_tree = 'contract_tree' if is_contract else 'class_tree'

    # Загрузить дерево классов в сессию
    if not type_tree in request.session:
        session_funs.update_class_tree(request, is_contract)

    # Загрузить меню справочников / контрактов
    if not type_menu in request.session:
        request.session[type_menu] = session_funs.update_class_menu(request, request.session[type_tree],
                                                                       request.session[type_tree], None, is_contract)
    # Загрузим меню черновиков
    if not 'draft_tree' in request.session:  # загрузить дерево черновиков в сессию
        session_funs.update_draft_tree(request, is_contract)

    try:
        class_id = int(request.GET['class_id'])
    except KeyError:
        if 'del' in request.GET:
            ids = [int(d) for d in request.GET['del'].split(',')]
            draft_name = 'contract_tree' if is_contract else 'class_tree'
            draft_funs.remove_all_drafts(request.user.id, ids, request.session[draft_name], is_contract)
            session_funs.update_draft_tree(request, is_contract)
            return HttpResponse('Все черновики были удалены. <a href="/">На главную</a>')
        else:
            return HttpResponse('Не указан класс черновика')

    # Проброска данных из гет в пост
    to_post_redirect = interface_funs.get_to_post(request, ('class_id',))
    if to_post_redirect:
        return to_post_redirect
    session_funs.update_omtd(request)
    session_funs.check_quant_tasks(request)  # контрольный пересчет заданий
    header_manager = Contracts.objects if is_contract else Designer.objects
    draft_manager = ContractDrafts.objects if is_contract else TableDrafts.objects
    new_obj_draft = ContractDrafts if is_contract else TableDrafts
    class_type = 'контракт' if is_contract else 'справочник'
    try:
        current_class = list(header_manager.filter(id=class_id, formula__in=('table', 'contract', 'array'))
             .select_related('parent'))[0]
    except:
        return HttpResponse('не найден ' + class_type + ' с ID = ' + request.GET['class_id'])
    headers = request.session['temp_object_manager']['headers']
    code = int(request.POST['i_code']) if 'i_code' in request.POST and request.POST['i_code'] else None
    draft_id = int(request.POST['i_id']) if 'i_id' in request.POST and request.POST['i_id'] else None

    title = 'массива' if current_class.formula == 'array' else class_type + 'а'
    title = 'Черновики ' + title + ' "' + current_class.name + '"' + '"' + ' ID: ' + request.GET['class_id']
    message = ''
    message_class = ''

    def draft_save(draft_id):
        # Редактируем
        if draft_id:
            is_change, draft = interface_funs.draft_edit(request, draft_id, is_contract)
            message = 'Черновик изменен<br>' if is_change else 'Вы не внесли изменений. Черновик не был сохранен<br>'
        # Создаем новый черновик
        else:
            params = {}
            if 'tps' in request.session['temp_object_manager']:
                params['tps_info'] = request.session['temp_object_manager']['tps']
            draft = interface_funs.make_graft(request, class_id, headers, code, request.user.id, is_contract,
                                                       **params)
            message = 'Создан новый черновик<br>'
            # Если у черновика есть подчиненные черновики - скопируем их
            if 'arrays' in request.session['temp_object_manager'] and request.session['temp_object_manager']['arrays']:
                for a in request.session['temp_object_manager']['arrays']:
                    key_slave = 'i_slave_' + str(a['id'])
                    owner = next(str(h['id']) for h in a['headers'] if h['name'] == 'Собственник')
                    # Если мы находимся на странице черновиков - то скоприуем черновики подчиненных массивов
                    if key_slave in request.POST and request.POST[key_slave]:
                        slaves_ids = json.loads(request.POST[key_slave])
                        slave_drafts = draft_manager.filter(id__in=slaves_ids)
                        new_slaves = []
                        timestamp = datetime.now()
                        for sd in slave_drafts:
                            sd.data['code'] = None
                            sd.data[owner]['value'] = draft.id
                            ns = new_obj_draft(data=sd.data, user_id=request.user.id, timestamp=timestamp)
                            new_slaves.append(ns)
                        draft_manager.bulk_create(new_slaves)
        return draft, message

    # Кнопка "Сохранить"
    if 'b_save' in request.POST:
        draft, message = draft_save(draft_id)
        # Если черновик был сохранен, то переместимся на первую страницу
        if message[:2] != 'Вы':
            request.POST._mutable = True
            request.POST['page'] = '1'
            request.POST._mutable = False

    elif 'b_save_file' in request.POST:
        response = interface_funs.download_file(request, is_contract)
        if response:
            return response
        else:
            message = 'Файл не найден\n'
            message_class = 'text-red'

    elif 'b_del_file' in request.POST:
        # Удалим ссылку на файл в БД
        del_file = draft_manager.get(id=draft_id)
        file_name = del_file.data[request.POST['b_del_file']]['value']
        del_file.data[request.POST['b_del_file']]['value'] = ''
        del_file.save()
        app.functions.files_funs.delete_draft_file(file_name, request.GET['class_id'], is_contract)  # Удалим файл физически
        message = 'Файл удален\n'

    elif 'b_del_draft' in request.POST:
        del_draft = draft_manager.get(id=draft_id)
        # Если есть файл - удалим его
        for h in headers:
            if h['formula'] == 'file':
                header_id = str(h['id'])
                if header_id in del_draft.data.keys():
                    file_name = del_draft.data[header_id]['value']
                    if file_name:
                        app.functions.files_funs.delete_draft_file(file_name, request.GET['class_id'], is_contract)
        # Если есть массивы - удалим их
        if 'arrays' in request.session['temp_object_manager']:
            for array in request.session['temp_object_manager']['arrays']:
                owner = next(str(h['id']) for h in array['headers'] if h['name'] == 'Собственник')
                my_arrays = draft_manager.filter(user_id=request.user.id, data__parent_structure=array['id'])
                for ma in my_arrays:
                    if ma.data[owner]['value'] == draft_id:
                        ma.delete()

        del_draft.delete()  #  Удалим запись
        message = 'Черновик удален'
        session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков

    elif 'b_delete_dict' in request.POST and request.POST['delete_dict']:
        dict_key = 'dict_' + request.POST['delete_dict']
        draft = draft_manager.get(id=draft_id)
        draft.data[dict_key] = None
        draft.timestamp = datetime.now()
        draft.save()
        message = 'Черновик сохранен\n'

    elif 'b_in_object' in request.POST:
        # отложенное создание объекта
        if request.POST['dt_delay_in_object']:
            draft = draft_save(draft_id)[0]
            draft.active = False
            draft.save()
            session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков

            date_delay = datetime.strptime(request.POST['dt_delay_in_object'], '%Y-%m-%dT%H:%M')
            dict_object = {'parent_structure': class_id, 'type': current_class.formula,
                           'location': 'contract' if is_contract else 'table', 'draft_id': draft_id}
            for ok, ov in request.POST.items():
                match_key = re.match(r'(?:i_code|ta_|chb_|i_float_|i_link_|i_date_|i_datetime_|s_enum_|s_alias_|i_branch'
                                     r'|i_filename_|dict_info)(\d+|)$', ok)
                if match_key:
                    if ok[:6] == 'i_code':
                        dict_object['code'] = int(ov) if ov else None
                    elif ok[:9] == 'dict_info':
                        dict_object[ok] = ov
                    elif ok[:10] == 'i_filename':
                        if re.match(r'\d{14}', ok):
                            dict_object[ok] = ov
                        else:
                            dict_object[ok] = next(dv['value'] for dk, dv in draft.data.items() if dk == ok[11:])
                    elif ok[:8] == 'i_branch':
                        dict_object['branch'] = int(ov) if ov else None
                    else:
                        dict_object[match_key[1]] = ov
            if 'arrays' in request.session['temp_object_manager']:
                draft_arrays = ContractDrafts.objects if is_contract else TableDrafts.objects
                for a in request.session['temp_object_manager']['arrays']:
                    draft_arrays = draft_arrays.filter(user_id=request.user.id, data__parent_structure=a['id'])
                    owner = next(str(o['id']) for o in a['headers'] if o['name'] == 'Собственник')
                    my_draft_arrays = []
                    for da in draft_arrays:
                        if da.data[owner]['value'] == draft_id:
                            data = da.data
                            data['draft_id'] = da.id
                            my_draft_arrays.append(data)
                            da.active = False
                            da.save()
                    dict_object['array' + str(a['id'])] = my_draft_arrays

            task_funs.ctdo(date_delay, dict_object, request.user.id)
            message = 'Черновик отправлен в очередь ожидания. Объект будет создан/изменен при наступлении указанного времени<br>'
        else:
            # Мгновенное создание объекта
            @transaction.atomic
            def draft_in_obj(code, current_class):
                aaa = 8
                # Проверка системных параметров контракта
                is_saved, message, message_class, code, transaction_id, timestamp = interface_funs\
                    .save_contract_object(request, code, current_class, headers, source='draft') if is_contract else\
                    interface_funs.save_object(request, class_id, code, current_class, headers, source='draft')

                is_error = bool(message_class)
                if not is_error:
                    message = ''
                # Получим массивы
                if not is_error and 'arrays' in request.session['temp_object_manager']:
                    dict_type_prefix = {'float': 'i_float_', 'bool': 'chb_', 'string': 'ta_', 'link': 'i_link_',
                                        'date': 'i_date_', 'datetime': 'i_datetime_', 'file': 'i_filename_',
                                        'const': 's_alias_',
                                        'enum': 's_enum_', 'stage': 'i_stage_'}
                    for array in request.session['temp_object_manager']['arrays']:
                        drafts_arrays = draft_manager.filter(user_id=request.user.id, data__parent_structure=array['id'])
                        owner = next(str(h['id']) for h in array['headers'] if h['name'] == 'Собственник')
                        for da in drafts_arrays:
                            if da.data[owner]['value'] == draft_id:
                                dict_obj = {}
                                for dk, dv in da.data.items():
                                    if dk == 'parent_structure':
                                        dict_obj['class_id'] = dv
                                    elif dk == 'code':
                                        dict_obj['i_code'] = dv
                                    elif dk == 'branch':
                                        if dv:
                                            dict_obj['i_branch'] = dv
                                    else:
                                        h = next(h for h in array['headers'] if h['id'] == int(dk))
                                        if h['name'] == 'Собственник':
                                            dict_obj[dict_type_prefix[h['formula']] + dk] = str(code)
                                        else:
                                            dict_obj[dict_type_prefix[h['formula']] + dk] = str(dv['value'])
                                        if is_contract:
                                            for dvk, dvv in dv.items():
                                                if dvk.startswith('tp_id'):
                                                    for dvvk, dvvv in dvv.items():
                                                        dict_obj['i_stage_' + dvvk] = dvvv
                                my_request = convert_procedures.dict_to_post(dict_obj)
                                my_request.user = request.user
                                my_request.GET['class_id'] = array['id']
                                tom = {'id': array['id']}
                                if is_contract:
                                    tom['tps'] = session_procedures.atic(array['id'])
                                my_request.session['temp_object_manager'] = tom
                                current_class = header_manager.get(id=array['id'])
                                params = {'source': 'draft', 'parent_transact': transaction_id, 'timestamp': timestamp}
                                array_saved, arr_msg, msg_cls, arr_code, trans_id, timestamp = interface_funs\
                                .save_contract_object(my_request, da.data['code'], current_class, array['headers'],
                                                      **params) if is_contract else\
                                interface_funs.save_object(my_request, array['id'], da.data['code'], current_class,
                                                           array['headers'], **params)
                                is_saved = is_saved or array_saved
                                is_error = is_error or bool(msg_cls)
                                if is_error:
                                    message += arr_msg + '<br>'
                                    break
                                else:
                                    da.delete()
                        else:
                            continue
                        break
                    if is_error:
                        raise Exception(message)
                return is_saved, message, message_class
            try:
                is_saved, message, message_class = draft_in_obj(code, current_class)
            except Exception as ex:
                is_saved = False
                message = str(ex)
                message_class = 'text-red'

            if is_saved:
                message = 'Черновик успешно загружен в объект<br>'
                if draft_id:
                    draft_manager.get(id=draft_id).delete()
                    session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков

    elif 'b_send' in request.POST:
        User = get_user_model()
        is_send = False
        if request.POST['i_recepient']:
            try:
                recepiend_id = int(request.POST['i_recepient'])
            except ValueError:
                message = 'Некорректно указан ID получателя.\n'
            else:
                try:
                    recepient = User.objects.get(id=recepiend_id)
                except ObjectDoesNotExist:
                    message = 'Не найдет пользователь с ID = ' + request.POST['i_recepient']
                else:
                    is_send = True
                    draft = draft_manager.get(id=request.POST['i_id'])
                    draft.user_id = recepiend_id
                    draft.sender_id = request.user.id
                    draft.save()
                    # Если есть подчиненные массивы - перекинем и их
                    arrays = header_manager.filter(parent_id=draft.data['parent_structure'], formula='array').values('id')
                    for a in arrays:
                        owner = header_manager.filter(parent_id=a['id'], name='Собственник').values('id')[0]
                        draft_arrays = draft_manager.filter(user_id=request.user.id, data__parent_structure=a['id'])
                        for da in draft_arrays:
                            if da.data[str(owner['id'])]['value'] == draft.id:
                                da.sender_id = request.user.id
                                da.user_id = recepiend_id
                                da.save()
                    session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков
                    message = 'Черновик успешно отправлен'
        else:
            message = 'Не указан получатель черновика.\n'

        if not is_send:
            message += 'Черновик не был отправлен\n'
            message_class = 'text-red'

    # Вывод
    drafts = draft_manager.filter(user_id=request.user.id, data__parent_structure=class_id, active=True).order_by('-timestamp')
    # фильтр по draft_id
    if 'draft_id' in request.POST and request.POST['draft_id']:
        drafts = drafts.filter(id=int(request.POST['draft_id']))
    elif 'owner' in request.POST and request.POST['owner']:
        owner = int(request.POST['owner'])
        list_ids = []
        owner_id = next(str(h['id']) for h in headers if h['name'] == 'Собственник')
        for d in drafts:
            if d.data[owner_id]['value'] == owner:
                list_ids.append(d.id)
        drafts = draft_manager.filter(id__in=list_ids)
    # Поиск
    elif 'input_search' in request.POST and request.POST['input_search']:
        search = request.POST['input_search']
        # поиск по коду
        try:
            search_code = int(search)
        except ValueError:
            pass
        else:
            drafts = drafts.filter(data__code=search_code).select_related('sender')

    # Пагинация
    paginator = common_funs.paginator_standart(request, drafts, method='post')
    # конвертация черновиков в формат объектов
    vis_headers = [h for h in headers if h['is_visible']][:6]
    list_arrays = []
    if 'arrays' in request.session['temp_object_manager']:
        for array in request.session['temp_object_manager']['arrays']:
            dict_array = {'headers': array['vis_headers'], 'id': array['id'],
                          'owner': next(str(h['id']) for h in array['headers'] if h['name'] == 'Собственник')}
            dict_array['objects'] = list(draft_manager.filter(data__parent_structure=array['id'], user_id=request.user.id))
            list_arrays.append(dict_array)
    objects = []
    for p in paginator['items_pages']:
        obj = {}
        obj['type'] = request.session['temp_object_manager']['current_class']['formula']
        obj['timestamp'] = p.timestamp.strftime('%d.%m.%Y %H:%M:%S')
        obj['id'] = p.id
        obj['sender'] = p.sender.first_name + ' ' + p.sender.last_name if p.sender_id else None
        for k, v in p.data.items():
            if k == 'code':
                obj['code'] = v
            elif k == 'parent_structure':
                obj['parent_structure'] = v
            elif k == 'branch':
                obj['branch'] = v
            else:
                if k[:4] != 'dict':
                    k = int(k)
                    obj[k] = v
                    try:
                        h = next(cp for cp in headers if cp['id'] == k)
                    except StopIteration:
                        continue
                    else:
                        obj[k]['name'] = h['name']
                        obj[k]['type'] = h['formula']
                else:
                    obj[k] = v
        for la in list_arrays:
            obj[la['id']] = {'headers': la['headers']}
            i = 0
            array_objs = []
            while i < len(la['objects']):
                if la['objects'][i].data[la['owner']]['value'] == obj['id']:
                    data = la['objects'][i].data
                    for dk in data.keys():
                        if dk in ('parent_structure', 'code', 'branch'):
                            continue
                        try:
                            data[dk]['type'] = next(h['formula'] for h in la['headers'] if h['id'] == int(dk))
                        except StopIteration:
                            pass
                    data['id'] = la['objects'][i].id
                    array_objs.append(data)
                    del la['objects'][i]
                else:
                    i += 1
            obj[la['id']]['objects'] = array_objs
        objects.append(obj)
    convert_funs.prepare_table_to_template(vis_headers, objects, request.user.id, is_contract)
    # добавим техпроцессы
    tp_lcf = []  #tech_rpcoess list_control_field
    if is_contract and request.session['temp_object_manager']['tps']:
        tp_lcf = [tp['cf'] for tp in request.session['temp_object_manager']['tps']]
    # url = common_funs.edit_url(request)
    session_funs.crqd(request, is_contract)  #  контрольный пересчет количества черновиков
    users = get_user_model().objects.all()[:10]

    ctx = {
        'title': title,
        'class': current_class,
        'objects': objects,
        'headers': headers,
        'vis_headers': vis_headers,
        'paginator': paginator,
        'message': message,
        'message_class': message_class,
        'users': users,
        'is_contract': str(is_contract).lower(),
        'lcf': tp_lcf
    }
    return render(request, 'drafts/draft.html', ctx)