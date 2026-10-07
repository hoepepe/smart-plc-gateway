"""
doc_plc_thu.py — Bước thử đầu tiên: laptop đọc thẳng PLC Mitsubishi, chưa cần ESP32.

Sơ đồ:  Laptop ══ cáp mạng (hoặc bộ chuyển USB→Ethernet) ══ PLC

Đặt IP tĩnh cho cổng mạng của laptop cùng dải với PLC, ví dụ 192.168.10.10.
Chạy:   pip install pymcprotocol
        python doc_plc_thu.py
        python doc_plc_thu.py --ip 127.0.0.1    # thử với plc_gia_lap.py

Nếu bước này chạy được thì PLC đã cài đúng; lỗi ở ESP32 sau đó chắc chắn nằm phía gateway.
Chỉ có lệnh đọc — không ghi gì vào PLC.
"""
import argparse
import time

import pymcprotocol

ap = argparse.ArgumentParser()
ap.add_argument("--ip", default="192.168.10.21", help="IP của PLC")
ap.add_argument("--port", type=int, default=5000, help="cổng MC protocol trong Open Setting")
a = ap.parse_args()

plc = pymcprotocol.Type3E(plctype="Q")
plc.connect(a.ip, a.port)
print(f"Đã nối PLC {a.ip}:{a.port}. Ctrl+C để dừng.\n")

try:
    while True:
        d = plc.batchread_wordunits(headdevice="D100", readsize=4)
        m = plc.batchread_wordunits(headdevice="M0", readsize=1)[0]
        bits = "".join(str((m >> b) & 1) for b in range(6))
        print(f"D100..D103 = {d}    M0..M5 = {bits}")
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    plc.close()
