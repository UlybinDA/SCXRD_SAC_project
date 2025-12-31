import django_filters
from .models import Application

# not used
class ApplicationFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    status = django_filters.ChoiceFilter(choices=Application.STATUS_CHOICES)

    class Meta:
        model = Application
        fields = ['status', 'lab']