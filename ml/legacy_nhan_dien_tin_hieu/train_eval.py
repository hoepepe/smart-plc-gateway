"""
train_eval.py — Huấn luyện mô hình và ĐÁNH GIÁ TRUNG THỰC.

Chạy:  python train_eval.py

Sinh ra:
  model.joblib   — mô hình + ngưỡng, để backend và gateway dùng
  metrics.json   — số liệu để dashboard hiển thị và để đưa vào pitch deck

Nguyên tắc ghi trong file này, đừng phá vỡ:
  1. Tập test tách theo PHIÊN, không tách ngẫu nhiên.
  2. Tập test KHÔNG được dùng để chọn siêu tham số hay chọn ngưỡng.
     Ngưỡng chọn bằng cross-validation TRÊN TẬP TRAIN.
  3. Báo cáo ma trận nhầm lẫn đầy đủ, không chỉ accuracy tổng.
  4. Báo cáo cả trường hợp mô hình sai. Con số xấu vẫn phải công bố.
"""

import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import confusion_matrix, classification_report

from features import FEATURE_NAMES, FEATURE_VERSION
from signals import build_dataset, KNOWN_CLASSES, OOD_CLASS


def pick_thresholds(clf, X_train, y_train):
    """Chọn ngưỡng tin cậy và ngưỡng tín hiệu lạ bằng cross-validation TRÊN TẬP TRAIN.
    Không bao giờ ngó sang tập test để chọn ngưỡng — đó là rò rỉ dữ liệu."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    proba = cross_val_predict(clf, X_train, y_train, cv=cv, method="predict_proba")
    classes = np.unique(y_train)          # cross_val_predict không fit lên clf gốc
    conf = proba.max(axis=1)
    pred = classes[proba.argmax(axis=1)]
    correct = pred == y_train

    # ngưỡng tin cậy: điểm mà dưới nó tỷ lệ sai tăng rõ rệt
    # lấy phân vị 10 của độ tin cậy khi đoán ĐÚNG
    conf_th = float(np.percentile(conf[correct], 10))
    conf_th = min(max(conf_th, 0.55), 0.90)

    # ngưỡng tín hiệu lạ: thấp hơn hẳn, dành cho trường hợp mô hình hoàn toàn phân vân
    ood_th = float(np.percentile(conf[correct], 2))
    ood_th = min(max(ood_th, 0.35), conf_th - 0.10)

    return round(conf_th, 3), round(ood_th, 3)


def main():
    print("=" * 62)
    print("SMART PLC GATEWAY — huấn luyện & đánh giá")
    print("=" * 62)

    d = build_dataset()
    Xtr, ytr, Xte, yte, Xood = (d["X_train"], d["y_train"],
                                d["X_test"], d["y_test"], d["X_ood"])

    print(f"\nĐặc trưng      : {len(FEATURE_NAMES)} (version {FEATURE_VERSION})")
    print(f"Tập train      : {Xtr.shape[0]} cửa sổ")
    print(f"Tập test       : {Xte.shape[0]} cửa sổ  (phiên thu thập KHÁC hoàn toàn)")
    print(f"Tập tín hiệu lạ: {Xood.shape[0]} cửa sổ  (lớp {OOD_CLASS}, chưa hề huấn luyện)")

    clf = RandomForestClassifier(
        n_estimators=60, max_depth=8, min_samples_leaf=3,
        random_state=42, n_jobs=-1,
    )

    conf_th, ood_th = pick_thresholds(clf, Xtr, ytr)
    print(f"\nNgưỡng chọn bằng CV trên tập train:")
    print(f"  ngưỡng tin cậy   = {conf_th}")
    print(f"  ngưỡng tín hiệu lạ = {ood_th}")

    clf.fit(Xtr, ytr)

    # ---------- Baseline để so sánh ----------
    # Đoán ngẫu nhiên đều giữa 4 lớp
    baseline_acc = 1.0 / len(KNOWN_CLASSES)

    # ---------- Đánh giá trên tập test giữ riêng ----------
    proba = clf.predict_proba(Xte)
    conf = proba.max(axis=1)
    pred = np.array(clf.classes_)[proba.argmax(axis=1)]

    acc_raw = float((pred == yte).mean())

    # Khi áp ngưỡng: dưới ngưỡng thì hệ thống KHÔNG trả lời (chuyển cho kỹ sư)
    answered = conf >= conf_th
    acc_answered = float((pred[answered] == yte[answered]).mean()) if answered.any() else 0.0
    coverage = float(answered.mean())

    print("\n" + "-" * 62)
    print("KẾT QUẢ TRÊN TẬP TEST GIỮ RIÊNG")
    print("-" * 62)
    print(f"Baseline (đoán ngẫu nhiên)       : {baseline_acc*100:.1f}%")
    print(f"Độ chính xác, không áp ngưỡng    : {acc_raw*100:.1f}%")
    print(f"Độ chính xác, khi hệ thống trả lời: {acc_answered*100:.1f}%")
    print(f"Tỷ lệ tự trả lời được (coverage) : {coverage*100:.1f}%")
    print(f"  -> {(1-coverage)*100:.1f}% còn lại hệ thống chuyển cho kỹ sư xác nhận")

    print("\nMa trận nhầm lẫn (hàng = thực tế, cột = mô hình đoán):")
    labels = sorted(KNOWN_CLASSES)
    cm = confusion_matrix(yte, pred, labels=labels)
    w = max(len(l) for l in labels) + 2
    print(" " * w + "".join(f"{l[:8]:>10}" for l in labels))
    for i, l in enumerate(labels):
        print(f"{l:<{w}}" + "".join(f"{cm[i][j]:>10}" for j in range(len(labels))))

    print("\nBáo cáo chi tiết theo lớp:")
    print(classification_report(yte, pred, labels=labels, digits=3, zero_division=0))

    # ---------- Kiểm tra phát hiện tín hiệu lạ ----------
    # Ngưỡng tin cậy MỘT MÌNH không đủ: Random Forest vẫn có thể rất "tự tin"
    # khi gặp tín hiệu hoàn toàn lạ, vì nó buộc phải chọn 1 trong 4 lớp đã biết.
    # Vì vậy dùng thêm một mô hình one-class học riêng vùng dữ liệu đã thấy.
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    # Ngưỡng phải được hiệu chuẩn trên phần dữ liệu mà Isolation Forest CHƯA thấy,
    # nếu không nó sẽ quá chặt và báo động giả tràn lan khi gặp phiên thu thập mới.
    # Chia tập train làm hai: một nửa để fit, một nửa để hiệu chuẩn ngưỡng.
    from sklearn.model_selection import train_test_split
    X_fit, X_calib = train_test_split(Xtr, test_size=0.35, random_state=7, shuffle=True)

    scaler = StandardScaler().fit(X_fit)
    iso = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
    iso.fit(scaler.transform(X_fit))

    # điểm càng âm càng bất thường.
    # Lấy phân vị 1 trên phần hiệu chuẩn, trừ thêm biên an toàn bằng độ lệch chuẩn
    # để hấp thụ khác biệt giữa các phiên thu thập.
    s_calib = iso.score_samples(scaler.transform(X_calib))
    iso_th = float(np.percentile(s_calib, 1) - 1.5 * np.std(s_calib))

    s_test = iso.score_samples(scaler.transform(Xte))
    s_ood = iso.score_samples(scaler.transform(Xood))

    # Phân biệt rõ hai tình huống, đây là điểm thiết kế quan trọng:
    #
    #   độ tin cậy thấp  -> mô hình phân vân GIỮA CÁC LỚP ĐÃ BIẾT  -> "pending", hỏi kỹ sư
    #   one-class gắn cờ -> tín hiệu KHÔNG GIỐNG BẤT KỲ LỚP NÀO    -> "unknown", tín hiệu lạ
    #
    # Trộn hai thứ này lại (kiểu "conf thấp thì coi là lạ") làm báo động giả tăng vọt,
    # vì tín hiệu bình thường nhưng nhiễu cũng bị gắn cờ lạ.
    # Độ tin cậy chỉ dùng như tín hiệu phụ, và chỉ khi thấp bất thường.
    CONF_FLOOR = 0.30

    ood_flagged = float(((s_ood < iso_th) | (clf.predict_proba(Xood).max(axis=1) < CONF_FLOOR)).mean())
    false_alarm = float(((s_test < iso_th) | (conf < CONF_FLOOR)).mean())

    print("-" * 62)
    print("PHÁT HIỆN TÍN HIỆU LẠ  (one-class + ngưỡng tin cậy)")
    print("-" * 62)
    print(f"Lớp {OOD_CLASS} bị gắn cờ đúng : {ood_flagged*100:.1f}%")
    print(f"Báo động giả trên lớp đã học    : {false_alarm*100:.1f}%")
    if ood_flagged < 0.5:
        print("  ! Cơ chế phát hiện tín hiệu lạ còn yếu — cần thêm đặc trưng")
        print("    hoặc thu thập thêm dạng tín hiệu đa dạng hơn cho tập train.")

    # ---------- Đặc trưng nào quan trọng ----------
    imp = sorted(zip(FEATURE_NAMES, clf.feature_importances_),
                 key=lambda x: -x[1])[:6]
    print("\n6 đặc trưng đóng góp nhiều nhất:")
    for name, v in imp:
        print(f"  {name:<16} {v:.4f}  {'#' * int(v * 90)}")

    # ---------- Xuất ----------
    metrics = {
        "feature_version": FEATURE_VERSION,
        "n_features": len(FEATURE_NAMES),
        "classes": labels,
        "ood_class": OOD_CLASS,
        "n_train": int(Xtr.shape[0]),
        "n_test": int(Xte.shape[0]),
        "n_ood": int(Xood.shape[0]),
        "conf_threshold": conf_th,
        "ood_threshold": ood_th,
        "iso_threshold": round(iso_th, 4),
        "conf_floor": 0.30,
        "baseline_accuracy": round(baseline_acc, 4),
        "accuracy_raw": round(acc_raw, 4),
        "accuracy_when_answered": round(acc_answered, 4),
        "coverage": round(coverage, 4),
        "ood_detection_rate": round(ood_flagged, 4),
        "false_alarm_rate": round(false_alarm, 4),
        "confusion_matrix": {"labels": labels, "matrix": cm.tolist()},
        "feature_importance": {k: round(float(v), 5) for k, v in
                               zip(FEATURE_NAMES, clf.feature_importances_)},
        "split_policy": "tách theo phiên thu thập, không tách ngẫu nhiên theo cửa sổ",
        "threshold_policy": "ngưỡng chọn bằng cross-validation trên tập train, không dùng tập test",
    }

    with open("metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    try:
        import joblib
        joblib.dump({"clf": clf, "scaler": scaler, "iso": iso,
                     "conf_th": conf_th, "ood_th": ood_th, "iso_th": iso_th,
                     "feature_version": FEATURE_VERSION}, "model.joblib")
        print("\nĐã lưu: model.joblib, metrics.json")
    except Exception as e:
        print(f"\nĐã lưu metrics.json (không lưu được model: {e})")

    print("\n" + "=" * 62)
    print("CÂU DÙNG CHO PITCH DECK (số đo thật, không làm tròn đẹp):")
    print(f'  "Trên {Xte.shape[0]} cửa sổ tín hiệu từ các phiên thu thập hoàn toàn mới,')
    print(f'   hệ thống tự nhận diện đúng {acc_answered*100:.1f}% số trường hợp nó tự trả lời,')
    print(f'   bao phủ {coverage*100:.1f}% số kênh; phần còn lại chuyển kỹ sư xác nhận.')
    print(f'   Baseline đoán ngẫu nhiên là {baseline_acc*100:.0f}%."')
    print("=" * 62)


if __name__ == "__main__":
    main()
