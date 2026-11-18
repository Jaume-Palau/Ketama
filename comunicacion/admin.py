"""Edición y publicación manual de avisos."""
from django.contrib import admin

from .models import Aviso


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fecha_creacion", "activo")
    list_editable = ("activo",)
    list_filter = ("activo",)
    search_fields = ("titulo", "mensaje")
    readonly_fields = ("fecha_creacion",)
