# Smart PLC Gateway

Thiết bị giá rẻ đọc dữ liệu từ máy PLC đời cũ — trạng thái máy, lực ép, lực xiết, áp lực khí nén — để tính OEE theo thời gian thực và phát hiện chu kỳ gia công bất thường. Không đụng vào máy: nguồn điện riêng, chỉ đọc, không sửa chương trình PLC.

> Bài dự thi **DENSO Factory Hacks 2026 — đề D1** (Kết nối PLC–IPC giá rẻ để thu dữ liệu).

---

## Bài toán

Theo trả lời của mentor DENSO ngày 21/09/2026:

- DENSO **đã có danh sách tín hiệu** và muốn lấy dữ liệu **trực tiếp từ PLC**
- Hiện dữ liệu PLC đời cũ được lấy **bằng tay qua thẻ nhớ**, và máy cũ **chưa được đưa lên hệ thống giám sát**
- Bộ mở rộng truyền thông cho PLC tốn **khoảng 30 triệu mỗi máy**, chưa tính công và layout
- Ba dòng PLC đang dùng nhiều: **Keyence KV-8000**, **Omron CJ2M-CPU33 và CPM2C**, **Mitsubishi Q10UDEHCPU**
- Điều kiện gia công cần thu: áp lực khí nén, chiều cao, tải trọng, lực ép, lực xiết
- Trạng thái máy: dừng, chuẩn bị vận hành, auto running, đang làm việc, hoàn thành, báo lỗi
- Thiết bị thêm vào phải dùng **nguồn ngoài**, và nên **đi dây** trước để ổn định

Gateway đọc các thanh ghi đó theo giao thức gốc của từng hãng, rồi làm hai việc:
1. **Trạng thái máy → OEE**: độ sẵn sàng, hiệu suất, chất lượng, và nguyên nhân dừng máy xếp theo thời gian mất
2. **Chu kỳ gia công → cảnh báo chất lượng**: chu kỳ ép hoặc siết có hình dạng lạ thường đi kèm chi tiết lỗi

---

## Cấu trúc

```
src/                     Giao diện (React + TypeScript + Vite)
  App.tsx                Điều phối mô phỏng, MQTT và bốn màn hình
  data/machines.ts       Cấu hình 4 máy — PLC, giao thức, thanh ghi, mã lỗi
  data/cycles.json       Tham số mô hình, xuất từ ml/cycles.py
  utils/detector.ts      Khoảng cách Mahalanobis — đúng mô hình đã đánh giá
  utils/oee.ts           OEE = sẵn sàng × hiệu suất × chất lượng
  utils/sim.ts           Mô phỏng vận hành khi chưa có PLC thật
  utils/mqtt.ts          Nối broker, tự về chế độ mô phỏng sau 3 giây
  components/            MonitorTab, OeeTab, DetectionTab, ConnectTab

ml/
  cycles.py              Sinh chu kỳ gia công, huấn luyện và đánh giá, xuất cycles.json
  gateway_sim.py         Giả lập gateway, phát MQTT đúng schema của gateway thật
  legacy_nhan_dien_tin_hieu/   Hướng cũ: AI đoán dây — xem README trong đó

backend/
  main.py                Nhận MQTT → SQLite → REST API, tính OEE và nguyên nhân dừng máy
```

## Luồng dữ liệu

```
PLC (Keyence / Omron / Mitsubishi)
   │  giao thức gốc của hãng, CHỈ ĐỌC
   ▼
Gateway ── tính đặc trưng chu kỳ, chấm điểm bất thường tại chỗ
   │  MQTT  gw/01/m/{máy}/state   gw/01/m/{máy}/cycle
   ▼
Broker MQTT (Mosquitto, trong mạng nội bộ)
   ├── WebSocket 9001 ──► giao diện
   └── TCP 1883 ────────► backend/main.py ──► SQLite ──► REST API :8000
```

---

## Chạy thử

### Giao diện

```bash
npm install
npm run dev
```

Mở `http://localhost:3000`. Không có broker thì giao diện tự chạy chế độ mô phỏng.

### Mô hình phát hiện chu kỳ bất thường

```bash
cd ml
pip install numpy scikit-learn
python cycles.py
cp cycles.json ../src/data/cycles.json
```

### Chạy đủ chuỗi: broker → gateway giả lập → máy chủ → giao diện

Cài Mosquitto, thêm vào `mosquitto.conf` — **phải bật cả cổng WebSocket**, nếu không trình duyệt không nối được:

```
listener 1883
protocol mqtt

listener 9001
protocol websockets

allow_anonymous true
```

Rồi mở ba cửa sổ dòng lệnh:

```bash
mosquitto -c mosquitto.conf                     # 1. broker
cd backend && pip install -r requirements.txt && python main.py   # 2. máy chủ
cd ml && pip install paho-mqtt && python gateway_sim.py            # 3. gateway giả lập
```

Mở giao diện: góc trên đổi thành **Đã nối gateway**. API máy chủ xem tại `http://localhost:8000/docs`.

| Endpoint | Công dụng |
|---|---|
| `GET /api/health` | Máy chủ sống chưa, đã nối MQTT chưa, đã nhận bao nhiêu bản tin |
| `GET /api/machines` | Trạng thái hiện tại và OEE từng máy |
| `GET /api/machines/{id}/states` | Lịch sử trạng thái |
| `GET /api/machines/{id}/cycles` | Chu kỳ gần đây, lọc được chu kỳ bất thường |
| `GET /api/machines/{id}/oee` | OEE một máy |
| `GET /api/stops` | Nguyên nhân dừng máy, xếp theo thời gian mất |

---

## Kết quả đo được

Đo trên chu kỳ **mô phỏng**, tách theo ca làm việc: 20 ca để học, 6 ca để chọn ngưỡng, 6 ca để kiểm tra — không ca nào dùng chung. Chỉ học trên chu kỳ bình thường, vì nhà máy có rất ít dữ liệu lỗi.

| Đại lượng | Bắt lỗi trung bình | Báo động giả |
|---|---|---|
| Lực ép | 99,4% | 0,7% |
| Lực xiết | 100% | 0,7% |
| Áp lực khí nén | 70,6% | 0% |

**Chỗ còn yếu:** van kẹt chỉ bắt được 33%, nguồn khí yếu 78%. Giao diện ghi rõ giả thuyết nguyên nhân và hướng sửa cho từng dạng.

**Vì sao chọn khoảng cách Mahalanobis thay vì Isolation Forest:** trên 9 dạng lỗi, Mahalanobis bắt tốt hơn ở 5 dạng, ngang ở 2, kém ở 2. Nó chỉ cần một vector và một ma trận 9×9 nên chạy được trên ESP32, và chỉ ra được đặc trưng nào lệch — kỹ sư biết vì sao máy bị cảnh báo.

**Chất lượng trong OEE là ước tính** — nó đếm chu kỳ bị gắn cờ, mà chu kỳ bất thường mới là nghi lỗi. Nối kết quả kiểm tra QC sẽ chính xác hơn.

---

## Những điều chưa biết

- **Vì sao cần bộ mở rộng 30 triệu khi cả ba CPU đã có cổng Ethernet?** Nếu cổng đang bận cho HMI, gateway cũng phải thêm phần cứng. Cần hỏi mentor trước khi dùng con số tiết kiệm.
- **Thẻ nhớ được rút bao lâu một lần?** Đây là vế "trước" của phép đo độ trễ dữ liệu.
- **Giao thức và lệnh đọc từng dòng PLC** trong `machines.ts` cần đối chiếu manual của hãng.
- Chưa có PLC thật để thử. Toàn bộ trạng thái máy là mô phỏng.
