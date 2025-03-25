import time
from datetime import datetime

from django.http import HttpResponseRedirect
from django.urls import reverse

# Декоратор, вычисляющий время выполнения функции
def how_long(fun):
    def wrapper(*args):
        start_time = datetime.today()
        fun(*args)
        time_delta = datetime.today() - start_time
        return str(time_delta)
    return wrapper
