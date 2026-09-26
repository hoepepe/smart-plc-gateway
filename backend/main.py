"""
main.py — Máy chủ của Smart PLC Gateway.

Làm ba việc:
  1. Nghe MQTT từ gateway: trạng thái máy và chu kỳ gia công
  2. Lưu vào SQLite, chấm lại điểm bất thường bằng đúng mô hình trong ml/cycles.json
     (để đối chiếu với điểm gateway tự tính)
  3. Phục vụ REST API: trạng thái hiện tại, lịch sử, OEE, nguyên nhân dừng máy

Chạy:
    pip install -r requirements.txt
    python main.py
    mở http://localhost:8000/docs để thử API

Không có broker vẫn chạy được: API hoạt động, chỉ không nhận dữ liệu mới.
"""

import json
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ───────────────────────── Cấu hình ─────────────────────────
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
GW_ID = os.getenv("GW_ID", "01")
DB_PATH = os.getenv("DB_PATH", "gateway.db")
API_PORT = int(os.getenv("API_PORT", "8000"))
MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "cycles.json"

# Khớp với src/data/machines.ts. Khi triển khai, sinh từ cùng một file cấu hình.
MACHINES = {
    "M01": {"name": "Máy ép vòng bi", "process": "PRESS_FORCE", "ideal_cycle_sec": 3.2},
    "M02": {"name": "Máy siết bu-lông", "process": "TORQUE", "ideal_cycle_sec": 3.6},
    "M03": {"name": "Cụm xi-lanh khí nén", "process": "AIR_PRESSURE", "ideal_cycle_sec": 2.8},
    "M04": {"name": "Máy ép đời cũ", "process": "PRESS_FORCE", "ideal_cycle_sec": 4.0},
}
RUN_STATES = {"AUTO", "WORKING", "DONE"}
VALID_STATES = RUN_STATES | {"STOPPED", "READY", "ERROR"}

_state = {"mqtt_connected": False, "messages": 0, "last_message_at": None}
_lock = threading.Lock()


# ───────────────────────── Mô hình ─────────────────────────
def load_model():
    data = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    out = {}
    for proc, p in data["processes"].items():
        m = p["model"]
        out[proc] = {
            "mu": np.array(m["mu"]),
            "inv_cov": np.array(m["inv_cov"]),
            "threshold": float(m["threshold"]),
        }
    return out


MODEL = load_model()


def mahalanobis(f, proc):
    m = MODEL[proc]
    d = np.asarray(f, dtype=float) - m["mu"]
    return float(np.sqrt(max(0.0, d @ m["inv_cov"] @ d)))


# ───────────────────────── Cơ sở dữ liệu ─────────────────────────
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript("""
        -- Mỗi lần trạng thái máy thay đổi là một dòng. Khoảng giữa hai dòng liên tiếp
        -- là thời gian máy ở trạng thái đó — đủ để tính độ sẵn sàng OEE.
        CREATE TABLE IF NOT EXISTS states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            ts INTEGER NOT NULL,            -- mili-giây, gắn tại gateway
            state TEXT NOT NULL,
            error_code TEXT,
            received_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_states ON states(machine_id, ts);

        -- Mỗi chu kỳ gia công là một dòng.
        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            ts INTEGER NOT NULL,
            score REAL NOT NULL,            -- điểm máy chủ tự chấm lại
            gateway_score REAL,             -- điểm gateway gửi lên, để đối chiếu
            anomalous INTEGER NOT NULL,
            features TEXT NOT NULL,
            curve TEXT,                     -- đường cong, giữ để xem lại chu kỳ bất thường
            received_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cycles ON cycles(machine_id, ts);
        """)
    print(f"[db] {Path(DB_PATH).resolve()}")


# ───────────────────────── MQTT ─────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        with _lock:
            _state["mqtt_connected"] = True
        client.subscribe([(f"gw/{GW_ID}/m/+/state", 0), (f"gw/{GW_ID}/m/+/cycle", 0)])
        print(f"[mqtt] Đã nối {MQTT_HOST}:{MQTT_PORT}")


def on_disconnect(client, userdata, *args, **kwargs):
    with _lock:
        _state["mqtt_connected"] = False


def on_message(client, userdata, msg):
    try:
        parts = msg.topic.split("/")
        machine_id, kind = parts[parts.index("m") + 1], parts[-1]
        if machine_id not in MACHINES:
            return
        p = json.loads(msg.payload.decode("utf-8"))
        now = int(time.time() * 1000)

        with db() as c:
            if kind == "state":
                if p.get("state") not in VALID_STATES:
                    return
                c.execute("INSERT INTO states (machine_id, ts, state, error_code, received_at) VALUES (?,?,?,?,?)",
                          (machine_id, int(p.get("ts", now)), p["state"], p.get("errorCode"), now))
            elif kind == "cycle":
                f = p.get("f") or []
                score = mahalanobis(f, MACHINES[machine_id]["process"])
                thr = MODEL[MACHINES[machine_id]["process"]]["threshold"]
                c.execute("""INSERT INTO cycles (machine_id, ts, score, gateway_score, anomalous, features, curve, received_at)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (machine_id, int(p.get("ts", now)), score, p.get("score"), int(score > thr),
                           json.dumps(f), json.dumps(p.get("y")), now))
        with _lock:
            _state["messages"] += 1
            _state["last_message_at"] = now
    except Exception as e:
        print(f"[mqtt] Bỏ qua bản tin lỗi ở {msg.topic}: {e}")


def start_mqtt():
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=f"backend-{GW_ID}")
    except AttributeError:
        client = mqtt.Client(client_id=f"backend-{GW_ID}")
    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message

    def loop():
        while True:
            try:
                client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
                client.loop_forever()
            except Exception as e:
                with _lock:
                    _state["mqtt_connected"] = False
                print(f"[mqtt] Chưa nối được ({e}) — thử lại sau 5 giây. API vẫn chạy.")
                time.sleep(5)

    threading.Thread(target=loop, daemon=True).start()


# ───────────────────────── Tính toán ─────────────────────────
def state_durations(machine_id, since_ms=0):
    """Cộng thời gian ở từng trạng thái, từ dãy thời điểm chuyển trạng thái."""
    with db() as c:
        rows = c.execute("SELECT ts, state, error_code FROM states WHERE machine_id=? AND ts>=? ORDER BY ts",
                         (machine_id, since_ms)).fetchall()
    now = int(time.time() * 1000)
    dur, errors = {s: 0.0 for s in VALID_STATES}, {}
    for i, r in enumerate(rows):
        end = rows[i + 1]["ts"] if i + 1 < len(rows) else now
        sec = max(0, end - r["ts"]) / 1000
        dur[r["state"]] += sec
        if r["state"] == "ERROR" and r["error_code"]:
            e = errors.setdefault(r["error_code"], {"count": 0, "seconds": 0.0})
            e["count"] += 1
            e["seconds"] += sec
    return dur, errors, (rows[-1] if rows else None)


def oee(machine_id, since_ms=0):
    dur, _, _ = state_durations(machine_id, since_ms)
    planned = sum(dur.values()) or 1
    run = sum(dur[s] for s in RUN_STATES)
    with db() as c:
        n, bad = c.execute("SELECT COUNT(*), COALESCE(SUM(anomalous),0) FROM cycles WHERE machine_id=? AND ts>=?",
                           (machine_id, since_ms)).fetchone()
    a = run / planned
    p = min(1.0, MACHINES[machine_id]["ideal_cycle_sec"] * n / run) if run > 0 else 0.0
    q = (n - bad) / n if n else 1.0
    return {"availability": a, "performance": p, "quality_estimate": q, "oee": a * p * q,
            "cycles": n, "anomalous_cycles": bad, "run_seconds": run, "planned_seconds": planned}


# ───────────────────────── API ─────────────────────────
@asynccontextmanager
async def lifespan(app):
    init_db()
    start_mqtt()
    yield


app = FastAPI(title="Smart PLC Gateway — máy chủ",
              description="Nhận trạng thái máy và chu kỳ gia công qua MQTT, lưu SQLite, tính OEE.",
              version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _check(machine_id):
    if machine_id not in MACHINES:
        raise HTTPException(404, f"Không có máy {machine_id}")


@app.get("/api/health", tags=["Hệ thống"])
def health():
    with _lock:
        s = dict(_state)
    with db() as c:
        ns = c.execute("SELECT COUNT(*) FROM states").fetchone()[0]
        nc = c.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
    return {"ok": True, **s, "mqtt_target": f"{MQTT_HOST}:{MQTT_PORT}", "rows": {"states": ns, "cycles": nc}}


@app.get("/api/machines", tags=["Máy"])
def machines():
    """Trạng thái hiện tại và OEE của từng máy."""
    out = []
    for mid, cfg in MACHINES.items():
        _, _, last = state_durations(mid)
        out.append({"id": mid, **cfg,
                    "state": last["state"] if last else None,
                    "error_code": last["error_code"] if last else None,
                    "since": last["ts"] if last else None,
                    "oee": oee(mid)})
    return out


@app.get("/api/machines/{machine_id}/states", tags=["Máy"])
def states(machine_id: str, limit: int = Query(500, ge=1, le=10000)):
    _check(machine_id)
    with db() as c:
        rows = c.execute("SELECT ts, state, error_code FROM states WHERE machine_id=? ORDER BY ts DESC LIMIT ?",
                         (machine_id, limit)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/machines/{machine_id}/cycles", tags=["Máy"])
def cycles(machine_id: str, limit: int = Query(100, ge=1, le=5000), only_anomalous: bool = False):
    _check(machine_id)
    q = "SELECT ts, score, gateway_score, anomalous, features FROM cycles WHERE machine_id=?"
    q += " AND anomalous=1" if only_anomalous else ""
    with db() as c:
        rows = c.execute(q + " ORDER BY ts DESC LIMIT ?", (machine_id, limit)).fetchall()
    return [{**dict(r), "features": json.loads(r["features"]), "anomalous": bool(r["anomalous"])} for r in rows]


@app.get("/api/machines/{machine_id}/oee", tags=["OEE"])
def machine_oee(machine_id: str, since_ms: int = 0):
    _check(machine_id)
    return oee(machine_id, since_ms)


@app.get("/api/stops", tags=["OEE"])
def stops(since_ms: int = 0):
    """Nguyên nhân dừng máy, xếp theo thời gian mất nhiều nhất."""
    agg = []
    for mid in MACHINES:
        _, errors, _ = state_durations(mid, since_ms)
        agg += [{"machine_id": mid, "error_code": k, **v} for k, v in errors.items()]
    return sorted(agg, key=lambda x: -x["seconds"])


if __name__ == "__main__":
    print(f"Smart PLC Gateway — máy chủ · API http://localhost:{API_PORT}/docs")
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")
