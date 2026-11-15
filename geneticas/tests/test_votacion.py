"""Envío de estrellas con cuentas y votos ficticios en la base de pruebas."""
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from geneticas.forms import ValoracionForm
from geneticas.models import Genetica, Valoracion
from socios.models import Socio


class VotacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="125")
        cls.socio = Socio.objects.create(
            usuario=cls.usuario, nombre_completo="Socio ficticio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.otro = Socio.objects.create(
            usuario=User.objects.create_user(username="126"), nombre_completo="Otro socio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        datos = {
            "clasificacion": Genetica.Clasificacion.HIBRIDA,
            "tipo_cultivo": Genetica.TipoCultivo.INTERIOR,
            "descripcion": "Genética para pruebas de votación.",
        }
        cls.genetica = Genetica.objects.create(nombre="Genética ficticia", **datos)
        cls.inactiva = Genetica.objects.create(nombre="Genética oculta", activo=False, **datos)
        cls.voto_otro = Valoracion.objects.create(
            socio=cls.otro, genetica=cls.genetica, puntuacion=3
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse("geneticas:valorar", args=[self.genetica.pk])

    def test_crear_voto_y_refrescar_agregaciones_con_confirmacion(self):
        response = self.client.post(self.url, {"puntuacion": "5"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu valoración se ha guardado.")
        self.assertContains(response, "Tu puntuación actual: 5 de 5.")
        voto = Valoracion.objects.get(socio=self.socio, genetica=self.genetica)
        self.assertEqual(voto.puntuacion, 5)
        genetica = response.context["genetica"]
        self.assertEqual(genetica.media_catalogo, 4)
        self.assertEqual(genetica.votos_catalogo, 2)
        self.assertEqual(genetica.mi_puntuacion, 5)
        self.assertEqual(response.context["distribucion"][0]["votos"], 1)
        self.assertEqual(response.context["form_valoracion"].initial["puntuacion"], 5)
        self.assertContains(response, 'value="5" required checked')

    def test_modificar_conserva_registro_fecha_y_numero_de_votos(self):
        self.client.post(self.url, {"puntuacion": "5"})
        anterior = Valoracion.objects.get(socio=self.socio)
        response = self.client.post(self.url, {"puntuacion": "1"}, follow=True)
        actualizado = Valoracion.objects.get(socio=self.socio)
        self.assertEqual(actualizado.pk, anterior.pk)
        self.assertEqual(actualizado.fecha, anterior.fecha)
        self.assertEqual(actualizado.puntuacion, 1)
        self.assertEqual(response.context["genetica"].votos_catalogo, 2)
        self.assertEqual(response.context["genetica"].media_catalogo, 2)
        self.assertEqual(response.context["distribucion"][0]["votos"], 0)
        self.assertEqual(response.context["distribucion"][-1]["votos"], 1)
        self.voto_otro.refresh_from_db()
        self.assertEqual(self.voto_otro.puntuacion, 3)
        # Refrescar el GET no repite el POST ni crea un voto nuevo.
        self.client.get(response.redirect_chain[-1][0])
        self.assertEqual(Valoracion.objects.count(), 2)

    def test_repetir_envio_no_crea_duplicados(self):
        for _ in range(2):
            self.assertEqual(self.client.post(self.url, {"puntuacion": "4"}).status_code, 302)
        self.assertEqual(Valoracion.objects.filter(socio=self.socio, genetica=self.genetica).count(), 1)

    def test_puntuaciones_invalidas_rechazadas_sin_crear_ni_modificar(self):
        for puntuacion in (None, "", "0", "6", "-1", "2.5", "3.0", "texto"):
            with self.subTest(puntuacion=puntuacion):
                data = {} if puntuacion is None else {"puntuacion": puntuacion}
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["form_valoracion"].errors)
                self.assertEqual(Valoracion.objects.count(), 1)
        self.client.post(self.url, {"puntuacion": "4"})
        response = self.client.post(self.url, {"puntuacion": "0"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Valoracion.objects.get(socio=self.socio).puntuacion, 4)

    def test_no_se_puede_votar_en_nombre_de_otro_o_cambiar_genetica_por_post(self):
        response = self.client.post(self.url, {
            "puntuacion": "5", "socio": self.otro.pk, "genetica": self.inactiva.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Valoracion.objects.get(socio=self.socio).genetica_id, self.genetica.pk)
        self.voto_otro.refresh_from_db()
        self.assertEqual(self.voto_otro.puntuacion, 3)
        self.assertFalse(Valoracion.objects.filter(genetica=self.inactiva).exists())

    def test_anonimos_caducados_y_cambio_pendiente_no_pueden_enviar(self):
        self.client.logout()
        response = self.client.post(self.url, {"puntuacion": "5"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))
        self.client.force_login(self.usuario)
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        self.assertRedirects(
            self.client.post(self.url, {"puntuacion": "5"}), reverse("socios:caducado")
        )
        Socio.objects.filter(pk=self.socio.pk).update(
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=True
        )
        self.assertRedirects(
            self.client.post(self.url, {"puntuacion": "5"}), reverse("socios:cambiar_password")
        )
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_cuenta_deshabilitada_no_puede_enviar(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)
        response = self.client.post(self.url, {"puntuacion": "5"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_personal_admin_y_usuarios_sin_perfil_no_pueden_votar(self):
        for numero, permisos in (
            ("201", {"is_staff": True}), ("202", {"is_superuser": True}), ("203", {}),
        ):
            usuario = User.objects.create_user(username=numero, **permisos)
            if permisos:
                Socio.objects.create(usuario=usuario, nombre_completo="Personal ficticio", estado=Socio.Estado.ACTIVO)
            self.client.force_login(usuario)
            self.assertEqual(self.client.post(self.url, {"puntuacion": "5"}).status_code, 403)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_revalidacion_si_caduca_entre_middleware_y_guardado(self):
        validar = ValoracionForm.is_valid

        def caducar_tras_validar(formulario):
            valido = validar(formulario)
            Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
            return valido

        with patch.object(ValoracionForm, "is_valid", caducar_tras_validar):
            response = self.client.post(self.url, {"puntuacion": "5"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_csrf_obligatorio_y_token_valido_permite_guardar(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        client.get(reverse("geneticas:detalle", args=[self.genetica.pk]))
        self.assertEqual(client.post(self.url, {"puntuacion": "5"}).status_code, 403)
        self.assertEqual(Valoracion.objects.count(), 1)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(self.url, {
            "puntuacion": "5", "csrfmiddlewaretoken": token,
        }).status_code, 302)
        self.assertEqual(Valoracion.objects.get(socio=self.socio).puntuacion, 5)

    def test_genetica_inactiva_inexistente_y_metodo_get_no_admitidos(self):
        for pk in (self.inactiva.pk, 9999999):
            self.assertEqual(self.client.post(reverse("geneticas:valorar", args=[pk]), {"puntuacion": "5"}).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Valoracion.objects.count(), 1)

    def test_retorno_conserva_filtros_sin_admitir_destinos_externos(self):
        response = self.client.post(self.url + "?q=prueba&clasificacion=hibrida&orden=precio_desc&next=https://example.com", {"puntuacion": "4"})
        retorno = urlsplit(response.url)
        self.assertEqual(retorno.path, reverse("geneticas:detalle", args=[self.genetica.pk]))
        self.assertEqual(retorno.netloc, "")
        self.assertEqual(retorno.fragment, "tu-valoracion")
        self.assertEqual(parse_qs(retorno.query), {
            "q": ["prueba"], "clasificacion": ["hibrida"], "orden": ["precio_desc"],
        })
