"""Catálogo y fichas privadas de genéticas; consultas sin escrituras."""
from django.db.models import Avg, Count, F, Max, Q
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from .models import Genetica


def opciones_catalogo(request):
    """Solo parámetros propios del catálogo, nunca una URL de retorno externa."""
    busqueda = request.GET.get("q", "").strip()[:150]
    clasificacion = request.GET.get("clasificacion", "")
    if clasificacion not in Genetica.Clasificacion.values:
        clasificacion = ""
    orden = request.GET.get("orden", "valoracion")
    if orden not in {"valoracion", "precio_asc", "precio_desc"}:
        orden = "valoracion"
    return busqueda, clasificacion, orden


def consulta_catalogo(busqueda, clasificacion, orden):
    parametros = QueryDict(mutable=True)
    if busqueda:
        parametros["q"] = busqueda
    if clasificacion:
        parametros["clasificacion"] = clasificacion
    parametros["orden"] = orden
    return parametros


@require_safe
def catalogo(request):
    busqueda, clasificacion, orden = opciones_catalogo(request)
    ordenaciones = {
        "valoracion": (F("media_catalogo").desc(nulls_last=True), "-votos_catalogo", "nombre", "pk"),
        "precio_asc": (F("precio").asc(nulls_last=True), "nombre", "pk"),
        "precio_desc": (F("precio").desc(nulls_last=True), "nombre", "pk"),
    }

    geneticas = Genetica.objects.filter(activo=True)
    if busqueda:
        geneticas = geneticas.filter(nombre__icontains=busqueda)
    if clasificacion:
        geneticas = geneticas.filter(clasificacion=clasificacion)
    geneticas = geneticas.annotate(
        media_catalogo=Avg("valoraciones__puntuacion"),
        votos_catalogo=Count("valoraciones"),
    ).order_by(*ordenaciones[orden])

    parametros = consulta_catalogo(busqueda, clasificacion, orden)
    filtros = []
    for valor, etiqueta in [("", "Todas"), *Genetica.Clasificacion.choices]:
        consulta = parametros.copy()
        if valor:
            consulta["clasificacion"] = valor
        else:
            consulta.pop("clasificacion", None)
        filtros.append({
            "etiqueta": etiqueta, "valor": valor,
            "activo": valor == clasificacion,
            "url": f"{reverse('geneticas:catalogo')}?{consulta.urlencode()}",
        })
    return render(request, "geneticas/catalogo.html", {
        "geneticas": geneticas, "busqueda": busqueda,
        "clasificacion": clasificacion, "orden": orden, "filtros": filtros,
        "consulta_catalogo": parametros.urlencode(),
        "catalogo_url": f"{reverse('geneticas:catalogo')}?{parametros.urlencode()}",
    })


@require_safe
def detalle(request, pk):
    agregaciones = {
        "media_catalogo": Avg("valoraciones__puntuacion"),
        "votos_catalogo": Count("valoraciones"),
        "mi_puntuacion": Max(
            "valoraciones__puntuacion",
            filter=Q(valoraciones__socio_id=request.socio.pk),
        ),
    }
    for puntuacion in range(1, 6):
        agregaciones[f"votos_{puntuacion}"] = Count(
            "valoraciones", filter=Q(valoraciones__puntuacion=puntuacion)
        )
    genetica = get_object_or_404(
        Genetica.objects.filter(activo=True).annotate(**agregaciones), pk=pk
    )
    distribucion = []
    for puntuacion in range(5, 0, -1):
        votos = getattr(genetica, f"votos_{puntuacion}")
        distribucion.append({
            "puntuacion": puntuacion, "votos": votos,
            "porcentaje": round(votos * 100 / genetica.votos_catalogo) if genetica.votos_catalogo else 0,
        })
    parametros = consulta_catalogo(*opciones_catalogo(request))
    volver = f"{reverse('geneticas:catalogo')}?{parametros.urlencode()}#tarjeta-{genetica.pk}"
    return render(request, "geneticas/detalle.html", {
        "genetica": genetica, "distribucion": distribucion,
        "estrellas": range(1, 6), "volver_catalogo": volver, "es_detalle": True,
    })
