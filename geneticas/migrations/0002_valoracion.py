import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("geneticas", "0001_initial"),
        ("socios", "0004_socio_estado"),
    ]

    operations = [
        migrations.CreateModel(
            name="Valoracion",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                )),
                ("puntuacion", models.PositiveSmallIntegerField(
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5),
                    ],
                    verbose_name="puntuación",
                )),
                ("fecha", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("genetica", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="valoraciones", to="geneticas.genetica",
                )),
                ("socio", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="valoraciones", to="socios.socio",
                )),
            ],
            options={
                "verbose_name": "valoración",
                "verbose_name_plural": "valoraciones",
                "base_manager_name": "objects",
                "ordering": ["-fecha", "-pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("socio", "genetica"), name="valoracion_unica_socio_genetica"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(puntuacion__gte=1, puntuacion__lte=5),
                        name="valoracion_puntuacion_entre_1_y_5",
                    ),
                ],
            },
        ),
    ]
