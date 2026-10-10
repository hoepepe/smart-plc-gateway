"""
quality.py — Kiểm tra chất lượng dữ liệu của một chu kỳ TRƯỚC khi đưa cho AI.

Mục đích: tách "lỗi tín hiệu / kết nối" khỏi "lỗi máy". Cảm biến đứng im, giá trị vượt dải vật lý hay
đọc PLC bị hụt mẫu thì báo là vấn đề dữ liệu, không chấm điểm, không học, không báo nhầm thành lỗi máy.
"""
import numpy as np

ISSUES_VI = {
    "too_short": "chu kỳ quá ngắn (ít hơn 8 lần đọc)",
    "frozen": "tín hiệu đứng im cả chu kỳ — cảm biến hoặc thanh ghi không cập nhật",
    "out_of_range": "giá trị vượt dải vật lý khai báo",
    "gaps": "đọc PLC bị hụt mẫu (mất kết nối giữa chừng)",
}


def check(y, ts=None, vmin=None, vmax=None, rate=100):
    y = np.asarray(y, dtype=float)
    issues = []
    if len(y) < 8:
        return ["too_short"]
    if np.ptp(y) <= max(1e-9, 1e-3 * max(abs(float(np.median(y))), 1e-6)):
        issues.append("frozen")
    if (vmin is not None and y.min() < vmin) or (vmax is not None and y.max() > vmax):
        issues.append("out_of_range")
    if ts is not None and len(ts) > 2:
        dt = np.diff(np.asarray(ts, dtype=float))
        # khoảng hở lớn hơn 10 chu kỳ đọc chiếm hơn 5% thời gian chu kỳ
        big = dt[dt > 10.0 / rate].sum()
        if big > 0.05 * (ts[-1] - ts[0]):
            issues.append("gaps")
    return issues
