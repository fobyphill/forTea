import json
import re

from django.db.models import Subquery
from django.forms import model_to_dict

from app.functions import convert_funs, convert_procedures, ajax_funs, ajax_procs
from app.models import TechProcessObjects, ContractCells, Objects, Contracts, Designer


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
def get_full_object(reqs, current_class, headers, location='table'):
    if isinstance(current_class, object):
        current_class = model_to_dict(current_class)
    obj = {'parent_structure': current_class['id'], 'type': current_class['formula']}
    if reqs and headers:
        obj['code'] = reqs[0].code
        for h in headers:
            obj[h['id']] = {'name': h['name'], 'formula': h['formula']}
            try:
                req = next(r for r in reqs if r.name_id == h['id'])
            except StopIteration:
                val = False if h['formula'] == 'bool' else None
                obj[h['id']]['value'] = val
                if location not in ('tp', 'dict'):
                    obj[h['id']]['delay'] = None
            else:
                obj[h['id']]['value'] = req.value
                if location not in ('tp', 'dict'):
                    obj[h['id']]['delay'] = req.delay
    return obj


# pati = prepare_alias_to_interface
def pati(alias, **params):
    user_id = params['user_id'] if 'user_id' in params else None
    is_contract = params['is_contract'] if 'is_contract' in params else False
    is_main_page = params['main_page'] if 'main_page' in params else False
    for a in alias:
        val = convert_procedures.userdata_to_interface(a, 0, is_contract, is_main_page)
        if val:
            a[a['id']] = {'value': val}
        else:
            a['code'] = 0
            convert_funs.deep_formula(a, [a, ], user_id, is_contract)

# aato = add_arrays_to_object
def aato(arrays_data, obj, user_id):
    for ad in arrays_data:
        obj[ad['id']] = dict()
        owner = next(h for h in ad['headers'] if h['name'] == 'Собственник')
        obj[ad['id']]['headers'] = [owner] + ad['vis_headers']
        is_contract = obj['type'] == 'contract'
        object_manager = ContractCells.objects if is_contract else Objects.objects
        childrens_codes = object_manager.filter(parent_structure_id=ad['id'], name_id=owner['id'], value=obj['code']).values('code')
        children = object_manager.filter(parent_structure_id=ad['id'], code__in=Subquery(childrens_codes))
        children = convert_funs.queryset_to_object(children)
        obj[ad['id']]['objects'] = children
        convert_funs.prepare_table_to_template(obj[ad['id']]['headers'], children, user_id, is_contract)


# tadatota = task_data_to_tag
def tadatoda(loc, name_id, task_code, data, user_id):
    manager = Contracts.objects if loc == 'c' else Designer.objects
    header = manager.get(id=name_id)
    if header.formula == 'enum':
        str_tag_data = f'<select id="tag_{task_code}" name="tag_{task_code}" class="form-control">'
        for v in header.value:
            str_tag_data += f'<option value="{v}"'
            if data == v:
                str_tag_data += ' selected'
            str_tag_data += f'>{v}</option>'
        str_tag_data += '</select>'
    elif header.formula == 'const':
        str_tag_data = f'<select id="tag_{task_code}" name="tag_{task_code}" class="form-control" ' \
                       f'onchange="recount_alias(this, {header.id}, \'{loc}\')">'
        alias_loc, parent_id = convert_procedures.slice_link_header(header.value)
        alias_manager = Contracts.objects if alias_loc == 'contract' else Designer.objects
        aliases = alias_manager.filter(parent_id=int(parent_id))
        for al in aliases:
            str_tag_data += f'<option value="{al.id}"'
            if data == al.id:
                str_tag_data += ' selected'
            str_tag_data += f'>{al.name}</option>'
        str_tag_data += f'</select><div class=form-control id="div_alias_{task_code}">'
        formula = '[[' + header.value + '.' + str(data) + ']]'
        const_result = convert_funs.static_formula(formula, user_id)
        str_tag_data += const_result + '</div>'

    elif header.formula == 'file':
        str_tag_data = f'<div class="input-group"><div class="custom-file"><input type="file" class="custom-file-input"' \
                       f'oninput="change_file_label(this)" id="i_file_{task_code}" name="i_file_{task_code}">' \
                       f'<span class="custom-file-label" style="height: auto;" id="s_file_{task_code}">{data[14:]}</span></div>' \
                       f'<button class="btn-outline-primary btn" name="b_save_file" value="{task_code}">Скачать</button>' \
                       f'<button class="tag-invis" id="b_load_{task_code}" name="b_load_file" value={task_code}>Загрузить</button></div>'
    else:
        str_tag_data = f'<input id="tag_{task_code}" name="tag_{task_code}" class="form-control"'
        if header.formula == 'bool':
            str_tag_data += f' type="checkbox"'
            if data:
                str_tag_data += ' checked'
            str_tag_data += '>'
        else:
            if header.formula != 'string':
                dict_types = {'date': 'date', 'datetime': 'datetime-local', 'float': 'number', 'link': 'number'}
                str_tag_data += f' type="{dict_types[header.formula]}"'
                if header.formula == 'link':
                    str_tag_data += f' oninput="get_link(this, {header.id}, \'{header.value}\', \'{loc}\')"'
            str_tag_data += f' value="{data}">'
            if header.formula == 'link':
                link_obj = ajax_procs.query_link(header.id, loc, data)
                location, link_id = convert_procedures.slice_link_header(header.value)
                url = '/contract' if location[0] == 'c' else '/manage-object'
                url += f'?class_id={link_id}'
                if link_obj:
                    url += f'&object_code={data}'
                    link_name = link_obj['object_name']
                else:
                    link_name = 'Перейти к объектам родителя'
                span_link = f'<a target=_blank href="{url}">{link_name}</a>'
                str_tag_data += f'<span class="input-group-text" id="s_link_{task_code}">{span_link}</span>'
    return str_tag_data


