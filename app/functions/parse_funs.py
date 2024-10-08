from datetime import datetime
import requests
import xmltodict
from app.functions import server_funs, api_funs
from app.models import ErrorsLog, Objects
from app.other import global_vars


# Парсинг валют. Парсит курс евро и доллара по отношению к рублю. Результаты кладет в значения курсов, регистраторы и их истории
def parse_valute():
    robot_dummy = 6
    date_time_update = datetime.today().strftime('%Y-%m-%dT%H:%M')
    date_last_parse = Objects.objects.get(id=393).value[:10]
    date_now = date_time_update[:10]
    class_value = 131
    if date_now <= date_last_parse:
        return 'Курсы валют актуальны. Данные не обновлены'
    try:
        # Парсим валюты
        proxies = {'https': global_vars.proxy,
                   'http': global_vars.proxy}
        response = requests.get("http://www.cbr.ru/scripts/XML_daily.asp", proxies=proxies)
        data = xmltodict.parse(response.content)
        counter = 0
        dollar_value = 0
        euro_value = 0
        for valute in data['ValCurs']['Valute']:
            if valute['CharCode'] == 'EUR':
                euro_value = float(valute['Value'].replace(',', '.'))
                counter += 1
            elif valute['CharCode'] == 'USD':
                dollar_value = float(valute['Value'].replace(',', '.'))
                counter += 1
            if counter >= 2:
                break
        # Сохраним курс доллара
        params = {'135': dollar_value, '137': date_time_update}
        api_funs.edit_object(class_value, 2, robot_dummy, 'table', **params)
        # Сохраним курс евро
        params = {'135': euro_value, '137': date_time_update}
        api_funs.edit_object(class_value, 3, robot_dummy, 'table', **params)
        return 'ok'
    except Exception as ex:
        ErrorsLog(name='Ошибка парсинга валют. ' + str(ex), date_time_error=datetime.strptime(date_time_update, '%Y-%m-%dT%H:%M'))
        text_error = 'Ошибка во время парсинга валют: ' + str(ex) + '. Дата и вемя операции - ' \
                     + date_time_update
        server_funs.send_mail('shulika@shopft.ru', 'Ошибка парсинга валют', text_error)
        return str(ex)