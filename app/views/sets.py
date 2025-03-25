from django.shortcuts import render
from app.functions import view_procedures, session_funs
from app.models import UserSets, MainPageConst


@view_procedures.is_auth_app
def sets(request):
    message = ''
    my_sets = UserSets.objects.filter(user_id=request.user.id)
    if my_sets:
        my_sets = my_sets[0]
    else:
        my_sets = UserSets(user_id=request.user.id)
        my_sets.save()
    const_main_page = MainPageConst.objects.all() if request.user.is_staff and request.user.is_superuser else []
    if 'b_save' in request.POST:
        my_sets.pagination = int(request.POST['i_pagination'])
        my_sets.main_page = request.POST['i_main_page']
        my_sets.save()
        message = 'Настройки сохранены'
        request.session['pagination'] = my_sets.pagination

        # выполним сохранение констант главной страницы
        if request.user.is_staff and request.user.is_superuser:
            for cmp in const_main_page:
                cmp.name = request.POST['ta_name_' + str(cmp.id)]
                cmp.value = request.POST['ta_value_' + str(cmp.id)]
                cmp.save()
            # Если были добавлены новые константы - сохраним их
            new_const_saved = False
            if 'ta_name_new_on' in request.POST:
                MainPageConst(user_login=True, name=request.POST['ta_name_new_on'], value=request.POST['ta_value_new_on']).save()
                new_const_saved = True
            if 'ta_name_new_off' in request.POST:
                MainPageConst(user_login=False, name=request.POST['ta_name_new_off'], value=request.POST['ta_value_new_off']).save()
                new_const_saved = True
            if new_const_saved:
                const_main_page = MainPageConst.objects.all()
    else:
        for cmp in const_main_page:
            if f'b_delete_{cmp.id}' in request.POST:
                cmp.delete()
                const_main_page = MainPageConst.objects.all()
                message = 'Константа была удалена'
    main_page_on = []
    main_page_off = []
    if request.user.is_superuser and request.user.is_staff:
        for cmp in const_main_page:
            if cmp.user_login:
                main_page_on.append(cmp)
            else:
                main_page_off.append(cmp)
    session_funs.check_quant_tasks(request)
    ctx = {
        'title': 'Настройки',
        'sets': my_sets,
        'message': message,
        'main_page_on': main_page_on,
        'main_page_off': main_page_off
    }
    return render(request, 'sets/sets.html', ctx)