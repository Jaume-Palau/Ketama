from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("socios", "0003_socio_telefono_opcional")]

    operations = [
        migrations.AddField(
            model_name="socio",
            name="estado",
            field=models.CharField(
                choices=[("activo", "Activo"), ("caducado", "Caducado")],
                default="caducado", max_length=8, verbose_name="estado",
            ),
        ),
    ]
