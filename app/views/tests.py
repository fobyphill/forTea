import math
import operator
import re
import time as tm
from datetime import datetime, time, date
from functools import reduce

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.db.models import F, Value, CharField, Q, Subquery, OuterRef, FloatField, DateTimeField, TextField, Func, \
    ExpressionWrapper, Sum, Avg
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, TruncDate, JSONObject, Upper
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from app.functions import convert_procedures, convert_funs, interface_funs, tree_funs, common_funs, view_procedures, \
    api_funs, session_funs, ajax_funs_2, ajax_funs, database_funs, parse_funs, update_funs, task_funs, api_funs2, \
    convert_funs2, temp_funs, class_funs, hist_funs
from app.functions.api_funs import get_object_list
from app.models import RegName, Objects, Designer, Contracts, RegistratorLog, ContractCells, TablesCodes, Dictionary, \
    TechProcessObjects, TechProcess, OtherCodes, Tasks, DictObjects, ObjectsTransactIds, TaskClasses
import pandas as pd
from django.db.models.functions import Upper


@view_procedures.is_auth_app
def tests(request):
    update_funs.run_delays()
    result = 'ok'
    return HttpResponse(result)

def tests_template(request):
    return render(request, 'common/graph-tests.html')


@csrf_exempt
def upload_file(request):
    return HttpResponse('получилось')

