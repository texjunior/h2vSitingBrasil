import requests

from django.core.cache import cache


URL_NASA_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"


class NasaPowerErro(Exception):
    """Erro ao consultar ou processar dados da NASA POWER."""
    pass


def _valores_validos(serie):
    if not isinstance(serie, dict):
        return []

    return [
        float(valor)
        for valor in serie.values()
        if isinstance(valor, (int, float)) and valor >= 0
    ]


def _obter_dados_solares_sem_cache(latitude, longitude, ano=2025):
    """
    Faz UMA única consulta NASA POWER trazendo:
    - ALLSKY_SFC_SW_DWN: irradiação solar;
    - WS10M: vento a 10 m;
    - WS50M: vento a 50 m.

    Assim a análise eólica não cria uma nova chamada externa e preserva
    o ganho de desempenho da versão com cache/paralelismo.
    """

    parametros = {
        "parameters": "ALLSKY_SFC_SW_DWN,WS10M,WS50M",
        "community": "RE",
        "latitude": latitude,
        "longitude": longitude,
        "start": f"{ano}0101",
        "end": f"{ano}1231",
        "format": "JSON",
    }

    try:
        resposta = requests.get(
            URL_NASA_POWER,
            params=parametros,
            timeout=(4, 15),
        )
        resposta.raise_for_status()

    except requests.RequestException as erro:
        raise NasaPowerErro(
            f"Não foi possível acessar a NASA POWER: {erro}"
        ) from erro

    try:
        dados = resposta.json()
        parametros_retorno = dados["properties"]["parameter"]
        serie_solar = parametros_retorno["ALLSKY_SFC_SW_DWN"]

    except (ValueError, KeyError, TypeError) as erro:
        raise NasaPowerErro(
            "A NASA POWER retornou uma resposta inesperada."
        ) from erro

    valores_solares = _valores_validos(serie_solar)

    if not valores_solares:
        raise NasaPowerErro(
            "Não foram encontrados dados solares válidos para esta localização."
        )

    irradiacao_media = sum(valores_solares) / len(valores_solares)
    irradiacao_anual = sum(valores_solares)

    serie_vento_10m = parametros_retorno.get("WS10M") or {}
    serie_vento_50m = parametros_retorno.get("WS50M") or {}

    return {
        "fonte": "NASA POWER",
        "parametro": "ALLSKY_SFC_SW_DWN",
        "ano": ano,
        "latitude": latitude,
        "longitude": longitude,
        "dias_analisados": len(valores_solares),
        "irradiacao_media": round(irradiacao_media, 3),
        "irradiacao_anual": round(irradiacao_anual, 3),
        "irradiacao_minima": round(min(valores_solares), 3),
        "irradiacao_maxima": round(max(valores_solares), 3),
        "vento": {
            "disponivel": bool(serie_vento_10m and serie_vento_50m),
            "parametros": ["WS10M", "WS50M"],
            "serie_10m": serie_vento_10m,
            "serie_50m": serie_vento_50m,
        },
    }


def obter_dados_solares(latitude, longitude, ano=2025):
    """
    Versão com cache local do Django.

    v2 invalida o cache antigo, que continha apenas o parâmetro solar.
    """
    chave = (
        f"h2v:nasa:v2:{ano}:"
        f"{round(float(latitude), 4)}:"
        f"{round(float(longitude), 4)}"
    )

    armazenado = cache.get(chave)
    if armazenado is not None:
        return armazenado

    resultado = _obter_dados_solares_sem_cache(
        latitude=latitude,
        longitude=longitude,
        ano=ano,
    )

    cache.set(chave, resultado, 60 * 60 * 24 * 7)
    return resultado
