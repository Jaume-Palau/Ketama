"""Rutas privadas ficticias para comprobar el middleware entre aplicaciones."""
from django.http import HttpResponse
from django.urls import include, path

from config.urls import urlpatterns as rutas_proyecto


def privada(request):
    return HttpResponse("Funcionalidad privada ficticia")


urlpatterns = [
    path("prueba-catalogo/", include(([
        path("", privada, name="inicio"),
        path("accion/", privada, name="accion"),
        path("login/", privada, name="login"),
    ], "geneticas"), namespace="geneticas")),
    *rutas_proyecto,
]
