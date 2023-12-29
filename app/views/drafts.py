from django.core.exceptions import ObjectDoesNotExist

import app.functions.contract_funs
import app.functions.files_funs

from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render
from app.functions import view_procedures, session_funs, interface_funs, convert_funs, common_funs, draft_funs
from app.models import Designer, TableDrafts, Contracts, ContractDrafts
from django.contrib.auth import get_user_model


@view_procedures.is_auth_app
def table_draft(request):
    is_contract = True if request.path[1] == 'c' else False
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
    class_type = 'контракт' if is_contract else 'справочник'
    try:
        current_class = header_manager.filter(id=class_id, formula__in=('table', 'contract', 'array')).select_related('parent').get()
    except:
        return HttpResponse('не найден ' + class_type + ' с ID = ' + request.GET['class_id'])
    exclude_names = ('parent_branch', 'business_rule', 'link_map', 'trigger')
    headers = list(header_manager.filter(parent_id=class_id).exclude(name__in=exclude_names).exclude(formula='array').values())
    code = int(request.POST['i_code']) if 'i_code' in request.POST and request.POST['i_code'] else None
    draft_id = int(request.POST['i_id']) if 'i_id' in request.POST and request.POST['i_id'] else None

    title = 'массива' if current_class.formula == 'array' else class_type + 'а'
    title = 'Черновики ' + title + ' "' + current_class.name + '"' + '"' + ' ID: ' + request.GET['class_id']
    message = ''
    message_class = ''

    # Кнопка "Сохранить"
    if 'b_save' in request.POST:
        is_saved = True
        # Редактируем
        if 'i_id' in request.POST and request.POST['i_id']:
            is_change, message = interface_funs.draft_edit(request, draft_id, is_contract)
            if not is_change:   message_class = 'text-red'
            is_saved = is_change
        # Создаем новый черновик
        else:
            msg = interface_funs.make_graft(request, code, is_contract)[1]
            if msg: message_class = 'text-red'
            message = 'Создан новый черновик\n' + msg
        if is_saved:
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

    elif 'b_delete' in request.POST:
        del_draft = draft_manager.get(id=draft_id)
        # Если есть файл - удалим его
        for h in headers:
            if h['formula'] == 'file':
                header_id = str(h['id'])
                if header_id in del_draft.data.keys():
                    file_name = del_draft.data[header_id]['value']
                    if file_name:
                        app.functions.files_funs.delete_draft_file(file_name, request.GET['class_id'], is_contract)
        del_draft.delete()  #  Удалим запись
        message = 'Черновик удален'
        session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков

    elif 'b_delete_dict' in request.POST and request.POST['delete_dict']:
        dict_key = 'dict_' + request.POST['delete_dict']
        draft = draft_manager.get(id=draft_id)
        draft.data[dict_key] = {}
        draft.timestamp = datetime.now()
        draft.save()
        message = 'Черновик сохранен\n'

    elif 'b_in_object' in request.POST:
        is_saved = False
        # Проверка системных параметров контракта
        if is_contract:
            hwa = [h for h in headers if h['formula'] != 'array']
            is_saved, message, message_class = interface_funs.save_contract_object(request, code, current_class,
                                                                                       hwa, source='draft')[:3]
        else:
            is_saved, message, message_class = interface_funs.save_object(request, class_id, code, current_class,
                                                                             headers, source='draft')[:3]
        if is_saved and draft_id:
            draft_manager.get(id=draft_id).delete()
            session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков

    elif 'b_send' in request.POST:
        User = get_user_model()
        is_send = False
        if request.POST['i_recepient']:
            recepiend_id = None
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
                    session_funs.update_draft_tree(request, is_contract)  # обновим меню черновиков
                    message = 'Черновик успешно отправлен'
        else:
            message = 'Не указан получатель черновика.\n'

        if not is_send:
            message += 'Черновик не был отправлен\n'
            message_class = 'text-red'

    # Вывод
    drafts = draft_manager.filter(user_id=request.user.id, data__parent_structure=class_id).order_by('-timestamp')
    # Поиск
    if 'input_search' in request.POST and request.POST['input_search']:
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
    objects = []
    for p in paginator['items_pages']:
        obj = {}
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
        objects.append(obj)
    convert_funs.prepare_table_to_template([h for h in headers if h['is_visible']], objects, request.user.id, is_contract)
    url = common_funs.edit_url(request)
    session_funs.crqd(request, is_contract)  #  контрольный пересчет количества черновиков
    users = get_user_model().objects.all()[:10]

    ctx = {
        'title': title,
        'class': current_class,
        'objects': objects,
        'headers': headers,
        'paginator': paginator,
        'path_without_page': url,
        'message': message,
        'message_class': message_class,
        'users': users
    }
    return render(request, 'drafts/draft.html', ctx)