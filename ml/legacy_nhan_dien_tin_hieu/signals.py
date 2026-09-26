"""
signals.py — Sinh tín hiệu mô phỏng và dựng bộ dữ liệu.

ĐIỂM QUAN TRỌNG NHẤT trong file này: hàm build_dataset() tách tập theo PHIÊN,
không tách ngẫu nhiên theo cửa sổ.

Vì sao: các cửa sổ liền kề trong cùng một phiên thu thập rất giống nhau
(cùng biên độ, cùng nhiễu nền, cùng điều kiện). Nếu tách ngẫu nhiên,
cửa sổ số 10 vào tập train và cửa sổ số 11 vào tập test — mô hình gần như
đang được chấm trên dữ liệu nó đã thấy. Độ chính xác sẽ đẹp giả tạo.

Tách theo phiên = mô phỏng đúng tình huống thật: mô hình gặp một lần
thu thập hoàn toàn mới.
"""

import numpy as np

WINDOW = 400          # 2 giây @ 200 Hz
FS = 200.0

# 4 lớp dùng để huấn luyện
KNOWN_CLASSES = ["TEMPERATURE", "VIBRATION", "COUNTER", "MOTOR_LOAD"]

# Lớp KHÔNG dùng để huấn luyện — chỉ dùng kiểm tra cơ chế phát hiện tín hiệu lạ.
# Đây là phép thử phân biệt hệ thống thật với hệ thống học thuộc lòng.
OOD_CLASS = "PRESSURE_BURST"

# Các dạng tín hiệu BẤT THƯỜNG do lỗi lắp đặt hoặc thiết bị xuống cấp.
# Không lớp nào trong đây được dùng để huấn luyện — chúng dùng để kiểm tra
# xem cơ chế one-class có bắt được các tình huống thực tế hay không.
FAULT_CLASSES = {
    "REVERSED_POLARITY": "Đấu ngược cực — tín hiệu lật quanh mức giữa",
    "LOOSE_WIRE":        "Dây lỏng — tín hiệu gián đoạn, rơi về 0 từng đoạn",
    "SATURATED":         "Tín hiệu bão hòa — chạm trần dải đo, mất thông tin",
    "DEAD_CHANNEL":      "Kênh chết — chỉ còn nhiễu nền quanh 0",
    "WHITE_NOISE":       "Nhiễu trắng thuần — không có cấu trúc",
}


# Độ khó của dữ liệu mô phỏng.
#   "easy"    — tín hiệu sạch, các lớp tách nhau rõ (cho kết quả ~100%, KHÔNG dùng để báo cáo)
#   "realistic" — có nhiễu nền, trôi nhiệt, gai xung, dải tham số chồng lấn giữa các lớp
# Mặc định để "realistic" vì đây mới là con số đáng đưa vào pitch deck.
DIFFICULTY = "realistic"


def _add_realism(x, rng, n, noise_scale):
    """Thêm các hiện tượng luôn có ở tín hiệu công nghiệp thật.

    Bốn thứ được mô phỏng:
      - trôi nền chậm  : nhiệt độ môi trường thay đổi, cảm biến lệch chuẩn theo thời gian
      - nhiễu 50 Hz    : nhiễu từ lưới điện xoay chiều lẫn vào dây tín hiệu
      - gai xung ngẫu nhiên : đóng cắt contactor, động cơ khởi động
      - mẫu lỗi        : ADC đọc hụt, dây tiếp xúc kém
    """
    t = np.arange(n)

    drift = rng.uniform(-4, 4) * np.sin(t / (n * rng.uniform(0.6, 1.4)) + rng.uniform(0, 6))
    hum = rng.uniform(0.4, 1.6) * noise_scale * np.sin(t * rng.uniform(1.4, 1.7))

    spikes = np.zeros(n)
    for _ in range(rng.integers(0, 4)):
        i = int(rng.integers(0, n))
        spikes[i:i + int(rng.integers(1, 3))] += rng.normal(0, 6) * noise_scale

    y = x + drift + hum + spikes

    # vài mẫu bị giữ nguyên giá trị trước đó (ADC đọc hụt)
    for _ in range(rng.integers(0, 3)):
        i = int(rng.integers(1, n))
        k = int(rng.integers(2, 6))
        y[i:i + k] = y[i - 1]

    return y


def _gen(kind, n, rng, offset, amp_scale, noise_scale):
    """Sinh n mẫu. offset/amp_scale/noise_scale thay đổi theo phiên để mô phỏng
    sự khác biệt giữa các lần thu thập (khác cảm biến, khác vị trí gắn, khác nhiệt độ môi trường)."""
    t = np.arange(n)
    hard = DIFFICULTY == "realistic"

    if kind == "TEMPERATURE":
        base = offset + amp_scale * (9 * np.sin(t / 95.0 + rng.uniform(0, 6))
                                     + 2.5 * np.sin(t / 31.0))
        # thực tế: nhiệt độ có gợn do quạt gió, bơm tuần hoàn
        if hard:
            base = base + amp_scale * rng.uniform(0, 2.0) * np.sin(t / rng.uniform(4, 9))
        noise = rng.normal(0, (2.2 if hard else 0.6) * noise_scale, n)

    elif kind == "VIBRATION":
        # dải tần rộng hơn, chồng lấn với MOTOR_LOAD ở vùng biên
        f1 = rng.uniform(0.75, 2.6) if hard else rng.uniform(0.75, 1.35)
        f2 = rng.uniform(0.45, 1.3) if hard else rng.uniform(0.45, 0.75)
        amp = rng.uniform(7, 16) if hard else 16
        base = offset + amp_scale * (amp * np.sin(t / f1) + 6 * np.sin(t / f2))
        noise = rng.normal(0, 4.0 * noise_scale, n)

    elif kind == "COUNTER":
        period = int(rng.integers(48, 80))
        step = max(1, period // 4)
        base = offset + amp_scale * (np.floor((t % period) / step) * 19)
        # thực tế: cạnh xung không vuông tuyệt đối, có thời gian lên/xuống
        if hard:
            k = int(rng.integers(2, 5))
            base = np.convolve(base, np.ones(k) / k, mode="same")
        noise = rng.normal(0, (1.4 if hard else 0.5) * noise_scale, n)

    elif kind == "MOTOR_LOAD":
        # chu kỳ tải chồng lấn với vùng tần số thấp của VIBRATION
        cyc = rng.uniform(6.0, 17.0) if hard else rng.uniform(11.0, 17.0)
        base = offset + amp_scale * (11 * np.sin(t / cyc)
                                     + 4 * np.sin(t / (cyc * 2.7)))
        noise = rng.normal(0, (3.4 if hard else 2.2) * noise_scale, n)

    elif kind == "REVERSED_POLARITY":
        # Đấu ngược hai đầu dây: điện áp đảo dấu so với chuẩn.
        # Tín hiệu 0-10V trở thành -10..0V, tức là rơi hẳn ra ngoài dải hợp lệ.
        # Đặc trưng thống kê (độ lệch chuẩn, tần suất cắt mức, tốc độ biến thiên)
        # gần như giữ nguyên, nên MÔ HÌNH không phát hiện được —
        # chỉ luật kiểm tra dải tuyệt đối mới bắt được.
        cyc = rng.uniform(11.0, 17.0)
        normal = offset + amp_scale * (11 * np.sin(t / cyc) + 4 * np.sin(t / (cyc * 2.7)))
        base = -normal                                       # đảo dấu quanh 0V
        noise = rng.normal(0, 2.2 * noise_scale, n)

    elif kind == "LOOSE_WIRE":
        # Tiếp xúc kém: tín hiệu bình thường xen kẽ những đoạn rơi hẳn về 0
        base = offset + amp_scale * 9 * np.sin(t / 60.0)
        i = 0
        while i < n:
            gap = int(rng.integers(20, 60))
            drop = int(rng.integers(5, 20))
            s0, e0 = min(i + gap, n), min(i + gap + drop, n)
            base[s0:e0] = rng.normal(0, 1.5, max(0, e0 - s0))
            i = e0 + 1
        noise = rng.normal(0, 1.0 * noise_scale, n)

    elif kind == "SATURATED":
        # Quá dải đo: đỉnh bị cắt phẳng, mất thông tin ở hai đầu
        raw = offset + amp_scale * 40 * np.sin(t / rng.uniform(8, 20))
        hi = float(np.percentile(raw, 72))
        lo = float(np.percentile(raw, 28))
        base = np.clip(raw, lo, hi)
        noise = rng.normal(0, 0.8 * noise_scale, n)

    elif kind == "DEAD_CHANNEL":
        # Cảm biến hỏng hoặc chưa đấu: chỉ còn nhiễu nền quanh 0
        base = np.full(n, rng.uniform(0, 2.5))
        noise = rng.normal(0, 0.9 * noise_scale, n)

    elif kind == "WHITE_NOISE":
        # Nhiễu thuần, không có cấu trúc tuần hoàn nào
        base = np.full(n, offset)
        noise = rng.normal(0, 14 * noise_scale, n)

    elif kind == "PRESSURE_BURST":
        # dạng chưa từng huấn luyện: im lặng dài xen kẽ burst đột ngột
        base = np.full(n, offset, dtype=float)
        i = 0
        while i < n:
            gap = int(rng.integers(55, 110))
            blen = int(rng.integers(8, 18))
            s = min(i + gap, n)
            e = min(s + blen, n)
            if s < n:
                base[s:e] += amp_scale * rng.uniform(35, 65)
            i = e + 1
        noise = rng.normal(0, 1.2 * noise_scale, n)

    else:
        raise ValueError(f"Loại tín hiệu không nhận ra: {kind}")

    out = base + noise
    if DIFFICULTY == "realistic":
        out = _add_realism(out, rng, n, noise_scale)
    return out


def make_session(kind, n_windows, seed):
    """Một 'phiên thu thập': cùng cảm biến, cùng điều kiện, sinh liên tục.
    Trả về list các cửa sổ."""
    rng = np.random.default_rng(seed)
    offset = rng.uniform(28, 62)
    amp_scale = rng.uniform(0.82, 1.22)
    noise_scale = rng.uniform(0.7, 1.4)

    total = n_windows * WINDOW
    stream = _gen(kind, total, rng, offset, amp_scale, noise_scale)
    return [stream[i * WINDOW:(i + 1) * WINDOW] for i in range(n_windows)]


def build_dataset(train_sessions=4, test_sessions=2, windows_per_session=12, seed=7):
    """
    Trả về dict gồm:
      X_train, y_train  — tách theo phiên, không trùng phiên với test
      X_test,  y_test   — phiên hoàn toàn mới, mô hình chưa từng thấy
      X_ood             — lớp chưa hề huấn luyện, để kiểm tra phát hiện tín hiệu lạ
    """
    from features import extract_batch

    Xtr, ytr, Xte, yte = [], [], [], []
    sid = seed * 1000

    for cls in KNOWN_CLASSES:
        for s in range(train_sessions):
            sid += 1
            w = make_session(cls, windows_per_session, sid)
            Xtr.append(extract_batch(w, FS))
            ytr += [cls] * len(w)
        for s in range(test_sessions):
            sid += 1
            w = make_session(cls, windows_per_session, sid)
            Xte.append(extract_batch(w, FS))
            yte += [cls] * len(w)

    ood_windows = []
    for s in range(test_sessions + 1):
        sid += 1
        ood_windows += make_session(OOD_CLASS, windows_per_session, sid)
    X_ood = extract_batch(ood_windows, FS)

    return {
        "X_train": np.vstack(Xtr), "y_train": np.array(ytr),
        "X_test": np.vstack(Xte),  "y_test": np.array(yte),
        "X_ood": X_ood,
    }
