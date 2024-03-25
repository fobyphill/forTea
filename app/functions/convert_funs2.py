import re

from django.forms import model_to_dict

from app.functions import convert_funs
from app.models import TechProcessObjects, ContractCells, Objects


# atptc = add_TechProcesses_to_contract
def atptc(objects, tps):
    codes = [o['code'] for o in objects]
    for t in tps:
        tp_cells = list(TechProcessObjects.objects.filter(parent_structure_id=t['id'], parent_code__in=codes).values())
        for o in objects:
            if t['control_field'] in o:
                control_field = o[t['control_field']]
                if not 'tps' in control_field:
                    control_field['tps'] = []
                stages = [tc['value'] for tc in tp_cells if tc['parent_code'] == o['code']]
                dict_tp = {'id': t['id'], 'stages': stages}
                control_field['tps'].append(dict_tp)


# Получаем объект в виде словаря. Вход - кверисет существующих реквизитов объекта, список заголовков
# Получает только объекты следующих типов - словари, контракты, массивы, деревья
def get_full_object(reqs, headers):
    object = dict()
    if reqs and headers:
        object['code'] = reqs[0].code
        object['parent_structure_id'] = reqs[0].parent_structure_id
        for h in headers:
            object[h['id']] = {'name': h['name'], 'type': h['formula']}
            try:
                req = next(r for r in reqs if r.name_id == h['id'])
            except StopIteration:
                object[h['id']]['value'] = None
                object[h['id']]['delay'] = None
            else:
                object[h['id']]['value'] = req.value
                object[h['id']]['delay'] = req.delay
    return object

# pati = prepare_alias_to_interface
def pati(alias, **params):
    user_id = params['user_id'] if 'user_id' in params else None
    is_contract = params['is_contract'] if 'is_contract' in params else False
    is_main_page = params['main_page'] if 'main_page' in params else False
    dict_types = {'string': 'text', 'number': 'number', 'bool': 'checkbox', 'date': 'date',
                  'datetime': 'datetime-local', 'link': 'text'}
    for a in alias:
        user_data = re.findall(r'\[\[\s*\n*\s*user_data_\d+\s*\n*\s*(?:\{\{[\w\W]*?\}\}|)\s*\n*\s*\]\]', a['value'], flags=re.M)
        if user_data:
            val = ''
            calc_button_label = 'Рассчитать'
            for ud in user_data:
                find_data = re.search(r'user_data_(\d+)\s*\n*\s*(?:\{\{([\w\W]*)\}\}|)', ud, flags=re.M)
                val += '<div class="input-group mb-3">'
                val += '<span class="input-group-text">'
                # Разберем опциональные параметры
                label = 'Пользовательская переменная №' + find_data[1]
                data_type = 'text'
                data_list = ''
                link_class = '0'
                link_location = 't'
                if find_data[2]:
                    find_label = re.search(r'label\s*\n*\s*=\s*\n*\s*\'([\w\s\_]+)\'', find_data[2])
                    if find_label:
                        label = find_label[1]
                    find_type = re.search(r'type\s*\n*\s*=\s*\n*\s*(string|number|bool|datetime|date|link)', find_data[2])
                    if find_type:
                        data_type = dict_types[find_type[1]]
                        if find_type[1] == 'link':
                            data_list = '<datalist id="dl_' + str(a['id']) + '_' + label + '"></datalist>'
                            find_link_class = re.search(r'link_class\s*\n*\s*=\s*\n*\s*(\d+)', find_data[2])
                            if find_link_class:
                                link_class = find_link_class[1]
                            find_link_location = re.search(r'link_location\s*\n*\s*=\s*\n*\s*([tc])', find_data[2])
                            if find_link_location:
                                link_location = find_link_location[1]
                    find_button_label = re.search(r'button\s*\n*\s*=\s*\n*\s*\'([\w\s\_]+)\'', find_data[2])
                    if find_button_label:
                        calc_button_label = find_button_label[1]
                val += label
                val += '</span>'
                val += '<input id=\'const_' + str(a['id']) + '_user_data_' + find_data[1] + '\' class= "form-control" ' \
                       'type="' + data_type + '"'
                if data_list:
                    val += ' list="dl_' + str(a['id']) + '_' + find_data[1] + '" oninput="promp_direct_link(this, \'' \
                           + link_location + '\', ' + link_class + ')"><datalist id="dl_' + str(a['id']) \
                           + '_' + find_data[1] + '"></datalist'

                val += '></div>'

            str_is_contract = str(is_contract).lower()
            fun_name = 'cmpf(' + str(a['id']) + ')' if is_main_page else 'calc_const(' + str(a['id']) + ', ' \
                                                                         + str_is_contract + ')'
            val = val[:-6] + f'<div class="input-group-append"><button class="btn btn-outline-secondary" onclick="{fun_name}"' \
            + '>' + calc_button_label + '</button></div></div>'
            val += '<div id="div_const_' + str(a['id']) + '_result"></div>'
            a[a['id']] = {'value': val}
        else:
            convert_funs.deep_formula(a, [a, ], user_id, is_contract)





