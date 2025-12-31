import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ccu_project.settings")

app = Celery("ccu_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_always_eager=False,
)



app.autodiscover_tasks()


app.conf.beat_schedule = {
    "daily-backup": {
        "task": "services.tasks.backup_postgres_daily",
        "schedule": crontab(hour="*/2", minute=0),
    },
    "weekly-backup": {
        "task": "services.tasks.backup_postgres_weekly",
        "schedule": crontab(hour=23, minute=0, day_of_week="sun"),
    },
    "monthly-backup": {
        "task": "services.tasks.backup_postgres_monthly",
        "schedule": crontab(hour=23, minute=0, day_of_month="1"),
    },
    # "update_daily_statistics": {
    #     "task": "services.tasks.update_daily_statistics_graph",
    #     'schedule': crontab(hour=23, minute=0),
    # },
}
