from django.urls import path
from .views import JornalListView

urlpatterns = [
path("", JornalListView.as_view(), name="home"),
]
