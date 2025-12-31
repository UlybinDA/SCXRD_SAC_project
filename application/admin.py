from django.contrib import admin
from .models import Application, DiffDevice
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django import forms
from services.email_service import sample_takeaway_reminder_email
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect

from django.contrib import admin
from .models import Application, ApplicationDraft
from probe.models import Probe  # Или используйте строковый импорт


@admin.register(ApplicationDraft)
class ProbeAdmin(admin.ModelAdmin):
    """
    Admin interface for the ``ApplicationDraft`` model.
    """

    list_display = ['user']
    search_fields = ['user']
    fieldsets = ((_('Шаблонные поля'), {
        'fields': (
            'user',
            'project',
            'inter_telephone',
            'urgt_comm',
            'operator_desired',
            'structurer_desired',
            'crystchemist_desired',
            'sample_appearance',
            'composition',
            'mother_solution',
            'tare',
            'sample_storage',
            'sample_storage_conditions',
            'desired_UCP_SG_appearance',
            'undesired_UCP_SG_appearance',
            'diffractometer',
            'experiment_temp',
            'experiment_type',
        )
    }),)


# Register your models here.


class ProbeInline(admin.TabularInline):
    """
    Inline editing interface for the ``Probe`` model.
    """

    model = Probe
    extra = 0
    fields = (
        'number',
        'size_x',
        'size_y',
        'size_z',
        'color1',
        'lattice_type',
        'dmin',
        'proc_status'
    )
    show_change_link = True

    # Добавляем кастомные отображения
    @admin.display(description='Размеры')
    def sizes_display(self, obj):
        """
        Return a string representation of the probe dimensions.

        Args:
            obj (Probe): The probe instance being displayed.

        Returns:
            str: Human‑readable dimension string or '-' if any value is missing.
        """
        return f"{obj.size_x}×{obj.size_y}×{obj.size_z}" if all([obj.size_x, obj.size_y, obj.size_z]) else "-"

    @admin.display(description='Ячейка')
    def cell_params_display(self, obj):
        """
        Return a string of the lattice parameters for a probe.

        Args:
            obj (Probe): The probe instance being displayed.

        Returns:
            str: Lattice parameter string or '-' if any value is missing.
        """
        if obj.a and obj.b and obj.c:
            return f"a={obj.a}, b={obj.b}, c={obj.c}"
        return "-"

    # Обновляем список полей для отображения
    fields = (
        'number',
        'sizes_display',
        'color1',
        'cell_params_display',
        'dmin',
        'proc_status'
    )
    readonly_fields = ('number', 'sizes_display', 'cell_params_display')


class ChoiceOrCharWidget(forms.MultiWidget):
    """
    Custom form widget that combines a drop‑down selection with an optional
    text input for specifying arbitrary values.

    The first sub‑widget is a ``Select`` field populated from the supplied
    *choices*.  The second is a hidden ``TextInput`` that becomes visible
    only when the user selects the special ``'other'`` choice.  The widget
    automatically decompresses and recombines values for form processing.
    """

    def __init__(self, choices, attrs=None):
        """
        Initialize the composite widget.

        Args:
            choices (list of tuple): List of two‑item tuples used to populate
                the selection field.
            attrs (dict, optional): Additional HTML attributes passed to both
                sub‑widgets.
        """
        widgets = [
            forms.Select(choices=choices, attrs={'class': 'choice-select'}),
            forms.TextInput(attrs={'class': 'custom-input', 'style': 'display: none;'})
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        Split a stored value into the two component parts of the widget.

        If *value* is one of the predefined choices, return that choice and
        an empty string.  Otherwise return ``'other'`` for the selector
        and the original value for the text input.

        Args:
            value (str): The persisted field value from the database.

        Returns:
            list[str]: Two elements – selector value and optional custom text.
        """
        if value:
            choices = [choice[0] for choice in self.widgets[0].choices]
            if value in choices:
                return [value, '']
            else:
                return ['other', value]
        return [None, '']

    def value_from_datadict(self, data, files, name):
        """
        Reconstruct the final value from submitted form data.

        The method checks whether the user selected ``'other'`` and
        chooses the appropriate text input accordingly.

        Args:
            data (QueryDict): POST or GET data.
            files (MultiValueDict): Uploaded file information (unused).
            name (str): Base name of the widget field.

        Returns:
            str: The final value to be stored in the model field.
        """
        selected = data.get(f'{name}_0')
        custom = data.get(f'{name}_1')
        return custom if selected == 'other' else selected


class ApplicationForm(forms.ModelForm):
    """
    Model form for creating and editing ``Application`` instances.

    The form dynamically attaches a custom widget to several fields
    (e.g. ``tare``, ``mother_solution``) based on the configuration
    dictionary defined in :data:`FIELD_CONFIG`.  Each configured field
    is rendered as either a standard dropdown or an “other” text entry.
    """

    FIELD_CONFIG = {
        'tare': {
            'choices': [
                ('бюкс с крышкой', 'бюкс с крышкой'),
                ('виалка с пластиковой крышкой', 'виалка с пластиковой крышкой'),
                ('пенициллинка с резиновой пробкой', 'пенициллинка с резиновой пробкой'),
                ('пробирка Эппендорфа', 'пробирка Эппендорфа'),
                ('запаянная ампула', 'запаянная ампула'),
                ('U-образная трубка', 'U-образная трубка'),
                ('чашка Петри', 'чашка Петри'),
                ('стакан или выпаривательная чашка, закрытая парафилмом',
                 'стакан или выпаривательная чашка, закрытая парафилмом'),
                ('предметное стекло', 'предметное стекло'),
                ('колба <100 мл', 'колба <100 мл'),
                ('контейнер с Ar', 'контейнер с Ar'),
                ('полиэтиленовый пакет', 'полиэтиленовый пакет')
            ],
            'label': 'Тара'
        },
        'mother_solution': {
            'choices': [
                ('ацетонитрил (MeCN)', 'ацетонитрил (MeCN)'),
                ('диметилформамид (DMF)', 'диметилформамид (DMF)'),
                ('хлороформ (CHCl3)', 'хлороформ (CHCl3)'),
                ('хлористый метилен (CH2Cl2)', 'хлористый метилен (CH2Cl2)'),
                ('диэтиловый эфир (Et2O)', 'диэтиловый эфир (Et2O)'),
                ('метиловый спирт (MeOH)', 'метиловый спирт (MeOH)'),
                ('этиловый спирт (EtOH)', 'этиловый спирт (EtOH)'),
                ('изопропиловый спирт (iPrOH)', 'изопропиловый спирт (iPrOH)'),
                ('ацетон (MeAc)', 'ацетон (MeAc)'),
                ('тетрагидрофуран (THF)', 'тетрагидрофуран (THF)'),
                ('бензол/толуол (PhR, R=H, Me)', 'бензол/толуол (PhR, R=H, Me)'),
                ('гексан/гептан (CnH2n+2, n=6-7)', 'гексан/гептан (CnH2n+2, n=6-7)'),
                ('диметилсульфоксид (DMSO)', 'диметилсульфоксид (DMSO)'),
                ('нейтральный водный раствор, pH~7', 'нейтральный водный раствор, pH~7'),
                ('кислый водный раствор, pH<5', 'кислый водный раствор, pH<5'),
                ('сильнокислый водный раствор, pH<2', 'сильнокислый водный раствор, pH<2'),
                ('щелочной водный раствор, pH>9', 'щелочной водный раствор, pH>9'),
                ('сильнощелочной водный раствор, pH>12', 'сильнощелочной водный раствор, pH>12')
            ],
            'label': 'Маточный раствор'
        },
        'sample_appearance': {
            'choices': [
                ('кристаллический, без маточного раствора (сухой)',
                 'кристаллический, без маточного раствора (сухой)'),
                ('порошок, без маточного раствора (сухой)', 'порошок, без маточного раствора (сухой)'),
                ('кристаллический, со следами маточного раствора/масла (влажный)',
                 'кристаллический, со следами маточного раствора/масла (влажный)'),
                ('порошок, со следами маточного раствора/масла (влажный)',
                 'порошок, со следами маточного раствора/масла (влажный)'),
                (
                    'кристаллический, под маточным раствором/маслом', 'кристаллический, под маточным раствором/маслом'),
                ('порошок, под маточным раствором/маслом', 'порошок, под маточным раствором/маслом'),
                ('готовые образцы на вкладышах ГГ', 'готовые образцы на вкладышах ГГ'),
                ('other', 'Другое...'),
            ],
            'label': 'Внешний вид образца'
        },
        'sample_storage': {
            'choices': [
                ('шкаф, лаб.301, ЛВЖ', 'шкаф, лаб.301, ЛВЖ'),
                ('шкаф, лаб.308, ЛВЖ', 'шкаф, лаб.308, ЛВЖ'),
                ('шкаф, лаб.311, ЛВЖ', 'шкаф, лаб.311, ЛВЖ'),
                ('шкаф, лаб.312, ЛВЖ', 'шкаф, лаб.312, ЛВЖ'),
                ('шкаф, лаб.338, ЛВЖ', 'шкаф, лаб.338, ЛВЖ'),
                ('шкаф, лаб.339, ЛВЖ', 'шкаф, лаб.339, ЛВЖ'),
                ('шкаф, общий, ЛВЖ', 'шкаф, общий, ЛВЖ'),
                ('шкаф, сухие образцы и запаянные ампулы', 'шкаф, сухие образцы и запаянные ампулы'),
                ('шкаф, кислоты и окислители', 'шкаф, кислоты и окислители'),
                ('шкаф, водн. р-ры и негигроскопичные нелетучие образцы',
                 'шкаф, водн. р-ры и негигроскопичные нелетучие образцы'),
                ('шкаф, U-трубки', 'шкаф, U-трубки'),
                ('мор. камера, лаб.312, ЛВЖ', 'мор. камера, лаб.312, ЛВЖ'),
                ('мор. камера, общий, ЛВЖ', 'мор. камера, общий, ЛВЖ'),
                ('будет предоставлено перед экспериментом', 'будет предоставлено перед экспериментом'),
                ('передано ответственному оператору', 'передано ответственному оператору'),
                ('other', 'Другое...'),
            ],
            'label': 'Место хранения образца'
        },
        'sample_storage_conditions': {
            'choices': [
                ('особых условий не требуется', 'особых условий не требуется'),
                ('морозильная камера', 'морозильная камера'),
                ('эксикатор с силикагелем', 'эксикатор с силикагелем'),
                ('в темноте', 'в темноте'),
                ('-', '-'),
                ('other', 'Другое...'),
            ],
            'label': 'Условия хранения образца'
        }
    }

    class Meta:
        model = Application
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """
        Attach the custom widget to all configured fields.

        For each field defined in :data:`FIELD_CONFIG`, the method ensures
        that a form field exists and applies ``ChoiceOrCharWidget`` with
        the appropriate choices.  The human‑readable label from the config
        is also assigned.
        """
        super().__init__(*args, **kwargs)

        # Применяем кастомные виджеты к полям
        for field_name, config in self.FIELD_CONFIG.items():
            # Создаем поле, если оно еще не создано
            if field_name not in self.fields:
                self.fields[field_name] = forms.CharField(
                    required=False,
                    label=config['label'],
                    max_length=255
                )

            self.fields[field_name].widget = ChoiceOrCharWidget(
                choices=config['choices']
            )
            self.fields[field_name].label = config['label']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """
    Admin interface for the ``Application`` model.

    The class customises the form to use :class:`ApplicationForm`,
    includes probe inlines, and defines fieldsets with Russian titles.
    It also provides an action that triggers a Celery task to send
    reminder e‑mails about unreturned samples.
    """

    form = ApplicationForm
    inlines = [ProbeInline]
    fieldsets = (
        (_('Основная информация'), {
            'fields': (
                'application_code',
                # 'name',
                'date',
                'client',
                'project',
                'time_spent',
                'lab',
                'client_home_lab',
                'supervisor',
                'operator',
                'status',
                'data_status',
                'asap_priority',
                'deadline',
                'locked_by'
            )
        }), (_('Контактная информация'), {
        'fields': (
            'inter_telephone',
            'urgt_comm',
            'presence_is_necessary',
        )
    }),
        (_('Предполагаемые исполнители'), {
            'fields': (
                'operator_desired',
                'structurer_desired',
                'crystchemist_desired',
            )
        }),
        (_('Описание образца'), {
            'fields': (
                'sample_code',
                'sample_appearance',  # Оригинальное поле с кастомным виджетом
                'composition',
                'mother_solution',  # Оригинальное поле с кастомным виджетом
                'tare',  # Оригинальное поле с кастомным виджетом
            )
        }),
        (_('Условия хранения'), {
            'fields': (
                'sample_storage',  # Оригинальное поле
                'sample_storage_conditions',  # Оригинальное поле
                'sample_storage_post_exp'
            )
        }),
        (_('Пожелания по анализу'), {
            'fields': (
                'desired_UCP_SG_appearance',
                'undesired_UCP_SG_appearance',
                'experiment_temp',
                'graph_comm',
            )
        }),
        (_('Информация об экспериментах'), {
            'fields': (
                'experiment_start_date',
                'experiment_start',
                'experiment_end',
                'experiment_end_date',
                'diffractometer',
            )
        }),
        (_('Результаты и наблюдения'), {
            'fields': (
                'proc_status_application',
                'smpl_type_application',
                'data_quantity_application',
                'dmin_application',
                'probe_count',
                'reduced_data_dir'
            )
        }),
        (_('Комментарии и отчетность'), {
            'fields': (
                'commentary',
            )
        }),
        (_('Ответственные лица'), {
            'fields': (
                'application_prepared_by',
            )
        }),
    )
    actions = ['send_reminder_emails']

    def send_reminder_emails(self, request, queryset):
        """
        Admin action to dispatch a Celery task that sends reminder e‑mails.

        When executed from the Django admin interface, this method triggers
        :func:`sample_takeaway_reminder_email.delay` and then notifies the user
        with a success message containing the task ID.  The function redirects
        back to the same page so that the list view is refreshed.

        Args:
            request (HttpRequest): Current admin request.
            queryset (QuerySet): Selected ``Application`` objects – not used in
                this action but required by the action signature.

        Returns:
            HttpResponseRedirect: Redirects back to the current admin URL.
        """
        task = sample_takeaway_reminder_email.delay()

        self.message_user(
            request,
            f'Задача отправки напоминаний запущена (ID: {task.id}). Проверьте логи Celery для отслеживания.',
            messages.SUCCESS
        )

        return HttpResponseRedirect(request.get_full_path())

    send_reminder_emails.short_description = "📧 Отправить напоминания о не возвращенных образцах"

    readonly_fields = ('application_code',
                       'smpl_type_application',
                       'data_quantity_application',
                       'dmin_application',
                       'probe_count')

    list_display = ('client', 'lab', 'sample_code', 'date')
    search_fields = ('client', 'lab' 'sample_code', 'application_code')

    class Media:
        css = {'all': ('application/css/choice-widget.css',)}
        js = ('application/js/choice-widget.js',)