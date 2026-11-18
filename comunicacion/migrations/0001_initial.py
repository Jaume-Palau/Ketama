from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Aviso",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                )),
                ("titulo", models.CharField(max_length=200, verbose_name="título")),
                ("mensaje", models.TextField(verbose_name="mensaje")),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("activo", models.BooleanField(default=False, verbose_name="publicado")),
            ],
            options={
                "verbose_name": "aviso", "verbose_name_plural": "avisos",
                "ordering": ["-fecha_creacion", "-pk"],
            },
        ),
    ]
