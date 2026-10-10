"""
danh_gia_pyscrew_gateway.py — Chạy AI ĐANG DÙNG TRONG GATEWAY trên dữ liệu siết bu-lông thật PyScrew,
so với giới hạn PLC và Isolation Forest, có khoảng tin cậy 95%. Dùng chung cách đo với ml/danh_gia_do_tin_cay.py.

Khác ml/benchmark_pyscrew.py (bản cũ): bản cũ dùng bộ phát hiện đời trước và chỉ học trên dữ liệu sạch.
Bản này dùng edge/detector.py (đúng bản trong gateway) và có thêm cách học "như thật": lẫn 2% lỗi không ai biết.

Chạy trên máy đã tải PyScrew (máy Tuấn):
    python ml/danh_gia_pyscrew_gateway.py --scenario s02
    python ml/danh_gia_pyscrew_gateway.py --scenario s04
    python ml/danh_gia_pyscrew_gateway.py --scenario s03
→ ml/reports/pyscrew_gateway_<kịch bản>.md  (gửi file này lên repo hoặc gửi cho Hưng)
"""
import argparse
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import benchmark_pyscrew as P  # noqa: E402
from danh_gia_do_tin_cay import PlcLimits, IForest, Gateway, fmt, auc_ci  # noqa: E402
from edge import detector as D  # noqa: E402


def feat(run):
    y = P.plc_view(run)                         # đúng thứ gateway đọc: 1 thanh ghi momen, 100 Hz, làm tròn
    return D.features(y, duration_s=float(run["t"][-1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="s02")
    ap.add_argument("--cache-dir", default="~/.cache/pyscrew")
    ap.add_argument("--from-pickle", help=argparse.SUPPRESS)
    ap.add_argument("--contam", type=float, default=0.02, help="tỉ lệ lỗi lẫn vào dữ liệu học ở cách 'như thật'")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    runs = P.runs_from(P.load(a.scenario, a.cache_dir, a.from_pickle))
    tr, ca, te, an, other = P.split(runs)
    learn = tr + ca                                    # 80% đầu (theo thứ tự) của các lần siết bình thường
    print(f"Kịch bản {a.scenario}: {len(runs)} lần siết · học {len(learn)} · kiểm tra bình thường {len(te)} · lỗi {len(an)}")
    if len(learn) < 30 or not an:
        sys.exit("Kịch bản này không đủ lần siết bình thường hoặc không có lớp lỗi để đánh giá.")

    print("Đang tính đặc trưng…")
    Fl = np.array([feat(r) for r in learn])
    Fn = np.array([feat(r) for r in te])
    Fa = np.array([feat(r) for r in an])
    cls = [f"{r['cls']}" for r in an]
    cat = [P.category(r) for r in an]

    rng = np.random.default_rng(a.seed)
    k = max(1, int(round(a.contam * len(learn))))
    mix = rng.choice(len(an), size=min(k, len(an) // 5 or 1), replace=False)
    keep = np.setdiff1d(np.arange(len(an)), mix)

    L = ["# PyScrew — AI của gateway so với giới hạn PLC", "",
         f"Kịch bản **{a.scenario}**, dữ liệu siết bu-lông công nghiệp thật (TU Dortmund), KHÔNG phải dữ liệu DENSO. "
         "Gateway chỉ thấy 1 thanh ghi momen đọc 100 lần/giây (làm tròn 0,001 N·m).", "",
         f"- Học: {len(learn)} lần siết bình thường đầu tiên theo thứ tự. Kiểm tra: {len(te)} lần bình thường sau đó + các lần lỗi.",
         f"- Cách \"như thật\": trộn thêm {len(mix)} lần lỗi (~{a.contam * 100:.0f}%) vào dữ liệu học mà không gắn nhãn; "
         "các lần lỗi này bị loại khỏi tập kiểm tra.",
         "- Trong ngoặc là khoảng tin cậy 95%.", ""]
    for lab, Xl, idx in (("Học trên dữ liệu sạch", Fl, np.arange(len(an))),
                         (f"Như thật: học lẫn {a.contam * 100:.0f}% lỗi", np.vstack([Fl, Fa[mix]]), keep)):
        L += [f"## {lab}", "", "| Cách phát hiện | AUC | Báo nhầm | Bắt lỗi | NOK máy tự báo | Lỗi ngầm (máy báo OK) |",
              "|---|---|---|---|---|---|"]
        per_cls = {}
        for M in (PlcLimits([0, D.FEATURES.index("duration_s")]), IForest(), Gateway()):
            M.fit(Xl)
            sn, sb = M.score(Fn), M.score(Fa[idx])
            au, lo, hi = auc_ci(sn, sb)
            cats = defaultdict(lambda: [0, 0]); cl = defaultdict(lambda: [0, 0])
            for j, s in zip(idx, sb):
                cats[cat[j]][0] += int(s > 1); cats[cat[j]][1] += 1
                cl[cls[j]][0] += int(s > 1); cl[cls[j]][1] += 1
            nm = "**" + M.name + "**" if M.name == Gateway.name else M.name
            L.append(f"| {nm} | {au:.2f} ({lo:.2f}–{hi:.2f}) | {fmt(int((sn > 1).sum()), len(sn))} | "
                     f"{fmt(int((sb > 1).sum()), len(sb))} | {fmt(*cats['NOK (máy siết tự báo)'])} | "
                     f"{fmt(*cats['Lỗi ngầm (máy báo OK)'])} |")
            per_cls[M.name] = cl
            print(f"  [{lab}] {M.name:<32} AUC {au:.2f}  báo nhầm {(sn > 1).mean() * 100:5.1f}%  bắt lỗi {(sb > 1).mean() * 100:5.1f}%")
        L += ["", "Theo từng loại lỗi:", "", "| Loại lỗi | Số lần | " + " | ".join(per_cls) + " |",
              "|---|---|" + "---|" * len(per_cls)]
        for c in sorted(next(iter(per_cls.values()))):
            n = next(iter(per_cls.values()))[c][1]
            L.append(f"| {c} | {n} | " + " | ".join(fmt(*per_cls[m][c]) for m in per_cls) + " |")
        L.append("")
    L += ["\"Lỗi ngầm\" là lần siết máy siết tự báo OK nhưng thực ra thuộc điều kiện lỗi — đây là phần giá trị nhất: "
          "PLC/máy hiện tại không bắt được, AI bắt được bao nhiêu thì đó là giá trị thêm.", ""]
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    out = os.path.join(HERE, "reports", f"pyscrew_gateway_{a.scenario}.md")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("Đã ghi", out)


if __name__ == "__main__":
    main()
