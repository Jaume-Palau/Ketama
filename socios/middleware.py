"""Control de acceso a los espacios privados; el Admin conserva su propio acceso."""
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.cache import patch_cache_control
from django.utils.deprecation import MiddlewareMixin

from .models import Socio

ESPACIOS_PRIVADOS = {"socios", "geneticas", "comunicacion"}


class AccesoSociosMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not match or not ESPACIOS_PRIVADOS.intersection(match.namespaces):
            return None
        es_socios = match.namespace == "socios"
        if es_socios and match.url_name == "login":
            return None
        if not request.user.is_authenticated:
            if es_socios and match.url_name == "logout":
                return None
            return redirect_to_login(request.get_full_path(), login_url="socios:login")
        if (
            not request.user.is_active
            or request.user.is_staff
            or request.user.is_superuser
        ):
            raise PermissionDenied
        try:
            request.socio = request.user.socio
        except Socio.DoesNotExist:
            raise PermissionDenied
        acceso_basico = es_socios and match.url_name in {"cambiar_password", "logout"}
        if request.socio.debe_cambiar_password and not acceso_basico:
            return redirect("socios:cambiar_password")
        es_aviso = es_socios and match.url_name == "caducado"
        if request.socio.estado != Socio.Estado.ACTIVO:
            if not acceso_basico and not es_aviso:
                return redirect("socios:caducado")
        elif es_aviso:
            return redirect("socios:inicio")
        return None

    def process_response(self, request, response):
        match = request.resolver_match
        if match and ESPACIOS_PRIVADOS.intersection(match.namespaces):
            patch_cache_control(response, private=True, no_store=True, no_cache=True)
        return response
