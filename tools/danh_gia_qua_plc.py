"""
danh_gia_qua_plc.py — Chấm độ chính xác của AI SAU KHI dữ liệu đi qua PLC + gateway.

So file phát lại (có nhãn đúng) với file log của cầu nối (điểm AI tính trên dữ liệu đọc từ PLC),
ghép theo cột tag (= D102).

    python tools/danh_gia_qua_plc.py ml/data/pyscrew_s03_replay.csv log_qua_plc.csv

In ra:
  - Số chu kỳ đã phát / đã nhận (chu kỳ thiếu = mất dữ liệu trên đường truyền)
  - Báo nhầm, bắt được lỗi, theo từng nhóm — tính bằng ngưỡng trong mô hình
  - Độ khớp: điểm qua PLC so với điểm offline của cùng chu kỳ — khớp nghĩa là
    chuỗi thu thập không làm méo dữ liệu
"""
import argparse
import csv
import json

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay_csv")
    ap.add_argument("bridge_log_csv", help="file do plc_to_mqtt.py --log-csv ghi khi phát lại")
    ap.add_argument("--model", help="file mô hình để lấy ngưỡng, vd. ml/models/pyscrew_s03.json")
    ap.add_argument("--out", help="ghi kết quả ra file markdown")
    a = ap.parse_args()

    truth = {}
    with open(a.replay_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            truth[int(r["tag"])] = r
    got = {}
    with open(a.bridge_log_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("tag") and r.get("score"):
                got[int(r["tag"])] = float(r["score"])      # chu kỳ trùng tag: lấy lần cuối

    if a.model:
        with open(a.model, encoding="utf-8") as f:
            thr = float(json.load(f)["model"]["threshold"])
    else:
        thr = None

    # Khi phát lại có --limit N, chỉ N tag đầu được phát: bỏ các tag sau tag lớn nhất nhận được
    if got:
        last = max(t for t in got if t in truth) if any(t in truth for t in got) else 0
        truth = {t: r for t, r in truth.items() if t <= last}
    both = sorted(set(truth) & set(got))
    missing = sorted(set(truth) - set(got))
    extra = sorted(set(got) - set(truth))
    out = [f"# Độ chính xác AI khi dữ liệu đi qua PLC", "",
           f"- Chu kỳ đã phát: {len(truth)} · cầu nối nhận và chấm: {len(both)} · thiếu: {len(missing)}"]
    if extra:
        out.append(f"- Tag lạ trong log (không có trong file phát lại, bỏ qua): {len(extra)}")
    if not both:
        print("\n".join(out))
        print("Không ghép được chu kỳ nào. Kiểm tra: cầu nối có chạy với --log-csv không, D102 có được ghi không.")
        return

    off = np.array([float(truth[t]["offline_score"]) for t in both])
    chain = np.array([got[t] for t in both])
    lab = np.array([int(truth[t]["label"]) for t in both])
    cat = [truth[t]["category"] for t in both]

    rel = np.abs(chain - off) / np.maximum(off, 1e-6)
    out += [f"- Độ lệch điểm qua PLC so với offline: trung vị {np.median(rel) * 100:.1f}%, "
            f"90% chu kỳ lệch dưới {np.percentile(rel, 90) * 100:.1f}%", ""]

    if thr is not None:
        fl_c, fl_o = chain > thr, off > thr
        agree = float((fl_c == fl_o).mean())
        out += [f"Ngưỡng mô hình: {thr:.2f}", "",
                "| Nhóm | Số chu kỳ | Gắn cờ (qua PLC) | Gắn cờ (offline) |", "|---|---|---|---|"]
        for c in sorted(set(cat)):
            m = np.array([x == c for x in cat])
            out.append(f"| {c} | {m.sum()} | {fl_c[m].mean() * 100:.1f}% | {fl_o[m].mean() * 100:.1f}% |")
        tp = int((fl_c & (lab == 1)).sum()); fn = int((~fl_c & (lab == 1)).sum())
        fp = int((fl_c & (lab == 0)).sum()); tn = int((~fl_c & (lab == 0)).sum())
        out += ["", "Ma trận nhầm lẫn (qua PLC):", "",
                "| | AI báo bất thường | AI báo bình thường |", "|---|---|---|",
                f"| Thật sự lỗi | {tp} | {fn} |", f"| Thật sự bình thường | {fp} | {tn} |", "",
                f"Kết luận qua PLC và offline trùng nhau ở {agree * 100:.1f}% chu kỳ."]
    else:
        out.append("(Thêm --model để có bảng gắn cờ theo ngưỡng.)")

    if missing:
        out += ["", f"Tag bị thiếu (10 cái đầu): {missing[:10]}"]
    text = "\n".join(out)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"\nĐã lưu {a.out}")


if __name__ == "__main__":
    main()
