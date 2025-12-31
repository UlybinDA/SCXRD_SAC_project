from django.urls import path
from .views import ListLabView, user_search_api, LaboratoryUserAssignmentView, take_away_permissions

urlpatterns = [
    path("", ListLabView.as_view(), name="lab_list"),
    path("lab_permission/", LaboratoryUserAssignmentView.as_view(), name="laboratory_permission"),
    path('api/user-search/', user_search_api, name='user_search_api'),
    path('takeaway_perm/', take_away_permissions, name="take_away_permissions"),
]
