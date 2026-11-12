"""Validación del perfil en altas del Admin, sin base de datos."""
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.test import SimpleTestCase

from socios.models import Socio


class PerfilSocioAdminTests(SimpleTestCase):
    def formset(self, nombre_completo="", telefono=""):
        perfil_formset = inlineformset_factory(
            User,
            Socio,
            fields=("nombre_completo", "telefono"),
            extra=1,
            max_num=1,
            can_delete=False,
        )
        return perfil_formset(
            instance=User(username="00042"),
            prefix="perfil",
            data={
                "perfil-TOTAL_FORMS": "1",
                "perfil-INITIAL_FORMS": "0",
                "perfil-MIN_NUM_FORMS": "0",
                "perfil-MAX_NUM_FORMS": "1",
                "perfil-0-nombre_completo": nombre_completo,
                "perfil-0-telefono": telefono,
            },
        )

    def test_perfil_completo_valido(self):
        perfil = self.formset("Socio de prueba", "+34 600 000 000")
        self.assertTrue(perfil.is_valid(), perfil.errors)
        socio = perfil.save(commit=False)[0]
        self.assertEqual(socio.numero_socio, "00042")

    def test_perfil_sin_telefono_valido(self):
        perfil = self.formset("Socio de prueba", "")
        self.assertTrue(perfil.is_valid(), perfil.errors)
        self.assertEqual(perfil.save(commit=False)[0].telefono, "")

    def test_perfil_requiere_nombre(self):
        perfil = self.formset("", "+34 600 000 000")
        self.assertFalse(perfil.is_valid())
        self.assertIn("nombre_completo", perfil.forms[0].errors)

    def test_administrador_puede_crearse_sin_perfil(self):
        perfil = self.formset()
        self.assertTrue(perfil.is_valid(), perfil.errors)
        self.assertEqual(perfil.save(commit=False), [])
