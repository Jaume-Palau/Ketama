"""Actualiza solo contraseñas temporales pendientes, identificadas desde CSV."""
from collections import Counter

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from socios.models import Socio
from .importar_socios import generar_password_inicial, leer_csv


class Command(BaseCommand):
    help = "Adapta contraseñas temporales pendientes al nuevo formato desde el CSV original."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta al CSV original (solo lectura).")
        modo = parser.add_mutually_exclusive_group(required=True)
        modo.add_argument("--dry-run", action="store_true", help="Contar sin modificar cuentas.")
        modo.add_argument("--apply", action="store_true", help="Actualizar las contraseñas elegibles.")

    def handle(self, *args, **options):
        filas, resumen_csv = leer_csv(options["archivo"])
        aplicar = options["apply"]
        if aplicar and resumen_csv["errores"]:
            raise CommandError(
                "Actualización cancelada: hay errores de validación en el CSV. "
                "Ejecuta --dry-run para consultar los recuentos."
            )
        resumen = Counter()
        try:
            with transaction.atomic():
                for fila in filas:
                    usuarios = User.objects.all()
                    perfiles = Socio.objects.all()
                    if aplicar:
                        # Mismo orden de bloqueo que el cambio de contraseña web:
                        # primero User, después Socio. Se revalida bajo bloqueo.
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
                    if not socio.debe_cambiar_password:
                        resumen["ya_cambiadas"] += 1
                        continue
                    password = generar_password_inicial(
                        fila.nombre, fila.apellidos, fila.numero
                    )
                    # Función sin setter: no actualiza hashes durante el dry-run.
                    if check_password(password, usuario.password):
                        resumen["ya_actualizadas"] += 1
                        continue
                    if aplicar:
                        usuario.set_password(password)
                        usuario.save(update_fields=["password"])
                    resumen["actualizables"] += 1
        except Exception:
            raise CommandError(
                "No se pudo completar la operación; no se ha actualizado ninguna contraseña."
            ) from None

        self.stdout.write("Actualización completada." if aplicar else "Simulación: sin cambios.")
        etiqueta = "Actualizadas" if aplicar else "Se actualizarían"
        self.stdout.write(f"{etiqueta}: {resumen['actualizables']}")
        self.stdout.write(f"Omitidas por contraseña ya cambiada: {resumen['ya_cambiadas']}")
        self.stdout.write(f"Omitidas por formato ya actualizado: {resumen['ya_actualizadas']}")
        self.stdout.write(f"Omitidas por cuenta de administración: {resumen['administracion']}")
        self.stdout.write(f"Omitidas por cuenta inexistente: {resumen['sin_cuenta']}")
        self.stdout.write(f"Omitidas por perfil inexistente: {resumen['sin_perfil']}")
        self.stdout.write(f"Filas leídas: {resumen_csv['total']}")
        self.stdout.write(f"Descartadas por inactividad o expulsión: {resumen_csv['inactivos']}")
        self.stdout.write(f"Descartadas por duplicados en CSV: {resumen_csv['duplicados']}")
        self.stdout.write(f"Descartadas por cuenta de prueba: {resumen_csv['protegidos']}")
        self.stdout.write(f"Descartadas por errores: {resumen_csv['errores']}")
        if resumen_csv["errores"]:
            self.stdout.write("La aplicación quedaría bloqueada hasta corregir los errores.")
