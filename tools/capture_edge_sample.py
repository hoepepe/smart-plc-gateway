"""
capture_edge_sample.py — Ghi lại một ảnh chụp trạng thái runtime edge (registry, learn, chu kỳ gần nhất)
vào src/data/edge_sample.json để dashboard hiện "dữ liệu mẫu" khi chưa nối được gateway.

    python -m edge.runtime --demo        (chạy vài phút, duyệt/gắn nhãn vài cảnh báo trên dashboard)
    python tools/capture_edge_sample.py  (nghe 15 giây rồi ghi file)
"""
import json
import os
import sys
import time

import paho.mqtt.client as mqtt

GW = os.getenv("GW_ID", "01")
OUT = os.path.join(os.path.dirname(__file__), "..", "src", "data", "edge_sample.json")
snap = {"online": True, "registry": None, "learn": {}, "cycles": {}}


def on(c, u, m):
    if not m.payload:
        return
    p = json.loads(m.payload)
    parts = m.topic.split("/")
    if parts[-1] == "registry":
        snap["registry"] = p
    elif parts[-1] == "learn":
        snap["learn"][parts[-2]] = p
    elif parts[-1] == "cycle":
        sc = p.get("score") if isinstance(p.get("score"), dict) else {}
        arr = snap["cycles"].setdefault(parts[-2], [])
        arr.append({"ts": p["ts"], "kind": p.get("kind"), "mode": p.get("mode"), "recipe": p.get("recipe", "*"),
                    "norm": p.get("norm"), "flag": sc.get("flag"), "alarm_id": p.get("alarm_id"),
                    "y": p.get("y", [])[::2], "issues": p.get("issues"), "top": sc.get("top")})
        del arr[:-160]


c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
c.on_message = on
c.connect(sys.argv[1] if len(sys.argv) > 1 else "localhost", 1883)
c.subscribe(f"gw/{GW}/#")
c.loop_start()
time.sleep(float(os.getenv("SECONDS", "15")))
c.loop_stop()
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
print(f"Đã ghi {OUT}: {len(snap['learn'])} máy, {sum(len(v) for v in snap['cycles'].values())} chu kỳ")
