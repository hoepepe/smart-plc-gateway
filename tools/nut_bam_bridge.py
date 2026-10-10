"""
nut_bam_bridge.py — Cầu nối giữa nút OK/NG + đèn trên hộp gateway (ESP32, firmware/nut_xac_nhan) và runtime AI.

    ESP32 ──USB── laptop:  "BTN,NG" / "BTN,OK"  ─►  MQTT gw/01/m/M01/button {"label": "fault"|"false_alarm"}
    runtime ─► MQTT gw/01/m/M01/andon, button_ack  ─►  "ANDON,red,1" / "ACK,1"  ──USB──► ESP32

Chạy:
    pip install pyserial paho-mqtt
    python tools/nut_bam_bridge.py --serial COM5 --machine M01          # có ESP32 cắm USB
    python tools/nut_bam_bridge.py --ban-phim --machine SIM-EP1         # CHƯA có ESP32: gõ n/o + Enter thay nút

Chế độ --ban-phim để demo ngay: gõ  n  = bấm nút NG (Đúng là lỗi),  o  = bấm nút OK (Báo nhầm),  q  = thoát.
Màu đèn in ra màn hình.
"""
import argparse
import json
import sys
import threading
import time

import paho.mqtt.client as mqtt

LABEL = {"NG": "fault", "OK": "false_alarm"}
VI = {"green": "XANH — bình thường", "yellow": "VÀNG — đang học / chờ duyệt / kiểm tra mẫu NG",
      "red": "ĐỎ — có cảnh báo AI chưa xác nhận", "off": "TẮT"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", help="cổng COM của ESP32, vd. COM5 hoặc /dev/ttyUSB0")
    ap.add_argument("--ban-phim", action="store_true", help="không có ESP32: dùng bàn phím thay nút")
    ap.add_argument("--machine", required=True)
    ap.add_argument("--gw", default="01")
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    a = ap.parse_args()
    if not a.serial and not a.ban_phim:
        sys.exit("Cần --serial COMx hoặc --ban-phim")

    ser = None
    if a.serial:
        import serial
        ser = serial.Serial(a.serial, 115200, timeout=0.2)
    base = f"gw/{a.gw}/m/{a.machine}"
    lock = threading.Lock()

    def to_esp(line):
        if ser:
            with lock:
                ser.write((line + "\n").encode())

    try:
        cli = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=f"nut-{a.machine}")
    except AttributeError:
        cli = mqtt.Client(client_id=f"nut-{a.machine}")

    def on_connect(c, *args, **kw):
        c.subscribe(base + "/andon")
        c.subscribe(base + "/button_ack")
        print(f"Đã nối MQTT {a.broker}:{a.port} — máy {a.machine}")

    def on_message(c, u, msg):
        try:
            d = json.loads(msg.payload.decode() or "{}")
        except Exception:
            return
        if msg.topic.endswith("/andon"):
            to_esp(f"ANDON,{d.get('color', 'off')},{1 if d.get('blink') else 0}")
            print(f"[đèn] {VI.get(d.get('color'), d.get('color'))}{' (nháy)' if d.get('blink') else ''} · {d.get('text', '')}")
        else:
            to_esp(f"ACK,{1 if d.get('ok') else 0}")
            print(f"[gateway] {'đã ghi nhận' if d.get('ok') else 'KHÔNG ghi được'}: {d.get('msg', '')}")

    cli.on_connect, cli.on_message = on_connect, on_message
    cli.connect(a.broker, a.port, keepalive=30)
    cli.loop_start()

    def press(which):
        cli.publish(base + "/button", json.dumps({"label": LABEL[which]}))
        print(f"[nút] {which} → {'Đúng là lỗi' if which == 'NG' else 'Báo nhầm'}")

    try:
        if ser:
            buf = b""
            while True:
                buf += ser.read(64)
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    s = line.decode(errors="ignore").strip()
                    if s.startswith("BTN,") and s[4:] in LABEL:
                        press(s[4:])
        else:
            print("Gõ  n  (nút NG = Đúng là lỗi),  o  (nút OK = Báo nhầm),  q  (thoát), rồi Enter.")
            for line in sys.stdin:
                k = line.strip().lower()
                if k == "q":
                    break
                if k in ("n", "o"):
                    press("NG" if k == "n" else "OK")
                time.sleep(0.05)
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        cli.loop_stop()


if __name__ == "__main__":
    main()
