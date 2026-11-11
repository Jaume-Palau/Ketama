"""Control de acceso para todas las rutas del espacio de socios."""
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.cache import patch_cache_control
from django.utils.deprecation import MiddlewareMixin

from .models import Socio


class AccesoSociosMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not match or match.namespace != "socios":
            return None
        if match.url_name == "login":
            return None
        if not request.user.is_authenticated:
            if match.url_name == "logout":
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
        if request.socio.debe_cambiar_password and match.url_name not in {
            "cambiar_password", "logout"
        }:
            return redirect("socios:cambiar_password")
        return None

    def process_response(self, request, response):
        match = request.resolver_match
        if match and match.namespace == "socios":
            patch_cache_control(response, private=True, no_store=True, no_cache=True)
        return response
