"""Fichas de genéticas del catálogo."""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Genetica(models.Model):
    class Clasificacion(models.TextChoices):
        SATIVA = "sativa", "Sativa"
        INDICA = "indica", "Índica"
        HIBRIDA = "hibrida", "Híbrida"

    class TipoCultivo(models.TextChoices):
        INTERIOR = "interior", "Interior"
        EXTERIOR = "exterior", "Exterior"

    nombre = models.CharField("nombre", max_length=200)
    imagen = models.URLField("URL de imagen", max_length=500, blank=True)
    clasificacion = models.CharField(
        "clasificación", max_length=10, choices=Clasificacion.choices
    )
    thc = models.DecimalField(
        "THC (%)",
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    tipo_cultivo = models.CharField(
        "tipo de cultivo", max_length=10, choices=TipoCultivo.choices
    )
    descripcion = models.TextField("descripción")
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "genética"
        verbose_name_plural = "genéticas"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(thc__gte=0, thc__lte=100) | models.Q(thc__isnull=True),
                name="genetica_thc_entre_0_y_100",
            ),
        ]

    def __str__(self):
        return self.nombre
