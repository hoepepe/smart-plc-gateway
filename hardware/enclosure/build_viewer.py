"""Tạo out/viewer.html — trình xem 3D xoay được (Three.js) cho đế, nắp và vị trí module.
Chạy sau gen_enclosure.py:  python hardware/enclosure/build_viewer.py"""
import base64
import json
import os

import gen_enclosure as G

OUT = G.OUT
b64 = {k: base64.b64encode(open(os.path.join(OUT, f"gateway_{k}.stl"), "rb").read()).decode()
       for k in ("base", "lid")}
COLORS = {"W5500": "#3b7dd8", "RS232": "#d9822b", "PC817": "#2f9e6f", "ADS1115": "#8a63d2",
          "ESP32": "#30343c", "LM2596": "#c9a227", "MPU6050": "#1f9aa5", "HW500": "#8b96a5"}
TALL = {"W5500": 13.5, "RS232": 12.5, "LM2596": 14.0}
mods = [dict(name=k, x=x, y=y, L=L, W=W, z=z, h=G.PCB_T + TALL.get(k, 3.0), desc=d, color=COLORS[k])
        for k, (x, y, L, W, z, d) in G.MODULES.items()]
cuts = [dict(side=s, label=n, w=w, h=h, shape=sh) for s, u, zc, w, h, sh, n in G.CUTS]
data = dict(IN_L=G.IN_L, IN_W=G.IN_W, IN_H=G.IN_H, WALL=G.WALL, FLOOR=G.FLOOR, mods=mods, cuts=cuts,
            oled=G.OLED)

SIDE = {"left": "Vách trái", "right": "Vách phải", "front": "Mặt trước", "back": "Mặt sau"}
mod_rows = "\n".join(
    f'<li><span class="sw" style="--c:{m["color"]}"></span><b>{m["name"]}</b>'
    f'<span class="dim">{m["L"]:g} × {m["W"]:g}</span><span class="desc">{m["desc"]}</span></li>' for m in mods)
cut_rows = "\n".join(
    f'<li><span class="side">{SIDE[c["side"]]}</span><span class="desc">{c["label"]}</span>'
    f'<span class="dim">{"Ø" + format(c["w"], "g") if c["shape"] == "circle" else format(c["w"], "g") + " × " + format(c["h"], "g")}</span></li>'
    for c in cuts)

ext_L = G.IN_L + 2 * G.WALL
ext_W = G.IN_W + 2 * G.WALL
ext_H = G.IN_H + G.FLOOR + G.LID_T

html = f"""<title>Vỏ hộp Smart PLC Gateway</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* Bố cục: khung xem 3D chiếm phần lớn, cột thông số kỹ thuật bên phải (xếp xuống dưới trên điện thoại) */
:root {{
  --bg: #eef1f4; --panel: #ffffff; --ink: #1c232c; --muted: #5d6875; --line: #d6dce3;
  --accent: #e0681f; --stage: #dfe5ea; --chip: #f3f5f8;
  --f-display: "Barlow", "Arial Narrow", system-ui, sans-serif;
  --f-body: "Barlow", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #12161b; --panel: #1a2027; --ink: #e6ebf0; --muted: #98a3af; --line: #2c343d;
  --accent: #f08a43; --stage: #0d1115; --chip: #222a33; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #12161b; --panel: #1a2027; --ink: #e6ebf0; --muted: #98a3af; --line: #2c343d;
  --accent: #f08a43; --stage: #0d1115; --chip: #222a33; color-scheme: dark; }}
html, body {{ height: 100%; }}
body {{ background: var(--bg); color: var(--ink); font-family: var(--f-body); font-size: 15px; line-height: 1.5; }}
.wrap {{ padding: 20px 16px 28px; max-width: 1280px; margin: 0 auto; display: grid; gap: 16px;
  grid-template-columns: minmax(0, 1fr) 340px; }}
header {{ grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 18px; }}
h1 {{ font-family: var(--f-display); font-weight: 700; font-size: clamp(22px, 3vw, 30px); letter-spacing: .01em;
  margin: 0; text-wrap: balance; }}
.tag {{ font-family: var(--f-mono); font-size: 12px; color: var(--muted); }}
.stage {{ position: relative; background: var(--stage); border: 1px solid var(--line); border-radius: 6px;
  min-height: 460px; height: min(72vh, 680px); overflow: hidden; min-width: 0; }}
#view {{ width: 100%; height: 100%; display: block; touch-action: none; }}
.controls {{ position: absolute; left: 12px; top: 12px; display: flex; flex-wrap: wrap; gap: 6px; max-width: calc(100% - 24px); }}
.controls button {{ font: 600 13px var(--f-body); color: var(--ink); background: var(--panel); border: 1px solid var(--line);
  border-radius: 4px; padding: 6px 10px; cursor: pointer; }}
.controls button[aria-pressed="true"] {{ border-color: var(--accent); color: var(--accent); }}
.controls button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.hint {{ position: absolute; right: 12px; bottom: 10px; font: 12px var(--f-mono); color: var(--muted); }}
aside {{ display: grid; gap: 14px; align-content: start; min-width: 0; }}
section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px; }}
h2 {{ font: 600 12px var(--f-body); text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 0 0 10px; }}
.size {{ font-family: var(--f-mono); font-size: 20px; font-variant-numeric: tabular-nums; }}
.size small {{ font-size: 12px; color: var(--muted); }}
ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }}
li {{ display: grid; grid-template-columns: auto 1fr auto; column-gap: 8px; align-items: baseline; font-size: 14px; }}
li .desc {{ grid-column: 2 / -1; color: var(--muted); font-size: 13px; line-height: 1.35; }}
li .dim {{ font-family: var(--f-mono); font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }}
.sw {{ width: 10px; height: 10px; border-radius: 2px; background: var(--c); align-self: center; }}
.side {{ font-weight: 600; font-size: 13px; }}
#cuts li {{ grid-template-columns: 82px 1fr auto; }}
#cuts li .desc {{ grid-column: 2; }}
.warn {{ border-left: 3px solid var(--accent); padding-left: 10px; font-size: 13.5px; color: var(--ink); margin: 0; }}
@media (max-width: 860px) {{ .wrap {{ grid-template-columns: minmax(0, 1fr); }} .stage {{ height: 62vh; min-height: 360px; }} }}
</style>

<div class="wrap">
  <header>
    <h1>Vỏ hộp Smart PLC Gateway</h1>
    <span class="tag">UET-BigHero · DENSO Factory Hacks 2026 · bản in 3D v0.1</span>
  </header>
  <div class="stage">
    <canvas id="view" aria-label="Mô hình 3D vỏ hộp, kéo để xoay"></canvas>
    <div class="controls" role="group" aria-label="Hiển thị">
      <button id="bLid" aria-pressed="true">Nắp</button>
      <button id="bOpen" aria-pressed="true">Tách nắp</button>
      <button id="bMods" aria-pressed="true">Module</button>
      <button id="bReset">Góc nhìn mặc định</button>
    </div>
    <div class="hint">kéo: xoay · cuộn: phóng to · chuột phải: dời</div>
  </div>
  <aside>
    <section>
      <h2>Kích thước ngoài</h2>
      <div class="size">{ext_L:g} × {ext_W:g} × {ext_H:g} <small>mm (chưa tính tai bắt vít)</small></div>
      <p style="margin:6px 0 0;color:var(--muted);font-size:13.5px">Vách {G.WALL:g} mm · đáy {G.FLOOR:g} mm · nắp {G.LID_T:g} mm có gờ lồng · 4 vít M3 tự ren · in PETG/PLA, không cần support cho đế</p>
    </section>
    <section>
      <h2>Lỗ khoét</h2>
      <ul id="cuts">{cut_rows}</ul>
    </section>
    <section>
      <h2>Module bên trong</h2>
      <ul>{mod_rows}
      <li><span class="sw" style="--c:#4c5562"></span><b>OLED 0.96″</b><span class="dim">27.3 × 27.8</span><span class="desc">SSD1306 bắt 4 vít M2 dưới nắp, có cửa sổ</span></li></ul>
    </section>
    <section>
      <p class="warn">Kích thước module là số phổ biến trên thị trường, chưa đo hàng thật. Đo bằng thước kẹp, sửa bảng MODULES trong <code>gen_enclosure.py</code> rồi chạy lại để ra STL mới.</p>
    </section>
  </aside>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const D = {json.dumps(data)};
const STL = {{ base: "{b64['base']}", lid: "{b64['lid']}" }};
const canvas = document.getElementById('view');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true }});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 1, 3000);
const controls = new THREE.OrbitControls(camera, canvas);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 0.75));
const sun = new THREE.DirectionalLight(0xffffff, 0.7); sun.position.set(150, 260, 180); scene.add(sun);
const fill = new THREE.DirectionalLight(0xffffff, 0.3); fill.position.set(-200, 80, -150); scene.add(fill);

// mô hình dùng z hướng lên → xoay về hệ y hướng lên của Three.js, đặt tâm hộp ở gốc
const world = new THREE.Group(); world.rotation.x = -Math.PI / 2;
world.position.set(-D.IN_L / 2, 0, D.IN_W / 2); scene.add(world);
function geo(b64) {{
  const bin = atob(b64), u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const g = new THREE.STLLoader().parse(u8.buffer); g.computeVertexNormals(); return g;
}}
const matBase = new THREE.MeshStandardMaterial({{ color: 0xc9d2db, roughness: 0.75, metalness: 0.0, transparent: true, opacity: 0.92 }});
const matLid = new THREE.MeshStandardMaterial({{ color: 0x9aa6b3, roughness: 0.7, metalness: 0.0 }});
const base = new THREE.Mesh(geo(STL.base), matBase); world.add(base);
const lid = new THREE.Mesh(geo(STL.lid), matLid); world.add(lid);
const mods = new THREE.Group(); world.add(mods);
for (const m of D.mods) {{
  const b = new THREE.Mesh(new THREE.BoxGeometry(m.L, m.W, m.h),
    new THREE.MeshStandardMaterial({{ color: m.color, roughness: 0.6 }}));
  b.position.set(m.x + m.L / 2, m.y + m.W / 2, m.z + m.h / 2); mods.add(b);
}}
const o = D.oled;
const oled = new THREE.Mesh(new THREE.BoxGeometry(o.L, o.W, 3), new THREE.MeshStandardMaterial({{ color: 0x4c5562 }}));
lid.add(oled); oled.position.set(o.x + o.L / 2, o.y + o.W / 2, -o.post_h - 1.5);

let showLid = true, open = true, showMods = true;
function layout() {{
  lid.visible = showLid;
  lid.position.z = D.IN_H + (open ? 45 : 0);
  mods.visible = showMods;
  matBase.opacity = showMods ? 0.92 : 1; matBase.transparent = showMods;
}}
function bind(id, fn) {{
  const el = document.getElementById(id);
  el.addEventListener('click', () => {{ const v = fn(); if (v !== undefined) el.setAttribute('aria-pressed', String(v)); layout(); }});
}}
bind('bLid', () => (showLid = !showLid));
bind('bOpen', () => (open = !open));
bind('bMods', () => (showMods = !showMods));
bind('bReset', () => {{ home(); }});
function home() {{ camera.position.set(170, 190, 230); controls.target.set(0, 25, 0); controls.update(); }}
function resize() {{
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}}
function theme() {{ scene.background = new THREE.Color(css('--stage') || '#dfe5ea'); }}
window.addEventListener('resize', resize);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', theme);
new MutationObserver(theme).observe(document.documentElement, {{ attributes: true, attributeFilter: ['data-theme'] }});
theme(); layout(); home(); resize();
(function loop() {{ controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); }})();
</script>
"""
with open(os.path.join(OUT, "viewer.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("Đã tạo", os.path.join(OUT, "viewer.html"), f"{len(html) / 1e6:.2f} MB")
