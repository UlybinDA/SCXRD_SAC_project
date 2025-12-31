from django.urls import path
from .views import CustomLoginView
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from .forms import APasswordResetForm
from .views import UserCreateView, CustomPasswordResetView

urlpatterns = [
path("login/", CustomLoginView.as_view(next_page='home'), name="login"),
path("logout/", LogoutView.as_view(next_page='home'), name="logout"),
path('create/', UserCreateView.as_view(), name='user_create'),
path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view( template_name='registration/password_reset_done.html' ),
        name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view( template_name='registration/password_reset_confirm.html' ),
        name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete'    ),



]
