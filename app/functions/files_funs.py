import os, re, shutil
from datetime import datetime
from app.other.global_vars import root_folder


# Удаление файла
# Вход: класс айди - строка, name_file - название файла, kwargs: folder - расположение файла - contract или table
def delete_file(class_id, file_name, **kwargs):
    general_folder = 'database_files_history'
    class_folder = kwargs['folder'] + '_' + str(class_id)
    date_folder = file_name[4:8] + '-' + file_name[2:4] + '-' + file_name[:2]
    current_dir = os.path.join(root_folder, 'static', general_folder, class_folder, date_folder)
    if os.path.exists(current_dir):
        os.remove(os.path.join(current_dir, file_name))


# Удалить файл из хранилища черновиков
def delete_draft_file(file_name, class_id, is_contract=False):
    date_folder = file_name[4:8] + '-' + file_name[2:4] + '-' + file_name[:2]
    int_folder = 'contract_' if is_contract else 'table_'
    path = os.path.join(root_folder, 'database_files_draft', int_folder + class_id, date_folder, file_name)
    if os.path.exists(path):
        os.remove(path)


# Копирует файл из папки черновики в историю и чистит его в черновиках
# cffdth - copy file from draft to history
# filename - строка. техническое имя файла вида - 05102022154532file.ext
# Опциональные параметры:
# rout [htd, dtd, dth]. Копирует [HistToDraft, DraftToDraft, DraftToHist]. В случае DTH удаляет файл
# location - table/contract. Default table
def cffdth(filename, class_id, **params):
    str_class_id = str(class_id)
    # reverse = 'reverse' in params and params['reverse']
    rout = params['rout'] if 'rout' in params else 'dth'
    location = 'contract_' if 'location' in params and params['location'] == 'contract' else 'table_'
    old_root_folder = 'database_files_draft' if rout[0] == 'd' else os.path.join('static', 'database_files_history')
    new_root_folder = 'database_files_draft' if rout[2] == 'd' else os.path.join('static', 'database_files_history')
    folder_date = filename[4:8] + '-' + filename[2:4] + '-' + filename[:2]
    new_timestamp = datetime.strftime(datetime.today(), '%d%m%Y%H%M%S')
    new_folder_date = new_timestamp[4:8] + '-' + new_timestamp[2:4] + '-' + new_timestamp[:2]
    new_filename = new_timestamp + filename[14:]
    file_from = os.path.join(root_folder, old_root_folder, location + str_class_id, folder_date, filename)
    file_to = os.path.join(root_folder, new_root_folder, location + str_class_id, new_folder_date, new_filename)
    folder_to = os.path.dirname(file_to)
    if not os.path.exists(folder_to):
        os.makedirs(folder_to)
    try:
        shutil.copyfile(file_from, file_to)
    except FileNotFoundError:
        return 'Ошибка. Файл не найден'
    else:
        if rout == 'dth':
            os.remove(file_from)
    return new_filename


# Загрузить файл на сервер
# вход: реквест, ключ файла - имя инпута, типа i_file_315, is_contract
# Опциональные параметры params: root_folder - Указать его только в том случае, если загружаем файл в черновики.
# Значение - database_files_draft
# Выход: result (символ), имя файла, сообщение
# Расшифровка выходной переменной result:
# o - ok, m - missing (нет файла для загрузки), e - error(ошибка загрузки), f - format (неподходящий формат файла)
def upload_file(request, file_key, file_name, str_class_id, is_contract=False, **params):
    # Опциональные параметры
    my_root_folder = params['root_folder'] if 'root_folder' in params else 'database_files_history'
    message = ''
    if file_key in request.FILES.keys():
        # Проверим, не относится ли файл к исполнительным
        find_ext = re.match(r'.*\.(\w+)$', request.FILES[file_key].name)
        if not find_ext:
            message = 'Файл ' + request.FILES[file_key].name + ' использует расширение неизвестного типа, поэтому не может быть загружен\n'
            return 'f', file_name, message
        ext = re.match(r'.*\.(\w+)$', request.FILES[file_key].name)[1]
        if ext in ['exe', 'com', 'bat']:
            message = 'Файл ' + request.FILES[file_key].name + ' является исполнительным, поэтому не может быть загружен\n'
            return 'f', file_name, message
        location = 'contract' if is_contract else 'table'
        file = request.FILES[file_key]
        file_name = datetime.today().strftime('%d%m%Y%H%M%S') + file.name
        folder_name = location + '_' + str_class_id
        file.name = file_name
        list_dir = [my_root_folder, folder_name, datetime.today().strftime('%Y-%m-%d')]
        dir = ''
        if list_dir[0] == 'database_files_history':
            list_dir.insert(0, 'static')
        list_dir.insert(0, root_folder)
        for ld in list_dir:
            dir = os.path.join(dir, ld)
            if not os.path.exists(dir):
                os.mkdir(dir)
        with open(os.path.join(dir, file.name), 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        result = 'o'
    else:
        result = 'm'
        message = 'Файл не был загружен'
    return result, file_name, message


def add_to_log(text):
    timestamp = datetime.strftime(datetime.today(), '%d.%m.%Y %H:%M:%S')
    log_path = os.path.join(root_folder, 'log.txt')
    f = open(log_path, 'a')
    f.write(text + '  ' + timestamp + '\n')
    f.close()