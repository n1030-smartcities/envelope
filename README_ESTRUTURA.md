# Envelope Construtivo — v2 Multi-Cidade

## Estrutura de arquivos

```
envelope/
├── app.py                    ← Interface Streamlit
├── schema.py                 ← Tipos canônicos (ParametrosZona, ConfigSimulacao…)
├── calculo.py                ← Motor de cálculo (agnóstico de cidade)
├── cidade_manager.py         ← Carregamento automático por cidade
├── coordenadas.py            ← Conversão UTM → WGS84
├── export3d.py               ← Exportação GeoJSON 3D / Giraffe
├── requirements.txt
├── data/
│   ├── parametros_curitiba_2026.xlsx
│   └── parametros_joinville_2026.xlsx   ← coloque aqui
└── loaders/
    ├── __init__.py
    ├── curitiba.py           ← Loader Curitiba
    └── joinville.py          ← Loader Joinville
```

## Para adicionar nova cidade

1. Coloque o XLSX em `data/parametros_{cidade}_{ano}.xlsx`
2. Crie `loaders/{cidade}.py` com função `carregar_{cidade}(xlsx_path) -> dict[str, ParametrosZona]`
3. Registre em `cidade_manager.py` no dict `_LOADERS`

## Diferenças arquiteturais entre cidades

| | Curitiba | Joinville |
|---|---|---|
| Chave de zona | `ZR-3` | `AUAP\|SA-01` |
| Gabarito | pavimentos → metros | metros direto |
| Afastamento lateral | H/6 facultado até N pav | h/6 + 0,5 mín 1,5m |
| Embasamento | Não | Sim (70% TO, até 9m) |
| CA permissível | Sim (algumas zonas) | Não no XLSX |

## Execução

```bash
pip install -r requirements.txt
streamlit run app.py
```
