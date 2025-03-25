from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


from app.views import handbooks, contracts, drafts, tree, tasks

urlpatterns = [
    path('manage-object', handbooks.manage_object, name="manage-object"),
    path('manage-class-tree', handbooks.manage_class_tree, name="manage-class-tree"),
    # Контракты
    path('manage-contracts', contracts.manage_contracts, name='manage-contracts'),
    path('contract', contracts.contract, name='contract'),
    # Другие
    path('table-draft', drafts.table_draft, name='table-draft'),
    path('contract-draft', drafts.table_draft, name='contract-draft'),
    # path('dictionary', handbooks.dictionary, name='dictionary'),
    path('tree', tree.tree, name='tree'),
    path('manage-tasks', tasks.manage_tasks, name='manage-tasks'),
    # Вспомагательные страницы
    path('tp-routing', contracts.tp_routing, name='tp-routing'),
]