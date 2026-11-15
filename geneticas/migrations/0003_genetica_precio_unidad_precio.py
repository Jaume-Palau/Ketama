from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("geneticas", "0002_valoracion")]

    operations = [
        migrations.AddField(
            model_name="genetica",
            name="precio",
            field=models.DecimalField(
                blank=True, null=True, decimal_places=2, max_digits=8,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="precio",
            ),
        ),
        migrations.AddField(
            model_name="genetica",
            name="unidad_precio",
            field=models.CharField(
                choices=[("gramo", "Gramo"), ("unidad", "Unidad")],
                default="gramo", max_length=6, verbose_name="unidad del precio",
            ),
        ),
        migrations.AddConstraint(
            model_name="genetica",
            constraint=models.CheckConstraint(
                condition=models.Q(precio__gte=0) | models.Q(precio__isnull=True),
                name="genetica_precio_no_negativo",
            ),
        ),
    ]
