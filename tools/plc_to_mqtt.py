"""
plc_to_mqtt.py — Cầu nối đưa dữ liệu PLC lên dashboard khi CHƯA có switch.

Hai cách lấy dữ liệu:

  1. Qua ESP32 (cách dùng khi thử gateway):
        PLC ══ cáp mạng ══ W5500 ── ESP32 ── cáp USB ── Laptop
     ESP32 nạp firmware/gateway_serial, gửi số liệu qua cổng USB.
        python plc_to_mqtt.py --serial COM5          (Windows; Linux/Mac: /dev/ttyUSB0)

  2. Laptop đọc thẳng PLC (không cần ESP32):
        PLC ══ cáp mạng ══ Laptop
        python plc_to_mqtt.py --plc 192.168.10.21

Sau đó: chạy Mosquitto (có bật cổng WebSocket 9001), mở dashboard — Navbar hiện đã kết nối.

Script làm bốn việc, giống hệt việc gateway sẽ tự làm khi có switch:
  - Đọc cờ M0–M5 → trạng thái máy, gửi lên khi trạng thái đổi (kèm mã lỗi D110)
  - Cắt chu kỳ theo cờ M3 "đang làm việc": bật là bắt đầu, tắt là kết thúc
  - Nội suy chu kỳ về đúng 100 mẫu/giây theo dấu thời gian thật — tần số dữ liệu huấn luyện,
    nếu không thì độ dốc, độ gồ ghề lệch đi và mô hình báo sai
  - Tính 9 đặc trưng bằng chính ml/cycles.py, chấm điểm bằng đúng tham số trong cycles.json

LƯU Ý KHI TRÌNH BÀY: ở chế độ này việc tính đặc trưng chạy trên laptop, chưa chạy trên ESP32.
Chỉ có lệnh ĐỌC PLC.
"""
import argparse
import json
import os
import sys
import time

import csv
import numpy as np
import paho.mqtt.client as mqtt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ml"))
import cycles as C  # noqa: E402

STATE_BITS = ["STOPPED", "READY", "AUTO", "WORKING", "DONE", "ERROR"]   # M0..M5
PRIORITY = ["ERROR", "STOPPED", "WORKING", "DONE", "AUTO", "READY"]     # nhiều bit cùng bật thì lấy cái đứng trước
RATE = 100                                                              # mẫu/giây của dữ liệu huấn luyện


def signed(w):
    return w - 0x10000 if w & 0x8000 else w


def state_from_bits(m):
    on = {STATE_BITS[b] for b in range(6) if (m >> b) & 1}
    for s in PRIORITY:
        if s in on:
            return s
    return "STOPPED"


# ───────── Nguồn dữ liệu ─────────
def source_serial(port, baud):
    """ESP32 in mỗi dòng: S,<millis>,<D100>,<D102>,<D110>,<Mword>"""
    import serial
    ser = serial.Serial(port, baud, timeout=1)
    print(f"Đang đọc ESP32 qua {port}")
    t_base = None
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line.startswith("S,"):
            if line:
                print("  [ESP32]", line)
            continue
        try:
            _, ms, d100, d102, d110, m = line.split(",")
            ms = int(ms)
            if t_base is None:
                t_base = time.time() - ms / 1000.0
            yield t_base + ms / 1000.0, signed(int(d100)), int(d110), int(m)
        except ValueError:
            continue


def source_plc(ip, port, hz):
    """Laptop đọc thẳng PLC bằng MC protocol."""
    import pymcprotocol
    plc = pymcprotocol.Type3E(plctype="Q")
    plc.connect(ip, port)
    print(f"Đang đọc thẳng PLC {ip}:{port}, mục tiêu {hz} lần/giây")
    period = 1.0 / hz
    nxt = time.time()
    while True:
        d = plc.batchread_wordunits(headdevice="D100", readsize=11)    # D100..D110
        m = plc.batchread_wordunits(headdevice="M0", readsize=1)[0]
        yield time.time(), signed(d[0] & 0xFFFF), d[10] & 0xFFFF, m & 0xFFFF
        nxt += period
        time.sleep(max(0.0, nxt - time.time()))


# ───────── Xử lý ─────────
def load_model(proc):
    with open(os.path.join(HERE, "..", "ml", "cycles.json"), encoding="utf-8") as f:
        mdl = json.load(f)["processes"][proc]["model"]
    return np.array(mdl["mu"]), np.array(mdl["inv_cov"]), float(mdl["threshold"])


def resample(ts, ys):
    """Nội suy về lưới 100 mẫu/giây theo dấu thời gian thật."""
    ts = np.asarray(ts) - ts[0]
    n = max(int(round(ts[-1] * RATE)) + 1, 8)
    return np.interp(np.linspace(0, ts[-1], n), ts, np.asarray(ys, float))


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--serial", help="cổng USB của ESP32, ví dụ COM5 hoặc /dev/ttyUSB0")
    src.add_argument("--plc", help="IP của PLC để laptop đọc thẳng")
    ap.add_argument("--plc-port", type=int, default=5000)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--hz", type=int, default=100, help="tần số đọc khi dùng --plc")
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--gw", default="01")
    ap.add_argument("--machine", default="M01")
    ap.add_argument("--process", default="PRESS_FORCE")
    ap.add_argument("--scale", type=float, default=0.01, help="đổi D100 sang đơn vị thật (0,01 kN mỗi đơn vị)")
    ap.add_argument("--log-csv", help="ghi mỗi chu kỳ ra file CSV để train lại, ví dụ cycles_M01.csv — "
                                      "bắt buộc nếu muốn train trên PLC thật, xem train_from_csv.py")
    a = ap.parse_args()

    csv_writer = csv_file = None
    if a.log_csv:
        is_new = not os.path.exists(a.log_csv)
        csv_file = open(a.log_csv, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if is_new:
            csv_writer.writerow(["ts", "n_samples", "y"])   # y: các giá trị trong chu kỳ, cách nhau bằng ";"
        print(f"Đang ghi mỗi chu kỳ vào {a.log_csv}")

    mu, inv, thr = load_model(a.process)

    try:
        cli = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=f"bridge-{a.machine}")
    except AttributeError:
        cli = mqtt.Client(client_id=f"bridge-{a.machine}")
    cli.connect(a.broker, 1883)
    cli.loop_start()
    base = f"gw/{a.gw}/m/{a.machine}"
    print(f"Đã nối MQTT {a.broker}:1883 — topic {base}/state và {base}/cycle\n")

    stream = source_serial(a.serial, a.baud) if a.serial else source_plc(a.plc, a.plc_port, a.hz)

    last_state, last_sent = None, 0.0
    buf_t, buf_y, in_cycle, n_cycle, n_flag = [], [], False, 0, 0
    # Chỉ nhận chu kỳ bắt đầu SAU khi script đã chạy. Nếu khởi động đúng lúc máy đang ép dở,
    # chu kỳ đó bị cắt cụt và sẽ bị chấm nhầm là bất thường — nên bỏ qua.
    armed = False

    for t, d100, d110, m in stream:
        st = state_from_bits(m)
        err = f"E{d110}" if (st == "ERROR" and d110) else None

        # Trạng thái: gửi khi đổi, và nhắc lại mỗi 5 giây
        if st != last_state or t - last_sent > 5:
            payload = {"ts": int(t * 1000), "state": st}
            if err:
                payload["errorCode"] = err
            cli.publish(f"{base}/state", json.dumps(payload))
            if st != last_state:
                print(f"Trạng thái: {st}" + (f" ({err})" if err else ""))
            last_state, last_sent = st, t

        # Chu kỳ: theo cờ M3 "đang làm việc"
        working = bool((m >> 3) & 1)
        if not armed:
            armed = not working          # chờ thấy máy rảnh một lần rồi mới bắt đầu cắt chu kỳ
            continue
        if working:
            buf_t.append(t)
            buf_y.append(d100 * a.scale)
            in_cycle = True
        elif in_cycle:
            in_cycle = False
            if len(buf_t) >= 8:
                y = resample(buf_t, buf_y)
                f = C.extract(y)
                dvec = f - mu
                score = float(np.sqrt(dvec @ inv @ dvec))
                n_cycle += 1
                flag = score > thr
                n_flag += flag
                cli.publish(f"{base}/cycle", json.dumps({
                    "ts": int(t * 1000),
                    "y": [round(float(v), 3) for v in y],
                    "f": [round(float(v), 5) for v in f],
                    "score": round(score, 3),
                }))
                if csv_writer:
                    csv_writer.writerow([int(t * 1000), len(y), ";".join(f"{v:.4f}" for v in y)])
                    csv_file.flush()   # ghi ngay — tắt script giữa chừng không mất chu kỳ vừa ghi
                tag = "BẤT THƯỜNG" if flag else "bình thường"
                print(f"  Chu kỳ #{n_cycle}: {len(buf_t)} lần đọc → {len(y)} mẫu, "
                      f"điểm {score:.2f} / ngưỡng {thr:.2f} → {tag}   "
                      f"(đã gắn cờ {n_flag}/{n_cycle})")
            buf_t, buf_y = [], []


if __name__ == "__main__":
    import atexit

    def _close_csv():
        pass  # file đóng tự nhiên khi tiến trình thoát; giữ hàm để mở rộng sau nếu cần
    atexit.register(_close_csv)

    try:
        main()
    except KeyboardInterrupt:
        print("\nDừng.")
