from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from django.shortcuts import render

from .services.ana_estacoes import (
    AnaEstacoesErro,
    obter_estacoes_fluviometricas_proximas,
)
from .services.ana_hidrografia import (
    AnaHidrografiaErro,
    obter_recursos_hidricos_proximos,
)
from .services.ana_hidroweb import (
    HidroWebErro,
    comparar_demanda_com_vazao,
    obter_configuracao_hidroweb,
    obter_vazao_30_dias,
)
from .services.eolica import (
    SimulacaoEolicaErro,
    gerar_recomendacao_energetica,
    simular_recurso_eolico,
)
from .services.hidrogenio import (
    SimulacaoErro,
    simular_hidrogenio,
)
from .services.nasa_power import (
    NasaPowerErro,
    obter_dados_solares,
)


PARAMETROS_PADRAO = {
    "potencia_solar_mwp": 10,
    "performance_ratio": 80,
    "potencia_eletrolisador_mw": 5,
    "consumo_especifico": 52,
}


def converter_float(valor, padrao=None):
    """Converte valores GET para float, aceitando ponto ou vírgula."""
    if valor is None or valor == "":
        return padrao
    return float(str(valor).strip().replace(",", "."))


def mapa(request):
    inicio = perf_counter()

    contexto = {
        "parametros": PARAMETROS_PADRAO.copy(),
        "hidroweb_config": obter_configuracao_hidroweb(),
    }

    latitude_recebida = request.GET.get("latitude")
    longitude_recebida = request.GET.get("longitude")

    if latitude_recebida in (None, "") or longitude_recebida in (None, ""):
        return render(request, "analises/mapa.html", contexto)

    try:
        latitude = converter_float(latitude_recebida)
        longitude = converter_float(longitude_recebida)

        if not -90 <= latitude <= 90:
            raise ValueError("Latitude inválida.")
        if not -180 <= longitude <= 180:
            raise ValueError("Longitude inválida.")

        contexto["ponto_selecionado"] = {
            "latitude": latitude,
            "longitude": longitude,
        }

        potencia_solar_mwp = converter_float(
            request.GET.get("potencia_solar_mwp"),
            PARAMETROS_PADRAO["potencia_solar_mwp"],
        )
        performance_ratio = converter_float(
            request.GET.get("performance_ratio"),
            PARAMETROS_PADRAO["performance_ratio"],
        )
        potencia_eletrolisador_mw = converter_float(
            request.GET.get("potencia_eletrolisador_mw"),
            PARAMETROS_PADRAO["potencia_eletrolisador_mw"],
        )
        consumo_especifico = converter_float(
            request.GET.get("consumo_especifico"),
            PARAMETROS_PADRAO["consumo_especifico"],
        )

        contexto["parametros"] = {
            "potencia_solar_mwp": potencia_solar_mwp,
            "performance_ratio": performance_ratio,
            "potencia_eletrolisador_mw": potencia_eletrolisador_mw,
            "consumo_especifico": consumo_especifico,
        }

        dados_hidricos = None
        dados_estacoes = None
        dados_solares = None
        dados_eolicos = None

        # NASA e hidrografia não dependem uma da outra.
        # Antes eram executadas em série; agora rodam ao mesmo tempo.
        with ThreadPoolExecutor(max_workers=3) as executor:
            futuro_nasa = executor.submit(
                obter_dados_solares,
                latitude,
                longitude,
                2025,
            )

            futuro_hidrografia = executor.submit(
                obter_recursos_hidricos_proximos,
                latitude,
                longitude,
                request.GET.get("recurso"),
                3,
            )

            # Primeiro obtemos a hidrografia porque ela define onde procurar
            # as estações. Enquanto isso, a NASA continua trabalhando.
            try:
                dados_hidricos = futuro_hidrografia.result()
                contexto["dados_hidricos"] = dados_hidricos
            except AnaHidrografiaErro as erro_ana:
                contexto["erro_ana"] = str(erro_ana)

            futuro_estacoes = None
            referencia_hidrica = (
                dados_hidricos.get("referencia")
                if dados_hidricos
                else None
            )

            if referencia_hidrica:
                futuro_estacoes = executor.submit(
                    obter_estacoes_fluviometricas_proximas,
                    referencia_hidrica["latitude_proxima"],
                    referencia_hidrica["longitude_proxima"],
                    referencia_hidrica["nome"],
                    request.GET.get("estacao"),
                    3,
                )

            # Recuperamos a NASA depois; frequentemente ela já terminou.
            try:
                dados_solares = futuro_nasa.result()
                contexto["dados_solares"] = dados_solares
            except NasaPowerErro as erro_nasa:
                contexto["erro_nasa"] = str(erro_nasa)

            if futuro_estacoes is not None:
                try:
                    dados_estacoes = futuro_estacoes.result()
                    contexto["dados_estacoes"] = dados_estacoes
                except AnaEstacoesErro as erro_estacoes:
                    contexto["erro_estacoes"] = str(erro_estacoes)

        # A análise eólica reutiliza WS10M/WS50M da MESMA chamada NASA.
        # Portanto não acrescenta uma nova requisição externa.
        if dados_solares and dados_solares.get("vento", {}).get("disponivel"):
            try:
                dados_eolicos = simular_recurso_eolico(
                    dados_solares["vento"]["serie_10m"],
                    dados_solares["vento"]["serie_50m"],
                )
                contexto["dados_eolicos"] = dados_eolicos
                contexto["recomendacao_energetica"] = gerar_recomendacao_energetica(
                    dados_solares,
                    dados_eolicos,
                )
            except SimulacaoEolicaErro as erro_eolica:
                contexto["erro_eolica"] = str(erro_eolica)

        # Simulação é local e praticamente instantânea.
        resultado_simulacao = None
        if dados_solares:
            try:
                resultado_simulacao = simular_hidrogenio(
                    irradiacao_media=dados_solares["irradiacao_media"],
                    irradiacao_anual=dados_solares["irradiacao_anual"],
                    potencia_solar_mwp=potencia_solar_mwp,
                    performance_ratio_percentual=performance_ratio,
                    potencia_eletrolisador_mw=potencia_eletrolisador_mw,
                    consumo_especifico_kwh_kg=consumo_especifico,
                )
                contexto["resultado_simulacao"] = resultado_simulacao
            except SimulacaoErro as erro_simulacao:
                contexto["erro"] = str(erro_simulacao)

        # HidroWeb só é chamado quando houver credenciais e estação.
        estacao_referencia = (
            dados_estacoes.get("referencia")
            if dados_estacoes
            else None
        )

        monitoramento = {
            "configurado": contexto["hidroweb_config"]["configurado"],
            "estacao": estacao_referencia,
            "vazao": None,
            "comparacao": None,
        }

        if (
            resultado_simulacao
            and estacao_referencia
            and monitoramento["configurado"]
        ):
            try:
                dados_vazao = obter_vazao_30_dias(estacao_referencia["codigo"])
                monitoramento["vazao"] = dados_vazao
                monitoramento["comparacao"] = comparar_demanda_com_vazao(
                    resultado_simulacao["agua_dia_m3"],
                    dados_vazao,
                )
            except HidroWebErro as erro_hidroweb:
                contexto["erro_hidroweb"] = str(erro_hidroweb)

        contexto["monitoramento_hidroweb"] = monitoramento

    except (TypeError, ValueError) as erro:
        contexto["erro"] = str(erro)

    contexto["tempo_analise_segundos"] = round(perf_counter() - inicio, 2)

    return render(request, "analises/mapa.html", contexto)
