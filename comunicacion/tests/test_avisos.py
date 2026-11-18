"""Avisos publicados: validación, lectura privada, navegación y administración."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from comunicacion.models import Aviso
from geneticas.models import Genetica
from socios.models import Socio


class AvisoModeloTests(SimpleTestCase):
    def test_titulo_y_mensaje_obligatorios_y_borrador_por_defecto(self):
        aviso = Aviso(titulo="Aviso ficticio", mensaje="Mensaje ficticio")
        aviso.full_clean()
        self.assertFalse(aviso.activo)
        self.assertEqual(str(aviso), "Aviso ficticio")
        for campo in ("titulo", "mensaje"):
            with self.subTest(campo=campo):
                datos = {"titulo": "Aviso ficticio", "mensaje": "Mensaje ficticio", campo: ""}
                with self.assertRaises(ValidationError) as error:
                    Aviso(**datos).full_clean()
                self.assertIn(campo, error.exception.message_dict)


class AvisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="125")
        cls.socio = Socio.objects.create(
            usuario=cls.usuario, nombre_completo="Socio ficticio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.reciente = Aviso.objects.create(
            titulo="Comunicado reciente", mensaje="Primera línea.\nSegunda línea.", activo=True
        )
        cls.antiguo = Aviso.objects.create(titulo="Comunicado anterior", mensaje="Contenido anterior", activo=True)
        cls.oculto = Aviso.objects.create(titulo="Borrador oculto", mensaje="Contenido no publicado")
        Aviso.objects.filter(pk=cls.antiguo.pk).update(fecha_creacion=timezone.now() - timedelta(days=2))
        cls.genetica = Genetica.objects.create(
            nombre="Genética ficticia", clasificacion=Genetica.Clasificacion.HIBRIDA,
            tipo_cultivo=Genetica.TipoCultivo.INTERIOR, descripcion="Prueba de navegación.",
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse("comunicacion:avisos")

    def test_solo_publicados_del_mas_reciente_al_mas_antiguo(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "comunicacion/avisos.html")
        self.assertEqual([aviso.pk for aviso in response.context["avisos"]], [self.reciente.pk, self.antiguo.pk])
        self.assertContains(response, "Comunicado reciente")
        self.assertContains(response, "Primera línea.<br>Segunda línea.")
        self.assertContains(response, "<time ", count=2)
        self.assertNotContains(response, self.oculto.titulo)
        self.assertNotContains(response, self.oculto.mensaje)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_estado_vacio_si_no_hay_avisos_publicados(self):
        Aviso.objects.all().update(activo=False)
        response = self.client.get(self.url)
        self.assertContains(response, "Todavía no hay avisos")
        self.assertNotContains(response, 'class="aviso-tarjeta"')

    def test_contenido_se_escapa_y_no_ejecuta_html(self):
        Aviso.objects.filter(pk=self.reciente.pk).update(
            titulo="<b>Título</b>", mensaje="<script>alert(1)</script>"
        )
        response = self.client.get(self.url)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<b>Título</b>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_lectura_no_modifica_avisos_y_post_no_permitido(self):
        antes = list(Aviso.objects.order_by("pk").values())
        self.client.get(self.url)
        self.assertEqual(self.client.post(self.url, {"titulo": "Intento"}).status_code, 405)
        self.assertEqual(list(Aviso.objects.order_by("pk").values()), antes)

    def test_navegacion_habilitada_en_todas_las_secciones(self):
        for url in (
            self.url, reverse("socios:perfil"), reverse("geneticas:catalogo"),
            reverse("geneticas:detalle", args=[self.genetica.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'href="' + self.url + '"')
                self.assertNotContains(response, 'aria-disabled="true"')
                if url == self.url:
                    self.assertContains(response, 'href="' + self.url + '" aria-current="page"')
                else:
                    self.assertNotContains(response, 'href="' + self.url + '" aria-current=')

    def test_anonimo_caducado_y_cambio_pendiente_no_acceden(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))
        self.client.force_login(self.usuario)
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        self.assertRedirects(self.client.get(self.url), reverse("socios:caducado"))
        Socio.objects.filter(pk=self.socio.pk).update(debe_cambiar_password=True)
        self.assertRedirects(self.client.get(self.url), reverse("socios:cambiar_password"))

    def test_cuenta_deshabilitada_no_accede(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))

    def test_personal_y_usuarios_sin_perfil_no_acceden_al_espacio_de_socios(self):
        for numero, permisos in (("201", {"is_staff": True}), ("202", {"is_superuser": True}), ("203", {})):
            usuario = User.objects.create_user(username=numero, **permisos)
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_admin_crea_edita_oculta_y_elimina_avisos(self):
        administrador = User.objects.create_superuser(username="admin-prueba")
        self.client.force_login(administrador)
        listado = self.client.get(reverse("admin:comunicacion_aviso_changelist"))
        self.assertContains(listado, 'name="form-0-activo"')
        response = self.client.post(reverse("admin:comunicacion_aviso_add"), {
            "titulo": "Nuevo aviso ficticio", "mensaje": "Contenido ficticio", "activo": "on", "_save": "Guardar",
        })
        self.assertEqual(response.status_code, 302)
        aviso = Aviso.objects.get(titulo="Nuevo aviso ficticio")
        self.assertTrue(aviso.activo)
        self.assertIsNotNone(aviso.fecha_creacion)
        fecha = aviso.fecha_creacion
        response = self.client.post(reverse("admin:comunicacion_aviso_change", args=[aviso.pk]), {
            "titulo": "Aviso editado", "mensaje": "Contenido editado", "_save": "Guardar",
        })
        self.assertEqual(response.status_code, 302)
        aviso.refresh_from_db()
        self.assertFalse(aviso.activo)
        self.assertEqual(aviso.mensaje, "Contenido editado")
        self.assertEqual(aviso.fecha_creacion, fecha)
        response = self.client.post(reverse("admin:comunicacion_aviso_delete", args=[aviso.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Aviso.objects.filter(pk=aviso.pk).exists())
