"""Ficha privada: datos reales del fixture, permisos y navegación de retorno."""
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from geneticas.models import Genetica, Valoracion
from geneticas.views import detalle
from socios.models import Socio


class DetalleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="125")
        cls.socio = Socio.objects.create(
            usuario=cls.usuario, nombre_completo="Socio ficticio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        otro = Socio.objects.create(
            usuario=User.objects.create_user(username="126"),
            nombre_completo="Otro socio ficticio", estado=Socio.Estado.ACTIVO,
        )
        datos = {
            "clasificacion": Genetica.Clasificacion.INDICA,
            "tipo_cultivo": Genetica.TipoCultivo.INTERIOR,
            "descripcion": "Descripción ficticia.\nSegunda línea.",
        }
        cls.genetica = Genetica.objects.create(
            nombre="Purple ficticia", imagen="https://example.com/foto.jpg",
            precio=Decimal("8"), thc=Decimal("22"), cbd=Decimal("0.60"), **datos,
        )
        cls.sin_datos = Genetica.objects.create(nombre="Sin datos opcionales", **datos)
        cls.inactiva = Genetica.objects.create(nombre="Genética oculta", activo=False, **datos)
        Valoracion.objects.create(socio=cls.socio, genetica=cls.genetica, puntuacion=5)
        Valoracion.objects.create(socio=otro, genetica=cls.genetica, puntuacion=3)

    def setUp(self):
        self.client.force_login(self.usuario)

    def url(self, genetica=None):
        return reverse("geneticas:detalle", args=[(genetica or self.genetica).pk])

    def test_ficha_muestra_datos_agregaciones_y_una_sola_foto(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "geneticas/detalle.html")
        for texto in ("Purple ficticia", "Índica", "8,00", "€/g", "22", "0,60", "THC", "CBD", "4,0", "2 valoraciones"):
            # floatformat -2 elimina ceros solo en enteros; conserva 0,60.
            self.assertContains(response, texto)
        self.assertContains(response, "Descripción ficticia.<br>Segunda línea.")
        self.assertContains(response, '<img ', count=1)
        genetica = response.context["genetica"]
        self.assertEqual(genetica.media_catalogo, 4)
        self.assertEqual(genetica.votos_catalogo, 2)
        self.assertEqual(genetica.mi_puntuacion, 5)
        self.assertEqual(response.context["distribucion"], [
            {"puntuacion": 5, "votos": 1, "porcentaje": 50},
            {"puntuacion": 4, "votos": 0, "porcentaje": 0},
            {"puntuacion": 3, "votos": 1, "porcentaje": 50},
            {"puntuacion": 2, "votos": 0, "porcentaje": 0},
            {"puntuacion": 1, "votos": 0, "porcentaje": 0},
        ])

    def test_sin_datos_opcionales_no_inventa_valores(self):
        response = self.client.get(self.url(self.sin_datos))
        self.assertContains(response, "Imagen no disponible")
        self.assertContains(response, "Precio no disponible")
        self.assertContains(response, "No informado", count=2)
        self.assertContains(response, "Sin valoraciones")
        self.assertContains(response, "0 votos")
        self.assertContains(response, "Aún no has valorado esta genética.")
        self.assertNotContains(response, '<img ')
        self.assertIsNone(response.context["genetica"].mi_puntuacion)
        self.assertTrue(all(fila["porcentaje"] == 0 for fila in response.context["distribucion"]))

    def test_valores_cero_y_precio_por_unidad_se_respetan(self):
        Genetica.objects.filter(pk=self.sin_datos.pk).update(
            precio=0, unidad_precio=Genetica.UnidadPrecio.UNIDAD, thc=0, cbd=0
        )
        response = self.client.get(self.url(self.sin_datos))
        self.assertContains(response, "0,00")
        self.assertContains(response, "€/ud.")
        self.assertNotContains(response, "No informado")
        self.assertNotContains(response, "Precio no disponible")

    def test_genetica_inactiva_o_inexistente_devuelve_404(self):
        self.assertEqual(self.client.get(self.url(self.inactiva)).status_code, 404)
        self.assertEqual(self.client.get(reverse("geneticas:detalle", args=[9999999])).status_code, 404)

    def test_retorno_conserva_parametros_y_ancla_sin_admitir_urls_externas(self):
        response = self.client.get(self.url(), {
            "q": "Purple & prueba", "clasificacion": "indica", "orden": "precio_desc",
            "next": "https://example.com/externo", "volver": "//example.com/externo",
        })
        volver = urlsplit(response.context["volver_catalogo"])
        self.assertEqual(volver.netloc, "")
        self.assertEqual(volver.path, reverse("geneticas:catalogo"))
        self.assertEqual(volver.fragment, f"tarjeta-{self.genetica.pk}")
        self.assertEqual(parse_qs(volver.query), {
            "q": ["Purple & prueba"], "clasificacion": ["indica"], "orden": ["precio_desc"],
        })

    def test_tarjeta_completa_enlaza_a_ficha_con_los_filtros(self):
        response = self.client.get(reverse("geneticas:catalogo"), {
            "q": "Purple", "clasificacion": "indica", "orden": "precio_desc",
        })
        enlace = self.url() + "?q=Purple&amp;clasificacion=indica&amp;orden=precio_desc"
        self.assertContains(response, 'href="' + enlace + '"')
        self.assertContains(response, f'data-ficha-genetica="tarjeta-{self.genetica.pk}"')

    def test_valoraciones_son_solo_lectura_y_no_hay_secciones_ficticias(self):
        response = self.client.get(self.url())
        self.assertContains(response, "Tu puntuación actual: 5 de 5.")
        self.assertContains(response, "La votación y la edición estarán disponibles próximamente.")
        self.assertContains(response, 'aria-disabled="true"', count=2)
        self.assertNotContains(response, 'name="puntuacion"')
        self.assertNotContains(response, "Carrito")
        self.assertNotContains(response, ">Inicio<")
        self.assertEqual(self.client.post(self.url(), {"puntuacion": 1}).status_code, 405)
        self.assertEqual(Valoracion.objects.get(socio=self.socio).puntuacion, 5)

    def test_descripcion_se_escapa(self):
        Genetica.objects.filter(pk=self.genetica.pk).update(descripcion="<script>alert(1)</script>")
        response = self.client.get(self.url())
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_detalle_completo_se_renderiza_con_una_consulta(self):
        request = RequestFactory().get(self.url())
        request.user = self.usuario
        request.socio = self.socio
        with self.assertNumQueries(1):
            response = detalle(request, self.genetica.pk)
        self.assertEqual(response.status_code, 200)

    def test_permisos_se_aplican_tambien_en_acceso_directo(self):
        self.client.logout()
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))
        self.client.force_login(self.usuario)
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        self.assertRedirects(self.client.get(self.url()), reverse("socios:caducado"))
        Socio.objects.filter(pk=self.socio.pk).update(debe_cambiar_password=True)
        self.assertRedirects(self.client.get(self.url()), reverse("socios:cambiar_password"))

    def test_admin_no_accede_como_socio_y_respuesta_privada_no_se_cachea(self):
        self.assertIn("no-store", self.client.get(self.url()).headers["Cache-Control"])
        administrador = User.objects.create_superuser(username="admin-prueba")
        self.client.force_login(administrador)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
