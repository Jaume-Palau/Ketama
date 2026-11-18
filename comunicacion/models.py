"""Comunicados publicados manualmente por el club."""
from django.db import models


class Aviso(models.Model):
    titulo = models.CharField("título", max_length=200)
    mensaje = models.TextField("mensaje")
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    activo = models.BooleanField("publicado", default=False)

    class Meta:
        verbose_name = "aviso"
        verbose_name_plural = "avisos"
        ordering = ["-fecha_creacion", "-pk"]

    def __str__(self):
        return self.titulo
