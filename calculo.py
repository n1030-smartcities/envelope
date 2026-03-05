"""
calculo.py — Motor de cálculo de envelope construtivo.
Versão única e definitiva. Sem herança de versões antigas.
Recebe altura em metros. Afastamento lateral controlado diretamente
pelo usuário via ConfigSimulacao.afastamentos_laterais.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math

from schema import ParametrosZona, ConfigSimulacao, ConfigGaragem, AfastamentoLateral


# ─────────────────────────────────────────────────────────────
# Geometria 2D
# ─────────────────────────────────────────────────────────────

def area_poligono(coords: list[list[float]]) -> float:
    n = len(coords)
    if n < 3: return 0.0
    a = 0.0
    for i in range(n):
        x1, y1 = coords[i][0], coords[i][1]
        x2, y2 = coords[(i+1)%n][0], coords[(i+1)%n][1]
        a += x1*y2 - x2*y1
    return abs(a) / 2.0


def centroide(coords: list[list[float]]) -> tuple[float, float]:
    n = len(coords)
    return sum(c[0] for c in coords)/n, sum(c[1] for c in coords)/n


def extrair_coords_simples(feature: dict) -> list[list[float]]:
    geom = feature.get("geometry", feature)
    gt = geom["type"]
    if gt == "Polygon":
        cs = geom["coordinates"][0]
    elif gt == "MultiPolygon":
        cs = max(geom["coordinates"], key=lambda p: area_poligono(p[0]))[0]
    else:
        raise ValueError(f"Geometria não suportada: {gt}")
    if len(cs) > 1 and cs[0] == cs[-1]:
        cs = cs[:-1]
    return [list(c[:2]) for c in cs]


def arestas_info(coords: list[list[float]]) -> list[dict]:
    n = len(coords)
    result = []
    for i in range(n):
        p1, p2 = coords[i], coords[(i+1)%n]
        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        result.append({
            "idx": i, "p1": p1, "p2": p2,
            "comprimento": math.sqrt(dx**2 + dy**2),
            "angulo_graus": math.degrees(math.atan2(dx, dy)) % 360,
            "midpoint": [(p1[0]+p2[0])/2, (p1[1]+p2[1])/2],
        })
    return result


def inset_poligono_simples(
    coords: list[list[float]],
    afastamentos: dict[int, float],
) -> list[list[float]] | None:
    """Aplica afastamento por aresta. Retorna novo polígono ou None se inviável."""
    n = len(coords)
    ctr = centroide(coords)

    def normal_int(p1, p2):
        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        L = math.sqrt(dx**2+dy**2)
        if L < 1e-10: return 0.0, 0.0
        nx, ny = -dy/L, dx/L
        mx, my = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
        if nx*(ctr[0]-mx) + ny*(ctr[1]-my) < 0:
            nx, ny = -nx, -ny
        return nx, ny

    def linha(i, off=0.0):
        p1, p2 = list(coords[i]), list(coords[(i+1)%n])
        if off > 0:
            nx, ny = normal_int(p1, p2)
            p1 = [p1[0]+nx*off, p1[1]+ny*off]
            p2 = [p2[0]+nx*off, p2[1]+ny*off]
        return p1, p2

    def intersect(a1, a2, b1, b2):
        dx1, dy1 = a2[0]-a1[0], a2[1]-a1[1]
        dx2, dy2 = b2[0]-b1[0], b2[1]-b1[1]
        d = dx1*dy2 - dy1*dx2
        if abs(d) < 1e-10: return [(a1[0]+a2[0])/2, (a1[1]+a2[1])/2]
        t = ((b1[0]-a1[0])*dy2 - (b1[1]-a1[1])*dx2) / d
        return [a1[0]+t*dx1, a1[1]+t*dy1]

    novos = []
    for i in range(n):
        prev_i = (i-1) % n
        a1, a2 = linha(prev_i, afastamentos.get(prev_i, 0.0))
        b1, b2 = linha(i,      afastamentos.get(i,      0.0))
        novos.append(intersect(a1, a2, b1, b2))

    return novos if area_poligono(novos) >= 1.0 else None


def calcular_testada(coords: list[list[float]], idx_frentes: list[int]) -> float:
    """
    Testada = distância em linha reta entre os extremos da cadeia de frente.
    p_inicio = coords[idx_frentes[0]]
    p_fim    = coords[(idx_frentes[-1]+1) % n]
    """
    if not idx_frentes:
        return 0.0
    n = len(coords)
    p_inicio = coords[idx_frentes[0]]
    p_fim = coords[(idx_frentes[-1] + 1) % n]
    dx = p_fim[0] - p_inicio[0]
    dy = p_fim[1] - p_inicio[1]
    return math.sqrt(dx**2 + dy**2)


def footprint_retangular(
    coords: list[list[float]],
    afastamentos: dict[int, float],
    idx_frentes: list[int],
    n_slices: int = 200,
) -> list[list[float]] | None:
    """
    Calcula o maior retângulo inscrito no polígono com afastamentos aplicados,
    alinhado à direção da testada. Algoritmo de histograma de fatias.
    """
    n = len(coords)
    if not idx_frentes or n < 3:
        return None

    # 1. Sistema de coordenadas alinhado à testada
    p_start = coords[idx_frentes[0]]
    p_end = coords[(idx_frentes[-1] + 1) % n]
    du = p_end[0] - p_start[0]
    dv_vec = p_end[1] - p_start[1]
    L = math.sqrt(du**2 + dv_vec**2)
    if L < 1e-10:
        return None

    u_hat = (du / L, dv_vec / L)
    # v_hat perpendicular, apontando para dentro do lote
    v_hat_cand = (-u_hat[1], u_hat[0])
    cx, cy = centroide(coords)
    mx = (p_start[0] + p_end[0]) / 2
    my = (p_start[1] + p_end[1]) / 2
    if v_hat_cand[0] * (cx - mx) + v_hat_cand[1] * (cy - my) < 0:
        v_hat = (-v_hat_cand[0], -v_hat_cand[1])
    else:
        v_hat = v_hat_cand

    # 2. Converter vértices para (u, v)
    def to_uv(p):
        rx, ry = p[0] - p_start[0], p[1] - p_start[1]
        return rx * u_hat[0] + ry * u_hat[1], rx * v_hat[0] + ry * v_hat[1]

    def from_uv(u, v):
        return [
            p_start[0] + u * u_hat[0] + v * v_hat[0],
            p_start[1] + u * u_hat[1] + v * v_hat[1],
        ]

    uvs = [to_uv(c) for c in coords]
    ctr_uv = to_uv((cx, cy))

    # 3. Arestas com offset aplicado, em espaço uv
    offset_edges_uv = []
    for i in range(n):
        p1uv = uvs[i]
        p2uv = uvs[(i + 1) % n]
        off = afastamentos.get(i, 0.0)
        if off > 0:
            duu = p2uv[0] - p1uv[0]
            dvv = p2uv[1] - p1uv[1]
            L2 = math.sqrt(duu**2 + dvv**2)
            if L2 < 1e-10:
                continue
            nx, ny = -dvv / L2, duu / L2
            mx2 = (p1uv[0] + p2uv[0]) / 2
            my2 = (p1uv[1] + p2uv[1]) / 2
            if nx * (ctr_uv[0] - mx2) + ny * (ctr_uv[1] - my2) < 0:
                nx, ny = -nx, -ny
            p1off = (p1uv[0] + nx * off, p1uv[1] + ny * off)
            p2off = (p2uv[0] + nx * off, p2uv[1] + ny * off)
        else:
            p1off = p1uv
            p2off = p2uv
        offset_edges_uv.append((p1off, p2off))

    if not offset_edges_uv:
        return None

    # 4. Faixa v
    all_v = [pt for edge in offset_edges_uv for pt in (edge[0][1], edge[1][1])]
    v_min = min(all_v)
    v_max = max(all_v)
    v_range = v_max - v_min
    if v_range < 1e-6:
        return None

    dv_step = v_range / n_slices

    # 5. Histograma: para cada fatia em v, calcular intervalo u válido
    u_lefts: list[float] = []
    u_rights: list[float] = []

    for k in range(n_slices):
        v_k = v_min + (k + 0.5) * dv_step
        xs: list[float] = []
        for (p1off, p2off) in offset_edges_uv:
            v1, v2 = p1off[1], p2off[1]
            if (v1 <= v_k < v2) or (v2 <= v_k < v1):
                t = (v_k - v1) / (v2 - v1)
                xs.append(p1off[0] + t * (p2off[0] - p1off[0]))
        if len(xs) < 2:
            u_lefts.append(0.0)
            u_rights.append(0.0)
        else:
            xs.sort()
            u_lefts.append(xs[0])
            u_rights.append(xs[-1])

    # 6. Maior retângulo no histograma — O(N²) com break precoce
    best_area = 0.0
    best_j = 0
    best_k = 0
    best_ul = 0.0
    best_ur = 0.0

    for j in range(n_slices):
        cur_ul = u_lefts[j]
        cur_ur = u_rights[j]
        if cur_ur - cur_ul < 1e-6:
            continue
        for k in range(j, n_slices):
            cur_ul = max(cur_ul, u_lefts[k])
            cur_ur = min(cur_ur, u_rights[k])
            if cur_ur - cur_ul < 1e-6:
                break
            area = (k - j + 1) * dv_step * (cur_ur - cur_ul)
            if area > best_area:
                best_area = area
                best_j = j
                best_k = k
                best_ul = cur_ul
                best_ur = cur_ur

    if best_area < 1.0:
        return None

    # 7. Converter de volta para UTM
    v_bot = v_min + best_j * dv_step
    v_top = v_min + (best_k + 1) * dv_step
    return [
        from_uv(best_ul, v_bot),
        from_uv(best_ur, v_bot),
        from_uv(best_ur, v_top),
        from_uv(best_ul, v_top),
    ]


# ─────────────────────────────────────────────────────────────
# Resultado
# ─────────────────────────────────────────────────────────────

@dataclass
class ResultadoSimulacao:
    area_lote: float
    area_construida_max: float
    area_projecao_max: float
    area_permeavel_min: float
    altura_total_m: float
    area_util_por_pav: float
    n_unidades_max: int
    n_vagas: int
    n_vagas_subsolo: int
    area_garagem_terreo: float
    area_garagem_subsolo: float
    alertas: list[str]
    geojson_footprint: dict
    geojson_lote: dict
    geojson_embasamento: Optional[dict]
    coords_footprint_utm: list
    coords_embasamento_utm: Optional[list]
    metricas: dict


# ─────────────────────────────────────────────────────────────
# Motor principal
# ─────────────────────────────────────────────────────────────

def calcular_envelope(
    geojson_feature: dict,
    config: ConfigSimulacao,
) -> ResultadoSimulacao:
    alertas: list[str] = []
    zona = config.zona
    garagem = config.garagem
    altura_m = config.altura_total_m

    # ── 1. Geometria ──────────────────────────────────────────
    coords = extrair_coords_simples(geojson_feature)
    area_lote = area_poligono(coords)

    # ── 2. Gabarito ───────────────────────────────────────────
    if zona.gabarito_max_m and altura_m > zona.gabarito_max_m:
        alertas.append(
            f"⚠️ Altura {altura_m:.1f}m excede gabarito máximo "
            f"({zona.gabarito_max_m:.1f}m) em {zona.sigla_display}."
        )

    # ── 3. CA ─────────────────────────────────────────────────
    ca = (zona.ca_permissivel if (config.usar_ca_permissivel and zona.ca_permissivel)
          else zona.ca_basico)

    # ── 4. Afastamentos ───────────────────────────────────────
    recuo = config.recuo_frontal_efetivo()
    afastamentos: dict[int, float] = {i: recuo for i in config.idx_frentes}

    # Laterais/fundos: valores definidos pelo usuário em config.afastamentos_laterais
    # O usuário pode colocar qualquer valor ≥ 0, mesmo quando facultado
    legal_val = zona.afastamento.calcular_legal(altura_m)
    is_fac    = zona.afastamento.is_facultado(altura_m)

    for idx, valor_usuario in config.afastamentos_laterais.items():
        if idx in config.idx_frentes:
            continue   # frente já definida
        if valor_usuario > 0:
            afastamentos[idx] = valor_usuario
        # valor_usuario == 0 → sem afastamento nessa aresta (facultado ou escolha do usuário)

        # Alertas: valor abaixo do mínimo legal
        if not is_fac and valor_usuario < legal_val:
            alertas.append(
                f"⚠️ Aresta {idx}: afastamento {valor_usuario:.2f}m abaixo do "
                f"mínimo legal ({legal_val:.2f}m)."
            )

    # ── 5. Footprint ──────────────────────────────────────────
    n_arestas = len(coords)
    usar_retangulo = (n_arestas > 4) or config.modo_retangular

    if usar_retangulo:
        coords_fp = footprint_retangular(coords, afastamentos, config.idx_frentes)
        if coords_fp is None:
            coords_fp = inset_poligono_simples(coords, afastamentos)
    else:
        coords_fp = inset_poligono_simples(coords, afastamentos)
        if coords_fp is None:
            coords_fp = footprint_retangular(coords, afastamentos, config.idx_frentes)

    if coords_fp is None:
        alertas.append("❌ Afastamentos tornaram o lote inviável.")
        coords_fp = coords

    area_fp = area_poligono(coords_fp)
    area_projecao_max = area_lote * zona.taxa_ocupacao
    if area_fp > area_projecao_max:
        alertas.append(
            f"⚠️ Footprint ({area_fp:.0f}m²) excede TO "
            f"({zona.taxa_ocupacao*100:.0f}% = {area_projecao_max:.0f}m²). "
            f"TO é o fator limitante."
        )
        area_fp = area_projecao_max

    # ── 6. Embasamento ────────────────────────────────────────
    coords_emb: Optional[list] = None
    geojson_emb: Optional[dict] = None

    emb = zona.embasamento
    if config.simular_embasamento and emb.permitido and emb.to_embasamento:
        afas_emb = {i: zona.recuo_frontal_m for i in config.idx_frentes}
        coords_emb = inset_poligono_simples(coords, afas_emb)
        if coords_emb:
            area_emb = min(area_poligono(coords_emb), area_lote * emb.to_embasamento)
            geojson_emb = {
                "type": "Feature",
                "properties": {
                    "tipo": "embasamento",
                    "altura_max_m": emb.altura_max_m,
                    "to_embasamento": emb.to_embasamento,
                    "area_m2": round(area_emb, 2),
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords_emb + [coords_emb[0]]]
                }
            }
            alertas.append(
                f"ℹ️ Embasamento até {emb.altura_max_m:.0f}m · "
                f"TO {emb.to_embasamento*100:.0f}% · "
                f"laterais ({emb.pct_perimetro_max*100:.0f}%) + fundos."
            )

    # ── 7. Área construída ────────────────────────────────────
    area_constr_ca  = area_lote * ca
    area_constr_pav = area_fp * (altura_m / 3.0)
    area_construida = min(area_constr_ca, area_constr_pav)
    area_util_pav   = area_fp

    # ── 8. Garagem ────────────────────────────────────────────
    area_gar_ter = area_gar_sub = 0.0
    n_vag = n_vag_sub = 0

    if not garagem.usar_subsolo:
        n_vag     = int(area_util_pav // garagem.area_vaga_terreo_m2)
        area_gar_ter = n_vag * garagem.area_vaga_terreo_m2
    else:
        n_vag_sub    = int((area_fp * garagem.n_subsolos) // garagem.area_vaga_subsolo_m2)
        area_gar_sub = n_vag_sub * garagem.area_vaga_subsolo_m2
        alertas.append(f"ℹ️ {garagem.n_subsolos} subsolo(s): {n_vag_sub} vagas.")
    n_vag = n_vag + n_vag_sub

    # ── 9. Unidades e permeabilidade ─────────────────────────
    area_perm = area_lote * zona.taxa_permeabilidade
    n_un = 0
    if zona.fracao_minima_m2 and zona.fracao_minima_m2 > 0:
        n_un = int(area_construida // zona.fracao_minima_m2)

    # ── 10. GeoJSON ───────────────────────────────────────────
    gj_fp = {
        "type": "Feature",
        "properties": {
            "tipo": "footprint", "zona": zona.sigla_display,
            "altura_m": round(altura_m, 2),
            "area_footprint_m2": round(area_fp, 2),
            "area_construida_m2": round(area_construida, 2),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords_fp + [coords_fp[0]]]
        }
    }
    gj_lote = {
        "type": "Feature",
        "properties": {"tipo": "lote", "area_m2": round(area_lote, 2)},
        "geometry": {"type": "Polygon", "coordinates": [coords + [coords[0]]]}
    }

    testada_m = calcular_testada(coords, config.idx_frentes)
    comp_frente = sum(
        math.sqrt((coords[(i+1)%len(coords)][0]-coords[i][0])**2 +
                  (coords[(i+1)%len(coords)][1]-coords[i][1])**2)
        for i in config.idx_frentes
    )

    metricas = {
        "CA utilizado": round(ca, 2),
        "Gabarito máx (m)": f"{zona.gabarito_max_m:.1f}" if zona.gabarito_max_m else "livre",
        "Afas. legal (m)": round(legal_val, 2),
        "Recuo frontal (m)": round(recuo, 2),
        "Testada (m)": round(testada_m, 2),
        "Comp. frente (m)": round(comp_frente, 2),
        "TO (%)": f"{zona.taxa_ocupacao*100:.1f}",
        "Permeabilidade (%)": f"{zona.taxa_permeabilidade*100:.1f}",
        "Área útil/pav (m²)": round(area_util_pav, 2),
        "Embasamento": "Sim" if (config.simular_embasamento and emb.permitido) else "Não",
    }

    return ResultadoSimulacao(
        area_lote=round(area_lote, 2),
        area_construida_max=round(area_construida, 2),
        area_projecao_max=round(area_projecao_max, 2),
        area_permeavel_min=round(area_perm, 2),
        altura_total_m=round(altura_m, 2),
        area_util_por_pav=round(area_util_pav, 2),
        n_unidades_max=n_un,
        n_vagas=n_vag,
        n_vagas_subsolo=n_vag_sub,
        area_garagem_terreo=round(area_gar_ter, 2),
        area_garagem_subsolo=round(area_gar_sub, 2),
        alertas=alertas,
        geojson_footprint=gj_fp,
        geojson_lote=gj_lote,
        geojson_embasamento=geojson_emb,
        coords_footprint_utm=coords_fp,
        coords_embasamento_utm=coords_emb,
        metricas=metricas,
    )


# ─────────────────────────────────────────────────────────────
# Otimização de pavimentos
# ─────────────────────────────────────────────────────────────

def otimizar_envelope(
    coords: list,
    zona: ParametrosZona,
    idx_frentes: list[int],
    recuo_frontal_m: float,
    h_pav_m: float = 3.0,
) -> dict:
    """
    Encontra n_pav e altura_total que maximiza a área construída,
    respeitando CA básico, TO e gabarito máximo.

    Aplica afastamento legal (H/divisor) a todas as arestas não-frente.
    Retorna dict com: n_pav, altura_m, area_footprint, area_construida,
                      fator_limitante ('CA' | 'gabarito' | 'TO'),
                      lateral_m, eficiencia_ca (%)
    """
    area_lote  = area_poligono(coords)
    n_arestas  = len(coords)
    ca         = zona.ca_basico
    area_ca    = area_lote * ca

    if zona.gabarito_max_m:
        n_max = max(1, int(zona.gabarito_max_m / h_pav_m))
    else:
        # sem gabarito: iterar até CA ser atingido com folga
        n_max = min(80, max(2, round(ca / zona.taxa_ocupacao) + 5))

    usar_retangulo = n_arestas > 4
    frentes_set = set(idx_frentes)
    best: dict = {}

    for n in range(1, n_max + 1):
        H = n * h_pav_m
        if zona.gabarito_max_m and H > zona.gabarito_max_m + 0.01:
            break

        lateral = zona.afastamento.calcular_legal(H)
        afas: dict[int, float] = {i: recuo_frontal_m for i in idx_frentes}
        for i in range(n_arestas):
            if i not in frentes_set and lateral > 0:
                afas[i] = lateral

        if usar_retangulo:
            fp = footprint_retangular(coords, afas, idx_frentes)
            if fp is None:
                fp = inset_poligono_simples(coords, afas)
        else:
            fp = inset_poligono_simples(coords, afas)
            if fp is None:
                fp = footprint_retangular(coords, afas, idx_frentes)

        if fp is None:
            break
        area_fp = min(area_poligono(fp), area_lote * zona.taxa_ocupacao)
        if area_fp < 1.0:
            break

        area_c = min(area_ca, area_fp * n)

        if not best or area_c > best["area_construida"]:
            if zona.gabarito_max_m and H >= zona.gabarito_max_m - 0.01:
                fator = "gabarito"
            elif area_fp * n >= area_ca:
                fator = "CA"
            else:
                fator = "TO"
            best = {
                "n_pav":          n,
                "altura_m":       round(H, 1),
                "area_footprint": round(area_fp, 1),
                "area_construida": round(area_c, 1),
                "fator_limitante": fator,
                "lateral_m":      round(lateral, 2),
                "eficiencia_ca":  round(area_c / area_ca * 100, 1),
            }

        # CA atingido → mais pavimentos só reduzem footprint, sem ganho
        if area_fp * n >= area_ca:
            break

    return best


def gerar_opcoes_otimizacao(
    coords: list,
    zona: ParametrosZona,
    idx_frentes: list[int],
    recuo_frontal_m: float,
    h_pav_m: float = 3.0,
) -> list:
    """
    Gera até 3 opções de configuração otimizada:
      Compacto  — metade dos pavimentos ótimos (footprint maior, menos afastamento)
      Ótimo     — maximiza área construída (resultado de otimizar_envelope)
      Torre     — gabarito máximo ou dobro do ótimo (menor footprint, mais altura)

    Cada item: label, descricao, n_pav, altura_m, area_footprint,
                area_construida, lateral_m, eficiencia_ca, coords_footprint (UTM)
    """
    area_lote = area_poligono(coords)
    n_arestas = len(coords)
    ca        = zona.ca_basico
    area_ca   = area_lote * ca
    usar_retangulo = n_arestas > 4
    frentes_set = set(idx_frentes)

    def _calcular(n: int) -> dict | None:
        if zona.gabarito_max_m:
            n = min(n, max(1, int(zona.gabarito_max_m / h_pav_m)))
        n = max(1, n)
        H       = n * h_pav_m
        lateral = zona.afastamento.calcular_legal(H)
        afas: dict[int, float] = {i: recuo_frontal_m for i in idx_frentes}
        for i in range(n_arestas):
            if i not in frentes_set and lateral > 0:
                afas[i] = lateral
        if usar_retangulo:
            fp = footprint_retangular(coords, afas, idx_frentes)
            if fp is None:
                fp = inset_poligono_simples(coords, afas)
        else:
            fp = inset_poligono_simples(coords, afas)
            if fp is None:
                fp = footprint_retangular(coords, afas, idx_frentes)
        if fp is None:
            return None
        area_fp = min(area_poligono(fp), area_lote * zona.taxa_ocupacao)
        if area_fp < 1.0:
            return None
        area_c = min(area_ca, area_fp * n)
        return {
            "n_pav":           n,
            "altura_m":        round(H, 1),
            "area_footprint":  round(area_fp, 1),
            "area_construida": round(area_c, 1),
            "lateral_m":       round(lateral, 2),
            "eficiencia_ca":   round(area_c / area_ca * 100, 1),
            "coords_footprint": fp,
        }

    opt = otimizar_envelope(coords, zona, idx_frentes, recuo_frontal_m, h_pav_m)
    if not opt:
        return []
    n_opt = opt["n_pav"]

    if zona.gabarito_max_m:
        n_torre = max(1, int(zona.gabarito_max_m / h_pav_m))
    else:
        n_torre = n_opt * 2

    candidatos = [
        ("Compacto", "Footprint maior, menos pavimentos",        max(1, n_opt // 2)),
        ("Ótimo",    "Maximiza área construída",                 n_opt),
        ("Torre",    "Gabarito máximo" if zona.gabarito_max_m
                     else "Altura estendida",                    n_torre),
    ]

    opcoes: list[dict] = []
    for label, desc, n in candidatos:
        r = _calcular(n)
        if r is None:
            continue
        if any(o["n_pav"] == r["n_pav"] for o in opcoes):
            continue          # descarta duplicatas
        r["label"]    = label
        r["descricao"] = desc
        opcoes.append(r)

    return opcoes
