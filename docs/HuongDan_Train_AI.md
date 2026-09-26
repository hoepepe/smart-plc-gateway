# Hướng dẫn phần AI — cho Duy

*Cập nhật sau trả lời của mentor DENSO ngày 21/09/2026.*

## Việc đã đổi

Bài toán cũ — AI đoán một dây đang đo đại lượng gì — **không còn là trọng tâm**, vì DENSO đã có danh sách tín hiệu. Code cũ giữ ở `ml/legacy_nhan_dien_tin_hieu/`.

Bài toán mới: **phát hiện chu kỳ gia công bất thường** trên lực ép, lực xiết, áp lực khí nén. Chu kỳ lạ thường đi kèm chi tiết lỗi.

Trạng thái máy và OEE **không cần AI** — chỉ là đọc thanh ghi rồi cộng thời gian.

## Chạy ngay, không cần GPU, không cần dữ liệu thật

```bash
cd ml
pip install numpy scikit-learn
python cycles.py
```

Khoảng vài giây. Dữ liệu mô phỏng là **đúng quy định**: dữ liệu thật của DENSO chỉ cấp khi vào Top 10.

## Mô hình đang dùng

Khoảng cách **Mahalanobis** trên 9 đặc trưng mỗi chu kỳ (giá trị đỉnh, đáy, thời điểm đạt đỉnh, mức trung bình, độ dốc tăng, độ gồ ghề, số đỉnh, mức đầu, mức giữa chu kỳ). Isolation Forest được chạy song song để so sánh.

## Ba nguyên tắc — đừng phá

1. **Tách theo ca, không tách ngẫu nhiên.** Các chu kỳ trong cùng một ca rất giống nhau, tách ngẫu nhiên thì con số đẹp giả tạo.
2. **Chỉ học trên chu kỳ bình thường.** Nhà máy có rất ít dữ liệu lỗi — phương pháp phải sống được với điều đó.
3. **Chọn ngưỡng trên ca hiệu chuẩn, không bao giờ nhìn tập kiểm tra.**

## Việc cần làm, theo thứ tự

1. **Sửa hai chỗ yếu.** Van kẹt bắt 33%, nguồn khí yếu 78%. Giả thuyết: van kẹt cần đặc trưng bắt biến thiên nhanh; nguồn khí yếu nên thêm luật ngưỡng áp nền tuyệt đối. Thử từng giả thuyết, đo lại, ghi cả kết quả xấu.
2. **Làm dữ liệu khó hơn.** Thêm biến động giữa các ca, nhiễu điện, chu kỳ bị cắt ngang. Con số 99–100% hiện tại là do dữ liệu dễ.
3. **Thêm chiều cao và tải trọng** — DENSO có nêu nhưng chưa mô phỏng.
4. **Khi có PLC hoặc CSV thật**, thay phần sinh chu kỳ trong `cycles.py` bằng đọc CSV. Phần huấn luyện và đánh giá giữ nguyên.
5. **Việc ngoài AI hợp với Duy nhất:** viết driver đọc Mitsubishi MC protocol bằng Python (thư viện `pymcprotocol`). Đây là mắt xích quyết định dự án có đọc được PLC thật hay không.

Sau mỗi lần sửa: chạy `cycles.py`, copy `cycles.json` sang `src/data/`, mọi con số trên giao diện tự cập nhật.
