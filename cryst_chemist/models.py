from django.db import models
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _


class CrystChemist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                             related_name='crystchem_user')
    is_active = models.BooleanField(default=True)
    def __str__(self):
        """
        Human-readable representation of the user associated with crystchemist.
        """
        return f"{self.user.get_full_name()}"