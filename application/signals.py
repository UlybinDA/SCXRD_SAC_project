from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Q
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Application
from probe.models import Probe
from services.email_service import EmailService
from quotagroup.views import check_if_period_needs_refresh, refresh_period_time

from django.utils.timezone import now
from django.core.cache import cache

from celery import shared_task

from quotagroup.views import plot_quota_time_new
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Application)
def handle_application_time(sender, instance, **kwargs):
    """
    Signal handler for Application pre-save events related to time quota management.

    Monitors status changes of Application instances and triggers quota period
    refresh checks when applications transition from 'submitted' to any other
    status.

    Args:
        sender (Model): The Application model class.
        instance (Application): The Application instance being saved.
        **kwargs: Additional keyword arguments from the signal.
    """

    if not instance.pk:
        return

    try:
        old_instance = Application.objects.get(pk=instance.pk)
    except Application.DoesNotExist:
        return

    if old_instance.previous_status == 'submitted' and instance.status != 'submitted':
        if check_if_period_needs_refresh():
            refresh_period_time()


@receiver(pre_save, sender=Application)
def application_status_changed(sender, instance, **kwargs):
    """
    Signal handler for Application status change notifications.

    Sends email notifications when application status changes to 'completed'
    or 'rejected'. Triggers quota time plotting after status changes.
    Only sends emails when the status actually changes (not on every save).

    Args:
        sender (Model): The Application model class.
        instance (Application): The Application instance being saved.
        **kwargs: Additional keyword arguments from the signal.
    """
    if instance.status == 'completed':

        if instance.pk:
            try:
                if instance.previous_status != 'completed':
                    logger.debug(instance.previous_status)
                    EmailService.send_application_completed_email(instance)
                    plot_quota_time_signal()
            except Application.DoesNotExist:

                pass

    elif instance.status == 'rejected':
        if instance.pk:
            try:
                if instance.previous_status != 'rejected':
                    EmailService.send_application_rejected_email(instance)
                    plot_quota_time_signal()
            except Application.DoesNotExist:

                pass


@receiver(post_save, sender=Application)
def application_data_status_changed(sender, instance, **kwargs):
    """
    Signal handler for Application data status change notifications.

    Sends email notifications when application data status changes to 'DATA_SENT',
    indicating that reduced data has been published and is available for download.

    Args:
        sender (Model): The Application model class.
        instance (Application): The Application instance being saved.
        **kwargs: Additional keyword arguments from the signal.
    """
    if instance.data_status == 'DATA_SENT':

        if instance.pk:
            try:

                if instance.prev_data_status != 'DATA_SENT':
                    EmailService.send_data_published_email(instance)
            except Application.DoesNotExist:
                pass


@receiver(post_save, sender=Probe)
def update_application_on_probe_change(sender, instance, **kwargs):
    """
    Signal handler for Probe post-save events to update related Application aggregates.

    When a Probe instance is saved, this signal triggers the update of aggregated
    fields (probe counts, statuses, etc.) on the related Application to maintain
    data consistency.

    Args:
        sender (Model): The Probe model class.
        instance (Probe): The Probe instance being saved.
        **kwargs: Additional keyword arguments from the signal.
    """
    if instance.application:
        instance.application.update_aggregated_fields()


def update_quota_application_counter(application_instance):
    """
    Update daily quota counters and timers for application status tracking.

    Increments daily counters and accumulates time spent for applications
    based on their status. Stores data in Django cache with a 24-hour timeout
    for daily aggregation and reporting purposes.

    Args:
        application_instance (Application): The Application instance to count.
    """
    status = application_instance.status
    quote_group = application_instance.lab.quota_group
    quote_group_id_str = str(quote_group.id)

    time_spent = application_instance.time_spent
    count_key = f'daily_counter_{status}'
    timer_key = f'daily_timer_{status}'

    counts = cache.get(count_key) or {}
    time = cache.get(timer_key) or {}

    time[quote_group_id_str] = time.get(quote_group_id_str, 0) + time_spent
    counts[quote_group_id_str] = counts.get(quote_group_id_str, 0) + 1

    cache.set(count_key, counts, timeout=3600 * 24)
    cache.set(timer_key, time, timeout=3600 * 24)


@shared_task
def plot_quota_time_signal():
    """
    Celery task to generate and save quota time visualization plots.

    This asynchronous task triggers the generation of quota time consumption
    plots, which are typically called after application status changes or
    quota period refreshes. Uses the newer plotting function for quota
    visualization.
    """
    plot_quota_time_new()
