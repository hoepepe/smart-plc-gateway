# Bộ phát hiện của gateway trên dữ liệu thật Bosch CNC

Dữ liệu rung máy phay trong nhà máy Bosch (công khai, CC BY 4.0), KHÔNG phải dữ liệu DENSO.
Bộ phát hiện: `edge/detector.py` — đúng bản đang chạy trong gateway (lọc bền vững, ngưỡng p99,5 chọn bằng kiểm định chéo theo khối thời gian, Mahalanobis + MAD).

Mỗi (máy, nguyên công) một mô hình, chu kỳ theo thứ tự thời gian. Chỉ dùng nhóm có ≥ 20 lần chạy để học (bộ phát hiện không học với ít hơn 20). Điểm > 1,0 là cảnh báo.

| Cách chạy | Số mô hình | Test good / lỗi | AUC | Báo nhầm | Bắt lỗi |
|---|---|---|---|---|---|
| A. Qua gateway (RMS 100 Hz) · Cách cũ: học trên good đã biết nhãn | 20 | 474 / 9 | 0.722 | 45.6% | 77.8% |
| A. Qua gateway (RMS 100 Hz) · Như thật: học 50% đầu, không biết nhãn | 21 | 494 / 9 | 0.742 | 43.9% | 77.8% |
| A. Qua gateway (RMS 100 Hz) · Như thật + học lại mỗi 10 lần chạy | 21 | 494 / 9 | 0.741 | 44.5% | 77.8% |
| A. Qua gateway (RMS 100 Hz) · Như thật + học lại + kỹ sư bấm Báo nhầm | 21 | 494 / 9 | 0.733 | 39.7% | 77.8% |
| B. Đầy đủ (rung 2 kHz) · Cách cũ: học trên good đã biết nhãn | 20 | 474 / 9 | 0.568 | 62.7% | 77.8% |
| B. Đầy đủ (rung 2 kHz) · Như thật: học 50% đầu, không biết nhãn | 21 | 494 / 9 | 0.592 | 60.9% | 66.7% |
| B. Đầy đủ (rung 2 kHz) · Như thật + học lại mỗi 10 lần chạy | 21 | 494 / 9 | 0.592 | 60.9% | 66.7% |
| B. Đầy đủ (rung 2 kHz) · Như thật + học lại + kỹ sư bấm Báo nhầm | 21 | 494 / 9 | 0.587 | 50.8% | 55.6% |

Ở cách "như thật" (bộ A), 27 lần chạy lỗi lẫn vào dữ liệu học mà không ai biết; bộ lọc bền vững tự bỏ 77 lần chạy, trong đó 27 là lỗi thật.

## Theo máy (bộ A, như thật)

| Máy | Lần chạy good test | Báo nhầm thật | Báo nhầm ước tính lúc học (trung bình) | Lỗi test | Bắt được |
|---|---|---|---|---|---|
| M01 | 87 | 12.6% | 6.6% | 2 | 100% |
| M02 | 247 | 74.1% | 7.7% | 1 | 100% |
| M03 | 160 | 14.4% | 8.2% | 6 | 67% |

Đọc kết quả (nói thật):
- **Bộ phát hiện hiện tại CHƯA đáng tin trên dữ liệu này.** Báo nhầm khoảng 40%, chủ yếu do máy M02 — máy này trôi mạnh theo thời gian (báo cáo cũ cũng thấy M02 báo nhầm 33,6%).
- Mỗi nguyên công chỉ có 20–28 lần chạy để học, rải trong nhiều năm. Gateway được thiết kế học 300 chu kỳ liên tiếp trong một ca rồi học lại định kỳ — dữ liệu Bosch không cho kiểm chứng đúng điều kiện đó.
- "Báo nhầm ước tính" lúc học (5–11%) đã cao hơn mục tiêu 0,5–1%, tức dashboard sẽ báo cho kỹ sư là chuẩn chưa ổn. Nhưng nó vẫn thấp hơn báo nhầm thật khi máy trôi nhiều năm — con số ước tính không thay được thời gian chạy thử.
- Học lại định kỳ chỉ trên chu kỳ không bị cảnh báo gần như không giúp: khi máy trôi, hầu hết chu kỳ đều bị cảnh báo nên không có gì để học. Phải có kỹ sư bấm "Báo nhầm" / "Bình thường mới" thì mới đỡ (≈ 40% thay vì 44%).
- Chỉ có 9 lần chạy lỗi rơi vào nửa sau, quá ít để nói chắc về tỉ lệ bắt lỗi.
- Số mô hình và cách chọn ngưỡng khác báo cáo cũ (bosch_cnc.md), nên hai báo cáo không so trực tiếp được.
