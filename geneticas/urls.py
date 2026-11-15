"""Rutas privadas del catálogo."""
from django.urls import path

from . import views

app_name = "geneticas"
urlpatterns = [
    path("", views.catalogo, name="catalogo"),
    path("<int:pk>/", views.detalle, name="detalle"),
]
