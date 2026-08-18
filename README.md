# H2V-Siting Brasil

MVP acadêmico para avaliação preliminar de localidades para produção de hidrogênio verde.

## Funcionalidades atuais

- Mapa interativo com Leaflet + OpenStreetMap
- Seleção do local por clique, coordenadas ou arraste do marcador
- Consulta da NASA POWER
- Irradiação solar média, mínima, máxima e anual
- Configuração da planta fotovoltaica
- Configuração do eletrólisador
- Estimativa de energia solar
- Estimativa de produção de H2
- Demanda teórica mínima de água
- Identificação preliminar do gargalo energético

## Instalação no Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

Acesse:

http://127.0.0.1:8000/

## Observação

O cálculo de água usa, nesta fase, o valor estequiométrico teórico aproximado
de 9 litros por kg de H2. Não representa o consumo total de água de uma planta real.
