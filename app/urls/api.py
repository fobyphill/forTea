from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from app.views import api

urlpatterns = [
    path('api/create-object', api.create_object, name='create-object'),
    path('api/edit-object', api.edit_object, name='edit-object'),
    path('api/remove-object', api.remove_object, name='remove-object'),
    path('api/get-object', api.get_object, name='get-object'),
    path('api/get-object-list', api.get_object_list, name='get-object-list'),
    path('api/create-class', api.create_class, name='api/create-class'),
    path('api/edit-class', api.edit_class, name='api/edit-class'),
    path('api/create-class-param', api.create_class_param, name='api/create-class-param'),
    path('api/edit-class-param', api.edit_class_param, name='api/edit-class-param'),
    path('api/remove-class-param', api.remove_class_param, name='api/remove-class-param'),
    path('api/remove-class', api.remove_class, name='api/remove-class'),
    path('api/get-class', api.get_class, name='api/get-class'),
    path('api/get-class-list', api.get_class_list, name='api/get-class-list'),
    path('api/run-eval', api.run_eval, name='api/run-eval'),
    path('api/login', api.login, name='api/login'),
    path('api/logout', api.logout, name='api/logout'),
    path('api/remove-object-list', api.remove_object_list, name='remove-object-list'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)