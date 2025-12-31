from django.urls import path
from .views import CreateSuggestion



urlpatterns = [
    path("suggestion/", CreateSuggestion.as_view(), name="suggestion"),
]