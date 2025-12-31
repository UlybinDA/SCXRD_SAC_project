from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import render
from services.mixins import ChiefUnderchiefRequiredMixin
from application.models import Application
from django.views.generic import View, TemplateView, CreateView, ListView
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.utils import timezone
from .models import QuotaGroup, QuotaTimeTransaction
import json
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from services.mixins import OperatorRequiredMixin
from labs.models import Laboratory
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Q
from decimal import Decimal
from django.core.cache import cache
import plotly.graph_objects as go
from celery import shared_task
import plotly.io as pio
from ccu_project.constants import QT_ST_CM_C, QT_ST_RJ_C, QT_ST_RJ_T, QT_ST_CM_T, QT_ST_GRPH
import logging
from django.utils.timezone import now
from .forms import QuotaTimeTransactionForm
from itertools import cycle
from services.service_functions import hours_to_str_time
from datetime import datetime

logger = logging.getLogger(__name__)


class ResetQuotaView(PermissionRequiredMixin, View):
    """
    Admin view to manually reset a quota group's time allocation.

    This view allows administrators with appropriate permissions to trigger
    a manual reset of a specific quota group, replenishing its time according
    to its period_time setting.
    """

    permission_required = 'quotas.change_quotagroup'

    def post(self, request, group_id):
        """
        Handle POST request to reset a specific quota group.

        Args:
            request (HttpRequest): The current request object.
            group_id (int): Primary key of the QuotaGroup to reset.

        Returns:
            HttpResponseRedirect: Redirect to admin quota group changelist.
        """
        group = get_object_or_404(QuotaGroup, id=group_id)
        group.reset_quota()
        return redirect('admin:quotas_quotagroup_changelist')


class QuotaApplicationsView(OperatorRequiredMixin, TemplateView):
    """
    View displaying applications organized by quota groups for operator workflow.

    This view provides operators with a comprehensive overview of submitted
    applications grouped by their laboratory's quota group, with prioritization
    based on deadlines, ASAP status, and operator assignments.
    """

    template_name = 'quotaview.html'

    def get_context_data(self, **kwargs):
        """
        Prepare context data with applications organized by quota groups.

        Builds a hierarchical data structure grouping applications by their
        quota groups, calculating priority metrics, and organizing for display.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Context dictionary with quota_data_json for JavaScript rendering.
        """
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        quota_data = {}
        user = self.request.user
        try:
            user_operator_profile = user.operator_profile
        except AttributeError:
            user_operator_profile = None
        applications = Application.objects.select_related(
            'lab', 'lab__quota_group'
        ).filter(
            status__in=['submitted']
        ).order_by('-date')[:500]
        for app in applications:
            quota_name = app.lab.quota_group.name if app.lab.quota_group else "Без группы"

            days_left = None
            if app.deadline:
                delta = app.deadline.date() - today
                days_left = delta.days + 1 if delta.days >= 0 else -1
            if app.operator_desired:
                if app.operator_desired == user_operator_profile:
                    app_affiliation = 'my_app'
                else:
                    app_affiliation = 'not_my_app'
            else:
                app_affiliation = 'shared_app'
            app_data = {
                'id': app.id,
                'code': app.application_code,
                'lab': app.lab.short_name,
                'sample_code': app.sample_code,
                'status_code': app.status,
                'client': app.client.get_short_name(),
                'date': app.date.strftime('%Y.%m.%d'),
                'datet': app.date,
                'deadline': app.deadline.strftime('%Y.%m.%d') if app.deadline else None,
                'priority': app.priority,
                'asap': app.asap_priority,
                'days_left': days_left,
                'process_url': reverse('application_process', args=[app.application_code]),
                'app_affiliation': app_affiliation,
            }

            if quota_name not in quota_data:
                quota_data[quota_name] = {}
                quota_data[quota_name]['apps'] = []

                quota_data[quota_name]['time_left'] = app.lab.quota_group.current_time
                quota_data[quota_name]['time_period'] = app.lab.quota_group.period_time

            quota_data[quota_name]['apps'].append(app_data)

        for quota_name, quota_data_ in quota_data.items():
            quota_data_['apps'].sort(key=lambda x: (-x['priority'], x['datet']))

        context['quota_data_json'] = json.dumps(quota_data, default=str)
        return context


def check_if_period_needs_refresh():
    """
    Determine if quota periods need refreshing based on system state.

    Checks if active quota groups have sufficient time or if there are no
    pending applications, indicating that quota periods should be refreshed.

    Returns:
        bool: True if quota periods need refreshing, False otherwise.
    """
    groups_not_needing_refresh = QuotaGroup.objects.filter(
        main=True
    ).filter(
        Q(current_time__gte=0) | Q(period_time=Decimal('-1')) | Q(is_active=True)
    )
    if not groups_not_needing_refresh.exists():
        return True
    labs = Laboratory.objects.filter(quota_group__in=groups_not_needing_refresh)
    applications = Application.objects.filter(lab__in=labs, status='submitted').count()
    return applications == 0


def refresh_period_time():
    """
    Refresh time for all quota groups configured for periodic updates.

    Iterates through all quota groups with update_time_on_period enabled
    and calls their reset_quota() method to replenish time allocations.
    """
    qgs = QuotaGroup.objects.filter(update_time_on_period=True)
    for qg in qgs:
        qg.reset_quota()


@user_passes_test(lambda user: user.is_authenticated and (user.is_superuser or user.is_active_operator))
def refresh_quotas_manually(request):
    """
    Manual endpoint to trigger quota period refresh.

    Provides a way for superusers and active operators to manually refresh
    all quota periods, bypassing automatic refresh conditions.

    Args:
        request (HttpRequest): The current request object.

    Returns:
        HttpResponseRedirect: Redirect to quota applications list.

    Note:
        Decorated to allow access only to superusers and active operators.
    """
    refresh_period_time()
    return redirect('quota_list')


class QuotaTimeTransferCreateView(ChiefUnderchiefRequiredMixin, CreateView):
    """
    View for creating time transfers between quota groups.

    Allows chiefs and underchiefs to transfer time from their laboratory's
    quota group to other active quota groups in the system.
    """

    template_name = 'quotatransfer.html'
    model = QuotaTimeTransaction
    form_class = QuotaTimeTransactionForm
    success_url = reverse_lazy('quota_transfer')

    def get_form_kwargs(self):
        """
        Prepare keyword arguments for form instantiation with user context.

        Returns:
            dict: Keyword arguments including current user for form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Prepare context data with current laboratory time information.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Context dictionary with laboratory name and time breakdown.
        """
        user = self.request.user
        laboratory = user.laboratory
        time_left = laboratory.quota_group.current_time
        hours_left, minutes_left = hours_to_str_time(time_left, val_only=True)
        context = super().get_context_data(**kwargs)
        context.update({'laboratory': laboratory.name, 'hours_left': hours_left, 'minutes_left': minutes_left})
        return context

    def form_valid(self, form):
        """
        Handle valid form submission to execute time transfer.

        Updates both donor and acceptor quota groups' time allocations
        and displays a success message with transfer details.

        Args:
            form (QuotaTimeTransactionForm): Validated form instance.

        Returns:
            HttpResponseRedirect: Redirect to success URL.
        """
        self.object = form.save(commit=False)
        time = self.object.time_transfer
        self.object.quota_group_donor.subtract_time(time)
        self.object.quota_group_acceptor.add_time(time)  # исправлена опечатка
        hours, minutes = hours_to_str_time(time, val_only=True)
        messages.success(self.request,
                         f"Успешно переведено {hours} ч. {minutes} мин. группе {self.object.quota_group_acceptor.name}")
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Handle invalid form submission with error message display.

        Args:
            form (QuotaTimeTransactionForm): Invalid form instance.

        Returns:
            HttpResponse: Form re-render with error messages.
        """
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    field_label = form.fields[field].label or field
                    messages.error(self.request, f"{field_label}: {error}")
        return super().form_invalid(form)


class QuotaTimeTransferListView(ChiefUnderchiefRequiredMixin, ListView):
    """
    View listing time transfer transactions for the current user's quota group.

    Displays both incoming and outgoing time transfers for the laboratory's
    quota group.
    """

    model = QuotaTimeTransaction
    template_name = 'quota_transfer_list.html'
    context_object_name = 'transactions'
    paginate_by = 20
    ordering = ['-datetime_stamp']  # Сначала новые транзакции

    def get_queryset(self):
        """
        Build queryset of transactions involving the user's quota group.

        Filters transactions where the user's quota group is either donor
        or acceptor, optimizing with select_related for related models.

        Returns:
            QuerySet: Filtered and optimized QuotaTimeTransaction queryset.
        """
        queryset = super().get_queryset().select_related(
            'user',
            'quota_group_donor',
            'quota_group_acceptor'
        )
        user_quota_group = self.request.user.laboratory.quota_group
        q_acceptor = queryset.filter(quota_group_acceptor=user_quota_group)
        q_donor = queryset.filter(quota_group_donor=user_quota_group)
        queryset = q_acceptor.union(q_donor)

        return queryset

    def get_context_data(self, **kwargs):
        """
        Prepare context data for template rendering.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Context dictionary for template.
        """
        context = super().get_context_data(**kwargs)
        return context



def plot_quota_time_new():
    """
    Generate enhanced Plotly visualization of quota usage statistics.

    Creates a stacked bar chart showing detailed breakdown of time usage:
    - Remaining time
    - Time spent on rejected applications (with individual application breakdown)
    - Time spent on completed applications (with individual application breakdown)
    - Time transfer transactions (donor and acceptor)

    Each application and transaction is displayed as a separate stacked segment
    with hover details. Uses color cycling for visual distinction.

    Stores the resulting Plotly figure JSON in cache for 60 days.
    """
    quotas = QuotaGroup.objects.filter(is_active=True)
    fig = go.Figure()

    # === Цвета и подписи ===
    color_time_left = 'rgba(65, 105, 225, 0.7)'
    reject_colors = cycle(["#d62728", "#ff9999"])
    completed_colors = cycle(["#d2b48c", "#c2a272"])
    donor_colors = cycle(["#4e79a7", "#8ab6d6"])
    acceptor_colors = cycle(["#9467bd", "#c5a3e0"])

    label_time_left = "Осталось времени"
    label_rejected = "Отклонённые заявки"
    label_completed = "Выполненные заявки"
    label_donor = "Транзакции донор"
    label_acceptor = "Транзакции акцептор"

    # === Параметры отрисовки ===
    width_main = 0.4
    width_tx = 0.4
    refresh_time = datetime.now().strftime("%H:%M:%S")
    for quota in quotas:
        qname = quota.name

        completed_qs = quota.applications_completed_this_period
        rejected_qs = quota.applications_rejected_this_period
        donor_qs = quota.donor_transfers_this_period
        acceptor_qs = quota.acceptor_transfers_this_period

        # --- MAIN GROUP (Осталось, отклонено, выполнено) ---
        offset_main = f"{qname}_main"
        current_base = 0

        # Осталось времени (если меньше 0, ставим 0)
        remaining_time = max(0, quota.current_time)
        fig.add_trace(go.Bar(
            x=[qname],
            y=[remaining_time],
            name=label_time_left,
            marker_color=color_time_left,
            offsetgroup=offset_main,
            width=width_main,
            hovertemplate=(
                f"<b>{label_time_left}</b><br>"
                f"Остаток: {hours_to_str_time(quota.current_time)} ч<extra></extra>"
            )
        ))
        current_base += remaining_time

        # Отклонённые заявки
        total_rejected = rejected_qs.count()
        total_rej_time = sum(app.time_spent for app in rejected_qs)
        for app in rejected_qs.all():
            color = next(reject_colors)
            fig.add_trace(go.Bar(
                x=[qname],
                y=[app.time_spent],
                name=label_rejected,
                marker_color=color,
                offsetgroup=offset_main,
                base=current_base,
                width=width_main,
                hovertemplate=(
                    f"<b>{label_rejected}</b><br>"
                    f"Клиент: {app.client}<br>"
                    f"Образец: {app.sample_code}<br>"
                    f"Время заявки: {hours_to_str_time(app.time_spent)}<br>"
                    f"Всего отклонённых: {total_rejected}<br>"
                    f"Суммарное время: {hours_to_str_time(total_rej_time)}<extra></extra>"
                ),
                showlegend=False
            ))
            current_base += app.time_spent

        # Выполненные заявки
        total_completed = completed_qs.count()
        total_comp_time = sum(app.time_spent for app in completed_qs)
        for app in completed_qs.all():
            color = next(completed_colors)
            fig.add_trace(go.Bar(
                x=[qname],
                y=[app.time_spent],
                name=label_completed,
                marker_color=color,
                offsetgroup=offset_main,
                base=current_base,
                width=width_main,
                hovertemplate=(
                    f"<b>{label_completed}</b><br>"
                    f"Клиент: {app.client}<br>"
                    f"Образец: {app.sample_code}<br>"
                    f"Время заявки: {hours_to_str_time(app.time_spent)}<br>"
                    f"Всего выполнено: {total_completed}<br>"
                    f"Суммарное время: {hours_to_str_time(total_comp_time)}<extra></extra>"
                ),
                showlegend=False
            ))
            current_base += app.time_spent

        # --- TX GROUP (Донор / Акцептор) ---
        offset_tx = f"{qname}_tx"
        current_base = 0

        total_donor = donor_qs.count()
        total_acceptor = acceptor_qs.count()

        for tx in donor_qs.all():
            color = next(donor_colors)
            fig.add_trace(go.Bar(
                x=[qname],
                y=[tx.time_transfer],
                name=label_donor,
                marker_color=color,
                offsetgroup=offset_tx,
                base=current_base,
                width=width_tx,
                hovertemplate=(
                    f"<b>{label_donor}</b><br>"
                    f"Донор: {tx.quota_group_donor}<br>"
                    f"Акцептор: {tx.quota_group_acceptor}<br>"
                    f"Время: {hours_to_str_time(tx.time_transfer)}<br>"
                    f"Всего донор-транзакций: {total_donor}<extra></extra>"
                ),
                showlegend=False
            ))
            current_base += tx.time_transfer

        for tx in acceptor_qs.all():
            color = next(acceptor_colors)
            fig.add_trace(go.Bar(
                x=[qname],
                y=[tx.time_transfer],
                name=label_acceptor,
                marker_color=color,
                offsetgroup=offset_tx,
                base=current_base,
                width=width_tx,
                hovertemplate=(
                    f"<b>{label_acceptor}</b><br>"
                    f"Донор: {tx.quota_group_donor}<br>"
                    f"Акцептор: {tx.quota_group_acceptor}<br>"
                    f"Время: {hours_to_str_time(tx.time_transfer)}<br>"
                    f"Всего акцептор-транзакций: {total_acceptor}<extra></extra>"
                ),
                showlegend=False
            ))
            current_base += tx.time_transfer

    # === Настройка макета ===
    fig.update_layout(
        barmode='stack',  # stacked внутри offsetgroup, группировка по квоте
        title=f"Статистика использования квот, обновлено {refresh_time}",
        xaxis_title="Группы квот",
        yaxis_title="Время, ч",
        template="plotly_white",
        height=700,
        bargap=0.2,
        showlegend=False
    )

    fig_json = pio.to_json(fig)
    cache.set(QT_ST_GRPH, fig_json, timeout=3600 * 24 * 60)


@shared_task
def task_quota_graph():
    """
    Celery task to generate and cache the enhanced quota usage visualization.

    Task calls plot_quota_time_new() to create the updated
    quota statistics graph and store it in cache for frontend display.
    """
    plot_quota_time_new()