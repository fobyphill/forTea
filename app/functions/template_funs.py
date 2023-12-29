# Превращаем дерево в html
# Опциональные параметры: is_object = True / False. По умолчанию False
def tree_to_html(item, branch, **params):
    is_object = True if 'is_contract' in params and params['is_contract'] else False
    if branch:
        code = branch['code']
    else:
        code = 0
    icon_closed = '<img src="/static/img/pics/folder_closed_50.png" width=20px>'
    icon_opened = '<img src="/static/img/pics/folder_opened_50.png" width=20px>'
    # Добавим символ "плюс" для классов с детьми
    if 'children' in item:
        if item['opened']:
            icon = '-' + icon_opened
        else:   icon = '+' + icon_closed
    else:   icon = icon_closed
    # отметим активную ветку
    if code == item['code']:
        class_style = 'class="table-active pb-1"'
        if code and is_object:
            button_edit = '<button class="btn btn-outline-primary" style="padding: 0; float: right;">Редактировать</button>'
        else:   button_edit = ''
    else:
        class_style = ''
        button_edit = ''
    item_code = str(item['code'])
    result = '<li id="unit' + item_code + '" onclick="select_branch(this)"' + class_style + '>' + icon \
             + str(item['code']) + ' ' + item['name'] + button_edit + '</li>'
    # добавим детей
    if 'children' in item and item['opened']:
        result += '<ul>'
        for ch in item['children']:
            result += tree_to_html(ch, branch, is_object=is_object)
        result += '</ul>'
    return result