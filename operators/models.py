from django.db import models
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _


class Operator(models.Model):
    """
    Model representing a crystallography equipment operator.

    Each operator is associated with a user account, has a unique code for identification,
    and may have a default directory prefix for organizing experimental data.

    Attributes:
        user (OneToOneField): Associated user account with operator privileges.
        code (str): Unique 5-character identifier for the operator.
        data_path (str): File system path to the operator's data storage.
        is_active (bool): Indicates if the operator is currently active.
        created_at (DateTimeField): Timestamp when the operator record was created.
        updated_at (DateTimeField): Timestamp when the operator record was last updated.
        default_dir_prefix (str): Default directory prefix for organizing experiment data.
    """

    user = models.OneToOneField(
        CustomUser,
        verbose_name=_('Пользователь'),
        on_delete=models.PROTECT,
        blank=False,
        null=False,
        related_name='operator_profile'
    )
    code = models.CharField(
        _('Код оператора'),
        max_length=5,
        unique=True,
        help_text=_('Уникальный идентификатор оператора')
    )
    data_path = models.CharField(
        _('Путь к данным'),
        max_length=100,
        help_text=_('Путь к данным оператора в файловой системе')
    )


    is_active = models.BooleanField(
        _('Активный'),
        default=True,
        help_text=_('Отметьте, если оператор активен')
    )
    created_at = models.DateTimeField(
        _('Дата создания'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('Дата обновления'),
        auto_now=True
    )

    default_dir_prefix = models.CharField(
        _('Префикс директории данных'),
        blank=True,
        null=True,
        default='',
    )

    class Meta:
        """
        Metadata class for Operator model.

        Defines verbose names for admin interface and default ordering by operator code.
        """
        verbose_name = _('Оператор')
        verbose_name_plural = _('Операторы')
        ordering = ['code']

    def __str__(self):
        """
        String representation of the Operator instance.

        Returns:
            str: Combination of operator's full name and code in parentheses.
        """

        return f"{self.user.get_full_name()} ({self.code})"

    @property
    def name(self):
        """
        Get the full name of the operator through the associated user.

        Returns:
            str: Full name of the associated user.
        """
        return self.user.get_full_name()

    @property
    def laboratory(self):
        """
        Get the laboratory of the operator through the associated user.

        Returns:
            Laboratory: The laboratory instance the operator belongs to.
        """
        return self.user.laboratory