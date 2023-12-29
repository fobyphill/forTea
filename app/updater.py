from apscheduler.schedulers.background import BackgroundScheduler

from app.functions import files_funs
from app.functions.update_funs import run_delays


def start():
    files_funs.add_to_log('Шедулер стартовал')
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_delays, 'interval', minutes=1)
    # scheduler.add_job(test_upd, 'interval', seconds=10)
    # scheduler.add_job(parse_valute, trigger='cron', hour='10', minute='15,30,45')
    scheduler.start()