from django.db import models
from django.utils.translation import gettext_lazy as _
from labs.models import Laboratory
from accounts.models import CustomUser
from operators.models import Operator
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from diffdevices.models import DiffDevice
from django.utils import timezone
import nanoid
from datetime import datetime, date, time, timedelta
from django.core.exceptions import ValidationError
from structurer.models import Structurer
from cryst_chemist.models import CrystChemist
import logging

logger = logging.getLogger(__name__)


def generate_application_code():
    """
    Generate a unique application code using nanoid.

    Returns:
        str: A 21-character unique string identifier for an application.
    """
    return nanoid.generate(size=21)


def validate_forbidden_chars(value):
    """
    Validate that a string doesn't contain forbidden characters.

    Checks if the value contains any of the forbidden characters: \, /, or |
    and raises a ValidationError if found.

    Args:
        value (str): The string value to validate.

    Raises:
        ValidationError: If the string contains forbidden characters.
    """
    forbidden_chars = r'\/|'
    if any(char in value for char in forbidden_chars):
        raise ValidationError(
            _('Строка не должна содержать символы: %(forbidden_chars)s'),
            params={'forbidden_chars': forbidden_chars},
        )


class ApplicationDraft(models.Model):
    """
    Draft model for temporarily storing application data before submission.

    Stores partial application data entered by users, allowing them to save
    progress and continue later. Each field corresponds to fields in the
    Application model.

    Attributes:
        TemplateClasses (class): Inner class defining CSS classes for draft
                                 field highlighting in UI templates.
    """

    user = models.ForeignKey(
        CustomUser,
        verbose_name=_('Заказчик'),
        on_delete=models.PROTECT,
        related_name='client_draft',
        blank=True,
        null=True,
    )
    project = models.CharField(_('Код проекта'), max_length=50, default='НИР')
    inter_telephone = models.CharField(_('Внутренний телефон'), max_length=20, blank=True)
    urgt_comm = models.TextField(_('Срочная связь'), blank=True)
    operator_desired = models.ForeignKey(
        Operator,
        verbose_name=_('Оператор'),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='_draft_desired_oper_applications'
    )
    structurer_desired = models.ForeignKey(
        Structurer,
        verbose_name=_('Структурщик'),
        on_delete=models.PROTECT,
        related_name='_draft_struct_applications',
        null=True,
        blank=True,
    )
    crystchemist_desired = models.ForeignKey(
        CrystChemist,
        verbose_name=_('Кристаллохимик'),
        on_delete=models.PROTECT,
        related_name='_draft_crystchem_applications',
        null=True,
        blank=True,
    )
    sample_appearance = models.TextField(_('Внешний вид образца'), blank=True, null=True)
    composition = models.TextField(_('Состав образца'), blank=True, null=True)
    mother_solution = models.TextField(_('Маточный раствор'), blank=True, null=True)
    tare = models.TextField(_('Тара'), max_length=100, blank=True, null=True)
    sample_storage = models.TextField(_('Место хранения образца'), blank=True, null=True)
    sample_storage_conditions = models.TextField(_('Условия хранения образца'), blank=True, null=True)
    desired_UCP_SG_appearance = models.TextField(_('Снимать только: габитус, цвет, ПЭЯ/ПГ'), blank=True, null=True)
    undesired_UCP_SG_appearance = models.TextField(_('Не снимать: габитус, цвет, ПЭЯ/ПГ'), blank=True, null=True)
    diffractometer = models.ForeignKey(
        DiffDevice,
        verbose_name=_('Дифрактометр'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    experiment_temp = models.IntegerField(
        _('Температура эксперимента, К'),

        null=False,
        blank=False,
        default=220,
        help_text=_('Температура в K'),
        validators=[
            MinValueValidator(80),
            MaxValueValidator(500)
        ]
    )
    experiment_type = models.CharField(
        _('Тип эксперимента'),
        max_length=50,
        default='',
    )

    class TemplateClasses:
        """
        CSS template classes for draft field highlighting.

        Maps field names to Bootstrap CSS classes for visual differentiation
        of draft fields in the user interface. Used to indicate field importance
        or status during application editing.
        """
        project = 'warning'
        inter_telephone = 'info'
        urgt_comm = 'info'
        operator_desired = 'warning'
        structurer_desired = 'warning'
        crystchemist_desired = 'warning'
        sample_appearance = 'danger'
        mother_solution = 'danger'
        tare = 'warning'
        sample_storage = 'warning'
        sample_storage_conditions = 'warning'
        desired_UCP_SG_appearance = 'danger'
        undesired_UCP_SG_appearance = 'warning'
        diffractometer = 'info'
        experiment_temp = 'danger'
        experiment_type = 'danger'


class Application(models.Model):
    """
    Main model representing a crystallography experiment application.

    Tracks all aspects of a research application from submission through
    completion, including sample details, experimental parameters, personnel
    assignments, time tracking, and status management. Integrates with
    laboratory quota systems and supports operator locking for concurrent editing.

    Attributes:
        operator_lock_cooldown (timedelta): Duration after which an operator
                                            lock for application expires (2 hours).
        STATUS_CHOICES (tuple): Available status choices for applications.
        DATA_STATUS_CHOICES (tuple): Available data processing status choices.
        POST_STORAGE_CHOICES (tuple): Options for post-experiment sample storage.
        EXPERIMENT_CHOICES (tuple): Types of crystallography experiments.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize an Application instance with time tracking and status monitoring.

        Sets up internal attributes for tracking time spent changes and
        previous status values during object lifecycle.
        """
        super().__init__(*args, **kwargs)
        self._current_time = self.time_spent
        self._prev_status = self.status

    operator_lock_cooldown = timedelta(hours=2)
    application_code = models.CharField(
        max_length=21,
        unique=True,
        default=generate_application_code,
        editable=False
    )
    project = models.CharField(_('Код проекта'), max_length=50, default='НИР')
    deadline = models.DateTimeField(_('Дэдлайн'), blank=True, null=True)
    asap_priority = models.BooleanField(_('ASAP приоритет'), blank=False, default=False)
    ignore_quota_limit = models.BooleanField(_('Игнорировать лимит квоты'), blank=False, default=False)
    quota_compensation = models.DurationField(null=True, blank=True)
    date = models.DateField(
        _('Дата создания'),
        default=timezone.now
    )

    client_home_lab = models.ForeignKey(
        Laboratory,
        verbose_name=_('Домашняя лаборатория клиента'),
        on_delete=models.PROTECT,
        related_name='application_home',
    )
    lab = models.ForeignKey(
        Laboratory,
        verbose_name=_('Лаборатория'),
        on_delete=models.PROTECT,
        related_name='applications'
    )
    time_spent = models.DecimalField(
        _('Затраченное время (ч)'),
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        blank=True,
    )
    client = models.ForeignKey(
        CustomUser,
        verbose_name=_('Заказчик'),
        on_delete=models.PROTECT,
        related_name='client_applications',
        blank=True,
        null=True

    )
    supervisor = models.ForeignKey(
        CustomUser,
        verbose_name=_('Руководитель'),
        on_delete=models.PROTECT,
        related_name='supervised_applications',
        blank=True,
        null=True
    )
    operator = models.ForeignKey(
        Operator,
        verbose_name=_('Оператор'),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='applications'
    )


    inter_telephone = models.CharField(_('Внутренний телефон'), max_length=20, blank=True)
    urgt_comm = models.TextField(_('Срочная связь'), blank=True)


    operator_desired = models.ForeignKey(
        Operator,
        verbose_name=_('Оператор'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='desired_oper_applications'
    )
    structurer_desired = models.ForeignKey(
        Structurer,
        verbose_name=_('Структурщик'),
        on_delete=models.PROTECT,
        related_name='struct_applications',
        null=True,
        blank=True,
    )
    crystchemist_desired = models.ForeignKey(
        CrystChemist,
        verbose_name=_('Кристаллохимик'),
        on_delete=models.PROTECT,
        related_name='crystchem_applications',
        null=True,
        blank=True,
    )

    sample_code = models.CharField(_('Код образца'), max_length=50, validators=[validate_forbidden_chars])
    sample_appearance = models.TextField(_('Внешний вид образца'))
    composition = models.TextField(_('Состав образца'))
    mother_solution = models.TextField(_('Маточный раствор'), null=True, blank=True, default="")
    tare = models.TextField(_('Тара'), max_length=100)

    sample_storage = models.TextField(_('Место хранения образца'))
    sample_storage_conditions = models.TextField(_('Условия хранения образца'))
    presence_is_necessary = models.BooleanField(_('Необходимо присутствие заказчика'), default=False)

    desired_UCP_SG_appearance = models.TextField(_('Снимать только: габитус, цвет, ПЭЯ/ПГС'), null=True, blank=True,
                                                 default="")
    undesired_UCP_SG_appearance = models.TextField(_('Не снимать: габитус, цвет, ПЭЯ/ПГС'), null=True, blank=True,
                                                   default="")
    graph_comm = models.TextField(_('Комментарии к заявке'), blank=True)

    experiment_start_date = models.DateField(_('Дата эксперимента'), null=True, blank=True)
    experiment_start = models.TimeField(_('Время начала эксперимента'), null=True, blank=True)
    experiment_end = models.TimeField(_('Время конца эксперимента'), null=True, blank=True)
    experiment_end_date = models.DateField(_('Дата конца эксперимента'), null=True, blank=True)
    diffractometer = models.ForeignKey(
        DiffDevice,
        verbose_name=_('Дифрактометр'),
        on_delete=models.PROTECT,
        related_name='applications',
    )
    probe_count = models.PositiveIntegerField(_('Количество проб'), default=0, blank=True)

    commentary = models.TextField(_('Комментарий'), blank=True)
    application_prepared_by = models.ForeignKey(
        CustomUser,
        verbose_name=_('Заявку подготовил'),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='prepared_applications'
    )


    experiment_temp = models.IntegerField(
        _('Температура эксперимента, К'),

        null=False,
        blank=False,
        default=220,
        help_text=_('Температура в K'),
        validators=[
            MinValueValidator(80),
            MaxValueValidator(500)
        ]
    )
    EXPERIMENT_CHOICES = (
        ('stns', _('Стандартная съемка на структуру')),
        ('stnp', _('Стандартная съемка на параметры')),
        ('powd', _('Порошковая дифрактограмма')),
        ('nstn', _('Нестандартный эксперимент, пояснение в комментарии')),
    )

    experiment_type = models.CharField(
        _('Тип эксперимента'),
        max_length=50,
        choices=EXPERIMENT_CHOICES,
        default='',
    )
    public = models.BooleanField(default=False)


    STATUS_CHOICES = (
        ('draft', _('Черновик')),
        ('submitted', _('Подана')),
        ('rejected', _('Отклонена')),
        ('completed', _('Завершена')),
    )

    POST_STORAGE_CHOICES = (
        ('cupboard', _('Хранится в шкафу')),
        ('freezer', _('Хранится в морозилке')),
        ('operator', _('Хранится у оператора')),
        ('structurer', _('Передано структурщику')),
        ('re', _('Передано на повторное исследование')),
        ('not_found', _('Не обнаружено в указанном месте')),
        ('taken', _('Забрали')),
        ('not_provided', _('Не предоставленно')),
        ('dumped', _('Выброшено')),
    )
    sample_storage_post_exp = models.CharField(_('Хранение образца после эксперимента'), choices=POST_STORAGE_CHOICES,
                                               blank=True, default=None, null=True)
    DATA_STATUS_CHOICES = (
        ('NO_DATA', _('Нет данных')),
        ('NEED_REDUCTION', _('Данные необходимо редуцировать')),
        ('DATA_REDUCED', _('Данные редуцированы')),
        ('DATA_SENT', _('Данные отправлены')),
    )
    POST_EXP_STORAGE_RETURN_CHECK = ('dumped', 'structurer', 're', 'taken', 'not_provided', 'not_found')

    sample_returned = models.BooleanField(_("Образец забрали"), blank=True, default=False)
    raw_data_dir = models.CharField(_('Директория сырых данных'), blank=True, default='')
    data_status = models.CharField(
        _('Статус данных'),
        max_length=20,
        choices=DATA_STATUS_CHOICES,
        default=DATA_STATUS_CHOICES[0][0],
    )
    prev_data_status = models.CharField(
        _('Прошлый Статус данных'),
        default='',
        max_length=20, )
    status = models.CharField(
        _('Статус заявки'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='submitted'
    )

    proc_status_application = models.CharField(
        _('Статусы обработки проб'),
        max_length=100,
        blank=True,
        default=''
    )
    smpl_type_application = models.CharField(
        _('Типы проб'),
        max_length=100,
        blank=True,
        default=''
    )
    data_quantity_application = models.CharField(
        _('Описания данных'),
        max_length=500,
        blank=True,
        default=''
    )
    dmin_application = models.CharField(
        _('Разрешения'),
        max_length=100,
        blank=True,
        default=''
    )
    prev_status = models.CharField(
        _('Предыдущий статус'),
        max_length=20,
        choices=STATUS_CHOICES,
        blank=True,
        null=True,
        editable=False
    )

    locked_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="locked_applications",
        verbose_name="Заблокировано оператором"
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    reduced_data_dir = models.CharField(
        _('Путь к редуцированным данным'),
        max_length=200,
        blank=True,
        null=True,
        default=None
    )

    def __str__(self):
        """
        String representation of the Application instance.

        Returns:
            str: Combination of sample code and client's short name.
        """
        return self.sample_code + ' ' + self.client.get_short_name()

    def update_aggregated_fields(self):
        """
        Safely update aggregated fields based on related probe records.

        Collects data from all related Probe objects and aggregates it into
        concatenated string fields for efficient display. Uses '♠' as a
        placeholder for null values to maintain string length consistency.
        """
        probes = self.probes.order_by('number')

        self.probe_count = len(probes)

        def safe_str(v):
            return str(v or '♠')

        self.proc_status_application = ''.join(safe_str(p.proc_status) for p in probes)
        self.smpl_type_application = ''.join(safe_str(p.smpl_type) for p in probes)
        self.data_quantity_application = ''.join(safe_str(p.data_quantity) for p in probes)
        self.dmin_application = ''.join(safe_str(p.dmin) for p in probes)

        super().save(update_fields=[
            'proc_status_application',
            'smpl_type_application',
            'data_quantity_application',
            'dmin_application',
            'probe_count',
        ])

    def save(self, *args, **kwargs):
        """
        Custom save method with time tracking and status history.

        Performs several operations:
        1. Computes time spent if experiment dates/times are provided
        2. Updates laboratory time quota consumption
        3. Tracks previous status and data status for change monitoring
        4. Updates aggregated fields when application is completed

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        logger.info(f'Im saving: {kwargs}')
        if self.pk:
            try:
                if not ('update_fields' in tuple(kwargs.keys())):
                    logger.info(f'Im updating time')
                    time_spent_compute = self.compute_time_spent(self.experiment_start_date, self.experiment_start,
                                                                 self.experiment_end_date, self.experiment_end)
                    if time_spent_compute:
                        if self._current_time:
                            self.lab.consume_time(time_spent_compute - self._current_time)
                        else:
                            self.lab.consume_time(time_spent_compute)
                        self.time_spent = time_spent_compute
                old_instance = Application.objects.get(pk=self.pk)
                self.prev_data_status = old_instance.data_status
                self.prev_status = old_instance.status
            except Application.DoesNotExist:
                self.prev_status = None
        else:
            self.prev_status = None

        created = not self.pk
        super().save(*args, **kwargs)
        self._prev_status = self.status

        if created and self.status == 'completed':
            self.update_aggregated_fields()

    class Meta:
        """
        Metadata class for Application model.

        Defines verbose names for admin interface and default ordering
        by creation date in descending order.
        """
        verbose_name = _('Заявка')
        verbose_name_plural = _('Заявки')
        ordering = ['-date']

    def compute_time_spent(self, sd, st, ed, et):
        """
        Calculate time spent on the experiment in hours.

        Computes duration between experiment start and end, handling overnight
        experiments and quota compensation. For multi-day experiments, uses
        the diffractometer's predefined night experiment duration.

        Args:
            sd (date or str): Experiment start date.
            st (time or str): Experiment start time.
            ed (date or str): Experiment end date.
            et (time or str): Experiment end time.

        Returns:
            Decimal: Total hours spent, rounded to 2 decimal places, or None
                     if any date/time parameter is missing.
        """
        if not all([sd, st, ed, et]):
            return None

        if isinstance(sd, str):
            sd = date.fromisoformat(sd)
        if isinstance(ed, str):
            ed = date.fromisoformat(ed)
        if isinstance(st, str):
            st = time.fromisoformat(st)
        if isinstance(et, str):
            et = time.fromisoformat(et)

        if sd != ed:
            hours = self.diffractometer.time_cons_night_experiment

            if hasattr(hours, 'total_seconds'):
                hours = hours.total_seconds() / 3600
            else:
                hours = float(hours)

            return Decimal(round(hours, 2))

        start_dt = datetime.combine(sd, st)
        end_dt = datetime.combine(ed, et)

        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        delta = end_dt - start_dt

        qc = getattr(self, "quota_compensation", None)
        if qc:
            if hasattr(qc, 'total_seconds'):
                delta += qc
            else:
                delta += timedelta(hours=float(qc))

        total_hours = delta.total_seconds() / 3600

        return Decimal(round(total_hours, 2))

    @property
    def priority(self):
        """
        Calculate dynamic priority score based on deadline and ASAP status.

        Priority scoring logic:
        - ASAP applications: 100
        - Overdue applications: 101
        - Applications with deadline within 14 days: linear scale 0-100
        - Applications with deadline >14 days away: 0
        - Applications without deadline: 0

        Returns:
            float: Priority score between 0 and 101.
        """
        if self.asap_priority:
            return 100

        if not self.deadline:
            return 0

        now = timezone.now()
        time_left = self.deadline - now

        if time_left <= timedelta(0):
            return 101

        days_left = time_left.days + (time_left.seconds / 86400)

        if days_left > 14:
            return 0

        return min(100, round(100 * (1 - days_left / 14), 2))

    def mark_all_probe_statuses_reduced(self):
        """
        Mark all related probes as reduced and update application data status.

        Iterates through all probes associated with this application, marks each
        as reduced, and updates the aggregated status string. Finally updates
        the application's data status to 'DATA_REDUCED'.
        """
        probes = self.probes.order_by('number')

        if probes:
            old_probe_statuses = []
            new_probe_statuses = []
            for p in probes:
                old_probe_statuses.append(p.proc_status)
                p.mark_reduced()
                new_probe_statuses.append(p.proc_status)
            if old_probe_statuses != new_probe_statuses:
                self.proc_status_application = ''.join(status for status in new_probe_statuses)
                self.data_status = 'DATA_REDUCED'
                super().save(update_fields=['proc_status_application', 'data_status'])

    def mark_all_reduced_probe_statuses_posted(self):
        """
        Mark all reduced probes as posted and update application data status.

        Similar to mark_all_probe_statuses_reduced, but transitions from
        'DATA_REDUCED' to 'DATA_SENT' status for data that has been sent
        to the client.
        """
        probes = self.probes.order_by('number')
        if probes:
            old_probe_statuses = []
            new_probe_statuses = []
            for p in probes:
                old_probe_statuses.append(p.proc_status)
                p.mark_posted()
                new_probe_statuses.append(p.proc_status)
            if old_probe_statuses != new_probe_statuses:
                self.proc_status_application = ''.join(status for status in new_probe_statuses)
                self.data_status = 'DATA_SENT'
                self.save(update_fields=['proc_status_application', 'data_status'])

    def mark_as_returned(self):
        """
        Mark the sample as returned to the client.

        Updates the sample_returned field to True and saves the change.
        """
        self.sample_returned = True
        self.save(update_fields=['sample_returned'])

    @property
    def can_download(self):
        """
        Check if data from this application is available for download.

        Returns:
            bool: True if data status is 'DATA_SENT', False otherwise.
        """
        return self.data_status == 'DATA_SENT'

    @property
    def previous_status(self):
        """
        Get the previous status of the application before the last save.

        Returns:
            str: The previous status value stored in _prev_status attribute.
        """
        return self._prev_status