from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from labs.models import Laboratory

from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Manager for CustomUser that provides methods to create regular users and superusers.
    """

    def create_user(self, username, email, password=None, **extra_fields):
        """
        Create and save a User with the given username, email, and password.

        Args:
            username (str): The user's desired username.
            email (str): The user's email address. Must be provided.
            password (str, optional): Plain-text password for the user.
                If None, the user will have no password set.
            **extra_fields: Additional fields to set on the user instance.

        Returns:
            CustomUser: The newly created user instance.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given username, email, and password.
        A default laboratory named 'Administration' is created if it does not exist.

        Args:
            username (str): The superuser's desired username.
            email (str): The superuser's email address. Must be provided.
            password (str, optional): Plain-text password for the superuser.
                If None, the user will have no password set.
            **extra_fields: Additional fields to set on the superuser instance.

        Returns:
            CustomUser: The newly created superuser instance.
        """
        lab, created = Laboratory.objects.get_or_create(
            name='Administration',
            defaults={
                'organization': 'System Administration',
                'country': 'System',
                'city': 'System'
            }
        )

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('first_name', 'Admin')
        extra_fields.setdefault('last_name', 'User')
        extra_fields.setdefault('patronymic', 'Super')
        extra_fields.setdefault('position', self.model.Position.CHIEF)

        extra_fields.setdefault('laboratory', lab)

        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    User model extending Django's AbstractUser with additional fields and
    custom business logic for a laboratory-based application.
    """

    class Position(models.TextChoices):
        CHIEF = 'CH', _('Шеф')
        UNDERCHIEF = 'UC', _('Куратор')
        WORKER = 'WR', _('Сотрудник')
        STUDENT = 'ST', _('Студент')


    first_name = models.CharField(_('Имя'), max_length=150, blank=False)
    last_name = models.CharField(_('Фамилия'), max_length=150, blank=False)
    email = models.EmailField(_('Email'), unique=True, blank=False)
    objects = CustomUserManager()
    asap_access = models.BooleanField(default=False)
    deadline_access = models.BooleanField(default=False)
    gets_statistics = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    lab_permissions = models.ManyToManyField(Laboratory,
                                             verbose_name=_('Права подачи заявок от лабораторий'),
                                             blank=True,
                                             related_name='users_with_permissions')

    patronymic = models.CharField(
        _('Отчество'),
        max_length=150,
        blank=False
    )

    position = models.CharField(
        _('Должность'),
        max_length=2,
        choices=Position.choices,
        default=Position.WORKER,
        blank=False
    )
    laboratory = models.ForeignKey(
        Laboratory,
        verbose_name=_('Лаборатория'),
        on_delete=models.PROTECT,
        blank=False,
        null=False,
        related_name='users'
    )

    supervisor = models.ForeignKey(
        'self',
        verbose_name=_('Руководитель'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates',
    )

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        related_name="custom_user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        related_name="custom_user_set",
        related_query_name="user",
    )

    class Meta:
        verbose_name = _('Пользователь')
        verbose_name_plural = _('Пользователи')

    def __str__(self):
        """
        Human-readable representation of the user.
        """
        return f"{self.last_name} {self.first_name} {self.patronymic}"

    def clean(self):
        """
        Custom validation to ensure a user cannot be their own supervisor.

        Raises:
            ValidationError: If self.supervisor is equal to self.
        """
        super().clean()

        if self.supervisor:
            if self.supervisor == self:
                raise ValidationError(
                    {'supervisor': _('User cannot supervise themselves')}
                )

    def save(self, *args, **kwargs):
        """
        Override save to perform full_clean before persisting changes.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def get_full_name(self):
        """
        Return the user's full name (last name, first name and patronymic).

        Returns:
            str: Full name of the user.
        """
        return f"{self.last_name} {self.first_name} {self.patronymic or ''}".strip()

    def get_short_name(self):
        """
        Return a short representation of the user's name.

        Returns:
            str: Short name including initials of first and patronymic.
        """
        return f"{self.last_name} {self.first_name[0]}." +  f"{self.patronymic[0] + '.' if self.patronymic else ''}"

    @property
    def is_active_operator(self):
        """
        Check whether the user has an active operator profile.

        Returns:
            bool: True if an operator profile exists and is active, False otherwise.
        """
        return hasattr(self, 'operator_profile') and self.operator_profile.is_active

    @property
    def has_app_draft(self):
        """
        Determine if the user has any application drafts associated with them.

        Returns:
            bool: True if at least one draft exists, False otherwise.
        """
        return self.client_draft.exists()

    @property
    def is_chief(self):
        """
        Check if the user's position is Chief.

        Returns:
            bool: True if user is a chief, False otherwise.
        """
        return self.position == self.Position.CHIEF.value

    @property
    def is_underchief(self):
        """
        Check if the user's position is Underchief.

        Returns:
            bool: True if user is an underchief, False otherwise.
        """
        return self.position == self.Position.UNDERCHIEF.value

    @property
    def has_lab(self):
        """
        Verify that the user is associated with a laboratory.

        Returns:
            bool: True if laboratory is set, False otherwise.
        """
        return self.laboratory is not None

    def make_student(self):
        """
        Promote the user to the Student position and save changes.
        """
        self.position = CustomUser.Position.STUDENT
        self.save()

    def make_worker(self):
        """
        Promote the user to the Worker position and save changes.
        """
        self.position = CustomUser.Position.WORKER
        self.save()

    def make_underchief(self):
        """
        Promote the user to the Underchief position and save changes.
        """
        self.position = CustomUser.Position.UNDERCHIEF
        self.save()

    def deactivate(self):
        """
        Deactivate the user account by setting is_active to False.
        """
        self.is_active = False
        self.save()
