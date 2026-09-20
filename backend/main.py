"""
main.py — Backend của Smart PLC Gateway.

Làm ba việc:
  1. Nghe MQTT từ gateway (hoặc gateway_sim.py), nhận bản tin phán đoán
  2. Lưu vào SQLite — dữ liệu time-series + nhật ký gán nhãn
  3. Phục vụ REST API cho dashboard đọc lịch sử và ghi nhãn kỹ sư xác nhận

Chạy:
    pip install fastapi uvicorn paho-mqtt
    python main.py

Sau đó mở http://localhost:8000/docs để xem và thử toàn bộ API.

Không có MQTT broker vẫn chạy được: API hoạt động bình thường,
chỉ là không nhận được dữ liệu mới. Trạng thái kết nối xem ở /api/health.
"""

import json
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ────────────────────────── Cấu hình ──────────────────────────
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
GW_ID = os.getenv("GW_ID", "01")
DB_PATH = os.getenv("DB_PATH", "gateway.db")
API_PORT = int(os.getenv("API_PORT", "8000"))

TOPIC_PRED = f"gw/{GW_ID}/ch/+/pred"
TOPIC_STATUS = f"gw/{GW_ID}/status"

# Giữ tối đa bao nhiêu bản ghi dự đoán mỗi kênh trước khi dọn bớt.
# Dữ liệu time-series phình rất nhanh: 4 kênh × 1 bản tin/2 giây ≈ 170k bản ghi/ngày.
MAX_ROWS_PER_CHANNEL = 50_000

_state = {"mqtt_connected": False, "last_msg_ts": None, "msg_count": 0}
_lock = threading.Lock()
_client: Optional[mqtt.Client] = None


# ────────────────────────── Database ──────────────────────────
def db():
    """Mỗi lần gọi mở một kết nối mới — SQLite không dùng chung được giữa các thread."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        -- Bản tin phán đoán từ gateway, mỗi cửa sổ tín hiệu một dòng
        CREATE TABLE IF NOT EXISTS predictions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gw_id       TEXT    NOT NULL,
            channel     INTEGER NOT NULL,
            ts          INTEGER NOT NULL,   -- Unix epoch mili-giây, gắn tại gateway
            cls         TEXT    NOT NULL,   -- nhãn mô hình đoán
            conf        REAL    NOT NULL,   -- độ tin cậy 0..1
            ood         INTEGER NOT NULL,   -- 1 = ngoài phân phối đã học
            state       TEXT,               -- auto | pending | unknown
            iso_score   REAL,
            features    TEXT,               -- JSON các đặc trưng đã trích
            received_at INTEGER NOT NULL    -- thời điểm backend nhận, để đối chiếu độ trễ
        );
        CREATE INDEX IF NOT EXISTS idx_pred_ch_ts ON predictions(channel, ts DESC);

        -- Nhãn cuối cùng do kỹ sư xác nhận hoặc hệ thống tự gán.
        -- Đây là tập dữ liệu huấn luyện tích lũy — tài sản thật của dự án.
        CREATE TABLE IF NOT EXISTS labels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gw_id       TEXT    NOT NULL,
            channel     INTEGER NOT NULL,
            ts          INTEGER NOT NULL,
            pred        TEXT,               -- mô hình đoán gì
            conf        REAL,
            final       TEXT    NOT NULL,   -- nhãn cuối
            src         TEXT    NOT NULL,   -- auto | engineer
            features    TEXT,               -- đặc trưng tại thời điểm gán, để train lại
            note        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_label_ts ON labels(ts DESC);

        -- Trạng thái sống của gateway
        CREATE TABLE IF NOT EXISTS gw_status (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            gw_id   TEXT NOT NULL,
            ts      INTEGER NOT NULL,
            uptime  INTEGER,
            rssi    INTEGER,
            fw      TEXT
        );
        """)
    print(f"[db] Sẵn sàng: {os.path.abspath(DB_PATH)}")


def prune_old_rows(channel: int):
    """Giữ bảng predictions không phình vô hạn. Nhãn thì giữ nguyên, không bao giờ xóa."""
    with db() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE channel = ?", (channel,)
        ).fetchone()[0]
        if n > MAX_ROWS_PER_CHANNEL:
            conn.execute("""
                DELETE FROM predictions WHERE id IN (
                    SELECT id FROM predictions WHERE channel = ?
                    ORDER BY ts ASC LIMIT ?
                )""", (channel, n - MAX_ROWS_PER_CHANNEL))
            print(f"[db] Dọn bớt {n - MAX_ROWS_PER_CHANNEL} bản ghi cũ của kênh {channel}")


# ────────────────────────── MQTT ──────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        with _lock:
            _state["mqtt_connected"] = True
        client.subscribe([(TOPIC_PRED, 0), (TOPIC_STATUS, 0)])
        print(f"[mqtt] Đã nối {MQTT_HOST}:{MQTT_PORT} · subscribe {TOPIC_PRED}")
    else:
        print(f"[mqtt] Nối thất bại, mã lỗi {rc}")


def on_disconnect(client, userdata, rc, properties=None, reason=None):
    with _lock:
        _state["mqtt_connected"] = False
    print("[mqtt] Mất kết nối, sẽ tự thử lại")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        parts = msg.topic.split("/")

        if msg.topic.endswith("/status"):
            with db() as conn:
                conn.execute(
                    "INSERT INTO gw_status (gw_id, ts, uptime, rssi, fw) VALUES (?,?,?,?,?)",
                    (GW_ID, payload.get("ts", 0), payload.get("uptime"),
                     payload.get("rssi"), payload.get("fw")))
            return

        # gw/{gw}/ch/{n}/pred
        ch_idx = parts.index("ch")
        channel = int(parts[ch_idx + 1])
        now_ms = int(time.time() * 1000)

        with db() as conn:
            conn.execute("""
                INSERT INTO predictions
                    (gw_id, channel, ts, cls, conf, ood, state, iso_score, features, received_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (GW_ID, channel, payload.get("ts", now_ms), payload.get("cls", "UNKNOWN"),
                 float(payload.get("conf", 0)), 1 if payload.get("ood") else 0,
                 payload.get("state"), payload.get("iso_score"),
                 json.dumps(payload.get("feat", {}), ensure_ascii=False), now_ms))

            # Mô hình tự tin đủ ngưỡng thì ghi luôn vào nhật ký nhãn, nguồn "auto".
            # Chỉ ghi khi nhãn đổi so với lần trước, tránh ghi trùng mỗi 2 giây.
            if payload.get("state") == "auto":
                last = conn.execute(
                    "SELECT final FROM labels WHERE channel = ? ORDER BY ts DESC LIMIT 1",
                    (channel,)).fetchone()
                if last is None or last["final"] != payload.get("cls"):
                    conn.execute("""
                        INSERT INTO labels (gw_id, channel, ts, pred, conf, final, src, features)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (GW_ID, channel, payload.get("ts", now_ms), payload.get("cls"),
                         float(payload.get("conf", 0)), payload.get("cls"), "auto",
                         json.dumps(payload.get("feat", {}), ensure_ascii=False)))

        with _lock:
            _state["msg_count"] += 1
            _state["last_msg_ts"] = now_ms
            count = _state["msg_count"]

        if count % 200 == 0:
            prune_old_rows(channel)

    except Exception as e:
        print(f"[mqtt] Lỗi xử lý bản tin từ {msg.topic}: {e}")


def start_mqtt():
    global _client
    try:
        _client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"backend-{GW_ID}")
    except AttributeError:
        _client = mqtt.Client(client_id=f"backend-{GW_ID}")   # paho 1.x

    _client.on_connect = on_connect
    _client.on_disconnect = on_disconnect
    _client.on_message = on_message

    def loop():
        while True:
            try:
                _client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
                _client.loop_forever()
            except Exception as e:
                with _lock:
                    _state["mqtt_connected"] = False
                print(f"[mqtt] Chưa nối được ({e}) — thử lại sau 5 giây. "
                      f"API vẫn chạy bình thường.")
                time.sleep(5)

    threading.Thread(target=loop, daemon=True).start()


# ────────────────────────── API ──────────────────────────
class LabelIn(BaseModel):
    label: str = Field(..., description="Nhãn cuối, ví dụ VIBRATION")
    src: str = Field("engineer", description="engineer | auto")
    note: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_mqtt()
    yield
    if _client:
        _client.disconnect()


app = FastAPI(
    title="Smart PLC Gateway — Backend",
    description="Nhận telemetry từ gateway qua MQTT, lưu SQLite, phục vụ dashboard.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # demo nội bộ; triển khai thật nên giới hạn origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["Hệ thống"])
def health():
    """Kiểm tra backend sống chưa và đã nối được MQTT chưa."""
    with _lock:
        s = dict(_state)
    with db() as conn:
        n_pred = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        n_label = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
    return {
        "status": "ok",
        "mqtt_connected": s["mqtt_connected"],
        "mqtt_target": f"{MQTT_HOST}:{MQTT_PORT}",
        "messages_received": s["msg_count"],
        "last_message_at": s["last_msg_ts"],
        "rows": {"predictions": n_pred, "labels": n_label},
        "db_path": os.path.abspath(DB_PATH),
    }


@app.get("/api/channels", tags=["Kênh"])
def list_channels():
    """Trạng thái mới nhất của từng kênh — dashboard gọi cái này khi mở trang."""
    with db() as conn:
        rows = conn.execute("""
            SELECT p.* FROM predictions p
            INNER JOIN (
                SELECT channel, MAX(ts) AS mx FROM predictions GROUP BY channel
            ) m ON p.channel = m.channel AND p.ts = m.mx
            ORDER BY p.channel""").fetchall()
        out = []
        for r in rows:
            lab = conn.execute(
                "SELECT final, src FROM labels WHERE channel = ? ORDER BY ts DESC LIMIT 1",
                (r["channel"],)).fetchone()
            out.append({
                "channel": r["channel"], "ts": r["ts"], "cls": r["cls"],
                "conf": r["conf"], "ood": bool(r["ood"]), "state": r["state"],
                "features": json.loads(r["features"] or "{}"),
                "final_label": lab["final"] if lab else None,
                "label_src": lab["src"] if lab else None,
            })
    return {"gw_id": GW_ID, "channels": out}


@app.get("/api/channels/{n}/history", tags=["Kênh"])
def channel_history(n: int, limit: int = Query(200, ge=1, le=5000), before: Optional[int] = None):
    """Lịch sử phán đoán của một kênh, mới nhất trước. Dùng `before` để phân trang."""
    with db() as conn:
        if before:
            rows = conn.execute(
                "SELECT * FROM predictions WHERE channel = ? AND ts < ? ORDER BY ts DESC LIMIT ?",
                (n, before, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM predictions WHERE channel = ? ORDER BY ts DESC LIMIT ?",
                (n, limit)).fetchall()
    return {
        "channel": n,
        "count": len(rows),
        "items": [{
            "ts": r["ts"], "cls": r["cls"], "conf": r["conf"],
            "ood": bool(r["ood"]), "state": r["state"],
            "features": json.loads(r["features"] or "{}"),
        } for r in rows],
    }


@app.post("/api/channels/{n}/label", tags=["Kênh"])
def set_label(n: int, body: LabelIn):
    """Kỹ sư xác nhận nhãn. Ghi vào DB và gửi ngược xuống gateway qua MQTT."""
    if n < 1 or n > 16:
        raise HTTPException(400, "Số kênh không hợp lệ")

    ts = int(time.time() * 1000)
    with db() as conn:
        last = conn.execute(
            "SELECT cls, conf, features FROM predictions WHERE channel = ? ORDER BY ts DESC LIMIT 1",
            (n,)).fetchone()
        conn.execute("""
            INSERT INTO labels (gw_id, channel, ts, pred, conf, final, src, features, note)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (GW_ID, n, ts,
             last["cls"] if last else None,
             last["conf"] if last else None,
             body.label, body.src,
             last["features"] if last else "{}",
             body.note))

    published = False
    if _client and _state["mqtt_connected"]:
        try:
            _client.publish(
                f"gw/{GW_ID}/ch/{n}/label",
                json.dumps({"ts": ts, "label": body.label, "src": body.src},
                           ensure_ascii=False), qos=0)
            published = True
        except Exception as e:
            print(f"[mqtt] Không gửi được nhãn xuống gateway: {e}")

    return {"ok": True, "channel": n, "label": body.label,
            "published_to_gateway": published, "ts": ts}


@app.get("/api/labels", tags=["Nhãn"])
def list_labels(limit: int = Query(100, ge=1, le=2000)):
    """Nhật ký gán nhãn đầy đủ — dùng cho bảng lịch sử trên dashboard."""
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM labels ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return {"count": len(rows), "items": [{
        "ts": r["ts"],
        "time": datetime.fromtimestamp(r["ts"] / 1000, tz=timezone.utc)
                        .astimezone().strftime("%H:%M:%S"),
        "channel": r["channel"], "pred": r["pred"], "conf": r["conf"],
        "final": r["final"], "src": r["src"], "note": r["note"],
    } for r in rows]}


@app.get("/api/training-data", tags=["Nhãn"])
def export_training_data():
    """Xuất toàn bộ cặp (đặc trưng, nhãn) để huấn luyện lại mô hình.

    Đây là giá trị tích lũy của hệ thống: càng nhiều lần kỹ sư xác nhận,
    tập dữ liệu càng lớn, lần triển khai sau càng ít phải can thiệp.
    """
    with db() as conn:
        rows = conn.execute(
            "SELECT channel, ts, final, src, features FROM labels ORDER BY ts ASC").fetchall()
    items = []
    for r in rows:
        feat = json.loads(r["features"] or "{}")
        if feat:
            items.append({"channel": r["channel"], "ts": r["ts"],
                          "label": r["final"], "src": r["src"], "features": feat})
    return {"count": len(items), "items": items}


@app.get("/api/metrics", tags=["Hệ thống"])
def metrics():
    """Số liệu tổng hợp cho các thẻ KPI trên dashboard."""
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        ood = conn.execute("SELECT COUNT(*) FROM predictions WHERE ood = 1").fetchone()[0]
        by_src = dict(conn.execute(
            "SELECT src, COUNT(*) FROM labels GROUP BY src").fetchall())
        by_ch = conn.execute("""
            SELECT channel, COUNT(*) AS n, AVG(conf) AS avg_conf
            FROM predictions GROUP BY channel ORDER BY channel""").fetchall()
    return {
        "predictions_total": total,
        "ood_total": ood,
        "ood_rate": round(ood / total, 4) if total else 0,
        "labels_by_source": {k: v for k, v in by_src.items()},
        "per_channel": [{"channel": r["channel"], "count": r["n"],
                         "avg_conf": round(r["avg_conf"], 4)} for r in by_ch],
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Smart PLC Gateway — Backend")
    print("=" * 60)
    print(f"  MQTT   : {MQTT_HOST}:{MQTT_PORT}  (topic {TOPIC_PRED})")
    print(f"  Database: {os.path.abspath(DB_PATH)}")
    print(f"  API    : http://localhost:{API_PORT}")
    print(f"  Thử API: http://localhost:{API_PORT}/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")
