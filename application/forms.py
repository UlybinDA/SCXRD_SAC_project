from django import forms
from django.db.models import ForeignKey
from django.utils.safestring import mark_safe
from diffdevices.models import DiffDevice
from .models import Application, Operator, ApplicationDraft, Laboratory
import json
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ApplicationCreateForm(forms.ModelForm):
    """
    Django ModelForm for creating new Application instances.

    This form handles the creation of new applications with user-specific field
    adjustments, draft-saving capabilities, and custom tooltips for form fields.
    It supports conditional field requirements based on user permissions and
    draft status.
    """

    tooltips = {
        'client': "Пользователь, подавший заявку на исследование",
        'supervisor': "Руководитель пользователя",
        'sample_code': "Код образца",
        'experiment_temp': "Температура проведения съемки",
        'experiment_type': "Тип эксперимента",
        'deadline': "Дата, до которой необходимо провести эксперимент. Доступно только зав. лаб. и куратору",
        'date': "Дата подачи заявки",
        'lab': "Подразделение за которым будет числится заявка, время затраченное на выполнение будет вычтено из квоты данного подразделения",
        'operator_desired': """Желаемый оператор для проведения работ<br>
        "Желаемый" Оператор выбирается только в случае необходимости нерутинного эксперимента (длительная или нетривиальная пробоподготовка, выбор нестандартных условий эксперимента, позволивших получить данные подходящего качества) может претендовать на авторские права при использовании результатов 
        """,
        'inter_telephone': "Внутренний телефон",
        'urgt_comm': "Контакты для срочной связи: сотовый телефон, контакты TG/WA ",
        'structurer_desired': """Желаемый структурщик.<br>
        Структурщик - сотрудник, занимающийся РСА (обработкой полученных экспериментальных данных, определением структурной модели, ее верификацией) и депонированием результатов в структурные базы данных.<br>
        Структурщик имеет авторское право на результат проведенного РСА.<br>
        Структурщик несет ответственность за корректность структурной модели и правильность ее депонирования.<br>
        При публикации структуры Структурщик должен предоставить техническое описание эксперимента, таблицы с экспериментальными параметрами и изображение структурного фрагмента, иллюстрирующего качество структурной модели.<br>
        В случае необходимости Структурщик должен подготовить текст с обоснованием правильности выбора модели.""",
        'crystchemist_desired': """Желаемый кристаллохимик.<br>
        Кристаллохимик - сотрудник, проводящий кристаллохимический анализ структурной модели и ее описание.<br>
            Кристаллохимик имеет авторское право на результат проведенного кристаллохимического анализа.<br>
            Кристаллохимик несет ответственность за корректность и полноту кристаллохимичесокого анализа.<br>
            При публикации структуры Кристаллохимик должен предоставить текст с описанием проведенного анализа и при необходимости таблицы с геометрическими характеристиками структурной модели, а также поясняющие рисунки.
        """,
        'project': "Номер проекта или договора в рамках которого выполняется исследование. При выполнении госзадания указать 'НИР' пример:РНФ 20-03-001 или НИР.",
        'presence_is_necessary': "Требуется ли присутствие заказчика при эксперименте",
        'diffractometer': "Тип дифрактометра для проведения измерений",
        'sample_storage': "Условия хранения образца до эксперимента",
        'sample_storage_conditions': "Особые условия хранения образца",
        'sample_appearance': "Внешний вид и морфология образца",
        'composition': "Химический/структурный состав образца",
        'mother_solution': "Состав маточного (МР) раствора<br> Обратить внимание на:<br>летучие/токсичные/ЛВЖ/кислоты/окислители/восстановители вещества в МР",
        'tare': "Тара или контейнер для образца",
        'asap_priority': 'Выставить наибольший приоритет среди заявок лаборатории. Доступно только зав. лаб. и куратору',
        'desired_UCP_SG_appearance': """Снимать образцы с подходящими параметрами габитуса, цвета, элементарной ячейки и пространственной группы.<br>
        Для однозначности пункта рекомендуется использовать логические операторы &-И и |-ИЛИ:<br>
        Пример: кристалл - вытянутая игла, красного цвета.<br>
        Условие: Красные кристаллы &(И) вытянутая форма -> СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) (вытянутая форма |(ИЛИ) октаэдры) -> СНИМАЕМ!<br>
        Условие: Красные кристаллы |(ИЛИ) октаэдры -> СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) октаэдры -> НЕ СНИМАЕМ!<br>
        """,
        'undesired_UCP_SG_appearance': """Не снимать образцы с подходящими параметрами габитуса, цвета, элементарной ячейки и пространственной группы.<br>
        Для однозначности пункта рекомендуется использовать логические операторы &-И и |-ИЛИ:<br>
        Пример: кристалл - вытянутая игла, красного цвета.<br>
        Условие: Красные кристаллы &(И) вытянутая форма -> НЕ СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) (вытянутая форма |(ИЛИ) октаэдры) -> НЕ СНИМАЕМ!<br>
        Условие: Красные кристаллы |(ИЛИ) октаэдры -> НЕ СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) октаэдры -> СНИМАЕМ!<br>
        """,
        'graph_comm': "Комментарий пользователя к заявке",
        'experiment_start_date': "Дата начала эксперимента",
        'experiment_start': "Время начала эксперимента",
        'experiment_end_date': "Дата окончания эксперимента",
        'experiment_end': "Время окончания эксперимента",
        'sample_returned': "Возвращен ли образец заказчику",
        'raw_data_dir': "Путь к директории с исходными данными измерений",
        'commentary': "Комментарий оператора, редуктора данных",
    }

    def __init__(self, *args, **kwargs):
        """
        Initialize the ApplicationCreateForm with user-specific settings.

        This constructor extracts user information and draft settings from kwargs,
        configures field querysets based on user permissions, and adjusts field
        requirements for draft-saving mode. It also applies template-specific
        CSS classes to draft fields.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments containing:
                user (User): The current user for permission-based field filtering.
                draft_fields (list): List of field names that are part of a draft.
                save_as_draft (bool): Flag indicating if the form should save as a draft.
        """
        self.user = kwargs.pop('user', None)
        self.draft_fields = kwargs.pop('draft_fields', [])
        self.save_as_draft = kwargs.pop('save_as_draft', False)
        super().__init__(*args, **kwargs)
        home_lab = self.user.laboratory
        lab_permissions = self.user.lab_permissions.all()

        if lab_permissions.exists():
            lab_ids = list(lab_permissions.values_list('pk', flat=True))
            lab_ids.append(home_lab.pk)
            instance_lab = getattr(self.instance, 'lab', None)
            if instance_lab and instance_lab.pk not in lab_ids:
                lab_ids = [instance_lab.pk] + lab_ids
            init_lab = instance_lab if instance_lab else home_lab
            qs = Laboratory.objects.filter(pk__in=lab_ids)
            self.fields['lab'] = forms.ModelChoiceField(
                queryset=qs,
                required=True,
                empty_label=None,
                initial=init_lab
            )

        if self.save_as_draft:
            for field in self.fields.values():
                field.required = False

        if self.user and (self.user.is_chief or self.user.is_underchief):
            self.fields['asap_priority'] = forms.BooleanField(required=False)

        self.fields['diffractometer'].queryset = DiffDevice.objects.filter(is_available=True)
        self.fields['operator_desired'].queryset = Operator.objects.filter(is_active=True)

        for field_name in self.fields:
            if field_name in self.draft_fields:
                if hasattr(ApplicationDraft.TemplateClasses, field_name):
                    template_class = getattr(ApplicationDraft.TemplateClasses, field_name)
                    current_class = self.fields[field_name].widget.attrs.get('class', '')
                    self.fields[field_name].widget.attrs['class'] = (
                        f'{current_class} template-{template_class}'
                    )

    class Meta:
        """
        Metadata class for ApplicationCreateForm.

        Defines the model, fields to include, and custom widgets with autocomplete
        data attributes for form fields. Provides predefined option lists for
        various dropdown and autocomplete fields.
        """

        model = Application
        fields = ('sample_storage',
                  'sample_storage_conditions',
                  'tare',
                  'sample_appearance',
                  'mother_solution',
                  'structurer_desired',
                  'operator_desired',
                  'crystchemist_desired',
                  'sample_code',
                  'composition',
                  'presence_is_necessary',
                  'desired_UCP_SG_appearance',
                  'undesired_UCP_SG_appearance',
                  'graph_comm',
                  'diffractometer',
                  'project',
                  'deadline',
                  'experiment_temp',
                  'experiment_type',
                  'urgt_comm',
                  'inter_telephone'
                  )

        TARE_OPTIONS = [
            'бюкс с крышкой',
            'виалка с пластиковой крышкой',
            'пенициллинка с резиновой пробкой',
            'пробирка Эппендорфа',
            'запаянная ампула',
            'U-образная трубка',
            'чашка Петри',
            'стакан или выпаривательная чашка, закрытая парафилмом',
            'предметное стекло',
            'колба <100 мл',
            'контейнер с Ar',
            'полиэтиленовый пакет'
        ]

        SAMPLE_APPEARANCE_OPTIONS = [
            'кристаллический, без маточного раствора (сухой)',
            'порошок, без маточного раствора (сухой)',
            'кристаллический, со следами маточного раствора/масла (влажный)',
            'порошок, со следами маточного раствора/масла (влажный)',
            'кристаллический, под маточным раствором/маслом',
            'порошок, под маточным раствором/маслом',
            'готовые образцы на вкладышах ГГ',

        ]

        MOTHER_SOLUTION_OPTIONS = [
            'ацетонитрил (MeCN)',
            'диметилформамид (DMF)',
            'хлороформ (CHCl3)',
            'хлористый метилен (CH2Cl2)',
            'диэтиловый эфир (Et2O)',
            'метиловый спирт (MeOH)',
            'этиловый спирт (EtOH)',
            'изопропиловый спирт (iPrOH)',
            'ацетон (MeAc)',
            'тетрагидрофуран (THF)',
            'бензол/толуол (PhR, R=H, Me)',
            'гексан/гептан (CnH2n+2, n=6-7)',
            'диметилсульфоксид (DMSO)',
            ' нейтральный водный раствор, pH~7',
            'кислый водный раствор, pH<5',
            'сильнокислый водный раствор, pH<2',
            'щелочной водный раствор, pH>9',
            'сильнощелочной водный раствор, pH>12'
        ]

        SAMPLE_STORAGE_OPTIONS = [
            'шкаф, лаб.301, ЛВЖ',
            'шкаф, лаб.308, ЛВЖ',
            'шкаф, лаб.311, ЛВЖ',
            'шкаф, лаб.312, ЛВЖ',
            'шкаф, лаб.338, ЛВЖ',
            'шкаф, лаб.339, ЛВЖ',
            'шкаф, общий, ЛВЖ',
            'шкаф, сухие образцы и запаянные ампулы',
            'шкаф, кислоты и окислители',
            'шкаф, водн. р-ры и негигроскопичные нелетучие образцы',
            'шкаф, U-трубки',
            'мор. камера, лаб.312, ЛВЖ',
            'мор. камера, общий, ЛВЖ',
            'будет предоставлено перед экспериментом',
            'передано ответственному оператору',
        ]

        SAMPLE_STORAGE_CONDITIONS_OPTIONS = [
            'особых условий не требуется',
            'морозильная камера',
            'эксикатор с силикагелем',
            'в темноте',
            '-',
        ]

        widgets = {
            'sample_storage': forms.TextInput(attrs={
                'id': 'id_sample_storage',
                'data-options': json.dumps(SAMPLE_STORAGE_OPTIONS)
            }),
            'sample_storage_conditions': forms.TextInput(attrs={
                'id': 'id_sample_storage_conditions',
                'data-options': json.dumps(SAMPLE_STORAGE_CONDITIONS_OPTIONS)
            }),
            'tare': forms.TextInput(attrs={
                'id': 'id_tare',
                'data-options': json.dumps(TARE_OPTIONS)
            }),
            'sample_appearance': forms.TextInput(attrs={
                'id': 'id_sample_appearance',
                'data-options': json.dumps(SAMPLE_APPEARANCE_OPTIONS)
            }),
            'mother_solution': forms.TextInput(attrs={
                'id': 'id_mother_solution',
                'data-options': json.dumps(MOTHER_SOLUTION_OPTIONS)
            }),
            'experiment_temp': forms.NumberInput(attrs={
                'id': 'id_experiment_temp',
                'min': 80,
                'max': 500,
                'step': 5,
                'place-holder': '80-500 K'
            }),
            'desired_UCP_SG_appearance': forms.Textarea(attrs={
                'rows': 3,
                'cols': 30,
                'class': 'form-control'
            }),
            'undesired_UCP_SG_appearance': forms.Textarea(attrs={
                'rows': 3,
                'cols': 30,
                'class': 'form-control'
            }),
            'composition': forms.Textarea(attrs={
                'rows': 3,
                'cols': 30,
                'class': 'form-control'
            }),
            'graph_comm': forms.Textarea(attrs={
                'rows': 3,
                'cols': 30,
                'class': 'form-control'
            }),
        }


class ApplicationProcessForm(forms.ModelForm):
    """
    Django ModelForm for processing existing Application instances.

    This form is used during the experiment processing stage to update application
    data. It organizes fields into logical groups, marks many fields as read-only,
    provides validation based on action type (completed/rejected/save).

    Attributes:
        field_groups (dict): Logical grouping of form fields for display.
        tooltips (dict): Mapping of field names to tooltip text in Russian.
        readonly_fields (list): Field names that should be displayed as read-only.
    """

    field_groups = {
        "Информация о заявке": ['client', 'supervisor', 'sample_code', 'experiment_temp', 'experiment_type', 'deadline',
                                'date', 'lab', 'operator_desired',
                                'inter_telephone', 'urgt_comm', 'structurer_desired', 'crystchemist_desired',
                                'presence_is_necessary', 'diffractometer'],
        "Хранение": ['sample_storage', 'sample_storage_conditions'],
        "Информация об образце": ['sample_appearance', 'composition', 'mother_solution', 'tare',
                                  'desired_UCP_SG_appearance',
                                  'undesired_UCP_SG_appearance', 'graph_comm'],
        "Время": ['experiment_start_date', 'experiment_start', 'experiment_end_date', 'experiment_end'],
        "Постэкспериментальное хранение": ['sample_storage_post_exp', 'sample_returned', 'raw_data_dir'],
        'Комментарий': ['commentary', ],
    }
    tooltips = {
        'client': "Пользователь, подавший заявку на исследование",
        'supervisor': "Руководитель пользователя",
        'sample_code': "Код образца",
        'experiment_temp': "Температура проведения съемки",
        'experiment_type': "Тип эксперимента",
        'deadline': "Дата, до которой необходимо провести эксперимент. Доступно только зав. лаб. и куратору",
        'date': "Дата подачи заявки",
        'lab': "Подразделение пользователя",
        'operator_desired': "Желаемый оператор для проведения работ",
        'inter_telephone': "Контактный телефон для связи",
        'urgt_comm': "Контакты для срочной связи: сотовый телефон, контакты TG/WA",
        'presence_is_necessary': "Требуется ли присутствие заказчика при эксперименте",
        'diffractometer': "Тип дифрактометра для проведения измерений",
        'sample_storage': "Условия хранения образца до эксперимента",
        'sample_storage_conditions': "Особые условия хранения образца",
        'sample_appearance': "Внешний вид и морфология образца",
        'composition': "Химический/структурный состав образца",
        'mother_solution': "Состав маточного (МР) раствора<br> Обратить внимание на:<br>летучие/токсичные/ЛВЖ/кислоты/окислители/восстановители вещества в МР",
        'tare': "Тара или контейнер для образца",

        'desired_UCP_SG_appearance': """Снимать образцы с подходящими параметрами габитуса, цвета, элементарной ячейки и пространственной группы.<br>
        Для однозначности пункта рекомендуется использовать логические операторы &-И и |-ИЛИ:<br>
        Пример: кристалл - вытянутая игла, красного цвета.<br>
        Условие: Красные кристаллы &(И) вытянутая форма -> СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) (вытянутая форма |(ИЛИ) октаэдры) -> СНИМАЕМ!<br>
        Условие: Красные кристаллы |(ИЛИ) октаэдры -> СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) октаэдры -> НЕ СНИМАЕМ!<br>
        """,
        'undesired_UCP_SG_appearance': """Не снимать образцы с подходящими параметрами габитуса, цвета, элементарной ячейки и пространственной группы.<br>
        Для однозначности пункта рекомендуется использовать логические операторы &-И и |-ИЛИ:<br>
        Пример: кристалл - вытянутая игла, красного цвета.<br>
        Условие: Красные кристаллы &(И) вытянутая форма -> НЕ СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) (вытянутая форма |(ИЛИ) октаэдры) -> НЕ СНИМАЕМ!<br>
        Условие: Красные кристаллы |(ИЛИ) октаэдры -> НЕ СНИМАЕМ!<br>
        Условие: Красные кристаллы &(И) октаэдры -> СНИМАЕМ!<br>
        """,
        'graph_comm': "Комментарий пользователя к заявке",
        'experiment_start_date': "Дата начала эксперимента",
        'experiment_start': "Время начала эксперимента",
        'experiment_end_date': "Дата окончания эксперимента",
        'experiment_end': "Время окончания эксперимента",
        'sample_storage_post_exp': "Условия хранения образца после эксперимента",
        'sample_returned': "Возвращен ли образец заказчику",
        'raw_data_dir': "Путь к директории с исходными данными измерений",
        'commentary': "Комментарий оператора, редуктора данных",
    }
    readonly_fields = ['client',
                       'supervisor',
                       'lab',
                       'client_home_lab',
                       'inter_telephone',
                       'urgt_comm',
                       'application_code',
                       'date',
                       'sample_storage',
                       'sample_storage_conditions',
                       'tare',
                       'sample_appearance',
                       'mother_solution',
                       'structurer_desired',
                       'operator_desired',
                       'crystchemist_desired',
                       'sample_code',
                       'composition',
                       'presence_is_necessary',
                       'desired_UCP_SG_appearance',
                       'undesired_UCP_SG_appearance',
                       'graph_comm',
                       'diffractometer',
                       'project',
                       'deadline',
                       'experiment_temp',
                       'experiment_type',
                       ]

    def get_grouped_fields(self):
        """
        Organize form fields into logical groups for template rendering.

        Processes each field group defined in `field_groups`, extracting field
        objects, labels, help text, read-only status, and display values.
        For ModelChoiceFields, uses string representation of the related object.

        Returns:
            dict: Dictionary with group names as keys and lists of field
                  information dictionaries as values.
        """
        grouped = {}
        for group, fields in self.field_groups.items():
            grouped_fields = []
            for field_name in fields:
                if field_name in self.fields:
                    field_obj = self[field_name]
                    raw_value = getattr(self.instance, field_name, None)


                    if isinstance(self.fields[field_name], forms.ModelChoiceField):
                        display_value = str(raw_value) if raw_value is not None else ""
                    elif hasattr(self.fields[field_name], 'choices') and self.fields[field_name].choices:
                        choices_dict = dict(self.fields[field_name].choices)
                        display_value = choices_dict.get(raw_value, raw_value)
                    else:
                        display_value = raw_value

                    grouped_fields.append({
                        'name': field_name,
                        'field': field_obj,
                        'label': self.fields[field_name].label,
                        'help_text': self.fields[field_name].help_text,
                        'is_readonly': (
                                self.fields[field_name].disabled or
                                self.fields[field_name].widget.attrs.get('readonly')
                        ),
                        'value': display_value,
                    })
            grouped[group] = grouped_fields
        return grouped

    def __init__(self, *args, **kwargs):
        """
        Initialize the ApplicationProcessForm with user-specific settings.

        Sets up Bootstrap tooltips for form fields, configures read-only fields
        based on `readonly_fields` list, and pre-populates the `raw_data_dir`
        field with the operator's default directory prefix if available.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments containing:
                user (User): The current user for operator profile lookup.
        """
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        for field_name, tooltip in self.tooltips.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'data-bs-toggle': 'tooltip',
                    'data-bs-placement': 'top',
                    'title': tooltip
                })

        for field_name in self.readonly_fields:
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

        if self.user and hasattr(self.user, 'operator_profile'):
            operator_profile = self.user.operator_profile
            if operator_profile and operator_profile.default_dir_prefix:

                if not self.initial.get('raw_data_dir') and not self.instance.raw_data_dir:
                    self.initial['raw_data_dir'] = operator_profile.default_dir_prefix

    def get_operator_prefix(self):
        """
        Retrieve the operator's default directory prefix.

        Returns the default directory prefix from the operator profile
        associated with the current user, if available.

        Returns:
            str: Operator's default directory prefix or empty string.
        """
        if self.user and hasattr(self.user, 'operator_profile'):
            operator_profile = self.user.operator_profile
            return operator_profile.default_dir_prefix if operator_profile else ''
        return ''

    def clean(self):
        """
        Validate form data based on the action type (completed or rejected).

        Performs conditional validation:
        - For 'completed' action: Checks required fields are filled
        - For 'rejected' action: Validates required fields and date/time logic
          (start date/time must be before end date/time)

        Returns:
            dict: Cleaned form data.

        Raises:
            forms.ValidationError: If validation fails for any required field
                                   or if date/time logic is invalid.
        """
        cleaned_data = super().clean()

        action = self.data.get('action')

        if action == 'completed':
            required_fields = [
                'experiment_start_date',
                'experiment_start',
                'experiment_end_date',
                'experiment_end',
                'sample_storage_post_exp',
                'raw_data_dir',
            ]
        elif action == 'rejected':
            required_fields = [
                'experiment_start_date',
                'experiment_start',
                'experiment_end_date',
                'experiment_end',
                'sample_storage_post_exp',
            ]

            errors = {}


            for field in required_fields:
                if not cleaned_data.get(field):
                    errors[field] = _('Поле должно быть заполнено')


            if not errors:
                start_date = cleaned_data.get('experiment_start_date')
                end_date = cleaned_data.get('experiment_end_date')
                start_time = cleaned_data.get('experiment_start')
                end_time = cleaned_data.get('experiment_end')

                if start_date and end_date:
                    if start_date > end_date:
                        errors['experiment_start_date'] = _('Дата начала не может быть позже даты окончания')
                    elif start_date == end_date and start_time and end_time and start_time >= end_time:
                        errors['experiment_start'] = _('Время начала должно быть раньше времени окончания')

            if errors:
                raise forms.ValidationError(errors)

        return cleaned_data

    class Meta:
        """
        Metadata class for ApplicationProcessForm.

        Specifies the model and excludes fields that should not be editable
        during the processing stage. Defines custom widgets for date and time
        inputs with appropriate HTML5 attributes.
        """

        model = Application

        exclude = [
            'status',
            'probe_count',
            'proc_status_application',
            'smpl_type_application',
            'data_quantity_application',
            'dmin_application',
            'sample_returned',
            'data_status',
            'prev_status',
            'prev_data_status',
            'operator',
            'application_prepared_by',
            'asap_priority'

        ]

        widgets = {
            'experiment_start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'date-input', 'id': 'experiment_start_date_id'},
                format='%Y-%m-%d',
            ),
            'experiment_start': forms.TimeInput(
                attrs={'type': 'time', 'class': 'time-input', 'id': 'experiment_start_id'},
            ),
            'experiment_end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'date-input', 'id': 'experiment_end_date_id'},
                format='%Y-%m-%d'
            ),
            'experiment_end': forms.TimeInput(
                attrs={'type': 'time', 'class': 'time-input', 'id': 'experiment_end_id'},
            ),
            'raw_data_dir': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Путь к данным'
            }),
        }


class JsonUploadForm(forms.Form):
    """
    Simple form for uploading JSON files containing info on published reduced experimental data.

    Used for importing application data statuses.
    """

    json_file = forms.FileField(
        label='Выберите JSON-файл',
        help_text='Поддерживаются только файлы в формате JSON',
        widget=forms.FileInput(attrs={'accept': '.json'})
    )