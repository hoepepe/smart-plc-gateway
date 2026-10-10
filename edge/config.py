"""
config.py — Khai báo máy: mẫu dựng sẵn + kiểm tra cấu hình kỹ sư nhập từ dashboard.

Một máy = một PLC + một tín hiệu quá trình (thanh ghi) + word trạng thái + (tuỳ chọn) thanh ghi mã lỗi, mã hàng.
"""
import copy
import re

from .profiles import PROFILES, PROCESS_TO_TYPE

STATES = ["STOPPED", "READY", "AUTO", "WORKING", "DONE", "ERROR"]

BASE = {
    "id": "", "name": "", "line": "", "process": "", "machine_type": "",
    "plc": {"driver": "mitsubishi_mc", "ip": "192.168.1.39", "port": 3000, "plctype": "Q"},
    "signal": {"register": "D100", "scale": 0.01, "unit": "", "min": None, "max": None},
    "state": {"register": "M0", "bits": {s: i for i, s in enumerate(STATES)}},
    "error_register": "D110",
    "recipe_register": None,
    "segment": {"mode": "bit", "window_s": 5.0},
    "rate_hz": 100,
    "ai": {"learn_target": 300, "retrain_every": 500, "auto_approve": False},
}

# Thanh ghi gợi ý cho từng loại máy (kỹ sư sửa theo chương trình PLC thật)
_REG = {"press": ("D100", 0.01), "torque": ("D200", 0.01), "cnc": ("D300", 0.1), "weld": ("D400", 0.01),
        "injection": ("D500", 0.1), "air": ("D600", 0.01), "generic": ("D100", 1.0)}
_SIM = {
    "press": {"period_s": 0.25, "fault_rate": 0.06, "error_every": 90, "dq_every": 160, "drift_per_1000": 0.03},
    "torque": {"period_s": 0.3, "fault_rate": 0.05, "error_every": 120, "recipes": ["BOLT-M6", "BOLT-M8"],
               "recipe_every": 400},
    "cnc": {"period_s": 0.3, "fault_rate": 0.05, "error_every": 150, "recipes": ["O1001", "O1002"],
            "recipe_every": 500, "drift_per_1000": 0.02},
    "air": {"period_s": 0.35, "fault_rate": 0.05},
}


def _templates():
    out = {}
    for t, p in PROFILES.items():
        reg, scale = _REG[t]
        common = {"machine_type": t, "process": p["process"], "signal": {"unit": p["unit"]}}
        out[f"mitsubishi_{t}"] = dict(
            label=f"{p['label']} · PLC Mitsubishi Q/L (MC protocol 3E)", machine_type=t, driver="mitsubishi_mc",
            cfg={**common, "signal": {"register": reg, "scale": scale, "unit": p["unit"]}})
        if p["sim"]:
            out[f"sim_{t}"] = dict(
                label=f"{p['label']} · mô phỏng (không cần PLC)", machine_type=t, driver="simulator",
                cfg={**common, "plc": {"driver": "simulator"}, "simulator": {"process": p["process"], **_SIM[t]}})
    return out


TEMPLATES = _templates()

REG = re.compile(r"^(D|W|R|ZR)\d+$", re.I)
BIT = re.compile(r"^(M|X|Y|B|L)[0-9A-F]+$", re.I)


def merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def from_template(template, **over):
    t = TEMPLATES[template]["cfg"]
    return normalize(merge(merge(BASE, t), over))


def normalize(cfg):
    """Điền mặc định và kiểm tra. Lỗi trả về bằng ValueError với câu tiếng Việt dễ hiểu."""
    c = merge(BASE, cfg)
    c["id"] = str(c["id"]).strip().upper()
    if not re.match(r"^[A-Z0-9_-]{1,16}$", c["id"]):
        raise ValueError("Mã máy chỉ gồm chữ, số, '-' hoặc '_' (tối đa 16 ký tự), ví dụ M05")
    c["name"] = str(c["name"]).strip() or c["id"]
    mt = c.get("machine_type") or PROCESS_TO_TYPE.get(c.get("process"), "generic")
    if mt not in PROFILES:
        raise ValueError(f"Loại máy chưa có: {mt}. Có: {', '.join(PROFILES)}")
    c["machine_type"] = mt
    c["process"] = c.get("process") or PROFILES[mt]["process"]
    drv = c["plc"]["driver"]
    if drv not in ("mitsubishi_mc", "simulator"):
        raise ValueError("Driver PLC chưa hỗ trợ. Hiện có: mitsubishi_mc, simulator (Omron FINS, Keyence đang làm)")
    if drv == "mitsubishi_mc":
        ip = str(c["plc"]["ip"]).strip()
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) or any(int(x) > 255 for x in ip.split(".")):
            raise ValueError("IP PLC không hợp lệ, ví dụ 192.168.1.39")
        p = int(c["plc"]["port"])
        if not 1 <= p <= 65535:
            raise ValueError("Cổng phải nằm trong 1–65535 (nhập số THẬP PHÂN)")
        c["plc"]["port"] = p
        if not REG.match(str(c["signal"]["register"])):
            raise ValueError("Thanh ghi tín hiệu phải là word, ví dụ D100")
        if not BIT.match(str(c["state"]["register"])):
            raise ValueError("Word trạng thái phải là bit đầu của một word, ví dụ M0")
        for k in ("error_register", "recipe_register"):
            if c[k] and not REG.match(str(c[k])):
                raise ValueError(f"{k} phải là word, ví dụ D110, hoặc để trống")
    c["signal"]["scale"] = float(c["signal"]["scale"])
    bits = {s: int(v) for s, v in c["state"]["bits"].items() if v is not None and str(v) != ""}
    if "WORKING" not in bits and c["segment"]["mode"] == "bit":
        raise ValueError("Cần khai báo bit 'đang làm việc' (WORKING) để cắt chu kỳ, hoặc chọn cắt theo khung thời gian")
    c["state"]["bits"] = bits
    ai = c["ai"]
    ai["learn_target"] = max(30, int(ai.get("learn_target", 300)))
    ai["retrain_every"] = max(50, int(ai.get("retrain_every", 500)))
    ai["auto_approve"] = bool(ai.get("auto_approve", False))
    return c


def templates_public():
    return {k: dict(label=v["label"], machine_type=v["machine_type"], driver=v["driver"], cfg=normalize(merge(merge(BASE, v["cfg"]), {"id": "NEW", "name": ""})))
            for k, v in TEMPLATES.items()}
