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

## Dashboard đổi theo loại máy

PLC không tự cho biết nó điều khiển máy gì: thanh ghi D300 chỉ là một con số. Nên kỹ sư chọn **loại máy một lần**
trong form "Thêm máy". Sau đó dashboard tự nói đúng ngôn ngữ của máy đó. Thuật toán AI vẫn giống nhau cho mọi loại.

| Loại máy | Tín hiệu | Một chu kỳ gọi là | Mã hàng gọi là | Gợi ý loại lỗi khi bấm "Đúng là lỗi" |
|---|---|---|---|---|
| Máy ép (press-fit) | Lực ép (kN) | lần ép | Mã hàng | Thiếu chi tiết, lệch vị trí, ép hai lần… |
| Máy siết bu-lông | Mô-men siết (N·m) | lần siết | Mã bu-lông | Trờn ren, ren chéo, chưa đủ lực… |
| Máy CNC phay / tiện | Tải trục chính (%) | chu kỳ gia công | Chương trình NC | Mòn dao, gãy/mẻ dao, rung (chatter)… |
| Máy hàn điểm | Dòng hàn (kA) | điểm hàn | Chương trình hàn | Thiếu ngấu, bắn tóe, điện cực mòn… |
| Máy ép phun nhựa | Áp suất phun (MPa) | lần phun | Khuôn | Short shot, ba via, co ngót… |
| Cụm khí nén / kiểm tra rò | Áp suất khí (bar) | chu kỳ | Mã hàng | Rò khí, nguồn khí yếu, van kẹt |
| Máy khác | Tín hiệu quá trình | chu kỳ | Mã hàng | (kỹ sư tự gõ) |

Những gì đổi theo loại máy:
- biểu tượng và tên loại trên thẻ máy
- tên tín hiệu và đơn vị
- cách gọi chu kỳ và mã hàng
- tên các đặc trưng trong cảnh báo, ví dụ máy CNC hiện "độ rung tải (chatter)" thay vì "độ gồ ghề"
- danh sách loại lỗi bấm nhanh
- thanh ghi gợi ý trong form

Thêm loại máy mới chỉ cần thêm một mục trong `edge/profiles.py`, không phải sửa giao diện.

**Phân loại lỗi dùng chung giữa các máy cùng loại.** Nhãn "Đúng là lỗi · Mòn dao" gắn trên máy CNC số 1 cũng giúp
máy CNC số 2 đoán loại lỗi, kể cả khi hai máy chạy mức tải khác nhau. Lý do: mỗi chu kỳ lỗi được quy về "lệch bao nhiêu
lần độ lệch thường" so với chuẩn của chính máy đó. Máy khác loại thì không dùng chung.

## Kiểm chứng độ chính xác ngay tại nhà máy

Không cần mua thêm đồ đo. Công nhân kiểm chi tiết bằng cách quen thuộc ở chuyền (nhìn, dưỡng go/no-go,
trạm kiểm tra sẵn có) rồi bấm một nút.

| Ở đâu | Làm gì | Dashboard tính ra |
|---|---|---|
| Nút trên dashboard (quét QR trên OLED → trang của máy) | Đúng là lỗi / Báo nhầm / Bình thường mới trên từng cảnh báo | Cảnh báo đúng = lỗi thật / cảnh báo đã xác nhận |
| **Nút NG / OK trên hộp gateway** | NG = đúng là lỗi, OK = báo nhầm, cho cảnh báo mở gần nhất (15 phút). Không có cảnh báo mà bấm NG → "AI bỏ sót" | như trên |
| "Báo lỗi AI bỏ sót" (dashboard) | Trạm kiểm tra cuối chuyền phát hiện lỗi mà AI không báo → chọn chu kỳ đó | Lỗi AI bắt được = lỗi AI bắt / lỗi đã biết |
| **"Kiểm tra mẫu NG chuẩn"** | Đầu ca bấm Bắt đầu, cho chạy 1–5 chi tiết lỗi chuẩn từ kho mẫu NG. AI phải bắt hết. Các chu kỳ này không tạo cảnh báo, không dùng để học | Lịch sử "AI bắt 3/3 ✓" |

Tất cả nằm trong tab **Máy và AI tự học → chọn máy → ô "Độ chính xác thực tế tại máy"** (hiện khi máy đang giám sát).

**Đèn trên hộp gateway:** xanh = bình thường · vàng = đang học / chờ duyệt / đang kiểm tra mẫu NG ·
đỏ nháy = có cảnh báo AI chưa xác nhận · đỏ sáng liền = mất kết nối PLC. Bấm nút → đèn nháy xác nhận.

Phần cứng: `firmware/nut_xac_nhan/nut_xac_nhan.ino` (nút GPIO32/33, LED GPIO25/27, còi GPIO14), nắp hộp có
2 lỗ nút Ø12 và 3 lỗ LED. Cầu nối USB ↔ MQTT trên laptop:

```
python tools/nut_bam_bridge.py --serial COM5 --machine M01     # có ESP32
python tools/nut_bam_bridge.py --ban-phim --machine SIM-EP1    # chưa có ESP32: gõ n = NG, o = OK
```

**Kết quả kiểm chứng đầy đủ** (so với giới hạn PLC, Isolation Forest, dữ liệu thật Bosch, PLC thật) xem ở tab
**Kiểm chứng AI** trên dashboard, hoặc `ml/reports/do_tin_cay.md`.

## Chạy thử không cần PLC (máy mô phỏng)

```
mosquitto -c mosquitto.conf -v               # hoặc dịch vụ Mosquitto đang chạy sẵn
pip install -r edge/requirements.txt
python -m edge.runtime --demo                 # 4 máy mô phỏng: ép, siết (2 mã bu-lông), CNC (2 chương trình NC), khí nén (tự duyệt)
npm run dev                                   # mở http://localhost:3000 → tab "Máy và AI tự học"
```

Máy mô phỏng chạy nhanh (khoảng 4 chu kỳ/giây), nên xem hết vòng đời học → duyệt → giám sát trong khoảng 1 phút.
Chạy lại từ đầu thì thêm `--fresh` để xoá dữ liệu cũ (`edge_data/edge.db`).

## Chạy với PLC Mitsubishi thật

```
python -m edge.runtime --add-plc 192.168.1.39:3000                          # máy ép, tín hiệu D100
python -m edge.runtime --add-plc 192.168.1.39:3000 --type cnc --signal D100  # cùng PLC nhưng trình bày như máy CNC
```

`--type` nhận: press, torque, cnc, weld, injection, air, generic.

Lệnh này khai báo nhanh máy M01 với cấu hình: tín hiệu theo loại máy (máy ép: D100 × 0,01), word trạng thái M0 (bit 3 = đang làm việc),
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
| `gw/01/m/{máy}/andon` (giữ lại) | màu đèn trên hộp gateway `{color, blink, text}` |
| `gw/01/m/{máy}/button` → `button_ack` | nút trên hộp gateway gửi `{"label": "fault"\|"false_alarm"}` |
| `gw/01/cmd` → `gw/01/ack` | lệnh `{id, op, …}`: add_machine, update_machine, remove_machine, approve, reject, relearn, rollback, retrain_now, feedback, set_ai, ng_check_start, ng_check_cancel, report_missed, sim_inject (máy mô phỏng) |

## Nói gì khi trình bày

- *"Lắp vào máy mới, gateway tự học chuẩn bình thường trong một ca. Không cần dữ liệu lịch sử, không cần chuyên gia AI."*
- *"AI không tự âm thầm thay đổi: mỗi lần học lại là một phiên bản, kỹ sư duyệt, sai thì quay về."*
- *"Chúng em theo dõi độ dịch so với chuẩn gốc, nên hao mòn từ từ vẫn lộ ra dù AI học lại định kỳ."*

## Giới hạn hiện tại (nói thật nếu được hỏi)

- Số đo đầy đủ, có so với giới hạn PLC và Isolation Forest, kèm khoảng tin cậy 95%: [ml/reports/do_tin_cay.md](../ml/reports/do_tin_cay.md) (tạo lại bằng `python ml/danh_gia_do_tin_cay.py`).
  - Mô phỏng 4 loại máy (học lẫn 2% lỗi không ai biết, kiểm tra trên 10 ca khác): AI bắt 81–100% lỗi, báo nhầm 0,2–2,2%; giới hạn PLC bắt 30–48%.
  - Dữ liệu thật Bosch CNC: có kỹ sư phản hồi thì AUC 0,90 (0,83–0,96), bắt 7/9 lỗi, nhưng báo nhầm ~19% — chưa đủ để chạy không cần người duyệt.
  - Khí nén còn yếu nhất: van kẹt bắt ~63%.
- Báo nhầm và Bình thường mới: đủ 5 nhãn thì AI tự tạo bản học lại chờ duyệt (không đợi lần học lại định kỳ).
- Chưa tự nhận ra loại máy từ hình dạng tín hiệu; kỹ sư chọn một lần khi thêm máy.
- Các tab cũ (Giám sát máy, OEE, Phát hiện bất thường) vẫn là demo cố định 4 máy. Tab "Máy và AI tự học" là phần tự đổi theo máy.
- Driver mới có Mitsubishi MC 3E. Omron FINS và Keyence chưa làm.
- Ngưỡng phân vị 99,5 → mục tiêu báo nhầm khoảng 0,5–1% mỗi tầng. Con số thật phải đo trên máy thật.
