"""Rutas principales del proyecto."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("catalogo/", include("geneticas.urls")),
    path("", include("socios.urls")),
]
