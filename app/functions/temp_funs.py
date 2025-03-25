import re


# Изменение внутренней структуры линкпамоп. Удалить после релиза таска "Добавить пакетное редактирование в линкпаме"
def change_linkmap(linkmap):
    new_linkmap = []
    for lm in linkmap:
        if not type(lm) is dict:
            continue
        new_lm = {}
        new_lm['class_id'] = lm['class_id']
        new_lm['loc'] = lm['loc']
        if not lm['code']:
            new_lm['code'] = None
        else:
            try:
                int(lm['code'])
                new_lm['code'] = lm['code']
            except ValueError:
                formula_match = re.match(r'\s*\[\[\s*(?:contract|table)\.\d+\.f(.*)\]\]', lm['code'])
                if formula_match:
                    new_lm['code'] = formula_match[1]
                else:
                    new_lm['code'] = lm['code']
        new_lm['event_kind'] = lm['event_kind']
        if lm['writeoff']:
            new_lm['method'] = 'wo'
        elif lm['new_code']:
            new_lm['method'] = 'en' if new_lm['code'] else 'n'
        else:
            new_lm['method'] = 'e'
        if new_lm['method'] in ['n', 'en']:
            new_lm['create_params'] = lm['create_params']
        if new_lm['method'] != 'n':
            new_lm['params'] = lm['params']
        new_linkmap.append(new_lm)
    return new_linkmap

