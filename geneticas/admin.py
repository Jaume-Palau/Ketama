"""Gestión del catálogo desde Django Admin."""
from django.contrib import admin

from .models import Genetica, Valoracion


@admin.register(Genetica)
class GeneticaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clasificacion", "thc", "tipo_cultivo", "activo")
    list_editable = ("activo",)
    list_filter = ("clasificacion", "tipo_cultivo", "activo")
    search_fields = ("nombre",)


@admin.register(Valoracion)
class ValoracionAdmin(admin.ModelAdmin):
    list_display = ("socio", "genetica", "puntuacion", "fecha")
    list_filter = ("puntuacion",)
    list_select_related = ("socio__usuario", "genetica")
    readonly_fields = ("socio", "genetica", "puntuacion", "fecha")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
