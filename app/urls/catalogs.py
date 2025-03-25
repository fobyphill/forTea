from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from app.views import common, history, tasks, sets

urlpatterns = [
    path('', common.index, name="index"),
    path('tasks', tasks.tasks, name='tasks'),
    # история - отчеты по регистраторам
    path('hist-reg', history.hist_reg, name="hist-reg"),
    path('hist-contracts', history.hist_reg, name="hist-contracts"),
    path('arhiv', history.arhiv, name="arhiv"),
    path('sets', sets.sets, name="sets"),
]