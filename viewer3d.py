"""
viewer3d.py — Visualizador 3D embutido no Streamlit via Three.js (r128).

API pública:
    render_3d(
        coords_footprint_utm,   # lista de [x, y] em metros
        altura_total_m,
        altura_por_pav_m,
        coords_embasamento_utm, # opcional
        altura_embasamento_m,   # opcional
        zona_sigla,
        height_px,
    ) -> str   # HTML completo para st.components.v1.html()
"""
from __future__ import annotations
import json
import math


def _centrar(coords: list[list[float]]) -> tuple[list[list[float]], float, float]:
    """Centraliza coords em torno da origem. Retorna (coords_centradas, cx, cy)."""
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    return [[c[0] - cx, c[1] - cy] for c in coords], cx, cy


def _triangular_poligono(coords: list[list[float]], z: float) -> list[float]:
    """
    Triangulação fan do polígono (para topo e base).
    Retorna lista flat de floats [x,y,z, x,y,z, ...] para Three.js BufferGeometry.
    Funciona bem para polígonos convexos e levemente côncavos.
    """
    if not coords:
        return []
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    verts = []
    n = len(coords)
    for i in range(n):
        p1 = coords[i]
        p2 = coords[(i + 1) % n]
        verts += [cx, z, cy,          # centroide (y=z no Three.js, eixo Y = altura)
                  p1[0], z, p1[1],
                  p2[0], z, p2[1]]
    return verts


def _paredes(coords: list[list[float]], z_bot: float, z_top: float) -> list[float]:
    """Gera quads (2 triângulos) para cada aresta lateral."""
    verts = []
    n = len(coords)
    for i in range(n):
        p1 = coords[i]
        p2 = coords[(i + 1) % n]
        # Tri 1
        verts += [p1[0], z_bot, p1[1],
                  p2[0], z_bot, p2[1],
                  p2[0], z_top, p2[1]]
        # Tri 2
        verts += [p1[0], z_bot, p1[1],
                  p2[0], z_top, p2[1],
                  p1[0], z_top, p1[1]]
    return verts


def _linhas_laje(coords: list[list[float]], z: float) -> list[float]:
    """Linha de contorno de uma laje em z."""
    pts = []
    n = len(coords)
    for i in range(n):
        p1 = coords[i]
        p2 = coords[(i + 1) % n]
        pts += [p1[0], z, p1[1], p2[0], z, p2[1]]
    return pts


def render_3d(
    coords_footprint_utm: list[list[float]],
    altura_total_m: float,
    altura_por_pav_m: float = 3.0,
    coords_embasamento_utm: list[list[float]] | None = None,
    altura_embasamento_m: float = 9.0,
    zona_sigla: str = "",
    height_px: int = 520,
) -> str:
    """
    Gera HTML com Three.js r128 para visualização 3D embutida no Streamlit.

    Geometrias geradas:
      - Terreno plano (grid) centralizado no lote
      - Torre principal: base + paredes + topo + linhas de laje
      - Embasamento (se fornecido): volume em cor diferente
      - Sombra projetada no terreno (círculo/mancha)
      - Eixo Norte (seta)
    """
    if not coords_footprint_utm or len(coords_footprint_utm) < 3:
        return "<div style='color:#ff6b6b'>Footprint sem dados para renderizar.</div>"

    # ── Centralizar coordenadas ──────────────────────────────
    fp_c, cx, cy = _centrar(coords_footprint_utm)
    n_pav = max(1, round(altura_total_m / altura_por_pav_m))

    emb_c = None
    if coords_embasamento_utm and len(coords_embasamento_utm) >= 3:
        emb_c = [[c[0] - cx, c[1] - cy] for c in coords_embasamento_utm]

    # ── Geometrias → listas flat de floats ───────────────────
    # Torre: paredes
    torre_paredes   = _paredes(fp_c, 0.0, altura_total_m)
    torre_base      = _triangular_poligono(fp_c, 0.0)
    torre_topo      = _triangular_poligono(fp_c, altura_total_m)
    # Linhas de laje (cada piso)
    linhas_laje = []
    for piso in range(n_pav + 1):
        z = piso * altura_por_pav_m
        if z > altura_total_m:
            z = altura_total_m
        linhas_laje += _linhas_laje(fp_c, z)

    # Embasamento
    emb_paredes = emb_base = emb_topo = []
    if emb_c:
        h_emb = min(altura_embasamento_m, altura_total_m)
        emb_paredes = _paredes(emb_c, 0.0, h_emb)
        emb_base    = _triangular_poligono(emb_c, 0.0)
        emb_topo    = _triangular_poligono(emb_c, h_emb)

    # Tamanho do terreno
    xs = [c[0] for c in fp_c]; zs = [c[1] for c in fp_c]
    extent = max(max(xs) - min(xs), max(zs) - min(zs)) * 2.5
    extent = max(extent, 40.0)

    data = {
        "torre_paredes":  torre_paredes,
        "torre_base":     torre_base,
        "torre_topo":     torre_topo,
        "linhas_laje":    linhas_laje,
        "emb_paredes":    emb_paredes,
        "emb_base":       emb_base,
        "emb_topo":       emb_topo,
        "altura_total":   altura_total_m,
        "n_pav":          n_pav,
        "extent":         extent,
        "has_emb":        bool(emb_c),
        "zona":           zona_sigla,
        "n_fp":           len(fp_c),
    }
    data_json = json.dumps(data)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0d0f14; overflow:hidden; font-family:'Space Mono',monospace; }}
  #c {{ width:100%; height:{height_px}px; display:block; }}
  #hud {{
    position:absolute; top:12px; left:12px;
    background:rgba(13,15,20,0.82); border:1px solid #252a38;
    border-radius:6px; padding:10px 14px;
    font-size:11px; color:#6b7280; line-height:2;
    pointer-events:none;
  }}
  #hud b {{ color:#e8c547; }}
  #legend {{
    position:absolute; bottom:12px; left:12px;
    display:flex; gap:12px; align-items:center;
    background:rgba(13,15,20,0.82); border:1px solid #252a38;
    border-radius:6px; padding:8px 12px; font-size:10px; color:#6b7280;
  }}
  .dot {{ width:10px; height:10px; border-radius:2px; display:inline-block; margin-right:4px; }}
  #controls {{
    position:absolute; top:12px; right:12px;
    display:flex; flex-direction:column; gap:6px;
  }}
  .btn {{
    background:rgba(21,24,32,0.9); border:1px solid #252a38;
    color:#6b7280; border-radius:4px; padding:6px 10px;
    font-family:'Space Mono',monospace; font-size:10px;
    cursor:pointer; transition:all .15s;
  }}
  .btn:hover {{ border-color:#e8c547; color:#e8c547; }}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="hud">
  <b id="zona-label">{zona_sigla}</b><br>
  Altura: <b>{altura_total_m:.1f}m</b> · {n_pav} pav.<br>
  Drag: orbitar · Scroll: zoom · Shift+drag: pan
</div>
<div id="legend">
  <span><span class="dot" style="background:#e8c547"></span>Torre</span>
  {"<span><span class=\"dot\" style=\"background:#4ecdc4\"></span>Embasamento</span>" if emb_c else ""}
  <span><span class="dot" style="background:#2a3550"></span>Terreno</span>
  <span><span class="dot" style="background:rgba(232,197,71,0.25)"></span>Sombra</span>
</div>
<div id="controls">
  <button class="btn" onclick="resetCamera()">↺ Reset</button>
  <button class="btn" onclick="toggleWire()">⊟ Wire</button>
  <button class="btn" onclick="setView('top')">⊤ Top</button>
  <button class="btn" onclick="setView('iso')">◈ Iso</button>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const DATA = {data_json};

// ── Setup ────────────────────────────────────────────────────
const canvas  = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{ canvas, antialias:true, alpha:false }});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(canvas.parentElement.offsetWidth, {height_px});
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setClearColor(0x0d0f14);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x0d0f14, 0.012);

const camera = new THREE.PerspectiveCamera(45, canvas.parentElement.offsetWidth / {height_px}, 0.1, 2000);
const ISO_POS = new THREE.Vector3(
  DATA.extent * 0.7,
  DATA.altura_total * 2.2 + 20,
  DATA.extent * 0.7
);
camera.position.copy(ISO_POS);
camera.lookAt(0, DATA.altura_total / 2, 0);

// ── Luzes ────────────────────────────────────────────────────
const amb = new THREE.AmbientLight(0xffffff, 0.35);
scene.add(amb);

const sun = new THREE.DirectionalLight(0xfff4e0, 1.1);
sun.position.set(DATA.extent * 0.8, DATA.altura_total * 3, DATA.extent * 0.5);
sun.castShadow = true;
sun.shadow.mapSize.width  = 2048;
sun.shadow.mapSize.height = 2048;
const sc = DATA.extent * 0.8;
sun.shadow.camera.left   = -sc; sun.shadow.camera.right = sc;
sun.shadow.camera.top    =  sc; sun.shadow.camera.bottom = -sc;
sun.shadow.camera.far    = DATA.extent * 6;
sun.shadow.bias = -0.001;
scene.add(sun);

const fill = new THREE.DirectionalLight(0x8ab4f8, 0.3);
fill.position.set(-DATA.extent, DATA.altura_total, -DATA.extent);
scene.add(fill);

// ── Helpers ───────────────────────────────────────────────────
function makeBuffer(flatVerts) {{
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(flatVerts, 3));
  geo.computeVertexNormals();
  return geo;
}}

function makeLines(flatPts, color) {{
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(flatPts, 3));
  return new THREE.LineSegments(geo, new THREE.LineBasicMaterial({{color, linewidth:1}}));
}}

// ── Terreno ────────────────────────────────────────────────────
const terrSize = DATA.extent * 2;
const terrGeo  = new THREE.PlaneGeometry(terrSize, terrSize, 40, 40);
terrGeo.rotateX(-Math.PI / 2);
const terrMat = new THREE.MeshLambertMaterial({{
  color: 0x1a2035,
  side: THREE.FrontSide,
}});
const terr = new THREE.Mesh(terrGeo, terrMat);
terr.position.y = -0.05;
terr.receiveShadow = true;
scene.add(terr);

// Grade no terreno
const gridH = new THREE.GridHelper(terrSize, 40, 0x252a38, 0x252a38);
gridH.position.y = 0.01;
gridH.material.transparent = true;
gridH.material.opacity = 0.5;
scene.add(gridH);

// ── Sombra projetada (mancha no chão) ─────────────────────────
// Usamos a própria projeção do shadow map — já configurada acima

// Plano receptor de sombra extra (mais escuro, debaixo do edifício)
const shadowGeo = new THREE.PlaneGeometry(terrSize, terrSize);
shadowGeo.rotateX(-Math.PI / 2);
const shadowMat = new THREE.ShadowMaterial({{ opacity: 0.45 }});
const shadowPlane = new THREE.Mesh(shadowGeo, shadowMat);
shadowPlane.position.y = 0.02;
shadowPlane.receiveShadow = true;
scene.add(shadowPlane);

// ── Torre principal ────────────────────────────────────────────
const torreColor  = 0xe8c547;
const torreColorD = 0xc9a82e;  // paredes um pouco mais escuras

const matTopo   = new THREE.MeshLambertMaterial({{ color: torreColor,  side:THREE.FrontSide }});
const matParede = new THREE.MeshLambertMaterial({{ color: torreColorD, side:THREE.FrontSide }});
const matBase   = new THREE.MeshLambertMaterial({{ color: 0x1c2030,    side:THREE.FrontSide }});

function addSolid(flatVerts, mat, castShadow=true) {{
  const m = new THREE.Mesh(makeBuffer(flatVerts), mat);
  m.castShadow = castShadow;
  m.receiveShadow = true;
  scene.add(m);
  return m;
}}

const torre_meshes = [];
torre_meshes.push(addSolid(DATA.torre_paredes, matParede));
torre_meshes.push(addSolid(DATA.torre_topo,    matTopo));
torre_meshes.push(addSolid(DATA.torre_base,    matBase, false));

// ── Linhas de laje ─────────────────────────────────────────────
const lajeLine = makeLines(DATA.linhas_laje, 0xe8c547);
lajeLine.material.transparent = true;
lajeLine.material.opacity = 0.55;
scene.add(lajeLine);

// Borda do topo (mais nítida)
const topoLine = makeLines(
  (() => {{
    const fp = DATA.torre_paredes;
    // reusa linhas do topo (y == altura_total) do laje
    const lines = DATA.linhas_laje.slice(-6 * DATA.n_fp);
    return lines;
  }})(),
  0xffe066
);
scene.add(topoLine);

// ── Embasamento ────────────────────────────────────────────────
if (DATA.has_emb) {{
  const matEmbP = new THREE.MeshLambertMaterial({{ color:0x2b9c8e, side:THREE.FrontSide }});
  const matEmbT = new THREE.MeshLambertMaterial({{ color:0x4ecdc4, side:THREE.FrontSide }});
  addSolid(DATA.emb_paredes, matEmbP);
  addSolid(DATA.emb_topo,    matEmbT);
  addSolid(DATA.emb_base,    matBase, false);
  const embLine = makeLines(DATA.linhas_laje.slice(0, 6*DATA.n_fp), 0x4ecdc4);
  scene.add(embLine);
}}

// ── Seta Norte ─────────────────────────────────────────────────
const northLen = DATA.extent * 0.12;
const northGroup = new THREE.Group();
const arrowGeo = new THREE.CylinderGeometry(0.3, 0.3, northLen, 8);
arrowGeo.translate(0, northLen/2, 0);
const arrowTip = new THREE.ConeGeometry(1.0, 2.5, 8);
arrowTip.translate(0, northLen + 1.25, 0);
const arrowMat = new THREE.MeshBasicMaterial({{ color:0xff6b6b }});
northGroup.add(new THREE.Mesh(arrowGeo, arrowMat));
northGroup.add(new THREE.Mesh(arrowTip, arrowMat));
northGroup.rotation.x = -Math.PI / 2;
northGroup.position.set(DATA.extent * 0.6, 0.5, -DATA.extent * 0.6);
scene.add(northGroup);

// ── Wire toggle ────────────────────────────────────────────────
let wireMode = false;
const solidMats = [matTopo, matParede, matBase];

function toggleWire() {{
  wireMode = !wireMode;
  solidMats.forEach(m => {{ m.wireframe = wireMode; }});
}}

// ── Câmera preset ─────────────────────────────────────────────
function resetCamera() {{
  camera.position.copy(ISO_POS);
  camera.lookAt(0, DATA.altura_total/2, 0);
  target.set(0, DATA.altura_total/2, 0);
}}

function setView(v) {{
  if (v === 'top') {{
    camera.position.set(0, DATA.altura_total * 4 + 50, 0.01);
    target.set(0, 0, 0);
  }} else {{
    resetCamera();
  }}
  camera.lookAt(target);
}}

// ── Orbit controls (manual, sem dep extra) ────────────────────
let isDragging = false, isShift = false;
let lastX = 0, lastY = 0;
const target = new THREE.Vector3(0, DATA.altura_total / 2, 0);

canvas.addEventListener('mousedown', e => {{
  isDragging = true; isShift = e.shiftKey;
  lastX = e.clientX; lastY = e.clientY;
}});
window.addEventListener('mouseup', () => isDragging = false);

window.addEventListener('mousemove', e => {{
  if (!isDragging) return;
  const dx = e.clientX - lastX;
  const dy = e.clientY - lastY;
  lastX = e.clientX; lastY = e.clientY;

  if (isShift) {{
    // Pan
    const right = new THREE.Vector3();
    const up    = new THREE.Vector3();
    camera.getWorldDirection(up);
    right.crossVectors(camera.up, up).normalize();
    const panScale = 0.08;
    camera.position.addScaledVector(right, dx * panScale);
    camera.position.y -= dy * panScale;
    target.addScaledVector(right, dx * panScale);
    target.y -= dy * panScale;
  }} else {{
    // Orbit
    const offset = new THREE.Vector3().subVectors(camera.position, target);
    const sph = new THREE.Spherical().setFromVector3(offset);
    sph.theta -= dx * 0.008;
    sph.phi   -= dy * 0.008;
    sph.phi = Math.max(0.05, Math.min(Math.PI / 2.05, sph.phi));
    offset.setFromSpherical(sph);
    camera.position.copy(target).add(offset);
  }}
  camera.lookAt(target);
}});

canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const offset = new THREE.Vector3().subVectors(camera.position, target);
  const factor = e.deltaY > 0 ? 1.12 : 0.89;
  offset.multiplyScalar(factor);
  camera.position.copy(target).add(offset);
  camera.lookAt(target);
}}, {{ passive: false }});

// Touch
let touches = [];
canvas.addEventListener('touchstart', e => {{ touches = Array.from(e.touches); }});
canvas.addEventListener('touchmove', e => {{
  e.preventDefault();
  if (e.touches.length === 1) {{
    const dx = e.touches[0].clientX - touches[0].clientX;
    const dy = e.touches[0].clientY - touches[0].clientY;
    const offset = new THREE.Vector3().subVectors(camera.position, target);
    const sph = new THREE.Spherical().setFromVector3(offset);
    sph.theta -= dx * 0.008; sph.phi -= dy * 0.008;
    sph.phi = Math.max(0.05, Math.min(Math.PI/2.05, sph.phi));
    offset.setFromSpherical(sph);
    camera.position.copy(target).add(offset);
    camera.lookAt(target);
  }} else if (e.touches.length === 2) {{
    const d0 = Math.hypot(touches[0].clientX-touches[1].clientX, touches[0].clientY-touches[1].clientY);
    const d1 = Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
    const factor = d0 / d1;
    const offset = new THREE.Vector3().subVectors(camera.position, target);
    offset.multiplyScalar(factor);
    camera.position.copy(target).add(offset);
    camera.lookAt(target);
  }}
  touches = Array.from(e.touches);
}}, {{ passive: false }});

// ── Resize ────────────────────────────────────────────────────
window.addEventListener('resize', () => {{
  const w = canvas.parentElement.offsetWidth;
  renderer.setSize(w, {height_px});
  camera.aspect = w / {height_px};
  camera.updateProjectionMatrix();
}});

// ── Render loop ───────────────────────────────────────────────
function animate() {{
  requestAnimationFrame(animate);
  // Leve rotação automática quando idle (desligada ao orbitar)
  renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>"""

    return html
