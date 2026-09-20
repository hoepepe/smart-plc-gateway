# Hướng dẫn huấn luyện mô hình

*Dành cho Duy — phụ trách AI, dự án Smart PLC Gateway (đề D1, DENSO Factory Hacks 2026)*

---

## Chạy ngay được, không cần phần cứng

```bash
cd ml
pip install numpy scipy scikit-learn joblib
python train_eval.py
```

Khoảng 10 giây. Sinh ra `model.joblib` (mô hình) và `metrics.json` (số liệu hiển thị trên tab Đánh giá của web).

Dữ liệu huấn luyện do `signals.py` sinh bằng công thức toán. Không cần cảm biến, không cần ESP32.

---

## Hiểu đúng mục tiêu trước khi tối ưu

Mục tiêu **không phải** đẩy độ chính xác lên cao nhất. Nếu chỉ cần con số đẹp thì làm dữ liệu dễ đi là xong — và con số đó vô giá trị.

Mục tiêu là ba thứ, theo thứ tự quan trọng:

**1. Con số đo được phải đáng tin.** Nghĩa là đo trên dữ liệu mô hình chưa từng thấy, và dữ liệu đó phải đủ khó để giống thực tế.

**2. Hệ thống phải biết khi nào nó không biết.** Trong nhà máy, một dự đoán sai mà tự tin nguy hiểm hơn việc không dự đoán gì. Đây là điểm kỹ thuật đáng kể nhất của dự án.

**3. Mô hình phải nhúng được lên ESP32.** Mô hình 99% mà không chạy nổi trên vi điều khiển thì vô dụng.

---

## Bốn nguyên tắc phương pháp — đừng phá vỡ

### Tách tập theo phiên, không tách ngẫu nhiên

Các cửa sổ liền kề trong cùng một phiên thu thập rất giống nhau: cùng cảm biến, cùng nhiễu nền, cùng điều kiện. Tách ngẫu nhiên thì cửa sổ số 10 vào tập train, số 11 vào tập test — mô hình gần như đang được chấm trên dữ liệu nó đã thấy.

`build_dataset()` trong `signals.py` đã tách theo phiên. **Nếu sửa thành `train_test_split` ngẫu nhiên trên toàn bộ cửa sổ, mọi con số sẽ đẹp giả tạo và mất hết giá trị.**

### Không bao giờ ngó sang tập test để chọn tham số

Ngưỡng tin cậy được chọn bằng cross-validation trên tập train (`pick_thresholds`). Ngưỡng one-class được hiệu chuẩn trên một phần tách riêng khỏi phần dùng để fit.

Nếu thử nhiều tham số rồi chọn cái cho kết quả tốt nhất **trên tập test**, tập test đã bị nhiễm và không còn là thước đo độc lập nữa.

### Giữ riêng một lớp chưa từng huấn luyện

Lớp `PRESSURE_BURST` không nằm trong tập train, chỉ dùng để kiểm tra cơ chế phát hiện tín hiệu lạ. Đây là phép thử phân biệt hệ thống thật với hệ thống học thuộc lòng.

### Báo cáo cả cái sai

Ma trận nhầm lẫn đầy đủ, không chỉ accuracy tổng. Nếu một lớp bị nhầm 18%, nói ra. Giám khảo kỹ sư tin đội dám công bố điểm yếu hơn đội chỉ khoe số đẹp.

---

## Hai phát hiện quan trọng đã rút ra

### Ngưỡng tin cậy một mình không phát hiện được tín hiệu lạ

Đo được: chỉ dùng ngưỡng tin cậy bắt được **8.3%** tín hiệu lạ. Thêm mô hình one-class (Isolation Forest) lên **100%**.

Lý do: Random Forest buộc phải chọn một trong bốn lớp đã biết. Gặp tín hiệu chưa từng thấy, nó vẫn cho độ tin cậy tới **0.93**. Nó không có khái niệm "cái này tôi chưa gặp bao giờ".

### Độ tin cậy thấp và tín hiệu lạ là hai chuyện khác nhau

Đây là lỗi thiết kế đã gặp và sửa trong quá trình làm:

| Tình huống | Nghĩa là | Xử lý đúng |
|---|---|---|
| Độ tin cậy thấp | Mô hình phân vân **giữa các lớp đã biết** | `pending` — hỏi kỹ sư |
| One-class gắn cờ | Tín hiệu **không giống bất kỳ lớp nào** | `unknown` — tín hiệu lạ |

Ban đầu code gộp hai thứ này ("độ tin cậy thấp thì coi là lạ"), kết quả báo động giả vọt lên **38.5%** — tín hiệu bình thường nhưng nhiễu cũng bị gắn cờ lạ, không dùng được.

Sau khi tách bạch và hiệu chuẩn lại ngưỡng, còn **1.0%** mà vẫn giữ 100% khả năng bắt tín hiệu lạ.

> Câu chuyện này nên đưa vào pitch deck. Nó cho thấy team hiểu giới hạn của mô hình, không chỉ biết gọi thư viện.

---

## Việc tiếp theo, theo thứ tự ưu tiên

### 1. Làm dữ liệu khó hơn nữa — quan trọng nhất

`signals.py` giờ có biến `DIFFICULTY`. Chế độ `realistic` đã thêm: trôi nền chậm, nhiễu 50 Hz từ lưới điện, gai xung do đóng cắt contactor, mẫu bị ADC đọc hụt, và dải tham số chồng lấn giữa `VIBRATION` với `MOTOR_LOAD`.

Nhưng độ chính xác vẫn 100% — nghĩa là **vẫn chưa đủ khó**. Duy nên tiếp tục:

- Cho hai lớp chồng lấn mạnh hơn nữa (ví dụ `MOTOR_LOAD` chu kỳ nhanh gần như trùng `VIBRATION` tần số thấp)
- Thêm trường hợp biên: cảm biến gần hỏng, tín hiệu bão hòa ở đầu dải, dây tiếp xúc kém gây gián đoạn
- Giảm biên độ tín hiệu xuống gần mức nhiễu

**Khi độ chính xác tụt về khoảng 85–92%, con số mới đáng đưa vào pitch deck.** Một mô hình 88% đo nghiêm túc thuyết phục hơn nhiều so với 100% trên dữ liệu dễ.

### 2. Thêm lớp tín hiệu

Hiện 4 lớp. Thực tế nhà máy còn có áp suất, lưu lượng, vị trí, dòng điện. Thêm lớp làm bài toán khó hơn và sát thực tế hơn.

### 3. Kiểm chứng phát hiện tín hiệu lạ kỹ hơn

Hiện chỉ test với một loại lạ. Duy nên thêm 2–3 loại khác nhau về bản chất — ví dụ tín hiệu nhiễu trắng thuần, tín hiệu chết (đường thẳng), tín hiệu răng cưa. Nếu tỷ lệ bắt được tụt xuống, đó là phát hiện quan trọng cần báo cáo.

### 4. Đo dung lượng và tốc độ để nhúng lên ESP32

Chưa ai làm, và đây là hai ô đang ghi "chưa đo" trong giao diện.

```bash
pip install micromlgen
```

```python
from micromlgen import port
import joblib

m = joblib.load("model.joblib")
code = port(m["clf"])
open("model.h", "w").write(code)
print("Kích thước file C++:", len(code) / 1024, "KB")
```

Nếu file quá lớn so với Flash của ESP32, giảm `n_estimators` hoặc `max_depth` rồi đo lại độ chính xác. Ghi lại cả hai con số — đây chính là đánh đổi cần trình bày.

### 5. Huấn luyện lại từ dữ liệu kỹ sư xác nhận

Backend có endpoint `GET /api/training-data` xuất ra các cặp (đặc trưng, nhãn) tích lũy được từ những lần kỹ sư bấm xác nhận.

Duy viết một script đọc dữ liệu đó, gộp với tập mô phỏng, train lại. Đây là thứ biến câu *"càng dùng càng ít phải can thiệp"* từ lời nói thành cơ chế kiểm chứng được — và là điểm khác biệt lớn nhất của dự án.

---

## Ba file cần đọc kỹ

| File | Vai trò | Lưu ý |
|---|---|---|
| `features.py` | Trích 16 đặc trưng — **bản chuẩn duy nhất của dự án** | Không đổi thứ tự. Thêm thì thêm vào cuối và tăng `FEATURE_VERSION` |
| `signals.py` | Sinh dữ liệu, tách tập theo phiên | Đây là chỗ cần sửa nhiều nhất |
| `train_eval.py` | Quy trình huấn luyện và đánh giá | Giữ nguyên bốn nguyên tắc phương pháp ở trên |

`features.py` là hợp đồng chung giữa ba người: Duy train theo thứ tự đặc trưng đó, Tuấn port đúng thứ tự đó sang C++ cho ESP32, backend kiểm tra chéo bằng chính module đó. Đổi thứ tự là làm hỏng mọi mô hình đã train.

---

## Khi có phần cứng thì thay đổi gì

Gần như không gì cả. Thay vì `signals.py` sinh dữ liệu, đọc dữ liệu thật từ cảm biến vào một mảng số rồi đưa qua `features.py` — phần còn lại y hệt.

Đây là lý do kiến trúc được tách sẵn từ đầu: `features.py` không quan tâm dữ liệu đến từ đâu.
