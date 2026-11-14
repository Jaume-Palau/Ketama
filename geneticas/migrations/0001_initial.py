from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Genetica",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                )),
                ("nombre", models.CharField(max_length=200, verbose_name="nombre")),
                ("imagen", models.URLField(
                    blank=True, max_length=500, verbose_name="URL de imagen"
                )),
                ("clasificacion", models.CharField(
                    choices=[("sativa", "Sativa"), ("indica", "Índica"), ("hibrida", "Híbrida")],
                    max_length=10, verbose_name="clasificación",
                )),
                ("thc", models.DecimalField(
                    blank=True, null=True, decimal_places=2, max_digits=5,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal("0")),
                        django.core.validators.MaxValueValidator(Decimal("100")),
                    ],
                    verbose_name="THC (%)",
                )),
                ("tipo_cultivo", models.CharField(
                    choices=[("interior", "Interior"), ("exterior", "Exterior")],
                    max_length=10, verbose_name="tipo de cultivo",
                )),
                ("descripcion", models.TextField(verbose_name="descripción")),
                ("activo", models.BooleanField(default=True, verbose_name="activo")),
            ],
            options={
                "verbose_name": "genética",
                "verbose_name_plural": "genéticas",
                "ordering": ["nombre"],
                "constraints": [models.CheckConstraint(
                    condition=models.Q(thc__gte=0, thc__lte=100) | models.Q(thc__isnull=True),
                    name="genetica_thc_entre_0_y_100",
                )],
            },
        ),
    ]
