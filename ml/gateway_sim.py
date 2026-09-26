"""
gateway_sim.py — Giả lập gateway khi chưa có PLC thật.

Phát đúng hai loại bản tin mà gateway thật sẽ phát cho mỗi máy:
    gw/01/m/{machineId}/state   {"ts", "state", "errorCode"?}
    gw/01/m/{machineId}/cycle   {"ts", "y", "f", "score"}

Đường cong và đặc trưng mỗi chu kỳ lấy từ tập kiểm tra trong cycles.json,
nên giao diện và máy chủ nhận đúng dữ liệu mô hình đã được đánh giá trên.

Chạy:
    pip install paho-mqtt numpy
    python gateway_sim.py --dry-run     # in ra màn hình, không cần broker
    python gateway_sim.py               # phát MQTT tới localhost:1883

Khi có gateway thật, tắt script này — giao diện và máy chủ không phải sửa gì.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

GW_ID = "01"
MODEL = json.loads((Path(__file__).parent / "cycles.json").read_text(encoding="utf-8"))

# Khớp với src/data/machines.ts
MACHINES = [
    {"id": "M01", "process": "PRESS_FORCE", "cycle": 3.2, "errors": ["E101", "E102", "E103"]},
    {"id": "M02", "process": "TORQUE", "cycle": 3.6, "errors": ["E201", "E202", "E203"]},
    {"id": "M03", "process": "AIR_PRESSURE", "cycle": 2.8, "errors": ["E301", "E302", "E303"]},
    {"id": "M04", "process": "PRESS_FORCE", "cycle": 4.0, "errors": ["E401", "E402"]},
]
ERROR_PROB = 0.01      # xác suất báo lỗi mỗi chu kỳ — cao hơn thực tế để demo thấy được
FAULT_PROB = 0.05      # xác suất chu kỳ mang lỗi gia công


def score(f, process):
    m = MODEL["processes"][process]["model"]
    d = np.asarray(f) - np.asarray(m["mu"])
    return float(np.sqrt(max(0.0, d @ np.asarray(m["inv_cov"]) @ d)))


class Machine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = "AUTO"
        self.until = time.time() + random.uniform(0.5, 1.5)
        self.error = None

    def next(self, now, emit):
        c = self.cfg
        if self.state == "AUTO":
            if random.random() < ERROR_PROB:
                self.error = random.choice(c["errors"])
                self._go("ERROR", now, emit, random.uniform(8, 20))
            else:
                self._go("WORKING", now, emit, c["cycle"] * random.uniform(0.92, 0.98))
        elif self.state == "WORKING":
            samples = MODEL["processes"][c["process"]]["samples"]
            if random.random() < FAULT_PROB:
                s = random.choice(samples["faults"][random.choice(list(samples["faults"]))])
            else:
                s = random.choice(samples["normal"])
            emit(f"gw/{GW_ID}/m/{c['id']}/cycle",
                 {"ts": int(now * 1000), "y": s["y"], "f": s["f"], "score": round(score(s["f"], c["process"]), 3)})
            self._go("DONE", now, emit, random.uniform(0.1, 0.2))
        elif self.state == "DONE":
            self._go("AUTO", now, emit, random.uniform(0.1, 0.3))
        elif self.state == "ERROR":
            self.error = None
            self._go("STOPPED", now, emit, random.uniform(3, 8))
        elif self.state == "STOPPED":
            self._go("READY", now, emit, random.uniform(2, 5))
        elif self.state == "READY":
            self._go("AUTO", now, emit, random.uniform(0.2, 0.6))

    def _go(self, state, now, emit, hold):
        self.state = state
        self.until = now + hold
        p = {"ts": int(now * 1000), "state": state}
        if state == "ERROR":
            p["errorCode"] = self.error
        emit(f"gw/{GW_ID}/m/{self.cfg['id']}/state", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    client = None
    if not a.dry_run:
        try:
            import paho.mqtt.client as mqtt
            try:
                client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=f"gw-sim-{GW_ID}")
            except AttributeError:
                client = mqtt.Client(client_id=f"gw-sim-{GW_ID}")
            client.connect(a.host, a.port, 60)
            client.loop_start()
            print(f"Đã nối MQTT {a.host}:{a.port}")
        except Exception as e:
            print(f"Không nối được broker ({e}). Chạy lại với --dry-run để thử không cần broker.")
            sys.exit(1)

    def emit(topic, payload):
        if client:
            client.publish(topic, json.dumps(payload))
        kind = topic.rsplit("/", 1)[-1]
        mid = topic.split("/")[3]
        if kind == "state":
            extra = f" {payload['errorCode']}" if "errorCode" in payload else ""
            print(f"{mid} trạng thái  {payload['state']}{extra}")
        else:
            thr = MODEL["processes"][next(m for m in MACHINES if m["id"] == mid)["process"]]["model"]["threshold"]
            flag = "BẤT THƯỜNG" if payload["score"] > thr else "bình thường"
            print(f"{mid} chu kỳ      điểm {payload['score']:.2f} / {thr:.2f}  {flag}")

    machines = [Machine(c) for c in MACHINES]
    print("Đang phát. Ctrl+C để dừng.\n")
    try:
        while True:
            now = time.time()
            for m in machines:
                if now >= m.until:
                    m.next(now, emit)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDừng.")
        if client:
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
