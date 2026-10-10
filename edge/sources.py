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


# ───────────── máy CNC mô phỏng: tải trục chính (%) theo chương trình NC ─────────────
CNC_FAULTS = {
    "TOOL_WEAR": "Mòn dao — tải cắt tăng ở mọi lần ăn dao",
    "TOOL_BREAK": "Gãy dao — tải tụt về mức chạy không giữa chừng",
    "CHATTER": "Rung — tải dao động mạnh khi cắt",
}


def _cnc_cycle(rng, s, fault=None):
    """Một chu kỳ gia công: khởi động trục chính (gai tải), 3 lần ăn dao với tải khác nhau, chạy không giữa các lần."""
    n = int(rng.integers(230, 270))
    t = np.linspace(0, 1, n)
    idle = s["idle"]
    y = np.full(n, idle)
    y += 30 * np.exp(-((t - 0.03) / 0.015) ** 2)                       # tăng tốc trục chính
    passes = [(0.10, 0.32, 1.0), (0.40, 0.62, 1.35), (0.70, 0.90, 0.8)]
    for a, b, k in passes:
        a += rng.uniform(-0.01, 0.01); b += rng.uniform(-0.01, 0.01)
        load = s["load"] * k * rng.uniform(0.97, 1.03)
        seg = (t >= a) & (t <= b)
        ramp = np.clip((t - a) / 0.03, 0, 1) * np.clip((b - t) / 0.02, 0, 1)
        y = np.where(seg, idle + load * ramp, y)
    tooth = np.sin(2 * np.pi * t * n / 100 * 40)                         # răng dao cắt 40 Hz
    cutting = y > idle + 2
    y = y + cutting * s["load"] * 0.03 * tooth
    if fault == "TOOL_WEAR":
        y = np.where(cutting, idle + (y - idle) * rng.uniform(1.28, 1.45), y)
    elif fault == "TOOL_BREAK":
        tb = rng.uniform(0.45, 0.8)
        k = (t > tb) & cutting
        y[k] = idle + rng.normal(0, 0.5, k.sum())
        i = int(tb * n)
        y[i:i + 3] += s["load"] * 0.9
    elif fault == "CHATTER":
        y = y + cutting * s["load"] * rng.uniform(0.18, 0.26) * np.sin(2 * np.pi * t * n / 100 * 14)
    return np.clip(y, 0, None)


def cnc_session(n_cycles, seed, fault=None):
    """Một ca trên máy CNC: tải nền, tải cắt (độ cứng lô phôi) và nhiễu cố định trong ca, khác nhau giữa các ca."""
    rng = np.random.default_rng(seed)
    s = {"idle": rng.uniform(6, 9), "load": 40 * rng.uniform(0.94, 1.06), "noise": rng.uniform(0.4, 0.9)}
    out = []
    for _ in range(n_cycles):
        y = _cnc_cycle(rng, s, fault)
        out.append(y + rng.normal(0, s["noise"], len(y)))
    return out


SIM_GEN = {"CNC_LOAD": (cnc_session, CNC_FAULTS)}


def sim_session(proc, n, seed, fault=None):
    if proc in SIM_GEN:
        return SIM_GEN[proc][0](n, seed, fault)
    return C.make_session(proc, n, seed, fault)


def sim_faults(proc):
    return list(SIM_GEN[proc][1]) if proc in SIM_GEN else list(C.FAULTS[proc])


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
        proc = s["process"] if (s["process"] in C.GEN or s["process"] in SIM_GEN) else "PRESS_FORCE"
        faults = sim_faults(proc)
        rnd = random.Random(hash(self.cfg["id"]) & 0xFFFF)
        on_conn(True, "Máy mô phỏng (không có PLC)")
        k, seed, queue = 0, (hash(self.cfg["id"]) & 0xFFF) * 100, []
        recipes = s["recipes"] or [None]
        while not stop.is_set():
            if not queue:
                seed += 1
                queue = sim_session(proc, int(s["shift_len"]), seed)
            k += 1
            ri = (k // s["recipe_every"]) % len(recipes) if s["recipe_every"] else 0
            recipe = recipes[ri]
            y = np.asarray(queue.pop(0), dtype=float)
            fault = None
            if rnd.random() < s["fault_rate"]:
                fault = rnd.choice(faults)
                y = np.asarray(sim_session(proc, 1, rnd.randrange(10 ** 6), fault)[0], dtype=float)
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
