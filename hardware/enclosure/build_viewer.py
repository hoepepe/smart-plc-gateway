"""Tạo out/viewer.html — trình xem 3D xoay được (Three.js): vỏ hộp + mô hình module theo kích thước thật.
Chạy sau gen_enclosure.py:  python hardware/enclosure/build_viewer.py

Mô hình module dựng từ khối đơn giản (PCB, chip, đầu cắm, linh kiện lớn) theo kích thước bảng MODULES.
Đủ để kiểm tra va chạm và vị trí lỗ, không phải mô hình CAD của nhà sản xuất."""
import base64
import json
import os

import gen_enclosure as G

OUT = G.OUT
b64 = {k: base64.b64encode(open(os.path.join(OUT, f"gateway_{k}.stl"), "rb").read()).decode()
       for k in ("base", "lid")}

# Nguồn kích thước — "xác nhận" khi có tài liệu, "phổ biến" khi là số thường gặp của hàng bán ngoài, cần đo lại
SRC = {
    "W5500": "55 × 28 × 15, RJ45 HanRun HR911105A, header 2×5 (xác nhận: components101)",
    "LM2596": "43 × 21 × 14 (xác nhận: Surplustronics)",
    "RS232": "MAX3232, DB9 cái (xác nhận) · kích thước PCB phổ biến, đo lại",
    "ESP32": "Bản DevKit V1 38 chân, micro-USB · 55 × 28 phổ biến, đo lại",
    "PC817": "4 kênh, header 5 chân hai đầu · kích thước phổ biến, đo lại",
    "ADS1115": "28 × 17,7 (theo Adafruit) · bản clone có thể khác",
    "MPU6050": "GY-521 · 21 × 16 phổ biến, đo lại",
    "HW685": "Đổi dòng 4–20 mA sang áp · 42 × 25 × 10, nguồn 7–36 V (theo trang bán hàng SCCC), đo lại",
}
mods = [dict(name=k, x=x, y=y, L=L, W=W, z=z, desc=d, src=SRC.get(k, ""))
        for k, (x, y, L, W, z, d) in G.MODULES.items()]
cuts = [dict(side=s, u=u, zc=zc, w=w, h=h, shape=sh, label=n) for s, u, zc, w, h, sh, n in G.CUTS]
data = dict(IN_L=G.IN_L, IN_W=G.IN_W, IN_H=G.IN_H, WALL=G.WALL, FLOOR=G.FLOOR, PCB_T=G.PCB_T,
            mods=mods, cuts=cuts, oled=G.OLED)

SIDE = {"left": "Vách trái", "right": "Vách phải", "front": "Mặt trước", "back": "Mặt sau"}
CONNECT = {
    "RJ45": "Cáp LAN tới switch → PLC và laptop cùng mạng",
    "DB9": "Cáp RS232 tới PLC/thiết bị có cổng nối tiếp",
    "USB ESP32": "Laptop nạp firmware, xem log",
    "Jack DC 5.5×2.1 bắt ren M8": "Nguồn 24 V tủ điện",
}
cut_rows = "\n".join(
    f'<li><span class="side">{SIDE[c["side"]]}</span><span class="what">{c["label"]}</span>'
    f'<span class="dim">{"Ø" + format(c["w"], "g") if c["shape"] == "circle" else format(c["w"], "g") + " × " + format(c["h"], "g")}</span>'
    f'<span class="desc">{CONNECT.get(c["label"], "Dây tín hiệu từ máy, ốc siết cáp PG7 (cáp Ø3–6,5)")}</span></li>'
    for c in cuts)
cut_rows += ('<li><span class="side">Nắp</span><span class="what">2 lỗ kim EN / BOOT</span><span class="dim">Ø3,2</span>'
             '<span class="desc">Reset và vào chế độ nạp ESP32 không cần mở nắp</span></li>'
             '<li><span class="side">Nắp</span><span class="what">Cửa sổ OLED, 2 LED</span><span class="dim">23 × 13</span>'
             '<span class="desc">Trạng thái kết nối PLC và cảnh báo AI tại chỗ</span></li>')
mod_rows = "\n".join(
    f'<li><b>{m["name"]}</b><span class="dim">{m["L"]:g} × {m["W"]:g}</span><span class="desc">{m["src"]}</span></li>'
    for m in mods)
mod_rows += '<li><b>OLED 0.96″</b><span class="dim">27 × 27</span><span class="desc">SSD1306, dày 4,1, vùng hiển thị 21,74 × 11,2 (xác nhận: datasheet module)</span></li>'

ext_L, ext_W, ext_H = G.IN_L + 2 * G.WALL, G.IN_W + 2 * G.WALL, G.IN_H + G.FLOOR + G.LID_T

JS = r"""
const canvas = document.getElementById('view');
const tagsEl = document.getElementById('tags');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 1, 1, 4000);
const controls = new THREE.OrbitControls(camera, canvas);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x3a4450, 0.8));
const sun = new THREE.DirectionalLight(0xffffff, 0.75); sun.position.set(120, 300, 160); scene.add(sun);
const rim = new THREE.DirectionalLight(0xffffff, 0.35); rim.position.set(-220, 120, -180); scene.add(rim);

// Mô hình dùng z hướng lên (mm) → Three.js y hướng lên; tâm hộp ở gốc
const world = new THREE.Group(); world.rotation.x = -Math.PI / 2;
world.position.set(-D.IN_L / 2, 0, D.IN_W / 2); scene.add(world);

const M = {};
function mat(key, color, o = {}) {
  if (!M[key]) M[key] = new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.6, metalness: 0 }, o));
  return M[key];
}
const PCB_BLUE = () => mat('pcbB', 0x1f4f9a, { roughness: 0.55 });
const PCB_BLACK = () => mat('pcbK', 0x1b1d20, { roughness: 0.5 });
const PCB_GREY = () => mat('pcbG', 0x5a6470);
const METAL = () => mat('metal', 0xc5cad1, { metalness: 0.75, roughness: 0.32 });
const BLACK = () => mat('blk', 0x141518, { roughness: 0.7 });
const CHIP = () => mat('chip', 0x202226, { roughness: 0.45 });
const GOLD = () => mat('gold', 0xd2a43a, { metalness: 0.8, roughness: 0.3 });
const WHITE = () => mat('wht', 0xeeeeee);
const T = D.PCB_T;

function B(g, x, y, z, sx, sy, sz, m) {
  const b = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), m);
  b.position.set(x + sx / 2, y + sy / 2, z + sz / 2); g.add(b); return b;
}
// trụ đứng (trục z), trụ theo trục x, trụ theo trục y
function Cz(g, x, y, z, r, h, m, seg = 24) {
  const c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), m);
  c.rotation.x = Math.PI / 2; c.position.set(x, y, z + h / 2); g.add(c); return c;
}
function Cx(g, x, y, z, r, h, m, seg = 24) {
  const c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), m);
  c.rotation.z = Math.PI / 2; c.position.set(x + h / 2, y, z); g.add(c); return c;
}
function Cy(g, x, y, z, r, h, m, seg = 24) {
  const c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), m);
  c.position.set(x, y + h / 2, z); g.add(c); return c;
}
// hàng header 2,54 mm: (x0,y0) là tâm chân đầu tiên, dir 'x' hoặc 'y'; chân cắm xuống dưới PCB
function header(g, x0, y0, n, dir, rows = 1) {
  const p = 2.54, len = n * p;
  for (let r = 0; r < rows; r++) {
    const ox = dir === 'y' ? r * p : 0, oy = dir === 'x' ? r * p : 0;
    if (dir === 'x') B(g, x0 - p / 2, y0 + oy - p / 2, -2.5, len, p, 2.5, BLACK());
    else B(g, x0 + ox - p / 2, y0 - p / 2, -2.5, p, len, 2.5, BLACK());
    for (let i = 0; i < n; i++) {
      const px = x0 + ox + (dir === 'x' ? i * p : 0), py = y0 + oy + (dir === 'y' ? i * p : 0);
      B(g, px - 0.32, py - 0.32, -8.5, 0.64, 0.64, 8.5 + T + 0.6, GOLD());
    }
  }
}
function smd(g, x, y, n, dx, dy) { for (let i = 0; i < n; i++) B(g, x + i * dx, y + i * dy, T, 1.6, 0.8, 0.5, mat('smd', 0x8a6a3c)); }

const BUILD = {
  ESP32(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLACK());
    // ESP-WROOM-32: 18 × 25,5 × 3,1, ăng-ten quay về đầu x = 0
    B(g, 0, (W - 18) / 2, T, 25.5, 18, 0.8, mat('wroom', 0x1d2633));
    B(g, 7.5, (W - 16) / 2, T + 0.8, 17.5, 16, 2.3, METAL());
    B(g, 1, (W - 14) / 2, T + 0.81, 5, 14, 0.06, GOLD());
    const x0 = (L - 18 * 2.54) / 2;
    header(g, x0, 1.27, 19, 'x'); header(g, x0, W - 1.27, 19, 'x');
    B(g, L - 5.5, W / 2 - 3.9, T, 6, 7.8, 2.8, METAL());              // micro-USB
    for (const by of [3.0, W - 6.6]) {                                    // nút EN / BOOT
      B(g, L - 9, by, T, 6, 3.6, 1.6, mat('btn', 0x30343a));
      B(g, L - 7.5, by + 0.9, T + 1.6, 3, 1.8, 0.7, WHITE());
    }
    B(g, 31, W / 2 - 2.5, T, 5, 5, 0.9, CHIP());                         // CP2102
    B(g, 30, 3.0, T, 6.5, 3.5, 1.6, CHIP());                             // AMS1117
    B(g, 40, W - 6, T, 1.6, 0.8, 0.5, mat('led', 0xff3b30));
  },
  W5500(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    // RJ45 HR911105A 21,3 × 16 × 13,5, mặt cắm hướng về vách trái
    B(g, -1.5, W / 2 - 8, T, 21.3, 16, 13.5, METAL());
    B(g, -1.62, W / 2 - 5.9, T + 1.2, 0.2, 11.8, 9.6, BLACK());
    B(g, -1.62, W / 2 - 7.6, T + 11.0, 0.2, 2.6, 1.8, mat('ledG', 0x34d058, { emissive: 0x0f5020 }));
    B(g, -1.62, W / 2 + 5.0, T + 11.0, 0.2, 2.6, 1.8, mat('ledY', 0xf5c400, { emissive: 0x504000 }));
    B(g, 29, W / 2 - 3.5, T, 7, 7, 0.9, CHIP());                         // chip W5500
    B(g, 39, 4, T, 5, 3.2, 1.1, METAL());                                 // thạch anh 25 MHz
    B(g, 39, W - 7.5, T, 6.5, 3.5, 1.6, CHIP());                         // ổn áp 3,3 V
    smd(g, 24, 4, 4, 0, 2.2);
    header(g, L - 3.81, W / 2 - 5.08, 5, 'y', 2);
  },
  RS232(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    // DB9 cái gắn PCB góc vuông: tấm mặt bích 30,8 × 12,5, thân D lồi ra vách
    B(g, 0, W / 2 - 15.4, T, 1, 30.8, 12.5, METAL());
    B(g, -6, W / 2 - 8.5, T + 2.2, 6, 17, 8.1, METAL());
    B(g, -6.1, W / 2 - 7.4, T + 3.0, 0.2, 14.8, 6.4, BLACK());
    for (const dy of [-12.5, 12.5]) Cx(g, -4.5, W / 2 + dy, T + 6.25, 2.4, 4.5, METAL(), 6);
    B(g, 1, W / 2 - 9.5, T, 9, 19, 10, BLACK());
    B(g, 15, W / 2 - 3, T, 10, 6, 1.7, CHIP());                          // MAX3232
    smd(g, 14, 3, 4, 3, 0); smd(g, 14, W - 4, 4, 3, 0);
    header(g, L - 1.27, W / 2 - 3.81, 4, 'y');
  },
  PC817(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    for (let i = 0; i < 4; i++) {
      const cx = 9 + i * 6.5;
      B(g, cx, W / 2 - 3.25, T, 4.6, 6.5, 3.5, CHIP());                  // PC817 DIP-4
      B(g, cx + 0.8, 3.5, T, 1.6, 0.8, 0.5, mat('led', 0xff3b30));
      B(g, cx + 0.5, W - 5, T, 3.2, 1.6, 0.6, mat('res', 0x222222));
    }
    header(g, 1.27, W / 2 - 5.08, 5, 'y');                                // IN1–IN4, G
    header(g, L - 1.27, W / 2 - 5.08, 5, 'y');                            // OUT1–OUT4, G
  },
  ADS1115(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    B(g, 12, 8, T, 3, 3, 1.0, CHIP());
    smd(g, 6, 10, 3, 0, 2);
    header(g, (L - 9 * 2.54) / 2, 1.27, 10, 'x');
  },
  LM2596(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    B(g, 3, 4.5, T, 10, 9, 4.4, CHIP());                                  // LM2596 TO-263
    B(g, 1.5, 6, T, 2, 6, 1.3, METAL());
    B(g, 16, 2.5, T, 12, 12, 7, mat('ind', 0x2c2e31, { roughness: 0.8 }));// cuộn cảm 33 µH
    Cz(g, 35, 6.0, T, 4, 11, mat('cap', 0x1e2a50));                      // tụ 220 µF
    Cz(g, 35, 6.0, T + 11, 3.2, 0.3, METAL());
    Cz(g, 35, 15.5, T, 3.15, 11, mat('cap', 0x1e2a50));
    Cz(g, 35, 15.5, T + 11, 2.5, 0.3, METAL());
    B(g, 16.5, 15.8, T, 9.5, 4.4, 10, mat('pot', 0x2f62c4));              // biến trở chỉnh áp
    Cz(g, 18.0, 18.0, T + 10, 1.1, 1.2, GOLD());
    for (const [px, py] of [[0.6, 1], [0.6, W - 3], [L - 2.6, 1], [L - 2.6, W - 3]]) B(g, px, py, T, 2, 2, 0.1, GOLD());
  },
  MPU6050(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    B(g, 9, 6.5, T, 4, 4, 0.9, CHIP());
    B(g, 3, 8, T, 3, 1.6, 1.1, CHIP());
    header(g, (L - 7 * 2.54) / 2, 1.27, 8, 'x');
  },
  HW685(g, L, W) {
    B(g, 0, 0, 0, L, W, T, PCB_BLUE());
    B(g, 0.5, W / 2 - 5, T, 7.5, 10, 8.5, mat('term', 0x2f8f5b));        // cầu đấu I+ I-
    B(g, 1.5, W / 2 - 4, T + 8.5, 4, 2.5, 0.6, METAL()); B(g, 1.5, W / 2 + 1.5, T + 8.5, 4, 2.5, 0.6, METAL());
    B(g, 15, W / 2 - 2.5, T, 5, 4, 1.5, CHIP());                          // op-amp
    for (const py of [3, W - 8]) { B(g, 24, py, T, 9.5, 4.8, 10, mat('pot', 0x2f62c4)); Cz(g, 25.5, py + 2.4, T + 10, 1.1, 1.2, GOLD()); }
    header(g, L - 1.27, W / 2 - 2.54, 3, 'y');                            // VCC VOUT GND
    B(g, 36, 3, T, 2.6, 5.1, 2.5, BLACK());                               // jumper chọn dải ra
  },
};

function geo(b64) {
  const bin = atob(b64), u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const g = new THREE.STLLoader().parse(u8.buffer); g.computeVertexNormals(); return g;
}
const matBase = new THREE.MeshStandardMaterial({ color: 0xd6dde4, roughness: 0.8, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false });
const matLid = new THREE.MeshStandardMaterial({ color: 0xa9b4bf, roughness: 0.75, transparent: true, opacity: 0.9 });
const base = new THREE.Mesh(geo(STL.base), matBase); base.renderOrder = 2; world.add(base);
const lid = new THREE.Mesh(geo(STL.lid), matLid); lid.renderOrder = 3; world.add(lid);

const mods = new THREE.Group(); world.add(mods);
const anchors = [];
for (const m of D.mods) {
  const g = new THREE.Group(); g.position.set(m.x, m.y, m.z);
  (BUILD[m.name] || BUILD.HW685)(g, m.L, m.W); mods.add(g);
  anchors.push({ obj: mods, p: new THREE.Vector3(m.x + m.L / 2, m.y + m.W / 2, m.z + 18), text: m.name, kind: 'mod' });
}
// OLED dưới nắp, mặt kính quay lên cửa sổ
const o = D.oled;
const og = new THREE.Group(); og.position.set(o.x, o.y, -o.post_h - 4.1); lid.add(og);
B(og, 0, 0, 0, o.L, o.W, T, PCB_BLUE());
B(og, 0.15, 3.0, T, 26.7, 19.3, 1.5, BLACK());
B(og, o.win_dx + 0.6, o.win_dy + 0.9, T + 1.51, 21.74, 11.2, 0.05, mat('scr', 0x0b2233, { emissive: 0x0a2c44 }));
for (let i = 0; i < 4; i++) B(og, o.L / 2 - 3.81 + i * 2.54 - 0.32, o.W - 1.6, T, 0.64, 0.64, 3, GOLD());

// Phụ kiện gắn vách (toạ độ hộp)
const acc = new THREE.Group(); world.add(acc);
const GREY = mat('gl', 0x3b4048, { roughness: 0.7 });
const CABLE = mat('cab', 0x6b7b8f, { roughness: 0.8 });
for (const c of D.cuts) {
  if (c.label.startsWith('Ốc siết cáp')) {                       // PG7: chụp ngoài + đai ốc trong
    Cy(acc, c.u, -D.WALL - 9, c.zc, 7.0, 9, GREY, 32);
    Cy(acc, c.u, -D.WALL - 12.5, c.zc, 4.2, 3.5, GREY, 32);
    Cy(acc, c.u, -D.WALL - 3, c.zc, 9.5, 3, GREY, 6);
    Cy(acc, c.u, 0, c.zc, 9.5, 3, GREY, 6);
    Cy(acc, c.u, -D.WALL - 60, c.zc, 2.8, 48, CABLE, 16);
  } else if (c.label.startsWith('Jack DC')) {                    // jack DC bắt ren M8
    Cx(acc, D.IN_L + D.WALL, c.u, c.zc, 6.4, 2.2, METAL(), 6);
    Cx(acc, D.IN_L + D.WALL + 2.2, c.u, c.zc, 4.3, 2.5, BLACK());
    Cx(acc, D.IN_L - 14, c.u, c.zc, 5.2, 14, BLACK());
  }
}
// Cáp LAN cắm vào RJ45: đầu cắm + chụp + dây
const rj = D.cuts.find(c => c.label === 'RJ45');
B(acc, -D.WALL - 6, rj.u - 5.9, rj.zc - 3.5, 8, 11.8, 7.5, mat('plug', 0xdfe6ee, { transparent: true, opacity: 0.85 }));
B(acc, -D.WALL - 22, rj.u - 6.5, rj.zc - 4.2, 16, 13, 8.4, mat('boot', 0x2b6cb0));
Cx(acc, -D.WALL - 92, rj.u, rj.zc, 3, 70, mat('lan', 0x2b6cb0), 16);
// Cáp RS232: giắc DB9 đực + dây
const db = D.cuts.find(c => c.label === 'DB9');
B(acc, -D.WALL - 20, db.u - 16, db.zc - 7, 17, 32, 14, mat('hood', 0x2a2d33));
Cx(acc, -D.WALL - 90, db.u, db.zc, 3.2, 70, mat('ser', 0x454c57), 16);
// 2 LED trên nắp
for (const [lx, col] of [[20, 0x34d058], [30, 0xff9f1c]]) {
  const led = Cz(lid, lx, D.IN_W - 12, LID_T - 1.5, 2.5, 3.5, mat('l' + col, col, { emissive: col, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
}
anchors.push({ obj: acc, p: new THREE.Vector3(-D.WALL - 92, rj.u, rj.zc + 6), text: 'LAN → switch → PLC + laptop', kind: 'io' });
anchors.push({ obj: acc, p: new THREE.Vector3(-D.WALL - 90, db.u, db.zc + 6), text: 'RS232 → PLC', kind: 'io' });
anchors.push({ obj: acc, p: new THREE.Vector3(D.IN_L + D.WALL + 6, 88, 30), text: '24 V DC', kind: 'io' });
anchors.push({ obj: acc, p: new THREE.Vector3(100, -D.WALL - 60, 34), text: 'Tín hiệu máy (PG7)', kind: 'io' });
anchors.push({ obj: acc, p: new THREE.Vector3(D.IN_L + D.WALL + 6, 54, 6), text: 'USB laptop', kind: 'io' });

// nhãn HTML bám theo điểm 3D
for (const a of anchors) { const el = document.createElement('span'); el.className = 'lbl ' + a.kind; el.textContent = a.text; tagsEl.appendChild(el); a.el = el; }
const v = new THREE.Vector3();
function placeTags() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  for (const a of anchors) {
    if (!showTags || !a.obj.visible) { a.el.hidden = true; continue; }
    v.copy(a.p); world.localToWorld(v); v.project(camera);
    a.el.hidden = v.z > 1;
    const half = a.el.offsetWidth / 2 + 6;
    const sx = Math.min(Math.max((v.x * 0.5 + 0.5) * w, half), w - half);
    a.el.style.transform = `translate(${sx}px, ${(-v.y * 0.5 + 0.5) * h}px) translate(-50%, -100%)`;
  }
}

let showLid = true, open = true, showMods = true, showTags = true;
function layout() {
  lid.visible = showLid;
  lid.position.z = D.IN_H + (open ? 55 : 0);
  mods.visible = showMods; acc.visible = showMods;
}
function bind(id, fn) {
  const el = document.getElementById(id);
  el.addEventListener('click', () => { const r = fn(); if (r !== undefined) el.setAttribute('aria-pressed', String(r)); layout(); });
}
bind('bLid', () => (showLid = !showLid));
bind('bOpen', () => (open = !open));
bind('bMods', () => (showMods = !showMods));
bind('bTags', () => (showTags = !showTags));
const VIEWS = {
  home: [[200, 210, 250], [0, 25, 0]],
  left: [[-300, 90, 40], [0, 20, 0]],
  front: [[30, 110, 300], [0, 20, 0]],
  top: [[0, 380, 1], [0, 0, 0]],
};
function go(k) { const [p, t] = VIEWS[k]; camera.position.set(...p); controls.target.set(...t); controls.update(); }
for (const k of Object.keys(VIEWS)) document.getElementById('v_' + k).addEventListener('click', () => go(k));
function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
function theme() { scene.background = new THREE.Color(css('--stage') || '#dfe5ea'); }
window.addEventListener('resize', resize);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', theme);
new MutationObserver(theme).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
theme(); layout(); go('home'); resize();
(function loop() { controls.update(); renderer.render(scene, camera); placeTags(); requestAnimationFrame(loop); })();
"""

html = f"""<title>Vỏ hộp Smart PLC Gateway</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* Bố cục: khung xem 3D lớn bên trái, cột thông số bên phải (xếp xuống dưới trên điện thoại) */
:root {{
  --bg: #eef1f4; --panel: #ffffff; --ink: #1c232c; --muted: #5d6875; --line: #d6dce3;
  --accent: #d9601a; --stage: #e3e8ed; --tag-bg: #ffffff; --tag-io: #fff1e6;
  --f-display: "Barlow", "Arial Narrow", system-ui, sans-serif;
  --f-body: "Barlow", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #12161b; --panel: #1a2027; --ink: #e6ebf0; --muted: #98a3af; --line: #2c343d;
  --accent: #f08a43; --stage: #0f1317; --tag-bg: #232b34; --tag-io: #3a2a1d; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #12161b; --panel: #1a2027; --ink: #e6ebf0; --muted: #98a3af; --line: #2c343d;
  --accent: #f08a43; --stage: #0f1317; --tag-bg: #232b34; --tag-io: #3a2a1d; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font-family: var(--f-body); font-size: 15px; line-height: 1.5; }}
.wrap {{ padding-block: 20px 28px; padding-inline: 16px; max-width: 1320px; margin: 0 auto; display: grid; gap: 16px;
  grid-template-columns: minmax(0, 1fr) 360px; }}
header {{ grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 18px; }}
h1 {{ font-family: var(--f-display); font-weight: 700; font-size: clamp(22px, 3vw, 30px); margin: 0; text-wrap: balance; }}
.tag {{ font-family: var(--f-mono); font-size: 12px; color: var(--muted); }}
.stage {{ position: relative; background: var(--stage); border: 1px solid var(--line); border-radius: 6px;
  min-height: 480px; height: min(76vh, 720px); overflow: hidden; min-width: 0; }}
#view {{ width: 100%; height: 100%; display: block; touch-action: none; }}
#tags {{ position: absolute; inset: 0; pointer-events: none; }}
.lbl {{ position: absolute; left: 0; top: 0; white-space: nowrap; font: 600 11.5px var(--f-body); color: var(--ink);
  background: var(--tag-bg); border: 1px solid var(--line); border-radius: 3px; padding: 1px 6px; }}
.lbl.io {{ background: var(--tag-io); border-color: var(--accent); }}
.bar {{ position: absolute; left: 12px; right: 12px; top: 12px; display: flex; flex-wrap: wrap; gap: 6px; }}
.bar .sep {{ width: 1px; background: var(--line); margin: 2px 4px; }}
.bar button {{ font: 600 13px var(--f-body); color: var(--ink); background: var(--panel); border: 1px solid var(--line);
  border-radius: 4px; padding: 5px 10px; cursor: pointer; }}
.bar button[aria-pressed="true"] {{ border-color: var(--accent); color: var(--accent); }}
.bar button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.hint {{ position: absolute; right: 12px; bottom: 10px; font: 12px var(--f-mono); color: var(--muted); }}
aside {{ display: grid; gap: 14px; align-content: start; min-width: 0; }}
section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px; }}
h2 {{ font: 600 12px var(--f-body); text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 0 0 10px; }}
.size {{ font-family: var(--f-mono); font-size: 20px; font-variant-numeric: tabular-nums; }}
.size small {{ font-size: 12px; color: var(--muted); }}
.note {{ margin: 6px 0 0; color: var(--muted); font-size: 13.5px; }}
ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }}
li {{ display: grid; grid-template-columns: 1fr auto; column-gap: 8px; align-items: baseline; font-size: 14px; }}
li .desc {{ grid-column: 1 / -1; color: var(--muted); font-size: 13px; line-height: 1.35; }}
li .dim {{ font-family: var(--f-mono); font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }}
#cuts li {{ grid-template-columns: 74px 1fr auto; }}
#cuts .side {{ font-weight: 600; font-size: 13px; }}
#cuts .desc {{ grid-column: 2 / -1; }}
.warn {{ border-left: 3px solid var(--accent); padding-left: 10px; font-size: 13.5px; margin: 0; }}
code {{ font-family: var(--f-mono); font-size: 12.5px; }}
@media (max-width: 900px) {{ .wrap {{ grid-template-columns: minmax(0, 1fr); }} .stage {{ height: 64vh; min-height: 380px; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto; }} }}
</style>

<div class="wrap">
  <header>
    <h1>Vỏ hộp Smart PLC Gateway</h1>
    <span class="tag">UET-BigHero · DENSO Factory Hacks 2026 · bản in 3D v0.2</span>
  </header>
  <div class="stage">
    <canvas id="view" aria-label="Mô hình 3D vỏ hộp và module, kéo để xoay"></canvas>
    <div id="tags"></div>
    <div class="bar" role="toolbar" aria-label="Hiển thị">
      <button id="bLid" aria-pressed="true">Nắp</button>
      <button id="bOpen" aria-pressed="true">Tách nắp</button>
      <button id="bMods" aria-pressed="true">Linh kiện</button>
      <button id="bTags" aria-pressed="true">Nhãn</button>
      <span class="sep"></span>
      <button id="v_home">Tổng thể</button>
      <button id="v_left">Vách trái</button>
      <button id="v_front">Mặt trước</button>
      <button id="v_top">Từ trên</button>
    </div>
    <div class="hint">kéo: xoay · cuộn: phóng to · chuột phải: dời</div>
  </div>
  <aside>
    <section>
      <h2>Kích thước ngoài</h2>
      <div class="size">{ext_L:g} × {ext_W:g} × {ext_H:g} <small>mm</small></div>
      <p class="note">Chưa tính 2 tai bắt vít 12 mm hai đầu. Vách {G.WALL:g} mm, đáy {G.FLOOR:g} mm, nắp {G.LID_T:g} mm có gờ lồng, 4 vít M3. In PETG, đế không cần support.</p>
    </section>
    <section>
      <h2>Lỗ khoét và kết nối</h2>
      <ul id="cuts">{cut_rows}</ul>
    </section>
    <section>
      <h2>Linh kiện bên trong</h2>
      <ul>{mod_rows}</ul>
    </section>
    <section>
      <p class="warn">Mục ghi "đo lại" là kích thước phổ biến của hàng bán ngoài, chưa đo trên module của nhóm. Đo bằng thước kẹp, sửa bảng <code>MODULES</code> trong <code>gen_enclosure.py</code>, chạy lại hai script là có STL và trang này mới.</p>
    </section>
  </aside>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const D = {json.dumps(data, ensure_ascii=False)};
const LID_T = {G.LID_T};
const STL = {{ base: "{b64['base']}", lid: "{b64['lid']}" }};
{JS}
</script>
"""
with open(os.path.join(OUT, "viewer.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("Đã tạo", os.path.join(OUT, "viewer.html"), f"{len(html) / 1e6:.2f} MB")
