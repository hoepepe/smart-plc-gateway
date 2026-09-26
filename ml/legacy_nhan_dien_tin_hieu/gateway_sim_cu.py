"""
gateway_sim.py — Gateway giả lập. Phần việc của Đức.

Mục đích: phát bản tin MQTT GIỐNG HỆT ESP32 thật sẽ phát, để Hưng test dashboard
và Đức test backend NGAY HÔM NAY, không phải chờ Đạt lắp xong phần cứng.

Khi phần cứng của Tuấn xong, tắt script này đi là xong — không phải sửa gì
ở backend hay dashboard, vì schema bản tin giống nhau.

Chạy:
    pip install paho-mqtt numpy scikit-learn joblib
    python gateway_sim.py                  # cần Mosquitto chạy ở localhost:1883
    python gateway_sim.py --dry-run        # in ra màn hình, không cần broker

Cấu hình Mosquitto (mosquitto.conf) — NHỚ bật cả WebSocket cho dashboard:
    listener 1883
    protocol mqtt
    listener 9001
    protocol websockets
    allow_anonymous true
"""

import argparse
import json
import time
import sys
import numpy as np

from features import extract, as_dict, FEATURE_VERSION
from signals import make_session, WINDOW, FS

GW_ID = "01"

# 4 kênh: 3 loại đã huấn luyện + 1 loại lạ (ca demo then chốt)
CHANNELS = [
    {"n": 1, "kind": "VIBRATION"},
    {"n": 2, "kind": "TEMPERATURE"},
    {"n": 3, "kind": "COUNTER"},
    {"n": 4, "kind": "PRESSURE_BURST"},   # chưa hề huấn luyện -> phải bị gắn cờ lạ
]


def load_model(path="model.joblib"):
    try:
        import joblib
        m = joblib.load(path)
        if m.get("feature_version") != FEATURE_VERSION:
            print(f"! model.joblib dùng feature_version {m.get('feature_version')}, "
                  f"code đang ở version {FEATURE_VERSION}. Train lại đi.")
            return None
        return m
    except Exception as e:
        print(f"! Không nạp được model.joblib ({e}). Chạy `python train_eval.py` trước.")
        return None


def predict(model, feat_vec):
    """Trả về cùng cấu trúc mà firmware ESP32 sẽ trả về."""
    X = feat_vec.reshape(1, -1)
    proba = model["clf"].predict_proba(X)[0]
    classes = model["clf"].classes_
    i = int(proba.argmax())
    cls, conf = str(classes[i]), float(proba[i])

    iso_score = float(model["iso"].score_samples(model["scaler"].transform(X))[0])
    is_ood = bool(iso_score < model["iso_th"] or conf < model["ood_th"])

    if is_ood:
        state = "unknown"
    elif conf < model["conf_th"]:
        state = "pending"
    else:
        state = "auto"

    return {"cls": cls, "conf": round(conf, 4), "ood": is_ood,
            "iso_score": round(iso_score, 4), "state": state}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--period", type=float, default=2.0,
                    help="giây giữa 2 cửa sổ (thật là 2.0)")
    ap.add_argument("--dry-run", action="store_true",
                    help="in ra màn hình thay vì gửi MQTT")
    ap.add_argument("--send-raw", action="store_true",
                    help="gửi kèm cả mẫu thô (tốn băng thông, chỉ bật khi cần)")
    args = ap.parse_args()

    model = load_model()
    if model is None:
        sys.exit(1)

    client = None
    if not args.dry_run:
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client(client_id=f"gw-sim-{GW_ID}")
            client.connect(args.host, args.port, 60)
            client.loop_start()
            print(f"Đã nối MQTT {args.host}:{args.port}")
        except Exception as e:
            print(f"! Không nối được broker ({e}). Chạy lại với --dry-run để test offline.")
            sys.exit(1)

    # mỗi kênh là một luồng liên tục
    streams = {}
    for ch in CHANNELS:
        streams[ch["n"]] = {"windows": make_session(ch["kind"], 200, seed=1000 + ch["n"]), "i": 0}

    def publish(topic, payload):
        s = json.dumps(payload, ensure_ascii=False)
        if client:
            client.publish(topic, s, qos=0)
        else:
            print(f"{topic}  {s[:150]}")

    print(f"Đang phát {len(CHANNELS)} kênh, mỗi {args.period}s một cửa sổ. Ctrl+C để dừng.\n")
    t0 = time.time()
    try:
        while True:
            for ch in CHANNELS:
                st = streams[ch["n"]]
                w = st["windows"][st["i"] % len(st["windows"])]
                st["i"] += 1

                ts = int(time.time() * 1000)
                f = extract(w, FS)
                r = predict(model, f)

                if args.send_raw:
                    publish(f"gw/{GW_ID}/ch/{ch['n']}/raw",
                            {"ts": ts, "fs": FS, "v": [round(float(x), 3) for x in w]})

                publish(f"gw/{GW_ID}/ch/{ch['n']}/pred", {
                    "ts": ts, "cls": r["cls"], "conf": r["conf"], "ood": r["ood"],
                    "state": r["state"], "iso_score": r["iso_score"],
                    "feat": as_dict(f), "feature_version": FEATURE_VERSION,
                    "truth": ch["kind"],      # chỉ có trong sim, firmware thật KHÔNG có field này
                })

                flag = {"auto": "OK   ", "pending": "CHỜ  ", "unknown": "LẠ   "}[r["state"]]
                print(f"CH-{ch['n']} {flag} {r['cls']:<14} conf={r['conf']:.2f} "
                      f"iso={r['iso_score']:+.3f}  (thực tế: {ch['kind']})")

            publish(f"gw/{GW_ID}/status", {
                "ts": int(time.time() * 1000),
                "uptime": int(time.time() - t0),
                "rssi": int(np.random.randint(-70, -45)),
                "fw": "sim-0.1.0",
            })
            print("-" * 62)
            time.sleep(args.period)

    except KeyboardInterrupt:
        print("\nDừng.")
        if client:
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
