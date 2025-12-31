from django.urls import path
from .views import add_doi_to_probe

urlpatterns = [
    path("attach_doi/", add_doi_to_probe, name="add_doi_to_probe"),
]

