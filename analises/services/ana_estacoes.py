import math
import re
import unicodedata

import requests

from django.core.cache import cache


URL_ESTACOES_ANA = (
    "https://portal1.snirh.gov.br/server/rest/services/"
    "Esta%C3%A7%C3%B5es_Hidrometeorol%C3%B3gicas_SNIRH/"
    "FeatureServer/0/query"
)


class AnaEstacoesErro(Exception):
    """Erro ao consultar as estações hidrometeorológicas da ANA/SNIRH."""
    pass


def _normalizar_texto(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _normalizar_nome_rio(valor):
    texto = _normalizar_texto(valor)

    for prefixo in (
        "rio ",
        "ribeirao ",
        "corrego ",
    ):
        if texto.startswith(prefixo):
            texto = texto[len(prefixo):]

    return texto.strip()


def _sim(valor):
    return _normalizar_texto(valor) in {
        "sim", "s", "1", "true", "ativo", "operando"
    }


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _codigo_estacao(valor):
    if valor is None:
        return ""

    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor).strip()


def _distancia_haversine_km(
    latitude_1,
    longitude_1,
    latitude_2,
    longitude_2,
):
    raio_terra_km = 6371.0088

    lat1 = math.radians(latitude_1)
    lon1 = math.radians(longitude_1)
    lat2 = math.radians(latitude_2)
    lon2 = math.radians(longitude_2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return raio_terra_km * c


def _consultar_estacoes(latitude, longitude, raio_km):
    parametros = {
        "where": "TipoEstacao = 'Fluviométrica'",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "distance": raio_km,
        "units": "esriSRUnit_Kilometer",
        "outFields": (
            "Codigo,Nome,TipoEstacao,Operando,"
            "CodigoAdicional,Latitude,Longitude,Altitude,AreaDrenagem,"
            "Bacia,SubBacia,Rio,UF,Municipio,"
            "ResponsavelSigla,OperadoraSigla,"
            "MedicaoDescargaLiquida,MedicaoDescargaLiquidaInicio,"
            "EstacaoTelemetrica,EstacaoTelemetricaInicio"
        ),
        "returnGeometry": "true",
        "outSR": 4326,
        "resultRecordCount": 1000,
        "f": "json",
    }

    try:
        resposta = requests.get(
            URL_ESTACOES_ANA,
            params=parametros,
            timeout=(4, 15),
        )
        resposta.raise_for_status()

    except requests.RequestException as erro:
        raise AnaEstacoesErro(
            "Não foi possível consultar as estações "
            f"fluviométricas da ANA/SNIRH: {erro}"
        ) from erro

    try:
        dados = resposta.json()

    except ValueError as erro:
        raise AnaEstacoesErro(
            "A ANA/SNIRH retornou uma resposta de estações "
            "que não pôde ser interpretada."
        ) from erro

    if dados.get("error"):
        mensagem = dados["error"].get("message") or "Erro não identificado."
        raise AnaEstacoesErro(
            "Erro retornado pelo serviço de estações "
            f"da ANA/SNIRH: {mensagem}"
        )

    return dados.get("features", [])


def _montar_estacao(
    feature,
    latitude_referencia,
    longitude_referencia,
    nome_recurso,
):
    atributos = feature.get("attributes") or {}
    geometria = feature.get("geometry") or {}

    latitude = _numero(atributos.get("Latitude"))
    longitude = _numero(atributos.get("Longitude"))

    if latitude is None:
        latitude = _numero(geometria.get("y"))

    if longitude is None:
        longitude = _numero(geometria.get("x"))

    if latitude is None or longitude is None:
        return None

    rio = str(atributos.get("Rio") or "").strip()

    nome_recurso_normalizado = _normalizar_nome_rio(nome_recurso)
    rio_normalizado = _normalizar_nome_rio(rio)

    mesmo_rio = bool(
        nome_recurso_normalizado
        and rio_normalizado
        and (
            nome_recurso_normalizado == rio_normalizado
            or nome_recurso_normalizado in rio_normalizado
            or rio_normalizado in nome_recurso_normalizado
        )
    )

    distancia_km = _distancia_haversine_km(
        latitude_referencia,
        longitude_referencia,
        latitude,
        longitude,
    )

    codigo = _codigo_estacao(atributos.get("Codigo"))

    return {
        "id": codigo,
        "codigo": codigo,
        "codigo_adicional": str(
            atributos.get("CodigoAdicional") or ""
        ).strip(),
        "nome": str(
            atributos.get("Nome") or "Estação sem nome"
        ).strip(),
        "rio": rio or "Não informado",
        "mesmo_rio": mesmo_rio,
        "operando": _sim(atributos.get("Operando")),
        "mede_vazao": _sim(atributos.get("MedicaoDescargaLiquida")),
        "telemetrica": _sim(atributos.get("EstacaoTelemetrica")),
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "distancia_km": round(distancia_km, 2),
        "area_drenagem_km2": _numero(atributos.get("AreaDrenagem")),
        "municipio": str(atributos.get("Municipio") or "").strip(),
        "uf": str(atributos.get("UF") or "").strip(),
        "bacia": str(atributos.get("Bacia") or "").strip(),
        "sub_bacia": str(atributos.get("SubBacia") or "").strip(),
        "responsavel": str(
            atributos.get("ResponsavelSigla") or ""
        ).strip(),
        "operadora": str(
            atributos.get("OperadoraSigla") or ""
        ).strip(),
    }


def _obter_estacoes_fluviometricas_proximas_sem_cache(
    latitude,
    longitude,
    nome_recurso=None,
    estacao_selecionada=None,
    limite=3,
):
    """
    Localiza estações fluviométricas próximas ao recurso hídrico escolhido.

    Prioridade preliminar:
    1. estação associada ao mesmo rio pelo nome;
    2. em operação;
    3. com medição de descarga líquida;
    4. telemétrica;
    5. menor distância geométrica.

    A distância é um filtro de proximidade e não prova equivalência
    hidrológica entre a estação e o ponto de captação.
    """

    features = []
    raio_encontrado = None

    for raio_km in (50, 100):
        features = _consultar_estacoes(
            latitude,
            longitude,
            raio_km,
        )
        raio_encontrado = raio_km

        if features:
            break

    estacoes = []

    for feature in features:
        estacao = _montar_estacao(
            feature,
            latitude,
            longitude,
            nome_recurso,
        )

        if estacao:
            estacoes.append(estacao)

    estacoes.sort(
        key=lambda item: (
            0 if item["mesmo_rio"] else 1,
            0 if item["operando"] else 1,
            0 if item["mede_vazao"] else 1,
            0 if item["telemetrica"] else 1,
            item["distancia_km"],
        )
    )

    candidatos = estacoes[:limite]

    referencia = None

    if estacao_selecionada:
        referencia = next(
            (
                item
                for item in candidatos
                if str(item["codigo"]) == str(estacao_selecionada)
            ),
            None,
        )

    if referencia is None:
        referencia = candidatos[0] if candidatos else None

    for item in candidatos:
        item["selecionada"] = bool(
            referencia and item["codigo"] == referencia["codigo"]
        )

    return {
        "encontrado": bool(referencia),
        "referencia": referencia,
        "candidatos": candidatos,
        "raio_busca_km": raio_encontrado,
        "total_encontradas": len(estacoes),
        "fonte": "ANA/SNIRH - Rede Hidrometeorológica Nacional",
        "criterio": (
            "mesmo rio → operação → medição de vazão "
            "→ telemetria → distância"
        ),
    }



def obter_estacoes_fluviometricas_proximas(
    latitude,
    longitude,
    nome_recurso=None,
    estacao_selecionada=None,
    limite=3,
):
    """Consulta de estações com cache de 6 horas."""
    chave = (
        "h2v:estacoes:"
        f"{round(float(latitude), 4)}:"
        f"{round(float(longitude), 4)}:"
        f"{str(nome_recurso or '').strip().lower()}:"
        f"{str(estacao_selecionada or 'auto')}:"
        f"{int(limite)}"
    )

    armazenado = cache.get(chave)
    if armazenado is not None:
        return armazenado

    resultado = _obter_estacoes_fluviometricas_proximas_sem_cache(
        latitude=latitude,
        longitude=longitude,
        nome_recurso=nome_recurso,
        estacao_selecionada=estacao_selecionada,
        limite=limite,
    )

    cache.set(chave, resultado, 60 * 60 * 6)
    return resultado
