# H₂V-Siting Brasil

**Explore o potencial de energia solar e eólica de qualquer localidade e estime os equipamentos necessários para produzir hidrogênio verde.**

> Projeto acadêmico de **pré-viabilidade**, não um estudo de engenharia de detalhe.

## ☀️ 🌬️ 💧 O que é possível fazer?

1. **Marque um ponto no mapa.** A localização determina os dados meteorológicos consultados.
2. **Informe quantos quilogramas de H₂ quer produzir por dia.** A meta representa uma média diária anual, não uma garantia em todos os dias.
3. **Escolha a participação solar/eólica e a potência de referência dos equipamentos.**
4. **Consulte a NASA POWER automaticamente.** A irradiação e o vento vêm da API, não de entradas arbitrárias do usuário.
5. **Veja os resultados visuais:** desenhos explicativos de painéis, aerogeradores e eletrolisador, quantidades e potências, gráficos mensais de energia solar e eólica, gráfico de perfil solar ao longo do dia, produção de H₂ e vento mensal.
6. **Consulte os recursos hídricos** na interface original, incluindo integração ANA/HidroWeb quando disponível.

### Visualização do fluxo

```text
📍 Ponto no mapa → 🛰️ NASA POWER → ☀️ Solar + 🌬️ Eólica
                                              ↓
                                  ⚡ Simulação horária
                                              ↓
                        💧 H₂ estimado + 🏭 Equipamentos
```

## Páginas

- **`/laboratorio/` — NOVO:** dashboard visual, dimensionamento orientado por meta, gráficos horários e mensais.
- **`/` — preservada:** interface original com consultas geográficas, geração solar/eólica e recursos hídricos da ANA.
- **`/api/perfil/`:** endpoint JSON da análise horária; recebe `latitude`, `longitude`, `ano`, `meta`, `painel`, `turbina` e `solar`.

## Instalação no Windows / PowerShell

```powershell
git clone https://github.com/texjunior/h2vSitingBrasil.git
cd h2vSitingBrasil
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

> Se estiver usando o ZIP desta entrega, extraia-o, abra a pasta que contém `manage.py` e execute os comandos a partir da criação do ambiente virtual.

Acesse http://127.0.0.1:8000/laboratorio/ . **Internet é necessária** para buscar dados NASA POWER, mapas e bibliotecas de gráficos.

## Como os cálculos funcionam

- **Dados:** NASA POWER Hourly Point API (`ALLSKY_SFC_SW_DWN`, `WS10M`, `WS50M`, `T2M`), padrão hora solar local (LST). Um ano completo por simulação, com cache Django de 30 dias.
- **Solar:** irradiação horária horizontal × potência dos módulos × PR fixo de 80%. Não inclui modelo de inclinação/orientação dos painéis.
- **Eólica:** curva normalizada **hipotética** de turbina usando `WS50M` (entrada 3 m/s, nominal 12 m/s, corte 25 m/s). **Não** é curva de fabricante nem representa altura real obrigatória do rotor.
- **Eletrólise:** consumo fixo de referência **52 kWh/kg H₂**, carga mínima de **15%** da potência nominal e balanço energético por hora. A potência é escalada junto às capacidades renováveis até atender aproximadamente a meta de produção **anual**, usando um procedimento heurístico (não otimização econômica).
- **Água:** mínimo estequiométrico aproximado de **9 litros por kg de H₂**, não inclui tratamento ou perdas.
- **Energia excedente:** produção renovável não consumida pelo eletrolisador no modelo, sem armazenamento ou exportação à rede.

### Como interpretar o gráfico solar diário?

O gráfico apresenta **média por hora ao longo do ano consultado**, a partir da série solar da NASA. O horário é **LST**, e pode diferir da hora oficial local. O valor de cada hora representa a irradiação acumulada naquele intervalo, em **kWh/m²**, e não irradiância instantânea em W/m².

### Limitações importantes

- Perfil de **um ano** de referência (não climatologia multianual ainda).
- Resolução e incertezas da fonte NASA POWER; não substitui estação local ou campanha de medição.
- Meta diária significa **média do total anual** dividida pelos dias simulados; não assegura produção constante.
- Sem custos, restrições de terreno, turbulência, inclinação solar, armazenamento, purificação, rede ou sazonalidade de demanda.
- A quantidade de equipamentos é calculada por estimativa; as figuras são **ilustrações esquemáticas**, não uma reprodução proporcional de cada painel/turbina.
- A comparação simultânea de várias localidades, a rosa dos ventos, o catálogo real de máquinas e análises plurianuais são evoluções planejadas e **não foram implementadas nesta entrega**.

## Arquivos novos

```text
analises/
├── laboratorio.py                         # Página e API JSON
├── services/perfil_energetico.py          # NASA horária e simulação
├── templates/analises/laboratorio.html    # Dashboard visual responsivo
└── tests_laboratorio.py                  # Testes básicos sem internet
```

## Referências

- [NASA POWER — API horária](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/)
- [NASA POWER — documentação](https://power.larc.nasa.gov/docs/)

## Situação da entrega

Esta é uma **primeira versão funcional do laboratório visual**, adicionada ao MVP original sem substituir a página existente. Os indicadores são estimativas e devem ser validados antes de uso científico ou comercial.


## Mapas e erro 403 do OpenStreetMap

Os mapas interativos utilizam **Leaflet**. A camada cartográfica padrão foi alterada
para **Esri World Topo Map**, com opção de **Esri World Imagery (satélite)**, tanto
na página principal quanto no laboratório visual. Os recursos e cálculos NASA POWER
e ANA permanecem independentes da camada visual.

A mudança evita depender diretamente do serviço comunitário
`tile.openstreetmap.org`, que pode retornar imagens com *403 Access blocked*
quando as solicitações não cumprem sua política de uso. Os créditos dos
provedores são apresentados na atribuição do mapa.

**Importante:** o serviço Esri também possui condições de uso próprias e não
garante disponibilidade contínua; em produção, selecione um provedor de mapas
com contrato e limites compatíveis com o tráfego esperado. Não remova a
atribuição nem tente contornar restrições de acesso.

Se o navegador mostrar blocos antigos após a atualização, faça uma atualização
com `Ctrl+F5` e reinicie o servidor Django.


## Correção da interface do laboratório (erro `h2_medio_dia_kg`)

A API `/api/perfil/` retorna o resultado na propriedade JSON `resultado`. A interface
foi alinhada a esse contrato (antes procurava `result`, causando o erro
`Cannot read properties of undefined`). O frontend também verifica se as séries
mensais e horárias estão presentes antes de construir os gráficos.

Se a página estiver aberta no navegador após atualizar os arquivos, force
a atualização com **Ctrl + F5**. Caso a NASA não responda, o sistema deverá
exibir a mensagem da API em vez de tentar desenhar resultados inexistentes.
