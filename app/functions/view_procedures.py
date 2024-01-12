import json
import re
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect


# Декоратор авторизации
def is_auth(fun):
    def wrapper(request):
        if request.user.is_authenticated:
            return fun(request)
        else:
            return HttpResponse('Вы не авторизованы. Пожалуйста авторизуйтесь')
    return wrapper


# Декоратор авторизации, отправляющий на страницу авторизации
def is_auth_app(fun):
    def wrapper(request):
        if request.user.is_authenticated:
            return fun(request)
        else:
            return HttpResponseRedirect(reverse('login'))
    return wrapper


# декоратор поиска class_id для страниц объектов
def is_class_id(fun):
    def wrapper(request):
        its_ok = True
        if 'class_id' not in request.GET:
            its_ok = False
        elif not request.GET['class_id']:
            its_ok = False
        else:
            try:
                int(request.GET['class_id'])
            except ValueError:
                its_ok = False
        if its_ok:
            return fun(request)
        else:
            return HttpResponse('Некорректно задан ID класса')
    return wrapper


# Декоратор ошибки. для функции с одним аргументом - реквестом
def if_error(fun):
    def wrapper(req):
        try:
            result = fun(req)
        except Exception as ex:
            return HttpResponse('Ошибка ' + str(ex))
        else:
            return result
    return wrapper


def if_error_json(fun):
    def wrapper(req):
        try:
            result = fun(req)
        except Exception as ex:
            err = {'error': 'Ошибка - "' + str(ex) + '"'}
            return HttpResponse(json.dumps(err, ensure_ascii=False), content_type="application/json")
        else:
            return result
    return wrapper


# конвертирование формата в джейсон из строкового при работе с объектами
def convert_in_json(k, v):
    if v:
        if re.match(r'^(i_link|i_float|chb|s_alias)', k):
            v = json.loads(v.lower())
    else:
        v = None
    return v


# декоратор пропуска суперадминов - временно не используется
def just_superadmin(fun):
    def wrapper(req):
        if req.user.is_superuser:
            return fun(req)
        else:
            return HttpResponseRedirect(reverse('login'))
    return wrapper


# декоратор пропуска тимлидов
def just_teamlead(fun):
    def wrapper(req):
        if req.user.is_staff:
            return fun(req)
        else:
            return HttpResponseRedirect(reverse('login'))
    return wrapper

