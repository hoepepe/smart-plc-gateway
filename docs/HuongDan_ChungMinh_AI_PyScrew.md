# Chứng minh độ chính xác AI bằng dữ liệu máy thật + PLC thật

Mục tiêu: trả lời câu giám khảo chắc chắn sẽ hỏi — *"AI của các bạn có bắt được lỗi trên máy thật không, hay chỉ trên dữ liệu tự bịa?"*

Ý tưởng: lấy dữ liệu **siết bu-lông công nghiệp thật** có nhãn lỗi (bộ PyScrew, TU Dortmund), cho nó **chạy qua PLC Mitsubishi thật + gateway**, rồi so kết luận của AI với nhãn đúng.

```
PyScrew (máy thật, có nhãn) ─ghi─▶ PLC Q06UDEH ─đọc─▶ ESP32 / laptop ─▶ AI ─▶ so với nhãn đúng
```

## Nói gì khi trình bày (đọc trước)

| Được nói | KHÔNG được nói |
|---|---|
| "AI kiểm chứng trên dữ liệu siết bu-lông công nghiệp công khai, có lỗi thật" | "AI đã chạy trên máy DENSO" |
| "Dữ liệu máy thật đi qua PLC Mitsubishi thật và gateway, AI vẫn chấm đúng X%" | "PLC đo được momen" — PLC chỉ chứa và chuyển dữ liệu |
| Ghi đúng con số script in ra, kể cả loại lỗi bắt kém | Chỉ chọn con số đẹp |

Giấy phép PyScrew: xem trang Zenodo trước khi ghi vào proposal. Thư mục `ml/data/` đã được bỏ khỏi git — không đẩy dữ liệu tải về lên repo.

---

## Phần 1 — Duy: train và đánh giá (laptop có mạng, ~15 phút)

```
cd smart-plc-gateway
git pull
pip install pyscrew numpy scikit-learn
python ml/benchmark_pyscrew.py --scenario s03
```

Lần đầu script tải dữ liệu từ zenodo.org (vài phút). Kết quả:

- `ml/reports/pyscrew_s03.md` — bảng kết quả cho slide
- `ml/models/pyscrew_s03.json` — mô hình để cầu nối dùng
- `ml/data/pyscrew_s03_replay.csv` — 300 chu kỳ kiểm tra (một nửa lỗi) để phát qua PLC

Script so hai bộ đặc trưng:
- **A. Qua PLC** — chỉ một thanh ghi momen, 100 lần/giây: đúng những gì gateway thấy.
- **B. Đầy đủ** — momen + góc ở 833 Hz: trần nếu đọc thêm tín hiệu. Khoảng cách A–B là lý do nên đọc thêm thanh ghi góc khi triển khai thật.

Chạy thêm để có bức tranh đầy đủ:
```
python ml/benchmark_pyscrew.py --scenario s02     # ma sát bề mặt
python ml/benchmark_pyscrew.py --scenario s01     # ren mòn dần: điểm bất thường theo số lần dùng
```
Nếu một kịch bản báo "quá ít lần siết bình thường" thì bỏ qua kịch bản đó.

Gửi Tuấn file `pyscrew_s03_replay.csv` và `pyscrew_s03.json` (qua Drive/Zalo, không qua git).

---

## Phần 2 — Tuấn: thử trên PLC giả lập trước (ở nhà, ~10 phút)

Bốn cửa sổ, đều `cd C:\Users\7560\smart-plc-gateway` trước. Đặt 2 file Duy gửi vào `ml\data\` và `ml\models\`.

1. Mosquitto: `"C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v`
2. PLC giả lập ở chế độ **thụ động** (chỉ giữ giá trị được ghi vào):
   ```
   python tools\plc_gia_lap.py --passive
   ```
3. Cầu nối, dùng mô hình PyScrew và ghi log:
   ```
   python tools\plc_to_mqtt.py --plc 127.0.0.1 --plc-port 5000 --model ml\models\pyscrew_s03.json --scale 0.001 --log-csv log_gia_lap.csv
   ```
4. Phát lại (thử 20 chu kỳ trước):
   ```
   python tools\phat_lai_vao_plc.py ml\data\pyscrew_s03_replay.csv --plc 127.0.0.1 --limit 20
   ```

Xong thì Ctrl+C cửa sổ 3, rồi chấm:
```
python tools\danh_gia_qua_plc.py ml\data\pyscrew_s03_replay.csv log_gia_lap.csv --model ml\models\pyscrew_s03.json
```

---

## Phần 3 — Tuấn: chạy trên PLC thật ở lab

### 3.1 Chuẩn bị PLC (GX Works2)

- **Chuyển PLC sang STOP** (công tắc trên CPU hoặc Online → Remote Operation → STOP). Khi STOP, chương trình ladder không chạy nên không ghi đè D100, D102, M0–M15 (ladder sinh dữ liệu của Tuấn đang dùng M0–M5). Đọc/ghi thanh ghi qua Ethernet vẫn hoạt động khi STOP.
- Nếu muốn để RUN: trong *Built-in Ethernet Port Setting* tích ô cho phép ghi khi RUN (dòng có chữ "Enable online change"), nạp lại tham số, và đảm bảo ladder không đụng D100, D102, M0–M15.
- Open Setting giữ như cũ: TCP, MC Protocol, cổng (nhập hex trong GX Works2, dùng số thập phân ở lệnh dưới).

> Chưa thử lệnh ghi trên PLC thật của nhóm. Nếu script báo lỗi khi ghi, chụp màn hình lỗi gửi lại — thường do chưa cho phép ghi hoặc sai cổng.

### 3.2 Chạy (laptop nối thẳng PLC)

Giống Phần 2, chỉ khác: **không chạy** `plc_gia_lap.py`, và thay `127.0.0.1` bằng `192.168.1.39`:

```
python tools\plc_to_mqtt.py --plc 192.168.1.39 --plc-port 5000 --model ml\models\pyscrew_s03.json --scale 0.001 --log-csv log_plc_that.csv
python tools\phat_lai_vao_plc.py ml\data\pyscrew_s03_replay.csv --plc 192.168.1.39 --plc-port 5000
```

300 chu kỳ mất khoảng 15–20 phút. Chấm:
```
python tools\danh_gia_qua_plc.py ml\data\pyscrew_s03_replay.csv log_plc_that.csv --model ml\models\pyscrew_s03.json --out ket_qua_qua_plc.md
```

### 3.3 Qua ESP32 (bước mạnh nhất)

Firmware `gateway_serial` đã gửi D100, D102, D110, M lên USB, nên không cần sửa firmware. Laptop vẫn chạy `phat_lai_vao_plc.py` (ghi vào PLC qua cổng mạng khác hoặc qua switch), còn cầu nối đọc từ ESP32:
```
python tools\plc_to_mqtt.py --serial COM5 --model ml\models\pyscrew_s03.json --scale 0.001 --log-csv log_esp32.csv
```
Lưu ý: ESP32 phải đọc PLC đủ nhanh (≈100 lần/giây). Nếu chậm hơn, điểm qua chuỗi sẽ lệch nhiều so với offline — đó cũng là một số liệu đáng báo cáo.

### 3.4 Quay video bằng chứng

Màn hình chia đôi: GX Works2 *Device Monitor* (D100, D102 nhảy số) + dashboard / cửa sổ cầu nối in "Chu kỳ #… (D102=…) → BẤT THƯỜNG". Kết thúc video bằng bảng của `danh_gia_qua_plc.py`.

---

## Đọc kết quả

`danh_gia_qua_plc.py` in ba thứ:

1. **Thiếu chu kỳ** — bằng 0 nghĩa là đường truyền không mất chu kỳ nào.
2. **Độ lệch điểm qua PLC so với offline** — nhỏ nghĩa là chuỗi thu thập không làm méo dữ liệu. Thử nghiệm trên PLC giả lập: trung vị khoảng 3%.
3. **Bảng gắn cờ và ma trận nhầm lẫn** — đây là độ chính xác của AI trên dữ liệu máy thật sau khi đi qua PLC.

Nhóm "Lỗi ngầm (máy báo OK)" là con số quan trọng nhất cho DENSO: máy siết tự cho là đạt, PLC không báo gì, chỉ AI phát hiện được.
