"""Reglas y restricciones de valoraciones en una base PostgreSQL de pruebas."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from geneticas.models import Genetica, Valoracion
from socios.models import Socio


class ValoracionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.socio = Socio.objects.create(
            usuario=User.objects.create_user(username="125"),
            nombre_completo="Socio ficticio", estado=Socio.Estado.ACTIVO,
        )
        cls.otro_socio = Socio.objects.create(
            usuario=User.objects.create_user(username="126"),
            nombre_completo="Otro socio ficticio", estado=Socio.Estado.ACTIVO,
        )
        cls.genetica = Genetica.objects.create(
            nombre="Genética ficticia", clasificacion=Genetica.Clasificacion.HIBRIDA,
            tipo_cultivo=Genetica.TipoCultivo.INTERIOR, descripcion="Prueba de valoración.",
        )

    def valorar(self, puntuacion=3, **cambios):
        datos = {"socio": self.socio, "genetica": self.genetica, "puntuacion": puntuacion}
        datos.update(cambios)
        return Valoracion.objects.create(**datos)

    def insertar_sin_validacion(self, puntuacion):
        # Solo en BD de pruebas: comprueba que PostgreSQL protege el dato incluso
        # si una escritura externa elude todos los validadores de Python.
        tabla = connection.ops.quote_name(Valoracion._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {tabla} (socio_id, genetica_id, puntuacion, fecha) VALUES (%s, %s, %s, %s)",
                [self.socio.pk, self.genetica.pk, puntuacion, timezone.now()],
            )

    def test_creacion_y_limites_incluidos(self):
        antes = timezone.now()
        voto = self.valorar(1)
        self.assertGreaterEqual(voto.fecha, antes)
        voto.puntuacion = 5
        voto.save()
        voto.refresh_from_db()
        self.assertEqual(voto.puntuacion, 5)

    def test_save_rechaza_cero_fuera_de_rango_fracciones_y_nulos(self):
        for puntuacion in (0, -1, 6, None, 2.5, Decimal("3.5")):
            with self.subTest(puntuacion=puntuacion):
                with self.assertRaises(ValidationError):
                    self.valorar(puntuacion)
        self.assertEqual(Valoracion.objects.count(), 0)

    def test_unicidad_en_validacion_y_postgresql(self):
        self.valorar(3)
        with self.assertRaises(ValidationError):
            self.valorar(4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.insertar_sin_validacion(4)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_postgresql_rechaza_puntuaciones_invalidas_sin_validacion_python(self):
        for puntuacion in (0, 6):
            with self.subTest(puntuacion=puntuacion):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.insertar_sin_validacion(puntuacion)
        self.assertEqual(Valoracion.objects.count(), 0)

    def test_modificar_voto_no_crea_otro_ni_cambia_fecha(self):
        voto = self.valorar(2)
        fecha = voto.fecha
        voto.puntuacion = 5
        voto.save(update_fields=["puntuacion"])
        voto.refresh_from_db()
        self.assertEqual(voto.puntuacion, 5)
        self.assertEqual(voto.fecha, fecha)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_update_or_create_modifica_el_voto_existente(self):
        voto = self.valorar(2)
        actualizado, creado = Valoracion.objects.update_or_create(
            socio=self.socio, genetica=self.genetica, defaults={"puntuacion": 4}
        )
        self.assertFalse(creado)
        self.assertEqual(actualizado.pk, voto.pk)
        self.assertEqual(actualizado.puntuacion, 4)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_caducado_no_puede_crear_ni_modificar_y_conserva_su_voto(self):
        voto = self.valorar(3)
        # Estado del objeto relacionado en memoria desactualizado deliberadamente.
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        voto.puntuacion = 5
        with self.assertRaises(ValidationError):
            voto.full_clean()
        with self.assertRaises(ValidationError):
            voto.save(update_fields=["puntuacion"])
        with self.assertRaises(ValidationError):
            self.valorar(4)
        voto.refresh_from_db()
        self.assertEqual(voto.puntuacion, 3)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_cuenta_deshabilitada_no_puede_valorar(self):
        User.objects.filter(pk=self.socio.usuario_id).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.valorar(3)

    def test_no_se_puede_eludir_validacion_reasignando_el_socio_en_save_parcial(self):
        voto = self.valorar(3)
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        voto.socio = self.otro_socio
        voto.puntuacion = 5
        with self.assertRaises(ValidationError):
            voto.save(update_fields=["puntuacion"])
        voto.refresh_from_db()
        self.assertEqual(voto.socio_id, self.socio.pk)
        self.assertEqual(voto.puntuacion, 3)

    def test_operaciones_masivas_no_eluden_validacion(self):
        voto = self.valorar(3)
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        with self.assertRaises(TypeError):
            Valoracion.objects.filter(pk=voto.pk).update(puntuacion=5)
        with self.assertRaises(TypeError):
            Valoracion._base_manager.filter(pk=voto.pk).update(puntuacion=5)
        voto.puntuacion = 5
        with self.assertRaises(TypeError):
            Valoracion.objects.bulk_update([voto], ["puntuacion"])
        with self.assertRaises(TypeError):
            Valoracion.objects.bulk_create([
                Valoracion(socio=self.socio, genetica=self.genetica, puntuacion=5)
            ])
        voto.refresh_from_db()
        self.assertEqual(voto.puntuacion, 3)

    def test_sin_valoraciones_media_cero_y_ningun_registro(self):
        self.assertEqual(self.genetica.resumen_valoraciones(), {"media": 0, "numero": 0})
        self.assertEqual(self.genetica.puntuacion_media, 0)
        self.assertEqual(self.genetica.numero_valoraciones, 0)
        self.assertEqual(Valoracion.objects.count(), 0)

    def test_agregaciones_reflejan_cambios_e_incluyen_valoraciones_historicas(self):
        voto = self.valorar(1)
        self.valorar(4, socio=self.otro_socio)
        with self.assertNumQueries(1):
            self.assertEqual(self.genetica.resumen_valoraciones(), {"media": 2.5, "numero": 2})
        voto.puntuacion = 2
        voto.save()
        self.genetica.activo = False
        self.genetica.save(update_fields=["activo"])
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        self.assertEqual(self.genetica.puntuacion_media, 3)
        self.assertEqual(self.genetica.numero_valoraciones, 2)
        self.assertEqual(Valoracion.objects.count(), 2)

    def test_admin_permite_consultar_sin_alterar_valoraciones(self):
        voto = self.valorar(4)
        administrador = User.objects.create_superuser(username="admin-prueba")
        self.client.force_login(administrador)
        url = reverse("admin:geneticas_valoracion_change", args=[voto.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"puntuacion": 1}).status_code, 403)
        voto.refresh_from_db()
        self.assertEqual(voto.puntuacion, 4)
