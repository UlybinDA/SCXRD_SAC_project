from django.shortcuts import render
from django.views.generic import CreateView, UpdateView, DeleteView, ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Suggestion
from django.urls import reverse_lazy


# Create your views here.


class CreateSuggestion(LoginRequiredMixin, CreateView):
    """
    View for creating new suggestion/feedback entries.

    This view provides a form for authenticated users to submit suggestions,
    feedback, or issue reports to the system administrators. Automatically
    associates the suggestion with the current user.

    Attributes:
        fields (list): Form fields to include (subject and text).
        model (Model): The Suggestion model class.
        template_name (str): Template for rendering the suggestion form.
        success_url (str): URL to redirect to after successful submission.
    """

    fields = ["subject", "text"]
    model = Suggestion
    template_name = "create_suggestion.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        """
        Handle valid form submission by setting the author to current user.

        Args:
            form (ModelForm): Validated form instance.

        Returns:
            HttpResponseRedirect: Redirect to success URL.
        """
        form.instance.author = self.request.user
        return super().form_valid(form)