"""Importación con archivos y cuentas ficticias, solo en la BD de pruebas."""
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

from socios.management.commands.importar_socios import (
    COLUMNAS, generar_password_inicial, normalizar_nombre,
)
from socios.models import Socio


class ImportarSociosTests(TestCase):
    def setUp(self):
        self.directorio = TemporaryDirectory(
            prefix=".prueba-importacion-", dir=settings.BASE_DIR
        )
        self.addCleanup(self.directorio.cleanup)
        self.ruta = Path(self.directorio.name) / "ficticio.csv"
        self.usuario_cero = User.objects.create_user(
            username="0", password="Solo-Pruebas-7!"
        )
        self.perfil_cero = Socio.objects.create(
            usuario=self.usuario_cero,
            nombre_completo="Cuenta de prueba",
            telefono="000000000",
            debe_cambiar_password=False,
        )

    def escribir(self, filas, columnas=COLUMNAS):
        with self.ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.writer(archivo, delimiter=";")
            escritor.writerow(columnas)
            escritor.writerows(filas)

    def ejecutar(self, modo="--dry-run"):
        salida = StringIO()
        call_command("importar_socios", str(self.ruta), modo, stdout=salida)
        return salida.getvalue()

    def comprobar_cero_intacto(self):
        hash_anterior = self.usuario_cero.password
        self.usuario_cero.refresh_from_db()
        self.perfil_cero.refresh_from_db()
        self.assertEqual(self.usuario_cero.password, hash_anterior)
        self.assertTrue(self.usuario_cero.is_active)
        self.assertFalse(self.perfil_cero.debe_cambiar_password)
        self.assertEqual(self.perfil_cero.nombre_completo, "Cuenta de prueba")
        self.assertEqual(self.perfil_cero.telefono, "000000000")

    def test_simulacion_cuenta_sin_modificar_la_base(self):
        self.escribir([
            ["activo", "125", "María", "García López", "001234567"],
            ["caducado", "126", "Ana", "De Prueba", "+34 600 000 002"],
            ["inactivo", "127", "Luis", "De Prueba", "600000003"],
            ["activo", "125", "Otra", "Persona", "600000004"],
            ["activo", "0", "Otra", "Persona", "600000005"],
            ["desconocido", "128", "Eva", "De Prueba", "600000006"],
            ["activo", "129", "Incompleta", "", ""],
        ])
        usuarios = list(User.objects.values())
        perfiles = list(Socio.objects.values())
        salida = self.ejecutar()
        self.assertIn("Se importarían: 2", salida)
        self.assertIn("Descartados por inactividad: 1", salida)
        self.assertIn("Descartados por duplicados: 1", salida)
        self.assertIn("Descartados por errores: 2", salida)
        self.assertIn("cuenta de prueba: 1", salida)
        self.assertEqual(list(User.objects.values()), usuarios)
        self.assertEqual(list(Socio.objects.values()), perfiles)
        for dato in ("María", "García", "001234567", "mariagarcia125"):
            self.assertNotIn(dato, salida)

    def test_aplicar_solo_activos_y_caducados_y_guardar_hash(self):
        self.escribir([
            [" ACTIVO ", "125", " María ", " García   López ", "001234567"],
            ["caducado", "00126", "Ana-María", "D'Ávila", "+34 600 000 002"],
            ["inactivo", "127", "Luis", "De Prueba", "600000003"],
            ["activo", "0", "Otra", "Persona", "600000005"],
        ])
        salida = self.ejecutar("--apply")
        self.assertIn("Importados: 2", salida)
        usuario = User.objects.get(username="125")
        self.assertTrue(usuario.check_password("mariagarcia125"))
        self.assertFalse(usuario.check_password("mariagarcialopez125"))
        self.assertNotEqual(usuario.password, "mariagarcia125")
        self.assertTrue(usuario.is_active)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(usuario.socio.nombre_completo, "María García López")
        self.assertEqual(usuario.socio.telefono, "001234567")
        self.assertTrue(usuario.socio.debe_cambiar_password)
        self.assertTrue(
            User.objects.get(username="00126").check_password("anamariadavila00126")
        )
        self.assertFalse(User.objects.filter(username="127").exists())
        self.comprobar_cero_intacto()

    def test_telefonos_vacios_se_simulan_y_guardan_como_cadena_vacia(self):
        self.escribir([
            ["activo", "125", "Ana", "De Prueba", ""],
            ["caducado", "126", "Eva", "De Prueba", "   "],
            ["inactivo", "127", "Luis", "De Prueba", ""],
        ])
        usuarios_antes = list(User.objects.values())
        perfiles_antes = list(Socio.objects.values())
        salida = self.ejecutar()
        self.assertIn("Se importarían: 2", salida)
        self.assertIn("Descartados por errores: 0", salida)
        self.assertIn("Descartados por inactividad: 1", salida)
        self.assertEqual(list(User.objects.values()), usuarios_antes)
        self.assertEqual(list(Socio.objects.values()), perfiles_antes)

        self.assertIn("Importados: 2", self.ejecutar("--apply"))
        for numero in ("125", "126"):
            usuario = User.objects.get(username=numero)
            self.assertEqual(usuario.socio.telefono, "")
            self.assertTrue(usuario.socio.debe_cambiar_password)
            self.assertTrue(usuario.is_active)
            self.assertFalse(usuario.is_staff)
            self.assertFalse(usuario.is_superuser)
        self.assertFalse(User.objects.filter(username="127").exists())
        self.comprobar_cero_intacto()

    def test_expulsados_se_descartan_sin_errores_ni_cuentas(self):
        self.escribir([
            ["expulsado", "125", "Ana", "De Prueba", ""],
            [" EXPULSADO ", "126", "", "", ""],
            ["inactivo", "127", "", "", ""],
            ["activo", "128", "Eva", "De Prueba", ""],
        ])
        salida = self.ejecutar()
        self.assertIn("Descartados por errores: 0", salida)
        self.assertIn("Descartados por inactividad: 3", salida)
        self.assertIn("Se importarían: 1", salida)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Socio.objects.count(), 1)
        salida = self.ejecutar("--apply")
        self.assertIn("Importados: 1", salida)
        self.assertIn("Descartados por errores: 0", salida)
        self.assertIn("Descartados por inactividad: 3", salida)
        self.assertFalse(User.objects.filter(username__in=["125", "126", "127"]).exists())
        self.assertTrue(User.objects.filter(username="128").exists())
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Socio.objects.count(), 2)
        self.comprobar_cero_intacto()

    def test_idempotencia_y_primera_fila_valida_gana(self):
        self.escribir([
            ["activo", "125", "María", "García López", "001234567"],
            ["activo", "125", "Otra", "Persona", "600000004"],
        ])
        self.ejecutar("--apply")
        usuario = User.objects.get(username="125")
        hash_anterior = usuario.password
        usuario.socio.debe_cambiar_password = False
        usuario.socio.save(update_fields=["debe_cambiar_password"])
        salida = self.ejecutar("--apply")
        usuario.refresh_from_db()
        self.assertEqual(usuario.password, hash_anterior)
        self.assertEqual(usuario.socio.nombre_completo, "María García López")
        self.assertFalse(usuario.socio.debe_cambiar_password)
        self.assertIn("Importados: 0", salida)
        self.assertIn("Descartados por duplicados: 2", salida)

    def test_usuario_existente_sin_perfil_no_se_modifica(self):
        usuario = User.objects.create_user(
            username="125", password="Existente-Prueba-8!", is_active=False,
            is_staff=True, is_superuser=True,
        )
        antes = User.objects.get(pk=usuario.pk).__dict__.copy()
        self.escribir([["activo", "125", "Otra", "Persona", "600000004"]])
        self.assertIn("Descartados por duplicados: 1", self.ejecutar("--apply"))
        usuario.refresh_from_db()
        for campo in ("password", "is_active", "is_staff", "is_superuser"):
            self.assertEqual(getattr(usuario, campo), antes[campo])
        self.assertFalse(Socio.objects.filter(usuario=usuario).exists())

    def test_filas_erroneas_bloquean_todas_las_altas(self):
        errores = [
            ["activo", "", "Ana", "Prueba", "600000000"],
            ["activo", "letras", "Ana", "Prueba", "600000000"],
            ["activo", "126", "", "Prueba", "600000000"],
            ["activo", "126", "Ana", "", "600000000"],
            ["otro", "126", "Ana", "Prueba", "600000000"],
            ["activo", "126", "Ana", "Prueba", "6" * 31],
            ["activo", "1" * 151, "Ana", "Prueba", "600000000"],
            ["activo", "126", "A" * 201, "Prueba", "600000000"],
            ["activo", "126", "---", "!!!", "600000000"],
            ["activo", "126", "Ana", "Prueba"],
            ["activo", "126", "Ana", "Prueba", "600000000", "extra"],
            ["activo", "126", "Ana\x00", "Prueba", "600000000"],
        ]
        for fila in errores:
            with self.subTest(tipo=len(fila)):
                self.escribir([
                    ["activo", "125", "Válida", "Prueba", "600000001"], fila,
                ])
                with self.assertRaises(CommandError):
                    self.ejecutar("--apply")
                self.assertEqual(User.objects.count(), 1)
                self.assertEqual(Socio.objects.count(), 1)

    def test_error_inesperado_revierte_todo_y_no_expone_datos(self):
        self.escribir([
            ["activo", "125", "María", "Prueba", "600000001"],
            ["activo", "126", "Ana", "Prueba", "600000002"],
        ])
        crear = Socio.objects.create
        llamadas = 0

        def fallo_segunda_alta(**kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("Datos privados: Ana 600000002")
            return crear(**kwargs)

        with patch.object(Socio.objects, "create", side_effect=fallo_segunda_alta):
            with self.assertRaises(CommandError) as error:
                self.ejecutar("--apply")
        self.assertNotIn("Ana", str(error.exception))
        self.assertNotIn("600000002", str(error.exception))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Socio.objects.count(), 1)
        self.comprobar_cero_intacto()

    def test_cabeceras_invalidas_rechazadas(self):
        for cabecera in (COLUMNAS[:-1], (*COLUMNAS, "OTRA"), ("ESTADO",) * 5):
            self.escribir([], cabecera)
            with self.assertRaises(CommandError):
                self.ejecutar()

    def test_csv_malformado_y_codificacion_invalida_no_importan(self):
        for contenido in (
            (";".join(COLUMNAS) + '\nactivo;125;"sin cierre').encode("utf-8"),
            b"\xff\xfe\x00",
        ):
            self.ruta.write_bytes(contenido)
            with self.assertRaises(CommandError):
                self.ejecutar("--apply")
            self.assertEqual(User.objects.count(), 1)

    def test_se_requiere_un_solo_modo_explicito(self):
        self.escribir([])
        for opciones in ((), ("--dry-run", "--apply")):
            with self.assertRaises(CommandError):
                call_command("importar_socios", str(self.ruta), *opciones)

    def test_normalizacion_de_signos_y_tildes(self):
        self.assertEqual(normalizar_nombre(" María-García D'Ávila / Núñez! "),
                         "mariagarciadavilanunez")

    def test_password_usa_nombre_completo_y_primera_palabra_de_apellidos(self):
        self.assertEqual(
            generar_password_inicial("María José", "  García López ", "00125"),
            "mariajosegarcia00125",
        )
        self.assertEqual(
            generar_password_inicial("Ana-María", "D'Ávila Pérez", "126"),
            "anamariadavila126",
        )
