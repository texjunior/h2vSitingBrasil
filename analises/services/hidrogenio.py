class SimulacaoErro(Exception):
    """Erro nos parâmetros da simulação."""
    pass


def simular_hidrogenio(
    irradiacao_media,
    irradiacao_anual,
    potencia_solar_mwp,
    performance_ratio_percentual,
    potencia_eletrolisador_mw,
    consumo_especifico_kwh_kg,
):
    """
    Estimativa preliminar da produção de hidrogênio verde
    alimentada por geração fotovoltaica.
    """

    if potencia_solar_mwp <= 0:
        raise SimulacaoErro("A potência solar deve ser maior que zero.")

    if potencia_eletrolisador_mw <= 0:
        raise SimulacaoErro(
            "A potência do eletrólisador deve ser maior que zero."
        )

    if not 0 < performance_ratio_percentual <= 100:
        raise SimulacaoErro("O PR deve estar entre 0 e 100%.")

    if consumo_especifico_kwh_kg <= 0:
        raise SimulacaoErro(
            "O consumo específico deve ser maior que zero."
        )

    performance_ratio = performance_ratio_percentual / 100

    potencia_solar_kwp = potencia_solar_mwp * 1000
    potencia_eletrolisador_kw = potencia_eletrolisador_mw * 1000

    # Geração fotovoltaica estimada.
    energia_solar_diaria_kwh = (
        potencia_solar_kwp * irradiacao_media * performance_ratio
    )

    energia_solar_anual_kwh = (
        potencia_solar_kwp * irradiacao_anual * performance_ratio
    )

    # Limite energético do eletrólisador.
    capacidade_eletrolisador_dia_kwh = potencia_eletrolisador_kw * 24
    capacidade_eletrolisador_ano_kwh = (
        capacidade_eletrolisador_dia_kwh * 365
    )

    energia_util_diaria_kwh = min(
        energia_solar_diaria_kwh,
        capacidade_eletrolisador_dia_kwh,
    )

    energia_util_anual_kwh = min(
        energia_solar_anual_kwh,
        capacidade_eletrolisador_ano_kwh,
    )

    excedente_diario_kwh = max(
        energia_solar_diaria_kwh - capacidade_eletrolisador_dia_kwh,
        0,
    )

    excedente_anual_kwh = max(
        energia_solar_anual_kwh - capacidade_eletrolisador_ano_kwh,
        0,
    )

    h2_dia_kg = energia_util_diaria_kwh / consumo_especifico_kwh_kg
    h2_ano_kg = energia_util_anual_kwh / consumo_especifico_kwh_kg

    # Demanda teórica mínima de água: aproximadamente 9 L/kg de H2.
    agua_dia_m3 = (h2_dia_kg * 9) / 1000
    agua_ano_m3 = (h2_ano_kg * 9) / 1000

    aproveitamento_eletrolisador = (
        energia_util_anual_kwh
        / capacidade_eletrolisador_ano_kwh
        * 100
    )

    if energia_solar_diaria_kwh > capacidade_eletrolisador_dia_kwh:
        gargalo = "Eletrólisador"
    else:
        gargalo = "Energia solar"

    return {
        "potencia_solar_mwp": round(potencia_solar_mwp, 2),
        "performance_ratio": round(performance_ratio_percentual, 1),
        "potencia_eletrolisador_mw": round(potencia_eletrolisador_mw, 2),
        "consumo_especifico": round(consumo_especifico_kwh_kg, 2),
        "energia_solar_diaria_mwh": round(
            energia_solar_diaria_kwh / 1000, 2
        ),
        "energia_solar_anual_mwh": round(
            energia_solar_anual_kwh / 1000, 2
        ),
        "energia_util_diaria_mwh": round(
            energia_util_diaria_kwh / 1000, 2
        ),
        "energia_util_anual_mwh": round(
            energia_util_anual_kwh / 1000, 2
        ),
        "excedente_diario_mwh": round(
            excedente_diario_kwh / 1000, 2
        ),
        "excedente_anual_mwh": round(
            excedente_anual_kwh / 1000, 2
        ),
        "h2_dia_kg": round(h2_dia_kg, 2),
        "h2_ano_kg": round(h2_ano_kg, 2),
        "h2_ano_t": round(h2_ano_kg / 1000, 2),
        "agua_dia_m3": round(agua_dia_m3, 2),
        "agua_ano_m3": round(agua_ano_m3, 2),
        "aproveitamento_eletrolisador": round(
            aproveitamento_eletrolisador, 1
        ),
        "gargalo": gargalo,
    }
