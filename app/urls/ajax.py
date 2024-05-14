from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from app.functions import ajax_funs, ajax_funs_2

urlpatterns = [

    path('query-link', ajax_funs.query_link, name='query-link'),
    path('class-link', ajax_funs.class_link, name='class-link'),
    path('default-link', ajax_funs.default_link, name='default-link'),
    path('get-alias-params', ajax_funs.get_alias_params, name='get-alias-params'),
    path('get-classes', ajax_funs.get_classes, name='get-classes'),
    path('get-name', ajax_funs.get_name, name='get-name'),
    path('retreive-const-list', ajax_funs.retreive_const_list, name='retreive-const-list'),
    path('promp-link', ajax_funs.promp_link, name='promp-link'),
    path('promp-direct-link', ajax_funs.promp_direct_link, name='promp-direct-link'),
    path('promp-owner', ajax_funs.promp_owner, name='promp-owner'),
    path('roh', ajax_funs.roh, name='roh'),
    path('retreive-const', ajax_funs.retreive_const, name='retreive-const'),
    path('retreive-draft-versions', ajax_funs_2.retreive_draft_versions, name='retreive-draft-versions'),
    path('retreive-object-drafts', ajax_funs_2.retreive_object_drafts, name='retreive-object-drafts'),
    path('get-users', ajax_funs_2.get_users, name='get-users'),
    path('get-user-by-id', ajax_funs_2.get_user_by_id, name='get-user-by-id'),
    path('get-business-rule', ajax_funs_2.get_business_rule, name='get-business-rule'),
    path('gc4lp', ajax_funs_2.gc4lp, name='gc4lp'),
    path('gon4d', ajax_funs_2.gon4d, name='gon4d'),
    path('gfob', ajax_funs_2.gfob, name='gfob'),
    path('get-object-version', ajax_funs_2.gov, name='get-object-version'),
    path('do-cc', ajax_funs_2.do_cc, name='do-cc'),
    path('get-all-float-fields', ajax_funs_2.gaff, name='get-all-float-fields'),
    path('calc-user-formula', ajax_funs_2.calc_user_formula, name='calc-user-formula'),
    path('calc-main-page-formula', ajax_funs_2.cmpf, name='calc-main-page-formula'),
    path('uch', ajax_funs_2.uch, name='uch'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)