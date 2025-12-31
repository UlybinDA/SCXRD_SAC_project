from django import forms
from accounts.models import CustomUser


class LaboratoryAddPermissionForm(forms.Form):
    """
    Form for granting laboratory access permissions to users.

    This form allows chief/underchief to select a user and grant them additional
    access permissions to a specific laboratory beyond their primary laboratory
    assignment. Validates that the user doesn't already have access and isn't
    already a member of the laboratory.

    Attributes:
        new_user (ModelChoiceField): Field for selecting the user to grant permissions to.
    """

    new_user = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        label="Пользователь"
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with laboratory context and dynamic queryset.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments containing:
                laboratory (Laboratory): The laboratory for which permissions are being granted.
        """
        self.laboratory = kwargs.pop('laboratory', None)
        super().__init__(*args, **kwargs)
        self.fields['new_user'].required = True


        if 'new_user' in self.data:
            try:
                user_id = int(self.data.get('new_user'))
                self.fields['new_user'].queryset = CustomUser.objects.filter(id=user_id)
            except (ValueError, TypeError):
                self.fields['new_user'].queryset = CustomUser.objects.none()

    def clean(self):
        """
        Validate form data to prevent duplicate permissions and invalid assignments.

        Checks if the selected user already has permissions for this laboratory
        or is already a primary member of the laboratory.

        Returns:
            dict: Cleaned form data.

        Raises:
            forms.ValidationError: If user already has access or is a laboratory member.
        """
        cleaned_data = super().clean()
        new_user = cleaned_data.get('new_user')

        if new_user and self.laboratory:
            if new_user.lab_permissions.filter(id=self.laboratory.id).exists():
                self.add_error(
                    'new_user',
                    f"У пользователя {new_user.get_full_name()} уже есть права доступа к этой лаборатории"
                )
            elif new_user.laboratory == self.laboratory:
                self.add_error(
                    'new_user',
                    f"Пользователь {new_user.get_full_name()} является сотрудником лаборатории"
                )

        return cleaned_data