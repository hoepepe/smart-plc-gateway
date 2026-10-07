"""
plc_gia_lap.py — PLC Mitsubishi GIẢ LẬP trên laptop, trả lời lệnh đọc MC protocol (khung 3E nhị phân).

Dùng khi chưa có PLC thật, hoặc PLC thật chưa có chương trình tạo dữ liệu.

    python plc_gia_lap.py                 # chờ ở cổng 5000
    python plc_gia_lap.py --port 5001

Bảng thanh ghi giống máy M01 trong src/data/machines.ts:
    D100     lực ép, đơn vị 0,01 kN (số nguyên có dấu)
    D102     chiều cao ép, đơn vị 0,01 mm
    D110     mã lỗi (0 = không lỗi, 102 = cảm biến phôi không tác động)
    M0..M5   dừng · chuẩn bị · auto · đang làm việc · hoàn thành · báo lỗi

Dữ liệu phát lại đúng các chu kỳ ép từ ml/cycles.py (cùng bộ sinh đã dùng để huấn luyện),
100 mẫu mỗi giây. Cứ vài chu kỳ chèn một chu kỳ lỗi — PLC KHÔNG báo lỗi ở chu kỳ này,
chỉ AI mới phát hiện. Thỉnh thoảng máy báo lỗi thật (M5 + D110) trong vài giây.

Chỉ hỗ trợ lệnh đọc liên tiếp theo word (0x0401 / 0x0000) với thanh ghi D và M.
Khi trình bày phải nói rõ đây là giả lập, không gọi là PLC thật.
"""
import argparse
import os
import random
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))
import cycles as C  # noqa: E402

RATE = 100            # mẫu mỗi giây — trùng tần số dữ liệu huấn luyện
GAP_S = 1.0           # nghỉ giữa hai chu kỳ
FAULT_EVERY = 6       # mỗi 6 chu kỳ chèn một chu kỳ lỗi (AI phải tự phát hiện)
ERROR_EVERY = 15      # mỗi 15 chu kỳ máy báo lỗi thật vài giây
ERROR_S = 4.0
DEV_D, DEV_M = 0xA8, 0x90

state = {"d": {}, "m": 0}
lock = threading.Lock()


def to_word(v):
    """Số nguyên có dấu → word 16 bit (bù hai), như PLC lưu."""
    return int(v) & 0xFFFF


def player():
    """Phát lại chu kỳ ép theo thời gian thật, cập nhật thanh ghi."""
    normal = [y for s in range(900, 906) for y in C.make_session("PRESS_FORCE", 25, s)]
    faults = {f: C.make_session("PRESS_FORCE", 10, 950, fault=f)
              for f in ["MISSING_PART", "MISALIGNED", "DOUBLE_HIT"]}
    k = 0
    while True:
        k += 1
        if k % ERROR_EVERY == 0:
            with lock:
                state["m"] = (1 << 5)                       # chỉ bật M5: báo lỗi
                state["d"] = {100: 0, 102: 0, 110: 102}
            print(f"[giả lập] Máy BÁO LỖI E102 trong {ERROR_S:.0f} giây")
            time.sleep(ERROR_S)
            continue

        if k % FAULT_EVERY == 0:
            name = random.choice(list(faults))
            y = random.choice(faults[name])
            print(f"[giả lập] Chu kỳ #{k}: LỖI {name} — PLC không báo, xem AI có bắt được không")
        else:
            y = random.choice(normal)

        t0 = time.time()
        for i, v in enumerate(y):
            with lock:
                state["m"] = (1 << 2) | (1 << 3)            # auto + đang làm việc
                state["d"] = {100: to_word(round(v * 100)), 102: to_word(2500), 110: 0}
            target = t0 + (i + 1) / RATE
            time.sleep(max(0.0, target - time.time()))

        with lock:
            state["m"] = (1 << 2) | (1 << 4)                # auto + hoàn thành
            state["d"] = {100: to_word(0), 102: to_word(2500), 110: 0}
        time.sleep(GAP_S)


def handle(conn, addr):
    print(f"[giả lập] Có kết nối từ {addr[0]}")
    with conn:
        while True:
            try:
                req = conn.recv(1024)
            except OSError:
                break
            if not req:
                break
            if len(req) < 21 or req[0:2] != b"\x50\x00":
                continue
            cmd, sub = struct.unpack("<HH", req[11:15])
            dev_no = int.from_bytes(req[15:18], "little")
            dev_code, pts = req[18], struct.unpack("<H", req[19:21])[0]

            if cmd == 0x0401 and sub == 0x0000 and dev_code in (DEV_D, DEV_M) and pts <= 64:
                with lock:
                    if dev_code == DEV_D:
                        words = [state["d"].get(dev_no + j, 0) for j in range(pts)]
                    else:
                        words = [(state["m"] >> (dev_no + 16 * j)) & 0xFFFF if dev_no + 16 * j < 16 else 0
                                 for j in range(pts)]
                body = b"\x00\x00" + b"".join(struct.pack("<H", w & 0xFFFF) for w in words)
            else:
                body = b"\x59\xC0"                           # lệnh không hỗ trợ
            conn.sendall(b"\xd0\x00\x00\xff\xff\x03\x00" + struct.pack("<H", len(body)) + body)
    print(f"[giả lập] {addr[0]} ngắt kết nối")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5000)
    a = ap.parse_args()

    threading.Thread(target=player, daemon=True).start()
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.port))
    srv.listen(4)
    print(f"[giả lập] PLC giả lập chờ ở cổng {a.port}. Ctrl+C để dừng.")
    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


if __name__ == "__main__":
    main()
