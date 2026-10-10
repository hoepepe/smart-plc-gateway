"""
gen_enclosure.py — Vỏ hộp in 3D cho Smart PLC Gateway (đế + nắp), xuất STL.

    pip install manifold3d trimesh numpy matplotlib
    python hardware/enclosure/gen_enclosure.py

Ra: hardware/enclosure/out/{gateway_base.stl, gateway_lid.stl, preview_*.png}

Toàn bộ kích thước nằm trong các bảng ở đầu file. KÍCH THƯỚC MODULE LÀ GIÁ TRỊ PHỔ BIẾN CỦA HÀNG
TRÊN THỊ TRƯỜNG — đo lại bằng thước kẹp module thật của nhóm, sửa bảng MODULES, chạy lại là xong.

Cách giữ module: mỗi module nằm trong một "khay góc" (4 góc có gờ đỡ + vách chặn + mấu giữ),
KHÔNG phụ thuộc vị trí lỗ bắt vít (mỗi hãng một kiểu, nhiều bản ESP32 38 chân không có lỗ).
Đơn vị: mm. Gốc toạ độ: góc trong của đáy hộp. x theo chiều dài, y theo chiều sâu, z hướng lên.
"""
import os

import numpy as np
from manifold3d import Manifold, OpType

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# ───────────────────────── Hộp ─────────────────────────
IN_L, IN_W, IN_H = 160.0, 105.0, 55.0   # lòng hộp (cao 55 để đủ chỗ dây dupont)
WALL, FLOOR = 2.5, 3.0
LID_T, LIP_H, LIP_T, FIT = 2.5, 4.0, 1.6, 0.3
BOSS_R, PILOT_R, SCREW_R = 4.0, 1.25, 1.7     # cột vít góc, lỗ mồi M3, lỗ thông M3
CORNER = [(3.5, 3.5), (IN_L - 3.5, 3.5), (3.5, IN_W - 3.5), (IN_L - 3.5, IN_W - 3.5)]  # lấn vào vách cho liền khối
SEG = 48

# ───────────────────────── Module (đo lại bằng thước kẹp!) ─────────────────────────
# tên: (x, y, dài, rộng, độ cao mặt dưới PCB so với đáy, mô tả)
# Bản demo cắm dây dupont cái vào chân đực của module, nên cần chừa chỗ cho đầu dupont:
#   chân cắm xuống (header hàn sẵn mặt dưới, như ESP32): PCB kê cao 28 mm → đầu dupont dài 14 mm + chỗ uốn dây
#   chân hướng lên (tự hàn header hướng lên, như ADS1115, MPU6050): PCB kê thấp 6 mm, dây đi phía trên
DOWN, UP = 28.0, 6.0
PCB_T = 1.6
MODULES = {
    "W5500":   (1.5, 10, 55.0, 28.0, DOWN, "W5500 Ethernet, RJ45 quay ra vách trái"),
    "RS232":   (1.5, 48, 33.0, 30.0, DOWN, "TTL-RS232 MAX3232, DB9 quay ra vách trái"),
    "PC817":   (65, 6, 40.0, 30.0, DOWN, "PC817 4 kênh, dây vào qua 2 ốc siết cáp mặt trước"),
    "ADS1115": (115, 8, 28.0, 18.0, UP, "ADS1115 — hàn header HƯỚNG LÊN"),
    "ESP32":   (102, 40, 55.0, 28.0, DOWN, "ESP32 DevKit V1 38 chân, cổng USB ra vách phải"),
    "LM2596":  (106, 78, 43.0, 21.0, UP, "LM2596 hạ áp 24V→5V, dây hàn/bắt vít phía trên"),
    "MPU6050": (34, 84, 21.0, 16.0, UP, "GY-521 MPU6050 — hàn header HƯỚNG LÊN"),
    "HW685":   (59, 78, 42.0, 25.0, DOWN, "HW-685 đổi 4–20 mA → 0–3,3 V, nguồn 7–36 V"),
}
PINS = {k: ("down" if v[4] == DOWN else "up") for k, v in MODULES.items()}
LEDGE = DOWN
# OLED SSD1306 0.96" gắn dưới nắp
# 0.96" SSD1306: PCB 27 × 27, dày 4,1, vùng hiển thị 21,74 × 11,2 (datasheet module)
OLED = dict(x=58, y=50, L=27.0, W=27.0, win_dx=2.0, win_dy=7.0, win_L=23.0, win_W=13.0,
            hole_inset=2.0, hole_r=0.9, post_h=4.0)

# ───────────────────────── Lỗ khoét vách ─────────────────────────
def _top(name):
    return MODULES[name][4] + PCB_T


ZW = 34.0     # độ cao tâm lỗ cho phụ kiện không gắn PCB (jack DC, ốc siết cáp)
CUTS = [
    # (vách, tâm theo trục ngang của vách, tâm z, rộng, cao, hình, ghi chú)
    ("left", MODULES["W5500"][1] + 14, _top("W5500") + 7.0, 17.0, 15.0, "rect", "RJ45"),
    ("left", MODULES["RS232"][1] + 15, _top("RS232") + 6.0, 20.0, 12.0, "rect", "DB9"),
    ("right", MODULES["ESP32"][1] + 14, _top("ESP32") + 1.5, 13.0, 8.5, "rect", "USB ESP32"),
    ("right", 88.0, ZW, 8.2, 8.2, "circle", "Jack DC 5.5×2.1 bắt ren M8"),
    ("front", 75.0, ZW, 12.6, 12.6, "circle", "Ốc siết cáp PG7 — đầu vào số"),
    ("front", 95.0, ZW, 12.6, 12.6, "circle", "Ốc siết cáp PG7 — đầu vào số"),
    ("front", 130.0, ZW, 12.6, 12.6, "circle", "Ốc siết cáp PG7 — cảm biến 4–20 mA"),
]
DB9_SCREW = 12.5          # 2 lỗ vít DB9 cách tâm ±12,5 mm
VENTS = dict(n=8, w=2.0, h=16.0, pitch=5.0, z=40.0)


def box(x, y, z, sx, sy, sz):
    return Manifold.cube((sx, sy, sz)).translate((x, y, z))


def cyl(x, y, z, h, r):
    return Manifold.cylinder(h, r, r, SEG).translate((x, y, z))


def wall_cut(side, u, zc, w, h, shape):
    """Khối dùng để khoét xuyên vách. u = vị trí dọc theo vách (toạ độ lòng hộp)."""
    d = WALL + 4
    if shape == "circle":
        c = Manifold.cylinder(d, w / 2, w / 2, SEG)
        if side in ("left", "right"):
            c = c.rotate((0, 90, 0))
            x = -WALL - 2 if side == "left" else IN_L - 2
            return c.translate((x, u, zc))
        c = c.rotate((-90, 0, 0))
        y = -WALL - 2 if side == "front" else IN_W - 2
        return c.translate((u, y, zc))
    if side in ("left", "right"):
        x = -WALL - 2 if side == "left" else IN_L - 2
        return box(x, u - w / 2, zc - h / 2, d, w, h)
    y = -WALL - 2 if side == "front" else IN_W - 2
    return box(u - w / 2, y, zc - h / 2, w, d, h)


def bx(x0, x1, y0, y1, z0, z1):
    return box(min(x0, x1), min(y0, y1), z0, abs(x1 - x0), abs(y1 - y0), z1 - z0)


def cradle(x, y, L, W, ledge):
    """Khay góc: gờ đỡ dưới PCB + vách chữ L ở 4 góc + mấu giữ 0,6 mm đè lên mặt PCB."""
    c, t, s = 0.3, 2.0, 7.0      # khe hở, dày vách, độ dài mỗi nhánh chữ L
    top = ledge + PCB_T + 1.4
    parts = []
    for cx, sx in ((x, -1), (x + L, 1)):
        for cy, sy in ((y, -1), (y + W, 1)):
            wx = cx + sx * c                                                                    # mặt trong vách
            wy = cy + sy * c
            # gờ đỡ 3 × 3 dưới góc PCB, liền khối với vách chữ L cho cứng (tránh chạm hàng header)
            parts.append(bx(cx - 3 * sx, wx + sx * t, cy - 3 * sy, wy + sy * t, 0, ledge))
            parts.append(bx(wx, wx + sx * t, cy - sy * s, wy + sy * t, 0, top))                # nhánh // trục y
            parts.append(bx(cx - sx * s, wx + sx * t, wy, wy + sy * t, 0, top))                # nhánh // trục x
            parts.append(bx(cx - sx * (s - 1), cx - sx * 1, wy, cy - sy * 0.6,                 # mấu giữ
                            ledge + PCB_T + 0.2, top))
    return Manifold.batch_boolean(parts, OpType.Add)


def make_base():
    ox, oy = -WALL, -WALL
    shell = box(ox, oy, -FLOOR, IN_L + 2 * WALL, IN_W + 2 * WALL, IN_H + FLOOR)
    shell = shell - box(0, 0, 0, IN_L, IN_W, IN_H + 1)
    # bo tròn ngoài thô: vát 4 cạnh đứng
    for (cx, cy) in [(ox, oy), (IN_L + WALL, oy), (ox, IN_W + WALL), (IN_L + WALL, IN_W + WALL)]:
        shell = shell - box(cx - 1.5, cy - 1.5, -FLOOR - 1, 3, 3, IN_H + FLOOR + 2)
    # cột vít góc
    for (cx, cy) in CORNER:
        shell = shell + cyl(cx, cy, 0, IN_H - LIP_H - 0.5, BOSS_R)
        shell = shell - cyl(cx, cy, IN_H - LIP_H - 16, 16, PILOT_R)
    # khay module
    for name, (x, y, L, W, ledge, _) in MODULES.items():
        shell = shell + cradle(x, y, L, W, ledge)
    # lỗ vách
    for side, u, zc, w, h, shape, _ in CUTS:
        shell = shell - wall_cut(side, u, zc, w, h, shape)
        if _ == "DB9":  # noqa
            for du in (-DB9_SCREW, DB9_SCREW):
                shell = shell - wall_cut(side, u + du, zc, 3.2, 3.2, "circle")
    # khe thông gió vách sau (phía trên ESP32 và LM2596)
    for i in range(VENTS["n"]):
        u = 100 + i * VENTS["pitch"]
        shell = shell - wall_cut("back", u, VENTS["z"], VENTS["w"], VENTS["h"], "rect")
    # tai bắt vít (bắt tường/tủ điện) hai đầu, lỗ Ø4,5
    for xe in (-WALL - 12, IN_L + WALL):
        ear = box(xe, IN_W / 2 - 15, -FLOOR, 12, 30, 3)
        ear = ear - cyl(xe + 6, IN_W / 2 - 7, -FLOOR - 1, 5, 2.25) - cyl(xe + 6, IN_W / 2 + 7, -FLOOR - 1, 5, 2.25)
        shell = shell + ear
    # 2 lỗ M3 dưới đáy để bắt kẹp DIN rail 35 mm mua sẵn (khoảng cách 2 lỗ: chỉnh theo kẹp)
    for dy in (-12.5, 12.5):
        shell = shell - cyl(IN_L / 2, IN_W / 2 + dy, -FLOOR - 1, FLOOR + 2, 1.7)
    return shell


def make_lid():
    """Nắp in úp (mặt ngoài nằm trên bàn in). Toạ độ: z=0 là mặt trong của nắp, lật lại khi lắp."""
    plate = box(-WALL, -WALL, 0, IN_L + 2 * WALL, IN_W + 2 * WALL, LID_T)
    lip_o = box(FIT, FIT, -LIP_H, IN_L - 2 * FIT, IN_W - 2 * FIT, LIP_H)
    lip_i = box(FIT + LIP_T, FIT + LIP_T, -LIP_H - 1, IN_L - 2 * (FIT + LIP_T), IN_W - 2 * (FIT + LIP_T), LIP_H + 1)
    lid = plate + (lip_o - lip_i)
    # chừa chỗ cho cột vít góc trong viền
    for (cx, cy) in CORNER:
        lid = lid - cyl(cx, cy, -LIP_H - 1, LIP_H + 1, BOSS_R + 0.4)
        lid = lid - cyl(cx, cy, -1, LID_T + 2, SCREW_R)
        lid = lid - cyl(cx, cy, LID_T - 1.6, 2, 3.2)          # chìm đầu vít
    # cửa sổ OLED + 4 cột M2 phía trong
    o = OLED
    lid = lid - box(o["x"] + o["win_dx"], o["y"] + o["win_dy"], -1, o["win_L"], o["win_W"], LID_T + 2)
    for hx in (o["x"] + o["hole_inset"], o["x"] + o["L"] - o["hole_inset"]):
        for hy in (o["y"] + o["hole_inset"], o["y"] + o["W"] - o["hole_inset"]):
            lid = lid + cyl(hx, hy, -o["post_h"], o["post_h"], 2.2) - cyl(hx, hy, -o["post_h"] - 1, o["post_h"] + 0.5, o["hole_r"])
    # khe thông gió trên LM2596 và ESP32
    for i in range(9):
        lid = lid - box(108 + i * 5, 72, -1, 2.0, 24, LID_T + 2)     # trên LM2596
    for i in range(7):
        lid = lid - box(108 + i * 5, 44, -1, 2.0, 20, LID_T + 2)     # trên ESP32, chừa chỗ lỗ nút
    # 2 lỗ kim Ø3 trên nút EN (reset) và BOOT của ESP32 — bấm bằng que nhựa/kim
    ex, ey, eL, eW = MODULES["ESP32"][:4]
    for by in (ey + 4.0, ey + eW - 4.0):
        lid = lid - cyl(ex + eL - 6.0, by, -1, LID_T + 2, 1.6)
    # 2 lỗ LED trạng thái Ø5 (nguồn, kết nối PLC)
    for lx in (20, 30):
        lid = lid - cyl(lx, IN_W - 12, -1, LID_T + 2, 2.6)
    return lid


def save(m, path):
    import trimesh
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    tm.export(path)
    return tm


def preview(base_tm, lid_tm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    colors = {"W5500": "#2b6cb0", "RS232": "#c05621", "PC817": "#2f855a", "ADS1115": "#6b46c1",
              "ESP32": "#1a202c", "LM2596": "#b7791f", "MPU6050": "#2c7a7b", "HW685": "#718096"}

    def module_boxes(ax):
        for name, (x, y, L, W, ledge, _) in MODULES.items():
            z0, h = ledge, PCB_T + (12 if name in ("W5500", "RS232", "LM2596") else 3)
            v = np.array([[x, y, z0], [x + L, y, z0], [x + L, y + W, z0], [x, y + W, z0],
                          [x, y, z0 + h], [x + L, y, z0 + h], [x + L, y + W, z0 + h], [x, y + W, z0 + h]])
            f = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
            ax.add_collection3d(Poly3DCollection([v[i] for i in f], facecolor=colors[name], alpha=0.9,
                                                 edgecolor="k", linewidth=0.2))
            ax.text(x + L / 2, y + W / 2, z0 + h + 2, name, fontsize=7, ha="center")

    def draw(tm, ax, color, alpha):
        ax.add_collection3d(Poly3DCollection(tm.vertices[tm.faces], facecolor=color, alpha=alpha,
                                             edgecolor="none", linewidth=0))

    for nm, elev, azim, with_lid in [("preview_ben_trong", 55, -60, False), ("preview_mat_trai", 18, -150, False),
                                     ("preview_dong_nap", 28, -55, True)]:
        fig = plt.figure(figsize=(9, 6.5), dpi=130)
        ax = fig.add_subplot(111, projection="3d")
        draw(base_tm, ax, "#cbd5e0", 0.55 if not with_lid else 0.9)
        if with_lid:
            lid = lid_tm.copy()
            lid.apply_transform(np.diag([1, 1, 1, 1]))
            lid.apply_translation((0, 0, IN_H))
            draw(lid, ax, "#a0aec0", 0.95)
        else:
            module_boxes(ax)
        ax.set_xlim(-20, IN_L + 20); ax.set_ylim(-10, IN_W + 10); ax.set_zlim(-5, 60)
        ax.set_box_aspect((IN_L + 40, IN_W + 20, 65))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title({"preview_ben_trong": "Bố trí module bên trong (khối màu = module, kích thước giả định)",
                      "preview_mat_trai": "Vách trái: RJ45 (PLC) và DB9 (RS232)",
                      "preview_dong_nap": "Hộp đóng nắp: cửa sổ OLED, khe thông gió, 2 lỗ LED"}[nm], fontsize=10)
        fig.savefig(os.path.join(OUT, nm + ".png"), bbox_inches="tight")
        plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    base, lid = make_base(), make_lid()
    for nm, m in (("base", base), ("lid", lid)):
        assert m.status().name == "NoError", (nm, m.status())
    b = save(base, os.path.join(OUT, "gateway_base.stl"))
    lt = save(lid, os.path.join(OUT, "gateway_lid.stl"))
    # nắp in úp: lật 180° để mặt ngoài nằm trên bàn in
    flip = lt.copy()
    flip.apply_transform(np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]))
    flip.export(os.path.join(OUT, "gateway_lid_print.stl"))
    for nm, tm in (("Đế", b), ("Nắp", lt)):
        ext = tm.bounds[1] - tm.bounds[0]
        print(f"{nm}: {ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm · kín khối={tm.is_watertight} · "
              f"thể tích {tm.volume / 1000:.0f} cm³")
    # ảnh xem trước: chạy build_viewer.py rồi mở out/viewer.html
    print("Đã lưu vào", OUT)


if __name__ == "__main__":
    main()
