from django import forms
from .models import Probe, Application


class ProbeForm(forms.ModelForm):
    """
    Django ModelForm for Probe instances with grouped field display.

    This form organizes probe fields into logical groups for better UI presentation,
    includes tooltips for field explanations, and handles different validation
    requirements based on the action context (save/complete/reject).
    """

    field_groups = {
        "Внешний вид": ["size_x", "size_y", "size_z", "transparent", 'matte', 'metallic', "color1", "color2", "habit",
                        "photo_rotation"],
        "Параметры решётки": ["a", "b", "c", "al", "bt", "gm", "lattice_type", "volume"],
        "Основные данные": [
            "dmin", "smpl_type", "data_quantity", "scans_desc"
        ],
        "Результат": ["proc_status", "db_code_found", "temperature"],
    }

    tooltips = {
        'volume': "Объем рассчитывается автоматически на основе параметров a, b, c, al, bt, gm",
        'a': "Параметр a кристаллической решетки",
        'b': "Параметр b кристаллической решетки",
        'c': "Параметр c кристаллической решетки",
        'al': "Угол α в градусах",
        'bt': "Угол β в градусах",
        'gm': "Угол γ в градусах",
    }

    def get_grouped_fields(self):
        """
        Organize form fields into logical groups for template rendering.

        Processes each field group defined in `field_groups`, extracting field
        objects, labels, and help text for organized display in templates.

        Returns:
            dict: Dictionary with group names as keys and lists of field
                  information dictionaries as values.
        """
        grouped = {}
        for group, fields in self.field_groups.items():
            grouped_fields = []
            for field_name in fields:
                if field_name in self.fields:
                    grouped_fields.append({
                        'name': field_name,
                        'field': self[field_name],
                        'label': self.fields[field_name].label,
                        'help_text': self.fields[field_name].help_text,
                    })
            grouped[group] = grouped_fields
        return grouped

    def __init__(self, *args, **kwargs):
        """
        Initialize the ProbeForm with action-based field configuration.

        Adjusts field requirements based on action type, sets up tooltips,
        and configures read-only fields for calculated values.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments containing:
                action (str): Context action affecting field requirements ('save', 'completed', 'rejected').
        """
        self.action = kwargs.pop('action', None)
        action = kwargs.pop('action', None)
        super().__init__(*args, **kwargs)


        if action == 'save':
            for f in self.fields.values():
                f.required = False

        if not self.instance.pk:
            self.fields['proc_status'].choices = Probe.ProcStatus.processing_options()

        readonly_fields = ['volume']

        for field_name in readonly_fields:
            if field_name in self.fields:
                if isinstance(self.fields[field_name], forms.ModelChoiceField):
                    self.fields[field_name].disabled = True
                    self.fields[field_name].widget.can_add_related = False
                    self.fields[field_name].widget.can_change_related = False
                    self.fields[field_name].widget.can_delete_related = False
                    self.fields[field_name].widget.can_view_related = False
                else:
                    self.fields[field_name].disabled = True
                    self.fields[field_name].widget.attrs['readonly'] = True

        for field_name, tooltip in self.tooltips.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'data-bs-toggle': 'tooltip',
                    'data-bs-placement': 'top',
                    'title': tooltip
                })

    class Meta:
        """
        Metadata class for ProbeForm.

        Defines the model and fields to include in the form for probe data entry.
        """

        model = Probe
        fields = (

            "size_x", "size_y", "size_z", 'habit', 'matte', 'metallic',
            "transparent", "color1", "color2",
            "lattice_type", "a", "b", "c", "al", "bt", "gm",
            "volume", "photo_rotation",
            "dmin", "smpl_type", "data_quantity", "scans_desc",
            "db_code_found", "proc_status", "temperature"
        )


class BaseProbeFormSet(forms.BaseInlineFormSet):
    """
    Custom formset for Probe forms with action-based validation.

    Extends Django's BaseInlineFormSet to provide context-aware validation
    where field requirements differ based on whether the application is being
    saved, completed, or rejected.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the formset with action context.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments containing:
                action (str): Context action for validation rules.
        """
        self.action = kwargs.pop('action', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """
        Validate formset data with action-specific field requirements.

        Performs conditional validation based on the action context:
        - 'completed': Validates against Probe.required_on_complete fields
        - 'rejected': Validates against Probe.required_on_reject fields
        - 'save' or 'saved': No additional validation

        Raises:
            forms.ValidationError: If required fields are missing for the action.
        """
        super().clean()

        if not self.action or self.action == 'saved':
            return

        if self.action == 'completed':
            required_fields = Probe.required_on_complete
        elif self.action == 'rejected':
            required_fields = Probe.required_on_reject
        else:
            return

        has_error = False

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get('DELETE', False):
                continue

            missing = []
            for field in required_fields:
                value = form.cleaned_data.get(field)
                if not value:
                    form.add_error(field, "Это поле обязательно для заполнения при завершении заявки.")
                    missing.append(field)

            if missing:
                number = form.instance.number or '?'
                form.add_error(
                    None,
                    f"Проба №{number}: не заполнены обязательные поля — {', '.join(missing)}"
                )
                has_error = True

        if has_error:

            raise forms.ValidationError("Некоторые пробы не заполнены полностью — проверьте выделенные поля.")

    def add_fields(self, form, index):
        """
        Add fields to form with action-based requirement adjustments.

        Propagates the action context to individual forms and adjusts
        field requirements for 'save' action.

        Args:
            form (ProbeForm): Individual form in the formset.
            index (int): Position of the form in the formset.
        """
        super().add_fields(form, index)
        form.action = self.action
        if self.action == 'save':
            for f in form.fields.values():
                f.required = False


ProbeFormSet = forms.inlineformset_factory(
    parent_model=Application,
    model=Probe,
    form=ProbeForm,
    formset=BaseProbeFormSet,
    extra=0,
    can_delete=True
)