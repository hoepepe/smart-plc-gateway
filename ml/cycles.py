"""
cycles.py — Mô phỏng chu kỳ gia công và huấn luyện bộ phát hiện chu kỳ bất thường.

Bối cảnh (theo trả lời của mentor DENSO, 21/09/2026):
  - DENSO đã có danh sách tín hiệu, muốn lấy dữ liệu TỪ PLC.
  - Điều kiện gia công cần thu: áp lực khí nén, lực ép, lực xiết, chiều cao, tải trọng.
  - Trạng thái máy: dừng, chuẩn bị, auto running, đang làm việc, hoàn thành, báo lỗi.

Script này làm ba việc:
  1. Sinh chu kỳ gia công cho 3 đại lượng: lực ép, lực xiết, áp lực khí nén —
     kèm các dạng lỗi thực tế của từng loại.
  2. Huấn luyện bộ phát hiện bất thường CHỈ TRÊN CHU KỲ BÌNH THƯỜNG.
     Nhà máy có rất nhiều dữ liệu bình thường nhưng rất ít dữ liệu lỗi, nên
     phương pháp phải học được từ dữ liệu bình thường là chính.
  3. Xuất cycles.json cho dashboard: tham số mô hình + một bộ chu kỳ mẫu
     lấy từ TẬP KIỂM TRA để giao diện phát lại.

Dashboard chạy ĐÚNG mô hình được đánh giá ở đây (khoảng cách Mahalanobis),
tính trên đặc trưng xuất sẵn — nên con số trên web và con số đo được là một.

Chạy:  python cycles.py
"""

import json
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.covariance import LedoitWolf

FS = 100  # Hz — tần số đọc thanh ghi PLC trong một chu kỳ

PROCESSES = {
    "PRESS_FORCE": {"vi": "Lực ép", "unit": "kN"},
    "TORQUE": {"vi": "Lực xiết", "unit": "N·m"},
    "AIR_PRESSURE": {"vi": "Áp lực khí nén", "unit": "bar"},
}

FAULTS = {
    "PRESS_FORCE": {
        "MISSING_PART": "Thiếu chi tiết — lực đỉnh thấp bất thường",
        "MISALIGNED": "Chi tiết lệch vị trí — có gai lực trước đỉnh",
        "DOUBLE_HIT": "Ép hai lần — xuất hiện hai đỉnh",
    },
    "TORQUE": {
        "STRIPPED": "Trờn ren — lực xiết tụt giữa chừng",
        "CROSS_THREAD": "Ren chéo — lực tăng dốc bất thường ngay đầu",
        "NOT_SEATED": "Không tới lực mục tiêu — bu-lông chưa bắt chặt",
    },
    "AIR_PRESSURE": {
        "LEAK": "Rò khí — áp tụt sâu và hồi chậm",
        "LOW_SUPPLY": "Nguồn khí yếu — áp nền thấp",
        "VALVE_STICK": "Van kẹt — áp dao động giật cục",
    },
}

FEATURES = ["peak", "trough", "t_peak", "mean_level", "rise_slope", "roughness", "n_peaks",
            "early_level", "mid_level"]


# ═══════════════════════ Sinh chu kỳ ═══════════════════════
def _press(rng, s, fault=None):
    """Chu kỳ ép: tăng đều lên đỉnh, giữ ổn định, nhả."""
    n = int(rng.integers(170, 230))
    t = np.linspace(0, 1, n)
    peak = s["peak"] * rng.uniform(0.97, 1.03)
    rise = np.clip(t / 0.35, 0, 1) ** 1.6
    fall = np.clip((1 - t) / 0.2, 0, 1)
    y = peak * np.minimum(rise, fall)

    if fault == "MISSING_PART":
        y *= rng.uniform(0.35, 0.6)
    elif fault == "MISALIGNED":
        i = int(n * rng.uniform(0.12, 0.2))
        y[i:i + 8] += peak * rng.uniform(0.35, 0.55)
        y *= rng.uniform(1.06, 1.15)
    elif fault == "DOUBLE_HIT":
        c2 = rng.uniform(0.72, 0.82)
        y = y + peak * 0.85 * np.exp(-((t - c2) / 0.045) ** 2)
        y[t > 0.62] = np.maximum(y[t > 0.62] * 0.35, peak * 0.85 * np.exp(-((t[t > 0.62] - c2) / 0.045) ** 2))
    return y


def _torque(rng, s, fault=None):
    """Chu kỳ siết: tăng chậm lúc vặn tự do, tăng tuyến tính sau khi chạm mặt, dừng ở lực mục tiêu."""
    n = int(rng.integers(160, 220))
    t = np.linspace(0, 1, n)
    target = s["peak"] * rng.uniform(0.98, 1.02)
    snug = rng.uniform(0.35, 0.45)
    y = np.where(t < snug, target * 0.12 * t / snug,
                 target * (0.12 + 0.88 * np.clip((t - snug) / (0.85 - snug), 0, 1)))
    y[t > 0.9] = y[t > 0.9] * np.clip((1 - t[t > 0.9]) / 0.1, 0, 1)

    if fault == "STRIPPED":
        k = t > rng.uniform(0.62, 0.72)
        y[k] = y[k] * rng.uniform(0.3, 0.5)
    elif fault == "CROSS_THREAD":
        y = np.where(t < 0.25, target * 0.65 * t / 0.25, y)
    elif fault == "NOT_SEATED":
        y *= rng.uniform(0.45, 0.7)
    return y


def _air(rng, s, fault=None):
    """Áp lực khí nén: ổn định ở mức nền, tụt khi van mở cho xi-lanh chạy, rồi hồi lại."""
    n = int(rng.integers(180, 240))
    t = np.linspace(0, 1, n)
    base = s["peak"]
    dip_depth = rng.uniform(0.65, 0.85)
    dip = dip_depth * np.exp(-((t - 0.35) / 0.08) ** 2)
    rec = 0.35 * dip_depth * np.exp(-((t - 0.5) / 0.12) ** 2)
    y = base - dip - rec

    if fault == "LEAK":
        y = base - 2.2 * dip - 3.5 * rec
    elif fault == "LOW_SUPPLY":
        y = y - rng.uniform(1.1, 1.6)
    elif fault == "VALVE_STICK":
        steps = np.floor(t * rng.uniform(9, 14)) % 2
        y = y - 0.45 * steps * np.exp(-((t - 0.45) / 0.25) ** 2)
    return y


GEN = {"PRESS_FORCE": _press, "TORQUE": _torque, "AIR_PRESSURE": _air}
NOMINAL = {"PRESS_FORCE": 12.0, "TORQUE": 25.0, "AIR_PRESSURE": 6.0}


def make_session(proc, n_cycles, seed, fault=None):
    """Một phiên = một ca làm việc trên một máy: cùng cảm biến, cùng khuôn, cùng điều kiện.

    Tham số ca (độ lệch chuẩn cảm biến, biên độ, mức nhiễu) cố định trong ca nhưng
    khác nhau giữa các ca — để việc tách tập theo phiên có ý nghĩa.
    """
    rng = np.random.default_rng(seed)
    s = {
        "peak": NOMINAL[proc] * rng.uniform(0.94, 1.06),
        "noise": NOMINAL[proc] * rng.uniform(0.006, 0.016),
        "drift": NOMINAL[proc] * rng.uniform(-0.02, 0.02),
    }
    out = []
    for _ in range(n_cycles):
        y = GEN[proc](rng, s, fault)
        y = y + s["drift"] + rng.normal(0, s["noise"], len(y))
        # nhiễu điện 50 Hz lẫn vào đường tín hiệu analog
        y = y + s["noise"] * 0.6 * np.sin(np.arange(len(y)) * 2 * np.pi * 50 / FS * rng.uniform(0.97, 1.03))
        out.append(y)
    return out


# ═══════════════════════ Đặc trưng mỗi chu kỳ ═══════════════════════
def extract(y):
    """9 đặc trưng mô tả hình dạng một chu kỳ.

    Giữ đơn giản và dễ giải thích: kỹ sư nhìn vào là hiểu từng số nghĩa là gì.
    Thứ tự PHẢI trùng với FEATURES và với bản TypeScript trên dashboard.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    d = np.diff(y)
    peak, trough = float(y.max()), float(y.min())
    rng_ = (peak - trough) or 1.0
    t_peak = float(np.argmax(y)) / n
    mean_level = float(y.mean())
    rise_slope = float(d.max()) * FS
    roughness = float(np.mean(np.abs(np.diff(d)))) * FS

    # đếm số đỉnh cục bộ đáng kể: cao hơn 60% biên độ và cách nhau đủ xa
    thr = trough + 0.6 * rng_
    peaks, last = 0, -999
    for i in range(1, n - 1):
        if y[i] > thr and y[i] >= y[i - 1] and y[i] >= y[i + 1] and i - last > n * 0.15:
            peaks += 1
            last = i
    # mức trung bình theo đoạn: đầu (0–30%) và giữa (30–60%) chu kỳ.
    # Kỹ sư quá trình vẫn xét đường cong theo từng đoạn — ví dụ ren chéo khác biệt
    # ngay đoạn đầu, rò khí khác biệt ở đoạn giữa khi van mở.
    a, b = int(n * 0.3), int(n * 0.6)
    early_level = float(y[:a].mean())
    mid_level = float(y[a:b].mean())
    return np.array([peak, trough, t_peak, mean_level, rise_slope, roughness, peaks,
                     early_level, mid_level], dtype=float)


# ═══════════════════════ Bộ phát hiện Mahalanobis ═══════════════════════
class Mahalanobis:
    """Khoảng cách từ một chu kỳ tới 'đám mây' chu kỳ bình thường.

    Chọn phương pháp này cho dashboard vì: chỉ cần vector trung bình và một ma trận
    7×7 là tính được — chạy thẳng trong trình duyệt và trên vi điều khiển, kết quả
    trùng khớp tuyệt đối với bản Python. Ước lượng hiệp phương sai bằng Ledoit-Wolf
    để ổn định khi số mẫu ít.
    """

    def fit(self, X):
        self.mu = X.mean(axis=0)
        cov = LedoitWolf().fit(X).covariance_
        self.inv = np.linalg.inv(cov)
        return self

    def score(self, X):
        D = X - self.mu
        return np.sqrt(np.einsum("ij,jk,ik->i", D, self.inv, D))


def main():
    print("=" * 64)
    print("CHU KỲ GIA CÔNG — huấn luyện & đánh giá phát hiện bất thường")
    print("=" * 64)

    export = {"sample_rate_hz": FS, "features": FEATURES, "processes": {}}
    summary = []

    for p_i, proc in enumerate(PROCESSES):
        base = 10_000 * (p_i + 1)

        # ── Tách theo phiên: ca huấn luyện / ca hiệu chuẩn / ca kiểm tra, không trùng ca ──
        train = [c for s in range(20) for c in make_session(proc, 25, base + s)]
        calib = [c for s in range(20, 26) for c in make_session(proc, 25, base + s)]
        test_ok = [c for s in range(26, 32) for c in make_session(proc, 25, base + s)]

        Xtr = np.vstack([extract(c) for c in train])
        Xca = np.vstack([extract(c) for c in calib])
        Xok = np.vstack([extract(c) for c in test_ok])

        # ── Mô hình chính: Mahalanobis, học CHỈ trên chu kỳ bình thường ──
        mh = Mahalanobis().fit(Xtr)
        # ngưỡng lấy từ ca hiệu chuẩn (chưa dùng để fit, cũng không phải tập kiểm tra)
        thr = float(np.percentile(mh.score(Xca), 99.5))

        # ── Đối chứng: Isolation Forest, cùng dữ liệu ──
        iso = IsolationForest(n_estimators=200, contamination="auto", random_state=0).fit(Xtr)
        iso_thr = float(np.percentile(iso.score_samples(Xca), 0.5))

        fa_mh = float((mh.score(Xok) > thr).mean())
        fa_iso = float((iso.score_samples(Xok) < iso_thr).mean())

        faults_out, fault_cycles = [], {}
        for f_i, (fcode, fdesc) in enumerate(FAULTS[proc].items()):
            fc = [c for s in range(3) for c in make_session(proc, 20, base + 500 + 10 * f_i + s, fcode)]
            Xf = np.vstack([extract(c) for c in fc])
            det_mh = float((mh.score(Xf) > thr).mean())
            det_iso = float((iso.score_samples(Xf) < iso_thr).mean())
            faults_out.append({"code": fcode, "vi": fdesc,
                               "detect_mahalanobis": round(det_mh, 4),
                               "detect_isoforest": round(det_iso, 4),
                               "n": len(fc)})
            fault_cycles[fcode] = fc[:8]

        # ── Bộ chu kỳ mẫu cho dashboard phát lại — lấy từ TẬP KIỂM TRA ──
        def pack(c):
            f = extract(c)
            step = max(1, len(c) // 110)
            return {"y": [round(float(v), 3) for v in c[::step]], "f": [round(float(v), 5) for v in f]}

        export["processes"][proc] = {
            "vi": PROCESSES[proc]["vi"],
            "unit": PROCESSES[proc]["unit"],
            "nominal": NOMINAL[proc],
            "model": {
                "type": "mahalanobis",
                "mu": [round(float(v), 6) for v in mh.mu],
                # độ lệch chuẩn từng đặc trưng — để dashboard chỉ ra đặc trưng nào lệch nhiều nhất
                "std": [round(float(v), 6) for v in Xtr.std(axis=0)],
                "inv_cov": [[round(float(v), 8) for v in row] for row in mh.inv],
                "threshold": round(thr, 4),
            },
            "metrics": {
                "n_train": len(train), "n_calib": len(calib), "n_test_normal": len(test_ok),
                "false_alarm_mahalanobis": round(fa_mh, 4),
                "false_alarm_isoforest": round(fa_iso, 4),
                "faults": faults_out,
            },
            "samples": {
                "normal": [pack(c) for c in test_ok[:24]],
                "faults": {k: [pack(c) for c in v] for k, v in fault_cycles.items()},
            },
        }

        print(f"\n[{PROCESSES[proc]['vi']}]  train {len(train)} · calib {len(calib)} · test {len(test_ok)} chu kỳ bình thường")
        print(f"  {'Dạng lỗi':<16}{'Mahalanobis':>13}{'IsoForest':>11}")
        for fo in faults_out:
            print(f"  {fo['code']:<16}{fo['detect_mahalanobis']*100:>12.0f}%{fo['detect_isoforest']*100:>10.0f}%")
        print(f"  {'báo động giả':<16}{fa_mh*100:>12.1f}%{fa_iso*100:>10.1f}%")
        summary.append((proc, fa_mh, np.mean([f['detect_mahalanobis'] for f in faults_out])))

    export["policy"] = {
        "split": "Tách theo ca làm việc: 20 ca huấn luyện, 6 ca hiệu chuẩn ngưỡng, 6 ca kiểm tra — không ca nào dùng chung",
        "training": "Chỉ học trên chu kỳ bình thường — nhà máy có rất ít dữ liệu lỗi",
        "threshold": "Phân vị 99.5 khoảng cách trên ca hiệu chuẩn, không nhìn tập kiểm tra",
        "caveat": "Dữ liệu mô phỏng. Khi có PLC thật, xuất CSV rồi chạy lại script này.",
    }

    with open("cycles.json", "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, separators=(",", ":"))

    print("\n" + "=" * 64)
    for proc, fa, det in summary:
        print(f"  {PROCESSES[proc]['vi']:<16} bắt lỗi TB {det*100:5.1f}%   báo động giả {fa*100:4.1f}%")
    print("Đã lưu cycles.json")


if __name__ == "__main__":
    main()
