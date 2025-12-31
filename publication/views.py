from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, reverse
from probe.models import Probe
from application.models import Application
from publication.models import Publication
from django.contrib import messages
import re


@login_required
def add_doi_to_probe(request):
    """
    View function to attach a DOI (Digital Object Identifier) to a probe.

    This function processes POST requests to link a publication DOI to a specific
    probe. It validates user permissions, DOI format, and probe eligibility before
    creating or retrieving the Publication and adding it to the probe's publications.

    Args:
        request (HttpRequest): The current request object containing POST data.

    Returns:
        HttpResponseRedirect: Redirect to application detail page with status message.

    """

    def fail(msg):
        """
        Helper function to handle failed validation with error message.

        Args:
            msg (str): Error message to display to the user.

        Returns:
            HttpResponseRedirect: Redirect with error message.
        """
        messages.error(request, msg)
        return redirect(redirect_url)

    if request.method != 'POST':
        messages.error(request, 'Метод запроса должен быть POST.')
        return redirect('/')

    doi = request.POST.get('doi')
    probe_id = request.POST.get('probe')
    app_code = request.POST.get('app_code')
    redirect_url = reverse('application_detail', kwargs={'application_code': app_code})

    application = Application.objects.get(application_code=app_code)

    # Проверка прав
    if not (request.user.laboratory == application.lab and
            (application.client == request.user or request.user.is_chief or request.user.is_underchief)):
        return fail('Нет прав на добавление doi')

    if not all([doi, probe_id, app_code]):
        return fail('Не указаны обязательные параметры.')

    try:
        probe = Probe.objects.get(id=int(probe_id))
    except (Probe.DoesNotExist, ValueError):
        return fail('Проба не найдена.')

    if not probe.publication_attachable:
        return fail('Нельзя прикрепить DOI к данной пробе.')

    if not re.fullmatch(Publication.doi_pattern, doi):
        return fail('DOI имеет неверный формат.')

    publication, _ = Publication.objects.get_or_create(doi=doi)
    probe.publications.add(publication)

    messages.success(request, f'DOI {doi} успешно привязан к пробе.')
    return redirect(redirect_url)