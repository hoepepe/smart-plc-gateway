# Mở lại dashboard và nối đủ chuỗi (dành cho Tuấn)

Dùng khi đã tắt hết và cần bật lại từ đầu. Thư mục dự án: `C:\Users\7560\smart-plc-gateway`.

Chuỗi cần chạy: **PLC (giả hoặc thật) → plc_to_mqtt.py → Mosquitto → Dashboard**.
Mỗi bước dùng **một cửa sổ terminal riêng** (PowerShell hoặc CMD). Không đóng cửa sổ nào khi đang chạy.

## Trước khi bắt đầu: kéo code mới nhất (làm 1 lần)

```
cd C:\Users\7560\smart-plc-gateway
git pull
```

## Cửa sổ 1 — Mosquitto (máy chủ MQTT)

```
cd C:\Users\7560\smart-plc-gateway
"C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v
```

- Thấy dòng `Opening ipv4 listen socket on port 1883` và `...port 9001` là đúng.
- Nếu báo cổng 1883 đã bị dùng: Mosquitto đang chạy ngầm dạng service. Mở PowerShell **Run as administrator**, gõ `net stop mosquitto`, rồi chạy lại lệnh trên.

## Cửa sổ 2 — PLC

Chọn **một** trong hai.

**A. PLC giả lập (không cần phòng lab):**
```
cd C:\Users\7560\smart-plc-gateway
python tools\plc_gia_lap.py
```
Thấy `PLC giả lập chờ ở cổng 5000` là được.

**B. PLC thật (ở phòng lab):** không chạy gì ở cửa sổ này. Chỉ cần PLC bật, cắm cáp mạng, laptop đặt IP tĩnh cùng lớp mạng, ví dụ `192.168.1.100`, mask `255.255.255.0`. Kiểm tra bằng `ping 192.168.1.39`. Xem `docs/HuongDan_LapRap_Gateway.md` để biết chi tiết.

## Cửa sổ 3 — Cầu nối PLC → MQTT

**Với PLC giả lập:**
```
cd C:\Users\7560\smart-plc-gateway
python tools\plc_to_mqtt.py --plc 127.0.0.1 --plc-port 5000
```

**Với PLC thật** (cổng là số **thập phân**; GX Works2 nhập hex, ví dụ `1388` hex = `5000` thập phân):
```
python tools\plc_to_mqtt.py --plc 192.168.1.39 --plc-port 5000
```

Thấy terminal in giá trị liên tục là đang đọc được. Thêm `--log-csv cycles_M01.csv` nếu muốn lưu dữ liệu cho Duy.

## Cửa sổ 4 — Dashboard

```
cd C:\Users\7560\smart-plc-gateway
npm install      (chỉ cần lần đầu)
npm run dev
```

Mở trình duyệt vào **http://localhost:3000**.

## Kiểm tra đã nối đúng chưa

- Góc dashboard hiện **"Đã nối gateway"** (nếu hiện "Chế độ mô phỏng" thì chưa nối).
- Máy M01 có số liệu thay đổi liên tục, số chu kỳ tăng dần.
- Chỉ máy M01 lấy dữ liệu từ gateway; các máy khác trên dashboard là dữ liệu mẫu.

## Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `python` không nhận lệnh | Cài Python 3.14 (không dùng 3.15), tích "Add to PATH" |
| `No module named numpy` / `paho` / `pymcprotocol` | `pip install numpy paho-mqtt pymcprotocol` |
| `unknown slot ID` khi import numpy | Đang dùng Python 3.15, đổi sang 3.14 |
| `mosquitto` không nhận lệnh | Dùng đường dẫn đầy đủ như ở cửa sổ 1 |
| Dashboard vẫn "Chế độ mô phỏng" | Kiểm tra cửa sổ 1 còn chạy và có cổng 9001; tải lại trang (Ctrl+F5) |
| Cầu nối báo lỗi kết nối PLC | PLC giả: cửa sổ 2 đã chạy chưa. PLC thật: ping được IP chưa, cổng thập phân đúng chưa |

## Thứ tự khi tắt

Đóng ngược lại: dashboard → cầu nối → PLC giả → Mosquitto (Ctrl+C ở mỗi cửa sổ).
