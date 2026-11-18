"""El componente se dibuja con geometría explícita, incluso sin cargar CSS."""
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from geneticas.precios import segmentos_nivel_precio
from geneticas.tests.componentes import BarrasPrecioParser


class IndicadorPrecioTests(SimpleTestCase):
    def test_cada_nivel_genera_cinco_segmentos_visibles_y_relleno_correcto(self):
        for nivel in range(1, 6):
            with self.subTest(nivel=nivel):
                html = render_to_string("geneticas/_nivel_precio.html", {
                    "nivel": nivel, "segmentos": segmentos_nivel_precio(nivel),
                })
                barras = BarrasPrecioParser(html).barras
                self.assertEqual(len(barras), 1)
                barra = barras[0]
                self.assertEqual(barra["atributos"]["aria-label"], f"Nivel de precio: {nivel} de 5")
                self.assertGreater(float(barra["atributos"]["width"]), 0)
                self.assertGreater(float(barra["atributos"]["height"]), 0)
                segmentos = barra["segmentos"]
                self.assertEqual(len(segmentos), 5)
                self.assertEqual(sum("relleno" in s["class"].split() for s in segmentos), nivel)
                self.assertEqual(sum(s["fill"] == "#aeef56" for s in segmentos), nivel)
                self.assertEqual(sum(s["fill"] == "#35403d" for s in segmentos), 5 - nivel)
                for indice, segmento in enumerate(segmentos):
                    self.assertGreater(float(segmento["width"]), 0)
                    self.assertGreater(float(segmento["height"]), 0)
                    self.assertGreater(float(segmento["rx"]), 0)
                    self.assertEqual(segmento["fill"], "#aeef56" if indice < nivel else "#35403d")
                    if indice:
                        anterior = segmentos[indice - 1]
                        self.assertGreater(float(segmento["x"]), float(anterior["x"]) + float(anterior["width"]))

    def test_precio_no_informado_muestra_aviso_y_no_una_barra_vacia(self):
        html = render_to_string("geneticas/_nivel_precio.html", {
            "nivel": None, "segmentos": segmentos_nivel_precio(None),
        })
        self.assertIn("Nivel no disponible", html)
        self.assertEqual(BarrasPrecioParser(html).barras, [])
