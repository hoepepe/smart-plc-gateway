"""
benchmark_bosch_cnc.py — Kiểm chứng bộ phát hiện bất thường trên dữ liệu MÁY PHAY CNC TRONG NHÀ MÁY THẬT (Bosch).

Nguồn: Bosch Research / TU München — Tnani, Feil, Diepold, "Smart Data Collection System for Brownfield
CNC Milling Machines: A New Benchmark Dataset for Data-Driven Machine Monitoring", Procedia CIRP 107 (2022).
    Dữ liệu: https://github.com/boschresearch/CNC_Machining   (dữ liệu CC BY 4.0, mã BSD-3-Clause)
    3 máy phay (M01–M03), 15 nguyên công (OP00–OP14), rung 3 trục 2 kHz, mỗi file = MỘT LẦN CHẠY nguyên công,
    gán nhãn good / bad (lỗi sản xuất thật: gãy dao, kẹp dao sai, kẹt phoi…), thu từ 10/2018 đến 08/2021.

Vì sao bộ này: là dữ liệu dây chuyền sản xuất THẬT, có cấu trúc chu kỳ, nhiều máy cùng loại — đúng tình huống
"mỗi máy, mỗi nguyên công một chuẩn bình thường riêng" của nhà máy DENSO.

Hai bộ đặc trưng:
  A. "Qua gateway": độ rung tổng hợp → RMS mỗi 10 ms → chuỗi 100 Hz (như một module cảm biến rung xuất RMS
     vào thanh ghi PLC), rồi 9 đặc trưng của ml/cycles.py — đúng thứ gateway xử lý.
  B. "Đầy đủ": RMS và độ nhọn từng trục, năng lượng theo dải tần, thời lượng — dùng toàn bộ tín hiệu 2 kHz.

Cách đánh giá (không rò rỉ nhãn):
  - Mỗi (máy, nguyên công) một mô hình, train CHỈ trên lần chạy good, sắp theo thời gian:
    60% sớm nhất để train, phần còn lại (muộn hơn) để kiểm tra báo nhầm. Mọi lần chạy bad chỉ dùng để kiểm tra.
  - Mỗi nguyên công chỉ có 13–54 lần chạy good, quá ít để đặt ngưỡng riêng. Nên: chấm điểm leave-one-out trên
    tập train của từng nguyên công, chuẩn hoá theo trung vị của chính nguyên công đó, rồi gộp lại để chọn MỘT
    ngưỡng chung (phân vị 99). Mô hình vẫn riêng từng nguyên công; chỉ thang ngưỡng là chung.
  - Hai thí nghiệm phụ: (1) gộp mọi nguyên công của một máy vào một mô hình; (2) dùng mô hình của máy này
    chấm máy khác cùng nguyên công — để chứng minh vì sao KHÔNG được gộp.

Chạy:
    git clone --depth 1 https://github.com/boschresearch/CNC_Machining.git      (≈1,8 GB)
    pip install h5py numpy scikit-learn scipy
    python ml/benchmark_bosch_cnc.py --data CNC_Machining/data

Kết quả: ml/reports/bosch_cnc.md
Nói khi trình bày: "dữ liệu máy phay trong nhà máy Bosch, công khai" — KHÔNG phải dữ liệu DENSO.
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
from scipy.signal import welch
from scipy.stats import kurtosis
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cycles as C  # noqa: E402
from benchmark_pyscrew import Detector  # noqa: E402

FS = 2000
TF_ORDER = ["Oct_2018", "Feb_2019", "Aug_2019", "Feb_2020", "Aug_2020", "Feb_2021", "Aug_2021"]
BANDS = [(0, 100), (100, 400), (400, 1000)]
PCT = 99.0


def feat_gateway(x):
    """Rung tổng hợp (bỏ thành phần tĩnh/trọng lực) → RMS mỗi 10 ms → chuỗi 100 Hz → 9 đặc trưng chuẩn."""
    mag = np.linalg.norm(x - x.mean(axis=0), axis=1)
    w = FS // C.FS
    n = len(mag) // w
    y = np.sqrt((mag[: n * w].reshape(n, w) ** 2).mean(axis=1))
    return C.extract(y)


def feat_full(x):
    xc = x - x.mean(axis=0)
    rms = np.log(np.sqrt((xc ** 2).mean(axis=0)) + 1e-9)
    kur = kurtosis(xc, axis=0)
    f, p = welch(xc, fs=FS, nperseg=1024, axis=0)
    tot = p.sum(axis=1)
    band = [np.log(tot[(f >= lo) & (f < hi)].sum() + 1e-9) for lo, hi in BANDS]
    return np.r_[rms, kur, band, np.log(len(x) / FS)]


def load(data_dir, cache):
    if cache and os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return list(z["meta"]), z["A"], z["B"]
    import h5py
    files = sorted(glob.glob(os.path.join(data_dir, "M0*", "OP*", "*", "*.h5")))
    if not files:
        sys.exit(f"Không thấy file .h5 trong {data_dir}. Đã clone boschresearch/CNC_Machining chưa?")
    meta, A, B = [], [], []
    for i, f in enumerate(files):
        p = f.split(os.sep)
        m = re.search(r"(M0\d)_(\w+_\d{4})_(OP\d\d)_(\d+)\.h5$", f)
        with h5py.File(f, "r") as h:
            x = h["vibration_data"][:]
        meta.append({"machine": m.group(1), "tf": m.group(2), "op": m.group(3), "k": int(m.group(4)),
                     "bad": p[-2] == "bad", "file": os.path.basename(f)})
        A.append(feat_gateway(x))
        B.append(feat_full(x))
        if (i + 1) % 200 == 0:
            print(f"  đã đọc {i + 1}/{len(files)} file")
    A, B = np.array(A), np.array(B)
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez(cache, meta=np.array(meta, dtype=object), A=A, B=B)
    return meta, A, B


def time_key(r):
    return (TF_ORDER.index(r["tf"]) if r["tf"] in TF_ORDER else 99, r["k"])


def score(det, X, kind):
    return det.maha(X) if kind == "maha" else det.robz(X)


def loo_scores(X, kind="maha"):
    out = []
    for i in range(len(X)):
        d = Detector().fit(np.delete(X, i, axis=0))
        out.append(score(d, X[i:i + 1], kind)[0])
    return np.array(out)


def run(meta, F, groups_of, min_train=10, kind="maha"):
    """groups_of(r) → khoá nhóm mô hình. Trả về điểm đã chuẩn hoá cho test normal / bad và LOO train."""
    groups = {}
    for i, r in enumerate(meta):
        groups.setdefault(groups_of(r), []).append(i)
    loo_all, te_n, te_b, used = [], [], [], 0
    per = {}
    for g, idx in groups.items():
        good = sorted([i for i in idx if not meta[i]["bad"]], key=lambda i: time_key(meta[i]))
        bad = [i for i in idx if meta[i]["bad"]]
        ntr = int(len(good) * 0.6)
        if ntr < min_train:
            continue
        tr, te = good[:ntr], good[ntr:]
        loo = loo_scores(F[tr], kind)
        scale = np.median(loo)
        det = Detector().fit(F[tr])
        sn = score(det, F[te], kind) / scale if te else np.array([])
        sb = score(det, F[bad], kind) / scale if bad else np.array([])
        loo_all.append(loo / scale)
        te_n.append(sn)
        te_b.append(sb)
        per[g] = (sn, sb, len(tr))
        used += 1
    return np.concatenate(loo_all), np.concatenate(te_n), np.concatenate(te_b), per, used


def pct(x):
    return f"{100 * x:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="CNC_Machining/data")
    ap.add_argument("--cache", default=os.path.join(HERE, "data", "bosch_cnc_features.npz"))
    a = ap.parse_args()

    meta, A, B = load(a.data, a.cache)
    n_bad = sum(r["bad"] for r in meta)
    print(f"{len(meta)} lần chạy nguyên công ({len(meta) - n_bad} good, {n_bad} bad), 3 máy × 15 nguyên công")

    lines = ["# Kết quả kiểm chứng trên Bosch CNC Machining", "",
             "Dữ liệu rung máy phay trong nhà máy Bosch (công khai, CC BY 4.0), KHÔNG phải dữ liệu DENSO.", "",
             f"- {len(meta)} lần chạy nguyên công, {n_bad} lần lỗi thật (gán nhãn thủ công).",
             "- Mỗi (máy, nguyên công) một mô hình, train trên 60% lần chạy good sớm nhất; kiểm tra trên phần good muộn hơn + toàn bộ bad.",
             f"- Ngưỡng chung: phân vị {PCT:.0f} của điểm leave-one-out trên tập train (đã chuẩn hoá theo từng nguyên công).", "",
             "## Kết quả chính (mỗi máy × nguyên công một mô hình)", "",
             "Hai cách chấm điểm: **Mahalanobis** (đám mây nhiều chiều) và **MAD** (lệch xa nhất theo từng đặc trưng, "
             "ít tham số hơn — hợp khi chỉ có vài chục chu kỳ bình thường). Ba ngưỡng, đều lấy từ tập train "
             "(phân vị 99 / 95 / 90 của điểm leave-one-out) — không nhìn tập kiểm tra.", "",
             "| Bộ đặc trưng | Chấm điểm | AUC | Ngưỡng p99: báo nhầm / bắt lỗi | p95 | p90 |",
             "|---|---|---|---|---|---|"]

    results = {}
    for name, F in [("A. Qua gateway (RMS 100 Hz)", A), ("B. Đầy đủ (rung 2 kHz)", B)]:
        for kind, kname in [("maha", "Mahalanobis"), ("robz", "MAD")]:
            loo, sn, sb, per, used = run(meta, F, lambda r: (r["machine"], r["op"]), kind=kind)
            auc = roc_auc_score(np.r_[np.zeros(len(sn)), np.ones(len(sb))], np.r_[sn, sb])
            cells = []
            for q in (99, 95, 90):
                thr = np.percentile(loo, q)
                cells.append(f"{pct((sn > thr).mean())} / {pct((sb > thr).mean())}")
            results[(name, kind)] = (np.percentile(loo, PCT), per)
            print(f"[{name} · {kname}] {used} mô hình · AUC {auc:.3f} · báo nhầm / bắt lỗi ở p99, p95, p90: "
                  + " · ".join(cells))
            lines.append(f"| {name} | {kname} | {auc:.3f} | " + " | ".join(cells) + " |")
    lines += ["", f"Kiểm tra: {len(sn)} lần chạy good muộn hơn, {len(sb)} lần chạy lỗi, {used} mô hình."]

    # theo máy (bộ B)
    thr, per = results[("B. Đầy đủ (rung 2 kHz)", "maha")]
    lines += ["", "## Theo máy (bộ B, Mahalanobis, ngưỡng p99)", "", "| Máy | Báo nhầm | Bắt được lỗi |", "|---|---|---|"]
    for m in ["M01", "M02", "M03"]:
        sn = np.concatenate([v[0] for g, v in per.items() if g[0] == m] or [np.array([])])
        sb = np.concatenate([v[1] for g, v in per.items() if g[0] == m] or [np.array([])])
        lines.append(f"| {m} | {pct((sn > thr).mean()) if len(sn) else '–'} ({len(sn)}) | "
                     f"{pct((sb > thr).mean()) if len(sb) else '–'} ({len(sb)}) |")

    # Thí nghiệm phụ 1: gộp mọi nguyên công của một máy
    lines += ["", "## Vì sao không gộp: thí nghiệm phụ", ""]
    loo, sn, sb, _, used = run(meta, B, lambda r: r["machine"], min_train=30)
    thr_p = np.percentile(loo, PCT) if len(loo) else np.nan
    auc_p = roc_auc_score(np.r_[np.zeros(len(sn)), np.ones(len(sb))], np.r_[sn, sb])
    print(f"\n[Gộp mọi nguyên công vào 1 mô hình/máy, bộ B] báo nhầm {pct((sn > thr_p).mean())} · "
          f"bắt lỗi {pct((sb > thr_p).mean())} · AUC {auc_p:.3f}")
    lines.append(f"- **Gộp 15 nguyên công vào 1 mô hình mỗi máy** (bộ B): báo nhầm {pct((sn > thr_p).mean())}, "
                 f"bắt lỗi {pct((sb > thr_p).mean())}, AUC {auc_p:.3f}.")

    # Thí nghiệm phụ 2: mô hình máy X chấm máy Y cùng nguyên công
    cross = []
    for op in sorted({r["op"] for r in meta}):
        for mx in ["M01", "M02", "M03"]:
            for my in ["M01", "M02", "M03"]:
                if mx == my:
                    continue
                gx = sorted([i for i, r in enumerate(meta) if r["machine"] == mx and r["op"] == op and not r["bad"]],
                            key=lambda i: time_key(meta[i]))
                gy = [i for i, r in enumerate(meta) if r["machine"] == my and r["op"] == op and not r["bad"]]
                ntr = int(len(gx) * 0.6)
                if ntr < 10 or not gy:
                    continue
                loo = loo_scores(B[gx[:ntr]])
                det = Detector().fit(B[gx[:ntr]])
                cross.append(((det.maha(B[gy]) / np.median(loo)) > thr).mean())
    if cross:
        print(f"[Mô hình máy X chấm lần chạy GOOD của máy Y cùng nguyên công] báo nhầm trung bình {pct(np.mean(cross))}")
        lines.append(f"- **Dùng mô hình của máy này cho máy khác cùng nguyên công**: trung bình {pct(np.mean(cross))} "
                     f"lần chạy good bị báo nhầm ({len(cross)} cặp máy × nguyên công).")
    lines += ["", "Đọc kết quả:",
              "- Chuyển mô hình sang máy khác là sai rõ ràng (báo nhầm rất cao) → mỗi máy phải học chuẩn của chính nó.",
              "- Gộp các nguyên công của CÙNG một máy cho AUC không thấp hơn, nhưng ở ngưỡng p99 bắt được ít lỗi hơn hẳn; "
              "chưa đủ bằng chứng để nói gộp nguyên công luôn kém — ghi đúng như vậy.",
              "- Mỗi nguyên công chỉ có 8–32 chu kỳ để train và dữ liệu kéo dài 3 năm (trôi theo thời gian), nên báo nhầm "
              "trên lần chạy muộn hơn còn cao. Khi triển khai cần thời gian học đủ dài và học lại định kỳ."]

    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    out = os.path.join(HERE, "reports", "bosch_cnc.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nĐã lưu {out}")


if __name__ == "__main__":
    main()
