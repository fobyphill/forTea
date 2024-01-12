from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

from app.models import RegName, DataTypesList, ClassTypesList


def initialisation():
    reg_names = RegName.objects.all()
    result = False
    # Инициализация таблицы RegNames
    if not reg_names:
        list_reg_names = [
            {'id': 1, 'name': 'Создание класса'},
            {'id': 2, 'name': 'Чтение класса'},
            {'id': 3, 'name': 'Редактирование класса'},
            {'id': 4, 'name': 'Удаление класса'},
            {'id': 5, 'name': 'Создание объекта'},
            {'id': 6, 'name': 'Чтение объекта'},
            {'id': 7, 'name': 'Редактирование объекта'},
            {'id': 8, 'name': 'Удаление объекта'},
            {'id': 9, 'name': 'Создание параметра класса'},
            {'id': 12, 'name': 'Чтение параметра класса'},
            {'id': 10, 'name': 'Редактирование параметра класса'},
            {'id': 11, 'name': 'Удаление параметра класса'},
            {'id': 13, 'name': 'Создание реквизита объекта'},
            {'id': 14, 'name': 'Чтение реквизита объекта'},
            {'id': 15, 'name': 'Редактирование реквизита объекта'},
            {'id': 16, 'name': 'Удаление реквизита объекта'},
            {'id': 17, 'name': 'Создание задачи'},
            {'id': 18, 'name': 'Создание записи задачи'},
            {'id': 19, 'name': 'Удаление записи задачи'},
            {'id': 20, 'name': 'Редактирование записи задачи'},
            {'id': 21, 'name': 'Удаление задачи'},
            {'id': 22, 'name': 'Изменение планирования реквизита объекта'}
        ]
        list_objs = []
        for lrn in list_reg_names:
            obj = RegName(id=lrn['id'], name=lrn['name'])
            list_objs.append(obj)
        RegName.objects.bulk_create(list_objs)
        result = True
    # инициализация базового пользователя
    if not get_user_model().objects.all().count():
        first_user = User.objects.create_user(is_superuser=True, is_staff=True, is_active=True, username='admin', password='admin')
        first_user.save()
        result = True
    # инициализация типов данных
    data_types = DataTypesList.objects.all()
    if not data_types:
        list_dt = [
            ['string', 'Строка'],
            ['float', 'Число'],
            ['link', 'Ссылка'],
            ['datetime', 'Дата и время'],
            ['date', 'Дата'],
            ['enum', 'Перечисление'],
            ['const', 'Константа'],
            ['file', 'Файл'],
            ['bool', 'Логический'],
            ['eval', 'Вычисляемый'],
        ]
        list_objs = []
        for ld in list_dt:
            obj = DataTypesList(name=ld[0], description=ld[1])
            list_objs.append(obj)
        DataTypesList.objects.bulk_create(list_objs)
    # Инициализация типов классов
    class_types = ClassTypesList.objects.all()
    if not class_types:
        list_objs = []
        list_ct = [
            ['table', 'Справочник'],
            ['contract', 'Контракт'],
            ['folder', 'Каталог'],
            ['tree', 'Дерево'],
            ['array', 'Массив'],
            ['dict', 'Словарь'],
            ['tp', 'Техпроцесс'],
            ['alias', 'Константа'],
        ]
        for lct in list_ct:
            obj = ClassTypesList(name=lct[0], description=lct[1])
            list_objs.append(obj)
        ClassTypesList.objects.bulk_create(list_objs)
    return result