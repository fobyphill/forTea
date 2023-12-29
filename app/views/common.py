from datetime import datetime
from django.contrib import auth
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from app.functions import session_funs, convert_funs, tech_funs
from app.models import Designer, MainPageConst


def login_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse("index"))
    else:
        user_count = auth.get_user_model().objects.all().count()
        if not user_count:
            tech_funs.initialisation()
        return render(request, 'common/login.html')

def logout(request):
    if request.user.is_authenticated:
        auth.logout(request)
    return HttpResponseRedirect(reverse("login"))

def index(request):
    if request.user.is_authenticated:
        main_page_const = list(MainPageConst.objects.all().values())
        for mpc in main_page_const:
            convert_funs.deep_formula(mpc, [mpc, ], request.user.id)
        ctx = {
            'title': 'Главная страница',
            'alias': main_page_const,
        }
        return render(request, 'index.html', ctx)
    elif request.method == 'POST':
        user = auth.authenticate(username=request.POST['email'], password=request.POST['password'])
        if user:
            auth.login(request, user)
            request.session['hour'] = datetime.today().hour
            session_funs.add_data_types(request)  # ДОбавим в сессию типы данных
            session_funs.add_class_types(request)  # добавим в сессию типы классов
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, 'common/login.html', {'message': 'Неверный логин или пароль. Попробуйте еще раз.'})
    else:
        return HttpResponseRedirect(reverse("login"))
