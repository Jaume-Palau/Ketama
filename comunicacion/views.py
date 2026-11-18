"""Lectura de avisos publicados, protegida por el middleware existente."""
from django.shortcuts import render
from django.views.decorators.http import require_safe

from .models import Aviso


@require_safe
def avisos(request):
    return render(request, "comunicacion/avisos.html", {
        "avisos": Aviso.objects.filter(activo=True),
        "avisos_activo": True,
    })
