"""
detector.py — Bộ phát hiện chu kỳ bất thường dùng chung cho mọi máy.

Thuật toán GIỐNG NHAU cho mọi máy. Mỗi máy (và mỗi mã hàng) chỉ khác "chuẩn bình thường" học được:
vector trung bình, ma trận hiệp phương sai, trung vị / MAD từng đặc trưng và hai ngưỡng.

Hai tầng chấm điểm:
  - Mahalanobis: chu kỳ lệch khỏi "đám mây" chu kỳ bình thường (bắt lỗi làm sai quan hệ giữa các đặc trưng)
  - MAD: đặc trưng lệch xa nhất so với trung vị của chính nó (bắt lỗi chỉ làm lệch một đại lượng, bền khi ít dữ liệu)
Báo bất thường nếu một trong hai vượt ngưỡng. Ngưỡng chọn trên tập hiệu chuẩn riêng, không nhìn dữ liệu lỗi.
"""
import os
import sys
import time

import numpy as np
from sklearn.covariance import LedoitWolf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml"))
import cycles as C  # noqa: E402

FEATURES = C.FEATURES + ["duration_s", "n_prominent", "late_level", "mid_jerk"]
FEATURES_VI = {
    "peak": "giá trị đỉnh", "trough": "giá trị đáy", "t_peak": "thời điểm đạt đỉnh",
    "mean_level": "mức trung bình", "rise_slope": "độ dốc lên", "roughness": "độ gồ ghề",
    "n_peaks": "số đỉnh", "early_level": "mức đoạn đầu", "mid_level": "mức đoạn giữa",
    "duration_s": "thời gian chu kỳ",
    "n_prominent": "số đỉnh rõ rệt", "late_level": "mức đoạn cuối", "mid_jerk": "độ giật đoạn giữa",
}
RATE = C.FS
PCT = 99.5
BLOCKS = 5       # số khối liên tiếp khi kiểm định chéo để chọn ngưỡng
ROBUST_Z = 5.0   # ngưỡng lọc chu kỳ nghi lỗi trong dữ liệu học


def features(y, duration_s=None):
    """Đặc trưng của một chu kỳ: 9 đặc trưng hình dạng (ml/cycles.py) + thời gian chu kỳ + 3 đặc trưng chống nhiễu.

    3 đặc trưng thêm tính trên tín hiệu đã làm mượt nên không bị nhiễu điện đánh lừa:
      n_prominent — số đỉnh rõ rệt (lên trên 75% biên độ rồi xuống dưới 45% mới tính đỉnh tiếp): bắt ép hai lần, siết hai lần
      late_level  — mức trung bình đoạn 60–90% chu kỳ: bắt lỗi xảy ra cuối chu kỳ (gãy dao, nhả lực sớm)
      mid_jerk    — độ giật đoạn 30–70% so với biên độ: bắt van kẹt, rung, giật cục
    """
    y = np.asarray(y, dtype=float)
    d = len(y) / RATE if duration_s is None else float(duration_s)
    return np.r_[C.extract(y), d, _robust(y)]


def _robust(y):
    n = len(y)
    k = max(3, n // 30)
    ys = np.convolve(y, np.ones(k) / k, mode="same")
    lo, hi = np.percentile(ys, 2), np.percentile(ys, 98)
    r = (hi - lo) or 1.0
    cnt, armed = 0, True
    for v in ys[k:-k]:
        if armed and v > lo + 0.75 * r:
            cnt += 1; armed = False
        elif not armed and v < lo + 0.45 * r:
            armed = True
    late = float(ys[int(n * 0.6):int(n * 0.9)].mean())
    a, b = int(n * 0.3), int(n * 0.7)
    mid = float(np.mean(np.abs(np.diff(ys[a:b]))) / r * n)
    return [cnt, late, mid]


def train(X, recipe="*", pct=PCT):
    """Học chuẩn bình thường từ các chu kỳ bình thường X (n × d), theo thứ tự thời gian.

    Lọc chu kỳ nghi lỗi → học trên toàn bộ phần sạch → chọn ngưỡng bằng kiểm định chéo theo khối thời gian.
    Trả về dict lưu được thành JSON.
    """
    X = np.asarray(X, dtype=float)
    if len(X) < 20:
        raise ValueError(f"Cần ít nhất 20 chu kỳ bình thường để học, mới có {len(X)}")
    # Lúc học máy vẫn có thể ra vài chu kỳ lỗi mà không ai biết. Lọc bền vững trước khi học:
    # bỏ chu kỳ có đặc trưng lệch quá 5 lần MAD so với trung vị (trung vị/MAD ít bị vài điểm lỗi kéo lệch).
    med0 = np.median(X, axis=0)
    mad0 = np.median(np.abs(X - med0), axis=0) * 1.4826
    sd0 = X.std(axis=0)
    sc0 = np.where(mad0 > 1e-9, mad0, np.where(sd0 > 1e-9, sd0, np.maximum(np.abs(med0) * 0.02, 1e-3)))
    z0 = np.max(np.abs(X - med0) / sc0, axis=1)
    keep = z0 <= ROBUST_Z
    if keep.mean() < 0.8:                      # không bỏ quá 20%: giữ 80% chu kỳ gần trung vị nhất
        keep = z0 <= np.quantile(z0, 0.8)
    dropped = int((~keep).sum())
    X = X[keep]
    n = len(X)
    m = _fit(X, recipe)
    # Ngưỡng: kiểm định chéo theo KHỐI LIÊN TIẾP (mỗi khối ≈ một khoảng thời gian / một ca).
    # Học trên các khối còn lại, chấm khối để riêng → điểm "chưa từng thấy" mang cả biến động giữa các ca,
    # nên ngưỡng không bị chặt quá như khi chỉ lấy đoạn cuối làm hiệu chuẩn.
    k = BLOCKS if n >= BLOCKS * 8 else 2
    edges = np.linspace(0, n, k + 1).astype(int)
    oof_m, oof_r = [], []
    for i in range(k):
        te = np.arange(edges[i], edges[i + 1])
        tr = np.setdiff1d(np.arange(n), te)
        mi = _fit(X[tr], recipe)
        oof_m.append(_maha(mi, X[te])); oof_r.append(_robz(mi, X[te]))
    sm, sr = np.concatenate(oof_m), np.concatenate(oof_r)
    m["t_maha"] = float(np.percentile(sm, pct))
    m["t_robz"] = float(np.percentile(sr, pct))
    m["calib_false_alarm"] = float(((sm > m["t_maha"]) | (sr > m["t_robz"])).mean())
    m.update(n_train=int(n), n_calib=int(n), n_dropped=dropped, blocks=int(k))
    return m


def _fit(X, recipe):
    mu = X.mean(axis=0)
    inv = np.linalg.inv(LedoitWolf().fit(X).covariance_)
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0) * 1.4826
    sd = X.std(axis=0)
    # đặc trưng gần như hằng số (vd. số đỉnh) → MAD = 0: dùng độ lệch chuẩn, rồi sàn theo độ lớn
    scale = np.where(mad > 1e-9, mad, np.where(sd > 1e-9, sd, np.maximum(np.abs(med) * 0.02, 1e-3)))
    return dict(recipe=str(recipe), features=FEATURES, mu=mu.tolist(), inv_cov=inv.tolist(),
                med=med.tolist(), scale=scale.tolist(), sd=sd.tolist(), created=time.time(),
                duration_med=float(med[-1]))


def _arr(m, k):
    return np.asarray(m[k], dtype=float)


def _maha(m, X):
    D = np.atleast_2d(X) - _arr(m, "mu")
    return np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", D, _arr(m, "inv_cov"), D), 0))


def _robz(m, X):
    return np.max(np.abs(np.atleast_2d(X) - _arr(m, "med")) / _arr(m, "scale"), axis=1)


def score(m, f):
    """Chấm một chu kỳ. Trả về điểm chuẩn hoá (1,0 = đúng ngưỡng) và 3 đặc trưng lệch nhiều nhất."""
    f = np.asarray(f, dtype=float)[:len(m["mu"])]     # mô hình học từ phiên bản cũ có ít đặc trưng hơn
    a = float(_maha(m, f)[0])
    z = np.abs(f - _arr(m, "med")) / _arr(m, "scale")
    r = float(z.max())
    norm = max(a / m["t_maha"], r / m["t_robz"])
    order = np.argsort(-z)[:3]
    top = [dict(feature=FEATURES[i], vi=FEATURES_VI.get(FEATURES[i], FEATURES[i]),
                z=round(float(z[i]), 2), value=round(float(f[i]), 4), normal=round(float(m["med"][i]), 4))
           for i in order]
    return dict(maha=round(a, 3), robz=round(r, 3), norm=round(norm, 3), flag=bool(norm > 1.0), top=top)


def shift(old, new):
    """Chuẩn mới lệch bao nhiêu so với chuẩn cũ — tính bằng Mahalanobis của trung bình mới dưới chuẩn cũ,
    chia căn số chiều (≈ số độ lệch chuẩn trung bình mỗi đặc trưng)."""
    d = min(len(old["mu"]), len(new["mu"]))
    o = {**old, "mu": old["mu"][:d], "inv_cov": [row[:d] for row in old["inv_cov"][:d]]}
    return float(_maha(o, np.asarray(new["mu"][:d]))[0] / np.sqrt(d))
