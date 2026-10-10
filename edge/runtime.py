"""
runtime.py — Chương trình chạy trên gateway (hoặc laptop): đọc nhiều máy, AI tự học tại chỗ, nói chuyện với dashboard qua MQTT.

    python -m edge.runtime                         # chạy các máy đã khai báo (lưu trong edge_data/edge.db)
    python -m edge.runtime --demo                  # tạo sẵn 3 máy mô phỏng để xem toàn bộ vòng đời học → duyệt → giám sát
    python -m edge.runtime --broker 192.168.1.10   # broker ở máy khác

MQTT (gw = mã gateway, mặc định 01):
    gw/{gw}/registry              (giữ lại)  danh sách máy + cấu hình + mẫu dựng sẵn
    gw/{gw}/m/{máy}/state                    trạng thái máy (như cầu nối cũ)
    gw/{gw}/m/{máy}/cycle                    mỗi chu kỳ: đường cong, đặc trưng, điểm, chế độ, cảnh báo
    gw/{gw}/m/{máy}/learn         (giữ lại)  tiến độ học, mô hình đang chạy / chờ duyệt, phiên bản, cảnh báo gần đây
    gw/{gw}/cmd                              lệnh từ dashboard  {"id","op",...}
    gw/{gw}/ack                              trả lời lệnh      {"id","ok","error","result"}

Lệnh (op): add_machine, update_machine, remove_machine, approve, reject, relearn, rollback, retrain_now,
           feedback, set_ai
"""
import argparse
import json
import os
import threading
import time
import traceback

import numpy as np
import paho.mqtt.client as mqtt

from . import detector as DT
from . import quality
from .config import TEMPLATES, from_template, normalize, templates_public
from .learner import Brain
from .sources import make_source
from .store import Store

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "edge_data")


def resample(t, y, rate=DT.RATE):
    """Nội suy về lưới đều `rate` mẫu/giây theo dấu thời gian thật của từng lần đọc."""
    t = np.asarray(t, dtype=float) - t[0]
    n = max(int(round(t[-1] * rate)) + 1, 8)
    return np.interp(np.linspace(0, t[-1], n), t, np.asarray(y, dtype=float))


class Worker:
    def __init__(self, rt, cfg):
        self.rt, self.cfg, self.mid = rt, cfg, cfg["id"]
        self.brain = Brain(self.mid, cfg, rt.store)
        self.stop = threading.Event()
        self.conn = dict(ok=False, msg="Đang khởi động")
        self.state = None
        self.cycles = 0
        self._last_pub = 0
        self.lock = threading.Lock()
        self.th = threading.Thread(target=self._run, daemon=True, name=f"may-{self.mid}")

    def start(self):
        self.th.start()
        return self

    def halt(self):
        self.stop.set()

    def _run(self):
        try:
            make_source(self.cfg).run(self.stop, self.on_conn, self.on_state, self.on_cycle)
        except Exception as e:
            self.on_conn(False, f"Nguồn dữ liệu dừng: {e}")
            traceback.print_exc()

    # ── callback từ nguồn ──
    def on_conn(self, ok, msg):
        changed = ok != self.conn["ok"]
        self.conn = dict(ok=ok, msg=msg, ts=time.time())
        if changed:
            print(f"[{self.mid}] {'KẾT NỐI' if ok else 'MẤT KẾT NỐI'} — {msg}")
        self.publish_status(force=True)

    def on_state(self, st, code):
        if st == self.state and st != "ERROR":
            return
        self.state = st
        p = {"ts": int(time.time() * 1000), "state": st}
        if code:
            p["errorCode"] = code
        self.rt.pub(f"m/{self.mid}/state", p)

    def on_cycle(self, c):
        with self.lock:
            y = resample(c["t"], c["y"]) if c.get("t") else np.asarray(c["y"], dtype=float)
            dq = quality.check(c["y"], c.get("t"), self.cfg["signal"].get("min"), self.cfg["signal"].get("max"),
                               rate=self.cfg.get("rate_hz", 100))
            f = DT.features(y, c.get("duration")) if "too_short" not in dq else None
            ev = self.brain.on_cycle(f, ts=c["ts"], recipe=c.get("recipe"), machine_error=c.get("machine_error"),
                                     dq=dq or None)
            self.cycles += 1
            step = max(1, len(y) // 110)
            out = {"ts": int(c["ts"] * 1000), "y": [round(float(v), 3) for v in y[::step]],
                   "f": [round(float(v), 5) for v in f] if f is not None else None, **{
                       k: v for k, v in ev.items() if k not in ("machine", "ts")}}
            sc = ev.get("score")
            if sc:
                out["norm"] = sc["norm"]
                out["anomalous"] = sc["flag"] and ev["kind"] == "score"
            if c.get("injected"):
                out["injected"] = c["injected"]       # chỉ có ở máy mô phỏng — để kiểm chứng, AI không dùng
            self.rt.pub(f"m/{self.mid}/cycle", out)
            if ev.get("alarm_id") or ev.get("trained") or ev.get("candidate"):
                self.publish_status(force=True)
            else:
                self.publish_status()

    def publish_status(self, force=False):
        now = time.time()
        if not force and now - self._last_pub < 1.0:
            return
        self._last_pub = now
        st = self.brain.status()
        st.update(conn=self.conn, state=self.state, cycles_seen=self.cycles, ts=int(now * 1000),
                  alarms=self.rt.store.alarms(self.mid, 25))
        self.rt.pub(f"m/{self.mid}/learn", st, retain=True)


class Runtime:
    def __init__(self, broker, port, gw, data_dir):
        self.gw = gw
        self.store = Store(os.path.join(data_dir, "edge.db"))
        self.workers = {}
        self.wlock = threading.RLock()
        try:
            self.cli = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=f"edge-{gw}")
        except AttributeError:
            self.cli = mqtt.Client(client_id=f"edge-{gw}")
        self.cli.on_connect = self._on_connect
        self.cli.on_message = self._on_message
        self.cli.will_set(f"gw/{gw}/online", json.dumps({"online": False}), retain=True)
        self.cli.connect(broker, port, keepalive=30)

    # ── MQTT ──
    def pub(self, sub, payload, retain=False):
        self.cli.publish(f"gw/{self.gw}/{sub}", json.dumps(payload, ensure_ascii=False), qos=0, retain=retain)

    def _on_connect(self, cli, *a, **k):
        cli.subscribe(f"gw/{self.gw}/cmd")
        self.pub("online", {"online": True, "ts": int(time.time() * 1000)}, retain=True)
        self.publish_registry()
        with self.wlock:
            for w in self.workers.values():
                w.publish_status(force=True)
        print(f"Đã nối MQTT — gateway {self.gw}")

    def _on_message(self, cli, userdata, msg):
        try:
            cmd = json.loads(msg.payload.decode())
        except Exception:
            return
        rid = cmd.get("id")
        try:
            res = self.handle(cmd)
            self.pub("ack", {"id": rid, "ok": True, "op": cmd.get("op"), "result": res})
        except Exception as e:
            self.pub("ack", {"id": rid, "ok": False, "op": cmd.get("op"), "error": str(e)})

    def publish_registry(self):
        self.pub("registry", {"machines": list(self.store.machines().values()), "templates": templates_public(),
                              "ts": int(time.time() * 1000)}, retain=True)

    # ── máy ──
    def start_machine(self, cfg):
        with self.wlock:
            old = self.workers.pop(cfg["id"], None)
            if old:
                old.halt()
            self.workers[cfg["id"]] = Worker(self, cfg).start()

    def handle(self, cmd):
        op, mid = cmd.get("op"), (cmd.get("machine") or "").upper()
        recipe = cmd.get("recipe") or "*"
        if op in ("add_machine", "update_machine"):
            cfg = normalize(cmd["cfg"])
            exists = cfg["id"] in self.store.machines()
            if op == "add_machine" and exists:
                raise ValueError(f"Mã máy {cfg['id']} đã có")
            self.store.put_machine(cfg)
            self.start_machine(cfg)
            self.publish_registry()
            return {"machine": cfg["id"]}
        if op == "remove_machine":
            with self.wlock:
                w = self.workers.pop(mid, None)
                if w:
                    w.halt()
            self.store.del_machine(mid)
            self.cli.publish(f"gw/{self.gw}/m/{mid}/learn", b"", retain=True)   # xoá bản tin giữ lại
            self.publish_registry()
            return {"machine": mid}
        with self.wlock:
            w = self.workers.get(mid)
        if not w:
            raise ValueError(f"Không có máy {mid}")
        b = w.brain
        if op == "approve":
            res = {"version": b.approve(recipe)}
        elif op == "reject":
            b.reject(recipe); res = {}
        elif op == "relearn":
            b.relearn(recipe); res = {}
        elif op == "rollback":
            b.rollback(recipe, cmd["version"]); res = {"version": int(cmd["version"])}
        elif op == "retrain_now":
            res = {"version": b.retrain_now(recipe)}
        elif op == "feedback":
            res = b.feedback(cmd["alarm_id"], cmd["label"], cmd.get("fault_type"), bool(cmd.get("all_open")))
        elif op == "set_ai":
            cfg = dict(w.cfg)
            cfg["ai"] = {**cfg.get("ai", {}), **(cmd.get("ai") or {})}
            cfg = normalize(cfg)
            self.store.put_machine(cfg)
            b.cfg.update(cfg["ai"])
            w.cfg = cfg
            self.publish_registry()
            res = {"ai": cfg["ai"]}
        else:
            raise ValueError(f"Lệnh không hỗ trợ: {op}")
        w.publish_status(force=True)
        return res

    def run(self):
        for cfg in self.store.machines().values():
            try:
                self.start_machine(normalize(cfg))
            except Exception as e:
                print(f"Bỏ qua máy {cfg.get('id')}: {e}")
        self.cli.loop_forever()


def main():
    ap = argparse.ArgumentParser(description="Smart PLC Gateway — runtime nhiều máy, AI tự học tại chỗ")
    ap.add_argument("--broker", default=os.getenv("MQTT_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    ap.add_argument("--gw", default=os.getenv("GW_ID", "01"))
    ap.add_argument("--data", default=os.getenv("EDGE_DATA", DATA), help="thư mục lưu edge.db")
    ap.add_argument("--demo", action="store_true", help="tạo 3 máy mô phỏng nếu chưa có máy nào")
    ap.add_argument("--fresh", action="store_true", help="xoá dữ liệu cũ (edge.db) trước khi chạy")
    ap.add_argument("--add-plc", metavar="IP:PORT", help="khai báo nhanh 1 PLC Mitsubishi thật (máy ép, D100/M0/D110)")
    a = ap.parse_args()

    if a.fresh:
        p = os.path.join(a.data, "edge.db")
        if os.path.exists(p):
            os.remove(p)
    rt = Runtime(a.broker, a.port, a.gw, a.data)
    if a.demo and not rt.store.machines():
        demo = [from_template("sim_press", id="SIM-EP1", name="Máy ép vòng bi (mô phỏng)", line="Line 2",
                              ai={"learn_target": 160, "retrain_every": 400}),
                from_template("sim_torque", id="SIM-SB1", name="Máy siết bu-lông (mô phỏng)", line="Line 2",
                              ai={"learn_target": 160, "retrain_every": 400}),
                from_template("sim_air", id="SIM-KN1", name="Cụm khí nén (mô phỏng)", line="Line 3",
                              ai={"learn_target": 200, "retrain_every": 500, "auto_approve": True})]
        for cfg in demo:
            rt.store.put_machine(cfg)
    if a.add_plc:
        ip, _, port = a.add_plc.partition(":")
        cfg = from_template("mitsubishi_press", id="M01", name="Máy ép (PLC thật)", plc={"ip": ip, "port": int(port or 3000)})
        rt.store.put_machine(cfg)
    print(f"Máy đã khai báo: {', '.join(rt.store.machines()) or '(chưa có — thêm từ dashboard)'}")
    try:
        rt.run()
    except KeyboardInterrupt:
        print("\nDừng.")


if __name__ == "__main__":
    main()
