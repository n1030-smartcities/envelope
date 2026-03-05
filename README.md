# Envelope Construtivo v3

## Arquitetura

```
app.py           Interface Streamlit
schema.py        Tipos canônicos (ParametrosZona, ConfigSimulacao, ...)
calculo.py       Motor de cálculo — recebe metros, afastamentos como dict
db_builder.py    Lê XLSX → grava params.db (SQLite)
db_manager.py    Lê params.db → retorna ParametrosZona
geometria.py     Simplificação de polígono + autodetect de zona
coordenadas.py   UTM SIRGAS2000 → WGS84 (sem deps)
export3d.py      Exportação GeoJSON 3D + Giraffe
params.db        Banco SQLite com 47 zonas Curitiba + 53 Joinville
data/            XLSX de parâmetros
```

## Uso

```bash
# 1ª vez: gerar o banco (já gerado, mas pode forçar rebuild)
python db_builder.py --data data/ --out params.db --force

# Rodar o app
streamlit run app.py
```

## Afastamento lateral

**Sempre editável**, independente de ser facultado ou não:

- Quando **facultado** (H ≤ limite): default=0m, badge azul "voluntário" se > 0
- Quando **obrigatório**: default=valor legal, badge laranja "⚠ abaixo legal" se < mínimo
- Motor aceita qualquer valor ≥ 0 e emite alertas sem bloquear o cálculo

## Adicionar nova cidade

1. Criar `data/parametros_{cidade}_{ano}.xlsx`
2. Criar `loaders/{cidade}.py` retornando lista de dicts com colunas do schema
3. Registrar em `db_builder.py` no dict `loaders`
4. Rodar `python db_builder.py --force`

## Schema SQLite (tabela `zonas`)

| Coluna | Tipo | Descrição |
|---|---|---|
| cidade | TEXT | "curitiba" / "joinville" |
| chave | TEXT | PK: "ZR-3" / "AUAC\|SA-04" |
| af_divisor | REAL | H/divisor (NULL = fixo) |
| af_acrescimo | REAL | + acréscimo após divisão |
| af_minimo | REAL | mínimo em metros |
| af_facultado_ate_m | REAL | 0 = nunca facultado |
| emb_permitido | INT | 0/1 |
| ... | ... | ... |
