from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.core.validators import MinValueValidator


class QuotaGroup(models.Model):
    """
    Model representing a group for managing time quotas for a group of laboratories.

    This model handles time allocation, tracking, and periodic resetting for groups
    of laboratories sharing equipment time quotas. Supports unlimited time, quota-free,
    and limited quota configurations.

    Attributes:
        name (str): Unique name identifier for the quota group.
        main (bool): Indicates if this is the primary quota group for the system.
        update_time_on_period (bool): Whether time should be replenished periodically.
        is_active (bool): Whether this quota group is currently active.
        period_time (Decimal): Time allocated per period in hours (NULL = unlimited, -1 = no quota).
        max_time (Decimal): Maximum time that can be accumulated across periods.
        current_time (Decimal): Currently available time in hours.
        quota_reset_time (Decimal): Time available after last reset.
        last_reset (DateTimeField): Timestamp of last quota reset.
        next_reset (DateTimeField): Scheduled timestamp for next reset.
    """

    name = models.CharField('Название группы', max_length=255, unique=True)
    main = models.BooleanField('Основная группа', default=True, blank=False)
    update_time_on_period = models.BooleanField('Обновлять время с периодом', default=True, blank=False)
    is_active = models.BooleanField('Квота активна', default=True, blank=False)
    period_time = models.DecimalField(
        'Время на период (ч)',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='NULL: неограниченное время, -1: группа без квоты'
    )
    max_time = models.DecimalField(
        'Максимальная квота (ч)',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Максимальное доступное время (NULL = без ограничений)'
    )
    current_time = models.DecimalField(
        'Текущее время (ч)',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    quota_reset_time = models.DecimalField(
        'Максимальное время данной квоты (ч)',
        max_digits=10,
        decimal_places=2,
        default=0)
    last_reset = models.DateTimeField(
        'Последний сброс',
        auto_now_add=True
    )
    next_reset = models.DateTimeField(
        'Следующий сброс',
        null=True,
        blank=True
    )

    class Meta:
        """
        Metadata class for QuotaGroup model.

        Defines verbose names for admin interface in Russian.
        """
        verbose_name = 'Группа квот'
        verbose_name_plural = 'Группы квот'

    def __str__(self):
        """
        String representation of the QuotaGroup instance.

        Returns:
            str: Group name with quota status in parentheses.
        """
        return f"{self.name} ({self.get_quota_status()})"

    def get_quota_status(self):
        """
        Generate human-readable description of the quota status.

        Returns:
            str: Formatted string describing the current quota configuration.
        """
        if self.period_time is None:
            return "Неограниченное время"
        if self.period_time == Decimal('-1'):
            return "Без квоты"
        return f"{self.current_time}/{self.max_time or '∞'} ч. (период: {self.period_time} ч.)"

    def reset_quota(self):
        """
        Reset the quota by adding period time to current time.

        Adds period_time to current_time, respecting max_time limit if set.
        Updates reset timestamps and saves the instance.
        """
        if self.period_time is None or self.period_time == Decimal('-1'):
            return

        new_time = self.current_time + self.period_time

        if self.max_time is not None and new_time > self.max_time:
            new_time = self.max_time

        self.current_time = new_time
        self.quota_reset_time = new_time
        self.last_reset = timezone.now()
        self.save()

    def clean(self):
        """
        Validate model data with custom business logic.

        Ensures that main quota groups have update_time_on_period enabled.

        Raises:
            ValidationError: If a main group has update_time_on_period disabled.
        """
        super().clean()
        if self.main and not self.update_time_on_period:
            raise ValidationError({
                'update_time_on_period': 'Основная группа должна иметь обновление времени с периодом.'
            })

    def add_time(self, time):
        """
        Add or subtract time from the current quota.

        Args:
            time (Decimal): Time to add (positive) or subtract (negative) in hours.

        Returns:
            Decimal: The added time value or None if no time was provided.
        """
        if time:
            self.current_time += time
            self.save()
            return time
        return None

    def subtract_time(self, time):
        """
        Subtract time from the current quota (convenience method).

        Args:
            time (Decimal): Time to subtract in hours.

        Returns:
            Decimal: The subtracted time value or None if no time was provided.
        """
        return self.add_time(-time)

    @property
    def donor_transfers_this_period(self):
        """
        Get time transfer transactions where this group was the donor since last reset.

        Returns:
            QuerySet: QuotaTimeTransaction queryset filtered by donor and date.
        """
        from .models import QuotaTimeTransaction
        return QuotaTimeTransaction.objects.filter(
            quota_group_donor=self,
            datetime_stamp__gte=self.last_reset
        )

    @property
    def acceptor_transfers_this_period(self):
        """
        Get time transfer transactions where this group was the acceptor since last reset.

        Returns:
            QuerySet: QuotaTimeTransaction queryset filtered by acceptor and date.
        """
        return QuotaTimeTransaction.objects.filter(
            quota_group_acceptor=self,
            datetime_stamp__gte=self.last_reset
        )

    @property
    def applications_completed_this_period(self):
        """
        Get applications completed by laboratories in this quota group since last reset.

        Returns:
            QuerySet: Application queryset filtered by completion status and date.
        """
        from application.models import Application
        return Application.objects.filter(
            lab__quota_group=self,
            status='completed',
            experiment_end_date__isnull=False,
            experiment_end__isnull=False
        ).filter(
            models.Q(experiment_end_date__gt=self.last_reset.date()) |
            models.Q(experiment_end_date=self.last_reset.date(), experiment_end__gte=self.last_reset.time())
        )

    @property
    def applications_rejected_this_period(self):
        """
        Get applications rejected by laboratories in this quota group since last reset.

        Returns:
            QuerySet: Application queryset filtered by rejection status and date.
        """
        from application.models import Application
        return Application.objects.filter(
            lab__quota_group=self,
            status='rejected',
            experiment_end_date__isnull=False,
            experiment_end__isnull=False
        ).filter(
            models.Q(experiment_end_date__gt=self.last_reset.date()) |
            models.Q(experiment_end_date=self.last_reset.date(), experiment_end__gte=self.last_reset.time())
        )


class QuotaTimeTransaction(models.Model):
    """
    Model representing a time transfer transaction between quota groups.

    Tracks the movement of time hours from one quota group (donor) to another
    (acceptor), including the user who initiated the transfer and timestamp.
    """

    user = models.ForeignKey('accounts.CustomUser', verbose_name='Инициализатор трансфера',
                             on_delete=models.PROTECT)  # lazy import для избежание циклического импорта
    quota_group_donor = models.ForeignKey(QuotaGroup, verbose_name='Квота донор', on_delete=models.PROTECT,
                                          related_name='quota_group_donor_transaction')
    quota_group_acceptor = models.ForeignKey(QuotaGroup, verbose_name='Квота акцептор', on_delete=models.PROTECT,
                                             related_name='quota_group_acceptor_transaction')
    time_transfer = models.DecimalField('Переведенное время, ч.', max_digits=10, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])
    datetime_stamp = models.DateTimeField('Дата трансфера', auto_now_add=True)

    class Meta:
        """
        Metadata class for QuotaTimeTransaction model.

        Defines verbose name for admin interface in Russian.
        """
        verbose_name = 'Трансфер времени'