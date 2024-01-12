from django.http import HttpResponse
from django.shortcuts import render

from app.models import RegName


def page_not_found(request, exception):
    return render(request, 'tech/404.html', status=404)


def error_500(request):
    return render(request, 'tech/500.html')