import os
import statistics
import time
from pathlib import Path

import requests

from django.core.cache import cache
from dotenv import load_dotenv


BASE_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas"
)

PROJETO_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJETO_DIR / ".env")


class HidroWebErro(Exception):
    """Erro ao consultar a API HidroWebService da ANA."""
    pass


_TOKEN_CACHE = {
    "token": None,
    "expira_em": 0,
}


def obter_configuracao_hidroweb():
    identificador = os.getenv(
        "ANA_HIDROWEB_IDENTIFICADOR",
        "",
    ).strip()

    senha = os.getenv(
        "ANA_HIDROWEB_SENHA",
        "",
    ).strip()

    return {
        "configurado": bool(identificador and senha),
        "identificador": identificador,
    }


def _extrair_token(dados):
    items = dados.get("items")

    if isinstance(items, list):
        items = items[0] if items else {}

    if not isinstance(items, dict):
        items = {}

    return (
        items.get("tokenautenticacao")
        or items.get("tokenAutenticacao")
        or items.get("token")
    )


def _obter_token():
    agora = time.time()

    if (
        _TOKEN_CACHE["token"]
        and agora < _TOKEN_CACHE["expira_em"]
    ):
        return _TOKEN_CACHE["token"]

    configuracao = obter_configuracao_hidroweb()

    if not configuracao["configurado"]:
        raise HidroWebErro(
            "Credenciais da API HidroWebService não configuradas."
        )

    senha = os.getenv(
        "ANA_HIDROWEB_SENHA",
        "",
    ).strip()

    try:
        resposta = requests.get(
            f"{BASE_URL}/OAUth/v1",
            headers={
                "Identificador": configuracao["identificador"],
                "Senha": senha,
            },
            timeout=30,
        )
        resposta.raise_for_status()

    except requests.RequestException as erro:
        raise HidroWebErro(
            "Não foi possível autenticar na API HidroWebService: "
            f"{erro}"
        ) from erro

    try:
        dados = resposta.json()

    except ValueError as erro:
        raise HidroWebErro(
            "A autenticação HidroWebService retornou uma resposta inválida."
        ) from erro

    token = _extrair_token(dados)

    if not token:
        mensagem = dados.get("message") or "Token não retornado."
        raise HidroWebErro(
            "A ANA não retornou um token válido: "
            f"{mensagem}"
        )

    # A documentação informa validade de 60 minutos.
    # Guardamos por 50 minutos para evitar autenticações repetitivas
    # e ainda manter uma margem antes da expiração.
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expira_em"] = agora + 50 * 60

    return token


def _numero(valor):
    if valor in (None, "", "null", "None"):
        return None

    try:
        return float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _status_valido(valor):
    if valor in (None, ""):
        return True

    return str(valor).strip() == "0"


def _obter_vazao_30_dias_sem_cache(codigo_estacao):
    """
    Consulta a série telemétrica adotada dos últimos 30 dias.

    Somente valores de Vazao_Adotada com QC 0 (ou sem status)
    entram no resumo estatístico.
    """

    token = _obter_token()

    parametros = {
        "CodigoDaEstacao": str(codigo_estacao),
        "TipoFiltroData": "DATA_LEITURA",
        "RangeIntervaloDeBusca": "DIAS_30",
    }

    try:
        resposta = requests.get(
            f"{BASE_URL}/HidroinfoanaSerieTelemetricaAdotada/v1",
            params=parametros,
            headers={
                "Authorization": f"Bearer {token}",
            },
            timeout=(4, 18),
        )
        resposta.raise_for_status()

    except requests.RequestException as erro:
        raise HidroWebErro(
            "Não foi possível consultar a série de vazão da estação: "
            f"{erro}"
        ) from erro

    try:
        dados = resposta.json()

    except ValueError as erro:
        raise HidroWebErro(
            "A API HidroWebService retornou uma resposta de vazão inválida."
        ) from erro

    items = dados.get("items", [])

    if not isinstance(items, list):
        items = []

    registros_validos = []

    for item in items:
        if not isinstance(item, dict):
            continue

        vazao = _numero(item.get("Vazao_Adotada"))
        status = item.get("Vazao_Adotada_Status")

        if (
            vazao is None
            or vazao < 0
            or not _status_valido(status)
        ):
            continue

        registros_validos.append(
            {
                "vazao": vazao,
                "data": str(item.get("Data_Hora_Medicao") or ""),
                "status": status,
            }
        )

    if not registros_validos:
        return {
            "disponivel": False,
            "codigo_estacao": str(codigo_estacao),
            "registros_validos": 0,
            "periodo": "30 dias",
        }

    registros_validos.sort(key=lambda item: item["data"])
    valores = [item["vazao"] for item in registros_validos]
    ultimo = registros_validos[-1]

    return {
        "disponivel": True,
        "codigo_estacao": str(codigo_estacao),
        "periodo": "30 dias",
        "registros_validos": len(valores),
        "vazao_atual_m3s": round(ultimo["vazao"], 3),
        "data_ultima_medicao": ultimo["data"],
        "vazao_media_m3s": round(statistics.fmean(valores), 3),
        "vazao_minima_m3s": round(min(valores), 3),
        "vazao_maxima_m3s": round(max(valores), 3),
    }


def comparar_demanda_com_vazao(demanda_m3_dia, dados_vazao):
    """
    Compara a demanda teórica da planta com a vazão observada.

    Este indicador é físico e preliminar. Não representa
    disponibilidade hídrica outorgável, vazão de referência para
    concessão de uso ou autorização de captação.
    """

    demanda_m3s = float(demanda_m3_dia) / 86400

    resultado = {
        "demanda_m3_dia": round(float(demanda_m3_dia), 3),
        "demanda_m3s": round(demanda_m3s, 8),
    }

    if not dados_vazao.get("disponivel"):
        return resultado

    vazao_media = dados_vazao.get("vazao_media_m3s")
    vazao_atual = dados_vazao.get("vazao_atual_m3s")

    if vazao_media and vazao_media > 0:
        resultado["demanda_sobre_media_percentual"] = round(
            (demanda_m3s / vazao_media) * 100,
            6,
        )

    if vazao_atual and vazao_atual > 0:
        resultado["demanda_sobre_atual_percentual"] = round(
            (demanda_m3s / vazao_atual) * 100,
            6,
        )

    return resultado



def obter_vazao_30_dias(codigo_estacao):
    """Vazão telemétrica com cache curto para não repetir a mesma leitura."""
    chave = f"h2v:hidroweb:vazao30:{str(codigo_estacao).strip()}"

    armazenado = cache.get(chave)
    if armazenado is not None:
        return armazenado

    resultado = _obter_vazao_30_dias_sem_cache(codigo_estacao)
    cache.set(chave, resultado, 60 * 5)
    return resultado
