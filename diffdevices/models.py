from django.db import models
from django.utils.translation import gettext_lazy as _



class DiffDevice(models.Model):
    # Основная информация о заявке
    device_name = models.CharField(
        max_length=50,
        unique=True,
    )
    is_available = models.BooleanField(
        _('Доступный'),
        default=True,
        help_text=_('Отметьте, если прибор доступен')
    )
    time_cons_mult = models.DecimalField(
        'Множитель затрачиваемой квоты',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='1.00 - затрачивается реальное время'
    )
    time_cons_night_experiment = models.DecimalField(
        decimal_places=2,
        max_digits=6,
        null=True,
        blank=True,
        help_text='Трата квоты для ночного эксперимента'
    )
    def __str__(self):
        """
        Human-readable representation of the Diffractometer with time multiplier.
        """
        return f"{self.device_name}, множитель времени: {self.time_cons_mult}"

    class Meta:
        verbose_name = _('Дифрактометр')
        verbose_name_plural = _('Дифрактометры')
