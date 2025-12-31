from django.db import models
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _


class Suggestion(models.Model):
    """
    Model representing user suggestions or feedback entries.

    This model stores suggestions, feedback, or issue reports submitted by
    users of the system. Each entry is tied to a user author and tracks
    submission date and resolution status.

    Attributes:
        author (ForeignKey): User who submitted the suggestion.
        subject (str): Brief subject or title of the suggestion.
        text (TextField): Detailed content of the suggestion.
        date (DateTimeField): Timestamp when the suggestion was submitted.
        status (bool): Whether the suggestion has been resolved/addressed.
    """

    author = models.ForeignKey(CustomUser,
                               verbose_name=_('Пользователь'),
                               on_delete=models.PROTECT,
                               blank=False,
                               null=False)
    subject = models.CharField(max_length=200, verbose_name=_('Тема предложения'))
    text = models.TextField(verbose_name=_('Содержание'))
    date = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField(verbose_name=_('Решено'), default=False)