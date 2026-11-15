"""Catálogo con datos ficticios; nunca modifica la base de desarrollo."""
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from geneticas.models import Genetica, Valoracion
from geneticas.views import catalogo
from socios.models import Socio


class CatalogoTests(TestCase):
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
            "tipo_cultivo": Genetica.TipoCultivo.INTERIOR,
            "descripcion": "Datos ficticios del catálogo.",
        }
        cls.sativa = Genetica.objects.create(
            nombre="Purple Haze", clasificacion=Genetica.Clasificacion.SATIVA,
            precio=Decimal("12"), **datos,
        )
        cls.indica = Genetica.objects.create(
            nombre="Índica ficticia", clasificacion=Genetica.Clasificacion.INDICA,
            precio=Decimal("8"), **datos,
        )
        cls.sin_datos = Genetica.objects.create(
            nombre="Híbrida sin datos", clasificacion=Genetica.Clasificacion.HIBRIDA, **datos,
        )
        cls.gratuita = Genetica.objects.create(
            nombre="Sin votos", clasificacion=Genetica.Clasificacion.SATIVA,
            precio=Decimal("0"), **datos,
        )
        cls.por_unidad = Genetica.objects.create(
            nombre="Por unidad", clasificacion=Genetica.Clasificacion.HIBRIDA,
            precio=Decimal("20"), unidad_precio=Genetica.UnidadPrecio.UNIDAD,
            imagen="https://example.com/genetica.jpg", **datos,
        )
        cls.inactiva = Genetica.objects.create(
            nombre="Oculta", clasificacion=Genetica.Clasificacion.SATIVA,
            precio=Decimal("1"), activo=False, **datos,
        )
        Valoracion.objects.create(socio=cls.socio, genetica=cls.sativa, puntuacion=4)
        Valoracion.objects.create(socio=otro, genetica=cls.sativa, puntuacion=5)
        Valoracion.objects.create(socio=cls.socio, genetica=cls.indica, puntuacion=5)

    def setUp(self):
        self.client.force_login(self.usuario)

    def ids(self, response):
        return [genetica.pk for genetica in response.context["geneticas"]]

    def test_solo_activas_ordenadas_por_media_y_sin_votos_al_final(self):
        response = self.client.get(reverse("geneticas:catalogo"))
        ids = self.ids(response)
        self.assertEqual(ids[:2], [self.indica.pk, self.sativa.pk])
        self.assertEqual(set(ids[2:]), {self.sin_datos.pk, self.gratuita.pk, self.por_unidad.pk})
        self.assertNotIn(self.inactiva.pk, ids)
        self.assertContains(response, "4,5")
        self.assertContains(response, "(2)")
        self.assertNotContains(response, "Oculta")

    def test_busqueda_y_clasificacion_se_combinan(self):
        url = reverse("geneticas:catalogo")
        self.assertEqual(self.ids(self.client.get(url, {"q": " purple ", "clasificacion": "sativa"})), [self.sativa.pk])
        self.assertEqual(self.ids(self.client.get(url, {"q": "purple", "clasificacion": "indica"})), [])

    def test_orden_precio_en_ambos_sentidos_y_nulos_siempre_al_final(self):
        casos = {
            "precio_asc": [self.gratuita.pk, self.indica.pk, self.sativa.pk, self.por_unidad.pk, self.sin_datos.pk],
            "precio_desc": [self.por_unidad.pk, self.sativa.pk, self.indica.pk, self.gratuita.pk, self.sin_datos.pk],
        }
        for orden, esperado in casos.items():
            with self.subTest(orden=orden):
                self.assertEqual(self.ids(self.client.get(reverse("geneticas:catalogo"), {"orden": orden})), esperado)

    def test_filtros_conservan_busqueda_y_orden_y_formulario_conserva_clasificacion(self):
        response = self.client.get(reverse("geneticas:catalogo"), {
            "q": "Purple & Haze", "orden": "precio_desc", "clasificacion": "sativa",
        })
        for filtro in response.context["filtros"]:
            consulta = parse_qs(urlsplit(filtro["url"]).query)
            self.assertEqual(consulta["q"], ["Purple & Haze"])
            self.assertEqual(consulta["orden"], ["precio_desc"])
            self.assertEqual(consulta.get("clasificacion", [""]), [filtro["valor"]])
        self.assertContains(response, 'name="clasificacion" value="sativa"')

    def test_parametros_invalidos_utilizan_valores_seguros(self):
        response = self.client.get(reverse("geneticas:catalogo"), {
            "clasificacion": "no-existe", "orden": "precio;otra-cosa",
        })
        self.assertEqual(response.context["clasificacion"], "")
        self.assertEqual(response.context["orden"], "valoracion")
        self.assertEqual(self.ids(response)[:2], [self.indica.pk, self.sativa.pk])

    def test_datos_ausentes_cero_y_unidades_reales_se_muestran_correctamente(self):
        response = self.client.get(reverse("geneticas:catalogo"))
        self.assertContains(response, "Imagen no disponible")
        self.assertContains(response, "Precio no disponible")
        self.assertContains(response, "Sin valoraciones")
        self.assertContains(response, "0,00")
        self.assertContains(response, "€/g")
        self.assertContains(response, "€/ud.")
        self.assertContains(response, 'aria-disabled="true"', count=2)
        self.assertContains(response, 'action="' + reverse("socios:logout") + '"')

    def test_vacio_con_y_sin_filtros(self):
        response = self.client.get(reverse("geneticas:catalogo"), {"q": "Sin coincidencias"})
        self.assertContains(response, "No encontramos esas genéticas")
        Genetica.objects.all().update(activo=False)
        response = self.client.get(reverse("geneticas:catalogo"))
        self.assertContains(response, "El catálogo estará disponible pronto")

    def test_una_consulta_para_renderizar_catalogo_con_sus_agregaciones(self):
        request = RequestFactory().get(reverse("geneticas:catalogo"))
        request.user = self.usuario
        with self.assertNumQueries(1):
            response = catalogo(request)
        self.assertEqual(response.status_code, 200)

    def test_permisos_se_mantienen_para_urls_directas(self):
        url = reverse("geneticas:catalogo")
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))
        self.client.force_login(self.usuario)
        Socio.objects.filter(pk=self.socio.pk).update(estado=Socio.Estado.CADUCADO)
        self.assertRedirects(self.client.get(url), reverse("socios:caducado"))
        Socio.objects.filter(pk=self.socio.pk).update(debe_cambiar_password=True)
        self.assertRedirects(self.client.get(url), reverse("socios:cambiar_password"))

    def test_personal_no_puede_abrir_el_catalogo_y_sigue_pudiendo_usar_admin(self):
        administrador = User.objects.create_superuser(username="admin-prueba")
        self.client.force_login(administrador)
        self.assertEqual(self.client.get(reverse("geneticas:catalogo")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_catalogo_rechaza_post_y_no_almacena_respuesta_en_cache(self):
        url = reverse("geneticas:catalogo")
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertIn("no-store", self.client.get(url).headers["Cache-Control"])
