"""Catálogo privado de genéticas; consultas sin escrituras."""
from django.db.models import Avg, Count, F
from django.http import QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

from .models import Genetica


@require_safe
def catalogo(request):
    busqueda = request.GET.get("q", "").strip()[:150]
    clasificacion = request.GET.get("clasificacion", "")
    if clasificacion not in Genetica.Clasificacion.values:
        clasificacion = ""
    orden = request.GET.get("orden", "valoracion")
    ordenaciones = {
        "valoracion": (F("media_catalogo").desc(nulls_last=True), "-votos_catalogo", "nombre", "pk"),
        "precio_asc": (F("precio").asc(nulls_last=True), "nombre", "pk"),
        "precio_desc": (F("precio").desc(nulls_last=True), "nombre", "pk"),
    }
    if orden not in ordenaciones:
        orden = "valoracion"

    geneticas = Genetica.objects.filter(activo=True)
    if busqueda:
        geneticas = geneticas.filter(nombre__icontains=busqueda)
    if clasificacion:
        geneticas = geneticas.filter(clasificacion=clasificacion)
    geneticas = geneticas.annotate(
        media_catalogo=Avg("valoraciones__puntuacion"),
        votos_catalogo=Count("valoraciones"),
    ).order_by(*ordenaciones[orden])

    parametros = QueryDict(mutable=True)
    if busqueda:
        parametros["q"] = busqueda
    parametros["orden"] = orden
    filtros = []
    for valor, etiqueta in [("", "Todas"), *Genetica.Clasificacion.choices]:
        consulta = parametros.copy()
        if valor:
            consulta["clasificacion"] = valor
        filtros.append({
            "etiqueta": etiqueta, "valor": valor,
            "activo": valor == clasificacion,
            "url": f"{reverse('geneticas:catalogo')}?{consulta.urlencode()}",
        })
    return render(request, "geneticas/catalogo.html", {
        "geneticas": geneticas, "busqueda": busqueda,
        "clasificacion": clasificacion, "orden": orden, "filtros": filtros,
    })
