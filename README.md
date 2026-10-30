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


## Tela inicial integrada (atualização)

- `/`: painel unificado, **um só mapa e uma única localização** para dimensionamento e consulta hídrica.
- `/api/perfil/`: perfil horário NASA POWER, simulação de solar + eólica e eletrólise, estimativa LCOH.
- `/api/recursos-hidricos/`: recurso de referência da base ANA para a localização selecionada.
- `/analise-territorial/`: página territorial antiga preservada como consulta detalhada/legado.
- Gráfico diário combinado: irradiação horária solar (kWh/m²) e vento a 50 m (m/s), dois eixos.
- O ano da análise deve ser um ano histórico completo; não se deve interpretar a série como previsão do tempo.
- CAPEX, tarifa, vida útil, OPEX e desconto são hipóteses editáveis, **não dados NASA**.
- LCOH simplificado = (CAPEX anualizado + eletricidade anual + OPEX não elétrico anual) / kg H₂ anuais.
- A geração fotovoltaica e a curva eólica são aproximações didáticas; não representam projetos executivos.
- A meta diária representa **média anual**, e não a garantia de produção em cada dia.

## Atualização — cenários energéticos e localização hídrica

- A tela principal oferece **Somente solar**, **Somente eólica** e **Híbrido** em vez de um controle de porcentagem solar. A alternativa híbrida usa divisão energética inicial de 50%/50% no pré-dimensionamento; os resultados reais variam com a simulação horária.
- Para cada consulta NASA POWER, os três cenários são dimensionados e simulados para a mesma meta média anual; os cartões, o gráfico mensal e a estimativa LCOH mostram o cenário selecionado.
- O gráfico de 24 horas compara a **potência média gerada (kW)** de cada cenário, não a irradiação ou velocidade do vento. Cada curva corresponde aos equipamentos dimensionados daquele cenário: as potências instaladas podem ser diferentes.
- O recurso hídrico de referência retornado pela ANA é representado por **marcador azul no mapa**, com linha tracejada até o local da planta. A distância é aproximada em linha reta, não percurso hidráulico.
- O CAPEX usado no LCOH continua a ser uma entrada única de referência, aplicada ao cenário selecionado. **Não comparar LCOHs entre configurações usando CAPEX idêntico sem um orçamento específico para cada tecnologia.**
- O modelo eólico usa curva genérica e vento a 50 m, adequados apenas à pré-viabilidade. O potencial hídrico não é uma confirmação de disponibilidade ou direito de captação.


## Comparação dos três cenários (atualização)

A página inicial não possui seletor de fonte. A mesma consulta NASA POWER é utilizada para dimensionar **simultaneamente** solar, eólica e híbrida para uma única localização e meta de H₂. A resposta `/api/perfil/` contém `cenarios.solar`, `cenarios.eolica` e `cenarios.hibrida`; os gráficos diário, anual e de produção mensal de hidrogênio mostram as três séries. A tabela exibe dimensionamento, horas, produção, água e LCOH para cada configuração. O mesmo CAPEX preenchido é aplicado como hipótese ilustrativa aos três casos e **não** fundamenta uma comparação econômica definitiva.

## Interface: quantidade de equipamentos por cenário

Os cards de **solar**, **eólica** e **híbrida** exibem agora, em destaque, o número de **placas solares** e **torres eólicas**, bem como as potências fotovoltaica (MWp) e eólica (MW) instaladas. Os valores são calculados pelo simulador para cada cenário, usando a meta de H₂ e os dados NASA POWER. Para fontes ausentes, é apresentado zero.


## Correção física e de dimensionamento (2026-10)

- Radiação horária NASA POWER interpretada como W/m² e convertida para kWh/m² por intervalo de 1 hora.
- Cache da série horária versionado (`v2`) para evitar reutilização de dados anteriormente processados.
- Nova busca de capacidades solares/eólicas inteiras e potências de eletrólise candidatas, que atende à meta anual e penaliza excedente e sobredimensionamento do conversor. É **heurística técnica preliminar**, não otimização econômica de CAPEX.
- Balanço físico auditável: energia gerada = energia consumida pela eletrólise + energia excedente, incluindo descarte por carga mínima.
- Percentuais de aproveitamento e excedente exibidos nos cartões e na tabela.
- Uma turbina indivisível pode causar sobreprodução em metas pequenas. A meta diária é média do ano, sem garantia dia a dia.

A equação do LCOH permanece **ilustrativa**, com CAPEX igual para os três cenários: não utilizar o ranking econômico até modelar custos próprios para solar, eólica e híbrida.

## Atualização: custos específicos por cenário

O módulo `analises/services/economia.py` calcula agora o LCOH por cenário,
considerando: preço unitário do painel, custo instalado da turbina por kW,
custo instalado da eletrólise por kW, infraestrutura adicional, manutenção
anual por subsistema e custos fixos anuais. A composição de CAPEX e LCOH
aparece nos cards e na tabela comparativa.

Os valores padrão são **hipóteses didáticas editáveis**, não preços verificados
nem cotações comerciais. Devem ser substituídos por estimativas de engenharia
ou propostas comerciais para estudos de viabilidade.

**Sem dupla contagem:** a geração própria já é representada no CAPEX e no OPEX.
O custo da eletricidade comprada só entra sobre a fração de consumo declarada
no formulário (0% por padrão). A opção de compra é uma sensibilidade de custo,
não modela uma nova fonte de energia no balanço horário.

Limitações: sem substituição de stacks, degradação, água tratada, compressão,
armazenamento, seguro, tributos, receitas de excedentes ou custos de rede.
O dimensionamento energético ainda é preliminar, sem otimização de LCOH.

## Custos técnico-econômicos por referência institucional

- **IRENA, Renewable Power Generation Costs in 2024**: solar fotovoltaica US$ 691/kW, eólica terrestre US$ 1.041/kW, custo total instalado em **USD de 2024**. https://www.irena.org/Digital-Report/Renewable-Power-Generation-Costs-in-2024
- **IEA, Global Hydrogen Review 2024**: eletrolisador alcalino US$ 2.000/kW e PEM US$ 2.450/kW instalados, referência de **2023**. https://www.iea.org/reports/global-hydrogen-review-2024
- O câmbio R$/USD é informado no formulário: padrão **R$ 5,00/US$ apenas ilustrativo**, não cotação corrente.
- O&M solar (US$ 22/kW/ano), eólico (US$ 44/kW/ano) e eletrólise (3% do CAPEX/ano) são hipóteses iniciais editáveis: **não representam preços oficiais verificados**.
- A vida de stack (40 mil horas) e o custo de troca (11% do CAPEX da eletrólise) são **hipóteses editáveis**, calculadas com reposições descontadas na vida do projeto. O cálculo usa horas anuais médias e não simula degradação nem parada para manutenção.
- Custos publicados usam bases de anos distintas; nenhum ajuste automático de inflação, localização, logística, tributos ou preços brasileiros foi incorporado. Valores são de pré-viabilidade, não orçamento de EPC.
- Como custos instalados já incluem componentes típicos de implantação, a rubrica 'integração adicional' começa em 0% para minimizar dupla contagem.

## Câmbio oficial automático e parâmetros institucionais

- A interface não pede mais para digitar os valores de CAPEX IRENA/IEA, que são carregados do catálogo institucional em `analises/services/economia.py`.
- A API `GET /api/referencias-e-cambio/?modo_cambio=base` consulta a **PTAX de venda oficial do Banco Central do Brasil** (OData), calculando a média aritmética das observações diárias em 2024 para solar/eólica e em 2023 para eletrólise. Valores históricos recebem cache de 30 dias.
- A opção `modo_cambio=atual` usa a última PTAX de venda disponível (cache de 6 horas); serve apenas como conversão nominal, **não** corrige inflação ou preços reais de implementação.
- A API `GET /api/perfil/` usa a mesma seleção de câmbio. Se o Banco Central estiver indisponível e não houver cache, a simulação econômica é bloqueada com erro explícito, sem usar um número inventado.
- Fontes: https://dadosabertos.bcb.gov.br/dataset/dolar-americano-usd-todos-os-boletins-diarios ; https://www.irena.org/Digital-Report/Renewable-Power-Generation-Costs-in-2024 ; https://www.iea.org/reports/global-hydrogen-review-2024
- Os CAPEX de relatórios não possuem uma API oficial pública padronizada garantida. Permanecem **fixados e versionados** no catálogo com fonte e ano de publicação; são atualizados mediante verificação de novos relatórios, nunca por extração automática não validada.
- OPEX e substituição de stacks ainda são hipóteses ajustáveis. Para um orçamento atual no Brasil, são necessários inflação/escalonamento monetário, impostos, custos locais e propostas de fornecedores.


## Interface simplificada e fontes auditáveis

O formulário básico exige apenas ano meteorológico, produção pretendida, tipo de eletrólise e critério de câmbio. Os custos publicados estão no catálogo `analises/services/economia.py`; os links oficiais completos podem ser abertos diretamente na interface. As demais entradas ficam em **Configurações avançadas**. A API NASA POWER fornece condições meteorológicas, não valores de equipamentos. A API PTAX fornece câmbio, não preços corrigidos por inflação.

Fontes principais:

- IRENA (2025), *Renewable Power Generation Costs in 2024*: https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2025/Jul/IRENA_TEC_RPGC_in_2024_2025.pdf
- IEA (2024), *Global Hydrogen Review 2024*: https://iea.blob.core.windows.net/assets/3ece5ee4-7537-4992-8ba6-b83c994c3fd4/GlobalHydrogenReview2024.pdf
- NREL, ATB 2024 PV: https://atb.nrel.gov/electricity/2024/utility-scale_pv
- NREL, ATB 2024 Wind: https://atb.nrel.gov/electricity/2024/Land-Based_Wind
- Banco Central PTAX: https://dadosabertos.bcb.gov.br/dataset/dolar-americano-usd-todos-os-boletins-diarios

Nota: O&M solar do NREL é em kW AC/ano, com conversão aproximada de kWp DC para AC usando ILR = 1,34 apenas para essa estimativa. Não equivale a engenharia final.

## Ajuste de interface e botão de comparação (2026-10)

- Formulário de entrada reorganizado em quatro etapas visuais.
- A consulta inicial `/api/referencias-e-cambio/` é **informativa**, e sua falha não bloqueia mais o botão Comparar. O envio consulta `/api/perfil/` diretamente e tenta a PTAX no servidor.
- Erros do servidor são exibidos no painel de simulação sem falha silenciosa.
- Os campos avançados e os links de fontes permanecem disponíveis.

**Nota:** a comparação requer dados de NASA POWER e PTAX. Quando ambas as fontes estiverem indisponíveis e não houver cache, o servidor retornará uma mensagem de erro; nenhum câmbio fictício é aplicado.


## Otimização econômica dos cenários

A simulação procura o menor LCOH estimado para a mesma meta anual de hidrogênio.
Avalia nove potências candidatas de eletrólise e dimensiona as fontes por busca binária.
No híbrido testa as participações de 10% a 90% de geração solar, em passos de 10 pontos percentuais.
A quota refere-se à participação de energia anual bruta inicialmente buscada; a participação
final é calculada com os equipamentos inteiros efetivamente escolhidos.

Os valores anteriores ainda são computados para permitir comparação da redução percentual.
É uma busca discreta aproximada, não uma prova de mínimo global. Sem baterias ou conexão
à rede; custos de instalação e O&M dependem dos parâmetros e fontes da versão atual.
Os dados meteorológicos da NASA POWER são horários e o resultado equivale a meta média anual.
A implementação usa numpy para tornar a avaliação horária vetorizada.
