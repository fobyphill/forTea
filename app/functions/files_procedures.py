import os



# Получить путь к файлу по его имени, айди класса, расположению и "черновик/нет"
def get_file_path(filename, class_id, **params):
    # обработка опциональных параметров
    if filename:
        is_draft = True if 'is_draft' in params and params['is_draft'] else False
        location = 'contract_' if 'location' in params and params['location'] == 'contract' else 'table_'
        location += class_id
        date_save = filename[4:8] + '-' + filename[2:4] + '-' + filename[:2]
        path = 'database_files_'
        if is_draft:
            path += 'drafts'
        else:
            path = 'static/' + path + 'history'
        return path + '/' + location + '/' + date_save + '/' + filename
    else:
        return ''