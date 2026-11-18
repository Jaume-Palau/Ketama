"""Rutas privadas ficticias para comprobar el middleware entre aplicaciones."""
from django.http import HttpResponse
from django.urls import include, path

from config.urls import urlpatterns as rutas_proyecto
from comunicacion.urls import urlpatterns as rutas_comunicacion


def privada(request):
    return HttpResponse("Funcionalidad privada ficticia")


urlpatterns = [
    path("avisos/", include(([
        *rutas_comunicacion,
        path("prueba/", privada, name="inicio"),
        path("prueba/accion/", privada, name="accion"),
        path("prueba/login/", privada, name="login"),
    ], "comunicacion"), namespace="comunicacion")),
    *(ruta for ruta in rutas_proyecto if getattr(ruta, "namespace", None) != "comunicacion"),
]
