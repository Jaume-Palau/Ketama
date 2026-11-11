"""Perfil de socio asociado a la cuenta nativa de Django."""
from django.conf import settings
from django.db import models


class Socio(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="socio",
        verbose_name="usuario",
    )
    nombre_completo = models.CharField("nombre completo", max_length=200)
    telefono = models.CharField("teléfono", max_length=30)

    class Meta:
        verbose_name = "socio"
        verbose_name_plural = "socios"
        ordering = ["usuario__username"]

    @property
    def numero_socio(self):
        return self.usuario.get_username()

    def __str__(self):
        return f"{self.numero_socio} — {self.nombre_completo}"
