import re

from django.core.exceptions import ObjectDoesNotExist

from app.functions import convert_procedures
from app.models import Contracts, Designer, Dictionary, Objects, ContractCells


def query_link(header_id, loc, link_code):
    my_class = Contracts.objects if loc == 'c' else Designer.objects if loc == 't' else Dictionary.objects
    my_class = my_class.get(id=header_id)
    base_link = my_class.value if loc != 'd' else re.match(r'(?:contract|table)\.\d+', my_class.default)[0]
    parent_class_type, parent_class_id = convert_procedures.slice_link_header(base_link)
    constructor = Designer.objects if parent_class_type == 'table' else Contracts.objects
    name = 'system_data' if parent_class_type == 'contract' else 'Наименование'
    parent_class_name_id = constructor.filter(parent_id=parent_class_id, is_required=True, name__iexact=name)[0].id
    records = Objects.objects if parent_class_type == 'table' else ContractCells.objects
    try:
        object = records.get(code=link_code, parent_structure_id=int(parent_class_id),
                             name_id=int(parent_class_name_id))
    except ObjectDoesNotExist:
        return None
    val = object.value['datetime_create'] if parent_class_type == 'contract' else object.value
    return {'class_id': parent_class_id, 'object_code': link_code, 'object_name': val, 'location': parent_class_type[0]}
