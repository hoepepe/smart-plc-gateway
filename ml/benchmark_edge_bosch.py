"""
benchmark_edge_bosch.py — Chạy BỘ PHÁT HIỆN ĐANG DÙNG TRONG GATEWAY (edge/detector.py) trên dữ liệu thật Bosch CNC,
theo đúng cách sản phẩm sẽ chạy ở nhà máy:

  - Mỗi (máy, nguyên công) một mô hình, chu kỳ đi theo thứ tự thời gian.
  - Giai đoạn học dùng các lần chạy ĐẦU TIÊN, KHÔNG biết nhãn: lần chạy lỗi lẫn vào thì vẫn bị đưa vào học
    (giống thực tế: lúc gateway học, không ai đứng gắn nhãn). Bộ lọc bền vững trong detector phải tự loại.
  - Sau đó giám sát các lần chạy còn lại; đo báo nhầm trên lần chạy good và tỉ lệ bắt trên lần chạy lỗi.
  - Biến thể "học lại định kỳ": cứ sau R lần giám sát thì học lại trên các lần chạy gần đây KHÔNG bị cảnh báo
    (giống learner._candidate, tự duyệt).

So sánh với cách đánh giá cũ (benchmark_bosch_cnc.py: train chỉ trên lần chạy good, đã biết nhãn).

Cần ml/data/bosch_cnc_features.npz (tạo bằng benchmark_bosch_cnc.py). Chạy: python ml/benchmark_edge_bosch.py
"""
import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from edge import detector as D  # noqa: E402

warnings.filterwarnings("ignore")
TF_ORDER = ["Aug_2019", "Feb_2019", "Feb_2020", "Feb_2021", "Aug_2020", "Aug_2021"]


def tkey(r):
    # cùng thứ tự thời gian với benchmark_bosch_cnc.py
    import benchmark_bosch_cnc as B
    return B.time_key(r)


def roc_auc(sn, sb):
    if not len(sn) or not len(sb):
        return float("nan")
    s = np.r_[sn, sb]; y = np.r_[np.zeros(len(sn)), np.ones(len(sb))]
    o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    return float((r[y == 1].sum() - len(sb) * (len(sb) + 1) / 2) / (len(sn) * len(sb)))


def run(meta, F, learn_frac=0.5, min_learn=20, retrain_every=0, window=30, oracle=False, feedback=False):
    groups = {}
    for i, r in enumerate(meta):
        groups.setdefault((r["machine"], r["op"]), []).append(i)
    sn, sb, used, bad_in_learn, dropped_bad, dropped = [], [], 0, 0, 0, 0
    per = {}   # máy → [điểm good], [điểm lỗi], [báo nhầm ước tính lúc học]
    for g, idx in groups.items():
        idx = sorted(idx, key=lambda i: tkey(meta[i]))
        n_learn = int(len(idx) * learn_frac)
        learn = idx[:n_learn]
        if oracle:                                  # cách cũ: biết nhãn, chỉ học trên good
            learn = [i for i in learn if not meta[i]["bad"]]
        if len(learn) < min_learn:
            continue
        try:
            m = D.train(F[learn])
        except Exception:
            continue
        used += 1
        pm = per.setdefault(g[0], ([], [], []))
        pm[2].append(m["calib_false_alarm"])
        nb = sum(meta[i]["bad"] for i in learn)
        bad_in_learn += nb
        # bộ lọc bền vững có bỏ đúng lần chạy lỗi không
        X = F[learn]
        med = np.median(X, axis=0); mad = np.median(np.abs(X - med), axis=0) * 1.4826
        sd = X.std(axis=0)
        sc = np.where(mad > 1e-9, mad, np.where(sd > 1e-9, sd, np.maximum(np.abs(med) * 0.02, 1e-3)))
        z = np.max(np.abs(X - med) / sc, axis=1)
        keep = z <= D.ROBUST_Z
        if keep.mean() < 0.8:
            keep = z <= np.quantile(z, 0.8)
        dropped += int((~keep).sum())
        dropped_bad += int(sum(meta[i]["bad"] for i, k in zip(learn, keep) if not k))
        recent, k = [], 0
        for i in idx[n_learn:]:
            s = D.score(m, F[i])
            (sb if meta[i]["bad"] else sn).append(s["norm"])
            (pm[1] if meta[i]["bad"] else pm[0]).append(s["norm"])
            # feedback=True: kỹ sư bấm "Báo nhầm" trên cảnh báo của lần chạy good → lần chạy đó được học lại
            # (learner._candidate cũng lấy các chu kỳ false_alarm). Lần chạy lỗi bị cảnh báo thì không học.
            if not s["flag"] or (feedback and not meta[i]["bad"]):
                recent.append(i)
            k += 1
            if retrain_every and k % retrain_every == 0 and len(recent) >= min_learn:
                try:
                    m = D.train(F[recent[-window:]])
                except Exception:
                    pass
    return np.array(sn), np.array(sb), used, bad_in_learn, dropped_bad, dropped, per


def line(name, res):
    sn, sb, used, bil, db, dr, per = res
    fa = (sn > 1).mean() if len(sn) else float("nan")
    det = (sb > 1).mean() if len(sb) else float("nan")
    return (f"| {name} | {used} | {len(sn)} / {len(sb)} | {roc_auc(sn, sb):.3f} | {fa * 100:.1f}% | {det * 100:.1f}% |"
            , dict(fa=fa, det=det, auc=roc_auc(sn, sb), bil=bil, db=db, dr=dr, per=per))


def main():
    sys.path.insert(0, HERE)
    d = np.load(os.path.join(HERE, "data", "bosch_cnc_features.npz"), allow_pickle=True)
    meta, A, B = list(d["meta"]), d["A"], d["B"]
    rows, info = [], {}
    for fs_name, F in (("A. Qua gateway (RMS 100 Hz)", A), ("B. Đầy đủ (rung 2 kHz)", B)):
        for name, kw in (("Cách cũ: học trên good đã biết nhãn", dict(oracle=True)),
                         ("Như thật: học 50% đầu, không biết nhãn", {}),
                         ("Như thật + học lại mỗi 10 lần chạy", dict(retrain_every=10)),
                         ("Như thật + học lại + kỹ sư bấm Báo nhầm", dict(retrain_every=10, feedback=True))):
            ln, inf = line(f"{fs_name} · {name}", run(meta, F, **kw))
            rows.append(ln); info[(fs_name, name)] = inf
            print(ln)
    a = info[("A. Qua gateway (RMS 100 Hz)", "Như thật: học 50% đầu, không biết nhãn")]
    out = ["# Bộ phát hiện của gateway trên dữ liệu thật Bosch CNC", "",
           "Dữ liệu rung máy phay trong nhà máy Bosch (công khai, CC BY 4.0), KHÔNG phải dữ liệu DENSO.",
           "Bộ phát hiện: `edge/detector.py` — đúng bản đang chạy trong gateway (lọc bền vững, ngưỡng p99,5 chọn bằng kiểm định chéo theo khối thời gian, Mahalanobis + MAD).",
           "",
           "Mỗi (máy, nguyên công) một mô hình, chu kỳ theo thứ tự thời gian. Chỉ dùng nhóm có ≥ 20 lần chạy để học "
           "(bộ phát hiện không học với ít hơn 20). Điểm > 1,0 là cảnh báo.", "",
           "| Cách chạy | Số mô hình | Test good / lỗi | AUC | Báo nhầm | Bắt lỗi |", "|---|---|---|---|---|---|",
           *rows, "",
           f"Ở cách \"như thật\" (bộ A), {a['bil']} lần chạy lỗi lẫn vào dữ liệu học mà không ai biết; "
           f"bộ lọc bền vững tự bỏ {a['dr']} lần chạy, trong đó {a['db']} là lỗi thật.", "",
           "## Theo máy (bộ A, như thật)", "",
           "| Máy | Lần chạy good test | Báo nhầm thật | Báo nhầm ước tính lúc học (trung bình) | Lỗi test | Bắt được |",
           "|---|---|---|---|---|---|",
           *[f"| {k} | {len(v[0])} | {np.mean(np.array(v[0]) > 1) * 100:.1f}% | {np.mean(v[2]) * 100:.1f}% | {len(v[1])} | "
             + (f"{np.mean(np.array(v[1]) > 1) * 100:.0f}%" if v[1] else "—") + " |" for k, v in sorted(a["per"].items())],
           "",
           "Đọc kết quả (nói thật):",
           "- **Bộ phát hiện hiện tại CHƯA đáng tin trên dữ liệu này.** Báo nhầm khoảng 40%, chủ yếu do máy M02 — máy này trôi mạnh theo thời gian (báo cáo cũ cũng thấy M02 báo nhầm 33,6%).",
           "- Mỗi nguyên công chỉ có 20–28 lần chạy để học, rải trong nhiều năm. Gateway được thiết kế học 300 chu kỳ liên tiếp trong một ca rồi học lại định kỳ — dữ liệu Bosch không cho kiểm chứng đúng điều kiện đó.",
           "- \"Báo nhầm ước tính\" lúc học (5–11%) đã cao hơn mục tiêu 0,5–1%, tức dashboard sẽ báo cho kỹ sư là chuẩn chưa ổn. Nhưng nó vẫn thấp hơn báo nhầm thật khi máy trôi nhiều năm — con số ước tính không thay được thời gian chạy thử.",
           "- Học lại định kỳ chỉ trên chu kỳ không bị cảnh báo gần như không giúp: khi máy trôi, hầu hết chu kỳ đều bị cảnh báo nên không có gì để học. Phải có kỹ sư bấm \"Báo nhầm\" / \"Bình thường mới\" thì mới đỡ (≈ 40% thay vì 44%).",
           "- Chỉ có 9 lần chạy lỗi rơi vào nửa sau, quá ít để nói chắc về tỉ lệ bắt lỗi.",
           "- Số mô hình và cách chọn ngưỡng khác báo cáo cũ (bosch_cnc.md), nên hai báo cáo không so trực tiếp được.",
           ]
    p = os.path.join(HERE, "reports", "edge_bosch.md")
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("Đã ghi", p)


if __name__ == "__main__":
    main()
