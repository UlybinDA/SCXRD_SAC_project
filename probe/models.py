from math import gamma
from unittest import case
import math
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from application.models import Application
from publication.models import Publication
import logging
logger = logging.getLogger(__name__)

class Probe(models.Model):
    """
    Model representing a crystallography probe or sample measurement.

    This model stores detailed information about individual samples or probes
    measured during crystallography experiments. It includes physical characteristics,
    lattice parameters, data quality indicators, and processing status.
    """

    class Color(models.TextChoices):
        """
        Color enumeration for crystal samples.

        Provides standardized color codes and Russian labels for visual
        characterization of probes.
        """
        NULL = '', '------'
        COLORLESS = 'CL', 'БЦ'
        YELLOW = 'YE', 'желтый'
        BLUE = 'BL', 'синий'
        RED = 'RD', 'красный'
        GREEN = 'GR', 'зеленый'
        BLACK = 'BK', 'черный'
        WHITE = 'WH', 'белый'
        PURPLE = 'PL', 'фиолетовый'
        ORANGE = 'OR', 'оранжевый'

    class BravaisLattice(models.TextChoices):
        """
        Bravais lattice type enumeration with parameter display logic.

        Defines all 14 Bravais lattice types and provides method for
        generating display templates for lattice parameters based on type.
        """
        aP = 'aP', 'aP'
        mP = 'mP', 'mP'
        mC = 'mC', 'mC'
        oP = 'oP', 'oP'
        oC = 'oC', 'oC'
        oI = 'oI', 'oI'
        oF = 'oF', 'oF'
        tP = 'tP', 'tP'
        tI = 'tI', 'tI'
        hP = 'hP', 'hP'
        hR = 'hR', 'hR'
        cP = 'cP', 'cP'
        cI = 'cI', 'cI'
        cF = 'cF', 'cF'

        @staticmethod
        def display_parameters_template(lattice_type, a, b, c, al, bt, gm):
            """
            Generate formatted display strings for lattice parameters.

            Creates human-readable representations of lattice parameters
            based on the lattice type's symmetry constraints.

            Args:
                lattice_type (str): Lattice type code from BravaisLattice choices.
                a (float): Lattice parameter a in Angstroms.
                b (float): Lattice parameter b in Angstroms.
                c (float): Lattice parameter c in Angstroms.
                al (float): Angle α in degrees.
                bt (float): Angle β in degrees.
                gm (float): Angle γ in degrees.

            Returns:
                dict: Dictionary with 'linear_prm' and 'angular_prm' display strings.
            """
            match lattice_type[0]:
                case 'a':
                    return {'linear_prm': f'a {a:.2f}, b {b:.2f}, c {c:.2f}',
                            'angular_prm': f'α {al:.1f}, β {bt:.1f}, γ {gm:.1f}'}
                case 'm':
                    return {'linear_prm': f'a {a:.2f}, b {b:.2f}, c {c:.2f}', 'angular_prm': f'β {bt:.1f}'}
                case 'o':
                    return {'linear_prm': f'a {a:.2f}, b {b:.2f}, c {c:.2f}', 'angular_prm': ''}
                case 't':
                    return {'linear_prm': f'a {a:.2f}, c {c:.2f}', 'angular_prm': ''}
                case 'h':
                    return {'linear_prm': f'a {a:.2f}, {c:.2f}', 'angular_prm': ''}
                case 'c':
                    return {'linear_prm': f'a {a:.2f}', 'angular_prm': ''}
                case _:
                    return {'linear_prm': f'a {a:.2f}, b {b:.2f}, c {c:.2f}',
                            'angular_prm': f'α {al:.1f}, β {bt:.1f}, γ {gm:.1f}'}

    class SampleType(models.TextChoices):
        """
        Sample type classification enumeration.

        Categorizes samples based on crystallographic properties and
        diffraction patterns for appropriate data processing workflows.
        """
        NULL = '', _('------')
        UNCLASSIFIED = 'UC', _('не классифицируется')
        POWDER = 'PW', _('порошок (дифракционные кольца)')
        POLYCRYSTAL = 'PC', _('поликристалл (отдельные пики, образующие кольца, >4 доменов)')
        OLIGOCRYSTAL = 'OC', _('олигокристалл (2-4 домена)')
        MODULATED = 'MS', _('модулированная структура (сателлиты у основных пиков)')
        MONOCRYSTAL_DIFFUSE = 'MD', _('монокристалл с сильным диффузным рассеянием')
        DECOMPOSED = 'DC', _('деформированный/разложившийся кристалл или образец с градиентом состава')
        TEXTURED_POWDER = 'TP', _('текстурированный порошок (дифракционные дуги)')
        CONTAMINATED = 'СC', _('грязный кристалл (один основной и несколько примесных доменов)')
        MONOCRYSTAL = 'MC', _('монокристалл')

    class DataQuantity(models.TextChoices):
        """
        Data quantity description enumeration.

        Describes the amount and type of data collected during the experiment.
        """
        NULL = '', _('------')
        F10 = 'F10', _('снято <10 фреймов')
        F100 = 'F100', _('снято <100 фреймов')
        S180 = 'S180', _('снят ~180° скан')
        S360 = 'S360', _('снят ~360° скан')
        MR_CS_PART = 'MR_CS_PART', _('несколько ранов, цс часть сферы (центросимметричная)')
        MR_NCS_PART = 'MR_NCS_PART', _('несколько ранов, нцс часть сферы (нецентросимметричная)')
        MR_CS_HALF = 'MR_CS_HALF', _('несколько ранов, цс половина сферы (центросимметричная)')
        MR_NCS_FULL = 'MR_NCS_FULL', _('несколько ранов, нцс полная сфера (нецентросимметричная)')
        POWDER = 'POWDER', _('порошковый')

    class ProcStatus(models.TextChoices):
        """
        Data processing status enumeration with workflow methods.

        Tracks the state of data processing for each probe and provides
        utility methods for status transitions and workflow management.
        """
        NULL = '', _('------')
        TRASH = 'x', 'пробный эксперимент, не содержит данных, заслуживающих внимания'
        SC_NR = '<', 'монокристальный эксперимент, требующий редукции'
        SC_R = '.', 'редуцированный монокристальный эксперимент, данные не переданы заказчику'
        RE_R = '!', 'требуется нерутинная или повторная редукция'
        FA_R = '@', 'удовлетворительная редукция не проведена, требуется нерутинная обработка'
        SC_RS = '>', 'монокристальный эксперимент, данные переданы заказчику'
        PW_NR = '(', 'порошковый эксперимент, требующий редукции'
        PW_R = ';', 'редуцированный порошковый эксперимент, данные не переданы заказчику'
        PW_RS = ')', 'порошковый эксперимент, данные переданы заказчику'
        EI_C = '+', 'полная съемка не проводилась из-за совпадения ПЭЯ с указанными в заявке в поле "не снимать"'
        EI_O = '#', 'полная съемка не проводилась из-за совпадения ПЭЯ со структурами из CCDC/ICSD (указать в следующей заявке в поле "не снимать"?)'
        C_REJ = '-', 'эксперимент не проводился или отменен заказчиком (детали в комментарии)'
        NC = '~', 'в пробе не обнаружены кристаллы - сделано словесное описание и фотография'
        LP = 'l', 'по просьбе заказчика проведено определение ПЭЯ (значения в бланке заявки)'

        @classmethod
        def processing_options(cls):
            """
            Get subset of statuses available for ApplicationProcessingView.

            Returns:
                list: List of (value, label) tuples for processing statuses.
            """
            selected_members = [
                cls.TRASH, cls.SC_NR, cls.SC_R, cls.RE_R, cls.FA_R, cls.PW_NR,
                cls.PW_R, cls.EI_C, cls.EI_O, cls.C_REJ, cls.NC, cls.LP
            ]
            return [(member.value, member.label) for member in selected_members]

        @classmethod
        def can_be_published(cls):
            """
            Get statuses that indicate data is ready for publication.

            Returns:
                tuple: Status values that allow publication linkage.
            """
            selected_members = [
                cls.SC_RS, cls.PW_RS, cls.LP
            ]
            return (member.value for member in selected_members)

        @classmethod
        def get_reduced_value(cls, status):
            """
            Get the reduced status equivalent for a given raw status.

            Args:
                status (str): Current processing status value.

            Returns:
                str: Corresponding reduced status value.
            """
            match status:
                case cls.SC_NR.value:
                    status = cls.SC_R.value
                case cls.PW_NR.value:
                    status = cls.PW_R.value
                case cls.RE_R.value:
                    status = cls.SC_R.value
                case _:
                    pass
            return status

        @classmethod
        def get_posted_value(cls, status):
            """
            Get the posted status equivalent for a given reduced status.

            Args:
                status (str): Current processing status value.

            Returns:
                str: Corresponding posted status value.
            """
            match status:
                case cls.SC_R.value:
                    status = cls.SC_RS.value
                case cls.PW_R.value:
                    status = cls.PW_RS.value
                case _:
                    pass
            return status

        @classmethod
        def need_to_post(cls, status):
            """
            Check if data with given status needs to be posted/sent to client.

            Args:
                status (str): Current processing status value.

            Returns:
                bool: True if data requires posting, False otherwise.
            """
            match status:
                case cls.SC_R.value:
                    return True
                case cls.PW_R.value:
                    return True
                case _:
                    return False


    application = models.ForeignKey(
        Application,
        verbose_name=_('Заявка'),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name='probes'
    )
    habit = models.CharField(_('Габитус'),

                             max_length=50,
                             null=True, blank=True
                             )
    number = models.PositiveIntegerField(_('Номер пробы'), blank=True)
    size_x = models.PositiveIntegerField(_('Размер x'), null=True, blank=True)
    size_y = models.PositiveIntegerField(_('Размер y'), null=True, blank=True)
    size_z = models.PositiveIntegerField(_('Размер z'), null=True, blank=True)
    transparent = models.BooleanField(_('Прозрачный'), default=True, blank=True)
    matte = models.BooleanField(_('Матовый'), default=False, blank=True)
    metallic = models.BooleanField(_('Металлический'), default=False, blank=True)

    color1 = models.CharField(
        max_length=2,
        choices=Color.choices,
        default=Color.COLORLESS,
        blank=True,
        null=True,
    )
    color2 = models.CharField(
        max_length=2,
        choices=Color.choices,
        default=Color.NULL,
        blank=True,
        null=True,
    )


    lattice_type = models.CharField(
        _('Тип решётки Бравэ'),
        max_length=2,
        choices=BravaisLattice.choices,
        default=BravaisLattice.aP,
        null=True,
        blank=True
    )
    a = models.DecimalField(
        _('Параметр a'),
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        help_text=_("Длина в ангстремах (Å)"),
        null=True,
        default=None,
        blank=True,

    )
    b = models.DecimalField(
        _('Параметр b'),
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        help_text=_("Длина в ангстремах (Å)"),
        null=True,
        default=None,
        blank=True,
    )
    c = models.DecimalField(
        _('Параметр c'),
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        help_text=_("Длина в ангстремах (Å)"),
        null=True,
        default=None,
        blank=True,
    )


    al = models.DecimalField(
        _('Угол α'),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(179.99)],
        help_text=_("Угол между b и c (градусы)"),
        null=True,
        default=None,
        blank=True,
    )
    bt = models.DecimalField(
        _('Угол β'),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(179.99)],
        help_text=_("Угол между a и c (градусы)"),
        null=True,
        default=None,
        blank=True,
    )
    gm = models.DecimalField(
        _('Угол γ'),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(179.99)],
        help_text=_("Угол между a и b (градусы)"),
        null=True,
        default=None,
        blank=True,
    )
    volume = models.DecimalField(
        _('Объем ячейки'),
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(0.01), MaxValueValidator(1000000.)],
        help_text=_("Объем (Å^3)"),
        null=True,
        default=None,
        blank=True,
    )
    photo_rotation = models.BooleanField(blank=True, default=False)


    dmin = models.DecimalField(
        _('Предельное разрешение Å'),
        max_digits=7,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
        help_text=_("Длина в ангстремах (Å)"),
        blank=True,
        null=True,
        default=None
    )


    smpl_type = models.CharField(
        _('Тип пробы'),
        max_length=2,
        choices=SampleType.choices,
        default=SampleType.NULL,
        blank=True,
        null=True,
    )

    data_quantity = models.CharField(
        _('Количественное описание данных'),
        max_length=15,
        choices=DataQuantity.choices,
        default=DataQuantity.NULL,
        blank=True,
        null=True,
    )


    scans_desc = models.CharField(_('основные сканирования'), max_length=100, default="", blank=True, null=True, )
    db_code_found = models.CharField(max_length=100, blank=True, null=True, default='')
    commentary = models.TextField(_('Комментарий'), blank=True, null=True)


    proc_status = models.CharField(
        max_length=1,
        choices=ProcStatus.choices,
        default=ProcStatus.NULL,
        verbose_name='Статус обработки',
        blank=True,
        null=True,
    )

    # Confirmation and temperature fields
    confirmed = models.BooleanField(_('Заполнено'), default=False, blank=True, null=True)
    temperature = models.DecimalField(_('Температура съемки, К'), decimal_places=2, max_digits=5, default=220.0,
                                      null=True, blank=True)

    # Publication relationship
    publications = models.ManyToManyField(Publication, blank=True, related_name='probe')

    # Required field lists for validation
    required_on_complete = [
        'size_x',
        'size_y',
        'size_z',
        'habit',
        'color1',
        'smpl_type',
        'data_quantity',
        'scans_desc',
        'proc_status',
        'temperature'
    ]
    required_on_reject = [
    ]

    class Meta:
        """
        Metadata class for Probe model.

        Defines verbose names for admin interface in Russian.
        """
        verbose_name = "Проба"
        verbose_name_plural = "Пробы"

    def save(self, *args, **kwargs):
        """
        Custom save method with automatic volume calculation.

        Calculates and updates cell volume if all lattice parameters are present
        before saving the instance.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        if self.has_parameters:
            self.volume = self.get_volume
        super().save(*args, **kwargs)

    @classmethod
    def get_need_reduction_statuses(cls):
        """
        Get status values indicating data needs reduction.

        Returns:
            tuple: Status values requiring data reduction.
        """
        return cls.ProcStatus.SC_NR.value, cls.ProcStatus.PW_NR.value, cls.ProcStatus.RE_R.value

    @classmethod
    def get_need_send_statuses(cls):
        """
        Get status values indicating data needs to be sent to client.

        Returns:
            tuple: Status values requiring data transmission.
        """
        return cls.ProcStatus.SC_R.value, cls.ProcStatus.PW_R.value

    @classmethod
    def get_sent_statuses(cls):
        """
        Get status values indicating data has been sent to client.

        Returns:
            tuple: Status values indicating data transmission completed.
        """
        return cls.ProcStatus.SC_RS.value, cls.ProcStatus.PW_RS.value

    def mark_reduced(self):
        """
        Mark this probe's data as reduced in processing workflow.

        Updates proc_status to the reduced equivalent if applicable.
        """
        current_status = self.proc_status
        new_status = self.ProcStatus.get_reduced_value(current_status)
        if new_status != current_status:
            self.proc_status = new_status
            self.save(update_fields=['proc_status'])

    def mark_posted(self):
        """
        Mark this probe's data as posted/sent to client.

        Updates proc_status to the posted equivalent if applicable.
        """
        current_status = self.proc_status
        new_status = self.ProcStatus.get_posted_value(current_status)
        if new_status != current_status:
            self.proc_status = new_status
            self.save(update_fields=['proc_status'])

    @property
    def get_volume(self):
        """
        Calculate unit cell volume from lattice parameters.

        Returns:
            float: Calculated cell volume in Å³, or None if parameters missing.
        """
        try:
            alpha = float(self.al)
            beta = float(self.bt)
            gamma = float(self.gm)
            a = float(self.a)
            b = float(self.b)
            c = float(self.c)

            alpha_rad = math.radians(alpha)
            beta_rad = math.radians(beta)
            gamma_rad = math.radians(gamma)

            cos_alpha = math.cos(alpha_rad)
            cos_beta = math.cos(beta_rad)
            cos_gamma = math.cos(gamma_rad)

            volume = a * b * c * math.sqrt(
                1 - cos_alpha ** 2 - cos_beta ** 2 - cos_gamma ** 2 +
                2 * cos_alpha * cos_beta * cos_gamma
            )
            return volume

        except (TypeError, ValueError, AttributeError) as e:
            logger.error(f'Error calculating volume for probe {self.id}: {e}')
            return None

    @property
    def parameter_str(self):
        """
        Generate formatted string representation of lattice parameters.

        Creates a human-readable string with appropriate parameters based on
        lattice symmetry, including calculated volume.

        Returns:
            str: Formatted parameter string with units.
        """
        parameters = self.BravaisLattice.display_parameters_template(self.lattice_type, self.a, self.b, self.c, self.al,
                                                                     self.bt, self.gm)
        volume = self.volume
        if not volume:
            volume = self.get_volume
            if volume: volume = f"{round(volume)}"

        return f"{parameters['linear_prm']}, Å,{parameters['angular_prm']}, °, V {volume}Å^3"

    @property
    def has_parameters(self):
        """
        Check if all required lattice parameters are present.

        Returns:
            bool: True if a, b, c, α, β, γ are all set, False otherwise.
        """
        return all((self.a, self.b, self.c, self.al, self.bt, self.gm))

    @property
    def publication_attachable(self):
        """
        Check if this probe can be linked to publications.

        Returns:
            bool: True if processing status allows publication linkage.
        """
        return self.proc_status in self.ProcStatus.can_be_published()