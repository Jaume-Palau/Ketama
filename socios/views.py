"""Acceso y página provisional de socios."""
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.db import transaction
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.http import require_safe

from .forms import AccesoSocioForm, CambioPasswordSocioForm


class AccesoSocioView(LoginView):
    template_name = "socios/login.html"
    authentication_form = AccesoSocioForm

    def get_success_url(self):
        # Destino fijo: no se permite saltar el control con ?next=, ni ir al Admin.
        if self.request.user.socio.debe_cambiar_password:
            return str(reverse_lazy("socios:cambiar_password"))
        return str(reverse_lazy("socios:inicio"))


class CambioPasswordSocioView(PasswordChangeView):
    template_name = "socios/cambiar_password.html"
    form_class = CambioPasswordSocioForm
    success_url = reverse_lazy("socios:inicio")

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            # PasswordChangeView conserva la sesión con update_session_auth_hash.
            socio = self.request.socio
            socio.debe_cambiar_password = False
            socio.save(update_fields=["debe_cambiar_password"])
        return response


class SalidaSocioView(LogoutView):
    next_page = reverse_lazy("socios:login")

    def get_success_url(self):
        return str(self.next_page)


@require_safe
def inicio(request):
    return render(request, "socios/inicio.html", {"socio": request.socio})
