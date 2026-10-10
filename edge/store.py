"""
store.py — Lưu trữ cục bộ của gateway (SQLite): cấu hình máy, chu kỳ, phiên bản mô hình, cảnh báo, nhãn.

Một file duy nhất (mặc định edge_data/edge.db), an toàn khi nhiều luồng máy cùng ghi.
"""
import json
import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS machines (id TEXT PRIMARY KEY, cfg TEXT NOT NULL, created REAL);
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, machine TEXT, recipe TEXT, ts REAL,
  f TEXT, score REAL, flag INTEGER DEFAULT 0,
  role TEXT,            -- learn | hold | monitor | excluded | discarded
  reason TEXT,          -- lý do loại (machine_error, dq:...)
  label TEXT,           -- NULL | fault | false_alarm | new_normal
  model_version INTEGER
);
CREATE INDEX IF NOT EXISTS ix_cycles ON cycles(machine, recipe, role, id);
CREATE TABLE IF NOT EXISTS models (
  machine TEXT, recipe TEXT, version INTEGER, status TEXT,   -- pending | active | retired | rejected
  kind TEXT,           -- initial | drift | new_normal | relearn
  note TEXT, body TEXT, created REAL,
  PRIMARY KEY (machine, recipe, version)
);
CREATE TABLE IF NOT EXISTS alarms (
  id INTEGER PRIMARY KEY AUTOINCREMENT, machine TEXT, recipe TEXT, ts REAL, cycle_id INTEGER,
  norm REAL, top TEXT, status TEXT DEFAULT 'open',   -- open | fault | false_alarm | new_normal
  fault_type TEXT, suggestion TEXT, resolved REAL
);
"""


class Store:
    def __init__(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()

    def q(self, sql, args=(), one=False):
        with self.lock:
            cur = self.db.execute(sql, args)
            rows = cur.fetchall()
            return (rows[0] if rows else None) if one else rows

    def x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.lastrowid

    # ── máy ──
    def machines(self):
        return {r["id"]: json.loads(r["cfg"]) for r in self.q("SELECT * FROM machines ORDER BY created")}

    def put_machine(self, cfg):
        self.x("INSERT INTO machines(id,cfg,created) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET cfg=excluded.cfg",
               (cfg["id"], json.dumps(cfg, ensure_ascii=False), time.time()))

    def del_machine(self, mid):
        for t in ("machines",):
            self.x(f"DELETE FROM {t} WHERE id=?", (mid,))
        for t in ("cycles", "models", "alarms"):
            self.x(f"DELETE FROM {t} WHERE machine=?", (mid,))

    # ── chu kỳ ──
    def add_cycle(self, machine, recipe, ts, f, role, score=None, flag=False, reason=None, model_version=None):
        return self.x("INSERT INTO cycles(machine,recipe,ts,f,score,flag,role,reason,model_version) VALUES(?,?,?,?,?,?,?,?,?)",
                      (machine, recipe, ts, json.dumps([round(float(v), 6) for v in f]) if f is not None else None,
                       score, int(bool(flag)), role, reason, model_version))

    def count(self, machine, recipe, role=None, reason_like=None, since_id=0):
        sql, a = "SELECT COUNT(*) c FROM cycles WHERE machine=? AND recipe=? AND id>?", [machine, recipe, since_id]
        if role:
            sql += " AND role=?"; a.append(role)
        if reason_like:
            sql += " AND reason LIKE ?"; a.append(reason_like)
        return self.q(sql, a, one=True)["c"]

    def features(self, machine, recipe, where, args=(), limit=None):
        sql = f"SELECT id, f FROM cycles WHERE machine=? AND recipe=? AND {where} ORDER BY id"
        rows = self.q(sql, (machine, recipe, *args))
        if limit:
            rows = rows[-limit:]
        ids, fs = [r["id"] for r in rows], [json.loads(r["f"]) for r in rows]
        if fs:   # chu kỳ ghi từ phiên bản cũ có ít đặc trưng hơn → chỉ giữ chu kỳ cùng số đặc trưng với chu kỳ mới nhất
            d = len(fs[-1])
            keep = [i for i, f in enumerate(fs) if len(f) == d]
            ids, fs = [ids[i] for i in keep], [fs[i] for i in keep]
        return ids, fs

    def set_role(self, machine, recipe, old, new):
        self.x("UPDATE cycles SET role=? WHERE machine=? AND recipe=? AND role=?", (new, machine, recipe, old))

    # ── mô hình ──
    def models(self, machine, recipe=None):
        if recipe is None:
            rows = self.q("SELECT * FROM models WHERE machine=? ORDER BY recipe, version", (machine,))
        else:
            rows = self.q("SELECT * FROM models WHERE machine=? AND recipe=? ORDER BY version", (machine, recipe))
        return [dict(r) for r in rows]

    def add_model(self, machine, recipe, body, kind, note, status="pending"):
        r = self.q("SELECT MAX(version) v FROM models WHERE machine=? AND recipe=?", (machine, recipe), one=True)
        v = (r["v"] or 0) + 1
        # chỉ giữ một bản chờ duyệt cho mỗi mã hàng
        self.x("UPDATE models SET status='rejected' WHERE machine=? AND recipe=? AND status='pending'", (machine, recipe))
        self.x("INSERT INTO models VALUES(?,?,?,?,?,?,?,?)",
               (machine, recipe, v, status, kind, note, json.dumps(body), time.time()))
        return v

    def model(self, machine, recipe, status=None, version=None):
        if version is not None:
            r = self.q("SELECT * FROM models WHERE machine=? AND recipe=? AND version=?", (machine, recipe, version), one=True)
        else:
            r = self.q("SELECT * FROM models WHERE machine=? AND recipe=? AND status=? ORDER BY version DESC",
                       (machine, recipe, status), one=True)
        if not r:
            return None
        d = dict(r)
        d["body"] = json.loads(d["body"])
        return d

    def set_model_status(self, machine, recipe, version, status):
        self.x("UPDATE models SET status=? WHERE machine=? AND recipe=? AND version=?", (status, machine, recipe, version))

    def recipes(self, machine):
        rs = {r["recipe"] for r in self.q("SELECT DISTINCT recipe FROM cycles WHERE machine=?", (machine,))}
        rs |= {r["recipe"] for r in self.q("SELECT DISTINCT recipe FROM models WHERE machine=?", (machine,))}
        return sorted(rs)

    # ── cảnh báo ──
    def add_alarm(self, machine, recipe, ts, cycle_id, norm, top, suggestion=None):
        return self.x("INSERT INTO alarms(machine,recipe,ts,cycle_id,norm,top,suggestion) VALUES(?,?,?,?,?,?,?)",
                      (machine, recipe, ts, cycle_id, norm, json.dumps(top, ensure_ascii=False),
                       json.dumps(suggestion, ensure_ascii=False) if suggestion else None))

    def alarm(self, aid):
        r = self.q("SELECT * FROM alarms WHERE id=?", (aid,), one=True)
        return dict(r) if r else None

    def alarms(self, machine, limit=30):
        rows = self.q("SELECT * FROM alarms WHERE machine=? ORDER BY id DESC LIMIT ?", (machine, limit))
        out = []
        for r in rows:
            d = dict(r)
            d["top"] = json.loads(d["top"]) if d["top"] else []
            d["suggestion"] = json.loads(d["suggestion"]) if d["suggestion"] else None
            out.append(d)
        return out

    def resolve_alarm(self, aid, status, fault_type=None):
        self.x("UPDATE alarms SET status=?, fault_type=?, resolved=? WHERE id=?", (status, fault_type, time.time(), aid))
        a = self.alarm(aid)
        if a:
            self.x("UPDATE cycles SET label=? WHERE id=?", (status, a["cycle_id"]))
        return a

    def labeled_faults(self, machines):
        """Chu kỳ đã được xác nhận là lỗi (có loại lỗi) của một hoặc nhiều máy: [(f, loại lỗi, máy, mã hàng)]."""
        if isinstance(machines, str):
            machines = [machines]
        ph = ",".join("?" * len(machines))
        rows = self.q(f"""SELECT c.f, a.fault_type, a.machine, a.recipe FROM alarms a JOIN cycles c ON c.id=a.cycle_id
                         WHERE a.machine IN ({ph}) AND a.status='fault' AND a.fault_type IS NOT NULL
                         AND a.fault_type<>''""", tuple(machines))
        return [(json.loads(r["f"]), r["fault_type"], r["machine"], r["recipe"]) for r in rows]
