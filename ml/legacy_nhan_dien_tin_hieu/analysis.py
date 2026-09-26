"""
analysis.py — Sinh các số liệu phân tích cho dashboard.

Chạy sau train_eval.py:
    python analysis.py

Xuất ra analysis.json gồm ba phần:

  1. feature_map    Chiếu 16 đặc trưng xuống 2 chiều bằng PCA, để dashboard vẽ
                    bản đồ không gian đặc trưng. Tín hiệu lạ nằm ngoài các đám mây.

  2. learning_curve Mô phỏng nhiều đợt triển khai liên tiếp, đo số lần kỹ sư phải
                    can thiệp mỗi đợt. Thứ tự loại tín hiệu được chọn NGẪU NHIÊN
                    và chạy lại nhiều lần với hạt giống khác nhau — nếu sắp đặt
                    thứ tự thì đường cong sẽ đẹp giả tạo.

  3. fault_detect   Kiểm tra cơ chế one-class trên 5 dạng lỗi lắp đặt/thiết bị
                    mà mô hình CHƯA hề được huấn luyện.

Mọi con số ở đây đều đo trên dữ liệu mô phỏng. Khi có dữ liệu thật, chạy lại
script này để cập nhật.
"""

import json
import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from features import extract_batch
from signals import (FAULT_CLASSES, FS, KNOWN_CLASSES, OOD_CLASS,
                     build_dataset, make_session)

CONF_FLOOR = 0.30


def fit_stack(X, y, seed=42):
    """Huấn luyện bộ đôi: phân loại + phát hiện ngoài phân phối.

    Ngưỡng one-class hiệu chuẩn trên phần dữ liệu tách riêng khỏi phần dùng để fit,
    nếu không nó quá chặt và báo động giả tràn lan khi gặp phiên thu thập mới.
    """
    clf = RandomForestClassifier(n_estimators=60, max_depth=8, min_samples_leaf=3,
                                 random_state=seed, n_jobs=-1).fit(X, y)
    X_fit, X_cal = train_test_split(X, test_size=0.35, random_state=7)
    sc = StandardScaler().fit(X_fit)
    iso = IsolationForest(n_estimators=200, contamination=0.02,
                          random_state=seed).fit(sc.transform(X_fit))
    s_cal = iso.score_samples(sc.transform(X_cal))
    iso_th = float(np.percentile(s_cal, 1) - 1.5 * np.std(s_cal))
    return clf, sc, iso, iso_th


def is_ood(clf, sc, iso, iso_th, X):
    """Lạ nếu one-class gắn cờ, hoặc mô hình phân vân bất thường."""
    s = iso.score_samples(sc.transform(X))
    conf = clf.predict_proba(X).max(axis=1)
    return (s < iso_th) | (conf < CONF_FLOOR)


# ══════════════════════ 1. BẢN ĐỒ KHÔNG GIAN ĐẶC TRƯNG ══════════════════════
def build_feature_map(d):
    """Chiếu đặc trưng xuống 2 chiều để vẽ được lên màn hình.

    PCA chỉ fit trên tập TRAIN. Tín hiệu lạ và tín hiệu lỗi được chiếu bằng
    cùng phép biến đổi đó — nếu fit cả trên chúng thì chúng sẽ bị kéo vào giữa
    và mất đúng thứ cần thấy.
    """
    Xtr, ytr = d["X_train"], d["y_train"]
    sc = StandardScaler().fit(Xtr)
    pca = PCA(n_components=2, random_state=0).fit(sc.transform(Xtr))

    def project(X):
        return pca.transform(sc.transform(X))

    pts = {c: project(Xtr[ytr == c]).round(3).tolist() for c in KNOWN_CLASSES}
    ood_pts = project(d["X_ood"]).round(3).tolist()

    faults = {}
    for name in FAULT_CLASSES:
        w = make_session(name, 10, seed=hash(name) % 9999)
        faults[name] = project(extract_batch(w, FS)).round(3).tolist()

    var = pca.explained_variance_ratio_
    return {
        "classes": {c: pts[c] for c in KNOWN_CLASSES},
        "ood": ood_pts,
        "faults": faults,
        "explained_variance": [round(float(v), 4) for v in var],
        "explained_total": round(float(var.sum()), 4),
        "note": ("PCA fit trên tập huấn luyện. Tín hiệu lạ và lỗi được chiếu bằng "
                 "cùng phép biến đổi, không tham gia vào việc fit."),
    }


# ══════════════════════ 2. ĐƯỜNG CONG HỌC ══════════════════════
def simulate_learning_curve(n_rounds=5, machines_per_round=4, n_seeds=20):
    """Đo số lần kỹ sư phải can thiệp qua từng đợt triển khai.

    Quy tắc mô phỏng, giữ cho trung thực:
      - Mỗi máy mang một loại tín hiệu chọn NGẪU NHIÊN từ danh mục nhà máy
      - Bắt đầu với mô hình chỉ biết 2 loại (nhà máy vừa mua thiết bị)
      - Gặp loại chưa biết -> kỹ sư gán nhãn 1 lần -> loại đó vào tập huấn luyện
      - Chạy lại n_seeds lần với hạt giống khác nhau rồi lấy trung bình

    Không sắp đặt thứ tự loại tín hiệu. Nếu sắp đặt, đường cong chắc chắn đi
    xuống nhưng đó là do người làm, không phải do hệ thống học được.
    """
    catalogue = KNOWN_CLASSES + [OOD_CLASS]        # 5 loại tín hiệu trong nhà máy
    curves = []

    for seed in range(n_seeds):
        rng = np.random.default_rng(1000 + seed)
        known = set(rng.choice(catalogue, size=2, replace=False))
        per_round = []
        for _ in range(n_rounds):
            interventions = 0
            for _ in range(machines_per_round):
                kind = str(rng.choice(catalogue))
                if kind not in known:
                    interventions += 1      # kỹ sư phải gán nhãn lần đầu
                    known.add(kind)         # hệ thống nhớ, lần sau tự nhận
            per_round.append(interventions)
        curves.append(per_round)

    arr = np.array(curves, dtype=float)
    mean = arr.mean(axis=0)
    total_machines = n_rounds * machines_per_round

    return {
        "rounds": list(range(1, n_rounds + 1)),
        "machines_per_round": machines_per_round,
        "interventions_mean": [round(float(v), 2) for v in mean],
        "interventions_std": [round(float(v), 2) for v in arr.std(axis=0)],
        "rate_mean": [round(float(v / machines_per_round), 3) for v in mean],
        "n_seeds": n_seeds,
        "n_signal_types": len(catalogue),
        "total_machines": total_machines,
        "total_interventions_mean": round(float(arr.sum(axis=1).mean()), 2),
        "baseline_interventions": total_machines,   # cách thủ công: mỗi máy một lần
        "assumptions": [
            f"Nhà máy có {len(catalogue)} loại tín hiệu khác nhau",
            f"Mỗi đợt triển khai {machines_per_round} máy, loại tín hiệu chọn ngẫu nhiên",
            "Mô hình ban đầu chỉ biết 2 trong số các loại đó",
            f"Trung bình của {n_seeds} lần chạy với hạt giống ngẫu nhiên khác nhau",
        ],
        "caveat": ("Đây là MÔ PHỎNG cơ chế, không phải số đo từ triển khai thật. "
                   "Con số thật chỉ có được sau khi lắp nhiều máy trong nhà máy."),
    }


# ══════════════════════ 3. PHÁT HIỆN LỖI LẮP ĐẶT ══════════════════════
# Dải hợp lệ của tín hiệu sau mạch hạ áp, dùng cho luật kiểm tra cứng.
VALID_MIN, VALID_MAX = 0.0, 120.0


def check_wiring(window):
    """Luật cứng, không dùng mô hình: tín hiệu ra ngoài dải hợp lệ là lỗi đấu nối.

    Cần luật này vì features.py chuẩn hóa biên độ, nên mô hình mù trước
    lỗi đấu ngược cực — dạng sóng lật quanh trung bình giữ nguyên mọi
    đặc trưng thống kê.
    """
    x = np.asarray(window)
    return (np.mean(x < VALID_MIN) > 0.05) or (np.mean(x > VALID_MAX) > 0.05)


def evaluate_fault_detection(d, n_windows=30):
    """Kiểm tra hai lớp bảo vệ trên các dạng lỗi mà mô hình chưa hề học:
    luật kiểm tra dải tuyệt đối, và mô hình one-class."""
    clf, sc, iso, iso_th = fit_stack(d["X_train"], d["y_train"])

    results = []
    for name, desc in FAULT_CLASSES.items():
        w = make_session(name, n_windows, seed=hash(name) % 9999)
        X = extract_batch(w, FS)
        by_model = is_ood(clf, sc, iso, iso_th, X)
        by_rule = np.array([check_wiring(win) for win in w])
        combined = by_model | by_rule
        results.append({
            "code": name, "description": desc,
            "detection_rate": round(float(combined.mean()), 4),
            "by_model": round(float(by_model.mean()), 4),
            "by_rule": round(float(by_rule.mean()), 4),
            "n_windows": n_windows,
        })

    # đối chứng: tín hiệu bình thường bị gắn cờ nhầm bao nhiêu
    fa = float(is_ood(clf, sc, iso, iso_th, d["X_test"]).mean())
    ood = float(is_ood(clf, sc, iso, iso_th, d["X_ood"]).mean())

    return {
        "faults": sorted(results, key=lambda r: -r["detection_rate"]),
        "ood_class": {"code": OOD_CLASS, "detection_rate": round(ood, 4)},
        "false_alarm_on_normal": round(fa, 4),
        "mean_detection": round(float(np.mean([r["detection_rate"] for r in results])), 4),
        "two_layer_note": ("Hai lớp bảo vệ bổ sung cho nhau: luật kiểm tra dải tuyệt đối "
                           "bắt lỗi đấu nối vật lý, mô hình one-class bắt dạng sóng lạ. "
                           "Không lớp nào thay được lớp kia."),
        "known_limitation": {
            "code": "REVERSED_POLARITY",
            "why": ("Đảo cực làm dạng sóng lật quanh giá trị trung bình, nhưng hầu hết "
                    "đặc trưng thống kê giữ nguyên: độ lệch chuẩn, tần suất cắt mức, "
                    "tốc độ biến thiên đều không đổi. Thêm nữa, features.py chuẩn hóa "
                    "biên độ nên thông tin về mức điện áp tuyệt đối bị loại bỏ."),
            "fix": ("ĐÃ CÀI: luật kiểm tra dải tuyệt đối chạy ngay tại gateway, trước mô hình. "
                    "Nếu tín hiệu analog xuống dưới 0V hoặc vượt dải đo thì báo lỗi đấu nối. "
                    "Luật này rẻ, chắc chắn, và bắt đúng thứ mô hình không bắt được."),
        },
    }


# ══════════════════════ 4. SUY GIẢM CẢM BIẾN ══════════════════════
def simulate_degradation(d, months=12):
    """Mô phỏng cảm biến xuống cấp dần theo thời gian.

    Mỗi 'tháng' tín hiệu nhiễu thêm một chút và lệch chuẩn dần. Đo điểm one-class
    để xem khi nào hệ thống phát hiện được bất thường — cùng mô hình dùng lúc
    lắp đặt, không cần thuật toán mới.
    """
    clf, sc, iso, iso_th = fit_stack(d["X_train"], d["y_train"])
    series, first_alert = [], None

    # Cảm biến xuống cấp theo ba cách, mô phỏng cả ba:
    #   - tỷ lệ tín hiệu trên nhiễu giảm dần (nhiễu tăng so với biên độ tín hiệu)
    #   - xuất hiện hiện tượng kẹt: giá trị đứng im vài mẫu rồi nhảy
    #   - thỉnh thoảng mất mẫu
    #
    # Lưu ý: features.py chuẩn hóa biên độ nên lệch chuẩn (bias) đơn thuần sẽ
    # KHÔNG bị phát hiện. Đây là đánh đổi có chủ đích — chuẩn hóa giúp mô hình
    # chuyển được từ cảm biến demo sang tín hiệu PLC thật, nhưng làm hệ thống
    # mù trước hiện tượng trôi chuẩn. Cần một luật kiểm tra dải tuyệt đối riêng.
    for m in range(months + 1):
        rng = np.random.default_rng(500 + m)
        w = make_session("TEMPERATURE", 12, seed=2000 + m)
        out = []
        for x in w:
            amp = float(np.ptp(x)) or 1.0
            snr_noise = amp * (0.02 + 0.035 * m)      # nhiễu tăng theo tỷ lệ biên độ
            y = x + rng.normal(0, snr_noise, len(x))
            # hiện tượng kẹt: số đoạn tăng dần theo tuổi cảm biến
            for _ in range(int(m * 0.8)):
                i = int(rng.integers(1, len(y)))
                k = int(rng.integers(3, 10))
                y[i:i + k] = y[i - 1]
            out.append(y)
        w = out

        X = extract_batch(w, FS)
        score = float(iso.score_samples(sc.transform(X)).mean())
        flagged = float(is_ood(clf, sc, iso, iso_th, X).mean())
        if first_alert is None and flagged >= 0.5:
            first_alert = m
        series.append({"month": m, "iso_score": round(score, 4),
                       "flag_rate": round(flagged, 3)})

    return {
        "series": series,
        "threshold": round(iso_th, 4),
        "first_alert_month": first_alert,
        "note": ("Cùng mô hình one-class dùng để nhận diện tín hiệu lúc lắp đặt, "
                 "được dùng lại để phát hiện cảm biến suy giảm trong vận hành."),
    }


def main():
    print("=" * 62)
    print("PHÂN TÍCH BỔ SUNG — Smart PLC Gateway")
    print("=" * 62)

    d = build_dataset()

    print("\n[1/4] Bản đồ không gian đặc trưng (PCA)")
    fmap = build_feature_map(d)
    print(f"      2 thành phần chính giải thích {fmap['explained_total']*100:.1f}% phương sai")

    print("\n[2/4] Đường cong học")
    lc = simulate_learning_curve()
    print(f"      Can thiệp trung bình mỗi đợt: "
          f"{' → '.join(str(v) for v in lc['interventions_mean'])}")
    print(f"      Tổng {lc['total_interventions_mean']} lần cho {lc['total_machines']} máy "
          f"(cách thủ công: {lc['baseline_interventions']} lần)")

    print("\n[3/4] Phát hiện lỗi lắp đặt")
    fd = evaluate_fault_detection(d)
    for r in fd["faults"]:
        print(f"      {r['code']:<20} {r['detection_rate']*100:>6.1f}%")
    print(f"      {'(báo động giả trên tín hiệu bình thường)':<20} "
          f"{fd['false_alarm_on_normal']*100:>6.1f}%")

    print("\n[4/4] Suy giảm cảm biến")
    dg = simulate_degradation(d)
    fa = dg["first_alert_month"]
    print(f"      Phát hiện bất thường từ tháng thứ {fa}" if fa is not None
          else "      Chưa phát hiện trong khoảng mô phỏng")

    out = {"feature_map": fmap, "learning_curve": lc,
           "fault_detection": fd, "degradation": dg}
    with open("analysis.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\nĐã lưu analysis.json")
    print("=" * 62)


if __name__ == "__main__":
    main()
