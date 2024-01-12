from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from app.views import tech, tests

urlpatterns = [
    path('tests-template', tests.tests_template, name="tests-template"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)