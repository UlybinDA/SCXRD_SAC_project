from django.db import models
from quotagroup.models import QuotaGroup
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class Laboratory(models.Model):
    """
    Model representing a research laboratory that uses crystallography equipment.

    Each laboratory belongs to an organization, has a location, and is associated
    with a QuotaGroup that manages its time allocation for equipment usage.
    """

    lab_code = models.CharField("Код", max_length=50, blank=False, unique=True)
    name = models.CharField("Название", max_length=255, unique=True)
    organization = models.CharField("Организация", max_length=255)
    country = models.CharField("Страна", max_length=100)
    city = models.CharField("Город", max_length=100)
    short_name = models.CharField('Сокращенное название', blank=True, null=True)
    quota_group = models.ForeignKey(
        QuotaGroup,
        verbose_name=_('Группа квот'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='labs'
    )

    def __str__(self):
        """
        String representation of the Laboratory instance.

        Returns:
            str: The short name of the laboratory.
        """
        return f"{self.short_name}"

    def get_available_time(self):
        """
        Calculate and return available time quota for the laboratory.

        Returns the current available time from the associated QuotaGroup,
        with special handling for unlimited time scenarios (None or -1 values).

        Returns:
            Decimal: Available time in hours, or 999999 for unlimited quotas.
        """
        if not self.quota_group:
            return Decimal('999999')


        if self.quota_group.period_time is None:
            return Decimal('999999')
        if self.quota_group.period_time == Decimal('-1'):
            return Decimal('999999')

        return self.quota_group.current_time

    def consume_time(self, hours):
        """
        Deduct specified hours from the laboratory's time quota.

        Updates the associated QuotaGroup's current_time by subtracting the
        provided hours, unless the quota is unlimited (None or -1).

        Args:
            hours (Decimal or float): Number of hours to consume from quota.
        """
        if not self.quota_group:
            return


        if self.quota_group.period_time in [None, Decimal('-1')]:
            return
        self.quota_group.current_time -= Decimal(hours)
        self.quota_group.save()