"""Perfis horários NASA POWER e pré-dimensionamento didático de H2V.

Os resultados são aproximações de pré-viabilidade. Não representam projeto executivo.
"""
from collections import defaultdict
from datetime import datetime
from math import ceil, isfinite
import requests
from django.core.cache import cache

URL = 'https://power.larc.nasa.gov/api/temporal/hourly/point'
PARAMS = 'ALLSKY_SFC_SW_DWN,WS10M,WS50M,T2M'

class PerfilEnergeticoErro(Exception):
    pass


def numero_valido(valor):
    try:
        x = float(valor)
        return x if isfinite(x) and x > -900 else None
    except (ValueError, TypeError):
        return None


def consultar_perfil(latitude, longitude, ano):
    latitude, longitude, ano = float(latitude), float(longitude), int(ano)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise PerfilEnergeticoErro('Coordenadas fora do intervalo permitido.')
    if not 2001 <= ano <= datetime.now().year - 1:
        raise PerfilEnergeticoErro('Escolha um ano completo entre 2001 e o ano anterior ao atual.')
    chave = f'h2v:hourly:v1:{latitude:.3f}:{longitude:.3f}:{ano}'
    dados = cache.get(chave)
    if dados is not None:
        return dados
    try:
        resposta = requests.get(URL, params={
            'parameters': PARAMS, 'community': 'RE', 'latitude': latitude,
            'longitude': longitude, 'start': f'{ano}0101', 'end': f'{ano}1231',
            'format': 'JSON', 'time-standard': 'LST',
        }, timeout=(8, 75))
        resposta.raise_for_status()
        raw = resposta.json()['properties']['parameter']
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        raise PerfilEnergeticoErro(f'Falha ao consultar a NASA POWER: {exc}') from exc
    solar = raw.get('ALLSKY_SFC_SW_DWN', {})
    if not solar:
        raise PerfilEnergeticoErro('A NASA POWER não retornou a série solar solicitada.')
    registros = []
    for chave_hora, irr in sorted(solar.items()):
        try:
            mes = int(chave_hora[4:6]); hora = int(chave_hora[8:10])
        except (ValueError, IndexError):
            continue
        s = numero_valido(irr)
        w10 = numero_valido(raw.get('WS10M', {}).get(chave_hora))
        w50 = numero_valido(raw.get('WS50M', {}).get(chave_hora))
        temp = numero_valido(raw.get('T2M', {}).get(chave_hora))
        if s is None or s < 0: s = None
        if w50 is None or w50 < 0: w50 = None
        if w10 is None or w10 < 0: w10 = None
        registros.append((mes, hora, s, w10, w50, temp))
    if len(registros) < 7000:
        raise PerfilEnergeticoErro('Série horária insuficiente para representar um ano.')
    cache.set(chave, registros, 60 * 60 * 24 * 30)
    return registros


def _potencia_eolica(vento, nominal_kw):
    # Curva de referência normalizada, apenas para estimativa inicial.
    if vento is None or vento < 3 or vento >= 25: return 0.0
    if vento >= 12: return nominal_kw
    return nominal_kw * (vento**3 - 3**3) / (12**3 - 3**3)


def simular(registros, meta_kg_dia=1000, painel_wp=600, turbina_kw=3000,
            quota_solar=50, consumo_kwh_kg=52, pr=0.80,
            carga_minima=0.15):
    """Busca capacidades inteiras que atendem a meta ANUAL de H2 por balanço horário.

    Sem bateria e sem fonte complementar. O ajuste representa a média do ano analisado;
    não garante atendimento diário constante. Eletrólise é simulada hora a hora.
    """
    meta_kg_dia = float(meta_kg_dia); painel_wp=float(painel_wp)
    turbina_kw=float(turbina_kw); quota_solar=float(quota_solar)
    consumo_kwh_kg=float(consumo_kwh_kg)
    if not (0 < meta_kg_dia <= 1e7 and 50 <= painel_wp <= 2000 and
            10 <= turbina_kw <= 20000 and 0 <= quota_solar <= 100 and
            25 <= consumo_kwh_kg <= 100):
        raise PerfilEnergeticoErro('Confira a meta e os parâmetros dos equipamentos.')
    n_horas=len(registros)
    n_dias=n_horas/24
    meta_anual=meta_kg_dia*n_dias
    energia_alvo=meta_anual*consumo_kwh_kg
    solar_unit=[]; wind_unit=[]
    por_mes=defaultdict(lambda: {'solar':0,'eolica':0,'h2':0,'horas':0,'irr':0,'n_irr':0,'vento':0,'n_vento':0})
    perfil_horario=defaultdict(lambda: [0,0])
    for mes,hora,irr,w10,w50,temp in registros:
        # Irradiação horária em kWh/m² por intervalo da NASA; 1 kWp -> irr kWh.
        # PR representa conjuntamente perdas aproximadas, sem modelo de inclinação.
        sp=(painel_wp/1000)*max(irr or 0,0)*pr
        wp=_potencia_eolica(w50,turbina_kw)
        solar_unit.append(sp); wind_unit.append(wp)
        if irr is not None:
            perfil_horario[hora][0]+=irr;perfil_horario[hora][1]+=1
            por_mes[mes]['irr']+=irr;por_mes[mes]['n_irr']+=1
        if w50 is not None:
            por_mes[mes]['vento']+=w50;por_mes[mes]['n_vento']+=1
    sum_s=sum(solar_unit); sum_w=sum(wind_unit)
    n_s=ceil(energia_alvo*quota_solar/100/sum_s) if sum_s>0 and quota_solar>0 else 0
    n_w=ceil(energia_alvo*(100-quota_solar)/100/sum_w) if sum_w>0 and quota_solar<100 else 0
    if (quota_solar>0 and sum_s==0) or (quota_solar<100 and sum_w==0):
        raise PerfilEnergeticoErro('Recurso solar ou eólico insuficiente nos dados consultados.')
    # Potência nominal de referência inicial: 24 h de produção alvo; ajustar
    # automaticamente capacidades da fonte e eletrólise até obter a meta anual.
    pel=max(1,meta_kg_dia*consumo_kwh_kg/24)
    def executar(n_s,n_w,pel):
        meses=defaultdict(lambda:{'solar':0.,'eolica':0.,'h2':0.,'horas':0.})
        total_h2=0.; horas=0.; energia_usada=0.; excedente=0.
        for i,(mes,_,*_) in enumerate(registros):
            a=solar_unit[i]*n_s; b=wind_unit[i]*n_w
            disponivel=a+b
            tomada=min(disponivel,pel)
            if tomada < pel*carga_minima: tomada=0.
            prod=tomada/consumo_kwh_kg
            total_h2+=prod; energia_usada+=tomada; excedente+=max(0,disponivel-tomada)
            if tomada>0: horas+=1;meses[mes]['horas']+=1
            meses[mes]['solar']+=a; meses[mes]['eolica']+=b; meses[mes]['h2']+=prod
        return total_h2,horas,energia_usada,excedente,meses
    # Expansão gradual de fonte e conversor, com limite explícito de iterações.
    for _ in range(28):
        total,horas,energia_usada,excedente,meses=executar(n_s,n_w,pel)
        if total>=meta_anual*0.999: break
        n_s=ceil(n_s*1.17) if n_s else 0
        n_w=ceil(n_w*1.17) if n_w else 0
        pel*=1.08
    else:
        raise PerfilEnergeticoErro('A meta não foi atingida dentro dos limites da simulação.')
    meses_saida=[]
    for m in range(1,13):
        z=meses[m]; w=por_mes[m]
        meses_saida.append({'mes':m,'solar_mwh':round(z['solar']/1000,2),
            'eolica_mwh':round(z['eolica']/1000,2),'h2_kg':round(z['h2'],1),
            'horas_eletrolise':z['horas'],
            'irradiacao_media_horaria':round(w['irr']/w['n_irr'],3) if w['n_irr'] else None,
            'vento_medio_50m':round(w['vento']/w['n_vento'],2) if w['n_vento'] else None})
    perfil=[round(perfil_horario[h][0]/perfil_horario[h][1],3)
            if perfil_horario[h][1] else None for h in range(24)]
    return {'paineis':n_s,'turbinas':n_w,'potencia_solar_mwp':round(n_s*painel_wp/1e6,3),
        'potencia_eolica_mw':round(n_w*turbina_kw/1000,3),
        'potencia_eletrolisador_mw':round(pel/1000,3),
        'horas_operacao':horas, 'horas_plena_carga':round(energia_usada/pel,1),
        'energia_util_mwh':round(energia_usada/1000,1),
        'energia_excedente_mwh':round(excedente/1000,1),
        'h2_ano_kg':round(total,1),'h2_medio_dia_kg':round(total/n_dias,1),
        'agua_teorica_m3_dia':round(total/n_dias*0.009,2),
        'meses':meses_saida,'perfil_solar_24h':perfil,
        'observacoes': ['Pré-dimensionamento anual com dados NASA POWER em hora solar local.',
          'Irradiação horizontal convertida por PR constante; sem modelagem detalhada de plano inclinado.',
          'Turbina de referência genérica com curva simplificada a 50 m; não representa equipamento comercial.',
          'Sem bateria, rede ou reservatório de H2; meta diária corresponde à média anual, não à garantia por dia.',
          'A potência e as horas de eletrólise são obtidas por balanço horário simulado.']}
