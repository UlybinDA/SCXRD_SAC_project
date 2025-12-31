from django.contrib.auth.views import LoginView, PasswordResetView
from .forms import EmailAuthenticationForm
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from .models import CustomUser
from .forms import CustomUserCreationForm
from accounts.forms import APasswordResetForm
import logging

logger = logging.getLogger(__name__)



class CustomLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_users = True
    template_name = 'registration/login.html'

    def form_invalid(self, form):
        """
        Handle invalid login forms by displaying an error message.
        Args:
            form: The invalid form instance.
        Returns:
            HttpResponse: The rendered login page with an error message.
        """
        messages.error(
            self.request,
            "Неверная почта или пароль. Попробуйте ещё раз."
        )
        return super().form_invalid(form)




class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'registration/create_user.html'
    success_url = reverse_lazy('user_list')

    def test_func(self):
        """
        Check if the current user has sufficient privileges to create new users.
        Returns:
            bool: True if user is CHIEF or UNDERCHIEF, otherwise False.
        """
        user = self.request.user
        return user.position in [CustomUser.Position.CHIEF, CustomUser.Position.UNDERCHIEF]

    def handle_no_permission(self):
        """
        Handle access denial by displaying an error message and redirecting.
        Returns:
            HttpResponseRedirect: Redirects the user to home with an error message.
        """
        messages.error(self.request, _('У вас нет прав для создания пользователей'))
        return redirect('home')

    def get_form_kwargs(self):
        """
        Pass the current user's laboratory and instance to the user creation form.
        Returns:
            dict: Keyword arguments for form instantiation, with added user_lab and current_user.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user_lab'] = self.request.user.laboratory
        kwargs['current_user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Add additional context information for the template, such as titles and allowed user positions.
        Args:
            **kwargs: Additional keyword arguments.
        Returns:
            dict: Template context including allowed positions and page title.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = _('Создание нового пользователя')
        context['allowed_positions'] = [
            {'value': CustomUser.Position.STUDENT, 'label': _('Студент')},
            {'value': CustomUser.Position.WORKER, 'label': _('Работник')},
        ]
        return context

    def form_valid(self, form):
        """
        Handle valid user creation form submissions, creating the user and providing feedback.
        Args:
            form: The valid CustomUserCreationForm instance.
        Returns:
            HttpResponse: Redirect or page response depending on creation success.
        """
        try:
            user = form.save()
            messages.success(
                self.request,
                _('Пользователь {} успешно создан.').format(user.get_full_name())
            )
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, _('Ошибка при создании пользователя: {}').format(str(e)))
            return self.form_invalid(form)

class CustomPasswordResetView(PasswordResetView):
    form_class = APasswordResetForm
    template_name = 'registration/password_reset_form.html'
    
    def form_valid(self, form):
        """
        Handle a valid password reset form submission, logging the event for debugging purposes.
        Args:
            form: The valid password reset form instance.
        Returns:
            HttpResponse: Redirect to the success URL after handling the reset.
        """
        logger.debug("CustomPasswordResetView.form_valid called")
        result = super().form_valid(form)
        logger.debug(f"Form is valid, redirecting to: {self.get_success_url()}")
        return result
    
    def form_invalid(self, form):
        """
        Handle an invalid password reset form, logging errors for debugging.
        Args:
            form: The invalid password reset form instance.
        Returns:
            HttpResponse: The rendered page with errors displayed.
        """
        logger.debug("CustomPasswordResetView.form_invalid called")
        logger.debug(f"Form errors: {form.errors}")
        return super().form_invalid(form)
