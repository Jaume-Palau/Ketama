from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("socios", "0002_socio_debe_cambiar_password")]

    operations = [
        migrations.AlterField(
            model_name="socio",
            name="telefono",
            field=models.CharField(blank=True, max_length=30, verbose_name="teléfono"),
        ),
    ]
