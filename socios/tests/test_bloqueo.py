"""Protección de ambos accesos con cuentas ficticias en la BD de pruebas."""
from datetime import timedelta
from unittest.mock import patch

from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from socios.models import Socio


class BloqueoAccesoTests(TestCase):
    password = "Temporal-De-Prueba-8x!"
    incorrecta = "Incorrecta-De-Prueba-9z!"

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="00125", password=cls.password)
        cls.socio = Socio.objects.create(
            usuario=cls.usuario, nombre_completo="Socio ficticio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.otro = User.objects.create_user(username="126", password=cls.password)
        Socio.objects.create(
            usuario=cls.otro, nombre_completo="Otro socio ficticio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.admin = User.objects.create_superuser(username="admin-prueba", password=cls.password)

    def acceder(self, *, usuario=None, password=None, admin=False, ip="192.0.2.1",
                client=None, instante=None, **headers):
        client = client or self.client
        url = reverse("admin:login" if admin else "socios:login")
        datos = {
            "username": usuario or self.usuario.username,
            "password": password or self.incorrecta,
        }
        instante = instante or timezone.now()
        with (
            patch("axes.handlers.proxy.now", return_value=instante),
            patch("django.utils.timezone.now", return_value=instante),
        ):
            return client.post(url, datos, REMOTE_ADDR=ip, **headers)

    def bloquear(self, *, usuario=None, admin=False, instante=None):
        for numero in range(1, 6):
            response = self.acceder(usuario=usuario, admin=admin, instante=instante)
            self.assertEqual(response.status_code, 429 if numero == 5 else 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        return response

    def test_quinto_fallo_bloquea_incluso_con_password_correcta(self):
        response = self.bloquear()
        intento = AccessAttempt.objects.get(username="00125")
        self.assertEqual(intento.failures_since_start, 5)
        self.assertTemplateUsed(response, "socios/bloqueo.html")
        self.assertContains(response, "15 minutos", status_code=429)
        self.assertContains(response, "css/login.css", status_code=429)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.acceder(password=self.password).status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_desbloqueo_a_los_quince_minutos_sin_prolongar_por_reintentos(self):
        inicio = timezone.now()
        self.bloquear(instante=inicio)
        original = AccessAttempt.objects.get(username=self.usuario.username)
        for minutos, password in ((10, self.incorrecta), (14, self.password)):
            response = self.acceder(
                instante=inicio + timedelta(minutes=minutos), password=password,
            )
            self.assertEqual(response.status_code, 429)
        actual = AccessAttempt.objects.get(pk=original.pk)
        self.assertEqual(actual.attempt_time, original.attempt_time)
        self.assertEqual(actual.failures_since_start, 5)
        self.assertEqual(self.acceder(
            instante=inicio + timedelta(minutes=15, seconds=1), password=self.password,
        ).status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_acceso_correcto_reinicia_contador(self):
        for _ in range(4):
            self.assertEqual(self.acceder().status_code, 200)
        self.assertEqual(self.acceder(password=self.password).status_code, 302)
        self.assertFalse(AccessAttempt.objects.filter(username=self.usuario.username).exists())
        self.client.post(reverse("socios:logout"))
        self.assertEqual(self.acceder().status_code, 200)
        self.assertEqual(AccessAttempt.objects.get(username=self.usuario.username).failures_since_start, 1)

    def test_otro_socio_en_la_misma_ip_puede_entrar(self):
        self.bloquear()
        response = self.acceder(usuario=self.otro.username, password=self.password, client=Client())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AccessAttempt.objects.filter(username=self.usuario.username).exists())

    def test_cambiar_ip_cliente_y_handler_no_evade_contador_compartido(self):
        for numero in range(1, 6):
            AxesProxyHandler.get_implementation(force=True)
            response = self.acceder(
                client=Client(), ip=f"192.0.2.{numero}",
                HTTP_USER_AGENT=f"Navegador ficticio {numero}",
            )
            self.assertEqual(response.status_code, 429 if numero == 5 else 200)
        self.assertEqual(settings.AXES_HANDLER, "axes.handlers.database.AxesDatabaseHandler")
        self.assertEqual(self.acceder(
            password=self.password, client=Client(), ip="198.51.100.1",
        ).status_code, 429)

    def test_admin_tambien_se_bloquea_y_no_bloquea_a_socios(self):
        response = self.bloquear(usuario=self.admin.username, admin=True)
        self.assertContains(response, reverse("admin:login"), status_code=429)
        self.assertEqual(self.acceder(
            usuario=self.admin.username, password=self.password, admin=True,
        ).status_code, 429)
        self.assertEqual(self.acceder(password=self.password, client=Client()).status_code, 302)

    def test_fallos_de_la_misma_cuenta_se_suman_entre_ambos_accesos(self):
        for numero in range(1, 6):
            response = self.acceder(admin=numero % 2 == 0)
            self.assertEqual(response.status_code, 429 if numero == 5 else 200)
        self.assertEqual(self.acceder(password=self.password).status_code, 429)
        self.assertEqual(self.acceder(password=self.password, admin=True).status_code, 429)

    def test_bloqueo_no_modifica_usuarios_perfiles_ni_passwords(self):
        usuarios = list(User.objects.order_by("pk").values())
        socios = list(Socio.objects.order_by("pk").values())
        self.bloquear()
        self.assertEqual(list(User.objects.order_by("pk").values()), usuarios)
        self.assertEqual(list(Socio.objects.order_by("pk").values()), socios)

    def test_cambio_obligatorio_y_permisos_se_conservan(self):
        self.socio.debe_cambiar_password = True
        self.socio.save(update_fields=["debe_cambiar_password"])
        response = self.acceder(password=self.password)
        self.assertEqual(response.url, reverse("socios:cambiar_password"))
        self.assertRedirects(self.client.get(reverse("geneticas:catalogo")), response.url)
        self.client.logout()
        self.socio.debe_cambiar_password = False
        self.socio.estado = Socio.Estado.CADUCADO
        self.socio.save(update_fields=["debe_cambiar_password", "estado"])
        response = self.acceder(password=self.password)
        self.assertEqual(response.url, reverse("socios:caducado"))
        self.client.logout()
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.assertEqual(self.acceder(password=self.password).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_no_entra_por_acceso_socios_y_socio_no_entra_en_admin(self):
        for usuario, admin in ((self.admin.username, False), (self.usuario.username, True)):
            response = self.acceder(usuario=usuario, password=self.password, admin=admin)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_respuesta_generica_para_usuario_inexistente_incluso_ajax(self):
        usuario = "cuenta-inexistente-ficticia"
        self.bloquear(usuario=usuario)
        response = self.acceder(usuario=usuario, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertContains(response, "Acceso temporalmente limitado", status_code=429)
        self.assertNotContains(response, usuario, status_code=429)
        self.assertNotContains(response, self.incorrecta, status_code=429)
        intento = AccessAttempt.objects.get(username=usuario)
        self.assertNotIn(self.incorrecta, intento.post_data)
        self.assertEqual(intento.ip_address, "0.0.0.0")

    def test_csrf_invalido_no_cuenta_como_fallo_de_credenciales(self):
        client = Client(enforce_csrf_checks=True)
        for admin in (False, True):
            self.assertEqual(self.acceder(client=client, admin=admin).status_code, 403)
        self.assertFalse(AccessAttempt.objects.exists())

    def test_admin_puede_desbloquear_sin_modificar_la_cuenta(self):
        self.bloquear()
        intento = AccessAttempt.objects.get(username=self.usuario.username)
        client = Client()
        client.force_login(self.admin)
        response = client.post(reverse("admin:axes_accessattempt_delete", args=[intento.pk]), {
            "post": "yes",
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AccessAttempt.objects.filter(username=self.usuario.username).exists())
        self.assertEqual(self.acceder(password=self.password).status_code, 302)
