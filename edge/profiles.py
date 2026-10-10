"""
profiles.py — Hồ sơ loại máy. Thuật toán AI giống nhau cho mọi máy; hồ sơ chỉ đổi CÁCH GỌI TÊN
để dashboard nói đúng ngôn ngữ của từng loại máy:
tên tín hiệu, đơn vị, chữ "chu kỳ" gọi là gì, mã hàng gọi là gì, tên các đặc trưng, gợi ý loại lỗi.

PLC không tự cho biết nó đang điều khiển máy gì (thanh ghi chỉ là con số), nên kỹ sư chọn loại máy
MỘT LẦN khi khai báo. Mọi thứ sau đó dashboard tự đổi theo.
"""

GENERIC_FEATURES = {
    "peak": "giá trị đỉnh", "trough": "giá trị đáy", "t_peak": "thời điểm đạt đỉnh",
    "mean_level": "mức trung bình", "rise_slope": "độ dốc lên", "roughness": "độ gồ ghề",
    "n_peaks": "số đỉnh", "early_level": "mức đoạn đầu", "mid_level": "mức đoạn giữa",
    "duration_s": "thời gian chu kỳ",
}

PROFILES = {
    "press": dict(
        label="Máy ép (press-fit)", icon="press", process="PRESS_FORCE",
        signal="Lực ép", unit="kN", cycle="lần ép", recipe="Mã hàng",
        features={"peak": "lực ép cực đại", "t_peak": "thời điểm đạt lực đỉnh", "rise_slope": "tốc độ tăng lực",
                  "roughness": "độ giật của lực", "n_peaks": "số lần ép trong chu kỳ", "early_level": "lực đoạn đầu hành trình",
                  "mid_level": "lực giữa hành trình", "duration_s": "thời gian ép"},
        faults=["Thiếu chi tiết", "Chi tiết lệch vị trí", "Ép hai lần", "Chi tiết sai kích thước"],
        sim=True),
    "torque": dict(
        label="Máy siết bu-lông", icon="torque", process="TORQUE",
        signal="Mô-men siết", unit="N·m", cycle="lần siết", recipe="Mã bu-lông",
        features={"peak": "mô-men cuối", "t_peak": "thời điểm đạt mô-men", "rise_slope": "độ dốc siết",
                  "early_level": "mô-men lúc vặn tự do", "mid_level": "mô-men lúc chạm mặt", "roughness": "độ giật mô-men",
                  "duration_s": "thời gian siết"},
        faults=["Trờn ren", "Ren chéo", "Chưa đủ lực", "Thiếu bu-lông"],
        sim=True),
    "cnc": dict(
        label="Máy CNC phay / tiện", icon="cnc", process="CNC_LOAD",
        signal="Tải trục chính", unit="%", cycle="chu kỳ gia công", recipe="Chương trình NC",
        features={"peak": "tải cắt cực đại", "trough": "tải nền khi chạy không", "t_peak": "thời điểm tải lớn nhất",
                  "mean_level": "tải cắt trung bình", "rise_slope": "tốc độ tăng tải khi vào dao",
                  "roughness": "độ rung tải (chatter)", "n_peaks": "số lần ăn dao", "early_level": "tải đoạn đầu chương trình",
                  "mid_level": "tải đoạn giữa chương trình", "duration_s": "thời gian gia công"},
        faults=["Mòn dao", "Gãy / mẻ dao", "Rung (chatter)", "Phôi sai kích thước", "Thiếu dung dịch làm mát"],
        sim=True),
    "weld": dict(
        label="Máy hàn điểm", icon="weld", process="WELD_CURRENT",
        signal="Dòng hàn", unit="kA", cycle="điểm hàn", recipe="Chương trình hàn",
        features={"peak": "dòng hàn cực đại", "mean_level": "dòng hàn trung bình", "rise_slope": "tốc độ lên dòng",
                  "roughness": "độ dao động dòng", "n_peaks": "số xung hàn", "duration_s": "thời gian hàn"},
        faults=["Hàn thiếu ngấu", "Bắn tóe", "Điện cực mòn", "Lệch điện cực"],
        sim=False),
    "injection": dict(
        label="Máy ép phun nhựa", icon="injection", process="INJECTION_PRESSURE",
        signal="Áp suất phun", unit="MPa", cycle="lần phun", recipe="Khuôn",
        features={"peak": "áp phun cực đại", "mid_level": "áp giữ (holding)", "t_peak": "thời điểm chuyển V/P",
                  "rise_slope": "tốc độ tăng áp", "roughness": "độ dao động áp", "duration_s": "thời gian chu kỳ phun"},
        faults=["Thiếu nhựa (short shot)", "Ba via (flash)", "Co ngót", "Nhựa ẩm"],
        sim=False),
    "air": dict(
        label="Cụm khí nén / kiểm tra rò", icon="air", process="AIR_PRESSURE",
        signal="Áp suất khí", unit="bar", cycle="chu kỳ", recipe="Mã hàng",
        features={"trough": "áp thấp nhất khi xi-lanh chạy", "mean_level": "áp trung bình", "roughness": "độ giật áp",
                  "mid_level": "áp lúc hồi", "duration_s": "thời gian chu kỳ"},
        faults=["Rò khí", "Nguồn khí yếu", "Van kẹt"],
        sim=True),
    "generic": dict(
        label="Máy khác", icon="generic", process="GENERIC",
        signal="Tín hiệu quá trình", unit="", cycle="chu kỳ", recipe="Mã hàng",
        features={}, faults=[], sim=False),
}

PROCESS_TO_TYPE = {p["process"]: k for k, p in PROFILES.items()}


def public():
    """Hồ sơ gửi lên dashboard (tên đặc trưng đã gộp với tên chung)."""
    return {k: dict(label=p["label"], icon=p["icon"], signal=p["signal"], unit=p["unit"], cycle=p["cycle"],
                    recipe=p["recipe"], features={**GENERIC_FEATURES, **p["features"]}, faults=p["faults"],
                    sim=p["sim"])
            for k, p in PROFILES.items()}


def feature_name(machine_type, feature):
    p = PROFILES.get(machine_type) or PROFILES["generic"]
    return p["features"].get(feature) or GENERIC_FEATURES.get(feature, feature)
