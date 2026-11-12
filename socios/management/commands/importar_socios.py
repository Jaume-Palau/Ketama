"""Importación inicial de socios, sin actualizar cuentas existentes."""
import csv
import re
import unicodedata
from collections import Counter
from typing import NamedTuple

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction

from socios.models import Socio


COLUMNAS = ("ESTADO", "NºSocio", "NOMBRE", "APELLIDOS", "TELEFONO")


class FilaSocio(NamedTuple):
    numero: str
    nombre_completo: str
    telefono: str
    nombre: str
    apellidos: str


def normalizar_nombre(nombre):
    """Sin tildes ni signos: solo letras y dígitos ASCII en minúsculas."""
    texto = unicodedata.normalize("NFKD", nombre).lower()
    return re.sub(r"[^a-z0-9]", "", texto)


def generar_password_inicial(nombre, apellidos, numero):
    """NOMBRE completo + primera palabra de APELLIDOS + número, normalizados."""
    return normalizar_nombre(nombre + apellidos.split()[0]) + numero


def leer_csv(ruta):
    """Valida todo el archivo antes de consultar o modificar cuentas."""
    filas = []
    resumen = Counter()
    vistos = set()
    max_usuario = User._meta.get_field("username").max_length
    max_nombre = Socio._meta.get_field("nombre_completo").max_length
    max_telefono = Socio._meta.get_field("telefono").max_length
    try:
        with open(ruta, encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo, delimiter=";", strict=True)
            if (
                lector.fieldnames is None
                or len(lector.fieldnames) != len(COLUMNAS)
                or set(lector.fieldnames) != set(COLUMNAS)
            ):
                raise CommandError("Cabecera incorrecta: se requieren las cinco columnas acordadas.")
            for fila in lector:
                resumen["total"] += 1
                if None in fila or any(valor is None for valor in fila.values()):
                    resumen["errores"] += 1
                    continue
                estado = fila["ESTADO"].strip().lower()
                if estado in {"inactivo", "expulsado"}:
                    resumen["inactivos"] += 1
                    continue
                if estado not in {"activo", "caducado"}:
                    resumen["errores"] += 1
                    continue
                numero = fila["NºSocio"].strip()
                if numero == "0":
                    resumen["protegidos"] += 1
                    continue
                nombre = " ".join(
                    f"{fila['NOMBRE'].strip()} {fila['APELLIDOS'].strip()}".split()
                )
                telefono = fila["TELEFONO"].strip()
                if (
                    not all(
                        fila[columna].strip()
                        for columna in ("ESTADO", "NºSocio", "NOMBRE", "APELLIDOS")
                    )
                    or not re.fullmatch(r"[0-9]+", numero)
                    or len(numero) > max_usuario
                    or len(nombre) > max_nombre
                    or len(telefono) > max_telefono
                    or not normalizar_nombre(
                        fila["NOMBRE"] + fila["APELLIDOS"].split()[0]
                    )
                    or any(
                        unicodedata.category(caracter) == "Cc"
                        for valor in fila.values()
                        for caracter in valor
                    )
                ):
                    resumen["errores"] += 1
                    continue
                if numero in vistos:
                    resumen["duplicados"] += 1
                    continue
                vistos.add(numero)
                filas.append(FilaSocio(
                    numero, nombre, telefono,
                    fila["NOMBRE"].strip(), fila["APELLIDOS"].strip(),
                ))
    except (OSError, UnicodeError, csv.Error):
        raise CommandError(
            "No se pudo leer el CSV completo. Comprueba el archivo, UTF-8 y el separador ';'."
        ) from None
    return filas, resumen


def descartar_existentes(filas, resumen):
    existentes = set(User.objects.values_list("username", flat=True))
    pendientes = []
    for fila in filas:
        if fila.numero in existentes:
            resumen["duplicados"] += 1
        else:
            pendientes.append(fila)
    return pendientes


class Command(BaseCommand):
    help = "Valida o importa socios desde un CSV UTF-8 separado por ';'."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta al CSV local (no se copia).")
        modo = parser.add_mutually_exclusive_group(required=True)
        modo.add_argument("--dry-run", action="store_true", help="Solo validar y contar.")
        modo.add_argument("--apply", action="store_true", help="Crear las cuentas válidas.")

    def mostrar_resumen(self, resumen, cantidad, simulacion):
        self.stdout.write("Simulación: sin cambios." if simulacion else "Importación completada.")
        etiqueta = "Se importarían" if simulacion else "Importados"
        self.stdout.write(f"Filas leídas: {resumen['total']}")
        self.stdout.write(f"{etiqueta}: {cantidad}")
        self.stdout.write(f"Descartados por inactividad: {resumen['inactivos']}")
        self.stdout.write(f"Descartados por duplicados: {resumen['duplicados']}")
        self.stdout.write(f"Descartados por errores: {resumen['errores']}")
        self.stdout.write(f"Descartados por protección de la cuenta de prueba: {resumen['protegidos']}")

    def handle(self, *args, **options):
        filas, resumen = leer_csv(options["archivo"])
        if options["dry_run"] or resumen["errores"]:
            try:
                pendientes = descartar_existentes(filas, resumen)
            except DatabaseError:
                raise CommandError("No se pudo consultar la base de datos.") from None
            self.mostrar_resumen(resumen, len(pendientes), simulacion=True)
            if resumen["errores"]:
                self.stdout.write("La aplicación quedaría bloqueada hasta corregir los errores.")
            if not options["dry_run"]:
                raise CommandError("Importación cancelada: corrige los errores y repite la simulación.")
            return

        try:
            with transaction.atomic():
                pendientes = descartar_existentes(filas, resumen)
                for fila in pendientes:
                    usuario = User.objects.create_user(
                        username=fila.numero,
                        password=generar_password_inicial(
                            fila.nombre, fila.apellidos, fila.numero
                        ),
                        is_active=True,
                        is_staff=False,
                        is_superuser=False,
                    )
                    Socio.objects.create(
                        usuario=usuario,
                        nombre_completo=fila.nombre_completo,
                        telefono=fila.telefono,
                        debe_cambiar_password=True,
                    )
        except Exception:
            # No incluir excepciones del ORM: podrían contener datos personales.
            # La transacción ya ha revertido todas las altas de esta ejecución.
            raise CommandError(
                "Importación cancelada por un error; no se ha guardado ninguna alta."
            ) from None
        self.mostrar_resumen(resumen, len(pendientes), simulacion=False)
