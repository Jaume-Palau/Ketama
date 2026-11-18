"""Espacio privado de avisos del club."""
from django.urls import path

from . import views

app_name = "comunicacion"
urlpatterns = [path("", views.avisos, name="avisos")]
