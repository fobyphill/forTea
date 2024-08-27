from app.functions import tree_funs
from app.models import ContractDrafts, TableDrafts


def remove_all_drafts(user_id, list_ids, draft_tree, is_contract=False):
    list_removed_ids = []
    for li in list_ids:
        list_removed_ids.append(li)
        branch = tree_funs.find_branch(draft_tree, 'id', li)
        list_removed_ids += tree_funs.retreive_branch_children(branch)
    manager = ContractDrafts.objects if is_contract else TableDrafts.objects
    all_drafts = manager.filter(user_id=user_id, active=True)
    if list_removed_ids:
        all_drafts = all_drafts.filter(data__parent_structure__in=list_removed_ids)
    all_drafts.delete()
