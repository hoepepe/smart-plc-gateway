"""
sources.py — Nguồn dữ liệu cho từng máy: đọc PLC thật (MC protocol) hoặc máy mô phỏng.

Mỗi nguồn gọi 3 hàm do runtime truyền vào:
    on_conn(ok: bool, msg: str)                 — trạng thái kết nối PLC
    on_state(state: str, error_code: str|None)  — khi trạng thái máy đổi
    on_cycle(dict)                              — khi một chu kỳ kết thúc:
        ts, y (giá trị đã nhân hệ số), t (thời điểm từng lần đọc), duration, machine_error, recipe
Chỉ có lệnh ĐỌC tới PLC.
"""
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml"))
import cycles as C  # noqa: E402

PRIORITY = ["ERROR", "STOPPED", "WORKING", "DONE", "AUTO", "READY"]


def state_from_word(word, bits):
    on = {s for s, b in bits.items() if (word >> b) & 1}
    for s in PRIORITY:
        if s in on:
            return s
    return "STOPPED"


def signed(w):
    w &= 0xFFFF
    return w - 0x10000 if w & 0x8000 else w


class McSource:
    """PLC Mitsubishi qua MC protocol 3E (thư viện pymcprotocol). Cắt chu kỳ theo bit WORKING hoặc khung thời gian."""

    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, stop, on_conn, on_state, on_cycle):
        import pymcprotocol
        c = self.cfg
        period = 1.0 / float(c.get("rate_hz", 100))
        bits = c["state"]["bits"]
        scale = c["signal"]["scale"]
        backoff = 1.0
        while not stop.is_set():
            try:
                plc = pymcprotocol.Type3E(plctype=c["plc"].get("plctype", "Q"))
                plc.connect(c["plc"]["ip"], int(c["plc"]["port"]))
                on_conn(True, f"Đang đọc {c['plc']['ip']}:{c['plc']['port']}")
                backoff = 1.0
                self._loop(plc, stop, period, bits, scale, on_state, on_cycle)
            except Exception as e:  # mất kết nối → thử lại, không làm sập runtime
                on_conn(False, f"Không đọc được PLC: {e}")
                stop.wait(backoff)
                backoff = min(backoff * 2, 15)
            finally:
                try:
                    plc.close()
                except Exception:
                    pass

    def _loop(self, plc, stop, period, bits, scale, on_state, on_cycle):
        c = self.cfg
        seg = c["segment"]
        last_state, buf_t, buf_y, err_seen, recipe = None, [], [], False, None
        armed = False
        win_start = time.time()
        nxt = time.time()
        while not stop.is_set():
            t = time.time()
            v = signed(plc.batchread_wordunits(headdevice=c["signal"]["register"], readsize=1)[0]) * scale
            word = plc.batchread_wordunits(headdevice=c["state"]["register"], readsize=1)[0] & 0xFFFF
            st = state_from_word(word, bits)
            code = None
            if st == "ERROR" and c.get("error_register"):
                code = f"E{plc.batchread_wordunits(headdevice=c['error_register'], readsize=1)[0] & 0xFFFF}"
            if st != last_state:
                on_state(st, code)
                last_state = st
            if st == "ERROR":
                err_seen = True
            if seg["mode"] == "window":
                buf_t.append(t); buf_y.append(v)
                if t - win_start >= float(seg["window_s"]):
                    on_cycle(dict(ts=t, y=buf_y, t=buf_t, duration=t - win_start, machine_error=err_seen,
                                  recipe=recipe or self._recipe(plc)))
                    buf_t, buf_y, err_seen, win_start, recipe = [], [], False, t, None
            else:
                working = bool((word >> bits["WORKING"]) & 1)
                if not armed:
                    armed = not working      # chỉ nhận chu kỳ bắt đầu sau khi runtime chạy
                elif working:
                    if not buf_t:
                        recipe = self._recipe(plc)
                    buf_t.append(t); buf_y.append(v)
                elif buf_t:
                    on_cycle(dict(ts=t, y=buf_y, t=buf_t, duration=buf_t[-1] - buf_t[0], machine_error=err_seen,
                                  recipe=recipe))
                    buf_t, buf_y, err_seen = [], [], False
            nxt += period
            stop.wait(max(0.0, nxt - time.time()))

    def _recipe(self, plc):
        r = self.cfg.get("recipe_register")
        if not r:
            return None
        return str(plc.batchread_wordunits(headdevice=r, readsize=1)[0] & 0xFFFF)


class SimSource:
    """Máy mô phỏng để demo không cần PLC: chu kỳ thật từ bộ sinh ml/cycles.py, thời gian nén lại.

    Có đủ tình huống: chuyển ca (tham số cảm biến đổi nhẹ), lỗi chèn ngẫu nhiên mà máy không báo,
    máy tự báo lỗi, tín hiệu đứng im (lỗi dữ liệu), hao mòn từ từ, đổi mã hàng."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.sim = {"process": cfg.get("process") or "PRESS_FORCE", "period_s": 0.25, "fault_rate": 0.05,
                    "error_every": 0, "dq_every": 0, "drift_per_1000": 0.0, "recipes": None, "recipe_every": 0,
                    "shift_len": 40, **(cfg.get("simulator") or {})}

    def run(self, stop, on_conn, on_state, on_cycle):
        s = self.sim
        proc = s["process"] if s["process"] in C.GEN else "PRESS_FORCE"
        faults = list(C.FAULTS[proc])
        rnd = random.Random(hash(self.cfg["id"]) & 0xFFFF)
        on_conn(True, "Máy mô phỏng (không có PLC)")
        k, seed, queue = 0, (hash(self.cfg["id"]) & 0xFFF) * 100, []
        recipes = s["recipes"] or [None]
        while not stop.is_set():
            if not queue:
                seed += 1
                queue = C.make_session(proc, int(s["shift_len"]), seed)
            k += 1
            ri = (k // s["recipe_every"]) % len(recipes) if s["recipe_every"] else 0
            recipe = recipes[ri]
            y = np.asarray(queue.pop(0), dtype=float)
            fault = None
            if rnd.random() < s["fault_rate"]:
                fault = rnd.choice(faults)
                y = np.asarray(C.make_session(proc, 1, rnd.randrange(10 ** 6), fault)[0], dtype=float)
            y = y * (1 + 0.18 * ri) * (1 + s["drift_per_1000"] * k / 1000)
            machine_error = bool(s["error_every"]) and k % s["error_every"] == 0
            if s["dq_every"] and k % s["dq_every"] == 0:
                y = np.full_like(y, y[0])                       # cảm biến đứng im
            on_state("WORKING", None)
            if machine_error:
                on_state("ERROR", "E102")
            dur = len(y) / C.FS
            on_cycle(dict(ts=time.time(), y=y.tolist(), t=None, duration=dur, machine_error=machine_error,
                          recipe=recipe, injected=fault))
            on_state("DONE", None)
            stop.wait(float(s["period_s"]))


def make_source(cfg):
    return SimSource(cfg) if cfg["plc"]["driver"] == "simulator" else McSource(cfg)
