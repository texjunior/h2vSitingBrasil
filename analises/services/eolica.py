import math


class SimulacaoEolicaErro(Exception):
    """Erro ao estimar o recurso eólico."""
    pass


def _numero(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numero) or numero < 0:
        return None

    return numero


def _velocidade_100m(vento_10m, vento_50m):
    """
    Extrapola a velocidade de 50 m para 100 m usando a lei de potência.

    O expoente alfa não é fixado arbitrariamente: ele é inferido para
    cada dia a partir das velocidades NASA POWER de 10 m e 50 m.

        alfa = ln(V50 / V10) / ln(50 / 10)
        V100 = V50 * (100 / 50) ** alfa
    """
    v10 = _numero(vento_10m)
    v50 = _numero(vento_50m)

    if v10 is None or v50 is None or v10 <= 0 or v50 <= 0:
        return None

    try:
        alfa = math.log(v50 / v10) / math.log(5.0)
        v100 = v50 * (2.0 ** alfa)
    except (ValueError, OverflowError, ZeroDivisionError):
        return None

    if not math.isfinite(v100) or v100 < 0:
        return None

    return v100, alfa


def _potencia_relativa_turbina(velocidade):
    """
    Curva de potência NORMALIZADA e simplificada de uma turbina de referência.

    Não representa um fabricante específico. Serve apenas para triagem:
    - cut-in: 3 m/s
    - nominal: 12 m/s
    - cut-out: 25 m/s
    - entre cut-in e nominal: interpolação cúbica normalizada.
    """
    cut_in = 3.0
    nominal = 12.0
    cut_out = 25.0

    if velocidade < cut_in or velocidade >= cut_out:
        return 0.0

    if velocidade >= nominal:
        return 1.0

    numerador = velocidade ** 3 - cut_in ** 3
    denominador = nominal ** 3 - cut_in ** 3

    return max(0.0, min(1.0, numerador / denominador))


def _classificar_vento(velocidade_media_100m):
    """
    Faixas PRELIMINARES do protótipo para leitura visual.

    Elas não substituem uma classificação normativa ou estudo eólico de sítio.
    """
    if velocidade_media_100m >= 7.0:
        return {
            "nivel": "Alto",
            "classe": "alto",
            "mensagem": (
                "O vento a 100 m apresenta potencial forte para aprofundar "
                "a avaliação eólica neste local."
            ),
        }

    if velocidade_media_100m >= 6.0:
        return {
            "nivel": "Médio",
            "classe": "medio",
            "mensagem": (
                "O recurso eólico é intermediário e merece comparação com "
                "a alternativa solar e com dados eólicos de maior resolução."
            ),
        }

    return {
        "nivel": "Baixo",
        "classe": "baixo",
        "mensagem": (
            "O vento médio estimado é baixo para priorização eólica nesta "
            "triagem preliminar."
        ),
    }


def simular_recurso_eolico(serie_10m, serie_50m):
    """
    Estima o recurso eólico a 100 m usando séries diárias NASA POWER.

    A geração específica é calculada para 1 MW de potência nominal usando
    uma curva de potência normalizada simplificada. Como a entrada é diária,
    esse resultado é adequado para PRÉ-VIABILIDADE, não para projeto executivo.
    """
    if not isinstance(serie_10m, dict) or not isinstance(serie_50m, dict):
        raise SimulacaoEolicaErro(
            "Séries de vento da NASA POWER indisponíveis para esta análise."
        )

    datas = sorted(set(serie_10m) & set(serie_50m))

    velocidades_10m = []
    velocidades_50m = []
    velocidades_100m = []
    alfas = []
    potencias_relativas = []

    for data in datas:
        estimativa = _velocidade_100m(
            serie_10m.get(data),
            serie_50m.get(data),
        )

        if estimativa is None:
            continue

        velocidade_100m, alfa = estimativa

        # Guardamos também os valores de entrada usados no mesmo dia.
        # Isso permite explicar no front-end, de forma auditável, de onde
        # veio o valor final apresentado ao usuário.
        velocidades_10m.append(float(serie_10m.get(data)))
        velocidades_50m.append(float(serie_50m.get(data)))
        velocidades_100m.append(velocidade_100m)
        alfas.append(alfa)
        potencias_relativas.append(
            _potencia_relativa_turbina(velocidade_100m)
        )

    if not velocidades_100m:
        raise SimulacaoEolicaErro(
            "Não foram encontrados dados de vento válidos para estimar 100 m."
        )

    dias_validos = len(velocidades_100m)
    velocidade_media = sum(velocidades_100m) / dias_validos

    # Média de 0,5 * rho * v³, em vez de aplicar v³ apenas à média.
    densidade_ar = 1.225
    densidade_potencia = sum(
        0.5 * densidade_ar * (velocidade ** 3)
        for velocidade in velocidades_100m
    ) / dias_validos

    fator_capacidade = sum(potencias_relativas) / len(potencias_relativas)

    # Anualização da energia de uma máquina normalizada de 1 MW.
    # 1 MW * 8760 h * CF = MWh/ano.
    geracao_especifica = fator_capacidade * 8760.0

    classificacao = _classificar_vento(velocidade_media)

    return {
        "fonte": "NASA POWER",
        "altura_referencia_m": 100,
        "dias_analisados": dias_validos,
        "velocidade_media_10m": round(
            sum(velocidades_10m) / dias_validos,
            2,
        ),
        "velocidade_media_50m": round(
            sum(velocidades_50m) / dias_validos,
            2,
        ),
        "soma_velocidade_100m": round(
            sum(velocidades_100m),
            3,
        ),
        "velocidade_media_100m": round(velocidade_media, 2),
        "velocidade_minima_100m": round(min(velocidades_100m), 2),
        "velocidade_maxima_100m": round(max(velocidades_100m), 2),
        "expoente_cisalhamento_medio": round(sum(alfas) / len(alfas), 3),
        "densidade_potencia_w_m2": round(densidade_potencia, 1),
        "fator_capacidade_referencia": round(fator_capacidade * 100, 1),
        "geracao_especifica_mwh_mw_ano": round(geracao_especifica, 0),
        "classificacao": classificacao,
        "modelo_turbina": (
            "Curva normalizada simplificada: cut-in 3 m/s, nominal 12 m/s, "
            "cut-out 25 m/s"
        ),
        "metodo_altura": (
            "Extrapolação 50→100 m por lei de potência com alfa inferido "
            "diariamente a partir de WS10M e WS50M"
        ),
    }


def gerar_recomendacao_energetica(dados_solares, dados_eolicos):
    """
    Recomendação de TRIAGEM energética, sem incorporar CAPEX/OPEX.

    A recomendação usa apenas a classe do recurso solar e eólico. Não deve ser
    interpretada como decisão financeira de investimento.
    """
    irradiacao = float(dados_solares.get("irradiacao_media", 0) or 0)

    if irradiacao >= 5.5:
        solar_score = 2
        solar_nivel = "Alto"
    elif irradiacao >= 4.5:
        solar_score = 1
        solar_nivel = "Médio"
    else:
        solar_score = 0
        solar_nivel = "Baixo"

    vento_nivel = dados_eolicos["classificacao"]["nivel"]
    vento_score = {
        "Baixo": 0,
        "Médio": 1,
        "Alto": 2,
    }.get(vento_nivel, 0)

    if solar_score == 2 and vento_score == 2:
        titulo = "Avaliar solução híbrida solar + eólica"
        classe = "hibrida"
        texto = (
            "Os dois recursos aparecem fortes nesta triagem. A combinação pode "
            "reduzir a dependência de uma única fonte e merece simulação horária."
        )
    elif vento_score > solar_score:
        titulo = "Prioridade energética: eólica"
        classe = "eolica"
        texto = (
            "O recurso eólico ficou mais favorável que o solar nesta leitura. "
            "Vale aprofundar a estimativa com série horária e curva real de turbina."
        )
    elif solar_score > vento_score:
        titulo = "Prioridade energética: solar"
        classe = "solar"
        texto = (
            "O recurso solar ficou mais favorável que o eólico nesta leitura. "
            "A geração fotovoltaica deve permanecer como primeira alternativa a aprofundar."
        )
    elif solar_score == 1 and vento_score == 1:
        titulo = "Comparar solar e eólica em cenário híbrido"
        classe = "hibrida"
        texto = (
            "Os dois recursos aparecem em nível intermediário. Uma análise horária "
            "de complementaridade pode definir a melhor combinação."
        )
    else:
        titulo = "Atratividade energética baixa nesta triagem"
        classe = "atencao"
        texto = (
            "Nem solar nem eólica se destacaram. O ponto deve ser comparado com "
            "outras localidades antes de avançar."
        )

    return {
        "titulo": titulo,
        "classe": classe,
        "texto": texto,
        "solar_nivel": solar_nivel,
        "eolica_nivel": vento_nivel,
        "observacao": (
            "Recomendação técnica preliminar de recurso energético; não inclui "
            "custos, conexão elétrica, terreno, licenciamento ou financiamento."
        ),
    }
