"""Fichas de genéticas del catálogo."""
from decimal import Decimal
from math import isfinite

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, router, transaction

from socios.models import Socio


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

    def resumen_valoraciones(self):
        """Media y número de votos en una consulta; incluye votos históricos."""
        return self.valoraciones.aggregate(
            media=models.Avg("puntuacion", default=0),
            numero=models.Count("pk"),
        )

    @property
    def puntuacion_media(self):
        return self.resumen_valoraciones()["media"]

    @property
    def numero_valoraciones(self):
        return self.valoraciones.count()


class ValoracionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError("Actualiza cada valoración mediante save() para validar sus reglas.")

    def bulk_create(self, *args, **kwargs):
        raise TypeError("Crea cada valoración mediante save() para validar sus reglas.")

    def bulk_update(self, *args, **kwargs):
        raise TypeError("Actualiza cada valoración mediante save() para validar sus reglas.")


class Valoracion(models.Model):
    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name="valoraciones")
    genetica = models.ForeignKey(Genetica, on_delete=models.CASCADE, related_name="valoraciones")
    puntuacion = models.PositiveSmallIntegerField(
        "puntuación", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    fecha = models.DateTimeField("fecha de creación", auto_now_add=True)

    objects = ValoracionQuerySet.as_manager()

    class Meta:
        verbose_name = "valoración"
        verbose_name_plural = "valoraciones"
        base_manager_name = "objects"
        ordering = ["-fecha", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["socio", "genetica"], name="valoracion_unica_socio_genetica"
            ),
            models.CheckConstraint(
                condition=models.Q(puntuacion__gte=1, puntuacion__lte=5),
                name="valoracion_puntuacion_entre_1_y_5",
            ),
        ]

    def clean_fields(self, exclude=None):
        # IntegerField convierte 2.5 en 2: rechazar fracciones antes de convertir.
        if "puntuacion" not in (exclude or ()) and isinstance(self.puntuacion, (float, Decimal)):
            if not isfinite(self.puntuacion) or self.puntuacion % 1:
                raise ValidationError({"puntuacion": "Introduce un número entero entre 1 y 5."})
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        if self.socio_id is not None:
            socio = Socio.objects.using(self._state.db).filter(pk=self.socio_id).values(
                "estado", "usuario__is_active"
            ).first()
            if socio and (
                socio["estado"] != Socio.Estado.ACTIVO or not socio["usuario__is_active"]
            ):
                raise ValidationError({"socio": "Solo un socio activo con cuenta habilitada puede valorar."})
        if self.pk is not None and not self._state.adding:
            original = type(self).objects.using(self._state.db).filter(pk=self.pk).values(
                "socio_id", "genetica_id"
            ).first()
            if original and (
                original["socio_id"] != self.socio_id or original["genetica_id"] != self.genetica_id
            ):
                raise ValidationError("No se puede reasignar una valoración; modifica solo su puntuación.")

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            # Serializa el voto con los cambios de estado del mismo socio.
            if self.socio_id is not None:
                Socio.objects.using(using).select_for_update().filter(pk=self.socio_id).first()
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.socio} · {self.genetica}: {self.puntuacion}"
