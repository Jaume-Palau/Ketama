"""Recuperación del estado desde CSV ficticio en una base de pruebas."""
import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from socios.management.commands.importar_socios import COLUMNAS
from socios.models import Socio


class AsignarEstadosSociosTests(TestCase):
    def setUp(self):
        self.directorio = TemporaryDirectory(prefix=".prueba-estados-", dir=settings.BASE_DIR)
        self.addCleanup(self.directorio.cleanup)
        self.ruta = Path(self.directorio.name) / "ficticio.csv"
        self.activo = self.crear_socio("125", Socio.Estado.CADUCADO, is_active=False)
        self.caducado = self.crear_socio("126", Socio.Estado.ACTIVO)
        self.cero = self.crear_socio("0", Socio.Estado.ACTIVO)
        self.personal = self.crear_socio("127", Socio.Estado.CADUCADO, is_staff=True)
        self.admin = self.crear_socio("128", Socio.Estado.CADUCADO, is_superuser=True)
        User.objects.create_user(username="129", password="Solo-Pruebas-8!")
        self.excluido = self.crear_socio("130", Socio.Estado.CADUCADO)
        self.expulsado = self.crear_socio("131", Socio.Estado.CADUCADO)
        self.filas = [
            ["activo", "125", "Nombre CSV", "Apellidos CSV", ""],
            ["caducado", "126", "Nombre CSV", "Apellidos CSV", ""],
            ["activo", "0", "Nombre CSV", "Apellidos CSV", ""],
            ["activo", "127", "Nombre CSV", "Apellidos CSV", ""],
            ["activo", "128", "Nombre CSV", "Apellidos CSV", ""],
            ["activo", "129", "Nombre CSV", "Apellidos CSV", ""],
            ["inactivo", "130", "", "", ""],
            ["expulsado", "131", "", "", ""],
            ["activo", "132", "Nombre CSV", "Apellidos CSV", ""],
        ]
        self.escribir(self.filas)

    def crear_socio(self, numero, estado, **permisos):
        usuario = User.objects.create_user(
            username=numero, password="Solo-Pruebas-8!", **permisos
        )
        Socio.objects.create(
            usuario=usuario, nombre_completo="Nombre conservado", telefono="600000000",
            estado=estado, debe_cambiar_password=False,
        )
        return usuario

    def escribir(self, filas):
        with self.ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
            writer = csv.writer(archivo, delimiter=";")
            writer.writerow(COLUMNAS)
            writer.writerows(filas)

    def ejecutar(self, modo="--dry-run"):
        salida = StringIO()
        call_command("asignar_estados_socios", str(self.ruta), modo, stdout=salida)
        return salida.getvalue()

    def snapshot(self):
        return list(User.objects.order_by("pk").values()), list(Socio.objects.order_by("pk").values())

    def test_simulacion_sin_escrituras_con_recuentos_y_sin_datos_personales(self):
        antes = self.snapshot()
        salida = self.ejecutar()
        self.assertEqual(self.snapshot(), antes)
        self.assertIn("Se actualizarían a activo: 1", salida)
        self.assertIn("Se actualizarían a caducado: 1", salida)
        self.assertIn("administración: 2", salida)
        self.assertIn("cuenta de prueba: 1", salida)
        self.assertIn("inactividad o expulsión: 2", salida)
        self.assertIn("cuenta inexistente: 1", salida)
        self.assertIn("perfil inexistente: 1", salida)
        for dato in ("Nombre CSV", "Apellidos CSV", "Nombre conservado", "600000000", self.activo.password):
            self.assertNotIn(dato, salida)

    def test_aplicacion_modifica_solo_estados_elegibles(self):
        usuarios_antes, socios_antes = self.snapshot()
        self.assertIn("Actualizadas a activo: 1", self.ejecutar("--apply"))
        usuarios_despues, socios_despues = self.snapshot()
        self.assertEqual(usuarios_antes, usuarios_despues)
        for antes, despues in zip(socios_antes, socios_despues):
            esperado = dict(antes)
            if antes["usuario_id"] == self.activo.pk:
                esperado["estado"] = Socio.Estado.ACTIVO
            elif antes["usuario_id"] == self.caducado.pk:
                esperado["estado"] = Socio.Estado.CADUCADO
            self.assertEqual(esperado, despues)
        self.assertFalse(User.objects.filter(username="132").exists())

    def test_repeticion_no_cambia_datos_y_cuenta_ambos_estados(self):
        self.ejecutar("--apply")
        antes = self.snapshot()
        salida = self.ejecutar("--apply")
        self.assertIn("Cuentas con destino activo: 1", salida)
        self.assertIn("Cuentas con destino caducado: 1", salida)
        self.assertIn("Actualizadas a activo: 0", salida)
        self.assertIn("Actualizadas a caducado: 0", salida)
        self.assertIn("Sin cambios necesarios: 2", salida)
        self.assertEqual(self.snapshot(), antes)

    def test_estados_desconocidos_o_contradictorios_bloquean_todos_los_cambios(self):
        for fila in (
            ["otro", "126", "Nombre", "Apellidos", ""],
            ["caducado", "125", "Nombre", "Apellidos", ""],
        ):
            with self.subTest(estado=fila[0]):
                self.escribir([self.filas[0], fila])
                antes = self.snapshot()
                self.assertIn("Errores de validación: 1", self.ejecutar())
                with self.assertRaises(CommandError):
                    self.ejecutar("--apply")
                self.assertEqual(self.snapshot(), antes)

    def test_fallo_inesperado_revierte_toda_la_transaccion(self):
        antes = self.snapshot()
        guardar = Socio.save
        llamadas = 0

        def fallo_segundo_cambio(socio, *args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("Datos personales ficticios")
            return guardar(socio, *args, **kwargs)

        with patch.object(Socio, "save", fallo_segundo_cambio):
            with self.assertRaises(CommandError) as error:
                self.ejecutar("--apply")
        self.assertNotIn("Datos personales", str(error.exception))
        self.assertEqual(self.snapshot(), antes)

    def test_modo_explicito_obligatorio_y_excluyente(self):
        for opciones in ((), ("--dry-run", "--apply")):
            with self.assertRaises(CommandError):
                call_command("asignar_estados_socios", str(self.ruta), *opciones)
