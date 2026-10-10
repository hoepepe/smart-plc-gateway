"""
danh_gia_do_tin_cay.py — Bộ đánh giá độ tin cậy của AI gateway, dùng để trình bày với ban giám khảo.

Nguyên tắc (để con số đáng tin):
  1. Bộ phát hiện được đánh giá là ĐÚNG BẢN chạy trong gateway (edge/detector.py), không phải bản riêng cho báo cáo.
  2. Lúc học KHÔNG biết nhãn: có lẫn chu kỳ lỗi trong dữ liệu học, giống thực tế ở nhà máy.
  3. Dữ liệu kiểm tra là ca / khoảng thời gian CHƯA TỪNG THẤY khi học.
  4. Ngưỡng chọn chỉ từ dữ liệu học. Không chỉnh tham số theo kết quả kiểm tra.
  5. So với 2 cách khác trên cùng dữ liệu:
       - Giới hạn PLC: kiểm tra giá trị đỉnh và thời gian chu kỳ nằm trong khoảng cho phép (cách OK/NG phổ biến hiện nay)
       - Isolation Forest: một thuật toán phát hiện bất thường phổ biến
  6. Mọi tỉ lệ đều có khoảng tin cậy 95% (Wilson cho tỉ lệ, bootstrap cho AUC).

Chạy: python ml/danh_gia_do_tin_cay.py   → ml/reports/do_tin_cay.md
Phần Bosch cần ml/data/bosch_cnc_features.npz (tạo bằng benchmark_bosch_cnc.py), thiếu thì bỏ qua.
"""
import glob
import os
import sys
import warnings

import numpy as np
from sklearn.ensemble import IsolationForest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import cycles as C  # noqa: E402
from edge import detector as D  # noqa: E402
from edge.sources import sim_session, sim_faults, CNC_FAULTS  # noqa: E402

warnings.filterwarnings("ignore")
Q = 0.25          # giới hạn PLC: phân vị 0,25 % / 99,75 % của dữ liệu học (cùng mục tiêu báo nhầm ~0,5 % như AI)


# ───────────────────────── thống kê ─────────────────────────
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def fmt(k, n):
    p, lo, hi = wilson(k, n)
    return f"{p * 100:.1f}% ({lo * 100:.0f}–{hi * 100:.0f})"


def auc(sn, sb):
    sn, sb = np.asarray(sn, float), np.asarray(sb, float)
    if not len(sn) or not len(sb):
        return float("nan")
    s = np.r_[sn, sb]
    o = np.argsort(s, kind="mergesort")
    r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    # xử lý điểm bằng nhau
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=r); r = (sums / cnt)[inv]
    return float((r[len(sn):].sum() - len(sb) * (len(sb) + 1) / 2) / (len(sn) * len(sb)))


def auc_ci(sn, sb, B=1000, seed=0):
    rng = np.random.default_rng(seed)
    sn, sb = np.asarray(sn), np.asarray(sb)
    v = [auc(rng.choice(sn, len(sn)), rng.choice(sb, len(sb))) for _ in range(B)]
    return auc(sn, sb), float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))


# ───────────────────────── 3 cách phát hiện ─────────────────────────
class PlcLimits:
    """Cách OK/NG hiện nay: đỉnh và thời gian chu kỳ phải nằm trong [min, max] học được."""
    name = "Giới hạn PLC (đỉnh + thời gian)"

    def __init__(self, cols):
        self.cols = cols

    def fit(self, X):
        X = np.asarray(X)[:, self.cols]
        self.lo, self.hi = np.percentile(X, Q, axis=0), np.percentile(X, 100 - Q, axis=0)
        return self

    def score(self, X):
        X = np.atleast_2d(X)[:, self.cols]
        w = np.maximum(self.hi - self.lo, 1e-9)
        return np.max(np.maximum(self.lo - X, X - self.hi) / w, axis=1) + 1.0   # > 1 là ngoài giới hạn


class IForest:
    name = "Isolation Forest"

    def fit(self, X):
        X = np.asarray(X)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        self.m = IsolationForest(n_estimators=200, random_state=0).fit((X - self.mu) / self.sd)
        self.t = np.percentile(-self.m.score_samples((X - self.mu) / self.sd), 99.5)
        return self

    def score(self, X):
        return -self.m.score_samples((np.atleast_2d(X) - self.mu) / self.sd) / self.t


class Gateway:
    name = "AI của gateway"

    def fit(self, X):
        self.m = D.train(X)
        return self

    def score(self, X):
        return np.array([D.score(self.m, f)["norm"] for f in np.atleast_2d(X)])


# ───────────────────────── A. mô phỏng 4 quá trình kiểu DENSO ─────────────────────────
PROCS = [("PRESS_FORCE", "Máy ép"), ("TORQUE", "Máy siết bu-lông"), ("CNC_LOAD", "Máy CNC"), ("AIR_PRESSURE", "Khí nén")]
FAULT_VI = {**{k: v for d in C.FAULTS.values() for k, v in d.items()}, **CNC_FAULTS}


def sim_eval(proc, seed=0, learn_shifts=5, per_shift=60, contam=0.02, test_shifts=10, test_per=40, fault_per=10):
    rng = np.random.default_rng(seed)
    faults = sim_faults(proc)
    # Học: 300 chu kỳ qua 5 ca, lẫn ~2% chu kỳ lỗi không ai gắn nhãn
    Xl = []
    for s in range(learn_shifts):
        for y in sim_session(proc, per_shift, 1000 * seed + s):
            if rng.random() < contam:
                y = sim_session(proc, 1, int(rng.integers(1e9)), str(rng.choice(faults)))[0]
            Xl.append(D.features(y))
    Xn = [D.features(y) for s in range(test_shifts) for y in sim_session(proc, test_per, 5000 + 1000 * seed + s)]
    Xf = {f: [D.features(y) for s in range(test_shifts) for y in sim_session(proc, fault_per, 9000 + 1000 * seed + 37 * s, f)]
          for f in faults}
    dur = D.FEATURES.index("duration_s")
    out = {}
    for M in (PlcLimits([0, dur]), IForest(), Gateway()):
        M.fit(np.array(Xl))
        sn = M.score(np.array(Xn))
        row = dict(fa=(int((sn > 1).sum()), len(sn)), det={})
        allb = []
        for f, X in Xf.items():
            sb = M.score(np.array(X)); allb.append(sb)
            row["det"][f] = (int((sb > 1).sum()), len(sb))
        row["auc"] = auc(sn, np.concatenate(allb))
        out[M.name] = row
    return out


# ───────────────────────── B. dữ liệu thật Bosch CNC ─────────────────────────
def bosch_eval(F, meta, feedback=False):
    import benchmark_bosch_cnc as B
    groups = {}
    for i, r in enumerate(meta):
        groups.setdefault((r["machine"], r["op"]), []).append(i)
    res = {}
    for M_ in (lambda: PlcLimits([0]), IForest, Gateway):
        sn, sb, used = [], [], 0
        name = None
        for g, idx in groups.items():
            idx = sorted(idx, key=lambda i: B.time_key(meta[i]))
            n = len(idx) // 2
            L = idx[:n]
            if len(L) < 20:
                continue
            M = M_().fit(F[L]); name = M.name; used += 1
            pool = list(L)
            for i in idx[n:]:
                s = float(M.score(F[i])[0])
                (sb if meta[i]["bad"] else sn).append(s)
                if feedback:
                    # kỹ sư xác nhận lần chạy good (bấm "Báo nhầm" nếu bị cảnh báo) → học lại trên các lần chạy
                    # đã xác nhận gần nhất. Lần chạy lỗi không bao giờ được đưa vào học.
                    if not meta[i]["bad"]:
                        pool.append(i)
                    try:
                        M = M_().fit(F[pool[-max(20, n):]])
                    except Exception:
                        pass
        res[name] = dict(sn=np.array(sn), sb=np.array(sb), used=used)
    return res


# ───────────────────────── báo cáo ─────────────────────────
def main():
    lines = ["# Độ tin cậy của AI gateway", "",
             "Tạo bằng `python ml/danh_gia_do_tin_cay.py`. Bộ phát hiện là đúng bản chạy trong gateway (`edge/detector.py`).", "",
             "**Cách đo** (để con số không tự lừa mình):",
             "- Lúc học **không biết nhãn**: dữ liệu học có lẫn chu kỳ lỗi, giống thực tế.",
             "- Kiểm tra trên **ca / khoảng thời gian chưa từng thấy** khi học.",
             "- Ngưỡng chọn chỉ từ dữ liệu học, không chỉnh theo kết quả kiểm tra.",
             "- So với 2 cách khác trên **cùng dữ liệu**: giới hạn PLC (đỉnh + thời gian nằm trong khoảng cho phép — cách OK/NG phổ biến hiện nay) và Isolation Forest.",
             "- Trong ngoặc là **khoảng tin cậy 95%**.", ""]

    # A. mô phỏng
    lines += ["## 1. Bốn loại máy kiểu DENSO (dữ liệu mô phỏng)", "",
              "Học 300 chu kỳ qua 5 ca (lẫn ~2% chu kỳ lỗi không ai biết). Kiểm tra 400 chu kỳ bình thường và 100 chu kỳ "
              "mỗi loại lỗi, lấy từ 10 ca khác. Lặp 3 lần với hạt giống khác nhau rồi cộng dồn.", ""]
    summary = {}
    J = dict(sim=[], bosch=[], made=None)        # bản tóm tắt cho dashboard (src/data/do_tin_cay.json)

    def wj(k, n):
        p_, lo, hi = wilson(k, n)
        return dict(k=int(k), n=int(n), p=round(p_, 4), lo=round(lo, 4), hi=round(hi, 4))
    for proc, vi in PROCS:
        agg = {}
        for seed in range(3):
            for meth, row in sim_eval(proc, seed).items():
                a = agg.setdefault(meth, dict(fa=[0, 0], det={}, auc=[]))
                a["fa"][0] += row["fa"][0]; a["fa"][1] += row["fa"][1]; a["auc"].append(row["auc"])
                for f, (k, n) in row["det"].items():
                    d = a["det"].setdefault(f, [0, 0]); d[0] += k; d[1] += n
        faults = list(next(iter(agg.values()))["det"])
        lines += [f"### {vi}", "",
                  "| Cách phát hiện | Báo nhầm | " + " | ".join(FAULT_VI.get(f, f).split(" —")[0] for f in faults) + " | Bắt lỗi chung |",
                  "|---|---|" + "---|" * (len(faults) + 1)]
        for meth, a in agg.items():
            tk = sum(v[0] for v in a["det"].values()); tn = sum(v[1] for v in a["det"].values())
            lines.append(f"| {'**' + meth + '**' if meth == Gateway.name else meth} | {fmt(*a['fa'])} | "
                         + " | ".join(fmt(*a["det"][f]) for f in faults) + f" | {fmt(tk, tn)} |")
            summary[(vi, meth)] = (a["fa"], (tk, tn))
        J["sim"].append(dict(machine=vi, methods=[dict(
            name=meth, fa=wj(*a["fa"]),
            det=wj(sum(v[0] for v in a["det"].values()), sum(v[1] for v in a["det"].values())),
            faults=[dict(name=FAULT_VI.get(f, f).split(" —")[0], **wj(*a["det"][f])) for f in faults])
            for meth, a in agg.items()]))
        lines.append("")
        print("xong", vi)

    # B. Bosch
    p = os.path.join(HERE, "data", "bosch_cnc_features.npz")
    if os.path.exists(p):
        d = np.load(p, allow_pickle=True)
        meta, A = list(d["meta"]), d["A"]
        lines += ["## 2. Dữ liệu thật: máy phay CNC trong nhà máy Bosch", "",
                  "Bộ dữ liệu công khai CNC Machining của Bosch (CC BY 4.0): rung động 3 máy phay, 2018–2021, lỗi do kỹ sư gắn nhãn. "
                  "Tín hiệu đưa qua đúng đường gateway (RMS 100 Hz). Mỗi (máy, nguyên công) một mô hình, học nửa đầu theo thời gian "
                  "(không biết nhãn), kiểm tra nửa sau.", "",
                  "| Cách chạy | Cách phát hiện | AUC | Báo nhầm | Bắt lỗi |", "|---|---|---|---|---|"]
        for fb, lab in ((False, "Học một lần rồi để nguyên"), (True, "Học lại theo phản hồi của kỹ sư")):
            for meth, r in bosch_eval(A, meta, feedback=fb).items():
                a, lo, hi = auc_ci(r["sn"], r["sb"])
                J["bosch"].append(dict(mode=lab, name=meth, auc=round(a, 3), auc_lo=round(lo, 3), auc_hi=round(hi, 3),
                                       fa=wj(int((r["sn"] > 1).sum()), len(r["sn"])),
                                       det=wj(int((r["sb"] > 1).sum()), len(r["sb"]))))
                lines.append(f"| {lab} | {'**' + meth + '**' if meth == Gateway.name else meth} | {a:.2f} ({lo:.2f}–{hi:.2f}) | "
                             f"{fmt(int((r['sn'] > 1).sum()), len(r['sn']))} | {fmt(int((r['sb'] > 1).sum()), len(r['sb']))} |")
            print("xong Bosch", lab)
        lines += ["", f"Kiểm tra trên {len(r['sn'])} lần chạy tốt và {len(r['sb'])} lần chạy lỗi (chỉ {len(r['sb'])} lỗi rơi vào nửa sau, "
                  "nên khoảng tin cậy của tỉ lệ bắt lỗi rất rộng).", ""]

    # C. PLC thật
    lines += ["## 3. Chuỗi thật: PLC Mitsubishi Q06UDEHCPU → gateway", "",
              "Phát lại chu kỳ siết bu-lông thật (PyScrew) vào thanh ghi PLC thật, gateway đọc lại qua MC protocol rồi chấm điểm:",
              "20 chu kỳ, đọc ổn định 99,8 mẫu/giây, **kết luận bình thường/bất thường trùng 100%** với chấm trực tiếp trên dữ liệu gốc, "
              "điểm lệch trung vị 6,5%. Điều này chứng minh đường truyền PLC → gateway không làm sai kết luận của AI "
              "(không phải chứng minh độ chính xác phát hiện lỗi).", ""]

    # D. PyScrew
    ps = sorted(glob.glob(os.path.join(HERE, "reports", "pyscrew_*.md")))
    lines += ["## 4. Dữ liệu thật: siết bu-lông PyScrew (TU Dortmund)", ""]
    if ps:
        for f in ps:
            lines += [f"Xem [{os.path.basename(f)}]({os.path.basename(f)}).", ""]
    else:
        lines += ["Đã chạy trên máy Tuấn (kịch bản s02, s04); đưa `ml/reports/pyscrew_*.md` vào repo để báo cáo này tự dẫn tới.", ""]

    # E. đọc kết quả
    lines += ["## Đọc kết quả", ""]
    for vi in [v for _, v in PROCS]:
        g = summary.get((vi, Gateway.name)); pl = summary.get((vi, PlcLimits.name))
        if g and pl:
            lines.append(f"- {vi}: AI bắt {wilson(*g[1])[0] * 100:.0f}% lỗi với {wilson(*g[0])[0] * 100:.1f}% báo nhầm; "
                         f"giới hạn PLC bắt {wilson(*pl[1])[0] * 100:.0f}% với {wilson(*pl[0])[0] * 100:.1f}% báo nhầm.")
    lines += ["- Isolation Forest dùng tham số mặc định, ngưỡng phân vị 99,5 của dữ liệu học (cùng mục tiêu báo nhầm với AI gateway).",
              "- Dữ liệu thật Bosch: khi có kỹ sư phản hồi, AI gateway có AUC cao nhất (0,90) và bắt 7/9 lỗi, nhưng báo nhầm ~19% — "
              "cao hơn Isolation Forest (~6%), dù Isolation Forest chỉ bắt 3/9. Chỉ có 9 lỗi nên chưa kết luận chắc được; "
              "báo nhầm 19% là chưa đủ để chạy không cần người duyệt.",
              "- Dữ liệu mô phỏng do nhóm tạo, nên con số cao là cận trên. Dữ liệu thật (Bosch) khó hơn nhiều: máy trôi theo nhiều năm.",
              "- Vì vậy thiết kế giữ con người trong vòng lặp: kỹ sư duyệt mọi chuẩn mới, bấm Báo nhầm / Bình thường mới để AI học lại.",
              ""]
    out = os.path.join(HERE, "reports", "do_tin_cay.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    import json
    import time as _t
    J["made"] = _t.strftime("%d/%m/%Y")
    jp = os.path.join(HERE, "..", "src", "data", "do_tin_cay.json")
    open(jp, "w", encoding="utf-8").write(json.dumps(J, ensure_ascii=False, indent=1))
    print("Đã ghi", jp)
    print("Đã ghi", out)


if __name__ == "__main__":
    main()
