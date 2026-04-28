"""
Creates the Celery Beat periodic task schedules so the worker doesn't need
manual admin configuration after first deploy.
"""
from django.db import migrations


def create_periodic_tasks(apps, schema_editor):
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    every_10s, _ = IntervalSchedule.objects.get_or_create(
        every=10, period="seconds"
    )
    every_15s, _ = IntervalSchedule.objects.get_or_create(
        every=15, period="seconds"
    )

    PeriodicTask.objects.get_or_create(
        name="dispatch-pending-payouts",
        defaults={
            "task": "payouts.tasks.dispatch_pending_payouts",
            "interval": every_10s,
            "enabled": True,
        },
    )
    PeriodicTask.objects.get_or_create(
        name="reap-stuck-payouts",
        defaults={
            "task": "payouts.tasks.reap_stuck_payouts",
            "interval": every_15s,
            "enabled": True,
        },
    )


def delete_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=["dispatch-pending-payouts", "reap-stuck-payouts"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payouts", "0001_initial"),
        ("django_celery_beat", "0018_improve_crontab_helptext"),
    ]

    operations = [
        migrations.RunPython(create_periodic_tasks, delete_periodic_tasks),
    ]
