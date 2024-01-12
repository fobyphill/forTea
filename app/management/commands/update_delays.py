from django.core.management.base import BaseCommand, CommandError
from app.functions.update_funs import run_delays


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'
    def handle(self, *args, **options):
        return run_delays()