import os
from pathlib import Path
from forteatoo.settings import DATABASES as dbses

root_folder = Path(__file__).resolve().parent.parent.parent
is_mysql = dbses['default']['ENGINE'] == 'django.db.backends.mysql'
proxy = 'http://fishulika:Ciffiav1@proxy2.f-trade.ru:3128'