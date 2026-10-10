# Độ tin cậy của AI gateway

Tạo bằng `python ml/danh_gia_do_tin_cay.py`. Bộ phát hiện là đúng bản chạy trong gateway (`edge/detector.py`).

**Cách đo** (để con số không tự lừa mình):
- Lúc học **không biết nhãn**: dữ liệu học có lẫn chu kỳ lỗi, giống thực tế.
- Kiểm tra trên **ca / khoảng thời gian chưa từng thấy** khi học.
- Ngưỡng chọn chỉ từ dữ liệu học, không chỉnh theo kết quả kiểm tra.
- So với 2 cách khác trên **cùng dữ liệu**: giới hạn PLC (đỉnh + thời gian nằm trong khoảng cho phép — cách OK/NG phổ biến hiện nay) và Isolation Forest.
- Trong ngoặc là **khoảng tin cậy 95%**.

## 1. Bốn loại máy kiểu DENSO (dữ liệu mô phỏng)

Học 300 chu kỳ qua 5 ca (lẫn ~2% chu kỳ lỗi không ai biết). Kiểm tra 400 chu kỳ bình thường và 100 chu kỳ mỗi loại lỗi, lấy từ 10 ca khác. Lặp 3 lần với hạt giống khác nhau rồi cộng dồn.

### Máy ép

| Cách phát hiện | Báo nhầm | Thiếu chi tiết | Chi tiết lệch vị trí | Ép hai lần | Bắt lỗi chung |
|---|---|---|---|---|---|
| Giới hạn PLC (đỉnh + thời gian) | 1.8% (1–3) | 74.7% (69–79) | 47.0% (41–53) | 0.0% (0–1) | 40.6% (37–44) |
| Isolation Forest | 0.0% (0–0) | 2.7% (1–5) | 15.3% (12–20) | 7.7% (5–11) | 8.6% (7–11) |
| **AI của gateway** | 0.5% (0–1) | 100.0% (99–100) | 100.0% (99–100) | 100.0% (99–100) | 100.0% (100–100) |

### Máy siết bu-lông

| Cách phát hiện | Báo nhầm | Trờn ren | Ren chéo | Không tới lực mục tiêu | Bắt lỗi chung |
|---|---|---|---|---|---|
| Giới hạn PLC (đỉnh + thời gian) | 14.7% (13–17) | 36.7% (31–42) | 8.0% (5–12) | 44.7% (39–50) | 29.8% (27–33) |
| Isolation Forest | 0.0% (0–0) | 53.7% (48–59) | 3.7% (2–6) | 15.0% (11–19) | 24.1% (21–27) |
| **AI của gateway** | 1.2% (1–2) | 100.0% (99–100) | 100.0% (99–100) | 100.0% (99–100) | 100.0% (100–100) |

### Máy CNC

| Cách phát hiện | Báo nhầm | Mòn dao | Gãy dao | Rung | Bắt lỗi chung |
|---|---|---|---|---|---|
| Giới hạn PLC (đỉnh + thời gian) | 0.2% (0–1) | 80.7% (76–85) | 28.7% (24–34) | 36.0% (31–42) | 48.4% (45–52) |
| Isolation Forest | 0.0% (0–0) | 35.3% (30–41) | 17.0% (13–22) | 2.0% (1–4) | 18.1% (16–21) |
| **AI của gateway** | 2.2% (2–3) | 99.3% (98–100) | 99.7% (98–100) | 99.7% (98–100) | 99.6% (99–100) |

### Khí nén

| Cách phát hiện | Báo nhầm | Rò khí | Nguồn khí yếu | Van kẹt | Bắt lỗi chung |
|---|---|---|---|---|---|
| Giới hạn PLC (đỉnh + thời gian) | 13.6% (12–16) | 16.7% (13–21) | 72.0% (67–77) | 16.7% (13–21) | 35.1% (32–38) |
| Isolation Forest | 0.0% (0–0) | 16.3% (13–21) | 78.0% (73–82) | 6.3% (4–10) | 33.6% (31–37) |
| **AI của gateway** | 0.2% (0–1) | 82.7% (78–87) | 96.3% (94–98) | 63.3% (58–69) | 80.8% (78–83) |

## 2. Dữ liệu thật: máy phay CNC trong nhà máy Bosch

Bộ dữ liệu công khai CNC Machining của Bosch (CC BY 4.0): rung động 3 máy phay, 2018–2021, lỗi do kỹ sư gắn nhãn. Tín hiệu đưa qua đúng đường gateway (RMS 100 Hz). Mỗi (máy, nguyên công) một mô hình, học nửa đầu theo thời gian (không biết nhãn), kiểm tra nửa sau.

| Cách chạy | Cách phát hiện | AUC | Báo nhầm | Bắt lỗi |
|---|---|---|---|---|
| Học một lần rồi để nguyên | Giới hạn PLC (đỉnh + thời gian) | 0.44 (0.30–0.59) | 20.0% (17–24) | 11.1% (2–44) |
| Học một lần rồi để nguyên | Isolation Forest | 0.83 (0.70–0.92) | 4.9% (3–7) | 11.1% (2–44) |
| Học một lần rồi để nguyên | **AI của gateway** | 0.74 (0.48–0.93) | 43.9% (40–48) | 77.8% (45–94) |
| Học lại theo phản hồi của kỹ sư | Giới hạn PLC (đỉnh + thời gian) | 0.54 (0.35–0.71) | 11.7% (9–15) | 22.2% (6–55) |
| Học lại theo phản hồi của kỹ sư | Isolation Forest | 0.87 (0.79–0.93) | 5.7% (4–8) | 33.3% (12–65) |
| Học lại theo phản hồi của kỹ sư | **AI của gateway** | 0.90 (0.83–0.96) | 18.6% (15–22) | 77.8% (45–94) |

Kiểm tra trên 494 lần chạy tốt và 9 lần chạy lỗi (chỉ 9 lỗi rơi vào nửa sau, nên khoảng tin cậy của tỉ lệ bắt lỗi rất rộng).

## 3. Chuỗi thật: PLC Mitsubishi Q06UDEHCPU → gateway

Phát lại chu kỳ siết bu-lông thật (PyScrew) vào thanh ghi PLC thật, gateway đọc lại qua MC protocol rồi chấm điểm:
20 chu kỳ, đọc ổn định 99,8 mẫu/giây, **kết luận bình thường/bất thường trùng 100%** với chấm trực tiếp trên dữ liệu gốc, điểm lệch trung vị 6,5%. Điều này chứng minh đường truyền PLC → gateway không làm sai kết luận của AI (không phải chứng minh độ chính xác phát hiện lỗi).

## 4. Dữ liệu thật: siết bu-lông PyScrew (TU Dortmund)

Đã chạy trên máy Tuấn (kịch bản s02, s04); đưa `ml/reports/pyscrew_*.md` vào repo để báo cáo này tự dẫn tới.

## Đọc kết quả

- Máy ép: AI bắt 100% lỗi với 0.5% báo nhầm; giới hạn PLC bắt 41% với 1.8% báo nhầm.
- Máy siết bu-lông: AI bắt 100% lỗi với 1.2% báo nhầm; giới hạn PLC bắt 30% với 14.7% báo nhầm.
- Máy CNC: AI bắt 100% lỗi với 2.2% báo nhầm; giới hạn PLC bắt 48% với 0.2% báo nhầm.
- Khí nén: AI bắt 81% lỗi với 0.2% báo nhầm; giới hạn PLC bắt 35% với 13.6% báo nhầm.
- Isolation Forest dùng tham số mặc định, ngưỡng phân vị 99,5 của dữ liệu học (cùng mục tiêu báo nhầm với AI gateway).
- Dữ liệu thật Bosch: khi có kỹ sư phản hồi, AI gateway có AUC cao nhất (0,90) và bắt 7/9 lỗi, nhưng báo nhầm ~19% — cao hơn Isolation Forest (~6%), dù Isolation Forest chỉ bắt 3/9. Chỉ có 9 lỗi nên chưa kết luận chắc được; báo nhầm 19% là chưa đủ để chạy không cần người duyệt.
- Dữ liệu mô phỏng do nhóm tạo, nên con số cao là cận trên. Dữ liệu thật (Bosch) khó hơn nhiều: máy trôi theo nhiều năm.
- Vì vậy thiết kế giữ con người trong vòng lặp: kỹ sư duyệt mọi chuẩn mới, bấm Báo nhầm / Bình thường mới để AI học lại.

