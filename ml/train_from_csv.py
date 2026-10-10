"""
train_from_csv.py — Huấn luyện lại bộ phát hiện bất thường trên chu kỳ THẬT từ PLC.

Dùng sau khi đã ghi được một số chu kỳ bằng tools/plc_to_mqtt.py --log-csv:

    python tools/plc_to_mqtt.py --plc 192.168.1.39 --plc-port 5000 --log-csv cycles_M01.csv
    (để chạy một lúc, càng nhiều chu kỳ BÌNH THƯỜNG càng tốt — ít nhất khoảng 60-100)
    Ctrl+C để dừng, rồi:
    python ml/train_from_csv.py cycles_M01.csv --process PRESS_FORCE --machine M01

CHỈ dùng chu kỳ bình thường để huấn luyện — đúng nguyên tắc trong cycles.py.
Nếu trong lúc ghi có bật bit lỗi (M100/M101) để demo, dùng --skip để bỏ các chu kỳ đó
(xem thời điểm trong log của plc_to_mqtt.py và loại theo khoảng thời gian).

Script này dùng LẠI `extract()` và `Mahalanobis` từ cycles.py — không viết lại thuật
toán, để mô hình học trên PLC thật đúng hệt công thức đã kiểm chứng trên dữ liệu mô phỏng.

Kết quả: cập nhật đúng một mục trong cycles.json (theo --process), giữ nguyên mọi
mục khác — nên dashboard vẫn hiển thị được các quá trình chưa có dữ liệu thật.
"""

import argparse
import csv
import json
import os

import numpy as np

from cycles import FEATURES, Mahalanobis, extract


def load_csv(path, min_samples=8):
    """Đọc file do plc_to_mqtt.py --log-csv ghi ra. Trả về list các mảng chu kỳ."""
    cycles = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vals = [float(v) for v in row["y"].split(";") if v]
            if len(vals) >= min_samples:
                cycles.append((int(row["ts"]), np.array(vals)))
    return cycles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", help="file do plc_to_mqtt.py --log-csv ghi ra")
    ap.add_argument("--process", required=True, choices=["PRESS_FORCE", "TORQUE", "AIR_PRESSURE"])
    ap.add_argument("--machine", default="M01", help="chỉ để in ra, không ảnh hưởng mô hình")
    ap.add_argument("--calib-frac", type=float, default=0.3,
                     help="tỷ lệ chu kỳ dùng để hiệu chuẩn ngưỡng (không dùng để fit)")
    ap.add_argument("--percentile", type=float, default=99.5,
                     help="phân vị khoảng cách trên tập hiệu chuẩn, dùng làm ngưỡng")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "cycles.json"))
    a = ap.parse_args()

    cycles = load_csv(a.csv_path)
    n = len(cycles)
    print(f"Đọc được {n} chu kỳ từ {a.csv_path} (máy {a.machine})")
    if n < 20:
        print("! Dưới 20 chu kỳ — ngưỡng sẽ không ổn định. Ghi thêm dữ liệu trước khi train thật.")
        if n < 5:
            return

    # Tách theo THỨ TỰ THỜI GIAN, không xáo trộn — mô phỏng đúng tình huống triển khai:
    # hiệu chuẩn trên các chu kỳ xảy ra SAU phần dùng để fit, không nhìn ngược từ tương lai.
    cycles.sort(key=lambda c: c[0])
    n_calib = max(5, int(n * a.calib_frac))
    n_fit = n - n_calib
    if n_fit < 10:
        n_fit, n_calib = max(5, n - 5), min(5, n - 5)
    fit_cycles = cycles[:n_fit]
    calib_cycles = cycles[n_fit:n_fit + n_calib]
    print(f"  Fit mô hình trên {len(fit_cycles)} chu kỳ đầu, hiệu chuẩn ngưỡng trên {len(calib_cycles)} chu kỳ sau")

    X_fit = np.vstack([extract(y) for _, y in fit_cycles])
    X_calib = np.vstack([extract(y) for _, y in calib_cycles])

    model = Mahalanobis().fit(X_fit)
    calib_scores = model.score(X_calib)
    threshold = float(np.percentile(calib_scores, a.percentile))

    print(f"  Ngưỡng ({a.percentile} phân vị trên tập hiệu chuẩn): {threshold:.3f}")
    print(f"  Điểm trên tập hiệu chuẩn: min {calib_scores.min():.2f} · "
          f"trung vị {np.median(calib_scores):.2f} · max {calib_scores.max():.2f}")
    false_alarm = float((calib_scores > threshold).mean())
    print(f"  Báo động giả trên chính tập hiệu chuẩn: {false_alarm*100:.1f}% "
          f"(gần đúng {100 - a.percentile:.1f}% theo thiết kế của phân vị)")

    # Vài chu kỳ mẫu cho dashboard phát lại — lấy từ phần hiệu chuẩn, chưa dùng để fit
    n_sample = min(24, len(calib_cycles))
    sample_idx = np.linspace(0, len(calib_cycles) - 1, n_sample).astype(int)
    samples = [[round(float(v), 3) for v in calib_cycles[i][1]] for i in sample_idx]

    with open(a.out, encoding="utf-8") as f:
        data = json.load(f)

    proc = data["processes"][a.process]
    proc["model"] = {
        "type": "mahalanobis",
        "mu": [round(float(v), 6) for v in model.mu],
        "std": proc["model"]["std"],          # chỉ để tham khảo hiển thị, không dùng để chấm điểm
        "inv_cov": [[round(float(v), 6) for v in row] for row in model.inv],
        "threshold": round(threshold, 4),
    }
    proc["metrics"] = {
        "n_train": len(fit_cycles),
        "n_calib": len(calib_cycles),
        "n_test_normal": None,                 # chưa có tập kiểm tra riêng từ PLC thật
        "false_alarm_mahalanobis": round(false_alarm, 4),
        "false_alarm_isoforest": None,
        "faults": [],                          # cần chèn lỗi thật (M100/M101…) và đo lại mới điền được
        "source": f"PLC thật — máy {a.machine} — {a.csv_path}",
    }
    proc["samples"] = samples

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nĐã cập nhật processes.{a.process} trong {a.out}")
    print("Các quá trình khác trong cycles.json giữ nguyên.")
    print("\nLƯU Ý CHƯA LÀM: chưa đo được tỷ lệ bắt lỗi (faults rỗng) vì cần chèn lỗi thật qua "
          "bit M100/M101 trên PLC rồi ghi riêng từng loại — xem bước tiếp theo trong hướng dẫn.")


if __name__ == "__main__":
    main()
