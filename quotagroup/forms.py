from django import forms
from django.db.models import ForeignKey
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import QuotaTimeTransaction, QuotaGroup
from decimal import Decimal


class QuotaTimeTransactionForm(forms.ModelForm):
    """
    Django ModelForm for creating QuotaTimeTransaction instances with time input.

    This form facilitates time transfers between quota groups by providing separate
    hours and minutes fields for intuitive time entry. It includes validation for
    available time in the donor's quota and prevents transfers within the same group.
    """

    hours = forms.IntegerField(min_value=0, label="Часы")
    minutes = forms.IntegerField(min_value=0, max_value=59, label="Минуты")

    class Meta:
        """
        Metadata class for QuotaTimeTransactionForm.

        Specifies the model and fields to include in the form, focusing on the
        acceptor group selection while donor and time are determined programmatically.
        """

        model = QuotaTimeTransaction
        fields = ['quota_group_acceptor']

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with user-specific acceptor group filtering.

        Limits the acceptor group choices to active quota groups excluding the
        user's own quota group to prevent self-transfers.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments containing:
                user (User): The current user initiating the transfer.
        """
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and hasattr(self.user, 'laboratory') and hasattr(self.user.laboratory, 'quota_group'):
            user_quota = self.user.laboratory.quota_group
            self.fields['quota_group_acceptor'].queryset = QuotaGroup.objects.filter(
                is_active=True
            ).exclude(id=user_quota.id)
        else:
            self.fields['quota_group_acceptor'].queryset = QuotaGroup.objects.filter(is_active=True)

    def clean(self):
        """
        Validate form data with business logic for time transfers.

        Performs several validations:
        1. Converts hours and minutes to decimal time transfer value.
        2. Checks donor has sufficient time available for transfer.
        3. Prevents transfers to the same quota group.

        Returns:
            dict: Cleaned form data with added 'time_transfer' field.

        Raises:
            ValidationError: If donor has insufficient time or attempts self-transfer.
        """
        cleaned_data = super().clean()
        hours = cleaned_data.get('hours') or 0
        minutes = cleaned_data.get('minutes') or 0
        quota_group_acceptor = cleaned_data.get('quota_group_acceptor')

        time_transfer = Decimal(hours) + Decimal(minutes) / Decimal(60)
        cleaned_data['time_transfer'] = time_transfer

        if self.user and hasattr(self.user, 'laboratory') and quota_group_acceptor:
            donor_quota = self.user.laboratory.quota_group

            if donor_quota.current_time < time_transfer:
                self.add_error(
                    None,
                    f"Недостаточно времени."
                )

            if donor_quota == quota_group_acceptor:
                self.add_error(
                    None,
                    "Нельзя переводить время в ту же группу"
                )

        return cleaned_data

    def save(self, commit=True):
        """
        Save the form instance with automatic donor and user assignment.

        Sets the user, donor quota group, and calculated time transfer value
        before saving the transaction instance.

        Args:
            commit (bool): Whether to save the instance to the database.

        Returns:
            QuotaTimeTransaction: The saved or unsaved transaction instance.
        """
        instance = super().save(commit=False)
        if self.user and hasattr(self.user, 'laboratory'):
            instance.user = self.user
            instance.quota_group_donor = self.user.laboratory.quota_group
        instance.time_transfer = self.cleaned_data['time_transfer']
        if commit:
            instance.save()
        return instance