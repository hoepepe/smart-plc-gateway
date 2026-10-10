"""
config.py — Khai báo máy: mẫu dựng sẵn + kiểm tra cấu hình kỹ sư nhập từ dashboard.

Một máy = một PLC + một tín hiệu quá trình (thanh ghi) + word trạng thái + (tuỳ chọn) thanh ghi mã lỗi, mã hàng.
"""
import copy
import re

STATES = ["STOPPED", "READY", "AUTO", "WORKING", "DONE", "ERROR"]

BASE = {
    "id": "", "name": "", "line": "", "process": "",
    "plc": {"driver": "mitsubishi_mc", "ip": "192.168.1.39", "port": 3000, "plctype": "Q"},
    "signal": {"register": "D100", "scale": 0.01, "unit": "", "min": None, "max": None},
    "state": {"register": "M0", "bits": {s: i for i, s in enumerate(STATES)}},
    "error_register": "D110",
    "recipe_register": None,
    "segment": {"mode": "bit", "window_s": 5.0},
    "rate_hz": 100,
    "ai": {"learn_target": 300, "retrain_every": 500, "auto_approve": False},
}

TEMPLATES = {
    "mitsubishi_press": dict(
        label="Mitsubishi Q/L (MC protocol 3E) · máy ép",
        cfg={"process": "PRESS_FORCE", "signal": {"register": "D100", "scale": 0.01, "unit": "kN"}}),
    "mitsubishi_torque": dict(
        label="Mitsubishi Q/L (MC protocol 3E) · máy siết",
        cfg={"process": "TORQUE", "signal": {"register": "D200", "scale": 0.01, "unit": "N·m"}}),
    "sim_press": dict(
        label="Mô phỏng · máy ép (không cần PLC)",
        cfg={"process": "PRESS_FORCE", "plc": {"driver": "simulator"}, "signal": {"unit": "kN"},
             "simulator": {"process": "PRESS_FORCE", "period_s": 0.25, "fault_rate": 0.06, "error_every": 90,
                           "dq_every": 160, "drift_per_1000": 0.03}}),
    "sim_torque": dict(
        label="Mô phỏng · máy siết (không cần PLC)",
        cfg={"process": "TORQUE", "plc": {"driver": "simulator"}, "signal": {"unit": "N·m"},
             "simulator": {"process": "TORQUE", "period_s": 0.3, "fault_rate": 0.05, "error_every": 120,
                           "recipes": ["BOLT-M6", "BOLT-M8"], "recipe_every": 400}}),
    "sim_air": dict(
        label="Mô phỏng · cụm khí nén (không cần PLC)",
        cfg={"process": "AIR_PRESSURE", "plc": {"driver": "simulator"}, "signal": {"unit": "bar"},
             "simulator": {"process": "AIR_PRESSURE", "period_s": 0.35, "fault_rate": 0.05}}),
}

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
    return {k: dict(label=v["label"], cfg=normalize(merge(merge(BASE, v["cfg"]), {"id": "NEW", "name": ""})))
            for k, v in TEMPLATES.items()}
