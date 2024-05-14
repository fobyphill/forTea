import json, datetime
import pandas as pd
from django.contrib.auth import get_user_model

from django.db.models import Value, CharField, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from app.functions import common_funs, session_funs
from app.models import RegName, RegistratorLog, TechProcess


def hist_reg(request):
    if request.user.is_authenticated:
        message = ''
        message_class = ''

        # обновим временные данные
        if session_funs.new_temp_data(request):
            request.session['temp_data']['data']['reg_names'] = list(RegName.objects.all().values())
        # Период
        now = datetime.datetime.today() + datetime.timedelta(minutes=1)
        one_month_ago = now - datetime.timedelta(days=31)
        one_month_ago = one_month_ago.strftime('%Y-%m-%dT%H:%M:%S')
        now = now.strftime('%Y-%m-%dT%H:%M:%S')
        date_in = request.GET['i_date_in'] if 'i_date_in' in request.GET and request.GET[
            'i_date_in'] else one_month_ago
        date_out = request.GET['i_date_out'] if 'i_date_out' in request.GET and request.GET[
            'i_date_out'] else now

        # вывод
        reg_log = RegistratorLog.objects.filter(date_update__gte=date_in, date_update__lte=date_out)\
            .order_by('-id').annotate(reg_data=Value('', output_field=CharField()),href=Value('', output_field=CharField()),
                                      reg_name_data=Value('', output_field=CharField()), user_data=Value('', output_field=CharField()))
        # валидация фильтров:
        is_valid = True
        if 'i_filter_reg' in request.GET and request.GET['i_filter_reg']:
            try:
                int(request.GET['i_filter_reg'])
            except ValueError:
                message += 'Некорректно указан ID регистратора\n'
                message_class = 'text-red'
                is_valid = False
        if 'i_filter_class' in request.GET and request.GET['i_filter_class']:
            try:
                int(request.GET['i_filter_class'])
            except ValueError:
                message += 'Некорректно указан ID класса\n'
                message_class = 'text-red'
                is_valid = False
        if 'i_filter_object' in request.GET and request.GET['i_filter_object']:
            try:
                int(request.GET['i_filter_object'])
            except ValueError:
                message += 'Некорректно указан код объекта\n'
                message_class = 'text-red'
                is_valid = False
        filter_user = None
        if 'i_filter_user' in request.GET and request.GET['i_filter_user']:
            try:
                filter_user = int(request.GET['i_filter_user'])
            except ValueError:
                message += 'Некорректно указан ID пользователя\n'
                message_class = 'text-red'
                is_valid = False
        if 'i_id' in request.GET and request.GET['i_id']:
            try:
                int(request.GET['i_id'])
            except ValueError:
                message += 'Некорректно указан ID параметра объекта\n'
                message_class = 'text-red'
                is_valid = False
        if 'i_name' in request.GET and request.GET['i_name']:
            try:
                int(request.GET['i_name'])
            except ValueError:
                message += 'Некорректно указан ID заголовка объекта\n'
                message_class = 'text-red'
                is_valid = False
        if is_valid:
            # Регистратор
            if 'i_filter_reg' in request.GET and request.GET['i_filter_reg']:
                reg_log = reg_log.filter(reg_name_id=request.GET['i_filter_reg'])
            # Класс
            if 'i_filter_class' in request.GET and request.GET['i_filter_class']:
                class_id = int(request.GET['i_filter_class'])
                reg_log = reg_log.filter(Q(json_class=class_id)
                                         | Q(json_income__class_id=class_id))
            # Расположение
            if 's_location' in request.GET and request.GET['s_location'] != 'all':
                reg_log = reg_log.filter(Q(json__location=request.GET['s_location']) |
                                         Q(json_income__location=request.GET['s_location']))
            # тип
            if 's_type' in request.GET and request.GET['s_type'] != 'all':
                reg_log = reg_log.filter(Q(json__type=request.GET['s_type']) |
                                         Q(json_income__type=request.GET['s_type']))
            # Объекты
            if 'i_filter_object' in request.GET and request.GET['i_filter_object']:
                code = int(request.GET['i_filter_object'])
                reg_log = reg_log.filter(Q(json__code=code) | Q(json_income__code=code))
            # Параметр
            if 'i_id' in request.GET and request.GET['i_id']:
                id = int(request.GET['i_id'])
                reg_log = reg_log.filter(Q(json__id=id) | Q(json__id=id))
            # Заголовок
            if 'i_name' in request.GET and request.GET['i_name']:
                name_id = int(request.GET['i_name'])
                reg_log = reg_log.filter(Q(json__name=name_id) | Q(json_income__name=name_id))
            # Транзакция
            if 'i_transact' in request.GET and request.GET['i_transact']:
                reg_log = reg_log.filter(transact_id__icontains=request.GET['i_transact'].lower())
            # родительская транзакция
            if 'i_parent_transact' in request.GET and request.GET['i_parent_transact']:
                reg_log = reg_log.filter(parent_transact_id__icontains=request.GET['i_parent_transact'].lower())
            # Пользователь
            if filter_user:
                reg_log = reg_log.filter(user_id=filter_user)
        # Входящие / исходящие
        if 's_in_out' in request.GET and request.GET['s_in_out'] == 'in':
            reg_log = reg_log.filter(json_income__isnull=False)
            in_out = 'in'
        elif 's_in_out' in request.GET and request.GET['s_in_out'] == 'out':
            reg_log = reg_log.filter(json__isnull=False)
            in_out = 'out'
        else:
            in_out = 'all'
        # только значения
        if 'chb_only_values' in request.GET and request.GET['chb_only_values'] == 'on':
            only_values = True
        else:    only_values = False

        # пагинация
        paginator = common_funs.paginator_standart(request, reg_log)
        # постобработка
        list_data = []
        users = get_user_model().objects.filter(id__in=[ip.user_id for ip in paginator['items_pages']])\
            .values('id', 'first_name', 'last_name')
        reg_names = request.session['temp_data']['data']['reg_names']
        current_user = {'id': 0}
        for ip in paginator['items_pages']:
            reg_data = {}
            if ip.state_income: reg_data['Входящее состояние'] = ip.state_income
            if ip.state:    reg_data['Текущее состояние'] = ip.state
            if ip.fact_income: reg_data['Входящее фактическое значение'] = ip.fact_income
            if ip.fact:    reg_data['Фактическое значение'] = ip.fact
            if ip.delay_income: reg_data['delay_in'] = ip.delay_income
            if ip.delay:    reg_data['delay_out'] = ip.delay
            # добавим инфу о юзере
            if current_user['id'] != ip.user_id:
                current_user = next(u for u in users if u['id'] == ip.user_id)
            ip.user_data = current_user['first_name'] + ' ' + current_user['last_name']
            ip.reg_name_data = next(rn['name'] for rn in reg_names if rn['id'] == ip.reg_name_id)
            # ссылка на объект
            if ip.json_income:
                json_href = ip.json_income
            elif ip.json:
                json_href = ip.json
            else:
                json_href = None
            # формируем ссылку
            if json_href and 'type' in json_href and 'class_id' in json_href:
                # ссылка на объект
                if 'code' in json_href:
                    if json_href['type'] == 'dict':
                        href = 'dictionary'
                    elif json_href['type'] == 'tree':
                        href = 'tree'
                    elif json_href['type'] == 'tp':
                        href = 'contract'
                    else:
                        href = 'manage-object' if json_href['location'] == 'table' else 'contract'
                    # получим код объекта
                    code = str(json_href['code'])
                    # Получим класс объекта
                    if json_href['type'] == 'tp':
                        obj_class_id = str(TechProcess.objects.get(id=json_href['class_id']).parent_id)
                    else:
                        obj_class_id = str(json_href['class_id'])
                    if href == 'tree':
                        href += '?class_id=' + str(json_href['class_id']) + '&branch_code=' + str(json_href['code'])\
                        + '&location=' + json_href['location'][0]
                    else:
                        href += '?class_id=' + obj_class_id + '&object_code=' + code
                # ссылка на класс
                else:
                    href = 'manage-class-tree' if json_href['location'] == 'table' else 'manage-contracts'
                    href += '?i_id=' + str(json_href['class_id'])
                ip.href = href
            elif ip.reg_name_id in (17, 18, 19, 20, 21):
                ip.href = 'tasks'

            # Если включен флаг "Только значения"
            if ip.json_income and in_out != 'out':
                if only_values:
                    if not ip.json_income or not 'value' in ip.json_income:
                        ip.json_income = {}
                    else:
                        ip.json_income = {'value': ip.json_income['value']}
                reg_data['in'] = ip.json_income
            if ip.json and in_out != 'in':
                if only_values:
                    if not ip.json or not 'value' in ip.json:
                        ip.json = {}
                    else:
                        ip.json = {'value': ip.json['value']}
                reg_data['out'] = ip.json

            ip.reg_data = reg_data
            reg_data_string = ''
            for k, v in reg_data.items():
                reg_data_string += str(k) + ':' + str(v) + '\n'
            ip.reg_data = reg_data_string

            if ip.json:
                ip.json.update({'in_out': 'out'})
                if in_out != 'in':
                    list_data.append(ip.json)
            if ip.json_income:
                ip.json_income.update({'in_out': 'in'})
                if in_out != 'out':
                    list_data.append(ip.json_income)

        # Заголовки
        url = common_funs.edit_url(request)

        # отчет вебдатарокс
        df = pd.json_normalize(list_data, max_level=3)
        df_json = df.to_json(orient="records", force_ascii=False)
        parsed = json.loads(df_json)
        temp_json = json.dumps(parsed, indent=4, ensure_ascii=False)

        ctx = {
            'title': 'История',
            'paginator': paginator,
            'date_in': date_in,
            'date_out': date_out,
            'message':message,
            'message_class': message_class,
            'list_data': temp_json,
            'path_without_page': url
        }
        return render(request, 'history/hist-reg.html', ctx)
    else:
        return HttpResponseRedirect(reverse('login'))