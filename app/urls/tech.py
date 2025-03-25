from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from app.views import tests, tech

urlpatterns = [
    path('tests-template', tests.tests_template, name="tests-template"),
    path('upload-file', tests.upload_file, name="upload-file"),
    path('clean-hist', tech.clean_hist, name="clean-hist"),
]