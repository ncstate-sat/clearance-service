"""
This module is responsible for tasks that run periodically in the background.
"""
import atexit

import tzlocal
from apscheduler.schedulers.background import BackgroundScheduler
from sat.logs import SATLogger

from clearance_service.util.scheduler_service import SchedulerService
from clearance_service.util.settings import SCHEDULE_CLEARANCES

logger = SATLogger(__name__)


class ServiceScheduler:
    """
    The scheduler keeps our datasources in sync by periodically pushing
    pending data to the CCure api.
    The scheduler also deletes stale assignment data daily.
    """

    def __init__(self):
        # Fix warning about pytz https://github.com/agronholm/apscheduler/discussions/570#discussioncomment-3383707
        self.scheduler = BackgroundScheduler(timezone=str(tzlocal.get_localzone()))

    def daily_jobs(self):
        """Add calls to jobs you want to run every day"""
        SchedulerService.update_liaison_clearance_names()
        SchedulerService.purge_scheduled_actions()

    def hourly_jobs(self):
        """Add calls to jobs you want to run every hour"""

    def one_minute_jobs(self):
        """Add calls to jobs you want to run every minute"""
        if SCHEDULE_CLEARANCES:
            logger.info("Process scheduled assignments")
            SchedulerService.push_to_ccure()

    def keep_alive(self):
        logger.info("Keepalive")
        SchedulerService.ccure_keepalive()

    def start_scheduler(self):
        """Schedule the jobs defined above"""
        self.scheduler.start()
        self.scheduler.add_job(self.daily_jobs, "cron", hour=1)
        self.scheduler.add_job(self.one_minute_jobs, "cron", minute="*/1")
        self.scheduler.add_job(self.keep_alive, "cron", minute="*/20")
        self.scheduler.add_job(self.hourly_jobs, "cron", minute="0")

        atexit.register(lambda: (self.scheduler.shutdown(wait=False)))
