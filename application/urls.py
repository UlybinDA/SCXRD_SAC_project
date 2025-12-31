from django.urls import path
from .views import (ApplicationCreateView, ApplicationUpdateView, ApplicationDeleteView, ApplicationDetailView,
    ApplicationListView, ApplicationProcessView, ReductionListView, mark_probes_reduced, mark_sample_returned,
                    StatisticsView, make_post_files_list,upload_app_post_file, download_reduced_data)

urlpatterns = [
    path("create_app/", ApplicationCreateView.as_view(), name="create_application"),
    path("list_app/", ApplicationListView.as_view(), name="application_list"),
    path('list_reductions/', ReductionListView.as_view(), name='reductions_list'),
    path('statistics/', StatisticsView.as_view(), name='statistics'),
    path('post_data/', make_post_files_list, name='post_data'),
    path('download/', download_reduced_data, name='download_red_data'),
    path('upload_post_data/', upload_app_post_file, name='upload_post_data'),
    path('<str:application_code>/edit/', ApplicationUpdateView.as_view(), name='application_edit'),
    path('<str:application_code>/delete/', ApplicationDeleteView.as_view(), name='application_delete'),
    path('<str:application_code>/', ApplicationDetailView.as_view(), name='application_detail'),
    path('<str:application_code>/process', ApplicationProcessView.as_view(), name='application_process'),
    path('application/<str:application_code>/mark_reduced/', mark_probes_reduced, name='mark_probes_reduced'),
    path('application/<str:application_code>/mark_returned/', mark_sample_returned, name='mark_sample_returned'),
]
