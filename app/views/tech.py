from datetime import datetime
from django.shortcuts import render
from app.functions import hist_funs, view_procedures


def page_not_found(request, exception):
    return render(request, 'tech/404.html', status=404)


def error_500(request):
    return render(request, 'tech/500.html')


@view_procedures.is_auth_app
def clean_hist(request):
    if 'i_date_in' in request.POST:
        try:
            date_from = datetime.strptime(request.POST['i_date_in'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            date_from = datetime.strptime(request.POST['i_date_in'], '%Y-%m-%dT%H:%M')
    else:
        date_from = None
    if 'i_date_out' in request.POST:
        try:
            date_to = datetime.strptime(request.POST['i_date_out'], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            date_to = datetime.strptime(request.POST['i_date_out'], '%Y-%m-%dT%H:%M')
    else:
        date_to = None
    if date_from and date_to:
        class_id = int(request.POST['i_class']) if request.POST['i_class'] else None
        code = int(request.POST['i_code']) if request.POST['i_code'] else None
        loc = request.POST['s_loc']
        table = '<table class=table><tr class=row><td class=col>Класс</td><td class=col>Код</td><td class=col>Loc</td>' \
                '<td class=col>Время</td></tr>'
        def get_table(objs, table):
            for o in objs:
                if objs.index(o) >= 1000:
                    break
                table += f'<tr class=row><td class=col>{o["json_class"]}</td><td class=col>{o["code"]}' \
                         f'</td><td class=col>{o["location"]}</td><td class=col></td></tr>'
            table = '<h4>Всего объектов ' + str(len(objs)) + '</h4>' + table
            return table

        def get_result(objs, table):
            for o in objs:
                time_start = datetime.today()
                res = hist_funs.clean_object_hist(o["json_class"], o["code"], o["location"][0], date_from, date_to)
                time_finish = datetime.today()
                time_delta = str(time_finish - time_start)
                if type(res) is str:
                    o['location'] = res
                table += f'<tr class=row><td class=col>{o["json_class"]}</td><td class=col>{o["code"]}' \
                         f'</td><td class=col>{o["location"]}</td><td class=col>{time_delta}</td></tr>'
            table = '<h4>Всего объектов ' + str(len(objs)) + '</h4>' + table
            return table

        if 'b_show' in request.POST:
            if class_id:
                if code:
                    table += f'<tr class=row><td class=col>{class_id}</td><td class=col>{code}</td><td class=col>{loc}</td>' \
                             '<td class=col></td></tr>'
                else:
                    objs = hist_funs.get_all_objs(date_from, date_to, loc=loc, class_id=class_id)
                    table = get_table(objs, table)
            else:
                objs = hist_funs.get_all_objs(date_from, date_to)
                table = get_table(objs, table)

        elif 'b_clean' in request.POST:
            if class_id:
                if code:
                    time_start = datetime.today()
                    res = hist_funs.clean_object_hist(class_id, code, loc, date_from, date_to)
                    if type(res) is str:
                        loc = res
                    time_finish = datetime.today()
                    time_delta = str(time_finish - time_start)
                    table += f'<tr class=row><td class=col>{class_id}</td><td class=col>{code}</td><td class=col>{loc}</td>' \
                             f'<td class=col>{time_delta}</td></tr>'
                else:
                    objs = hist_funs.get_all_objs(date_from, date_to, loc=loc, class_id=class_id)
                    table = get_result(objs, table)

            else:
                objs = hist_funs.get_all_objs(date_from, date_to)
                table = get_result(objs, table)
        table += '</table>'
    else:
        table = ''
    ctx = {'table': table,
           'date_from': date_from,
           'date_to': date_to,
           'title': 'Очистка истории'}
    return render(request, 'common/graph-tests.html', ctx)