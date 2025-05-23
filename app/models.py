from datetime import datetime
from django.contrib import auth
from django.db import models


# Справочники
class Designer(models.Model):
    name = models.CharField(max_length=100)
    formula = models.CharField(max_length=100, null=True)
    delay_settings = models.JSONField(default={'handler': None, 'auto_approve': False})
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True)
    is_required = models.BooleanField(null=False, default=False)
    default = models.CharField(max_length=500, null=True)
    is_visible = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    value = models.JSONField(null=True)
    delay = models.BooleanField(null=True)
    system = models.BooleanField(default=False)
    settings = models.JSONField(null=True)


class Objects(models.Model):
    code = models.PositiveIntegerField()
    parent_structure = models.ForeignKey(Designer, on_delete=models.DO_NOTHING, related_name='table_name')
    name = models.ForeignKey(Designer, on_delete=models.DO_NOTHING, related_name='field_name')
    delay = models.JSONField(null=True)
    value = models.JSONField(null=True)


# Контракты
class Contracts(models.Model):
    name = models.CharField(max_length=100)
    formula = models.CharField(max_length=100, null=True)
    value_str = models.CharField(max_length=1000, null=True)
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True)
    is_required = models.BooleanField(null=False, default=False)
    default = models.CharField(max_length=500, null=True)
    is_visible = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    value = models.JSONField(null=True)
    delay = models.JSONField(null=True)
    system = models.BooleanField(default=False)
    settings = models.JSONField(null=True)


class ContractCells(models.Model):
    code = models.PositiveIntegerField()
    parent_structure = models.ForeignKey(Contracts, on_delete=models.DO_NOTHING, related_name='table_name')
    name = models.ForeignKey(Contracts, on_delete=models.DO_NOTHING, related_name='field_name')
    delay = models.JSONField(null=True)
    value = models.JSONField(null=True)


# Регистраторы
class RegName(models.Model):
    name = models.CharField(max_length=100, null=False)


class Registrator(models.Model):
    state = models.CharField(max_length=100, null=True)
    fact = models.CharField(max_length=100, null=True)
    delay = models.CharField(max_length=100, null=True)
    json = models.JSONField(null=True)
    json_string = models.CharField(max_length=1000, null=True)  # поле на время разработки
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING)
    reg_name = models.ForeignKey(RegName, on_delete=models.DO_NOTHING, related_name='registrator')
    state_income = models.CharField(max_length=100, null=True)
    fact_income = models.CharField(max_length=100, null=True)
    delay_income = models.CharField(max_length=100, null=True)
    json_income = models.JSONField(null=True)
    json_string_income = models.CharField(max_length=1000, null=True) # поле на время разработки
    date_update = models.DateTimeField()
    transact_id = models.CharField(max_length=25, null=True)
    parent_transact_id = models.CharField(max_length=25, null=True)


class RegistratorLog(models.Model):
    date_delay = models.DateTimeField(null=True)
    fact = models.CharField(max_length=100, null=True)
    delay = models.JSONField(null=True)
    json = models.JSONField(null=True, )
    json_string = models.CharField(max_length=1000, null=True)  # поле на время разработки
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING)
    reg_name = models.ForeignKey(RegName, on_delete=models.DO_NOTHING)
    state_income = models.CharField(max_length=100, null=True)
    fact_income = models.CharField(max_length=100, null=True)
    delay_income = models.JSONField(null=True)
    json_income = models.JSONField(null=True)
    json_string_income = models.CharField(max_length=1000, null=True)  # поле на время разработки
    date_update = models.DateTimeField(db_index=True)
    transact_id = models.CharField(max_length=25, null=True)
    parent_transact_id = models.CharField(max_length=25, null=True)
    json_class = models.IntegerField(null=True, db_index=True)


# Таблица "Ошибки"
class ErrorsLog(models.Model):
    name = models.CharField(max_length=300)
    date_time_error = models.DateTimeField(default=datetime(2023, 3, 24, 13, 21, 20, 43951))


# Таблица "Словари"
class Dictionary(models.Model):
    name = models.CharField(max_length=100)
    formula = models.CharField(max_length=100, null=True)
    parent_id = models.PositiveIntegerField(null=True)
    default_string = models.CharField(max_length=500, null=True)
    is_visible = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    default = models.JSONField(null=True)


# Таблица "Объекты словарей"
class DictObjects(models.Model):
    value = models.CharField(max_length=500, null=True)
    name = models.ForeignKey(Dictionary, on_delete=models.RESTRICT, related_name='key_name')
    parent_structure = models.ForeignKey(Dictionary, on_delete=models.RESTRICT, related_name='dict')
    code = models.PositiveIntegerField(null=True)


# Таблица "Коды таблиц". Location = table / contract / dict
class TablesCodes(models.Model):
    class_id = models.PositiveIntegerField()
    location = models.CharField(max_length=10)
    max_code = models.PositiveIntegerField(null=True)
    transact_id = models.BigIntegerField(null=True)


class ObjectsTransactIds(models.Model):
    class_id = models.PositiveIntegerField()
    location = models.CharField(max_length=10)
    code = models.PositiveIntegerField()
    last_transact_id = models.BigIntegerField()


# Таблица "Черновики справочников"
class TableDrafts(models.Model):
    data = models.JSONField(null=True)
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING)
    timestamp = models.DateTimeField(null=True)
    sender = models.ForeignKey(auth.models.User, on_delete=models.RESTRICT, null=True, related_name='sender')
    active = models.BooleanField(default=True)


# Черновики контрактов
class ContractDrafts(models.Model):
    data = models.JSONField(null=True)
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING)
    timestamp = models.DateTimeField(null=True)
    sender = models.ForeignKey(auth.models.User, on_delete=models.RESTRICT, null=True, related_name='send_from')
    active = models.BooleanField(default=True)


# задания
class Tasks(models.Model):
    data = models.JSONField(default={})
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING, null=True)
    date_create = models.DateTimeField(null=True)
    date_done = models.DateTimeField(null=True)
    code = models.PositiveIntegerField()
    date_delay = models.DateTimeField(null=True)
    kind = models.CharField(max_length=10)


class TaskClasses(models.Model):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True)
    kind = models.CharField(max_length=10)
    br = models.JSONField(null=True)
    lm = models.JSONField(null=True)
    tr = models.JSONField(null=True)


class OtherCodes(models.Model):
    name = models.CharField(max_length=50)
    code = models.PositiveIntegerField()


# Техпроцессы - заголовки
class TechProcess(models.Model):
    name = models.CharField(max_length=100)
    formula = models.CharField(max_length=50)
    parent_id = models.PositiveIntegerField(null=True)
    value = models.JSONField(null=True)
    settings = models.JSONField(default={'system': False, 'visible': True})


# Техпроцессы - объекты
class TechProcessObjects(models.Model):
    parent_code = models.IntegerField()
    name = models.ForeignKey(TechProcess, on_delete=models.RESTRICT)
    parent_structure = models.ForeignKey(TechProcess, on_delete=models.RESTRICT, related_name='tp')
    value = models.JSONField(null=True)


# Константы главной страницы
class MainPageConst(models.Model):
    name = models.CharField(max_length=50)
    value = models.JSONField(null=True)
    user_login = models.BooleanField(default=True)


# адреса главных страниц
class MainPageAddress(models.Model):
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING, null=True)
    address = models.CharField(max_length=50, null=True)


# Типы данных
class DataTypesList(models.Model):
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=50)


# Типы классов
class ClassTypesList(models.Model):
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=50)


# Модели БД Архив
class Arhiv(models.Model):
    reg_id = models.IntegerField()
    transact_id = models.CharField(max_length=25)
    parent_transact = models.CharField(max_length=25, null=True)
    date_update = models.DateTimeField()
    class_id = models.IntegerField()
    code = models.IntegerField(null=True)
    location = models.CharField(max_length=1)
    type = models.CharField(max_length=20)
    header_id = models.IntegerField(null=True)
    value_inc = models.JSONField(null=True)
    value_outc = models.JSONField(null=True)
    user_id = models.IntegerField()


class UserSets(models.Model):
    user = models.ForeignKey(auth.models.User, on_delete=models.DO_NOTHING)
    pagination = models.IntegerField(default=10)
    main_page = models.CharField(null=True, max_length=50)

