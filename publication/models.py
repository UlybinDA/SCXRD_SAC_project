from django.db import models
import re
# Create your models here.
class Publication(models.Model):
    """
    Model representing a publication.
    """

    doi_pattern = re.compile(r'^10\.\d{4,}(?:\.\d+)*\/[^\s/]+$')
    doi = models.CharField(
        'Код doi',
        max_length=100,
        unique=True
    )