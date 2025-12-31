from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied


class OperatorRequiredMixin(AccessMixin):
    """
    Mixin to restrict view access to authenticated users with operator role.

    This mixin ensures that only users with active operator profiles can
    access views where it's applied. Non-authenticated users are redirected
    to log in, authenticated non-operators receive PermissionDenied or redirect.
    """

    login_url = reverse_lazy('login')
    permission_denied_message = "Доступ запрещён: требуется роль оператора"
    redirect_authenticated_users = True

    def dispatch(self, request, *args, **kwargs):
        """
        Dispatch method override to add operator permission checking.

        Validates user authentication and operator status before allowing
        access to the view.

        Args:
            request (HttpRequest): The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: View response or redirect/permission denied response.
        """
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()

        if not user.is_active_operator:
            if self.redirect_authenticated_users:
                return redirect(self.get_redirect_url())
            raise PermissionDenied(self.permission_denied_message)

        return super().dispatch(request, *args, **kwargs)

    def get_redirect_url(self):
        """
        Get the URL to redirect unauthorized users to.

        Returns:
            str: The login URL configured for the mixin.
        """
        return self.login_url


class ChiefUnderchiefRequiredMixin(AccessMixin):
    """
    Mixin to restrict view access to authenticated users with chief or underchief roles.

    This mixin ensures that only users with chief (заведующий) or underchief (куратор)
    positions can access views where it's applied.
    """

    login_url = reverse_lazy('login')
    permission_denied_message = "Доступ запрещён: требуется роль шефа или куратора"
    redirect_authenticated_users = True

    def dispatch(self, request, *args, **kwargs):
        """
        Dispatch method override to add chief/underchief permission checking.

        Validates user authentication and position status before allowing
        access to the view.

        Args:
            request (HttpRequest): The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: View response or redirect/permission denied response.
        """
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()

        if not (user.is_chief or user.is_underchief):
            if self.redirect_authenticated_users:
                return redirect(self.get_redirect_url())
            raise PermissionDenied(self.permission_denied_message)

        return super().dispatch(request, *args, **kwargs)

    def get_redirect_url(self):
        """
        Get the URL to redirect unauthorized users to.

        Returns:
            str: The login URL configured for the mixin.
        """
        return self.login_url