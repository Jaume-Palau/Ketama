"""Recuperación manual del estado original, sin alterar otros datos del socio."""
from collections import Counter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from socios.models import Socio
from .importar_socios import leer_csv


class Command(BaseCommand):
    help = "Asigna estados de socios existentes desde el CSV original, de forma manual."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="CSV original, solo lectura.")
        modo = parser.add_mutually_exclusive_group(required=True)
        modo.add_argument("--dry-run", action="store_true", help="Validar y contar sin escribir.")
        modo.add_argument("--apply", action="store_true", help="Asignar los estados del CSV.")

    def handle(self, *args, **options):
        filas, resumen_csv = leer_csv(
            options["archivo"], rechazar_estados_contradictorios=True
        )
        aplicar = options["apply"]
        if aplicar and resumen_csv["errores"]:
            raise CommandError(
                "Asignación cancelada: el CSV contiene errores o estados contradictorios. "
                "Revisa los recuentos con --dry-run."
            )
        resumen = Counter()
        try:
            with transaction.atomic():
                for fila in filas:
                    usuarios = User.objects.all()
                    perfiles = Socio.objects.all()
                    if aplicar:
                        usuarios = usuarios.select_for_update()
                        perfiles = perfiles.select_for_update()
                    usuario = usuarios.filter(username=fila.numero).first()
                    if usuario is None:
                        resumen["sin_cuenta"] += 1
                        continue
                    if usuario.username == "0" or usuario.is_staff or usuario.is_superuser:
                        resumen["administracion"] += 1
                        continue
                    socio = perfiles.filter(usuario_id=usuario.pk).first()
                    if socio is None:
                        resumen["sin_perfil"] += 1
                        continue
                    resumen[f"destino_{fila.estado}"] += 1
                    if socio.estado == fila.estado:
                        resumen["sin_cambios"] += 1
                        continue
                    if aplicar:
                        socio.estado = fila.estado
                        socio.save(update_fields=["estado"])
                    resumen[f"cambios_{fila.estado}"] += 1
        except Exception:
            raise CommandError(
                "No se pudo completar la operación; no se ha guardado ningún cambio de estado."
            ) from None

        self.stdout.write("Asignación completada." if aplicar else "Simulación: sin cambios.")
        for estado in Socio.Estado.values:
            self.stdout.write(f"Cuentas con destino {estado}: {resumen[f'destino_{estado}']}")
            etiqueta = "Actualizadas" if aplicar else "Se actualizarían"
            self.stdout.write(f"{etiqueta} a {estado}: {resumen[f'cambios_{estado}']}")
        self.stdout.write(f"Sin cambios necesarios: {resumen['sin_cambios']}")
        self.stdout.write(f"Omitidas por administración: {resumen['administracion']}")
        self.stdout.write(f"Omitidas por cuenta inexistente: {resumen['sin_cuenta']}")
        self.stdout.write(f"Omitidas por perfil inexistente: {resumen['sin_perfil']}")
        self.stdout.write(f"Filas leídas: {resumen_csv['total']}")
        self.stdout.write(f"Descartadas por inactividad o expulsión: {resumen_csv['inactivos']}")
        self.stdout.write(f"Descartadas por cuenta de prueba: {resumen_csv['protegidos']}")
        self.stdout.write(f"Duplicados en CSV: {resumen_csv['duplicados']}")
        self.stdout.write(f"Errores de validación: {resumen_csv['errores']}")
        if resumen_csv["errores"]:
            self.stdout.write("La aplicación quedaría bloqueada hasta corregir los errores.")
