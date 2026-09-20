# Smart PLC Gateway

Cổng kết nối giá rẻ giúp thu thập dữ liệu từ máy công nghiệp đời cũ, có khả năng **tự nhận diện loại tín hiệu** và **biết khi nào nó không nhận ra**.

> Bài dự thi **DENSO Factory Hacks 2026 — Đề D1** (Kết nối PLC–IPC giá rẻ để thu dữ liệu).

---

## Bài toán

Nhà máy có nhiều máy đời cũ. Dữ liệu cảm biến bên trong không lấy ra được, và nhiều máy đã mất tài liệu kỹ thuật nên kỹ sư không biết dây nào đo đại lượng gì. Theo đề bài, chi phí trang bị IoT cho một máy hiện khoảng **30 triệu đồng**.

Dự án này làm một gateway giá **dưới 1 triệu đồng**: đấu dây vào, thiết bị tự phân tích dạng sóng và đoán ra tín hiệu đang đo gì, rồi đẩy dữ liệu lên hệ thống giám sát.

Điểm thiết kế quan trọng nhất: khi gặp tín hiệu chưa từng thấy, hệ thống **báo "không nhận ra" thay vì đoán bừa**.

---

## Cấu trúc

```
src/
  App.tsx              Điều phối trạng thái, vòng lặp tín hiệu, kết nối MQTT
  types.ts             Kiểu dữ liệu dùng chung
  components/          Navbar, ConsoleTab, EvaluationTab, RoiTab, Oscilloscope, ...
  utils/
    signal.ts          Trích đặc trưng + phân loại (bản mô phỏng cho giao diện)
    mqtt.ts            Kết nối MQTT WebSocket, tự rơi về demo sau 3 giây
  data/metrics.ts      Số liệu đánh giá, xuất từ ml/metrics.json

ml/
  features.py          Trích đặc trưng — BẢN CHUẨN của toàn dự án
  signals.py           Sinh tín hiệu mô phỏng, tách tập theo phiên
  train_eval.py        Huấn luyện + đánh giá, xuất metrics.json
  analysis.py          PCA, đường cong học, phát hiện lỗi, suy giảm -> analysis.json
  gateway_sim.py       Giả lập gateway, phát MQTT thật

backend/
  main.py              Nhận MQTT → lưu SQLite → phục vụ REST API
  requirements.txt
```

## Luồng dữ liệu

```
gateway (hoặc gateway_sim.py)
        │ MQTT  gw/01/ch/{n}/pred
        ▼
   Mosquitto broker
        ├──── WebSocket 9001 ────► dashboard (hiển thị realtime)
        └──── TCP 1883 ──────────► backend/main.py ──► SQLite
                                          │
                                          └──► REST API :8000
```

---

## Chạy thử

### Giao diện web

```bash
npm install
npm run dev
```

Mở `http://localhost:3000`. Không có MQTT broker thì giao diện tự chạy ở chế độ demo.

### Huấn luyện và đánh giá mô hình

```bash
cd ml
pip install numpy scipy scikit-learn joblib
python train_eval.py
```

In ra ma trận nhầm lẫn, so sánh với baseline, và xuất `model.joblib` + `metrics.json`.

### Phân tích bổ sung

```bash
python analysis.py
```

Xuất `analysis.json` cho tab **Phân tích chuyên sâu** trên dashboard, gồm bốn phần:

| Phần | Nội dung | Kết quả đo được |
|---|---|---|
| Bản đồ đặc trưng | Chiếu 16 đặc trưng xuống 2 chiều bằng PCA | 2 thành phần giữ 71.6% phương sai |
| Đường cong học | Số lần kỹ sư can thiệp qua 5 đợt triển khai | 3 lần cho 20 máy, so với 20 lần nếu làm thủ công |
| Phát hiện lỗi lắp đặt | 5 dạng lỗi, hai lớp bảo vệ | Đấu ngược cực 100% (luật), dây lỏng 100% (mô hình), kênh chết 100%, nhiễu trắng 70%, bão hòa 60% |
| Suy giảm cảm biến | Cảm biến xuống cấp dần qua 12 tháng | Cảnh báo lẻ tẻ từ tháng 7, vượt ngưỡng tháng 11 |

Sau khi chạy, copy `analysis.json` sang `src/data/` để dashboard đọc.

### Backend (nhận MQTT, lưu dữ liệu, phục vụ API)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

API chạy ở `http://localhost:8000`, tài liệu tương tác tại `http://localhost:8000/docs`.
Không có broker vẫn chạy được — API hoạt động bình thường, chỉ là không nhận dữ liệu mới.

| Endpoint | Công dụng |
|---|---|
| `GET /api/health` | Backend sống chưa, đã nối MQTT chưa, đã nhận bao nhiêu bản tin |
| `GET /api/channels` | Trạng thái mới nhất của từng kênh |
| `GET /api/channels/{n}/history` | Lịch sử phán đoán một kênh, có phân trang |
| `POST /api/channels/{n}/label` | Kỹ sư xác nhận nhãn, gửi ngược xuống gateway |
| `GET /api/labels` | Nhật ký gán nhãn |
| `GET /api/training-data` | Xuất cặp (đặc trưng, nhãn) để huấn luyện lại |
| `GET /api/metrics` | Số liệu tổng hợp cho KPI |

Dữ liệu lưu vào `backend/gateway.db` (SQLite, tự tạo khi chạy lần đầu).

### Giả lập gateway phát MQTT

```bash
pip install paho-mqtt
python gateway_sim.py --dry-run   # in ra màn hình, không cần broker
python gateway_sim.py             # phát MQTT thật
```

Cấu hình Mosquitto (`mosquitto.conf`) — **nhớ bật cả cổng WebSocket**, nếu không trình duyệt không kết nối được:

```
listener 1883
protocol mqtt

listener 9001
protocol websockets

allow_anonymous true
```

---

## Về các con số trong dự án

Toàn bộ số liệu ở tab **Đánh giá mô hình** đo trên **dữ liệu mô phỏng**, chưa phải tín hiệu PLC thật.

Hai điều cần nói rõ:

**Vì sao độ chính xác đạt 100%.** Tín hiệu mô phỏng sinh bằng công thức toán nên bốn loại tách nhau rất rõ. Tín hiệu thật từ máy trong xưởng sẽ nhiễu hơn nhiều, và con số này chắc chắn giảm. Kết quả hiện tại cho thấy quy trình huấn luyện và đánh giá chạy đúng, chưa nói lên độ tin cậy khi lắp vào nhà máy.

**Hai lớp bảo vệ, không lớp nào thay được lớp kia.** Đấu ngược cực làm điện áp đảo dấu nhưng giữ nguyên mọi đặc trưng thống kê, và `features.py` chuẩn hóa biên độ nên mô hình bắt 0% — luật kiểm tra dải tuyệt đối bắt 100%. Ngược lại, dây lỏng nằm trong dải hợp lệ nên luật chỉ bắt 3%, mô hình bắt 100%. Vì vậy `checkWiring()` chạy trước mô hình, và cả hai cùng tồn tại.

**Ngưỡng tin cậy một mình không phát hiện được tín hiệu lạ.** Đo được: chỉ dùng ngưỡng tin cậy bắt được 8.3%; thêm mô hình one-class (Isolation Forest) lên 100%, báo động giả 3.1%. Random Forest vẫn cho độ tin cậy tới 0.93 trên tín hiệu chưa từng thấy, vì nó buộc phải chọn một trong các lớp đã biết.

Các thông số phần cứng đánh dấu **"chưa đo"** sẽ được cập nhật sau khi lắp ráp và nạp firmware.

---

## Lưu ý kỹ thuật

`utils/signal.ts` dùng **luật ngưỡng viết tay** để giao diện chạy được realtime trong trình duyệt. Mô hình thật (Random Forest + Isolation Forest, scikit-learn) nằm ở `ml/train_eval.py` và chạy trên thiết bị. Hai bản này khác nhau về số đặc trưng và kích thước cửa sổ — mọi con số công bố đều lấy từ bản Python.

`ml/features.py` là **bản chuẩn duy nhất** cho việc trích đặc trưng. Thứ tự đặc trưng trong đó không được đổi; nếu thêm, thêm vào cuối và tăng `FEATURE_VERSION`.
