from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user based on email (instead of username) and password.
        Args:
            request: The current HttpRequest object.
            username (str): The user's email address.
            password (str): The user's password.
            **kwargs: Additional keyword arguments.
        Returns:
            The authenticated user instance if credentials are valid, otherwise None.
        """
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            return None
        else:
            if user.check_password(password):
                return user
        return None