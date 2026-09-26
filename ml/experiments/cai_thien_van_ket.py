"""
cai_thien_van_ket.py — Thí nghiệm cải thiện phát hiện lỗi VAN KẸT (áp lực khí nén).

Chạy:  cd ml && python experiments/cai_thien_van_ket.py

VẤN ĐỀ
    Mô hình hiện tại chỉ bắt được khoảng 33–60% chu kỳ van kẹt (con số thay đổi
    theo cách chia ca). Đây là điểm yếu duy nhất đáng kể của bộ phát hiện.

ĐÃ THỬ VÀ THẤT BẠI (giữ lại để khỏi thử lại)
    - Đếm số bước nhảy lớn       : 59% -> 61%   (đoạn tụt áp bình thường cũng dốc, bị đếm nhầm)
    - Độ dao động sau làm mượt   : 59% -> 60%   (cửa sổ làm mượt trùng thang thời gian của lỗi)
    - Số lần đổi chiều           : 59% -> 64%   (nhiễu làm chu kỳ bình thường cũng đổi chiều nhiều)
    - Năng lượng dải 4-10 nhịp   : 59% -> 60%   (!!! xem phát hiện bên dưới)

PHÁT HIỆN THEN CHỐT
    Riêng đặc trưng "năng lượng dải 4-10 nhịp", dùng MỘT ngưỡng đơn, bắt được 97% van kẹt.
    Nhưng gộp vào khoảng cách Mahalanobis 10 chiều thì tụt còn 60%.

    Lý do: một đặc trưng lệch mạnh bị 9 đặc trưng bình thường còn lại "pha loãng"
    trong khoảng cách tổng. Đặc trưng đúng — cách GỘP mới là vấn đề.

GIẢI PHÁP ĐÃ KIỂM CHỨNG
    Hai tầng kiểm tra, báo bất thường nếu MỘT trong hai vượt ngưỡng:
      1. Khoảng cách Mahalanobis (bắt lệch tổng thể, nhiều đặc trưng cùng lệch nhẹ)
      2. Độ lệch lớn nhất của TỪNG đặc trưng (bắt một đặc trưng lệch mạnh)
    Cả hai ngưỡng hiệu chuẩn trên ca hiệu chuẩn, không nhìn tập kiểm tra.

    Kết quả: van kẹt 60% -> 93%, áp lực khí nén không tăng báo động giả.
    ĐÁNH ĐỔI PHẢI BÁO CÁO: báo động giả của lực xiết tăng 1,3% -> 2,7%.

VIỆC CẦN LÀM ĐỂ ĐƯA VÀO SẢN PHẨM
    1. Thêm band_energy() vào extract() trong cycles.py (thành 10 đặc trưng)
    2. Thêm tầng "lệch từng đặc trưng" vào bộ phát hiện, xuất mu/sd/ngưỡng vào cycles.json
    3. Cập nhật src/utils/detector.ts cho khớp — THỨ TỰ ĐẶC TRƯNG PHẢI TRÙNG với Python
    4. Chạy lại cycles.py, cập nhật số liệu trên dashboard
    5. Sửa docstring lớp Mahalanobis đang ghi "ma trận 7x7" (thực tế 9x9, sau cải tiến 10x10)
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cycles as C  # noqa: E402


def band_energy(y):
    """Tỷ lệ năng lượng ở dải 4-10 nhịp mỗi chu kỳ.

    Van kẹt làm áp lực dao động có nhịp đều khoảng 5-7 lần mỗi chu kỳ.
    Chu kỳ bình thường chỉ tụt một lần rồi hồi, năng lượng dồn ở dải 1-3 nhịp.
    """
    y = np.asarray(y, float)
    y = y - y.mean()
    p = np.abs(np.fft.rfft(y)) ** 2
    tot = p[1:].sum() or 1e-12
    return float(p[4:11].sum() / tot)


def feats(y):
    return np.append(C.extract(y), band_energy(y))


FAULTS = {
    "PRESS_FORCE": ["MISSING_PART", "MISALIGNED", "DOUBLE_HIT"],
    "TORQUE": ["STRIPPED", "CROSS_THREAD", "NOT_SEATED"],
    "AIR_PRESSURE": ["LEAK", "LOW_SUPPLY", "VALVE_STICK"],
}


def main():
    print(f"{'':14}{'Chỉ Mahalanobis':>36}   {'Mahalanobis + lệch từng đặc trưng':>42}")
    for proc, fl in FAULTS.items():
        def mk(seeds, f=None):
            return np.vstack([feats(y) for s in seeds
                              for y in C.make_session(proc, 25, s, fault=f)])

        # tách theo ca: huấn luyện / hiệu chuẩn / kiểm tra — không ca nào dùng chung
        tr, ca, te = mk(range(100, 120)), mk(range(300, 306)), mk(range(500, 506))

        m = C.Mahalanobis().fit(tr)
        mu, sd = tr.mean(0), tr.std(0) + 1e-9

        def zmax(X):
            return np.max(np.abs((X - mu) / sd), axis=1)

        th_m = np.percentile(m.score(ca), 99.5)
        th_z = np.percentile(zmax(ca), 99.5)

        def only_m(X):
            return m.score(X) > th_m

        def combined(X):
            return (m.score(X) > th_m) | (zmax(X) > th_z)

        r1 = [only_m(mk(range(700, 704), f)).mean() for f in fl]
        r2 = [combined(mk(range(700, 704), f)).mean() for f in fl]
        s1 = " ".join(f"{v*100:4.0f}%" for v in r1) + f" | giả {only_m(te).mean()*100:.1f}%"
        s2 = " ".join(f"{v*100:4.0f}%" for v in r2) + f" | giả {combined(te).mean()*100:.1f}%"
        print(f"{proc:14}{s1:>36}   {s2:>42}")

    print("\nCột theo thứ tự:", FAULTS)


if __name__ == "__main__":
    main()
