# AI tự học tại chỗ — hướng dẫn chạy và trình bày

Mỗi máy có một "chuẩn bình thường" riêng, gateway tự học ngay trên máy đó trong ca đầu tiên.
Không cần dataset lịch sử của nhà máy, không cần nhãn lỗi, không cần người làm AI có mặt.
Thuật toán giống nhau cho mọi máy. Chỉ chuẩn bình thường là khác nhau giữa các máy.

## Vòng đời của mỗi máy (và mỗi mã hàng)

```
Khai báo ──▶ Tự học N chu kỳ ──▶ Kỹ sư duyệt ──▶ Giám sát ──▶ (phản hồi, học lại định kỳ) ──▶ Giám sát
```

| Bước | Gateway làm gì | Người làm gì |
|---|---|---|
| Khai báo | — | Tab **Máy và AI tự học → Thêm máy**: chọn mẫu, nhập IP, cổng, thanh ghi tín hiệu, word trạng thái |
| Tự học | Gom N chu kỳ (mặc định 300). **Loại** chu kỳ máy tự báo lỗi và chu kỳ lỗi tín hiệu. Chưa phát cảnh báo AI. | Để máy chạy bình thường, nên qua ≥ 2 ca |
| Huấn luyện | Lọc chu kỳ nghi lỗi lẫn trong dữ liệu học (lệch > 5 MAD), học chuẩn, chọn ngưỡng bằng **kiểm định chéo theo khối thời gian** (mỗi khối ≈ một khoảng ca) để ngưỡng bao được biến động giữa các ca | — |
| Duyệt | Hiện số chu kỳ học, số chu kỳ tự bỏ, báo nhầm ước tính, chấm thử trên chu kỳ mới | Bấm **Kích hoạt giám sát** hoặc **Học lại từ đầu** |
| Giám sát | Mỗi chu kỳ: điểm (1,0 = ngưỡng), 3 đặc trưng lệch nhiều nhất, gợi ý loại lỗi nếu đủ nhãn | Phản hồi trên mỗi cảnh báo |
| Học lại định kỳ | Sau mỗi `retrain_every` chu kỳ: học lại trên chu kỳ gần đây **không bị cảnh báo, không bị đánh dấu lỗi** → bản chờ duyệt, kèm độ dịch chuẩn so với bản đang chạy và **so với bản gốc** | Duyệt / giữ bản cũ. Bản nào cũng giữ lại, **quay về** được |

**Ba nút phản hồi trên mỗi cảnh báo**

- **Đúng là lỗi** (ghi loại lỗi): thành nhãn. Đủ ≥ 10 nhãn, ≥ 2 loại, mỗi loại ≥ 3 thì tự bật tầng phân loại (Random Forest), cảnh báo sau có dòng "AI đoán: …".
- **Báo nhầm**: chu kỳ được đưa vào dữ liệu học lại.
- **Bình thường mới**: chế độ chạy mới hợp lệ. Đủ 10 chu kỳ thì tự tạo bản học lại. Tick "áp cho mọi cảnh báo đang mở" để gắn nhãn cả loạt.

**Mã hàng:** khai báo thanh ghi mã hàng thì mỗi mã hàng tự học chuẩn riêng. Mã hàng chưa từng chạy sẽ tự vào chế độ học.

**Lỗi tín hiệu khác lỗi máy:** tín hiệu đứng im, vượt dải vật lý, hay đọc PLC bị hụt mẫu thì báo **lỗi tín hiệu**. Những chu kỳ này không được chấm điểm và không được dùng để học.

## Chạy thử không cần PLC (máy mô phỏng)

```
mosquitto -c mosquitto.conf -v               # hoặc dịch vụ Mosquitto đang chạy sẵn
pip install -r edge/requirements.txt
python -m edge.runtime --demo                 # 3 máy mô phỏng: ép, siết (2 mã hàng), khí nén (tự duyệt)
npm run dev                                   # mở http://localhost:3000 → tab "Máy và AI tự học"
```

Máy mô phỏng chạy nhanh (khoảng 4 chu kỳ/giây), nên xem hết vòng đời học → duyệt → giám sát trong khoảng 1 phút.
Chạy lại từ đầu thì thêm `--fresh` để xoá dữ liệu cũ (`edge_data/edge.db`).

## Chạy với PLC Mitsubishi thật

```
python -m edge.runtime --add-plc 192.168.1.39:3000
```

Lệnh này khai báo nhanh máy M01 với cấu hình: tín hiệu D100 × 0,01, word trạng thái M0 (bit 3 = đang làm việc),
mã lỗi D110. Cấu hình khác thì thêm máy từ dashboard. Cổng nhập **số thập phân**, mỗi dòng Open Setting chỉ nhận
một kết nối. Gateway chỉ gửi lệnh **đọc**.

Đã thử với `tools/plc_gia_lap.py` (PLC giả lập MC protocol): runtime kết nối được, cắt chu kỳ theo bit M3,
và loại đúng chu kỳ có máy báo lỗi (M5 + D110).

## MQTT (cho Tuấn và Duy)

| Topic | Nội dung |
|---|---|
| `gw/01/registry` (giữ lại) | danh sách máy + cấu hình + các mẫu |
| `gw/01/m/{máy}/learn` (giữ lại) | chế độ, tiến độ học, mô hình đang chạy / chờ duyệt, phiên bản, 25 cảnh báo gần nhất, trạng thái phân loại |
| `gw/01/m/{máy}/cycle` | mỗi chu kỳ: `y`, `f`, `kind` (learn/preview/score/dq/excluded), `norm`, `score.top`, `alarm_id` |
| `gw/01/m/{máy}/state` | trạng thái máy (giống cầu nối cũ) |
| `gw/01/cmd` → `gw/01/ack` | lệnh `{id, op, …}`: add_machine, update_machine, remove_machine, approve, reject, relearn, rollback, retrain_now, feedback, set_ai |

## Nói gì khi trình bày

- *"Lắp vào máy mới, gateway tự học chuẩn bình thường trong một ca. Không cần dữ liệu lịch sử, không cần chuyên gia AI."*
- *"AI không tự âm thầm thay đổi: mỗi lần học lại là một phiên bản, kỹ sư duyệt, sai thì quay về."*
- *"Chúng em theo dõi độ dịch so với chuẩn gốc, nên hao mòn từ từ vẫn lộ ra dù AI học lại định kỳ."*

## Giới hạn hiện tại (nói thật nếu được hỏi)

- Máy mô phỏng khí nén bắt lỗi kém: với dữ liệu giả lập, ngưỡng chọn được không tách nổi LEAK/VALVE_STICK khỏi biến động áp nguồn giữa các ca. Đây là giới hạn của bộ đặc trưng hiện tại với loại tín hiệu này. Hướng sửa: thêm đặc trưng tương đối (độ sâu đoạn tụt so với mức nền).
- Driver mới có Mitsubishi MC 3E. Omron FINS và Keyence chưa làm.
- Ngưỡng phân vị 99,5 → mục tiêu báo nhầm khoảng 0,5–1% mỗi tầng. Con số thật phải đo trên máy thật.
