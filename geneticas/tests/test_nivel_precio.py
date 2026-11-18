"""Límites decimales, privacidad de las vistas y precio real reservado al Admin."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from geneticas.models import Genetica
from geneticas.precios import nivel_precio_sql
from geneticas.tests.componentes import BarrasPrecioParser
from socios.models import Socio


class NivelPrecioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(username="125")
        Socio.objects.create(
            usuario=cls.usuario, nombre_completo="Socio ficticio",
            estado=Socio.Estado.ACTIVO, debe_cambiar_password=False,
        )
        cls.genetica = cls.crear_genetica("Genética ficticia", Decimal("4321.67"))

    @classmethod
    def crear_genetica(cls, nombre, precio):
        return Genetica.objects.create(
            nombre=nombre, precio=precio, clasificacion=Genetica.Clasificacion.HIBRIDA,
            tipo_cultivo=Genetica.TipoCultivo.INTERIOR, descripcion="Descripción ficticia.",
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_cinco_niveles_y_limites_exactos(self):
        casos = (
            (None, None), ("0.00", 1), ("5.99", 1), ("6.00", 1),
            ("6.01", 2), ("6.50", 2), ("7.49", 2), ("7.50", 2),
            ("7.51", 3), ("8.99", 3), ("9.00", 3),
            ("9.01", 4), ("10.49", 4), ("10.50", 4),
            ("10.51", 5), ("999999.99", 5),
        )
        for valor, esperado in casos:
            with self.subTest(precio=valor):
                precio = Decimal(valor) if valor is not None else None
                genetica = self.crear_genetica("Frontera ficticia", precio)
                nivel = Genetica.objects.filter(pk=genetica.pk).annotate(
                    nivel=nivel_precio_sql()
                ).values_list("nivel", flat=True).get()
                self.assertEqual(nivel, esperado)

    def test_html_y_datos_presentacion_no_contienen_importes_ni_unidades(self):
        for url in (
            reverse("geneticas:catalogo"),
            reverse("geneticas:detalle", args=[self.genetica.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                for prohibido in (
                    "4321.67", "4321,67", "4.321,67", "4,321.67", "€",
                    "&euro;", "&#8364;", 'data-precio=', '"precio":', "€/g", "€/ud.",
                ):
                    self.assertNotContains(response, prohibido)
                self.assertContains(response, 'aria-label="Nivel de precio: 5 de 5"')
                self.assertContains(response, 'class="nivel-precio-segmento relleno"', count=5)
                datos = response.context["geneticas"] if url == reverse("geneticas:catalogo") else [response.context["genetica"]]
                for genetica in datos:
                    self.assertFalse(hasattr(genetica, "precio"))
                    self.assertFalse(hasattr(genetica, "unidad_precio"))
                    self.assertEqual(genetica.nivel_precio, 5)

    def test_barra_muestra_cinco_segmentos_y_rellena_solo_el_nivel(self):
        for precio, esperado in (("6.00", 1), ("6.50", 2), ("9.00", 3), ("10.50", 4), ("10.51", 5)):
            nombre = f"Barra {esperado}"
            genetica = self.crear_genetica(nombre, Decimal(precio))
            for url in (
                reverse("geneticas:catalogo"),
                reverse("geneticas:detalle", args=[genetica.pk]),
            ):
                with self.subTest(nivel=esperado, url=url):
                    filtros = {"q": nombre} if url == reverse("geneticas:catalogo") else {}
                    response = self.client.get(url, filtros)
                    self.assertContains(response, 'class="nivel-precio-segmento', count=5)
                    self.assertContains(response, 'class="nivel-precio-segmento relleno"', count=esperado)
                    barras = BarrasPrecioParser(response.content.decode()).barras
                    self.assertEqual(len(barras), 1)
                    segmentos = barras[0]["segmentos"]
                    self.assertEqual(len(segmentos), 5)
                    self.assertEqual(sum(s["fill"] == "#aeef56" for s in segmentos), esperado)
                    self.assertEqual(sum(s["fill"] == "#35403d" for s in segmentos), 5 - esperado)
                    self.assertContains(response, "css/nivel_precio.css?v=2")
                    datos = response.context["geneticas"][0] if filtros else response.context["genetica"]
                    self.assertEqual(datos.nivel_precio, esperado)
                    self.assertEqual(len(datos.segmentos_precio), 5)
                    self.assertNotContains(response, precio)

    def test_precio_desconocido_no_se_confunde_con_nivel_uno(self):
        genetica = self.crear_genetica("Sin precio ficticio", None)
        for url in (
            reverse("geneticas:catalogo") + "?q=Sin+precio",
            reverse("geneticas:detalle", args=[genetica.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, "Nivel no disponible")
            self.assertNotContains(response, 'class="nivel-precio-segmento')

    def test_formulario_de_votacion_invalido_tampoco_expone_el_importe(self):
        response = self.client.post(
            reverse("geneticas:valorar", args=[self.genetica.pk]), {"puntuacion": "0"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "4321", status_code=400)
        self.assertNotContains(response, "€", status_code=400)
        self.assertFalse(hasattr(response.context["genetica"], "precio"))

    def test_ordenacion_usa_importes_reales_incluso_dentro_del_mismo_nivel(self):
        menor = self.crear_genetica("B orden", Decimal("7.80"))
        mayor = self.crear_genetica("A orden", Decimal("8.90"))
        nulo = self.crear_genetica("C orden", None)
        for orden, esperado in (
            ("precio_asc", [menor.pk, mayor.pk, nulo.pk]),
            ("precio_desc", [mayor.pk, menor.pk, nulo.pk]),
        ):
            response = self.client.get(reverse("geneticas:catalogo"), {"q": "orden", "orden": orden})
            self.assertEqual([g.pk for g in response.context["geneticas"]], esperado)

    def test_precio_se_conserva_en_base_de_datos_y_formulario_admin(self):
        administrador = User.objects.create_superuser(username="admin-prueba")
        self.client.force_login(administrador)
        response = self.client.get(reverse("admin:geneticas_genetica_change", args=[self.genetica.pk]))
        self.assertEqual(response.status_code, 200)
        formulario = response.context["adminform"].form
        self.assertIn("precio", formulario.fields)
        self.assertEqual(formulario.initial["precio"], Decimal("4321.67"))
        self.genetica.refresh_from_db()
        self.assertEqual(self.genetica.precio, Decimal("4321.67"))
