from django.core.management.base import BaseCommand, CommandError
from app.functions.parse_funs import parse_valute


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'
    def handle(self, *args, **options):
        return parse_valute()