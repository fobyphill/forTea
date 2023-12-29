# Пагинация
import re
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Max
from app.models import Objects, Designer

# Пагинация классическая
def paginator_standart(request, Items, **params):
    is_post = False
    if 'method' in params:
        is_post = True if params['method'] == 'post' else False
    req = request.POST if is_post else request.GET
    # Работа с пагинатором
    if 'q_items_on_page' in req:
        q_items_on_page = int(req['q_items_on_page'])
    else:
        q_items_on_page = 10
    paginator = Paginator(Items, q_items_on_page)
    if 'page' in req and req['page']:
        page_num = int(req['page'])
    else:
        page_num = 1
    try:
        items_pages = paginator.page(page_num)
    except PageNotAnInteger:
        items_pages = paginator.page(1)
    except EmptyPage:
        items_pages = paginator.page(paginator.num_pages)
    ctx_pagination = {
        'items_pages': items_pages,
        'page_num': page_num,
        'pages_count': paginator.num_pages,
        'q_items_on_page': q_items_on_page
    }
    return ctx_pagination

def paginator_classes(request, items):
    # Количество записей на странице
    if 'q_items_on_page' in request.GET:
        q_items_on_page = int(request.GET['q_items_on_page'])
    else:
        q_items_on_page = 10

    # Получим количество записей, выводимое на страницу
    paginator = Paginator(items, q_items_on_page)

    if 'page' in request.GET and len(request.GET['page']) > 0:
        page_num = int(request.GET['page'])
        if page_num > paginator.num_pages:  page_num = paginator.num_pages
    else:
        page_num = 1
    try:
        items_pages = paginator.page(page_num)
    except PageNotAnInteger:
        items_pages = paginator.page(1)
    except EmptyPage:
        items_pages = paginator.page(paginator.num_pages)
    ctx_pagination = {
        'items_pages': items_pages,
        'page_num': page_num,
        'pages_count': paginator.num_pages,
        'q_items_on_page': q_items_on_page
    }
    return ctx_pagination

# пагинатор объектов. Вход - массив объектов по имени. Выход - список айди объектов
def paginator_object(items, q_items_on_page=10, page_num=1):
    # Работа с пагинатором
    paginator = Paginator(items, q_items_on_page)
    try:
        items_pages = paginator.page(page_num)
    except PageNotAnInteger:
        items_pages = paginator.page(1)
    except EmptyPage:
        items_pages = paginator.page(paginator.num_pages)
    items_codes = [ip['code'] if type(ip) is dict else ip.code for ip in items_pages]
    ctx_pagination = {
        'items_pages': items_pages,
        'items_codes': items_codes,
        'page_num': page_num,
        'pages_count': paginator.num_pages,
        'q_items_on_page': q_items_on_page
    }
    return ctx_pagination

# Обрезка лишних данных в адресе
def edit_url(request):
    url = re.sub(r'&page=.*&', '&', request.META['QUERY_STRING']) # о странице
    url = re.sub(r'&page=.*$', '', url)
    url = re.sub(r'&page_num=.*&', '&', url)
    url = re.sub(r'&page_num=.*$', '', url)
    url = re.sub(r'&b_save.*?&', '&', url)
    url = re.sub(r'&b_save.*?$', '', url)
    url = re.sub(r'&b_delete.*?&', '&', url)
    url = re.sub(r'&b_delete.*?$', '', url)
    return url