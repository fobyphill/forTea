from apscheduler.schedulers.background import BackgroundScheduler

from app.functions import files_funs
from app.functions.update_funs import run_delays


def start():
    pass
    # files_funs.add_to_log('Шедулер стартовал')
    # scheduler = BackgroundScheduler()
    # scheduler.add_job(run_delays, 'interval', minutes=1)
    # scheduler.start()