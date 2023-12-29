import datetime
import copy

from app.functions import reg_funs, task_funs, contract_funs, interface_procedures, task_procedures
from app.models import Tasks, ContractCells, Objects, Registrator, TechProcess, TechProcessObjects, Contracts


def run_delays(props=None):
    if not props:
        props = Tasks.objects.filter(kind='prop', date_done__isnull=False, date_delay__lte=datetime.datetime.today())\
            .order_by('date_delay', 'id')
    if props:
        for p in props:
            task_transact = reg_funs.get_transact_id('task', p.code)
            obj_transact = reg_funs.get_transact_id(p.data['class_id'], p.data['code'], p.data['location'])
            timestamp = p.date_done if p.date_delay < p.date_done else p.date_delay

            obj_manager = ContractCells.objects if p.data['location'] == 'c' else Objects.objects
            obj = obj_manager.get(parent_structure_id=p.data['class_id'], code=p.data['code'], name_id=p.data['name_id'])
            if obj.name.formula == 'float':
                obj_new_val = p.data['delay'] + obj.value if obj.value else p.data['delay']
            else:
                obj_new_val = p.data['delay']

            # для контрактов выполним системные функции - BR, LM, Tr
            res = 'ok'
            if p.data['location'] == 'c':
                headers = list(Contracts.objects.filter(parent_id=p.data['class_id'])\
                    .exclude(formula__in=('array', 'business_rule', 'link_map', 'trigger')).values())
                dict_object = {'code': p.data['code'], 'parent_structure': p.data['class_id'], obj.name_id: obj_new_val}

                if obj.parent_structure.formula == 'contract':
                    res = contract_funs.dcsp(p.data['class_id'], p.data['code'], headers, p.data['sender_id'], dict_object,
                                             {}, timestamp, obj_transact)

            date_delay = datetime.datetime.strftime(p.date_delay, '%Y-%m-%dT%H:%M')
            loc4hist = 'contract' if p.data['location'] == 'c' else 'table'
            inc = {'class_id': p.data['class_id'], 'location': loc4hist, 'code': p.data['code'], 'type': obj.name.parent.formula,
                   'name': p.data['name_id'], 'id': obj.id, 'value': obj.value}
            inc_delay = inc.copy()
            inc_delay['delay'] = obj.delay.copy()
            del inc_delay['value']
            if res == 'ok':
                obj.value = obj_new_val
                outc = inc.copy()
                outc['value'] = obj.value
                reg = {'json': outc, 'json_income': inc}
                reg_funs.simple_reg(p.data['sender_id'], 15, timestamp, obj_transact, task_transact, **reg)
                # Изменим первые стадии всех подчиненных ТПсов
                if 'cf' in p.data and p.data['cf']:
                    tps = TechProcess.objects.filter(formula='tp', parent_id=p.data['class_id'], value__control_field=p.data['name_id'])
                    for t in tps:
                        header_stage_0 = TechProcess.objects.filter(parent_id=t.id).exclude(settings__system=True)[0]
                        stage_0 = TechProcessObjects.objects.filter(parent_structure_id=t.id, name_id=header_stage_0.id,
                                                                    parent_code=p.data['code'])[0]
                        inc = {'class_id': t.id, 'location': 'contract', 'type': 'tp', 'id': stage_0.id,
                               'name': header_stage_0.id, 'value': copy.deepcopy(stage_0.value)}
                        outc = inc.copy()
                        stage_0.value['fact'] += p.data['delay']
                        stage_0.save()
                        outc['value'] = stage_0.value
                        reg = {'json': outc, 'json_income': inc}
                        reg_funs.simple_reg(p.data['sender_id'], 15, timestamp, obj_transact, task_transact, **reg)
            else:
                p.data['error'] = res
            obj.delay = [od for od in obj.delay if od['date_update'] != date_delay or od['value'] != p.data['delay']]
            obj.save()
            outc_delay = inc_delay.copy()
            outc_delay['delay'] = obj.delay
            reg_delay = {'json': outc_delay, 'json_income': inc_delay}
            reg_funs.simple_reg(p.data['sender_id'], 22, timestamp, obj_transact, task_transact, **reg_delay)
            task_funs.delete_simple_task(p, timestamp, task_transact=task_transact)
        today = datetime.datetime.today()
        upd_to_log(today)



# тестовый апдейт
def test_upd():
    today = datetime.datetime.today()
    Registrator(user_id=4, reg_name_id=14, date_update=today).save()
    upd_to_log(today)




def upd_to_log(today):
    with open("log.txt", "a") as myfile:
        myfile.write("Запись в БД " + datetime.datetime.strftime(today, '%d.%m.%Y %H:%M:%S') + '\n')