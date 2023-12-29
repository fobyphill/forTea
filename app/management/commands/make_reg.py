from django.core.management.base import BaseCommand, CommandError
from app.functions.reg_funs import make_reg_console


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'
    def handle(self, *args, **options):
        return make_reg_console()