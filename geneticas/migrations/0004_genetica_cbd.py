from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("geneticas", "0003_genetica_precio_unidad_precio")]

    operations = [
        migrations.AddField(
            model_name="genetica",
            name="cbd",
            field=models.DecimalField(
                blank=True, null=True, decimal_places=2, max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
                verbose_name="CBD (%)",
            ),
        ),
        migrations.AddConstraint(
            model_name="genetica",
            constraint=models.CheckConstraint(
                condition=models.Q(cbd__gte=0, cbd__lte=100) | models.Q(cbd__isnull=True),
                name="genetica_cbd_entre_0_y_100",
            ),
        ),
    ]
