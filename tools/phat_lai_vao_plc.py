"""
phat_lai_vao_plc.py — Phát lại chu kỳ máy THẬT (từ bộ dữ liệu công khai) vào thanh ghi PLC,
để chứng minh độ chính xác của AI khi dữ liệu đi qua ĐÚNG chuỗi PLC → gateway → MQTT → AI.

    Dữ liệu máy thật (PyScrew)  ──ghi MC protocol──▶  PLC  ──đọc──▶  ESP32 / plc_to_mqtt.py  ──▶  AI
                                                        ▲                                           │
                                         D102 = số thứ tự chu kỳ                     so với nhãn đúng
                                                                                     (tools/danh_gia_qua_plc.py)

Thanh ghi dùng (giống máy M01, để ESP32 và cầu nối không phải sửa):
    D100   momen xiết, đơn vị 0,001 N·m           (cầu nối chạy với --scale 0.001)
    D102   số thứ tự chu kỳ (cột tag trong file)  — để đối chiếu với nhãn đúng
    M0..M15 ghi cả word: M2 AUTO + M3 ĐANG LÀM VIỆC trong chu kỳ, M2 + M4 HOÀN THÀNH giữa hai chu kỳ

Cách chạy:
    # PLC giả lập (thử trên laptop):
    python tools/plc_gia_lap.py --passive
    python tools/phat_lai_vao_plc.py ml/data/pyscrew_s03_replay.csv --plc 127.0.0.1

    # PLC thật: xem docs/HuongDan_ChungMinh_AI_PyScrew.md — PLC phải cho phép GHI qua Ethernet,
    # và chương trình ladder KHÔNG được ghi vào D100, D102, M0..M15 trong lúc phát lại.

Nói khi trình bày: PLC ở đây là nơi chứa và chuyển dữ liệu, KHÔNG tự đo. Điều được chứng minh là
dữ liệu máy thật đi qua PLC Mitsubishi thật + gateway mà AI vẫn chấm đúng như khi chạy offline.
"""
import argparse
import csv
import sys
import time

AUTO, WORKING, DONE = 1 << 2, 1 << 3, 1 << 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay_csv", help="file do ml/benchmark_pyscrew.py tạo, vd. ml/data/pyscrew_s03_replay.csv")
    ap.add_argument("--plc", required=True, help="IP PLC (giả lập: 127.0.0.1)")
    ap.add_argument("--plc-port", type=int, default=5000, help="cổng MC protocol, số THẬP PHÂN")
    ap.add_argument("--rate", type=int, default=100, help="mẫu mỗi giây — PHẢI trùng tần số đọc của cầu nối")
    ap.add_argument("--scale", type=float, default=0.001, help="1 đơn vị thanh ghi = bao nhiêu N·m")
    ap.add_argument("--gap", type=float, default=1.5, help="giây nghỉ giữa hai chu kỳ")
    ap.add_argument("--limit", type=int, default=0, help="chỉ phát N chu kỳ đầu (0 = tất cả)")
    a = ap.parse_args()

    import pymcprotocol
    with open(a.replay_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[: a.limit]
    total_s = sum(int(r["n"]) / a.rate + a.gap for r in rows)
    print(f"{len(rows)} chu kỳ, khoảng {total_s / 60:.1f} phút. Mở cầu nối TRƯỚC khi chạy script này.")

    plc = pymcprotocol.Type3E(plctype="Q")
    plc.connect(a.plc, a.plc_port)
    print(f"Đã nối PLC {a.plc}:{a.plc_port}")

    def put(d100=None, d102=None, m=None):
        if d100 is not None and d102 is not None:
            plc.batchwrite_wordunits(headdevice="D100", values=[d100, 0, d102])   # D100, D101, D102
        elif d100 is not None:
            plc.batchwrite_wordunits(headdevice="D100", values=[d100])
        if m is not None:
            plc.batchwrite_wordunits(headdevice="M0", values=[m])

    put(0, 0, AUTO | DONE)
    time.sleep(a.gap)
    slow = 0
    try:
        for k, r in enumerate(rows, 1):
            tag = int(r["tag"])
            ys = [float(v) for v in r["y"].split(";") if v]
            words = [max(-32768, min(32767, round(v / a.scale))) for v in ys]
            put(words[0], tag, None)
            put(m=AUTO | WORKING)
            t0 = time.perf_counter()
            for i, w in enumerate(words):
                put(d100=w)
                target = t0 + (i + 1) / a.rate
                lag = time.perf_counter() - target
                if lag > 0.5 / a.rate:
                    slow += 1
                time.sleep(max(0.0, target - time.perf_counter()))
            put(m=AUTO | DONE)
            put(0, tag, None)
            real_rate = len(words) / (time.perf_counter() - t0)
            print(f"  [{k}/{len(rows)}] tag {tag:>4}  {r['category']:<24} offline điểm {float(r['offline_score']):6.2f}"
                  f"   tốc độ ghi {real_rate:5.1f} mẫu/s")
            time.sleep(a.gap)
    except KeyboardInterrupt:
        print("\nDừng giữa chừng.")
    finally:
        try:
            put(0, 0, AUTO | DONE)
        except Exception:
            pass
    if slow:
        print(f"\nCẢNH BÁO: {slow} lần ghi bị trễ hơn nửa chu kỳ lấy mẫu. Nếu tốc độ ghi in ra < {a.rate * 0.95:.0f} "
              f"mẫu/s thì dạng sóng bị giãn — thử --rate 50 cho CẢ script này lẫn cầu nối (--hz 50).", file=sys.stderr)
    print("Xong. Đánh giá:  python tools/danh_gia_qua_plc.py <file replay> <file log của cầu nối>")


if __name__ == "__main__":
    main()
