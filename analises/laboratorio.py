import json
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .services.perfil_energetico import consultar_perfil, simular, PerfilEnergeticoErro

@require_GET
def painel(request):
    return render(request, 'analises/laboratorio.html', {'ultimo_ano':datetime.now().year-1})

@require_GET
def calcular(request):
    try:
        latitude=float(request.GET['latitude']); longitude=float(request.GET['longitude'])
        ano=int(request.GET.get('ano',datetime.now().year-1))
        registros=consultar_perfil(latitude,longitude,ano)
        resultado=simular(registros,
            meta_kg_dia=float(request.GET.get('meta',1000)),
            painel_wp=float(request.GET.get('painel',600)),
            turbina_kw=float(request.GET.get('turbina',3000)),
            quota_solar=float(request.GET.get('solar',50)))
        return JsonResponse({'ok':True,'ano':ano,'latitude':latitude,'longitude':longitude,'resultado':resultado})
    except (PerfilEnergeticoErro,ValueError,KeyError,TypeError) as exc:
        return JsonResponse({'ok':False,'erro':str(exc)},status=400)
