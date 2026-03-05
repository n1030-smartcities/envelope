"""
app.py — Motor de Envelope Construtivo · Streamlit
Multi-cidade via SQLite. Afastamento lateral sempre editável
(mesmo quando facultado pela lei).
"""
from __future__ import annotations
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

from schema import ConfigGaragem, ConfigSimulacao
from calculo import (
    calcular_envelope,
    extrair_coords_simples,
    arestas_info,
    area_poligono,
    inset_poligono_simples,
    footprint_retangular,
    calcular_testada,
    otimizar_envelope,
    gerar_opcoes_otimizacao,
)
from coordenadas import coords_utm_to_wgs84, coords_wgs84_to_utm, is_wgs84
from db_manager import DBManager
from geometria import simplificar_poligono, detectar_zona_geojson, compass_label
from viewer3d import render_3d
import streamlit.components.v1 as components

DB_PATH = os.path.join(os.path.dirname(__file__), "params.db")

# ── Rebuild automático se banco não existe ─────────────────────
if not os.path.exists(DB_PATH):
    from db_builder import build_db
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    build_db(data_dir, DB_PATH)

_mgr = DBManager(DB_PATH)

# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Envelope Construtivo",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Tema ─────────────────────────────────────────────────────
if "tema_ui" not in st.session_state:
    st.session_state.tema_ui = "Escuro"

with st.sidebar:
    st.radio("🎨 Tema", ["Escuro", "Claro"], key="tema_ui",
             horizontal=True, label_visibility="collapsed")

_T = {
    "Claro": {
        "bg": "#f7f8fb", "surface": "#ffffff", "surface2": "#f2f4f8",
        "accent": "#c58900", "accent2": "#0f766e", "danger": "#b42318",
        "warn": "#b45309", "text": "#111827", "muted": "#6b7280", "border": "#e5e7eb",
    },
    "Escuro": {
        "bg": "#0d0f14", "surface": "#151820", "surface2": "#1c2030",
        "accent": "#e8c547", "accent2": "#4ecdc4", "danger": "#ff6b6b",
        "warn": "#f59e0b", "text": "#e8eaf0", "muted": "#6b7280", "border": "#252a38",
    },
}[st.session_state.tema_ui]

st.markdown(f"""<style>
:root{{
  --bg:{_T["bg"]};--surface:{_T["surface"]};--surface2:{_T["surface2"]};
  --accent:{_T["accent"]};--accent2:{_T["accent2"]};--danger:{_T["danger"]};
  --warn:{_T["warn"]};--text:{_T["text"]};--muted:{_T["muted"]};--border:{_T["border"]};
}}
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
html,body,[class*="css"]{{font-family:'Syne',sans-serif;background:var(--bg);color:var(--text);}}
.stApp{{background:var(--bg);}}
section[data-testid="stSidebar"]{{background:var(--surface);border-right:1px solid var(--border);}}
.stSelectbox>div>div,.stNumberInput>div>div>input,.stTextArea textarea{{
  background:var(--surface2)!important;border:1px solid var(--border)!important;
  color:var(--text)!important;border-radius:6px!important;font-family:'Space Mono',monospace!important;}}
.stSelectbox label,.stNumberInput label,.stCheckbox label,.stTextArea label,.stSlider label{{
  color:var(--muted)!important;font-size:11px!important;letter-spacing:0.08em!important;text-transform:uppercase!important;}}
.stButton>button{{background:var(--accent)!important;color:#0d0f14!important;border:none!important;
  border-radius:4px!important;font-family:'Space Mono',monospace!important;font-weight:700!important;
  padding:0.6rem 1.4rem!important;width:100%!important;}}
.stButton>button:hover{{background:#f5d76e!important;transform:translateY(-1px);}}
[data-testid="stMetric"]{{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:16px 20px;}}
[data-testid="stMetricLabel"]{{color:var(--muted)!important;font-size:11px!important;letter-spacing:0.1em!important;text-transform:uppercase!important;}}
[data-testid="stMetricValue"]{{color:var(--accent)!important;font-family:'Space Mono',monospace!important;font-size:1.6rem!important;}}
.card{{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:20px 24px;margin-bottom:12px;}}
.card-title{{font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}}
.card-value{{font-family:'Space Mono',monospace;font-size:1.4rem;color:var(--accent);}}
.card-sub{{font-size:12px;color:var(--muted);margin-top:4px;}}
.al-err{{background:rgba(255,107,107,0.08);border-left:3px solid var(--danger);border-radius:4px;
  padding:10px 14px;margin:6px 0;font-size:13px;font-family:'Space Mono',monospace;}}
.al-warn{{background:rgba(245,158,11,0.08);border-left:3px solid var(--warn);border-radius:4px;
  padding:10px 14px;margin:6px 0;font-size:13px;font-family:'Space Mono',monospace;}}
.al-info{{background:rgba(78,205,196,0.08);border-left:3px solid var(--accent2);border-radius:4px;
  padding:10px 14px;margin:6px 0;font-size:13px;font-family:'Space Mono',monospace;}}
.hero-title{{font-size:2.2rem;font-weight:800;letter-spacing:-0.02em;margin-bottom:4px;}}
.hero-title span{{color:var(--accent);}}
.hero-sub{{color:var(--muted);font-family:'Space Mono',monospace;font-size:13px;letter-spacing:0.05em;}}
.divider{{height:1px;background:var(--border);margin:24px 0;}}
.mapa-container{{background:var(--surface2);border:1px solid var(--border);border-radius:8px;overflow:hidden;min-height:480px;}}
button[data-baseweb="tab"]{{font-family:'Space Mono',monospace!important;font-size:12px!important;letter-spacing:0.08em!important;}}
.stCheckbox>label{{color:var(--text)!important;text-transform:none!important;font-size:14px!important;letter-spacing:normal!important;}}
details summary{{color:var(--accent2)!important;font-family:'Space Mono',monospace!important;font-size:12px!important;}}
.badge{{display:inline-block;font-family:'Space Mono',monospace;font-size:10px;font-weight:700;
  letter-spacing:0.1em;padding:3px 8px;border-radius:3px;margin-left:6px;vertical-align:middle;}}
.badge-cidade{{background:var(--accent);color:#0d0f14;}}
.badge-auto{{background:var(--accent2);color:#0d0f14;font-size:9px;}}
.badge-fac{{background:rgba(78,205,196,0.15);color:var(--accent2);border:1px solid var(--accent2);}}
.badge-legal{{background:rgba(245,158,11,0.15);color:var(--warn);border:1px solid var(--warn);}}
::-webkit-scrollbar{{width:6px;background:var(--bg);}}
::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px;}}
</style>""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────
def _converter_geojson_para_utm(feature: dict) -> tuple[dict, bool]:
    """
    Se o GeoJSON estiver em WGS84 (graus decimais), converte para UTM 22S.
    Retorna (feature_utm, foi_convertido).
    """
    import copy
    geom = feature.get("geometry", feature)
    gtype = geom.get("type", "")

    # Pega amostra de coordenadas para detectar o CRS
    sample: list = []
    if gtype == "Polygon":
        sample = geom["coordinates"][0][:1]
    elif gtype == "MultiPolygon":
        sample = geom["coordinates"][0][0][:1]

    if not sample or not is_wgs84(sample):
        return feature, False

    feat = copy.deepcopy(feature)
    g = feat.get("geometry", feat)
    if gtype == "Polygon":
        g["coordinates"] = [
            coords_wgs84_to_utm(ring) for ring in g["coordinates"]
        ]
    elif gtype == "MultiPolygon":
        g["coordinates"] = [
            [coords_wgs84_to_utm(ring) for ring in poly]
            for poly in g["coordinates"]
        ]
    return feat, True


def alerta(msg: str) -> str:
    if msg.startswith("❌"):
        cls = "al-err"
    elif msg.startswith("⚠"):
        cls = "al-warn"
    else:
        cls = "al-info"
    return f'<div class="{cls}">{msg}</div>'


def render_svg(
    coords_lote, coords_fp, coords_emb,
    arestas_simpl, idx_frentes: list[int], laterais_idx,
    width=620, height=460,
) -> str:
    BG   = "#151820" if st.session_state.tema_ui == "Escuro" else "#f2f4f8"
    GRID = "#1c2030" if st.session_state.tema_ui == "Escuro" else "#e5e7eb"

    xs = [c[0] for c in coords_lote]; ys = [c[1] for c in coords_lote]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    dx = maxx - minx or 1; dy = maxy - miny or 1
    pad = 60; sw = width - 2*pad; sh = height - 2*pad
    scale = min(sw/dx, sh/dy)
    offx = pad + (sw - dx*scale)/2; offy = pad + (sh - dy*scale)/2

    def sv(c): return (offx + (c[0]-minx)*scale, offy + (maxy-c[1])*scale)
    def pts(cs): return " ".join(f"{sv(c)[0]:.1f},{sv(c)[1]:.1f}" for c in cs)

    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'style="background:{BG};border-radius:8px;font-family:Space Mono,monospace">')
    p.append(f'<defs><pattern id="gr" width="20" height="20" patternUnits="userSpaceOnUse">'
             f'<path d="M20 0L0 0 0 20" fill="none" stroke="{GRID}" stroke-width="1"/>'
             f'</pattern></defs>')
    p.append(f'<rect width="{width}" height="{height}" fill="url(#gr)"/>')

    if coords_emb and len(coords_emb) >= 3:
        p.append(f'<polygon points="{pts(coords_emb)}" '
                 f'fill="rgba(78,205,196,0.12)" stroke="#4ecdc4" stroke-width="1.5" '
                 f'stroke-dasharray="4,2" stroke-linejoin="round"/>')

    p.append(f'<polygon points="{pts(coords_lote)}" '
             f'fill="#1c2030" stroke="#6b7280" stroke-width="1" stroke-linejoin="round"/>')

    if coords_fp and len(coords_fp) >= 3:
        p.append(f'<polygon points="{pts(coords_fp)}" '
                 f'fill="rgba(232,197,71,0.18)" stroke="#e8c547" stroke-width="2" '
                 f'stroke-dasharray="6,3" stroke-linejoin="round"/>')

    for c in coords_lote:
        sx, sy = sv(c)
        p.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="2" fill="#3d4455"/>')

    _frentes_set = set(idx_frentes)
    for ar in arestas_simpl:
        p1s = sv(ar["p1"]); p2s = sv(ar["p2"]); mx, my = sv(ar["midpoint"])
        is_frente  = (ar["idx"] in _frentes_set)
        is_lat     = (ar["idx"] in laterais_idx)
        cor = "#ff6b6b" if is_frente else ("#4ecdc4" if is_lat else "#4a5568")
        lw  = "3" if is_frente else ("2.5" if is_lat else "1.5")
        label = (f"▶ {ar['comprimento']:.0f}m" if is_frente else
                 f"◀ {ar['comprimento']:.0f}m" if is_lat else
                 f"{ar['comprimento']:.0f}m")

        p.append(f'<line x1="{p1s[0]:.1f}" y1="{p1s[1]:.1f}" '
                 f'x2="{p2s[0]:.1f}" y2="{p2s[1]:.1f}" '
                 f'stroke="{cor}" stroke-width="{lw}" stroke-linecap="round"/>')
        dxa = p2s[0]-p1s[0]; dya = p2s[1]-p1s[1]
        ang = math.degrees(math.atan2(dya, dxa))
        norm = math.sqrt(dxa**2 + dya**2) or 1
        px = -dya/norm*16; py = dxa/norm*16
        p.append(f'<text x="{mx+px:.1f}" y="{my+py:.1f}" fill="{cor}" font-size="10" '
                 f'text-anchor="middle" dominant-baseline="middle" '
                 f'transform="rotate({ang:.1f},{mx+px:.1f},{my+py:.1f})">{label}</text>')
        if is_frente or is_lat:
            p.append(f'<text x="{mx:.1f}" y="{my:.1f}" fill="{cor}" font-size="11" '
                     f'text-anchor="middle" dominant-baseline="middle" '
                     f'font-weight="bold">#{ar["idx"]}</text>')

    for ar in arestas_simpl:
        sx, sy = sv(ar["p1"])
        is_frente = (ar["idx"] in _frentes_set)
        is_lat    = (ar["idx"] in laterais_idx)
        cor = "#ff6b6b" if is_frente else ("#4ecdc4" if is_lat else "#6b7280")
        r   = "5" if (is_frente or is_lat) else "3"
        p.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r}" fill="{cor}" '
                 f'stroke="#0d0f14" stroke-width="1"/>')
        p.append(f'<text x="{sx:.1f}" y="{sy-9:.1f}" fill="{cor}" font-size="9" '
                 f'text-anchor="middle">{ar["idx"]}</text>')

    ly = height - 14
    for ii, (lbl, cor) in enumerate([
        ("── Footprint", "#e8c547"), ("── Embasamento", "#4ecdc4"),
        ("● Frente", "#ff6b6b"), ("● Lateral", "#4ecdc4"),
    ]):
        p.append(f'<text x="{pad + ii*140}" y="{ly}" fill="{cor}" font-size="9">{lbl}</text>')

    p.append('</svg>')
    return "".join(p)


# ─── Session state ────────────────────────────────────────────
for k, v in [("geojson_raw", None), ("resultado", None), ("config_salva", None)]:
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown("**📂 LOTE (GeoJSON)**")
    arquivo = st.file_uploader("Upload .geojson / .json / .zip", type=["geojson", "json", "zip"])
    if arquivo:
        try:
            import zipfile, io
            if arquivo.name.lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(arquivo.read())) as zf:
                    geojson_names = [n for n in zf.namelist()
                                     if n.lower().endswith((".geojson", ".json"))]
                    if not geojson_names:
                        st.error("ZIP não contém nenhum arquivo .geojson / .json.")
                        geojson_names = None
                    if geojson_names:
                        with zf.open(geojson_names[0]) as f:
                            gj = json.load(f)
            else:
                gj = json.load(arquivo)

            if gj.get("type") == "FeatureCollection":
                gj = gj["features"][0]
            gj, _conv = _converter_geojson_para_utm(gj)
            if _conv:
                st.info("Coordenadas WGS84 detectadas e convertidas para UTM 22S automaticamente.")
            st.session_state.geojson_raw = gj
            st.session_state.resultado = None
        except Exception as e:
            st.error(f"Erro: {e}")

    with st.expander("ou cole o JSON"):
        txt = st.text_area("JSON", height=80, label_visibility="collapsed",
                           placeholder='{"type":"Feature",...}')
        if txt.strip():
            try:
                gj = json.loads(txt)
                if gj.get("type") == "FeatureCollection":
                    gj = gj["features"][0]
                gj, _conv = _converter_geojson_para_utm(gj)
                if _conv:
                    st.info("Coordenadas WGS84 detectadas e convertidas para UTM 22S automaticamente.")
                st.session_state.geojson_raw = gj
                st.session_state.resultado = None
            except Exception as e:
                st.error(f"JSON inválido: {e}")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Cidade ────────────────────────────────────────────────
    st.markdown("**🏙️ CIDADE**")
    cidades = _mgr.cidades_disponiveis()
    if not cidades:
        st.error("params.db vazio. Rode: python db_builder.py")
        st.stop()

    cidade_sel = st.selectbox(
        "Cidade", options=cidades,
        format_func=lambda c: c.capitalize(),
        key="cidade_sel_sb",
    )

    # ── Zona ─────────────────────────────────────────────────
    zonas_dict = _mgr.zonas(cidade_sel)
    st.markdown("**🗺️ ZONA**")

    autodetect = None
    if st.session_state.geojson_raw:
        props = st.session_state.geojson_raw.get("properties", {})
        autodetect = detectar_zona_geojson(props, cidade_sel)

    keys_sorted = sorted(zonas_dict.keys())
    def_key = keys_sorted[0]
    is_auto = False
    if autodetect:
        chave_auto, conf = autodetect
        if chave_auto in zonas_dict:
            def_key = chave_auto
            is_auto = conf

    z_idx = keys_sorted.index(def_key) if def_key in keys_sorted else 0
    zona_chave = st.selectbox(
        "Zona / Setor", options=keys_sorted, index=z_idx,
        format_func=lambda k: f"{k}  —  {zonas_dict[k].nome[:36]}",
    )
    if is_auto:
        st.markdown('<span class="badge badge-auto">🎯 autodetect</span>',
                    unsafe_allow_html=True)

    zona = zonas_dict[zona_chave]

    with st.expander("📋 Parâmetros da zona"):
        af = zona.afastamento
        af_formula = (
            f"H/{af.divisor:g}" + (f"+{af.acrescimo:g}" if af.acrescimo else "")
            + f" mín {af.minimo:g}m"
            if af.divisor else (f"fixo {af.minimo:g}m" if af.minimo else "sem afastamento")
        )
        fac_str = (
            "nunca facultado" if not af.facultado_ate_m and af.minimo > 0
            else (f"H ≤ {af.facultado_ate_m:.0f}m" if af.facultado_ate_m else "sempre facultado")
        )
        st.markdown(f"""<div style="font-family:'Space Mono',monospace;font-size:12px;line-height:2.2">
        <span style="color:var(--muted)">CA básico</span> · <b>{zona.ca_basico}</b><br>
        <span style="color:var(--muted)">CA permissível</span> · <b>{zona.ca_permissivel or "—"}</b><br>
        <span style="color:var(--muted)">Gabarito máx</span> · <b>{"livre" if not zona.gabarito_max_m else f"{zona.gabarito_max_m:.0f}m"}</b><br>
        <span style="color:var(--muted)">TO</span> · <b>{zona.taxa_ocupacao*100:.0f}%</b><br>
        <span style="color:var(--muted)">Permeabilidade</span> · <b>{zona.taxa_permeabilidade*100:.0f}%</b><br>
        <span style="color:var(--muted)">Recuo frontal</span> · <b>{zona.recuo_frontal_m:.1f}m</b><br>
        <span style="color:var(--muted)">Afas. lateral</span> · <b>{af_formula}</b><br>
        <span style="color:var(--muted)">Facultado</span> · <b>{fac_str}</b><br>
        <span style="color:var(--muted)">Fração/unidade</span> · <b>{f"{zona.fracao_minima_m2:.0f}m²" if zona.fracao_minima_m2 else "—"}</b><br>
        <span style="color:var(--muted)">Embasamento</span> · <b>{"Sim" if zona.embasamento.permitido else "Não"}</b>
        </div>""", unsafe_allow_html=True)
        if zona.observacoes:
            st.caption(zona.observacoes[:200])

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Simulação ─────────────────────────────────────────────
    st.markdown("**📐 SIMULAÇÃO**")

    gab_max = zona.gabarito_max_m or 120.0
    altura_m = st.number_input(
        "Altura total (m)",
        min_value=3.0, max_value=float(gab_max),
        value=min(9.0, float(gab_max)), step=0.5,
        help=f"Gabarito máximo: {zona.gabarito_max_m:.0f}m" if zona.gabarito_max_m else "Sem limite",
    )

    usar_ca_perm = False
    if zona.ca_permissivel:
        usar_ca_perm = st.checkbox(f"CA permissível ({zona.ca_permissivel})", value=False)

    simular_emb = False
    if zona.embasamento.permitido:
        simular_emb = st.checkbox(
            f"Embasamento (até {zona.embasamento.altura_max_m:.0f}m, "
            f"TO {(zona.embasamento.to_embasamento or 0)*100:.0f}%)",
            value=False,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Garagem ───────────────────────────────────────────────
    st.markdown("**🚗 GARAGEM**")
    usar_subsolo = st.checkbox("Garagem em subsolo", value=False)
    if usar_subsolo:
        n_subsolos    = st.number_input("Nº de subsolos", 1, 5, 1, step=1)
        area_vaga_sub = st.number_input("m²/vaga subsolo", 25.0, 60.0, 35.0, step=1.0)
        area_vaga_ter = 30.0
    else:
        n_subsolos    = 0
        area_vaga_ter = st.number_input("m²/vaga térreo", 20.0, 50.0, 30.0, step=1.0)
        area_vaga_sub = 35.0

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    btn_calcular = st.button("⚡ CALCULAR ENVELOPE", use_container_width=True)


# ─────────────────────────────────────────────────────────────
# TELA INICIAL
# ─────────────────────────────────────────────────────────────
if st.session_state.geojson_raw is None:
    st.markdown('<div class="hero-title">Motor de <span>Envelope</span> Construtivo</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Curitiba · Joinville · SQLite · SIRGAS 2000 UTM 22S</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for col, (tit, sub) in zip([c1, c2, c3], [
        ("01 · Lote",   "Upload do GeoJSON em UTM 22S. Zona detectada automaticamente das properties."),
        ("02 · Zona",   "Curitiba ou Joinville. Parâmetros carregados do banco SQLite (params.db)."),
        ("03 · Afaste", "Afastamento lateral sempre editável — mesmo quando facultado pela lei."),
    ]):
        col.markdown(f"""<div class="card">
            <div class="card-title">{tit}</div>
            <div class="card-sub" style="font-size:13px;line-height:1.6">{sub}</div>
        </div>""", unsafe_allow_html=True)
    st.stop()


# ─────────────────────────────────────────────────────────────
# LOTE CARREGADO
# ─────────────────────────────────────────────────────────────
geojson      = st.session_state.geojson_raw
coords_orig  = extrair_coords_simples(geojson)
area_lote    = area_poligono(coords_orig)
n_orig       = len(coords_orig)

SIMPLIFICAR = n_orig > 20
coords_simpl = (simplificar_poligono(coords_orig, angulo_threshold_deg=3.0)[0]
                if SIMPLIFICAR else coords_orig)
arestas_simpl = arestas_info(coords_simpl)
n_simpl       = len(arestas_simpl)

# Hero
st.markdown(
    f'<div class="hero-title">Motor de <span>Envelope</span> Construtivo'
    f'<span class="badge badge-cidade">{cidade_sel.upper()}</span></div>',
    unsafe_allow_html=True)
st.markdown(
    f'<div class="hero-sub">LOTE · {area_lote:,.0f}m²'
    f' · {n_orig} vértices{f" → {n_simpl} simplificados" if SIMPLIFICAR else ""}'
    f' · {zona.sigla_display} · {altura_m:.1f}m</div>',
    unsafe_allow_html=True)

# ── Propriedades do GeoJSON carregado ─────────────────────────
_props_raw = geojson.get("properties") or {}
_WKT_KEYS  = {"wkt", "geom", "geometry", "the_geom", "wkb", "shape"}
_props_show = {
    k: v for k, v in _props_raw.items()
    if k.lower() not in _WKT_KEYS
    and not (isinstance(v, str) and len(v) > 120)
    and v not in (None, "", [])
}
if _props_show:
    _itens = "".join(
        f'<span style="color:var(--muted);font-size:10px;text-transform:uppercase;'
        f'letter-spacing:.07em">{k}</span>'
        f'<span style="font-family:\'Space Mono\',monospace;font-size:12px;'
        f'margin-left:4px;margin-right:18px;color:var(--text)">{v}</span>'
        for k, v in _props_show.items()
    )
    st.markdown(
        f'<div style="background:var(--surface2);border:1px solid var(--border);'
        f'border-radius:6px;padding:10px 16px;margin-top:8px;'
        f'display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 0">{_itens}</div>',
        unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PASSO 1 — SELECIONAR FRENTE DO LOTE
# ─────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
    'color:var(--muted);margin-bottom:10px">01 · Identifique e selecione a aresta de frente</div>',
    unsafe_allow_html=True)

def _arestas_consecutivas(idxs: list[int], n: int) -> bool:
    if len(idxs) <= 1:
        return True
    s = sorted(idxs)
    # Verificar consecutividade circular: existe início tal que idxs formem uma cadeia
    for start in s:
        run = [(start + j) % n for j in range(len(s))]
        if sorted(run) == s:
            return True
    return False

_col_sel, _col_svg1 = st.columns([2, 3], gap="large")

with _col_sel:
    _rows_ar = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
        f'border-bottom:1px solid var(--border);font-size:12px;'
        f'font-family:\'Space Mono\',monospace">'
        f'<span style="color:var(--accent)">#{ar["idx"]}</span>'
        f'<span>{ar["comprimento"]:.1f} m</span>'
        f'<span style="color:var(--muted)">{compass_label(ar["angulo_graus"])}'
        f' {ar["angulo_graus"]:.0f}°</span>'
        f'</div>'
        for ar in arestas_simpl
    )
    st.markdown(
        f'<div style="background:var(--surface2);border:1px solid var(--border);'
        f'border-radius:6px;padding:10px 14px;margin-bottom:14px">'
        f'<div style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;'
        f'color:var(--muted);margin-bottom:8px">Arestas do lote</div>'
        f'{_rows_ar}</div>',
        unsafe_allow_html=True)

    idx_frentes_raw = st.multiselect(
        "Aresta(s) de FRENTE (via pública)",
        options=list(range(n_simpl)),
        default=[0],
        format_func=lambda i: (
            f"#{i} — {arestas_simpl[i]['comprimento']:.1f}m"
            f" ({compass_label(arestas_simpl[i]['angulo_graus'])})"
        ),
        help="Selecione uma ou mais arestas adjacentes que fazem frente para a via pública",
    )
    if not idx_frentes_raw:
        idx_frentes_raw = [0]

    # Validação de adjacência
    idx_frentes = sorted(idx_frentes_raw)
    if len(idx_frentes) > 1 and not _arestas_consecutivas(idx_frentes, n_simpl):
        st.warning("⚠️ As arestas de frente devem ser consecutivas. Usando apenas a primeira.")
        idx_frentes = [idx_frentes[0]]

    # Para uso legado (single-front helpers)
    idx_frente = idx_frentes[0]

    # Testada e comprimento de frente
    testada_m   = calcular_testada(coords_simpl, idx_frentes)
    comp_frente = sum(arestas_simpl[i]["comprimento"] for i in idx_frentes)
    st.markdown(
        f'<div style="background:var(--surface2);border:1px solid var(--border);'
        f'border-radius:6px;padding:8px 14px;margin-top:6px;'
        f'font-family:\'Space Mono\',monospace;font-size:12px">'
        f'<span style="color:var(--muted)">Testada</span> '
        f'<b style="color:var(--accent)">{testada_m:.1f}m</b>'
        f'{"" if len(idx_frentes) == 1 else f"  ·  <span style=\'color:var(--muted)\'>Comp. frente</span> <b>{comp_frente:.1f}m</b>"}'
        f'</div>',
        unsafe_allow_html=True)

with _col_svg1:
    _svg_p1 = render_svg(coords_orig, None, None, arestas_simpl, idx_frentes, [])
    st.markdown(f'<div class="mapa-container">{_svg_p1}</div>', unsafe_allow_html=True)
    st.caption("Aresta(s) em vermelho = frente selecionada · Selecione as arestas que fazem frente para a rua")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PASSO 2 — CONFIGURAÇÕES OTIMIZADAS
# ─────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
    'color:var(--muted);margin-bottom:10px">02 · Configurações otimizadas · selecione para visualizar</div>',
    unsafe_allow_html=True)

_c_hpav, _ = st.columns([1, 5])
with _c_hpav:
    h_pav_ot = st.number_input(
        "m/pav (otim.)", min_value=2.5, max_value=6.0,
        value=3.0, step=0.5, key="h_pav_ot",
        help="Altura por pavimento usada no cálculo de otimização",
    )

opcoes_ot = gerar_opcoes_otimizacao(coords_simpl, zona, idx_frentes, zona.recuo_frontal_m, h_pav_ot)

if "opcao_ot_sel" not in st.session_state:
    st.session_state.opcao_ot_sel = None

if opcoes_ot:
    _card_cols = st.columns(len(opcoes_ot))
    for _ci, (_ccol, _op) in enumerate(zip(_card_cols, opcoes_ot)):
        with _ccol:
            _is_sel  = (st.session_state.opcao_ot_sel == _ci)
            _brd     = "2px solid var(--accent)" if _is_sel else "1px solid var(--border)"
            _bg      = "rgba(232,197,71,0.07)"   if _is_sel else "var(--surface2)"
            _ef_cor  = "var(--accent2)" if _op["eficiencia_ca"] >= 95 else "var(--warn)"
            st.markdown(f"""<div style="background:{_bg};border:{_brd};border-radius:8px;
padding:14px 16px;margin-bottom:6px;min-height:160px">
<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;
color:var(--muted)">{_op['label']}</div>
<div style="font-size:9px;color:var(--muted);margin-bottom:10px">{_op['descricao']}</div>
<div style="font-family:'Space Mono',monospace;margin-bottom:8px">
  <span style="color:var(--accent);font-size:1.2rem;font-weight:700">{_op['n_pav']} pav</span>
  <span style="color:var(--muted);font-size:11px"> · {_op['altura_m']:.0f} m</span>
</div>
<div style="font-size:12px;font-family:'Space Mono',monospace;line-height:1.9">
  <span style="color:var(--muted)">Constr. </span>{_op['area_construida']:,.0f} m²<br>
  <span style="color:var(--muted)">Footprint </span>{_op['area_footprint']:,.0f} m²<br>
  <span style="color:var(--muted)">Afas. lat. </span>{_op['lateral_m']:.2f} m<br>
  <span style="color:{_ef_cor}">Ef. CA {_op['eficiencia_ca']:.0f}%</span>
</div></div>""", unsafe_allow_html=True)

            _btn_lbl = "✓ Visualizando" if _is_sel else "Visualizar"
            if st.button(_btn_lbl, key=f"btn_ot_{_ci}", use_container_width=True):
                st.session_state.opcao_ot_sel = None if _is_sel else _ci
                st.rerun()

# Footprint da opção selecionada (passado para o SVG)
_sel_idx   = st.session_state.opcao_ot_sel
coords_fp_ot = (
    opcoes_ot[_sel_idx]["coords_footprint"]
    if _sel_idx is not None and opcoes_ot and 0 <= _sel_idx < len(opcoes_ot)
    else None
)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# LAYOUT: Mapa | Configuração de arestas
# ─────────────────────────────────────────────────────────────
col_mapa, col_cfg = st.columns([3, 2], gap="large")

# Calcular afastamento legal atual
legal_val = zona.afastamento.calcular_legal(altura_m)
is_fac    = zona.afastamento.is_facultado(altura_m)

with col_cfg:
    _frentes_label = (f"aresta #{idx_frentes[0]}" if len(idx_frentes) == 1
                      else f"arestas {', '.join(f'#{i}' for i in idx_frentes)}")
    st.markdown(
        f'<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
        f'color:var(--muted);margin-bottom:14px">03 · Configurar afastamentos'
        f' · frente: {_frentes_label}</div>',
        unsafe_allow_html=True)

    # Recuo frontal editável
    recuo_legal_m = zona.recuo_frontal_m
    c_rf, c_rf_tag = st.columns([4, 1])
    with c_rf:
        recuo_frontal_m = st.number_input(
            f"↔ Recuo frontal (m)  [legal: {recuo_legal_m:.1f}m]",
            min_value=0.0, max_value=50.0,
            value=float(recuo_legal_m),
            step=0.5, format="%.2f",
            key=f"rf_{zona_chave}",
        )
    with c_rf_tag:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if recuo_frontal_m < recuo_legal_m:
            st.markdown(
                f'<span class="badge badge-legal" style="font-size:9px;padding:2px 5px">'
                f'⚠ {recuo_legal_m:.1f}m</span>',
                unsafe_allow_html=True
            )
        elif recuo_frontal_m > recuo_legal_m:
            st.markdown(
                f'<span class="badge badge-fac" style="font-size:9px;padding:2px 5px">'
                f'+{recuo_frontal_m - recuo_legal_m:.1f}m</span>',
                unsafe_allow_html=True
            )
    # ── Modo retangular ───────────────────────────────────────
    _n_arestas_simpl = len(coords_simpl)
    if _n_arestas_simpl > 4:
        st.markdown(
            f'<div class="al-info" style="margin-bottom:8px">'
            f'Lote irregular ({_n_arestas_simpl} arestas) — footprint retangular ativado automaticamente.</div>',
            unsafe_allow_html=True)
        modo_retangular = True
    else:
        modo_retangular = st.checkbox(
            "Forçar footprint retangular",
            value=False,
            help="Usa retângulo inscrito máximo em vez do polígono insetado",
        )

    st.markdown("---")

    # ── Afastamentos laterais — SEMPRE editáveis ──────────────
    st.markdown("**🔵 Afastamentos laterais / fundos**")

    if is_fac:
        st.markdown(
            f'<div class="al-info" style="margin-bottom:12px">'
            f'<b>Facultado</b> para H={altura_m:.1f}m — afastamento zero é permitido. '
            f'Você pode definir um valor voluntário para qualquer aresta.</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="al-warn" style="margin-bottom:12px">'
            f'<b>Mínimo legal: {legal_val:.2f}m</b> para H={altura_m:.1f}m. '
            f'Você pode editar o valor — valores abaixo do legal geram alerta.</div>',
            unsafe_allow_html=True
        )

    afastamentos_laterais: dict[int, float] = {}
    for i in [x for x in range(n_simpl) if x not in set(idx_frentes)]:
        ar = arestas_simpl[i]
        dir_label = f"#{i} · {ar['comprimento']:.1f}m · {compass_label(ar['angulo_graus'])}"

        ativo = st.checkbox(
            dir_label,
            key=f"chk_{i}_{zona_chave}_{altura_m}",
            value=True,
        )
        if ativo:
            # Default: legal quando obrigatório, 0 quando facultado
            val_default = round(legal_val, 2) if not is_fac else 0.0

            c_num, c_tag = st.columns([4, 1])
            with c_num:
                val = st.number_input(
                    f"m · aresta #{i}",
                    min_value=0.0, max_value=50.0,
                    value=val_default, step=0.1, format="%.2f",
                    key=f"af_{i}_{zona_chave}_{altura_m}",
                    label_visibility="collapsed",
                )
            with c_tag:
                if not is_fac and val < legal_val:
                    st.markdown(
                        f'<span class="badge badge-legal" style="font-size:9px;padding:2px 5px">'
                        f'⚠ {legal_val:.1f}m</span>',
                        unsafe_allow_html=True
                    )
                elif is_fac and val > 0:
                    st.markdown(
                        f'<span class="badge badge-fac" style="font-size:9px;padding:2px 5px">'
                        f'voluntário</span>',
                        unsafe_allow_html=True
                    )
            afastamentos_laterais[i] = val

# ── Preview SVG ───────────────────────────────────────────────
afas_prev: dict[int, float] = {i: recuo_frontal_m for i in idx_frentes}
for i, v in afastamentos_laterais.items():
    if v > 0:
        afas_prev[i] = v

_n_prev = len(coords_simpl)
if _n_prev > 4 or modo_retangular:
    coords_fp_prev = footprint_retangular(coords_simpl, afas_prev, idx_frentes)
    if coords_fp_prev is None:
        coords_fp_prev = inset_poligono_simples(coords_simpl, afas_prev)
else:
    coords_fp_prev = inset_poligono_simples(coords_simpl, afas_prev)
    if coords_fp_prev is None:
        coords_fp_prev = footprint_retangular(coords_simpl, afas_prev, idx_frentes)

coords_emb_prev = None
if simular_emb and zona.embasamento.permitido:
    _afas_emb = {i: recuo_frontal_m for i in idx_frentes}
    coords_emb_prev = inset_poligono_simples(coords_simpl, _afas_emb)

# Se uma opção de otimização está selecionada, usa o footprint dela no SVG
_fp_display = coords_fp_ot if coords_fp_ot is not None else coords_fp_prev

with col_mapa:
    _ot_label = ""
    if coords_fp_ot is not None and opcoes_ot and _sel_idx is not None:
        _op_sel = opcoes_ot[_sel_idx]
        _ot_label = (
            f' · <span style="color:var(--accent);font-family:\'Space Mono\',monospace;'
            f'font-size:10px">{_op_sel["label"].upper()}: {_op_sel["n_pav"]} pav · '
            f'{_op_sel["altura_m"]:.0f}m</span>'
        )
    st.markdown(
        f'<div style="font-size:12px;font-weight:600;margin-bottom:6px">'
        f'Visualização do Lote{_ot_label}</div>',
        unsafe_allow_html=True)
    svg = render_svg(
        coords_orig, _fp_display, coords_emb_prev,
        arestas_simpl, idx_frentes, list(afastamentos_laterais.keys()),
    )
    st.markdown(f'<div class="mapa-container">{svg}</div>', unsafe_allow_html=True)
    _caption = (
        f"Otimização · {opcoes_ot[_sel_idx]['label']} selecionada"
        if coords_fp_ot is not None and opcoes_ot and _sel_idx is not None
        else "🔴 Frente · 🟡 Footprint (preview) · 🔵 Laterais · pontos = vértices originais"
    )
    st.caption(_caption)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# CÁLCULO
# ─────────────────────────────────────────────────────────────
if btn_calcular or st.session_state.resultado is not None:

    if btn_calcular:
        cfg = ConfigSimulacao(
            zona=zona,
            altura_total_m=float(altura_m),
            idx_frentes=idx_frentes,
            afastamentos_laterais=afastamentos_laterais,
            garagem=ConfigGaragem(
                usar_subsolo=usar_subsolo,
                n_subsolos=n_subsolos if usar_subsolo else 0,
                area_vaga_terreo_m2=area_vaga_ter,
                area_vaga_subsolo_m2=area_vaga_sub,
            ),
            usar_ca_permissivel=usar_ca_perm,
            simular_embasamento=simular_emb,
            recuo_frontal_m=float(recuo_frontal_m),
            modo_retangular=modo_retangular,
        )
        gj_calc = {
            "type": "Feature", "properties": {},
            "geometry": {"type": "Polygon",
                         "coordinates": [coords_simpl + [coords_simpl[0]]]}
        }
        resultado = calcular_envelope(gj_calc, cfg)
        st.session_state.resultado  = resultado
        st.session_state.config_salva = cfg

    resultado    = st.session_state.resultado
    config_salva = st.session_state.config_salva

    st.markdown("## 📊 Resultado da Simulação")
    for a in resultado.alertas:
        st.markdown(alerta(a), unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Área do Lote",         f"{resultado.area_lote:,.0f} m²")
    k2.metric("Área Construída Máx.",  f"{resultado.area_construida_max:,.0f} m²")
    k3.metric("Footprint (TO×lote)",   f"{resultado.area_projecao_max:,.0f} m²")
    k4.metric("Unidades Máx.", str(resultado.n_unidades_max),
              help=f"Fração mín: {zona.fracao_minima_m2:.0f}m²" if zona.fracao_minima_m2 else None)

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Altura",              f"{resultado.altura_total_m:.1f} m")
    k6.metric("Área/Pavimento",      f"{resultado.area_util_por_pav:,.0f} m²")
    k7.metric("Vagas",               str(resultado.n_vagas))
    k8.metric("Área Permeável Mín.", f"{resultado.area_permeavel_min:,.0f} m²")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    tab_names = ["🏗️ Footprint", "🎲 3D", "🚗 Garagem", "📐 Detalhes", "💾 Exportar"]
    if resultado.geojson_embasamento:
        tab_names.insert(1, "🧱 Embasamento")
    tabs   = st.tabs(tab_names)
    # offset: 1 se tem embasamento (inserido na pos 1)
    offset = 1 if resultado.geojson_embasamento else 0

    # ── Footprint ─────────────────────────────────────────────
    with tabs[0]:
        c1, c2 = st.columns([2, 1])
        with c1:
            svg2 = render_svg(
                coords_simpl,
                resultado.coords_footprint_utm,
                resultado.coords_embasamento_utm,
                arestas_simpl, idx_frentes,
                list(afastamentos_laterais.keys()),
            )
            st.markdown(f'<div class="mapa-container">{svg2}</div>', unsafe_allow_html=True)
        with c2:
            af_legal = zona.afastamento.calcular_legal(resultado.altura_total_m)
            recuo_ef = config_salva.recuo_frontal_efetivo() if config_salva else zona.recuo_frontal_m
            recuo_tag = ("⚠ abaixo legal" if recuo_ef < zona.recuo_frontal_m
                         else (f"+{recuo_ef - zona.recuo_frontal_m:.1f}m acima" if recuo_ef > zona.recuo_frontal_m
                               else "legal"))
            recuo_cor = "var(--danger)" if recuo_ef < zona.recuo_frontal_m else "var(--accent)"
            st.markdown(f"""<div class="card">
                <div class="card-title">Recuo frontal</div>
                <div class="card-value" style="color:{recuo_cor}">{recuo_ef:.2f}m</div>
                <div class="card-sub">legal={zona.recuo_frontal_m:.2f}m · {recuo_tag} · {_frentes_label}</div>
            </div>""", unsafe_allow_html=True)
            if config_salva:
                for idx, uv in config_salva.afastamentos_laterais.items():
                    fac_ = zona.afastamento.is_facultado(resultado.altura_total_m)
                    tag = ("facult." if fac_ and uv == 0 else
                           "voluntário" if fac_ else
                           "⚠ abaixo legal" if uv < af_legal else "legal")
                    cor = "var(--danger)" if (not fac_ and uv < af_legal) else "var(--accent)"
                    st.markdown(f"""<div class="card">
                        <div class="card-title">Lateral aresta #{idx}</div>
                        <div class="card-value" style="color:{cor}">{uv:.2f}m</div>
                        <div class="card-sub">legal={af_legal:.2f}m · {tag}</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="card">
                <div class="card-title">Footprint real</div>
                <div class="card-value">{area_poligono(resultado.coords_footprint_utm):.0f}m²</div>
            </div>""", unsafe_allow_html=True)

    # ── Embasamento ───────────────────────────────────────────
    if resultado.geojson_embasamento:
        with tabs[1]:
            ep = resultado.geojson_embasamento["properties"]
            ea, eb, ec = st.columns(3)
            ea.metric("TO embasamento", f"{ep['to_embasamento']*100:.0f}%")
            eb.metric("Altura máx.",    f"{ep['altura_max_m']:.0f}m")
            ec.metric("Área",           f"{ep['area_m2']:.0f}m²")
            st.markdown(
                '<div class="al-info">ℹ️ Embasamento até 9m de altura, '
                'TO 70%, pode ocupar laterais (até 50% do perímetro) e fundos (100%).</div>',
                unsafe_allow_html=True)

    # ── 3D ────────────────────────────────────────────────────
    # Fica sempre na posição 1 + offset (após Footprint e opcional Embasamento)
    with tabs[1 + offset]:
        # Slider de altura do pavimento para o viewer
        c3d_a, c3d_b = st.columns([3, 1])
        with c3d_b:
            h_pav_3d = st.number_input(
                "m/pavimento (visualização)",
                min_value=2.5, max_value=5.0,
                value=3.0, step=0.1,
                help="Afeta só a visualização 3D, não o cálculo.",
            )
            # Altura embasamento para o viewer
            h_emb_3d = float(zona.embasamento.altura_max_m) if zona.embasamento.permitido else 9.0
            mostrar_eixos = st.checkbox("Mostrar eixo Norte", value=True)
            altura_viewer = st.select_slider(
                "Altura do viewer",
                options=[420, 520, 620, 720],
                value=520,
            )
            st.markdown(f"""<div class="al-info" style="font-size:11px">
            <b>Controles:</b><br>
            🖱 Drag → orbitar<br>
            Shift + drag → pan<br>
            Scroll → zoom<br>
            📱 1 dedo → orbitar<br>
            2 dedos → zoom
            </div>""", unsafe_allow_html=True)

        with c3d_a:
            html_3d = render_3d(
                coords_footprint_utm=resultado.coords_footprint_utm,
                altura_total_m=resultado.altura_total_m,
                altura_por_pav_m=float(h_pav_3d),
                coords_embasamento_utm=resultado.coords_embasamento_utm,
                altura_embasamento_m=h_emb_3d,
                zona_sigla=zona.sigla_display,
                height_px=int(altura_viewer),
            )
            components.html(html_3d, height=int(altura_viewer) + 4, scrolling=False)

    # ── Garagem ───────────────────────────────────────────────
    with tabs[2 + offset]:
        g1, g2 = st.columns(2)
        modo = "Subsolo" if usar_subsolo else "Térreo"
        g1.markdown(f"""<div class="card">
            <div class="card-title">Modo garagem</div>
            <div class="card-value">{modo}</div>
            <div class="card-sub">{f"{n_subsolos} subsolos · {area_vaga_sub:.0f}m²/vaga" if usar_subsolo else f"{area_vaga_ter:.0f}m²/vaga"}</div>
        </div>""", unsafe_allow_html=True)
        g2.markdown(f"""<div class="card">
            <div class="card-title">Vagas totais</div>
            <div class="card-value">{resultado.n_vagas}</div>
            <div class="card-sub">Subsolo: {resultado.n_vagas_subsolo} · Térreo: {resultado.n_vagas - resultado.n_vagas_subsolo}</div>
        </div>""", unsafe_allow_html=True)

    # ── Detalhes ──────────────────────────────────────────────
    with tabs[3 + offset]:
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Parâmetros urbanísticos**")
            for k, v in resultado.metricas.items():
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                    f'border-bottom:1px solid var(--border);font-size:13px">'
                    f'<span style="color:var(--muted)">{k}</span>'
                    f'<span style="font-family:Space Mono,monospace">{v}</span></div>',
                    unsafe_allow_html=True)
        with d2:
            st.markdown("**Afastamentos definidos**")
            af_legal = zona.afastamento.calcular_legal(resultado.altura_total_m)
            recuo_ef = config_salva.recuo_frontal_efetivo() if config_salva else zona.recuo_frontal_m
            rf_tag = ("⚠ abaixo legal" if recuo_ef < zona.recuo_frontal_m else
                      f"+{recuo_ef - zona.recuo_frontal_m:.1f}m" if recuo_ef > zona.recuo_frontal_m
                      else "legal")
            rows_af = [("Recuo frontal", recuo_ef, rf_tag)]
            if config_salva:
                fac_ = zona.afastamento.is_facultado(resultado.altura_total_m)
                for idx, uv in config_salva.afastamentos_laterais.items():
                    st_txt = ("facult." if fac_ and uv == 0 else
                              "voluntário" if fac_ else
                              f"legal={af_legal:.2f}m" if uv >= af_legal else
                              f"⚠ legal={af_legal:.2f}m")
                    rows_af.append((f"Lateral #{idx}", uv, st_txt))
            for nome, uv, st_txt in rows_af:
                cor = "#ff6b6b" if "⚠" in st_txt else "var(--accent)"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">'
                    f'<span style="color:var(--muted)">{nome}</span>'
                    f'<span style="font-family:Space Mono,monospace;color:{cor}">'
                    f'{uv:.2f}m <span style="color:var(--muted);font-size:11px">({st_txt})</span>'
                    f'</span></div>',
                    unsafe_allow_html=True)

    # ── Exportar ──────────────────────────────────────────────
    with tabs[4 + offset]:
        from export3d import build_giraffe_features, to_json_str

        h_pav_exp = st.number_input(
            "Altura por pavimento para export (m)",
            min_value=2.5, max_value=6.0, value=3.0, step=0.1,
            help="Define a espessura de cada Feature no Giraffe.",
        )

        h_emb_exp = float(zona.embasamento.altura_max_m) if zona.embasamento.permitido else 9.0
        fc_giraffe = build_giraffe_features(
            coords_footprint_utm=resultado.coords_footprint_utm,
            altura_total_m=resultado.altura_total_m,
            altura_por_pav_m=float(h_pav_exp),
            coords_embasamento_utm=resultado.coords_embasamento_utm,
            altura_embasamento_m=h_emb_exp,
            n_unidades=resultado.n_unidades_max,
            zona_sigla=zona.sigla_display,
            area_construida_m2=resultado.area_construida_max,
        )

        n_features = len(fc_giraffe["features"])
        n_pav_exp  = sum(1 for f in fc_giraffe["features"] if f["properties"].get("uso") == "convencional")
        tem_emb    = any(f["properties"].get("uso") == "embasamento" for f in fc_giraffe["features"])

        zona_safe = zona.sigla_display.replace("/", "_").replace(" ", "")
        json_str  = to_json_str(fc_giraffe)

        # Preview do conteúdo
        st.markdown(f"""<div class="card">
        <div class="card-title">Conteúdo do arquivo Giraffe</div>
        <div style="font-size:13px;line-height:2.2;font-family:'Space Mono',monospace">
        {"<span style='color:#4ecdc4'>● Embasamento</span>  · 1 Feature · base 0m → " + f"{h_emb_exp:.0f}m<br>" if tem_emb else ""}
        <span style="color:#e8c547">● Pavimentos</span>   · {n_pav_exp} Features · {h_pav_exp:.1f}m cada<br>
        <span style="color:var(--muted)">Total</span>         · <b>{n_features} Features</b>
        </div>
        <div style="font-size:11px;color:var(--muted);margin-top:8px">
        Cada Feature tem <code>height</code> (espessura) e <code>stackOrder</code> (ordem de empilhamento).<br>
        Giraffe empilhará cada andar automaticamente pelo stackOrder.
        </div>
        </div>""", unsafe_allow_html=True)

        # Tabela de pavimentos
        with st.expander(f"Ver {n_features} features do arquivo"):
            for f in fc_giraffe["features"]:
                p = f["properties"]
                uso_cor = "#4ecdc4" if p["uso"] == "embasamento" else "#e8c547"
                st.markdown(
                    f'<div style="font-family:Space Mono,monospace;font-size:11px;'
                    f'padding:5px 0;border-bottom:1px solid var(--border)">'
                    f'<span style="color:{uso_cor}">● {p["uso"]}</span>'
                    f'  stackOrder={p["stackOrder"]}'
                    f'  stackOrder={p["stackOrder"]}'
                    f'  h={p["height"]:.1f}m</div>',
                    unsafe_allow_html=True
                )

        st.download_button(
            f"⬇️ Baixar Giraffe ({n_features} pavimentos)",
            data=json_str,
            file_name=f"giraffe_{zona_safe}_{resultado.altura_total_m:.0f}m_{n_features}pav.geojson",
            mime="application/geo+json",
            use_container_width=True,
        )
        st.markdown(
            '<div class="al-info">ℹ️ No Giraffe: File → Import → selecione o .geojson. '
            'Cada Feature é extrudada individualmente pela property <code>height</code>.</div>',
            unsafe_allow_html=True)

# ─── Footer ───────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown(
    '<div style="color:#3d4455;font-family:Space Mono,monospace;font-size:10px;'
    'letter-spacing:0.1em;text-align:center">'
    'ENVELOPE CONSTRUTIVO · CURITIBA · JOINVILLE · SQLite · ZMSMART'
    '</div>', unsafe_allow_html=True)
