"""
features.py — Trích đặc trưng tín hiệu, dùng chung cho toàn dự án.

Module này là "hợp đồng" giữa 3 phần việc:
  - Duy  : train mô hình trên đặc trưng từ đây
  - Tuấn : port logic này sang C++ cho ESP32 (giữ ĐÚNG thứ tự đặc trưng)
  - Đức  : backend tính lại đặc trưng khi cần kiểm tra chéo

QUY TẮC BẤT DI BẤT DỊCH:
  Thứ tự trong FEATURE_NAMES không được đổi. Nếu thêm đặc trưng mới,
  thêm vào CUỐI danh sách và tăng FEATURE_VERSION.
  Mô hình train bằng version nào chỉ dùng được với version đó.
"""

import numpy as np

FEATURE_VERSION = 1

FEATURE_NAMES = [
    # --- miền thời gian ---
    "mean", "std", "rms", "slew_mean", "slew_max",
    "zcr", "n_levels", "kurtosis", "skewness", "peak_to_peak",
    # --- miền tần số ---
    "dom_freq", "spec_centroid", "spec_entropy", "lowband_ratio",
    # --- tương quan ---
    "acf_lag1", "acf_lag20",
]

N_FEATURES = len(FEATURE_NAMES)


def _autocorr(x_centered, lag, denom):
    if lag >= len(x_centered) or denom == 0:
        return 0.0
    return float(np.dot(x_centered[:-lag], x_centered[lag:]) / denom)


def extract(window, fs=200.0, normalize=True):
    """
    window : list/array giá trị thô của MỘT cửa sổ (mặc định 2 giây @200Hz = 400 mẫu)
    fs     : tần số lấy mẫu (Hz)
    normalize : chuẩn hóa biên độ về [0,1] trước khi tính.
                BẬT mặc định vì tín hiệu PLC thật có thang đo khác hẳn cảm biến demo —
                đây là điều kiện để mô hình chuyển được từ demo sang thực tế.

    Trả về np.ndarray shape (N_FEATURES,) theo ĐÚNG thứ tự FEATURE_NAMES.
    """
    x = np.asarray(window, dtype=np.float64)
    if x.size < 8:
        raise ValueError("Cửa sổ quá ngắn, cần ít nhất 8 mẫu")

    raw_ptp = float(np.ptp(x))

    if normalize:
        rng = raw_ptp if raw_ptp > 1e-9 else 1.0
        x = (x - x.min()) / rng

    n = x.size
    mean = float(x.mean())
    std = float(x.std())
    rms = float(np.sqrt(np.mean(x ** 2)))

    d = np.abs(np.diff(x))
    slew_mean = float(d.mean())
    slew_max = float(d.max())

    centered = x - mean
    zcr = float(np.count_nonzero(np.diff(np.signbit(centered))) / n)

    # số mức rời rạc: phân biệt tín hiệu bậc thang với tín hiệu liên tục
    n_levels = int(len(np.unique(np.round(x, 2))))

    s = std if std > 1e-9 else 1.0
    kurtosis = float(np.mean((centered / s) ** 4))
    skewness = float(np.mean((centered / s) ** 3))
    peak_to_peak = float(np.ptp(x))

    # --- phổ ---
    win = x * np.hanning(n)
    spec = np.abs(np.fft.rfft(win))[1:]          # bỏ thành phần DC
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)[1:]
    tot = float(spec.sum())

    if tot > 1e-12:
        p = spec / tot
        dom_freq = float(freqs[int(np.argmax(spec))])
        spec_centroid = float(np.dot(freqs, p))
        spec_entropy = float(-np.sum(p * np.log(p + 1e-12)) / np.log(len(p)))
        cutoff = len(freqs) // 4
        lowband_ratio = float(spec[:cutoff].sum() / tot)
    else:
        dom_freq = spec_centroid = spec_entropy = 0.0
        lowband_ratio = 1.0

    denom = float(np.dot(centered, centered))
    acf1 = _autocorr(centered, 1, denom)
    acf20 = _autocorr(centered, 20, denom)

    return np.array([
        mean, std, rms, slew_mean, slew_max,
        zcr, n_levels, kurtosis, skewness, peak_to_peak,
        dom_freq, spec_centroid, spec_entropy, lowband_ratio,
        acf1, acf20,
    ], dtype=np.float64)


def extract_batch(windows, fs=200.0, normalize=True):
    return np.vstack([extract(w, fs, normalize) for w in windows])


def as_dict(vec):
    return {k: round(float(v), 5) for k, v in zip(FEATURE_NAMES, vec)}
