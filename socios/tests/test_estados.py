"""Permisos por estado: las cuotas no se representan con User.is_active."""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from socios.models import Socio


class EstadoSocioModeloTests(SimpleTestCase):
    def test_estado_inicial_restringido_y_validacion(self):
        socio = Socio(nombre_completo="Socio ficticio", telefono="")
        self.assertEqual(socio.estado, Socio.Estado.CADUCADO)
        socio.estado = "desconocido"
        with self.assertRaises(ValidationError) as error:
            socio.full_clean(exclude=["usuario"], validate_unique=False)
        self.assertIn("estado", error.exception.message_dict)


@override_settings(ROOT_URLCONF="socios.tests.urls_acceso")
class AccesoPorEstadoTests(TestCase):
    password = "Temporal-Solo-Pruebas-8!"
    password_nueva = "Personal-Solo-Pruebas-9!"
    aviso = "Tu cuota de socio está caducada. Contacta con el club para renovarla"

    def setUp(self):
        self.usuario = User.objects.create_user(username="125", password=self.password)
        self.socio = Socio.objects.create(
            usuario=self.usuario, nombre_completo="Socio de prueba",
            debe_cambiar_password=False,
        )

    def acceder(self):
        return self.client.post(reverse("socios:login"), {
            "username": "125", "password": self.password,
        })

    def test_caducado_puede_iniciar_sesion_y_solo_ve_aviso(self):
        self.assertRedirects(self.acceder(), reverse("socios:caducado"))
        response = self.client.get(reverse("socios:caducado"))
        self.assertContains(response, self.aviso)
        self.assertNotContains(response, self.socio.nombre_completo)
        self.assertIn("_auth_user_id", self.client.session)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_urls_directas_y_post_quedan_bloqueados(self):
        self.acceder()
        for nombre in ("socios:inicio", "geneticas:inicio", "geneticas:accion", "geneticas:login"):
            for metodo in (self.client.get, self.client.post):
                with self.subTest(nombre=nombre, metodo=metodo.__name__):
                    self.assertRedirects(
                        metodo(reverse(nombre)), reverse("socios:caducado")
                    )

    def test_cambio_password_es_obligatorio_antes_del_aviso(self):
        self.socio.debe_cambiar_password = True
        self.socio.save(update_fields=["debe_cambiar_password"])
        self.assertRedirects(self.acceder(), reverse("socios:cambiar_password"))
        for nombre in ("socios:inicio", "socios:caducado", "geneticas:inicio"):
            self.assertRedirects(
                self.client.get(reverse(nombre)), reverse("socios:cambiar_password")
            )
        response = self.client.post(reverse("socios:cambiar_password"), {
            "old_password": self.password,
            "new_password1": self.password_nueva,
            "new_password2": self.password_nueva,
        })
        self.assertRedirects(response, reverse("socios:caducado"))
        self.socio.refresh_from_db()
        self.assertFalse(self.socio.debe_cambiar_password)
        self.assertEqual(self.socio.estado, Socio.Estado.CADUCADO)
        self.assertIn("_auth_user_id", self.client.session)

    def test_renovacion_y_caducidad_se_aplican_a_sesion_existente(self):
        self.acceder()
        hash_anterior = self.usuario.password
        self.socio.estado = Socio.Estado.ACTIVO
        self.socio.save(update_fields=["estado"])
        self.assertEqual(self.client.get(reverse("socios:inicio")).status_code, 200)
        self.assertContains(self.client.get(reverse("geneticas:inicio")), "Funcionalidad privada")
        self.assertRedirects(
            self.client.get(reverse("socios:caducado")), reverse("socios:inicio")
        )
        self.socio.estado = Socio.Estado.CADUCADO
        self.socio.save(update_fields=["estado"])
        self.assertRedirects(
            self.client.get(reverse("geneticas:inicio")), reverse("socios:caducado")
        )
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        self.assertEqual(self.usuario.password, hash_anterior)

    def test_activo_sin_cambio_pendiente_entra_normalmente(self):
        self.socio.estado = Socio.Estado.ACTIVO
        self.socio.save(update_fields=["estado"])
        self.assertRedirects(self.acceder(), reverse("socios:inicio"))

    def test_caducado_puede_cerrar_sesion(self):
        self.acceder()
        self.assertRedirects(
            self.client.post(reverse("socios:logout")), reverse("socios:login")
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deshabilitado_no_puede_iniciar_sesion(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.assertEqual(self.acceder().status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_administrador_con_perfil_caducado_conserva_el_admin(self):
        usuario = User.objects.create_superuser(username="admin-prueba", password=self.password)
        Socio.objects.create(usuario=usuario, nombre_completo="Admin ficticio")
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_admin_permita_cambiar_estado_del_perfil(self):
        administrador = User.objects.create_superuser(username="admin-prueba", password=self.password)
        self.client.force_login(administrador)
        response = self.client.get(reverse("admin:auth_user_change", args=[self.usuario.pk]))
        self.assertContains(response, 'name="socio-0-estado"')
        hash_anterior = self.usuario.password
        response = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]), {
                "username": self.usuario.username,
                "is_active": "on",
                "date_joined_0": self.usuario.date_joined.date().isoformat(),
                "date_joined_1": self.usuario.date_joined.strftime("%H:%M:%S"),
                "socio-TOTAL_FORMS": "1",
                "socio-INITIAL_FORMS": "1",
                "socio-MIN_NUM_FORMS": "0",
                "socio-MAX_NUM_FORMS": "1",
                "socio-0-id": str(self.socio.pk),
                "socio-0-usuario": str(self.usuario.pk),
                "socio-0-nombre_completo": self.socio.nombre_completo,
                "socio-0-telefono": "",
                "socio-0-estado": Socio.Estado.ACTIVO,
                "_save": "Guardar",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.socio.refresh_from_db()
        self.usuario.refresh_from_db()
        self.assertEqual(self.socio.estado, Socio.Estado.ACTIVO)
        self.assertEqual(self.usuario.password, hash_anterior)
        self.assertTrue(self.usuario.is_active)

    def test_anonimo_no_puede_abrir_aviso_ni_catalogo(self):
        for nombre in ("socios:caducado", "geneticas:inicio"):
            response = self.client.get(reverse(nombre))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("socios:login")))
