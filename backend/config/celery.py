"""
Celery configuration for TimeWise project.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("timewise")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

# Periodic tasks schedule
app.conf.beat_schedule = {
    "check-overdue-invoices": {
        "task": "apps.invoicing.tasks.check_overdue_invoices",
        "schedule": crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    "send-timesheet-reminders": {
        "task": "apps.timesheets.tasks.send_timesheet_reminders",
        "schedule": crontab(hour=9, minute=0, day_of_week="friday"),  # Fridays at 9 AM
    },
    "generate-weekly-reports": {
        "task": "apps.reports.tasks.generate_weekly_reports",
        "schedule": crontab(hour=6, minute=0, day_of_week="monday"),  # Mondays at 6 AM
    },
    "auto-stop-stale-timers": {
        "task": "apps.time_entries.tasks.auto_stop_stale_timers",
        "schedule": crontab(minute=0),  # Every hour
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
