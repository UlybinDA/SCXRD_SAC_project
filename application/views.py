# views.py
import datetime
import os
import urllib.parse
from django.views.generic import CreateView, UpdateView, DeleteView, ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from .models import Application, ApplicationDraft
from .forms import ApplicationCreateForm, ApplicationProcessForm
from django.utils import timezone
from django.urls import reverse_lazy
import logging
from .models import CustomUser
from django.contrib import messages
from django import forms
from django.db.models import Q, Case, When, Value, BooleanField
from django.shortcuts import get_object_or_404
from probe.forms import ProbeFormSet
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from services.mixins import OperatorRequiredMixin
from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.views.generic import View
import csv
from operators.models import Operator
from labs.models import Laboratory
from probe.models import Probe
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import JsonUploadForm
import json
import pathlib
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class ApplicationBaseView:
    """
    Base view class providing common functionality for Application-related views.

    This abstract class defines the common method for retrieving Application
    objects by their unique application_code, which is used as a
    slug across multiple views.
    """

    def get_object(self, queryset=None):
        """
        Retrieve Application instance by application_code from URL parameters.

        Args:
            queryset (QuerySet, optional): Custom queryset to use. Defaults to None.

        Returns:
            Application: The Application object with the given application_code.

        Raises:
            Http404: If no Application with the given application_code exists.
        """
        application_code = self.kwargs.get('application_code')
        return get_object_or_404(Application, application_code=application_code)


class ApplicationCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating new crystallography research applications.

    This view handles the creation of new application forms with support for
    draft loading, user-specific field configuration, and proper permission
    validation. It integrates with ApplicationDraft model for template functionality.
    """

    model = Application
    form_class = ApplicationCreateForm
    template_name = 'application_form.html'
    success_url = reverse_lazy('home')

    def get_form_kwargs(self):
        """
        Prepare keyword arguments for form instantiation with user context.

        Adds user information and optionally loads draft data when requested.
        Handles draft-saving mode when 'save_draft' is present in POST data.

        Returns:
            dict: Keyword arguments for form instantiation.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        logger.info(kwargs)
        if 'use_draft' in self.request.GET and self.request.user.has_app_draft:
            _initial = kwargs['initial']
            kwargs['draft_fields'] = [k for k, v in _initial.items() if v not in [None, '', []]]

        if 'save_draft' in self.request.POST:
            kwargs['save_as_draft'] = True

        return kwargs

    def get_initial(self):
        """
        Return initial data for the form with current date and draft data.

        Populates the form with current date and optionally loads data from
        user's draft if 'use_draft' parameter is present in GET request.

        Returns:
            dict: Initial data dictionary for form fields.
        """
        initial = super().get_initial()
        initial['date'] = timezone.now().strftime('%Y-%m-%d')

        if 'use_draft' in self.request.GET:
            if self.request.user.has_app_draft:
                draft = ApplicationDraft.objects.get(user=self.request.user)
                initial.update(self._draft_to_initial(draft))

                messages.info(self.request, "Данные загружены из шаблона")
            else:
                messages.error(self.request, "Шаблон не найден")

        return initial

    def _draft_to_initial(self, draft):
        """
        Convert ApplicationDraft instance data into form initial dictionary.

        Extracts only fields that exist in both the draft model and the form's
        field list, excluding empty/null values.

        Args:
            draft (ApplicationDraft): Draft instance to extract data from.

        Returns:
            dict: Initial data dictionary for form population.
        """
        initial = {}

        # Список полей, разрешённых в форме
        form_fields = getattr(ApplicationCreateForm.Meta, "fields", [])

        # Берём только поля, которые реально есть в ApplicationDraft
        draft_fields = [f.name for f in ApplicationDraft._meta.fields]

        for field in form_fields:
            if field in draft_fields:
                value = getattr(draft, field, None)
                if value not in [None, '', []]:
                    initial[field] = value

        return initial

    def form_valid(self, form):
        """
        Handle valid form submission with draft or application creation logic.

        Routes submission to appropriate handler based on whether the user
        is saving a draft or creating a full application.

        Args:
            form (ApplicationCreateForm): Validated form instance.

        Returns:
            HttpResponse: Redirect response or form re-render.
        """
        # Обработка сохранения шаблона
        if 'save_draft' in self.request.POST:
            return self._save_as_draft(form)

        # Обычное сохранение заявки
        return self._save_as_application(form)

    def _save_as_draft(self, form):
        """
        Save form data as a user draft template.

        Deletes any existing draft for the user and creates a new one with
        current form data. Used for template/save-and-continue functionality.

        Args:
            form (ApplicationCreateForm): Form with cleaned data to save.

        Returns:
            HttpResponseRedirect: Redirect to current page with message.
        """
        try:
            ApplicationDraft.objects.filter(user=self.request.user).delete()

            draft_data = {
                f.name: form.cleaned_data.get(f.name)
                for f in ApplicationDraft._meta.fields
                if f.name in form.cleaned_data
            }

            ApplicationDraft.objects.create(user=self.request.user, **draft_data)
            messages.success(self.request, "Шаблон успешно сохранен")
            return redirect(self.request.path)

        except Exception as e:
            error_msg = f"Ошибка при сохранении шаблона: {str(e)}"
            messages.error(self.request, error_msg)
            logger.exception("Ошибка при сохранении шаблона")
            return self.form_invalid(form)

    def _save_as_application(self, form):
        """
        Save form data as a complete Application instance.

        Sets user-related fields, validates required data, and creates the
        application with appropriate laboratory assignment and priority settings.

        Args:
            form (ApplicationCreateForm): Validated form instance.

        Returns:
            HttpResponse: Redirect to success URL or form re-render on error.
        """
        try:
            form.instance.client = self.request.user
            form.instance.application_prepared_by = self.request.user

            if hasattr(self.request.user, 'supervisor') and self.request.user.supervisor:
                form.instance.supervisor = self.request.user.supervisor

            if hasattr(self.request.user, 'laboratory') and self.request.user.laboratory:
                form.instance.client_home_lab = self.request.user.laboratory
            else:
                error_msg = "У вашего аккаунта не назначена лаборатория"
                messages.error(self.request, error_msg)
                logger.error(f"User {self.request.user} has no lab assigned")
                return self.form_invalid(form)

            if not form.cleaned_data.get('sample_code'):
                error_msg = "Код образца обязателен для заполнения"
                messages.error(self.request, error_msg)
                logger.error(f"Sample code missing for user {self.request.user}")
                return self.form_invalid(form)

            if 'lab' in form.cleaned_data:
                form.instance.lab = form.cleaned_data['lab']
            else:
                form.instance.lab = self.request.user.laboratory

            if 'asap_priority' in form.cleaned_data:
                form.instance.asap_priority = form.cleaned_data['asap_priority']

            response = super().form_valid(form)
            sample_code = form.cleaned_data.get('sample_code')
            messages.success(self.request, f"Заявка {sample_code} успешно создана")
            return response

        except Exception as e:
            error_msg = f"Ошибка при сохранении заявки: {str(e)}"
            messages.error(self.request, error_msg)
            logger.exception("Ошибка при создании заявки")
            return self.form_invalid(form)

    def form_invalid(self, form):
        """
        Handle invalid form submission with logging and user feedback.

        Logs form errors and displays a generic error message to the user
        for form correction.

        Args:
            form (ApplicationCreateForm): Invalid form instance.

        Returns:
            HttpResponse: Form re-render with error messages.
        """
        errors = form.errors.as_json()
        logger.error(f"Невалидная форма: {errors}")
        messages.error(self.request, "Пожалуйста, исправьте ошибки в форме")
        return super().form_invalid(form)


class ApplicationUpdateView(UpdateView):
    """
    View for updating existing Application instances.

    Provides edit functionality for applications with permission validation,
    operator locking mechanisms, and field-specific update logic.
    """

    model = Application
    form_class = ApplicationCreateForm
    template_name = 'application_form.html'
    success_url = reverse_lazy('application_list')
    slug_field = 'application_code'
    slug_url_kwarg = 'application_code'

    def get_form_kwargs(self):
        """
        Prepare keyword arguments for form instantiation with user context.

        Returns:
            dict: Keyword arguments including current user for form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        """
        Pre-dispatch handler for permission checking and operator lock management.

        Validates user permissions, checks for operator locks with cooldown
        periods, and releases expired locks before proceeding with the request.

        Args:
            request (HttpRequest): The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Dispatch result or PermissionDenied exception.

        Raises:
            PermissionDenied: If user lacks edit permissions or lock is active.
        """
        self.object = self.get_object()
        user = self.request.user
        if user.is_active_operator:
            oper_profile = user.operator_profile
        else:
            oper_profile = None
        if not (self.object.locked_by == oper_profile) and self.object.locked_by:
            locked = self.object.locked_at
            now = timezone.now()
            diff = now - locked
            if diff < Application.operator_lock_cooldown:
                raise PermissionDenied(f"Заявка выполняется оператором {self.object.locked_by.get_full_name()}")
            else:
                self.object.locked_by = None
                self.object.locked_at = None
                self.object.save()

        if not self.can_edit():
            raise PermissionDenied("У вас нет прав на редактирование этой заявки")

        return super().dispatch(request, *args, **kwargs)

    def can_edit(self):
        """
        Determine if current user has permission to edit this application.

        Permission logic:
        - Superusers: Always allowed
        - Active operators: Always allowed
        - Application client: Allowed for non-final statuses
        - Lab chiefs/underchiefs: Allowed for applications in their lab (for non-final statuses)
        - Otherwise: Denied

        Returns:
            bool: True if user has edit permission, False otherwise.
        """
        user = self.request.user
        app = self.object

        if user.is_superuser:
            return True

        if user.is_active_operator:  # Используем новое свойство
            return True

        if app.status in ['completed', 'rejected', 'cancelled']:
            return False

        return (app.client == user or ((
                                               user.position == CustomUser.Position.CHIEF or user.position == CustomUser.Position.UNDERCHIEF) and app.lab == user.laboratory))

    def get_context_data(self, **kwargs):
        """
        Add permission context for template rendering.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Context dictionary with 'can_edit' flag.
        """
        context = super().get_context_data(**kwargs)
        context['can_edit'] = self.can_edit()
        return context

    def form_valid(self, form):
        """
        Handle valid form submission with priority and lab field processing.

        Args:
            form (ApplicationCreateForm): Validated form instance.

        Returns:
            HttpResponseRedirect: Redirect to success URL.
        """
        if 'asap_priority' in form.cleaned_data:
            form.instance.asap_priority = form.cleaned_data['asap_priority']
        if 'lab' in form.cleaned_data:
            form.instance.lab = form.cleaned_data['lab']
        response = super().form_valid(form)
        return response


class ApplicationDeleteView(LoginRequiredMixin, ApplicationBaseView, DeleteView):
    """
    View for deleting Application instances with permission validation.

    Provides deletion functionality with comprehensive permission checks
    and status-based restrictions to prevent accidental deletions.

    """

    model = Application
    template_name = 'application_confirm_delete.html'
    success_url = reverse_lazy('application_list')
    slug_field = 'application_code'
    slug_url_kwarg = 'application_code'

    def get_object(self, queryset=None):
        """
        Retrieve and validate Application instance for deletion.

        Overrides base method to add permission validation before returning
        the object for deletion.

        Args:
            queryset (QuerySet, optional): Custom queryset to use. Defaults to None.

        Returns:
            Application: Validated Application object.

        Raises:
            PermissionDenied: If user lacks deletion permissions.
            Http404: If application doesn't exist.
        """
        obj = super().get_object(queryset)
        if not self.can_delete(obj):
            raise PermissionDenied("У вас нет прав на удаление этой заявки")

        return obj

    def can_delete(self, application):
        """
        Determine if current user can delete the specified application.

        Permission logic:
        - Superusers: Always allowed
        - Application client: Allowed for non-final statuses
        - Lab chiefs/underchiefs: Allowed for applications in their lab
        - Completed/rejected applications: Never deletable

        Args:
            application (Application): Application instance to check.

        Returns:
            bool: True if deletion is permitted, False otherwise.
        """
        user = self.request.user

        # Админы могут удалять всегда
        if user.is_superuser:
            return True

        # Запрещаем удаление завершенных или отклоненных заявок
        if application.status in ['completed', 'rejected']:
            return False

        # Разрешаем удаление если:
        # 1. Пользователь - автор заявки
        # 2. Пользователь - CH и заявка из его лаборатории
        return (
                application.client == user or
                ((user.position == CustomUser.Position.CHIEF or user.position == CustomUser.Position.UNDERCHIEF) and
                 application.lab == user.laboratory)
        )

    def get_context_data(self, **kwargs):
        """
        Add permission context for template rendering.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Context dictionary with 'can_delete' flag.
        """
        context = super().get_context_data(**kwargs)
        context['can_delete'] = self.can_delete(self.object)
        return context


class ApplicationDetailView(LoginRequiredMixin, ApplicationBaseView, DetailView):
    """
    View for displaying detailed information about a single Application.

    Provides read-only access to application details with permission validation
    to ensure users can only view applications they're authorized to see.
    """

    model = Application
    template_name = 'application_detail.html'
    context_object_name = 'application'
    slug_field = 'application_code'
    slug_url_kwarg = 'application_code'

    def get_object(self, queryset=None):
        """
        Retrieve and validate Application instance for viewing.

        Overrides base method to add permission validation ensuring users
        can only view their own applications or applications in their lab
        (for chiefs/underchiefs).

        Args:
            queryset (QuerySet, optional): Custom queryset to use. Defaults to None.

        Returns:
            Application: Validated Application object.

        Raises:
            PermissionDenied: If user lacks view permissions.
            Http404: If application doesn't exist.
        """
        obj = super().get_object(queryset)

        if not (
                obj.client == self.request.user or
                ((
                         self.request.user.position == CustomUser.Position.CHIEF or self.request.user.position == CustomUser.Position.UNDERCHIEF) and
                 obj.lab == self.request.user.laboratory) or
                self.request.user.is_superuser
        ):
            raise PermissionDenied("У вас нет прав доступа к этой заявке")

        return obj


class ApplicationListView(LoginRequiredMixin, ListView):
    """
    View for listing Application instances with filtering and pagination.

    Provides a comprehensive list view with multiple filtering options,
    permission-based queryset filtering, and pagination for large datasets.
    """

    model = Application
    template_name = 'list_my_applications.html'
    context_object_name = 'applications'
    paginate_by = 20

    def get_queryset(self):
        """
        Build and filter queryset based on user permissions and request parameters.

        Applies multiple filters from GET parameters, orders results by date,
        and adds permission flags for template rendering.

        Returns:
            QuerySet: Filtered and annotated Application queryset.
        """
        queryset = super().get_queryset().select_related('client', 'lab', 'operator', 'diffractometer')

        # Получаем все параметры фильтрации
        status_filter = self.request.GET.get('status')
        sample_code_filter = self.request.GET.get('sample_code')
        client_filter = self.request.GET.get('client')
        date_from_filter = self.request.GET.get('date_from')
        date_to_filter = self.request.GET.get('date_to')
        lab_filter = self.request.GET.get('lab')
        composition_filter = self.request.GET.get('composition')
        sample_returned_filter = self.request.GET.get('sample_returned')  # Исправлено имя

        # Применяем фильтры
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if sample_code_filter:
            queryset = queryset.filter(sample_code__icontains=sample_code_filter)

        if client_filter:
            queryset = queryset.filter(client__last_name__icontains=client_filter)

        if date_from_filter:
            queryset = queryset.filter(experiment_end_date__gte=date_from_filter)

        if date_to_filter:
            queryset = queryset.filter(experiment_end_date__lte=date_to_filter)

        if lab_filter:
            queryset = queryset.filter(lab_id=lab_filter)

        if composition_filter:
            queryset = queryset.filter(composition__icontains=composition_filter)

        if sample_returned_filter:
            sample_returned_bool = sample_returned_filter.lower() == 'true'
            queryset = queryset.filter(sample_returned=sample_returned_bool)

        user = self.request.user
        if user.is_superuser or user.is_active_operator:
            pass
        elif user.is_chief or user.is_underchief:
            queryset = queryset.filter(
                Q(client=user) | Q(lab=user.laboratory))
        else:
            queryset = queryset.filter(lab=user.laboratory)
            # queryset = queryset.filter(client=user)

        queryset = queryset.order_by('-date')

        for app in queryset:
            app.can_delete = self.can_delete_application(app)
            app.can_edit = self.can_edit_application(app)

        return queryset

    def get_context_data(self, **kwargs):
        """
        Prepare context data for template rendering with filter values and user info.

        Includes current filter values, user role flags, and choice options
        for form controls in the template.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Comprehensive context dictionary for template.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        labs = Laboratory.objects.all()

        current_status = self.request.GET.get('status', '')
        current_sample_code = self.request.GET.get('sample_code', '')
        current_client = self.request.GET.get('client', '')
        current_date_from = self.request.GET.get('date_from', '')
        current_date_to = self.request.GET.get('date_to', '')
        current_lab = self.request.GET.get('lab', '')
        current_composition = self.request.GET.get('composition', '')
        current_sample_returned = self.request.GET.get('sample_returned', '')
        query_filter = self.request.GET.copy()
        query_filter.pop('page', None)

        context.update({
            'is_worker': user.position == CustomUser.Position.WORKER,
            'is_chief': user.position == CustomUser.Position.CHIEF,
            'is_underchief': user.position == CustomUser.Position.UNDERCHIEF,
            'is_admin': user.is_superuser or user.is_staff,
            'status_choices': Application.STATUS_CHOICES,
            'sample_returned_choices': (
                ('false', _('Не возвращен')),
                ('true', _('Возвращен')),
            ),
            'labs': labs,
            'current_status': current_status,
            'current_sample_code': current_sample_code,
            'current_client': current_client,
            'current_date_from': current_date_from,
            'current_date_to': current_date_to,
            'current_lab': current_lab,
            'current_composition': current_composition,
            'current_sample_returned': current_sample_returned,
            'querystring': urlencode(query_filter),

        })
        return context

    def can_edit_application(self, application):
        """
        Determine if current user can edit the specified application.

        Permission logic similar to ApplicationUpdateView but for list context.
        Used to show/hide edit buttons in the list template.

        Args:
            application (Application): Application instance to check.

        Returns:
            bool: True if edit is permitted, False otherwise.
        """
        user = self.request.user

        if application.status in ['completed', 'rejected', 'cancelled']:
            return False

        # Админы могут редактировать всегда
        if user.is_superuser:
            return True

        if hasattr(user, 'operator_profile') and user.operator_profile.is_active:
            return True

        # Для завершенных/отклоненных заявок редактирование запрещено

        # Разрешаем редактирование если:
        # 1. Пользователь - автор заявки
        # 2. Пользователь - CH и заявка из его лаборатории
        return (
                application.client == user or
                ((user.position == CustomUser.Position.CHIEF or user.position == CustomUser.Position.UNDERCHIEF) and
                 application.lab == user.laboratory)
        )

    def can_delete_application(self, application):
        """
        Determine if current user can delete the specified application.

        Permission logic similar to ApplicationDeleteView but for list context.
        Used to show/hide delete buttons in the list template.

        Args:
            application (Application): Application instance to check.

        Returns:
            bool: True if deletion is permitted, False otherwise.
        """
        user = self.request.user

        if application.status in ['completed', 'rejected', 'cancelled']:
            return False

        # Админы могут удалять всегда
        if user.is_superuser:
            return True

        # Запрещаем удаление завершенных или отклоненных заявок

        return (
                application.client == user or
                (user.position == CustomUser.Position.CHIEF and
                 application.lab == user.laboratory)
        )


class ApplicationProcessView(ApplicationBaseView, UpdateView):
    """
    View for processing applications by operators (experiment execution phase).

    This specialized view handles the operator workflow for completing or
    rejecting applications, including probe management, data status updates,
    and operator locking mechanisms.
    """

    model = Application
    form_class = ApplicationProcessForm  # Используем новую форму
    template_name = 'application_process.html'
    success_url = reverse_lazy('application_list')
    slug_field = 'application_code'
    slug_url_kwarg = 'application_code'
    context_object_name = 'application'

    def dispatch(self, request, *args, **kwargs):
        """
        Pre-dispatch handler for operator authentication and lock management.

        Validates operator permissions, manages application locking to prevent
        concurrent processing, and handles lock expiration.

        Args:
            request (HttpRequest): The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Dispatch result or PermissionDenied exception.

        Raises:
            PermissionDenied: If user is not an active operator or lock is active.
        """
        self.object = self.get_object()
        self.user = request.user

        if not self.user.is_authenticated:
            return self.handle_no_permission()

        if not self.user.is_active_operator:
            if self.redirect_authenticated_users:
                return redirect(self.get_redirect_url())
            raise PermissionDenied(self.permission_denied_message)

        if self.object.locked_by and self.object.locked_by != self.user:
            locked = self.object.locked_at
            now = timezone.now()
            diff = now - locked
            if diff < Application.operator_lock_cooldown:
                raise PermissionDenied(f"Заявка выполняется оператором {self.object.locked_by.get_full_name()}")
            else:
                self.object.locked_by = self.user
                self.object.locked_at = timezone.now()
                self.object.save(update_fields=["locked_by", "locked_at"])
                return super().dispatch(request, *args, **kwargs)

        self.object.locked_by = self.user
        self.object.locked_at = timezone.now()
        self.object.save(update_fields=["locked_by", "locked_at"])

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """
        Prepare keyword arguments for form instantiation with operator context.

        Returns:
            dict: Keyword arguments including current user for form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Prepare context data with probe formsets for template rendering.

        Builds ProbeFormSet for managing application probes and organizes
        form data for display in the processing template.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Comprehensive context dictionary with formsets and forms.
        """
        context = super().get_context_data(**kwargs)
        application = self.object

        action = self.request.POST.get('action')  # <-- получаем действие

        if self.request.POST:
            formset = ProbeFormSet(
                self.request.POST,
                self.request.FILES,
                instance=application,
                action=action,  # <-- передаём сюда
            )
            probe_forms = formset.forms
        else:
            formset = ProbeFormSet(instance=application)
            probe_forms = [f for f in formset.forms if getattr(f.instance, 'pk', None)]

        context['formset'] = formset
        context['probe_forms'] = probe_forms
        for form in context['probe_forms']:
            form.grouped_fields = form.get_grouped_fields()

        empty_form = formset.empty_form
        empty_form.grouped_fields = empty_form.get_grouped_fields()
        empty_form.fields['temperature'].initial = application.experiment_temp
        context['empty_form'] = empty_form

        return context

    def get_success_url(self):
        """
        Determine redirect URL after successful processing.

        Returns:
            str: URL to redirect to quota list after processing.
        """
        return reverse_lazy('quota_list')

    def form_invalid(self, form):
        """
        Handle invalid form submission with error logging and user feedback.

        Args:
            form (ApplicationProcessForm): Invalid form instance.

        Returns:
            HttpResponse: Form re-render with error messages.
        """
        errors = form.errors.as_json()
        logger.error(f"Невалидная форма: {errors}")

        # Добавляем общее сообщение об ошибке
        messages.error(
            self.request,
            "Пожалуйста, исправьте ошибки в форме"
        )

        return super().form_invalid(form)

    def form_valid(self, form):
        """
        Handle valid form submission with comprehensive processing logic.

        Manages probe updates, status transitions, data status calculations,
        and application completion/rejection workflows.

        Args:
            form (ApplicationProcessForm): Validated form instance.

        Returns:
            HttpResponseRedirect: Redirect to quota list or form re-render.
        """
        context = self.get_context_data()
        formset = context['formset']

        current_probes = list(self.object.probes.all())
        updated_probe_ids = set()

        if formset.is_valid():
            self.object = form.save(commit=False)
            action = self.request.POST.get('action')

            next_number = 1
            new_probes_statuses = []
            for form_in_formset in formset:
                if form_in_formset.cleaned_data.get('DELETE', False):
                    if form_in_formset.instance.pk:
                        form_in_formset.instance.delete()
                    continue

                # Обновляем номер пробы и сохраняем
                probe = form_in_formset.save(commit=False)
                new_probes_statuses.append(probe.proc_status)
                probe.number = next_number
                probe.save()
                next_number += 1

                if probe.pk:
                    updated_probe_ids.add(probe.pk)

            for probe in current_probes:
                if probe.pk not in updated_probe_ids:
                    probe.delete()
            need_reduction_statuses = Probe.get_need_reduction_statuses()
            need_send_statuses = Probe.get_need_send_statuses()
            sent_statuses = Probe.get_sent_statuses()
            not_no_data_statuses = list(need_reduction_statuses) + list(need_send_statuses) + list(sent_statuses)
            no_data_flag = all([status not in not_no_data_statuses for status in new_probes_statuses])
            need_send_flag = any([status in need_send_statuses for status in new_probes_statuses])
            need_reduction_flag = any([status in need_reduction_statuses for status in new_probes_statuses])
            some_sent_flag = any([status in sent_statuses for status in new_probes_statuses])

            if no_data_flag:
                self.object.data_status = 'NO_DATA'
            elif some_sent_flag and not (need_send_flag or need_reduction_flag):
                self.object.data_status = 'DATA_SENT'
            elif need_reduction_flag:
                self.object.data_status = 'NEED_REDUCTION'
            elif need_send_flag and not need_reduction_flag:
                self.object.data_status = 'DATA_REDUCED'

            if action in ('completed', 'rejected'):
                self.object.operator = self.user.operator_profile
                if action == 'completed':
                    pass
                elif action == 'rejected':
                    self.object.data_status = 'NO_DATA'
                if form.cleaned_data.get('sample_storage_post_exp', False) in Application.POST_EXP_STORAGE_RETURN_CHECK:
                    self.object.sample_returned = True

                self.object.status = action

            # Сохраняем объект и пересчитываем агрегаты
            self.object.save()
            # super(Application, self.object).save()
            self.object.update_aggregated_fields()
            self.release_lock()

            return redirect('quota_list')

        else:
            return self.render_to_response(self.get_context_data(form=form))

    def release_lock(self):
        """
        Release operator lock on the application after processing completion.

        Clears the locked_by and locked_at fields to allow other operators
        to work on the application.
        """
        self.object.locked_by = None
        self.object.locked_at = None
        self.object.save(update_fields=["locked_by", "locked_at"])


class ReductionListView(OperatorRequiredMixin, ListView):
    """
    View for listing applications requiring data reduction work.

    Displays applications with 'completed' status and 'NEED_REDUCTION' data
    status, prioritized by whether the current user is the assigned operator.

    Attributes:
        model (Model): The Application model class.
        template_name (str): Template for reduction list display.
        context_object_name (str): Template variable name for the queryset.
        paginate_by (int): Number of items per page for pagination.
    """

    model = Application
    template_name = 'reduction_list.html'
    context_object_name = 'applications'
    paginate_by = 20

    def get_queryset(self):
        """
        Build queryset for reduction list with operator prioritization.

        Filters for applications needing reduction and annotates with
        whether the current user is the assigned operator for sorting.

        Returns:
            QuerySet: Filtered and annotated Application queryset.
        """
        queryset = super().get_queryset()
        queryset = queryset.filter(status='completed', data_status='NEED_REDUCTION')
        user = self.request.user
        queryset = queryset.annotate(
            is_operator=Case(
                When(operator__user=user, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        )
        queryset = queryset.order_by('-is_operator', 'id')
        return queryset


def mark_probes_reduced(request, application_code):
    """
    View function to mark all probes in an application as reduced.

    Updates probe statuses and application data status when data reduction
    is complete.

    Args:
        request (HttpRequest): The current request object.
        application_code (str): Unique identifier of the application.

    Returns:
        HttpResponseRedirect: Redirect to reductions list or home page.
    """
    app = get_object_or_404(Application, application_code=application_code)
    if request.method == 'POST':
        app.mark_all_probe_statuses_reduced()
        messages.success(request, f'Статусы проб для заявки {app.sample_code} обновлены.')
        return redirect('reductions_list')
    return redirect('home')


def mark_sample_returned(request, application_code):
    """
    View function to mark an application's sample as returned to the client.

    Updates the sample_returned field when physical samples are returned
    after experiment completion.

    Args:
        request (HttpRequest): The current request object.
        application_code (str): Unique identifier of the application.

    Returns:
        HttpResponseRedirect: Redirect to application list or home page.
    """
    app = get_object_or_404(Application, application_code=application_code)
    if request.method == 'POST':
        app.mark_as_returned()
        messages.success(request, f'Образец помечен возвращенным {app.sample_code}.')
        return redirect('application_list')
    return redirect('home')


class StatisticsView(OperatorRequiredMixin, View):
    """
    View for generating statistical reports on application data.

    Provides both form display and CSV generation for operator and user
    statistics over customizable date ranges.
    """

    template_name = 'statistics.html'

    def get(self, request):
        """
        Handle GET requests to display statistics form.

        Args:
            request (HttpRequest): The current request object.

        Returns:
            HttpResponse: Rendered statistics form template.
        """
        context = {
            'page_title': 'Статистика',
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """
        Handle POST requests to generate CSV statistics reports.

        Validates input parameters, processes data, and returns CSV file
        with requested statistics.

        Args:
            request (HttpRequest): The current request object.

        Returns:
            HttpResponse: CSV file download or form re-render with errors.
        """
        context = {
            'page_title': 'Статистика',
        }

        stat_type = request.POST.get('stat_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if not all([stat_type, start_date, end_date]):
            context['error_message'] = 'Все поля обязательны для заполнения'
            return render(request, self.template_name, context)

        try:
            start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.datetime.strptime(end_date, '%Y-%m-%d')

            if start > end:
                context['error_message'] = 'Начальная дата не может быть больше конечной'
                return render(request, self.template_name, context)

        except ValueError:
            context['error_message'] = 'Неверный формат даты'
            return render(request, self.template_name, context)
        period_applications = Application.objects.filter(
            experiment_end_date__gte=start_date,
            experiment_end_date__lte=end_date
        )
        if stat_type == 'operators':
            return self.generate_operators_csv(applications=period_applications)
        elif stat_type == 'users':
            return self.generate_users_csv(applications=period_applications)
        else:
            context['error_message'] = 'Неверный тип статистики'
            return render(request, self.template_name, context)

    def generate_operators_csv(self, applications):
        """
        Generate CSV report of operator statistics.

        Creates a CSV file with columns for operator name, completed/rejected
        application counts, total probe counts, and total time spent.

        Args:
            applications (QuerySet): Filtered applications for the period.

        Returns:
            HttpResponse: CSV file download response.
        """
        response = HttpResponse(content_type='text/csv')
        filename = f"operators_statistics_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            'Оператор',
            'Выполнено заявок',
            'Отклонено заявок',
            'Общее количество проб',
            'Общее затраченное время (ч)'
        ])

        operator_ids = applications.exclude(operator=None).values_list('operator', flat=True).distinct()
        operators = Operator.objects.filter(id__in=operator_ids)

        statistics_dict = {}

        for operator in operators:
            op_apps = applications.filter(operator=operator)

            if op_apps.exists():
                statistics_dict[operator.id] = {
                    'name': operator.name,
                    'completed': 0,
                    'rejected': 0,
                    'probes': 0,
                    'time_spent': 0
                }

                statistics_dict[operator.id]['completed'] = op_apps.filter(status='completed').count()
                statistics_dict[operator.id]['rejected'] = op_apps.filter(status='rejected').count()

                for app in op_apps:
                    statistics_dict[operator.id]['probes'] += app.probe_count if app.probe_count else 0
                    statistics_dict[operator.id]['time_spent'] += float(app.time_spent) if app.time_spent else 0

        for operator_id, stats in statistics_dict.items():
            writer.writerow([
                stats['name'],
                stats['completed'],
                stats['rejected'],
                stats['probes'],
                round(stats['time_spent'], 2)
            ])

        return response

    def generate_users_csv(self, applications):
        """
        Generate CSV report of user statistics with comparative analysis.

        Creates a comprehensive CSV file with user-level metrics including
        time percentages relative to lab and global totals, and favorite
        operator preferences.

        Args:
            applications (QuerySet): Filtered applications for the period.

        Returns:
            HttpResponse: CSV file download response.
        """
        response = HttpResponse(content_type='text/csv')
        filename = f"user_statistics_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            'Пользователь',
            'Выполнено заявок',
            'Отклонено заявок',
            'Общее затраченное время (ч)',
            'Занято времени относительно коллег по лаборатории, %',
            'Занято времени относительно всех пользователей, %',
            'Любимый оператор',
            'Заявок от любимого оператора, %',
        ])

        lab_stats = {}

        for application in applications:
            if not application.lab or not application.client:
                continue

            lab = application.lab
            user = application.client
            user_name = user.get_full_name() or user.username

            if lab.id not in lab_stats:
                lab_stats[lab.id] = {
                    'name': lab.name,
                    'total_time': 0,
                    'users': {}
                }

            if user.id not in lab_stats[lab.id]['users']:
                lab_stats[lab.id]['users'][user.id] = {
                    'name': user_name,
                    'completed': 0,
                    'rejected': 0,
                    'time_spent': 0,
                    'operators': {}
                }

            if application.status == 'completed':
                lab_stats[lab.id]['users'][user.id]['completed'] += 1
            elif application.status == 'rejected':
                lab_stats[lab.id]['users'][user.id]['rejected'] += 1

            if application.time_spent:
                time_val = float(application.time_spent)
                lab_stats[lab.id]['users'][user.id]['time_spent'] += time_val
                lab_stats[lab.id]['total_time'] += time_val

            if application.operator:
                operator_id = application.operator.id
                if operator_id not in lab_stats[lab.id]['users'][user.id]['operators']:
                    lab_stats[lab.id]['users'][user.id]['operators'][operator_id] = {
                        'name': application.operator.name,
                        'count': 0
                    }
                lab_stats[lab.id]['users'][user.id]['operators'][operator_id]['count'] += 1

        total_global_time = 0
        for lab_id in lab_stats:
            total_global_time += lab_stats[lab_id]['total_time']

        final_stats = []
        for lab_id, lab_data in lab_stats.items():
            for user_id, user_data in lab_data['users'].items():

                lab_time_percent = 0
                if lab_data['total_time'] > 0:
                    lab_time_percent = round((user_data['time_spent'] / lab_data['total_time']) * 100, 2)

                global_time_percent = 0
                if total_global_time > 0:
                    global_time_percent = round((user_data['time_spent'] / total_global_time) * 100, 2)

                favorite_operator = None
                favorite_operator_percent = 0

                if user_data['operators']:
                    total_operator_apps = sum(op['count'] for op in user_data['operators'].values())
                    favorite = max(user_data['operators'].values(), key=lambda x: x['count'])
                    favorite_operator = favorite['name']
                    favorite_operator_percent = round((favorite['count'] / total_operator_apps) * 100, 2)

                final_stats.append({
                    'name': user_data['name'],
                    'completed': user_data['completed'],
                    'rejected': user_data['rejected'],
                    'time_spent': round(user_data['time_spent'], 2),
                    'lab_time_percent': lab_time_percent,
                    'global_time_percent': global_time_percent,
                    'favorite_operator': favorite_operator,
                    'favorite_operator_percent': favorite_operator_percent
                })

        for stats in final_stats:
            writer.writerow([
                stats['name'],
                stats['completed'],
                stats['rejected'],
                stats['time_spent'],
                stats['lab_time_percent'],
                stats['global_time_percent'],
                stats['favorite_operator'] or 'Не указан',
                stats['favorite_operator_percent'],
            ])

        return response


@user_passes_test(lambda user: user.is_superuser or user.is_active_operator)
def make_post_files_list(request):  # Добавьте параметр request
    """
    Generate JSON file listing applications with data ready for posting.

    Creates a JSON file with detailed information about applications that
    have reduced data ready for publication, including probe statuses.

    Args:
        request (HttpRequest): The current request object.

    Returns:
        HttpResponse: JSON file download response.
    """
    apps = Application.objects.filter(status='completed', data_status='DATA_REDUCED')
    data_output = {}

    for app in apps:
        data_output[app.application_code] = {
            'directory': app.raw_data_dir,
            'sample_code': app.sample_code,
            'client': app.client.__str__(),
            'lab': app.lab.__str__(),
            'operator': app.operator.__str__(),
            'all_posted': False,
            'probes': {}
        }
        probes = app.probes.all()
        for probe in probes:
            data_output[app.application_code]['probes'][probe.id] = {
                'status': probe.proc_status,
                'need_to_post': Probe.ProcStatus.need_to_post(probe.proc_status),
                'number': probe.number,
                'post_successful': None,
            }

    # Создаем HttpResponse только один раз
    response = HttpResponse(
        json.dumps(data_output, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )
    filename = f"post_files_{datetime.datetime.now().strftime('%Y-%m-%d')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@user_passes_test(lambda user: user.is_superuser or user.is_active_operator)
def upload_app_post_file(request):
    """
    Handle uploaded JSON file with posted data status updates.

    Processes JSON files containing information about successfully posted
    data and updates application/probe statuses accordingly.

    Args:
        request (HttpRequest): The current request object.

    Returns:
        HttpResponseRedirect: Redirect to referrer page with status message.
    """
    if request.method == 'POST':
        form = JsonUploadForm(request.POST, request.FILES)
        if form.is_valid():
            json_file = request.FILES['json_file']

            if not json_file.name.endswith('.json'):
                messages.error(request, 'Это не JSON-файл!')
                return redirect(request.META.get('HTTP_REFERER', '/'))

            try:
                data = json.loads(json_file.read().decode('utf-8'))
                process_json_data(data)
                messages.success(request, 'Файл успешно обработан!')
                return redirect(request.META.get('HTTP_REFERER', '/'))

            except json.JSONDecodeError:
                messages.error(request, 'Ошибка декодирования JSON!')
            except UnicodeDecodeError:
                messages.error(request, 'Ошибка кодировки файла!')
            except Exception as e:
                messages.error(request, f'Ошибка: {str(e)}')

    return redirect(request.META.get('HTTP_REFERER', '/'))


def process_json_data(data):
    """
    Process JSON data to update application and probe posting statuses.

    Updates data status for applications marked as 'sent' in the JSON
    and records the path to posted data.

    Args:
        data (dict): JSON data dictionary with application posting statuses.
    """
    app_codes = [
        app_code for app_code in data
        if data[app_code].get('sent') is True
    ]
    for app_code in app_codes:
        app = Application.objects.get(application_code=app_code)
        if app.data_status in ['NO_DATA', 'NEED_REDUCTION', 'DATA_SENT']:
            continue
        app.mark_all_reduced_probe_statuses_posted()
        app.reduced_data_dir = data[app_code]['sent_path']
        app.save()


@login_required
def download_reduced_data(request):
    """
    Serve reduced data files for download via X-Accel-Redirect.

    Provides secure file download functionality using nginx's
    X-Accel-Redirect feature for protected file serving.

    Args:
        request (HttpRequest): The current request object.

    Returns:
        HttpResponse: File download response with X-Accel-Redirect header.

    Raises:
        Http404: If application doesn't exist or data is not ready for download.
    """
    if request.method != "GET":
        logger.warning("Download attempted with non-GET method: %s", request.method)
        raise Http404("Только GET запрос поддерживается")

    app_code = request.GET.get('app_code')

    if not app_code:
        raise Http404("Не указан параметр app_code")

    try:
        obj = Application.objects.get(application_code=app_code)
    except Application.DoesNotExist:
        raise Http404("Объект не найден")

    if not obj.can_download:
        raise Http404("Данные не готовы")

    rel_path = obj.reduced_data_dir.replace("\\", "/")
    encoded_path = urllib.parse.quote(rel_path)

    filename = pathlib.Path(rel_path).name

    filename_encoded = urllib.parse.quote(filename)

    if ".." in rel_path or rel_path.startswith("/"):
        raise Http404("Неверный путь к файлу")

    response = HttpResponse()
    response["Content-Type"] = "application/octet-stream"
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename_encoded}"
    response["X-Accel-Redirect"] = f"/protected/{encoded_path}"

    return response