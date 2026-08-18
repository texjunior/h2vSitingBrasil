import math
import re
import unicodedata

import requests

from django.core.cache import cache


URL_HIDROGRAFIA_ANA = (
    "https://portal1.snirh.gov.br/server/rest/services/"
    "dados_abertos/Hidrografia/MapServer/0/query"
)


class AnaHidrografiaErro(Exception):
    """Erro ao consultar ou processar a hidrografia da ANA/SNIRH."""
    pass


def _projetar_localmente(latitude, longitude, latitude_ref, longitude_ref):
    km_por_grau_lat = 110.574
    km_por_grau_lon = 111.320 * math.cos(math.radians(latitude_ref))

    x = (longitude - longitude_ref) * km_por_grau_lon
    y = (latitude - latitude_ref) * km_por_grau_lat

    return x, y


def _distancia_ponto_segmento(latitude_ref, longitude_ref, inicio, fim):
    lon_a, lat_a = inicio
    lon_b, lat_b = fim

    ax, ay = _projetar_localmente(
        lat_a, lon_a, latitude_ref, longitude_ref
    )
    bx, by = _projetar_localmente(
        lat_b, lon_b, latitude_ref, longitude_ref
    )

    dx = bx - ax
    dy = by - ay
    comprimento_quadrado = dx * dx + dy * dy

    if comprimento_quadrado == 0:
        t = 0.0
    else:
        t = -(ax * dx + ay * dy) / comprimento_quadrado
        t = max(0.0, min(1.0, t))

    ponto_x = ax + t * dx
    ponto_y = ay + t * dy

    distancia = math.sqrt(ponto_x * ponto_x + ponto_y * ponto_y)

    latitude_proxima = lat_a + t * (lat_b - lat_a)
    longitude_proxima = lon_a + t * (lon_b - lon_a)

    return distancia, latitude_proxima, longitude_proxima


def _distancia_ate_geometria(latitude, longitude, caminhos):
    melhor = None

    for caminho in caminhos or []:
        if not caminho:
            continue

        if len(caminho) == 1:
            lon, lat = caminho[0]
            x, y = _projetar_localmente(lat, lon, latitude, longitude)
            distancia = math.sqrt(x * x + y * y)

            candidato = {
                "distancia_km": distancia,
                "latitude_proxima": lat,
                "longitude_proxima": lon,
                "caminho": caminho,
                "indice_segmento": 0,
            }

            if melhor is None or distancia < melhor["distancia_km"]:
                melhor = candidato

            continue

        for indice in range(len(caminho) - 1):
            inicio = caminho[indice]
            fim = caminho[indice + 1]

            distancia, latitude_proxima, longitude_proxima = (
                _distancia_ponto_segmento(
                    latitude,
                    longitude,
                    inicio,
                    fim,
                )
            )

            if melhor is None or distancia < melhor["distancia_km"]:
                melhor = {
                    "distancia_km": distancia,
                    "latitude_proxima": latitude_proxima,
                    "longitude_proxima": longitude_proxima,
                    "caminho": caminho,
                    "indice_segmento": indice,
                }

    return melhor


def _recortar_caminho_local(caminho, indice_segmento, margem_vertices=10):
    if not caminho:
        return []

    if len(caminho) <= 2:
        return caminho

    inicio = max(0, indice_segmento - margem_vertices)
    fim = min(len(caminho), indice_segmento + margem_vertices + 2)

    recorte = caminho[inicio:fim]

    return recorte if len(recorte) >= 2 else caminho


def _normalizar_texto(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _nome_valido(nome):
    normalizado = _normalizar_texto(nome)

    if not normalizado:
        return False

    invalidos = {
        "sem nome",
        "sem denominacao",
        "nao informado",
        "curso d'agua sem nome cadastrado",
        "curso dagua sem nome cadastrado",
    }

    return normalizado not in invalidos


def _id_recurso(atributos):
    codigo = str(atributos.get("COCURSODAG") or "").strip()
    if codigo:
        return f"curso:{codigo}"

    nome = _normalizar_texto(atributos.get("NORIOCOMP"))
    if nome:
        return f"nome:{nome}"

    return f"obj:{atributos.get('OBJECTID', '')}"


def _consultar_raio(latitude, longitude, raio_km):
    parametros = {
        "where": "1=1",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "distance": raio_km,
        "units": "esriSRUnit_Kilometer",
        "outFields": (
            "OBJECTID,COCURSODAG,COBACIA,NORIOCOMP,DEDOMINIAL"
        ),
        "returnGeometry": "true",
        "outSR": 4326,
        "resultRecordCount": 2000,
        "f": "json",
    }

    try:
        resposta = requests.get(
            URL_HIDROGRAFIA_ANA,
            params=parametros,
            timeout=(4, 15),
        )
        resposta.raise_for_status()
    except requests.RequestException as erro:
        raise AnaHidrografiaErro(
            f"Não foi possível acessar a hidrografia da ANA/SNIRH: {erro}"
        ) from erro

    try:
        dados = resposta.json()
    except ValueError as erro:
        raise AnaHidrografiaErro(
            "A ANA/SNIRH retornou uma resposta que não pôde ser interpretada."
        ) from erro

    if dados.get("error"):
        mensagem = dados["error"].get("message") or "Erro não identificado."
        raise AnaHidrografiaErro(
            f"Erro retornado pelo serviço da ANA/SNIRH: {mensagem}"
        )

    return dados.get("features", [])


def _montar_candidato(recurso, distancia, raio_busca_km):
    atributos = recurso.get("attributes", {})

    nome_original = str(atributos.get("NORIOCOMP") or "").strip()
    identificado = _nome_valido(nome_original)

    nome = (
        nome_original
        if identificado
        else "Curso d'água sem nome cadastrado"
    )

    dominio = str(atributos.get("DEDOMINIAL") or "Não informado").strip()

    caminho_local = _recortar_caminho_local(
        distancia["caminho"],
        distancia["indice_segmento"],
    )

    geometria_leaflet = [
        [ponto[1], ponto[0]]
        for ponto in caminho_local
        if len(ponto) >= 2
    ]

    return {
        "id": _id_recurso(atributos),
        "nome": nome,
        "identificado": identificado,
        "dominio": dominio,
        "codigo_curso": str(atributos.get("COCURSODAG") or ""),
        "codigo_bacia": str(atributos.get("COBACIA") or ""),
        "objectid": atributos.get("OBJECTID"),
        "distancia_km": round(distancia["distancia_km"], 2),
        "latitude_proxima": round(distancia["latitude_proxima"], 6),
        "longitude_proxima": round(distancia["longitude_proxima"], 6),
        "geometria": geometria_leaflet,
        "raio_busca_km": raio_busca_km,
    }


def _obter_recursos_hidricos_proximos_sem_cache(
    latitude,
    longitude,
    recurso_selecionado=None,
    limite=3,
):
    """
    Retorna uma análise hídrica preliminar com:
    - trecho geometricamente mais próximo;
    - até 3 cursos candidatos;
    - curso de referência selecionado.

    Cursos identificados recebem prioridade sobre trechos anônimos,
    mas a distância continua sendo exibida para transparência.
    """

    # Começamos com uma janela regional de 15 km para evitar que
    # pequenos trechos urbanos dominem a seleção. Se não houver dados,
    # ampliamos progressivamente.
    raios_busca = [15, 30, 60]
    recursos = []
    raio_encontrado = None

    for raio_km in raios_busca:
        recursos = _consultar_raio(latitude, longitude, raio_km)
        raio_encontrado = raio_km

        if recursos:
            break

    if not recursos:
        return {
            "encontrado": False,
            "fonte": "ANA/SNIRH - Hidrografia",
            "raio_busca_km": raios_busca[-1],
            "candidatos": [],
            "trecho_mais_proximo": None,
            "referencia": None,
        }

    grupos = {}
    trecho_mais_proximo = None

    for recurso in recursos:
        geometria = recurso.get("geometry") or {}
        caminhos = geometria.get("paths", [])
        distancia = _distancia_ate_geometria(
            latitude,
            longitude,
            caminhos,
        )

        if distancia is None:
            continue

        candidato = _montar_candidato(
            recurso,
            distancia,
            raio_encontrado,
        )

        if (
            trecho_mais_proximo is None
            or candidato["distancia_km"]
            < trecho_mais_proximo["distancia_km"]
        ):
            trecho_mais_proximo = candidato

        chave = candidato["id"]
        existente = grupos.get(chave)

        if (
            existente is None
            or candidato["distancia_km"] < existente["distancia_km"]
        ):
            grupos[chave] = candidato

    candidatos = list(grupos.values())

    # Primeiro cursos identificados, depois anônimos; dentro de cada grupo,
    # menor distância primeiro.
    candidatos.sort(
        key=lambda item: (
            0 if item["identificado"] else 1,
            item["distancia_km"],
        )
    )

    candidatos = candidatos[:limite]

    if not candidatos and trecho_mais_proximo:
        candidatos = [trecho_mais_proximo]

    referencia = None

    if recurso_selecionado:
        referencia = next(
            (
                item
                for item in candidatos
                if item["id"] == recurso_selecionado
            ),
            None,
        )

    if referencia is None:
        referencia = candidatos[0] if candidatos else trecho_mais_proximo

    for item in candidatos:
        item["selecionado"] = bool(
            referencia and item["id"] == referencia["id"]
        )

    return {
        "encontrado": bool(referencia),
        "fonte": "ANA/SNIRH - Hidrografia",
        "base": "Base hidrográfica ANA - serviço REST público",
        "raio_busca_km": raio_encontrado,
        "total_trechos": len(recursos),
        "total_cursos": len(grupos),
        "trecho_mais_proximo": trecho_mais_proximo,
        "candidatos": candidatos,
        "referencia": referencia,
    }


# Compatibilidade temporária com chamadas anteriores.
def obter_recurso_hidrico_mais_proximo(latitude, longitude):
    dados = obter_recursos_hidricos_proximos(latitude, longitude)
    referencia = dados.get("referencia")

    if not referencia:
        return {
            "encontrado": False,
            "fonte": dados.get("fonte"),
            "raio_busca_km": dados.get("raio_busca_km"),
        }

    return {
        "encontrado": True,
        **referencia,
        "fonte": dados.get("fonte"),
        "base": dados.get("base"),
        "tipo_geometria": "Eixo de drenagem",
    }



def obter_recursos_hidricos_proximos(
    latitude,
    longitude,
    recurso_selecionado=None,
    limite=3,
):
    """Consulta hidrográfica com cache para evitar chamadas repetidas."""
    recurso_chave = str(recurso_selecionado or "auto").strip()
    chave = (
        "h2v:hidrografia:"
        f"{round(float(latitude), 4)}:"
        f"{round(float(longitude), 4)}:"
        f"{recurso_chave}:{int(limite)}"
    )

    armazenado = cache.get(chave)
    if armazenado is not None:
        return armazenado

    resultado = _obter_recursos_hidricos_proximos_sem_cache(
        latitude=latitude,
        longitude=longitude,
        recurso_selecionado=recurso_selecionado,
        limite=limite,
    )

    cache.set(chave, resultado, 60 * 60 * 24)
    return resultado
