"""Actualización de contraseñas con CSV y cuentas ficticias en la BD de pruebas."""
import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from socios.management.commands.importar_socios import COLUMNAS
from socios.models import Socio


class ActualizarPasswordsInicialesTests(TestCase):
    def setUp(self):
        self.directorio = TemporaryDirectory(prefix=".prueba-passwords-", dir=settings.BASE_DIR)
        self.addCleanup(self.directorio.cleanup)
        self.ruta = Path(self.directorio.name) / "ficticio.csv"
        self.usuario = self.crear_socio("125", "mariajosegarcialopez125")
        self.cambiado = self.crear_socio("126", "Personal-Prueba-6!", pendiente=False)
        self.cero = self.crear_socio("0", "No-Tocar-Prueba-7!")
        self.personal = self.crear_socio("127", "No-Tocar-Prueba-8!", is_staff=True)
        self.admin = self.crear_socio("128", "No-Tocar-Prueba-9!", is_superuser=True)
        self.sin_perfil = User.objects.create_user(username="129", password="Sin-Perfil-8!")
        self.inactivo_csv = self.crear_socio("130", "No-Tocar-Prueba-10!")
        self.expulsado_csv = self.crear_socio("131", "No-Tocar-Prueba-11!")
        self.escribir([
            ["activo", "125", "María José", "García López", ""],
            ["caducado", "126", "Eva", "De Prueba", ""],
            ["activo", "0", "Cuenta", "De Prueba", ""],
            ["activo", "127", "Personal", "De Prueba", ""],
            ["activo", "128", "Administrador", "De Prueba", ""],
            ["activo", "129", "Sin", "Perfil", ""],
            ["inactivo", "130", "Luis", "De Prueba", ""],
            ["expulsado", "131", "Luis", "De Prueba", ""],
            ["activo", "132", "No", "Existe", ""],
            ["activo", "125", "Otra", "Persona", ""],
        ])

    def crear_socio(self, numero, password, pendiente=True, **permisos):
        usuario = User.objects.create_user(username=numero, password=password, **permisos)
        # Nombre deliberadamente distinto: el comando debe consultar el CSV.
        Socio.objects.create(
            usuario=usuario, nombre_completo="Ficha ficticia", telefono="",
            debe_cambiar_password=pendiente,
        )
        return usuario

    def escribir(self, filas):
        with self.ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
            writer = csv.writer(archivo, delimiter=";")
            writer.writerow(COLUMNAS)
            writer.writerows(filas)

    def ejecutar(self, modo="--dry-run"):
        salida = StringIO()
        call_command("actualizar_passwords_iniciales", str(self.ruta), modo, stdout=salida)
        return salida.getvalue()

    def snapshot(self):
        return list(User.objects.order_by("pk").values()), list(Socio.objects.order_by("pk").values())

    def test_dry_run_no_escribe_y_solo_cuenta_elegibles(self):
        antes = self.snapshot()
        salida = self.ejecutar()
        self.assertEqual(self.snapshot(), antes)
        self.assertIn("Se actualizarían: 1", salida)
        self.assertIn("contraseña ya cambiada: 1", salida)
        self.assertIn("cuenta de administración: 2", salida)
        self.assertIn("perfil inexistente: 1", salida)
        self.assertIn("cuenta inexistente: 1", salida)
        self.assertIn("inactividad o expulsión: 2", salida)
        self.assertIn("duplicados en CSV: 1", salida)
        self.assertIn("cuenta de prueba: 1", salida)
        for dato in ("María", "García", "mariajosegarcia125", self.usuario.password):
            self.assertNotIn(dato, salida)

    def test_apply_cambia_solo_password_pendiente_y_conserva_perfil_y_permisos(self):
        usuarios_antes, perfiles_antes = self.snapshot()
        self.assertIn("Actualizadas: 1", self.ejecutar("--apply"))
        usuarios_despues, perfiles_despues = self.snapshot()
        self.assertEqual(perfiles_antes, perfiles_despues)
        for antes, despues in zip(usuarios_antes, usuarios_despues):
            if antes["id"] == self.usuario.pk:
                self.assertNotEqual(antes["password"], despues["password"])
                antes = {k: v for k, v in antes.items() if k != "password"}
                despues = {k: v for k, v in despues.items() if k != "password"}
            self.assertEqual(antes, despues)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("mariajosegarcia125"))
        self.assertFalse(self.usuario.check_password("mariajosegarcialopez125"))
        self.assertTrue(self.usuario.socio.debe_cambiar_password)
        self.assertFalse(User.objects.filter(username="132").exists())

    def test_repetir_no_reescribe_hash_correcto(self):
        self.ejecutar("--apply")
        antes = self.snapshot()
        self.assertIn("Se actualizarían: 0", self.ejecutar())
        salida = self.ejecutar("--apply")
        self.assertIn("Actualizadas: 0", salida)
        self.assertIn("formato ya actualizado: 1", salida)
        self.assertEqual(self.snapshot(), antes)

    def test_dry_run_no_actualiza_un_hash_antiguo_con_password_correcta(self):
        # Hash deliberadamente débil solo para probar la ausencia de auto-upgrade.
        self.usuario.password = PBKDF2PasswordHasher().encode(
            "mariajosegarcia125", "sal-ficticia-prueba", iterations=1
        )
        self.usuario.save(update_fields=["password"])
        antes = self.snapshot()
        salida = self.ejecutar()
        self.assertIn("Se actualizarían: 0", salida)
        self.assertIn("formato ya actualizado: 1", salida)
        self.assertEqual(self.snapshot(), antes)

    def test_revalida_el_indicador_entre_simulacion_y_aplicacion(self):
        self.assertIn("Se actualizarían: 1", self.ejecutar())
        self.usuario.set_password("Personal-Elegida-Prueba-8!")
        self.usuario.save(update_fields=["password"])
        Socio.objects.filter(usuario=self.usuario).update(debe_cambiar_password=False)
        antes = self.snapshot()
        self.assertIn("Actualizadas: 0", self.ejecutar("--apply"))
        self.assertEqual(self.snapshot(), antes)

    def test_validacion_erronea_impide_actualizar_cualquier_cuenta(self):
        self.escribir([
            ["activo", "125", "María José", "García López", ""],
            ["desconocido", "126", "Eva", "De Prueba", ""],
        ])
        antes = self.snapshot()
        self.assertIn("Descartadas por errores: 1", self.ejecutar())
        with self.assertRaises(CommandError):
            self.ejecutar("--apply")
        self.assertEqual(self.snapshot(), antes)

    def test_error_inesperado_revierte_todas_las_actualizaciones(self):
        self.crear_socio("133", "Antigua-Prueba-12!")
        self.escribir([
            ["activo", "125", "María José", "García López", ""],
            ["activo", "133", "Ana", "García López", ""],
        ])
        antes = self.snapshot()
        guardar = User.save
        llamadas = 0

        def fallo_segunda_password(usuario, *args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("Datos privados de prueba")
            return guardar(usuario, *args, **kwargs)

        with patch.object(User, "save", fallo_segunda_password):
            with self.assertRaises(CommandError) as error:
                self.ejecutar("--apply")
        self.assertNotIn("Datos privados", str(error.exception))
        self.assertEqual(self.snapshot(), antes)

    def test_modo_es_obligatorio_y_excluyente(self):
        for opciones in ((), ("--dry-run", "--apply")):
            with self.assertRaises(CommandError):
                call_command("actualizar_passwords_iniciales", str(self.ruta), *opciones)
