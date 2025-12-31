from django.db import models
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _


class Structurer(models.Model):
    """
    Model representing a structure determination specialist (структурщик).

    This model associates users with the specialized role of performing
    crystal structure analysis, refinement, and deposition tasks. Tracks
    whether the structurer is currently active in the system.
    """

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='structurer_user')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """
        String representation of the Structurer instance.

        Returns:
            str: Full name of the associated user.
        """
        return f"{self.user.get_full_name()}"