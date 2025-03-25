"""forteatoo URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from app.views import common, tests
from app.urls.catalogs import urlpatterns as app_urls
from app.urls.tech import urlpatterns as tech_urls
from app.urls.constructors import urlpatterns as constructors_url
from app.urls.ajax import urlpatterns as ajax_urls
from app.urls.api import urlpatterns as api_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(app_urls)),
    path('', include(tech_urls)),
    path('', include(constructors_url)),
    path('', include(ajax_urls)),
    path('', include(api_urls)),

    # Общедоступные адреса
    path('login', common.login_view, name='login'),
    path('logout', common.logout, name='logout'),
    path('tests', tests.tests, name='tests'),
    path('tests-template', tests.tests_template, name='tests-template'),
] + static(settings.MEDIA_URL, document_root=settings.STATIC_ROOT)

handler404 = "app.views.tech.page_not_found"
handler500 = "app.views.tech.error_500"
