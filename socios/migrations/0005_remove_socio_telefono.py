from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("socios", "0004_socio_estado")]

    operations = [
        migrations.RemoveField(
            model_name="socio",
            name="telefono",
        ),
    ]
