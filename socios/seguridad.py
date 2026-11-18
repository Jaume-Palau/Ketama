"""Adaptación mínima de Axes: privacidad y presentación del bloqueo."""
from django.conf import settings
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_cache_control


def ip_no_identificativa(request):
    """No registrar IPs reales; el bloqueo depende únicamente de username."""
    # Valor técnico fijo: evita NULL en la unicidad de AccessAttempt de Axes,
    # también cuando dos procesos registran el primer fallo simultáneamente.
    return "0.0.0.0"


def respuesta_bloqueo(request, original_response=None, credentials=None):
    # La respuesta predeterminada de Axes puede incluir username en JSON para
    # XMLHttpRequest. Siempre ofrecer una respuesta genérica sin credenciales.
    admin_login = reverse("admin:login")
    response = render(request, settings.AXES_LOCKOUT_TEMPLATE, {
        "url_acceso": admin_login if request.path == admin_login else reverse("socios:login"),
    }, status=settings.AXES_HTTP_RESPONSE_CODE)
    patch_cache_control(response, private=True, no_store=True, no_cache=True)
    return response
