from django.urls import path
from .views import QuotaApplicationsView, refresh_quotas_manually,QuotaTimeTransferCreateView,QuotaTimeTransferListView

urlpatterns = [
    path("quota_list/", QuotaApplicationsView.as_view(), name="quota_list"),
    path("quota_transfer/", QuotaTimeTransferCreateView.as_view(), name="quota_transfer"),
    path('quota-transactions/', QuotaTimeTransferListView.as_view(), name='quota_transfer_list'),
    path("quota_refresh/", refresh_quotas_manually, name="quota_man_request"),
]