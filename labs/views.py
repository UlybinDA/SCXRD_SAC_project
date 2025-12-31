from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, FormView
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from .models import Laboratory
from accounts.models import CustomUser
from services.mixins import ChiefUnderchiefRequiredMixin
from .forms import LaboratoryAddPermissionForm
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.decorators import user_passes_test
import logging

logger = logging.getLogger(__name__)


class ListLabView(LoginRequiredMixin, ListView):
    """
    View for listing users in the current user's laboratory with management capabilities.

    This view displays all active users in the current user's laboratory, ordered by position.
    It also provides context for displaying users with additional permissions and supports
    POST actions for changing user roles and statuses (for chiefs and underchiefs).
    """

    template_name = 'lab_list.html'
    model = Laboratory
    context_object_name = 'lab_users'
    paginate_by = 100

    def get_queryset(self):
        """
        Build queryset of active users in the current user's laboratory.

        Returns:
            QuerySet: Filtered CustomUser queryset ordered by position.
        """
        laboratory = self.request.user.laboratory
        queryset = laboratory.users.filter(is_active=True)
        queryset = queryset.order_by('-position')
        return queryset

    def get_context_data(self, **kwargs):
        """
        Prepare context data for template rendering with user role flags and permissions.

        Includes laboratory information, current user's role flags, and list of users
        with additional permissions to this laboratory.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Comprehensive context dictionary for template.
        """
        context = super().get_context_data(**kwargs)
        users_with_permissions = self.request.user.laboratory.users_with_permissions.all()
        logger.info(f"users_with_permissions: {users_with_permissions}")
        context.update({
            'laboratory': self.request.user.laboratory,
            'is_chief': self.request.user.position == CustomUser.Position.CHIEF,
            'is_underchief': self.request.user.position == CustomUser.Position.UNDERCHIEF,
            'is_worker': self.request.user.position == CustomUser.Position.WORKER,
            'is_student': self.request.user.position == CustomUser.Position.STUDENT,
            'users_with_permissions': users_with_permissions,
            'has_users_with_permissions': users_with_permissions.count() > 0,

        })

        return context

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for user role and status management actions.

        Processes actions to change user positions (make underchief/worker/student)
        or deactivate users. Only available to chiefs and underchiefs for users
        in their own laboratory.

        Args:
            request (HttpRequest): The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponseRedirect: Redirect to lab list with status message.

        Raises:
            PermissionDenied: If user lacks required permissions or tries to
                              modify inappropriate users.
        """
        if not (request.user.position == CustomUser.Position.CHIEF or
                request.user.position == CustomUser.Position.UNDERCHIEF):
            raise PermissionDenied("У вас нет прав для выполнения этого действия")

        if not hasattr(request.user, 'laboratory') or not request.user.laboratory:
            raise PermissionDenied("У вас нет назначенной лаборатории")

        user_id = request.POST.get('user_id')

        action = request.POST.get('action')

        target_user = get_object_or_404(CustomUser, id=user_id)

        if target_user.position == CustomUser.Position.CHIEF:
            raise PermissionDenied("У вас нет прав для выполнения этого действия")

        if target_user.laboratory != request.user.laboratory:
            raise PermissionDenied("Вы можете управлять только пользователями своей лаборатории")

        if target_user == request.user:
            messages.error(request, "Вы не можете изменить свою собственную должность")
            return redirect('lab_list')

        success_message = ""
        if action == 'make_underchief':
            if request.user.position == CustomUser.Position.CHIEF:
                target_user.make_underchief()
                success_message = f'{target_user.get_full_name()} назначен куратором'
            else:
                messages.error(request, "Недостаточно прав для назначения куратора")

        elif action == 'make_worker':
            target_user.make_worker()
            success_message = f'{target_user.get_full_name()} назначен работником'

        elif action == 'make_student':
            target_user.make_student()
            success_message = f'{target_user.get_full_name()} назначен студентом'

        elif action == 'deactivate':
            target_user.deactivate()
            success_message = f'{target_user.get_full_name()} деактивирован'

        if success_message:
            messages.success(request, success_message)

        return redirect('lab_list')


class LaboratoryUserAssignmentView(ChiefUnderchiefRequiredMixin, FormView):
    """
    View for granting additional laboratory permissions to users.

    This form view allows chiefs and underchiefs to grant other users
    permission to create applications on behalf of their laboratory,
    even if those users have a different primary laboratory.
    """

    template_name = 'give_permission.html'
    form_class = LaboratoryAddPermissionForm
    success_url = reverse_lazy('lab_list')

    def get_form_kwargs(self):
        """
        Prepare keyword arguments for form instantiation with laboratory context.

        Returns:
            dict: Keyword arguments including current user's laboratory.
        """
        kwargs = super().get_form_kwargs()
        kwargs['laboratory'] = self.request.user.laboratory
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Prepare context data for template rendering with laboratory information.

        Args:
            **kwargs: Additional context data.

        Returns:
            dict: Context dictionary with laboratory and title.
        """
        context = super().get_context_data(**kwargs)
        laboratory = self.request.user.laboratory
        context['laboratory'] = laboratory
        context['title'] = f'Управление доступом - {laboratory.name}'
        return context

    def form_valid(self, form):
        """
        Handle valid form submission to grant laboratory permissions.

        Adds the selected user to the laboratory's permission list and
        displays a success message.

        Args:
            form (LaboratoryAddPermissionForm): Validated form instance.

        Returns:
            HttpResponseRedirect: Redirect to success URL.
        """
        user = self.request.user

        laboratory = user.laboratory
        selected_user = form.cleaned_data['new_user']

        selected_user.lab_permissions.add(laboratory)
        messages.success(
            self.request,
            f'Пользователю {selected_user.get_full_name()} предоставлен доступ к лаборатории "{laboratory.name}"'
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Handle invalid form submission with error message display.

        Extracts validation errors from the form and converts them to
        Django messages for user feedback.

        Args:
            form (LaboratoryAddPermissionForm): Invalid form instance.

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


@user_passes_test(lambda u: u.is_chief or u.is_underchief)
def take_away_permissions(request):
    """
    View function to revoke additional laboratory permissions from a user.

    Removes a user from the laboratory's permission list, revoking their
    ability to create applications on behalf of that laboratory.

    Args:
        request (HttpRequest): The current request object.

    Returns:
        HttpResponseRedirect: Redirect to laboratory list with status message.

    Note:
        Decorated to allow access only to chiefs and underchiefs.
    """
    user = request.user
    laboratory = user.laboratory
    worker_id = request.POST.get('worker')

    try:
        if worker_id:
            worker = CustomUser.objects.get(id=worker_id)
            if worker.lab_permissions.filter(id=laboratory.id).exists():
                worker.lab_permissions.remove(laboratory)
                messages.success(request,
                                 f'Пользователь {worker} был лишен возможности создавать заявки от лица группы {laboratory.name}')
            else:
                messages.warning(request,
                                 f'Пользователь {worker} не имеет прав на создание заявок для этой лаборатории')
        else:
            messages.error(request, 'ID пользователя не указан')

        return redirect('lab_list')
    except CustomUser.DoesNotExist:
        messages.error(request, 'Пользователь не найден')
        return redirect('lab_list')
    except Exception as e:
        messages.error(request, f'Ошибка {e}')
        return redirect('lab_list')


def user_search_api(request):
    """
    API endpoint for searching users by name or username.

    Provides JSON response for autocomplete functionality in user selection
    forms. Returns up to 20 matching users.

    Args:
        request (HttpRequest): The current request object.

    Returns:
        JsonResponse: JSON object with list of matching users in format
                      {"id": user.id, "text": user_string_representation}.
    """
    query = request.GET.get('q', '').strip()

    if query:
        users = CustomUser.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query)
        )[:20]
    else:
        users = CustomUser.objects.all()[:20]

    results = [
        {"id": u.id, "text": str(u)}
        for u in users
    ]

    return JsonResponse({"results": results})