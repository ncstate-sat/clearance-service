"""
This module is responsible for tasks that run periodically in the background.
"""

import atexit
import logging
import sys

from apscheduler.schedulers.background import BackgroundScheduler

from clearance_service.models.scheduler_service import SchedulerService


class ServiceScheduler:
    """
    The scheduler keeps our datasources in sync by periodically pushing
    pending data to the CCure api.
    The schedular also deletes stale data daily.
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="%m/%d/%Y %I:%M:%S %p",
        )

    def daily_jobs(self):
        """Add calls to jobs you want to run every day"""
        SchedulerService.delete_old_assignments()

    def hourly_jobs(self):
        """Add calls to jobs you want to run every hour"""

    def one_minute_jobs(self):
        """Add calls to jobs you want to run every minute"""
        SchedulerService.push_to_ccure()
        SchedulerService.ccure_keepalive()

    def start_scheduler(self):
        """Schedule the jobs defined above"""
        self.scheduler.start()
        self.scheduler.add_job(self.daily_jobs, "cron", hour=1)
        self.scheduler.add_job(self.one_minute_jobs, "cron", minute="*/1")
        self.scheduler.add_job(self.hourly_jobs, "cron", minute="0")

        atexit.register(lambda: (self.scheduler.shutdown(wait=False), print("scheduler shutdown")))
