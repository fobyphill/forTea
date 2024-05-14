import math
import operator
from datetime import datetime, time, date
from functools import reduce

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.db.models import F, Value, CharField, Q, Subquery, OuterRef, FloatField, DateTimeField, TextField, Func, \
    ExpressionWrapper
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, TruncDate, JSONObject, Upper
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from app.functions import convert_procedures, convert_funs, interface_funs, tree_funs, common_funs, view_procedures, \
    api_funs, session_funs, ajax_funs_2, ajax_funs, database_funs, parse_funs, update_funs, task_funs, api_funs2, \
    convert_funs2
from app.functions.api_funs import get_object_list
from app.models import RegName, Objects, Designer, Contracts, RegistratorLog, ContractCells, TablesCodes, Dictionary, \
    TechProcessObjects, TechProcess, OtherCodes, Tasks, DictObjects
import pandas as pd


@view_procedures.is_auth_app
def tests(request):
    ccs = Objects.objects.filter(name__name__icontains='Наименование')
    return HttpResponse(str(len(ccs)))


def tests_template(request):
    return render(request, 'common/graph-tests.html')


@csrf_exempt
def upload_file(request):
    aaa = 888
    return HttpResponse('получилось')

