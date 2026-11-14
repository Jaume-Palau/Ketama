"""Gestión del catálogo desde Django Admin."""
from django.contrib import admin

from .models import Genetica


@admin.register(Genetica)
class GeneticaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clasificacion", "thc", "tipo_cultivo", "activo")
    list_editable = ("activo",)
    list_filter = ("clasificacion", "tipo_cultivo", "activo")
    search_fields = ("nombre",)
