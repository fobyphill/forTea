from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from app.functions.update_funs import run_clean_hist


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        parser.add_argument('date_from', action='store', type=str)
        parser.add_argument('date_to', action='store', type=str)

    def handle(self, *args, **kwargs):
        date_from = datetime.strptime(kwargs['date_from'], '%Y-%m-%dT%H:%M:%S')
        date_to = datetime.strptime(kwargs['date_to'], '%Y-%m-%dT%H:%M:%S')
        return run_clean_hist(date_from, date_to)