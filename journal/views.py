from django.shortcuts import render
from django.views.generic import ListView
from application.models import Application


class JornalListView(ListView):
    model = Application
    template_name = 'home.html'

