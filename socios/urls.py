"""Rutas propias del espacio de socios, independientes de /admin/."""
from django.urls import path

from . import views

app_name = "socios"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("cuota-caducada/", views.caducado, name="caducado"),
    path("acceso/", views.AccesoSocioView.as_view(), name="login"),
    path("cambiar-password/", views.CambioPasswordSocioView.as_view(), name="cambiar_password"),
    path("salir/", views.SalidaSocioView.as_view(), name="logout"),
]
