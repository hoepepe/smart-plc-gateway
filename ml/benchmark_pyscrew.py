"""
benchmark_pyscrew.py — Kiểm chứng bộ phát hiện bất thường trên DỮ LIỆU SIẾT BU-LÔNG CÔNG NGHIỆP THẬT.

Nguồn dữ liệu: PyScrew (West & Deuse, TU Dortmund) — hơn 34.000 lần siết bu-lông thật,
mỗi lần có momen xiết, góc xoay, thời gian; có nhãn OK/NOK do máy siết tự đánh giá và nhãn
điều kiện thí nghiệm (bình thường / có lỗi được cố ý tạo ra).
    Bài báo:  https://arxiv.org/abs/2505.11925
    Dữ liệu:  https://zenodo.org/records/15393134  (kiểm tra giấy phép tại đây trước khi dùng)

Vì sao bộ này: máy siết bu-lông là một trong các máy mentor DENSO nêu (dashboard: M02 lực xiết),
và mỗi lần siết là MỘT CHU KỲ có dạng sóng — đúng kiểu dữ liệu gateway thu từ PLC.

Script làm ba việc:
  1. Tải dữ liệu (cần mạng tới zenodo.org; lần đầu mất vài phút, sau đó đọc từ bộ nhớ đệm).
  2. Train CHỈ trên các lần siết bình thường, chọn ngưỡng trên tập hiệu chuẩn riêng,
     đánh giá trên tập kiểm tra — tách theo thứ tự thời gian, không trộn ngẫu nhiên.
     So hai bộ đặc trưng:
        A. "Qua PLC": momen lấy mẫu lại 100 Hz, làm tròn 0,001 N·m, 9 đặc trưng của ml/cycles.py
           — ĐÚNG những gì gateway nhìn thấy khi đọc một thanh ghi D ở 100 lần/giây.
        B. "Đầy đủ": momen + góc ở tần số gốc 833 Hz — trần hiệu năng nếu đọc được nhiều tín hiệu hơn.
  3. Xuất:
        ml/models/pyscrew_<kịch bản>.json         mô hình A, dùng được ngay với tools/plc_to_mqtt.py --model
        ml/data/pyscrew_<kịch bản>_replay.csv     các chu kỳ KIỂM TRA để phát lại qua PLC (giả hoặc thật)
        ml/reports/pyscrew_<kịch bản>.md          bảng kết quả để đưa vào slide

Chạy:
    pip install pyscrew numpy scikit-learn
    python ml/benchmark_pyscrew.py                       # mặc định kịch bản s03 (lỗi lắp ráp)
    python ml/benchmark_pyscrew.py --scenario s02        # ma sát bề mặt
    python ml/benchmark_pyscrew.py --scenario s01        # ren mòn dần — xem điểm bất thường tăng theo số lần dùng

QUY TẮC TRUNG THỰC khi trình bày:
  - Đây là dữ liệu máy siết bu-lông của phòng thí nghiệm TU Dortmund, KHÔNG phải máy DENSO.
  - Nói "kiểm chứng phương pháp trên dữ liệu công nghiệp công khai", không nói "đã chạy ở DENSO".
  - Ghi đúng con số script in ra, kể cả loại lỗi bắt kém.
"""
import argparse
import csv
import json
import os
import pickle
import sys

import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cycles as C  # noqa: E402

RATE = C.FS            # 100 Hz — tần số gateway đọc thanh ghi
QUANT = 0.001          # PLC lưu số nguyên: 1 đơn vị thanh ghi = 0,001 N·m
FULL_FEATURES = ["max_torque", "final_torque", "final_angle", "duration", "angle_at_max",
                 "seat_angle", "torque_mean", "torque_std", "work", "final_slope",
                 "max_jump", "n_drops", "torque_q25", "torque_q50", "torque_q75"]
PCT = 99.5             # ngưỡng = phân vị 99,5 trên tập hiệu chuẩn → mục tiêu ~0,5% báo nhầm


# ───────────────────────── Tải dữ liệu ─────────────────────────
def load(scenario, cache_dir, from_pickle=None):
    if from_pickle:
        with open(from_pickle, "rb") as f:
            return pickle.load(f)
    try:
        import pyscrew
    except ImportError:
        sys.exit("Chưa cài pyscrew:  pip install pyscrew")
    print(f"Đang tải kịch bản {scenario} (lần đầu cần mạng tới zenodo.org, có thể mất vài phút)…")
    return pyscrew.get_data(
        scenario=scenario,
        return_measurements=None,    # lấy cả 4 đại lượng: pyscrew 1.2.2 lỗi nếu bỏ gradient
        target_length=None,          # giữ độ dài thật của từng lần siết, không đệm số 0
        cache_dir=cache_dir,
    )


def runs_from(data):
    """Đổi dict của pyscrew thành list các lần siết, giữ nguyên thứ tự trong bộ dữ liệu."""
    out = []
    n = len(data["torque_values"])
    for i in range(n):
        t = np.asarray(data["time_values"][i], float)
        q = np.asarray(data["torque_values"][i], float)
        a = np.asarray(data["angle_values"][i], float)
        k = min(len(t), len(q), len(a))
        t, q, a = t[:k], q[:k], a[:k]
        # bỏ phần đệm cuối (nếu có): thời gian phải tăng dần
        if k > 1:
            good = np.r_[True, np.diff(t) > 0]
            t, q, a = t[good], q[good], a[good]
        if len(t) < 10:
            continue
        cond = str(data["scenario_condition"][i]).lower()
        res = str(data["workpiece_result"][i]).upper()
        out.append({
            "idx": i, "t": t - t[0], "torque": q, "angle": a,
            "cls": str(data["class_values"][i]),
            "condition": cond, "result": res,
            "usage": int(data["workpiece_usage"][i]) if "workpiece_usage" in data else 0,
            "location": str(data.get("workpiece_location", ["?"] * n)[i]),
        })
    return out


# ───────────────────────── Đặc trưng ─────────────────────────
def plc_view(run):
    """Điều gateway thấy: một thanh ghi momen, đọc 100 lần/giây, làm tròn theo đơn vị thanh ghi."""
    t, q = run["t"], run["torque"]
    n = max(int(round(t[-1] * RATE)) + 1, 8)
    y = np.interp(np.linspace(0, t[-1], n), t, q)
    return np.round(y / QUANT) * QUANT


def feat_plc(run):
    return C.extract(plc_view(run))


def feat_full(run):
    t, q, a = run["t"], run["torque"], run["angle"]
    mx = float(q.max())
    i_mx = int(np.argmax(q))
    above = np.nonzero(q > 0.5 * mx)[0]
    seat = float(a[above[0]]) if len(above) else float(a[-1])
    a_rng = float(a[-1] - a[0]) or 1.0
    tail = a >= a[0] + 0.9 * a_rng
    if tail.sum() >= 3 and np.ptp(a[tail]) > 0:
        slope = float(np.polyfit(a[tail], q[tail], 1)[0])
    else:
        slope = 0.0
    dq = np.diff(q)
    # số lần momen tụt mạnh (>10% đỉnh) — dấu hiệu trờn ren
    drops = int(np.sum(dq < -0.1 * mx)) if mx > 0 else 0
    work = float(np.trapezoid(q, a)) if hasattr(np, "trapezoid") else float(np.trapz(q, a))
    return np.array([
        mx, float(q[-1]), float(a[-1]), float(t[-1]), float(a[i_mx]), seat,
        float(q.mean()), float(q.std()), work, slope,
        float(np.abs(dq).max()) if len(dq) else 0.0, drops,
        float(np.percentile(q, 25)), float(np.percentile(q, 50)), float(np.percentile(q, 75)),
    ])


# ───────────────────────── Bộ phát hiện ─────────────────────────
class Detector:
    """Tầng 1: Mahalanobis (đám mây bình thường). Tầng 2: lệch theo từng đặc trưng (median ± MAD).
    Báo bất thường nếu MỘT trong hai tầng vượt ngưỡng. Ngưỡng mỗi tầng chọn trên tập hiệu chuẩn."""

    def fit(self, X):
        self.mu = X.mean(axis=0)
        self.inv = np.linalg.inv(LedoitWolf().fit(X).covariance_)
        self.med = np.median(X, axis=0)
        mad = np.median(np.abs(X - self.med), axis=0) * 1.4826
        # đặc trưng gần như hằng số (vd. số đỉnh) → MAD = 0; dùng độ lệch chuẩn, rồi sàn nhỏ
        sd = X.std(axis=0)
        self.mad = np.where(mad > 1e-9, mad, np.where(sd > 1e-9, sd, 1e-6))
        return self

    def maha(self, X):
        D = X - self.mu
        return np.sqrt(np.einsum("ij,jk,ik->i", D, self.inv, D))

    def robz(self, X):
        return np.max(np.abs(X - self.med) / self.mad, axis=1)

    def calibrate(self, X, pct=PCT):
        self.t_maha = float(np.percentile(self.maha(X), pct))
        self.t_robz = float(np.percentile(self.robz(X), pct))
        return self

    def flags(self, X):
        m, r = self.maha(X) > self.t_maha, self.robz(X) > self.t_robz
        return m, r, m | r


# ───────────────────────── Chia dữ liệu ─────────────────────────
def split(runs):
    """Bình thường = điều kiện 'normal' VÀ máy báo OK. Tách theo thứ tự (thời gian):
    60% đầu để train, 20% tiếp để chọn ngưỡng, 20% cuối để kiểm tra.
    Lỗi = điều kiện 'faulty' hoặc máy báo NOK — chỉ dùng để kiểm tra, không bao giờ để train."""
    normal = [r for r in runs if r["condition"] == "normal" and r["result"] == "OK"]
    anom = [r for r in runs if r["condition"] == "faulty" or r["result"] == "NOK"]
    used = {r["idx"] for r in normal} | {r["idx"] for r in anom}
    other = [r for r in runs if r["idx"] not in used]   # vd. 'mixed' + OK: bỏ, không rõ nhãn
    n = len(normal)
    a, b = int(n * 0.6), int(n * 0.8)
    return normal[:a], normal[a:b], normal[b:], anom, other


def category(r):
    if r["result"] == "NOK":
        return "NOK (máy siết tự báo)"
    return "Lỗi ngầm (máy báo OK)"


# ───────────────────────── Chạy ─────────────────────────
def evaluate(name, fx, tr, ca, te, an):
    Xtr = np.vstack([fx(r) for r in tr])
    Xca = np.vstack([fx(r) for r in ca])
    Xte = np.vstack([fx(r) for r in te])
    det = Detector().fit(Xtr).calibrate(Xca)
    res = {"name": name, "det": det}
    m, r, c = det.flags(Xte)
    res["fa"] = {"maha": m.mean(), "robz": r.mean(), "both": c.mean()}
    if an:
        Xan = np.vstack([fx(x) for x in an])
        am, ar, ac = det.flags(Xan)
        res["det_all"] = {"maha": am.mean(), "robz": ar.mean(), "both": ac.mean()}
        y = np.r_[np.zeros(len(Xte)), np.ones(len(Xan))]
        res["auc"] = float(roc_auc_score(y, np.r_[det.maha(Xte), det.maha(Xan)]))
        by_cat, by_cls = {}, {}
        for x, hit in zip(an, ac):
            by_cat.setdefault(category(x), []).append(hit)
            by_cls.setdefault(x["cls"], []).append(hit)
        res["by_cat"] = {k: (float(np.mean(v)), len(v)) for k, v in by_cat.items()}
        res["by_cls"] = {k: (float(np.mean(v)), len(v)) for k, v in sorted(by_cls.items())}
    return res


def drift_report(fx, runs):
    """Kịch bản không có lớp lỗi (vd. s01 ren mòn dần): train trên các lần dùng đầu tiên,
    xem điểm bất thường tăng thế nào khi chi tiết bị dùng lại nhiều lần."""
    us = np.array([r["usage"] for r in runs])
    lo = np.percentile(us, 25)
    base = [r for r in runs if r["usage"] <= lo]
    n = len(base)
    tr, ca = base[: int(n * 0.75)], base[int(n * 0.75):]
    det = Detector().fit(np.vstack([fx(r) for r in tr])).calibrate(np.vstack([fx(r) for r in ca]))
    edges = np.unique(np.percentile(us, [0, 25, 50, 75, 100]))
    rows = []
    for lo_e, hi_e in zip(edges[:-1], edges[1:]):
        tr_ids = {r["idx"] for r in tr}
        grp = [r for r in runs if lo_e <= r["usage"] <= hi_e and r["idx"] not in tr_ids]
        if not grp:
            continue
        X = np.vstack([fx(r) for r in grp])
        rows.append((int(lo_e), int(hi_e), float(np.median(det.maha(X))), float(det.flags(X)[2].mean()), len(grp)))
    return rows


def pct(x):
    return f"{x * 100:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="s03", help="s01..s06 (mặc định s03: lỗi lắp ráp)")
    ap.add_argument("--cache-dir", default="~/.cache/pyscrew")
    ap.add_argument("--from-pickle", help=argparse.SUPPRESS)       # dùng cho kiểm thử offline
    ap.add_argument("--location", choices=["left", "right", "both"], default="both",
                    help="vị trí vít trên chi tiết; hai vị trí có thể có dạng sóng khác nhau")
    ap.add_argument("--replay-max", type=int, default=300,
                    help="số chu kỳ tối đa ghi ra file phát lại (≈3 giây/chu kỳ khi phát)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    data = load(a.scenario, a.cache_dir, a.from_pickle)
    runs = runs_from(data)
    if a.location != "both":
        runs = [r for r in runs if r["location"] == a.location]
    print(f"Đọc được {len(runs)} lần siết — kịch bản {a.scenario}")

    os.makedirs(os.path.join(HERE, "models"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    report_path = os.path.join(HERE, "reports", f"pyscrew_{a.scenario}.md")
    lines = [f"# Kết quả kiểm chứng trên PyScrew — kịch bản {a.scenario}", "",
             "Dữ liệu siết bu-lông công nghiệp công khai (TU Dortmund), KHÔNG phải dữ liệu DENSO.", ""]

    tr, ca, te, an, other = split(runs)
    print(f"Bình thường: train {len(tr)} · hiệu chuẩn {len(ca)} · kiểm tra {len(te)}   "
          f"Lỗi (chỉ để kiểm tra): {len(an)}   Bỏ qua (nhãn không rõ): {len(other)}")

    if not an:
        print("\nKịch bản này không có lớp lỗi → chạy chế độ THEO DÕI MÒN DẦN.")
        lines += ["## Chế độ theo dõi mòn dần", "",
                  "Train trên 25% số lần dùng đầu tiên. Bảng: điểm bất thường theo số lần chi tiết đã dùng.", "",
                  "| Số lần dùng | Bộ đặc trưng | Điểm trung vị | Tỉ lệ bị gắn cờ | Số lần siết |", "|---|---|---|---|---|"]
        for nm, fx in [("A. Qua PLC", feat_plc), ("B. Đầy đủ", feat_full)]:
            for lo, hi, med, fr, n in drift_report(fx, runs):
                print(f"  {nm:<12} dùng {lo:>3}–{hi:<3}  điểm trung vị {med:6.2f}  gắn cờ {pct(fr):>6}  (n={n})")
                lines.append(f"| {lo}–{hi} | {nm} | {med:.2f} | {pct(fr)} | {n} |")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nĐã lưu {report_path}")
        return

    if len(tr) < 30:
        sys.exit("Quá ít lần siết bình thường để train (cần ≥ 30). Thử kịch bản khác, vd. --scenario s02.")

    results = [evaluate("A. Qua PLC (1 thanh ghi, 100 Hz)", feat_plc, tr, ca, te, an),
               evaluate("B. Đầy đủ (momen + góc, 833 Hz)", feat_full, tr, ca, te, an)]

    lines += [f"- Bình thường: train {len(tr)}, hiệu chuẩn ngưỡng {len(ca)}, kiểm tra {len(te)} (tách theo thứ tự thời gian)",
              f"- Lần siết lỗi (chỉ dùng để kiểm tra): {len(an)}",
              f"- Ngưỡng: phân vị {PCT} trên tập hiệu chuẩn → mục tiêu khoảng 0,5% báo nhầm mỗi tầng", "",
              "## Tổng quan", "",
              "| Bộ đặc trưng | Báo nhầm (bình thường bị gắn cờ) | Bắt được lỗi | AUC (Mahalanobis) |",
              "|---|---|---|---|"]
    for r in results:
        print(f"\n[{r['name']}]")
        print(f"  Báo nhầm trên chu kỳ bình thường: Mahalanobis {pct(r['fa']['maha'])} · "
              f"MAD {pct(r['fa']['robz'])} · kết hợp {pct(r['fa']['both'])}")
        print(f"  Bắt được lỗi:                     Mahalanobis {pct(r['det_all']['maha'])} · "
              f"MAD {pct(r['det_all']['robz'])} · kết hợp {pct(r['det_all']['both'])}   AUC {r['auc']:.3f}")
        for k, (v, n) in r["by_cat"].items():
            print(f"    {k:<26} {pct(v):>6}  (n={n})")
        lines.append(f"| {r['name']} | {pct(r['fa']['both'])} | {pct(r['det_all']['both'])} | {r['auc']:.3f} |")

    lines += ["", "## Theo loại", "", "| Nhóm | " + " | ".join(r["name"] for r in results) + " | Số mẫu |",
              "|---|" + "---|" * (len(results) + 1)]
    for k in results[0]["by_cat"]:
        lines.append(f"| {k} | " + " | ".join(pct(r["by_cat"][k][0]) for r in results) + f" | {results[0]['by_cat'][k][1]} |")
    lines += ["", "## Theo lớp lỗi của bộ dữ liệu", "",
              "| Lớp | " + " | ".join(r["name"] for r in results) + " | Số mẫu |", "|---|" + "---|" * (len(results) + 1)]
    for k in results[0]["by_cls"]:
        lines.append(f"| {k} | " + " | ".join(pct(r["by_cls"][k][0]) for r in results) + f" | {results[0]['by_cls'][k][1]} |")
    lines += ["", "Ghi chú: \"Lỗi ngầm\" = điều kiện thí nghiệm có lỗi nhưng máy siết vẫn báo OK — "
              "loại lỗi gateway + AI cần bắt, vì PLC không tự báo."]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # ── Xuất mô hình A (chạy được trên cầu nối) ──
    det = results[0]["det"]
    model_path = os.path.join(HERE, "models", f"pyscrew_{a.scenario}.json")
    Xtr = np.vstack([feat_plc(r) for r in tr])
    with open(model_path, "w", encoding="utf-8") as f:
        json.dump({
            "source": f"PyScrew {a.scenario} — dữ liệu công khai TU Dortmund, không phải DENSO",
            "signal": "torque", "unit": "N·m", "register_scale": QUANT, "sample_rate_hz": RATE,
            "features": C.FEATURES,
            "model": {"type": "mahalanobis",
                      "mu": det.mu.round(6).tolist(),
                      "std": Xtr.std(axis=0).round(6).tolist(),
                      "inv_cov": det.inv.round(8).tolist(),
                      "threshold": round(det.t_maha, 4)},
        }, f, ensure_ascii=False)

    # ── Xuất chu kỳ kiểm tra để phát lại qua PLC ──
    rng = np.random.default_rng(a.seed)
    n_an = min(len(an), a.replay_max // 2)
    n_ok = min(len(te), a.replay_max - n_an)
    pick = [te[i] for i in rng.choice(len(te), n_ok, replace=False)] + \
           [an[i] for i in rng.choice(len(an), n_an, replace=False)]
    pick = [pick[i] for i in rng.permutation(len(pick))]
    replay_path = os.path.join(HERE, "data", f"pyscrew_{a.scenario}_replay.csv")
    an_ids = {r["idx"] for r in an}
    with open(replay_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tag", "label", "category", "class", "result", "offline_score", "n", "y"])
        for tag, r in enumerate(pick, start=1):
            y = plc_view(r)
            s = float(det.maha(C.extract(y)[None, :])[0])
            is_an = r["idx"] in an_ids
            w.writerow([tag, int(is_an), category(r) if is_an else "Bình thường", r["cls"], r["result"],
                        round(s, 4), len(y), ";".join(f"{v:.3f}" for v in y)])

    print(f"\nĐã lưu:\n  {report_path}\n  {model_path}\n  {replay_path}  ({len(pick)} chu kỳ: {n_ok} bình thường, {n_an} lỗi)")
    print("\nBước tiếp: phát lại các chu kỳ này qua PLC — xem docs/HuongDan_ChungMinh_AI_PyScrew.md")


if __name__ == "__main__":
    main()
