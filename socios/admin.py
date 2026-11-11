"""Gestión conjunta de cuentas y perfiles desde Django Admin."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Socio


class SocioInline(admin.StackedInline):
    model = Socio
    fields = ("nombre_completo", "telefono", "debe_cambiar_password")
    extra = 1
    max_num = 1
    can_delete = False
    verbose_name_plural = "Perfil de socio (solo para cuentas de socios)"


admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    inlines = (SocioInline,)
    list_display = ("username", "nombre_socio", "is_active", "is_staff")
    search_fields = ("username", "socio__nombre_completo", "socio__telefono")
    list_filter = ("is_active", "is_staff")
    list_select_related = ("socio",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Acceso", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "username":
            kwargs["label"] = "Número de socio / usuario administrador"
            kwargs["help_text"] = (
                "Para los socios, introduce su número de socio. "
                "Será su identificador único de inicio de sesión."
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="Nombre completo", ordering="socio__nombre_completo")
    def nombre_socio(self, obj):
        try:
            return obj.socio.nombre_completo
        except Socio.DoesNotExist:
            return "—"
