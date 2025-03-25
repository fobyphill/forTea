from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from app.functions.update_funs import test_upd


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        parser.add_argument('date_from', action='store', type=str)

    def handle(self, *args, **kwargs):
        date_from = datetime.strptime(kwargs['date_from'], '%Y-%m-%dT%H:%M:%S')
        now = datetime.today()
        # return 'С той поры прошло ' + str(now - date_from)
        return test_upd(options['a'])