"""Nivel público de precio: el importe permanece en PostgreSQL y en Admin."""
from decimal import Decimal

from django.db.models import Case, IntegerField, Value, When


def nivel_precio_sql():
    """Expresión reutilizable; los límites se comparan como decimales exactos."""
    return Case(
        When(precio__isnull=True, then=Value(None)),
        When(precio__lte=Decimal("6.00"), then=Value(1)),
        When(precio__lte=Decimal("7.50"), then=Value(2)),
        When(precio__lte=Decimal("9.00"), then=Value(3)),
        When(precio__lte=Decimal("10.50"), then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )


def segmentos_nivel_precio(nivel):
    """Geometría pública: cinco segmentos con relleno, sin importes."""
    if nivel is None:
        return ()
    return tuple(
        {"x": 1 + indice * 30, "activo": indice < nivel}
        for indice in range(5)
    )
