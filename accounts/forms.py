from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from labs.models import Laboratory
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.translation import gettext_lazy as _
from .models import CustomUser
from django.utils.crypto import get_random_string
import logging
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.template.loader import render_to_string
from django.conf import settings








logger = logging.getLogger(__name__)

class CustomUserCreationForm(forms.ModelForm):
    """Форма создания пользователя без ввода пароля"""
    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'patronymic',
            'email', 'position', 'supervisor'
        ]
        labels = {
            'username': _('Логин'),
            'first_name': _('Имя'),
            'last_name': _('Фамилия'),
            'patronymic': _('Отчество'),
            'email': _('Email'),
            'position': _('Должность'),
            'supervisor': _('Руководитель'),
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'patronymic': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'supervisor': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize the user creation form with additional context.
        Params:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments. Can include 'user_lab' and 'current_user'.
        Sets up position and supervisor field limits based on the laboratory and validates required fields.
        """
        self.user_lab = kwargs.pop('user_lab', None)
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        self.fields['position'].choices = [
            (CustomUser.Position.STUDENT, _('Студент')),
            (CustomUser.Position.WORKER, _('Сотрудник')),
        ]

        if self.user_lab:
            self.fields['supervisor'].queryset = CustomUser.objects.filter(
                laboratory=self.user_lab,
                is_active=True
            ).exclude(
                position=CustomUser.Position.STUDENT
            )

        for field in ['first_name', 'last_name', 'patronymic', 'email']:
            self.fields[field].required = True

    def generate_temp_password(self):
        """
        Generate a random temporary password for the new user.
        Returns:
            str: A randomly generated password containing 10 characters (excluding ambiguous ones).
        """
        return get_random_string(10, 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789')

    def save(self, commit=True):
        """
        Save the user object with a generated temporary password. Optionally assigns a laboratory if specified.
        Args:
            commit (bool): Whether to commit the save to the database immediately.
        Returns:
            user: The created user instance with the set password and (optionally) laboratory.
        """
        user = super().save(commit=False)
        user.set_password(self.generate_temp_password())
        if self.user_lab:
            user.laboratory = self.user_lab
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """
        Initialize the user change form and limit the choices for the laboratory field.
        Args:
            *args: Variable positional arguments.
            **kwargs: Arbitrary keyword arguments.
        The laboratory field's queryset is limited to all existing laboratories.
        """
        super().__init__(*args, **kwargs)

        self.fields['laboratory'].queryset = Laboratory.objects.all()




class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'autofocus': True, 'placeholder': ''})
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update({'placeholder': ''})









class APasswordResetForm(PasswordResetForm):
    def clean_email(self):
        """
        Validate the entered email for password reset and log various scenarios if the user does not exist or is inactive.
        Returns:
            str: The cleaned email address if validation passes.
        Raises:
            forms.ValidationError: If the email is not associated with any user.
        """
        email = self.cleaned_data['email']
        logger.debug(f"APasswordResetForm.clean_email called with: {email}")
        

        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        users = list(self.get_users(email))
        if not users:
            logger.warning(f"No active users found for email: {email}")
            

            inactive_users = User.objects.filter(email__iexact=email, is_active=False)
            if inactive_users.exists():
                logger.warning(f"Found inactive user with email: {email}")
            

            all_users = User.objects.filter(email__iexact=email)
            if all_users.exists():
                logger.warning(f"Found users with different case: {[u.email for u in all_users]}")
            
            raise forms.ValidationError("Пользователь с таким email не найден.")
        
        logger.debug(f"Found {len(users)} users for email: {email}")
        return email

    def get_users(self, email):
        """
        Override to improve logging when fetching users for password reset by email.
        Args:
            email (str): The email address to search for.
        Returns:
            generator: Active users with a usable password matching the provided email.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        email_field_name = User.get_email_field_name()
        active_users = User._default_manager.filter(**{
            f'{email_field_name}__iexact': email,
            'is_active': True,
        })
        
        logger.debug(f"Searching for users with {email_field_name}__iexact={email}, is_active=True")
        logger.debug(f"Found {active_users.count()} active users")
        
        return (u for u in active_users if u.has_usable_password())
