import django_filters
from .models import Application

# not used
class ApplicationFilter(django_filters.FilterSet):
    class Meta:
        model = Application
        fields = ['sample_code', 'status', 'date', 'lab']