# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py

# Rebuild the SQLite database from XLSX files (place XLSX in data/)
python db_builder.py --data data/ --out params.db
python db_builder.py --force   # force rebuild even if params.db exists
```

## Architecture

This is a Streamlit app that calculates the **envelope construtivo** (building envelope) for urban lots in Brazilian cities (Curitiba and Joinville), based on zoning regulations.

### Data flow

1. User uploads a GeoJSON polygon (lot in UTM SIRGAS2000 22S coordinates)
2. Zone parameters are loaded from `params.db` (SQLite)
3. The calculation engine (`calculo.py`) applies setbacks and computes buildable area
4. Results are displayed as SVG footprint, 3D viewer, and exportable Giraffe GeoJSON

### Module responsibilities

- **`schema.py`** — Canonical dataclasses: `ParametrosZona`, `AfastamentoLateral`, `Embasamento`, `ConfigSimulacao`, `ConfigGaragem`, `ResultadoSimulacao`. Single source of truth for all types.
- **`calculo.py`** — Pure calculation engine. Takes UTM coordinates + `ConfigSimulacao`, returns `ResultadoSimulacao`. Also contains 2D polygon geometry helpers (`area_poligono`, `inset_poligono_simples`, `arestas_info`, `extrair_coords_simples`).
- **`db_manager.py`** — Reads `params.db`, returns `ParametrosZona` objects. Caches per-city results.
- **`db_builder.py`** — Parses XLSX files and writes `params.db`. Contains city-specific loaders (`_load_curitiba`, `_load_joinville`). Auto-triggered by `app.py` if `params.db` is missing.
- **`geometria.py`** — Polygon simplification (removes near-collinear vertices) and zone autodetection from GeoJSON properties.
- **`coordenadas.py`** — UTM SIRGAS2000 22S to WGS84 conversion (no external dependencies).
- **`export3d.py`** — Builds Giraffe-format GeoJSON (one Feature per floor with `height` and `base_height` properties). Converts UTM to WGS84 before export.
- **`viewer3d.py`** — Generates inline HTML with a 3D WebGL viewer for Streamlit.
- **`app.py`** — Streamlit UI. Manages session state, sidebar controls, SVG preview, result tabs, and export.

### Key design decisions

- All coordinates inside the engine stay in **UTM meters** (SIRGAS2000 22S). Conversion to WGS84 happens only at export time in `export3d.py`.
- Lateral setbacks (`afastamentos_laterais`) are always user-editable — even when legally optional ("facultado"). The engine emits warnings but never blocks calculation.
- The `AfastamentoLateral.calcular_legal(altura_m)` formula is `max(H / divisor + acrescimo, minimo)`. When `altura_m <= facultado_ate_m`, the legal minimum is 0.
- Curitiba gabarito is defined in **pavimentos** (floors) and converted to meters via `_ALTURA_PAV_M = 3.0`. Joinville gabarito is directly in meters.
- Joinville zone key format: `"MACROZONA|SETOR"` (e.g., `"AUAC|SA-04"`). Curitiba key: plain sigla (e.g., `"ZR-3"`).

### Adding a new city

1. Add XLSX to `data/parametros_{cidade}_{ano}.xlsx`
2. Add a loader function `_load_{cidade}(xlsx_path) -> list[dict]` in `db_builder.py`
3. Register the loader in the `loaders` dict inside `build_db()`
4. Run `python db_builder.py --force`
5. Add zone autodetect field names to `geometria.py` if needed

### `morto/`, `morto2/`, `morto3/`, `morto4/` directories

These are archived old versions. The active codebase is only the root-level `.py` files.
