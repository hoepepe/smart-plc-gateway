# Bản cũ — nhận diện loại tín hiệu

Thư mục này giữ lại hướng tiếp cận ban đầu: AI đoán một dây tín hiệu đang đo đại lượng gì
(nhiệt độ, rung động, bộ đếm, tải động cơ).

**Vì sao không còn là hướng chính:** ngày 21/09/2026 mentor DENSO xác nhận DENSO đã có
danh sách tín hiệu và muốn lấy dữ liệu trực tiếp từ PLC. Bài toán đoán dây không còn
là painpoint.

Vẫn giữ lại vì hai kết quả còn giá trị cho đường tín hiệu analog phụ (DENSO xác nhận vẫn
dùng cả 0–10V và 4–20mA):
- Hai lớp bảo vệ: đấu ngược cực — mô hình bắt 0%, luật kiểm tra dải bắt 100%
- Ngưỡng tin cậy một mình không phát hiện được tín hiệu lạ (8.3%), cần mô hình one-class (100%)

Hướng hiện tại nằm ở `../cycles.py`.
