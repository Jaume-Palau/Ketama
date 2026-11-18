"""Perfil privado y acceso a las funciones de cuenta existentes."""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from geneticas.models import Genetica
from socios.models import Socio


class PerfilTests(TestCase):
    password = "Temporal-De-Prueba-8x!"
    password_nueva = "Personal-De-Prueba-9z!"

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="00125", password=cls.password)
        cls.socio = Socio.objects.create(
            usuario=cls.usuario, nombre_completo="Nombre del socio autenticado",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.otro = Socio.objects.create(
            usuario=User.objects.create_user(username="00126"),
            nombre_completo="Nombre privado de otro socio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.genetica = Genetica.objects.create(
            nombre="Genética ficticia", clasificacion=Genetica.Clasificacion.HIBRIDA,
            tipo_cultivo=Genetica.TipoCultivo.INTERIOR, descripcion="Datos ficticios.",
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse("socios:perfil")

    def test_muestra_solo_nombre_y_numero_del_socio_autenticado(self):
        response = self.client.get(self.url, {
            "socio": self.otro.pk, "numero_socio": self.otro.numero_socio,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "socios/perfil.html")
        self.assertEqual(response.context["nombre_completo"], self.socio.nombre_completo)
        self.assertEqual(response.context["numero_socio"], "00125")
        self.assertContains(response, self.socio.nombre_completo)
        self.assertContains(response, "00125")
        self.assertNotContains(response, self.otro.nombre_completo)
        self.assertNotContains(response, self.usuario.password)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.get(self.url + str(self.otro.pk) + "/").status_code, 404)

    def test_botones_reutilizan_cambio_de_password_y_logout_post_con_csrf(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'href="' + reverse("socios:cambiar_password") + '"')
        self.assertContains(response, 'action="' + reverse("socios:logout") + '"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "Cambiar contraseña")
        self.assertContains(response, "Cerrar sesión")
        self.assertEqual(self.client.get(reverse("socios:cambiar_password")).status_code, 200)

    def test_cambio_voluntario_conserva_sesion_y_redireccion_existente(self):
        self.client.get(self.url)
        response = self.client.post(reverse("socios:cambiar_password"), {
            "old_password": self.password,
            "new_password1": self.password_nueva,
            "new_password2": self.password_nueva,
        })
        self.assertRedirects(response, reverse("geneticas:catalogo"))
        self.usuario.refresh_from_db()
        self.socio.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.password_nueva))
        self.assertFalse(self.socio.debe_cambiar_password)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_cierre_de_sesion_requiere_csrf_y_funciona_desde_el_perfil(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        client.get(self.url)
        self.assertEqual(client.post(reverse("socios:logout")).status_code, 403)
        self.assertIn("_auth_user_id", client.session)
        response = client.post(reverse("socios:logout"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, reverse("socios:login"))
        self.assertNotIn("_auth_user_id", client.session)

    def test_navegacion_habilita_perfil_y_solo_marca_la_seccion_actual(self):
        for url in (
            self.url, reverse("geneticas:catalogo"),
            reverse("geneticas:detalle", args=[self.genetica.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'href="' + self.url + '"')
                self.assertNotContains(response, 'aria-disabled="true"')
                self.assertContains(response, 'href="' + reverse("comunicacion:avisos") + '"')
                if url == self.url:
                    self.assertContains(response, 'href="' + self.url + '" aria-current="page"')
                    self.assertNotContains(response, 'href="' + reverse("geneticas:catalogo") + '" aria-current=')
                else:
                    self.assertNotContains(response, 'href="' + self.url + '" aria-current=')

    def test_anonimo_no_puede_abrir_perfil(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))

    def test_caducado_y_cambio_obligatorio_conservan_restricciones(self):
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        self.assertRedirects(self.client.get(self.url), reverse("socios:caducado"))
        Socio.objects.filter(pk=self.socio.pk).update(debe_cambiar_password=True)
        self.assertRedirects(self.client.get(self.url), reverse("socios:cambiar_password"))

    def test_usuario_deshabilitado_no_puede_abrir_perfil(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))

    def test_administradores_y_usuarios_sin_perfil_no_pueden_entrar(self):
        for numero, permisos in (("201", {"is_staff": True}), ("202", {"is_superuser": True}), ("203", {})):
            usuario = User.objects.create_user(username=numero, **permisos)
            if permisos:
                Socio.objects.create(usuario=usuario, nombre_completo="Personal ficticio", estado=Socio.Estado.ACTIVO)
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_perfil_es_solo_consulta_y_rechaza_post(self):
        antes = list(Socio.objects.order_by("pk").values())
        response = self.client.post(self.url, {"nombre_completo": "Intento de edición", "socio": self.otro.pk})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(list(Socio.objects.order_by("pk").values()), antes)
