"""Validación del modelo sin consultas ni migraciones de base de datos."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from geneticas.models import Genetica


class GeneticaTests(SimpleTestCase):
    def genetica(self, **cambios):
        datos = {
            "nombre": "Genética de prueba",
            "clasificacion": Genetica.Clasificacion.HIBRIDA,
            "thc": Decimal("18.50"),
            "tipo_cultivo": Genetica.TipoCultivo.INTERIOR,
            "descripcion": "Descripción ficticia para pruebas.",
        }
        datos.update(cambios)
        return Genetica(**datos)

    def validar(self, genetica):
        # La restricción SQL se aplicará al migrar. Aquí se prueban los
        # validadores de campos sin acceder a la base de datos.
        genetica.full_clean(validate_constraints=False)

    def test_ficha_valida_activa_por_defecto(self):
        genetica = self.genetica()
        self.validar(genetica)
        self.assertTrue(genetica.activo)
        self.assertEqual(str(genetica), "Genética de prueba")

    def test_nombre_obligatorio(self):
        with self.assertRaises(ValidationError) as error:
            self.validar(self.genetica(nombre=""))
        self.assertIn("nombre", error.exception.message_dict)

    def test_imagen_opcional_y_url_valida(self):
        for imagen in ("", "https://example.com/genetica.jpg"):
            with self.subTest(imagen=imagen):
                self.validar(self.genetica(imagen=imagen))
        with self.assertRaises(ValidationError) as error:
            self.validar(self.genetica(imagen="imagen.jpg"))
        self.assertIn("imagen", error.exception.message_dict)

    def test_thc_admite_limites_decimales_y_desconocido(self):
        for thc in (Decimal("0"), Decimal("100"), Decimal("18.50"), None):
            with self.subTest(thc=thc):
                self.validar(self.genetica(thc=thc))

    def test_thc_rechaza_fuera_de_rango_y_precision_excesiva(self):
        for thc in (Decimal("-0.01"), Decimal("100.01"), Decimal("18.555")):
            with self.subTest(thc=thc):
                with self.assertRaises(ValidationError) as error:
                    self.validar(self.genetica(thc=thc))
                self.assertIn("thc", error.exception.message_dict)

    def test_selecciones_admitidas(self):
        for clasificacion in Genetica.Clasificacion:
            for tipo in Genetica.TipoCultivo:
                with self.subTest(clasificacion=clasificacion, tipo=tipo):
                    self.validar(self.genetica(clasificacion=clasificacion, tipo_cultivo=tipo))

    def test_selecciones_rechazan_valores_desconocidos_o_multiples(self):
        for campo, valor in (
            ("clasificacion", "otra"),
            ("clasificacion", "sativa,indica"),
            ("tipo_cultivo", "otro"),
            ("tipo_cultivo", "interior,exterior"),
        ):
            with self.subTest(campo=campo, valor=valor):
                with self.assertRaises(ValidationError) as error:
                    self.validar(self.genetica(**{campo: valor}))
                self.assertIn(campo, error.exception.message_dict)

    def test_se_puede_desactivar(self):
        genetica = self.genetica(activo=False)
        self.validar(genetica)
        self.assertFalse(genetica.activo)
