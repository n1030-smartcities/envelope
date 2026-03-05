"""
geometria.py — Utilitários de geometria 2D e detecção de zona.

Funções exportadas:
  simplificar_poligono(coords, angulo_threshold_deg) → (coords_simpl, idx_mapa)
  detectar_zona_geojson(properties, cidade) → (chave, confiavel) | None
  compass_label(angulo_graus) → str
"""
from __future__ import annotations
import math
from typing import Optional


def compass_label(ang: float) -> str:
    """Retorna direção cardinal para ângulo em graus (0=N, 90=L)."""
    return ["N","NE","L","SE","S","SO","O","NO"][round(ang / 45) % 8]


def _angulo_entre_arestas(p1, p2, p3) -> float:
    """
    Ângulo de deflexão no vértice p2 entre as arestas p1→p2 e p2→p3.
    Retorna valor em graus (0 = colinear, 180 = inversão total).
    """
    dx1, dy1 = p2[0]-p1[0], p2[1]-p1[1]
    dx2, dy2 = p3[0]-p2[0], p3[1]-p2[1]
    L1 = math.sqrt(dx1**2 + dy1**2)
    L2 = math.sqrt(dx2**2 + dy2**2)
    if L1 < 1e-10 or L2 < 1e-10:
        return 0.0
    cos_a = (dx1*dx2 + dy1*dy2) / (L1 * L2)
    cos_a = max(-1.0, min(1.0, cos_a))
    return math.degrees(math.acos(cos_a))


def simplificar_poligono(
    coords: list[list[float]],
    angulo_threshold_deg: float = 3.0,
    min_comprimento_m: float = 1.0,
) -> tuple[list[list[float]], dict[int, int]]:
    """
    Simplifica um polígono removendo vértices que:
      (a) formam ângulo de deflexão < angulo_threshold_deg (quase colinear), OU
      (b) estão em segmento mais curto que min_comprimento_m

    Retorna:
      coords_simpl: lista de vértices simplificados
      idx_mapa: {idx_simplificado → idx_original}

    Garante no mínimo 3 vértices.
    Útil para lotes com centenas de vértices de arredondamento.
    """
    n = len(coords)
    if n <= 4:
        return coords, {i: i for i in range(n)}

    # Marcar vértices a manter
    manter = [True] * n

    # Iteração: vários passes até estabilizar
    for _ in range(10):
        changed = False
        indices_ativos = [i for i in range(n) if manter[i]]
        if len(indices_ativos) <= 4:
            break

        for j in range(len(indices_ativos)):
            prev_j = (j - 1) % len(indices_ativos)
            next_j = (j + 1) % len(indices_ativos)
            i_prev = indices_ativos[prev_j]
            i_curr = indices_ativos[j]
            i_next = indices_ativos[next_j]

            p1 = coords[i_prev]
            p2 = coords[i_curr]
            p3 = coords[i_next]

            # Comprimento das arestas adjacentes
            L1 = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            L2 = math.sqrt((p3[0]-p2[0])**2 + (p3[1]-p2[1])**2)

            # Remover se segmento muito curto
            if min(L1, L2) < min_comprimento_m:
                manter[i_curr] = False
                changed = True
                continue

            # Remover se quase colinear
            ang = _angulo_entre_arestas(p1, p2, p3)
            if ang < angulo_threshold_deg:
                manter[i_curr] = False
                changed = True

        if not changed:
            break

    indices_finais = [i for i in range(n) if manter[i]]
    # Garantir mínimo de 3
    if len(indices_finais) < 3:
        indices_finais = list(range(min(3, n)))

    coords_simpl = [coords[i] for i in indices_finais]
    idx_mapa = {j: indices_finais[j] for j in range(len(indices_finais))}
    return coords_simpl, idx_mapa


# Campos que podem conter macrozona/setor no GeoJSON de Joinville
_CAMPOS_MACROZONA = ["macrozona", "macrozona_min", "macrozona_max", "MACROZONA", "zona_macro"]
_CAMPOS_SETOR     = ["setor", "setor_min", "setor_max", "SETOR", "setor_unico", "setor_unique", "sector"]
_CAMPOS_SIGLA_CWB = ["sigla", "SIGLA", "sg_zona", "SG_ZONA", "sigla_gis", "Sigla", "zona"]


def detectar_zona_geojson(
    properties: dict,
    cidade: str,
) -> tuple[str, bool] | None:
    """
    Tenta detectar a zona de zoneamento a partir das properties do GeoJSON.

    Retorna (chave_zona, confiavel) ou None se não encontrado.
      confiavel=True  → campo exato encontrado com valor único
      confiavel=False → campo encontrado mas pode ser ambíguo (min/max diferentes)
    """
    if not properties:
        return None

    cidade = cidade.lower()

    if cidade == "joinville":
        st = None
        for campo in _CAMPOS_SETOR:
            v = properties.get(campo)
            if v and isinstance(v, str) and len(v) >= 4:
                st = v.strip()
                break

        if not st:
            return None

        chave = st

        # Confiável se não houver divergência entre *_min e *_max
        st_min = properties.get("setor_min", st)
        st_max = properties.get("setor_max", st)
        confiavel = (st_min == st_max == st)

        return chave, confiavel

    elif cidade == "curitiba":
        for campo in _CAMPOS_SIGLA_CWB:
            v = properties.get(campo)
            if v and isinstance(v, str):
                return v.strip(), True

    return None
