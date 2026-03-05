"""
Exportação para GeoJSON.

Gera:
- Feature 'giraffe' por PAVIMENTO — uma Feature por piso com
  properties 'height' (espessura do piso) e 'stackOrder' (ordem de empilhamento).
  É o formato que o Giraffe usa para extrudar andares individualmente.
- build_giraffe_features() → FeatureCollection com N features (N = pavimentos)
- build_export_completo() → mantido como conveniência (usa só giraffe agora)
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import json

from coordenadas import coords_utm_to_wgs84


def _ring_close(coords: List[List[float]]) -> List[List[float]]:
    if not coords or coords[0] == coords[-1]:
        return coords
    return coords + [coords[0]]


def _to_wgs(coords_utm: List[List[float]]) -> List[List[float]]:
    return _ring_close(coords_utm_to_wgs84(coords_utm))


# ─────────────────────────────────────────────────────────────
# Giraffe por pavimentos
# ─────────────────────────────────────────────────────────────

def build_giraffe_features(
    coords_footprint_utm: List[List[float]],
    altura_total_m: float,
    altura_por_pav_m: float,
    coords_embasamento_utm: Optional[List[List[float]]],
    altura_embasamento_m: float,
    n_unidades: int,
    zona_sigla: str,
    area_construida_m2: float,
) -> Dict[str, Any]:
    """
    FeatureCollection com uma Feature por pavimento, no formato Giraffe:

    Pavimento convencional:
      "height"      → espessura do piso em metros (floor-to-floor)
      "levels"      → 1 (sempre)
      "stackOrder"  → índice de empilhamento (0 = térreo, cresce para cima)
      "baseHeight"  → cota absoluta da base em metros (omitido no térreo = 0)
      "uso"         → "convencional" | "embasamento"

    O Giraffe posiciona cada Feature pela 'baseHeight' e extrudada pela 'height'.
    """
    features: List[Dict[str, Any]] = []
    ring_fp  = _to_wgs(coords_footprint_utm)

    h_emb = 0.0  # nível onde começa a torre

    # ── Embasamento ──────────────────────────────────────────
    stack = 0        # stackOrder (0 = ground, increases upward)
    base_acum = 0.0  # baseHeight acumulado em metros
    if coords_embasamento_utm and len(coords_embasamento_utm) >= 3:
        h_emb = min(altura_embasamento_m, altura_total_m)
        ring_emb = _to_wgs(coords_embasamento_utm)
        props_emb: Dict[str, Any] = {
            "height":      round(h_emb, 2),
            "levels":      max(1, round(h_emb / altura_por_pav_m)),
            "stackOrder":  stack,
            "uso":         "embasamento",
            "zona":        zona_sigla,
        }
        if base_acum > 0:
            props_emb["baseHeight"] = round(base_acum, 2)
        features.append({
            "type": "Feature",
            "properties": props_emb,
            "geometry": {"type": "Polygon", "coordinates": [ring_emb]},
        })
        stack += 1
        base_acum += h_emb

    # ── Pavimentos convencionais ──────────────────────────────
    altura_torre = altura_total_m - h_emb
    if altura_torre <= 0:
        # toda a altura é embasamento
        return {"type": "FeatureCollection",
                "name": f"giraffe_{zona_sigla}",
                "features": features}

    n_pav = max(1, round(altura_torre / altura_por_pav_m))
    h_real_pav = altura_torre / n_pav  # pode diferir levemente de altura_por_pav_m

    for piso in range(n_pav):
        props_pav: Dict[str, Any] = {
            "height":       round(h_real_pav, 2),
            "levels":       1,
            "stackOrder":   stack + piso,
            "uso":          "convencional",
            "zona":         zona_sigla,
            "area_piso_m2": round(area_construida_m2 / n_pav, 1),
            "n_unidades":   n_unidades if piso == 0 else 0,
        }
        piso_base = base_acum + piso * h_real_pav
        if piso_base > 0:
            props_pav["baseHeight"] = round(piso_base, 2)
        features.append({
            "type": "Feature",
            "properties": props_pav,
            "geometry": {"type": "Polygon", "coordinates": [ring_fp]},
        })

    return {
        "type": "FeatureCollection",
        "name": f"giraffe_{zona_sigla}",
        "features": features,
    }


# ─────────────────────────────────────────────────────────────
# Exportação completa (somente Giraffe agora — sem lote, sem casca)
# ─────────────────────────────────────────────────────────────

def build_export_completo(
    coords_lote_utm: List[List[float]],      # mantido por compatibilidade, não usado
    coords_footprint_utm: List[List[float]],
    altura_total: float,
    n_pavimentos: int,
    altura_por_pav: float,
    area_lote: float,                        # mantido por compat.
    area_construida: float,
    n_unidades: int,
    zona_sigla: str,
    z_base: float = 0.0,
    coords_embasamento_utm: Optional[List[List[float]]] = None,
    altura_embasamento_m: float = 9.0,
) -> Dict[str, Any]:
    """
    Retorna FeatureCollection Giraffe (um Feature por pavimento).
    Parâmetros herdados (coords_lote_utm, z_base, area_lote) ignorados.
    """
    return build_giraffe_features(
        coords_footprint_utm=coords_footprint_utm,
        altura_total_m=altura_total,
        altura_por_pav_m=altura_por_pav,
        coords_embasamento_utm=coords_embasamento_utm,
        altura_embasamento_m=altura_embasamento_m,
        n_unidades=n_unidades,
        zona_sigla=zona_sigla,
        area_construida_m2=area_construida,
    )


def to_json_str(fc: Dict[str, Any]) -> str:
    return json.dumps(fc, ensure_ascii=False, indent=2)
