from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("socios", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="socio",
            name="debe_cambiar_password",
            field=models.BooleanField(
                default=True, verbose_name="debe cambiar la contraseña"
            ),
        ),
    ]
