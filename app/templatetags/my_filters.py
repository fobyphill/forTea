import json
import re

from django import template

from app.functions import template_funs

register = template.Library()

# Фильтр получения значения по ключу в словаре
# Синтаксис {{ mydict|get_item:item.NAME }}
@register.filter
def get_item(dictionary, key):
    try:
        result = dictionary.get(key)
        if not result:
            result = dictionary.get(str(key))
    except Exception:
        result = None
    return result

# Вывод данных в виде ветки дерева. Вход - запись верхнего уровня
@register.filter
def get_children(item, result=''):
    icon_folder = '<img src="/static/img/pics/folder_closed_50.png" width=20px>'
    icon_book = '<img src="/static/img/pics/book_50.png" width=20px>'
    icon_home = '<img src="/static/img/pics/home_50.png" width=20px>'
    icon_star = '<img src="/static/img/pics/star_50.png" width=20px>'
    icon_pen = '<img src="/static/img/pics/pen_50.png" width=20px>'
    icon_tree = '<img src="/static/img/pics/tree_32_blue.png" width=20px>'
    icon_array = '<img src="/static/img/pics/array_50.png" width=15px>'
    dict_icon = {'folder': icon_folder, 'contract': icon_pen, 'table': icon_book, 'alias': icon_home,
                 'array': icon_array, 'dict': icon_star, 'tree': icon_tree}
    icon = dict_icon[item['formula']]
    # Добавим символ "плюс" для классов с детьми
    if 'children' in item:
        icon = '+' + icon
    # внесем отличия для словарей
    s_info = 's_info'
    item_id = str(item['id'])
    if item['formula'] == 'dict':
        s_info += '_dict'
        item_id = '_dict' + item_id
        is_dict = 'true'
    else:
        is_dict = 'false'
    begin = '<li id="unit' + item_id + '" onclick="show_hide_branch(this); select_unit(this, '+ is_dict +')">'
    middle = icon + '&nbsp;' + item['name'] + ' <b>ID:</b> ' + str(item['id'])
    end = '</li><span id="' + s_info + str(item['id']) + '" class="tag-invis">' + json.dumps(item) + '</span>'
    if item['formula'] != 'folder':
        a_href = '<a href="manage-class-tree?is_dict=&i_id=' if item['formula'] == 'dict' else '<a href="manage-class-tree?i_id='
        middle = a_href + str(item['id']) + '">' + middle + '</a>'
    if 'children' in item:
        end += '<ul class="tag-invis">'
        for ch in item['children']:
            end = get_children(ch, end)
        end += '</ul>'
    result += begin + middle + end
    return result

# вывод данных ветки дерева для управления контрактов
@register.filter
def get_children_contract(item, result=''):
    icon_folder = '<img src="/static/img/pics/folder_closed_50.png" width=20px>'
    icon_book = '<img src="/static/img/pics/book_50.png" width=20px>'
    icon_home = '<img src="/static/img/pics/home_50.png" width=20px>'
    icon_star = '<img src="/static/img/pics/star_50.png" width=20px>'
    icon_pen = '<img src="/static/img/pics/pen_50.png" width=20px>'
    icon_tree = '<img src="/static/img/pics/tree_32_blue.png" width=20px>'
    icon_array = '<img src="/static/img/pics/array_50.png" width=20px>'
    tp_tree = '<img src="/static/img/pics/tp_50.png" width=15px>'
    dict_icon = {'folder': icon_folder, 'contract': icon_pen, 'table': icon_book, 'alias': icon_home,
                 'array': icon_array, 'dict': icon_star, 'tree': icon_tree, 'tp': tp_tree}
    icon = dict_icon[item['formula']]
    # Добавим символ "плюс" для классов с детьми
    if 'children' in item:
        icon = '+' + icon
    s_info = 's_info'
    item_id = str(item['id'])
    if item['formula'] == 'dict':
        s_info += '_dict'
        item_id = '_dict' + item_id
        is_dict = 'true'
    elif item['formula'] in ('techprocess', 'tp'):
        s_info += '_tp'
        item_id = '_tp' + item_id
        is_dict = 'false'
    else:
        is_dict = 'false'
    location = 't' if item['formula'] == 'tp' else 'd' if item['formula'] == 'dict' else 'c'
    begin = '<li id="unit' + item_id + '" onclick="show_hide_branch(this); select_unit(this, '+ is_dict +')">'
    middle = icon + '&nbsp;' + item['name'] + ' <b>ID:</b> ' + str(item['id'])
    end = '</li><span id="' + s_info + str(item['id']) + '" class="tag-invis">' + json.dumps(item) + '</span>'
    if item['formula'] != 'folder':
        a_href = '<a href="manage-contracts?is_dict=&i_id=' if item['formula'] == 'dict' else '<a href="manage-contracts?i_id='
        middle = a_href + str(item['id']) + '&location=' + location + '">' + middle + '</a>'
    if 'children' in item:
        end += '<ul class="tag-invis">'
        for ch in item['children']:
            end = get_children_contract(ch, end)
        end += '</ul>'
    result += begin + middle + end
    return result

# Конверим джейсон в строку в шаблоне страницы
@register.filter
def json_dumps(dict):
    try:
        result = json.dumps(dict, ensure_ascii=False)
    except Exception as ex:
        result = 'Ошибка. ' + str(ex)
    return result


# Конверим строку в джейсон в шаблоне страницы
@register.filter
def json_loads(dict):
    return json.loads(dict)


# конвертим строку даты в российский формат  д.м.Г. ч:м
@register.filter
def datetime_string_to_russian(datetime_string):
    return datetime_string[8:10] + '.' + datetime_string[5:7] + '.' + datetime_string[:4] + ' ' + datetime_string[11:13]\
        + ':' + datetime_string[14:]


# Конвертим строку в дату российского формата д.м.Г
@register.filter
def date_string_to_russin(date_string):
    if date_string and len(date_string) >= 10:
        return date_string[8:10] + '.' + date_string[5:7] + '.' + date_string[:4]
    else:   return ''


# # конвертим строковое датавремя в российский формат д.м.Г ч:м
# def datetime_string_to_russian(datetime_string):
#     if datetime_string and len(datetime_string) >= 16:
#         return datetime_string[8:10] + '.' + datetime_string[5:7] + '.' + datetime_string[:4] + ' ' \
#                + datetime_string[11:]
#     else:   return ''


# Конвертим таймдельту в строковое выражение периода на русском tdts = timedelta to string
@register.filter
def tdts(td):
    days = 'день'
    if 5 > td.days % 10 > 1:
        days = 'дня'
    elif td.days % 10 > 5 or td.days % 10 == 0:
        days = 'дней'
    return re.sub(r'day(?:s|)', days, str(td))


# gcft - get children from tree. Извлекает детей из ветки дерева, рисует html
@register.filter
def gcft(item, branch):
    return template_funs.tree_to_html(item, branch)


# gcftto - get children from tree to objects. Извлекает детей из ветки дерева на странице объектов
@register.filter
def gcftto(item, branch):
    return template_funs.tree_to_html(item, branch, is_object=True)

# gpft - get props from tree
@register.filter
def gpft(item, branch):
    if branch:
        code = branch['code']
    else:
        code = 0
    result = '<div class=row'
    # отметим активную ветку
    if code == item['code']:
        result += ' table-active'
    result += '">'
    # Добавим свойства
    if 'props' in item and item['props']:
        iter_counter = 0
        for k, v in item['props'].items():
            result += '<div class="col-4 text-center">' + str(v) + '</div>'
            iter_counter += 1
            if iter_counter > 3:
                break
    result += '</div>'
    # добавим детей
    if 'children' in item and item['opened']:
        for ch in item['children']:
            result += gpft(ch, branch)
    return result

@register.filter
def add_spaces(string):
    return string + '&emsp;&emsp;'

@register.filter
def get_link(data):
    try:
        name_field = 'Наименование' if data['type'] == 'table' else 'Дата и время записи'
        for k, v in data.items():
            if k in ('code', 'parent_structure', 'type'):
                continue
            if v['name'] == name_field:
                return v['value']
        return ''
    except Exception:
        return ''
