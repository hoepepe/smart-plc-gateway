# Kết quả kiểm chứng trên Bosch CNC Machining

Dữ liệu rung máy phay trong nhà máy Bosch (công khai, CC BY 4.0), KHÔNG phải dữ liệu DENSO.

- 1702 lần chạy nguyên công, 70 lần lỗi thật (gán nhãn thủ công).
- Mỗi (máy, nguyên công) một mô hình, train trên 60% lần chạy good sớm nhất; kiểm tra trên phần good muộn hơn + toàn bộ bad.
- Ngưỡng chung: phân vị 99 của điểm leave-one-out trên tập train (đã chuẩn hoá theo từng nguyên công).

## Kết quả chính (mỗi máy × nguyên công một mô hình)

Hai cách chấm điểm: **Mahalanobis** (đám mây nhiều chiều) và **MAD** (lệch xa nhất theo từng đặc trưng, ít tham số hơn — hợp khi chỉ có vài chục chu kỳ bình thường). Ba ngưỡng, đều lấy từ tập train (phân vị 99 / 95 / 90 của điểm leave-one-out) — không nhìn tập kiểm tra.

| Bộ đặc trưng | Chấm điểm | AUC | Ngưỡng p99: báo nhầm / bắt lỗi | p95 | p90 |
|---|---|---|---|---|---|
| A. Qua gateway (RMS 100 Hz) | Mahalanobis | 0.715 | 2.6% / 0.0% | 9.9% / 25.7% | 17.7% / 42.9% |
| A. Qua gateway (RMS 100 Hz) | MAD | 0.873 | 3.0% / 7.1% | 13.5% / 80.0% | 22.9% / 87.1% |
| B. Đầy đủ (rung 2 kHz) | Mahalanobis | 0.772 | 17.7% / 51.4% | 37.0% / 81.4% | 52.8% / 88.6% |
| B. Đầy đủ (rung 2 kHz) | MAD | 0.783 | 3.3% / 8.6% | 16.5% / 48.6% | 30.1% / 71.4% |

Kiểm tra: 665 lần chạy good muộn hơn, 70 lần chạy lỗi, 43 mô hình.

## Theo máy (bộ B, Mahalanobis, ngưỡng p99)

| Máy | Báo nhầm | Bắt được lỗi |
|---|---|---|
| M01 | 6.0% (200) | 61.8% (34) |
| M02 | 33.6% (253) | 55.6% (27) |
| M03 | 9.9% (212) | 0.0% (9) |

## Vì sao không gộp: thí nghiệm phụ

- **Gộp 15 nguyên công vào 1 mô hình mỗi máy** (bộ B): báo nhầm 2.9%, bắt lỗi 14.3%, AUC 0.826.
- **Dùng mô hình của máy này cho máy khác cùng nguyên công**: trung bình 44.3% lần chạy good bị báo nhầm (84 cặp máy × nguyên công).

Đọc kết quả:
- Chuyển mô hình sang máy khác là sai rõ ràng (báo nhầm rất cao) → mỗi máy phải học chuẩn của chính nó.
- Gộp các nguyên công của CÙNG một máy cho AUC không thấp hơn, nhưng ở ngưỡng p99 bắt được ít lỗi hơn hẳn; chưa đủ bằng chứng để nói gộp nguyên công luôn kém — ghi đúng như vậy.
- Mỗi nguyên công chỉ có 8–32 chu kỳ để train và dữ liệu kéo dài 3 năm (trôi theo thời gian), nên báo nhầm trên lần chạy muộn hơn còn cao. Khi triển khai cần thời gian học đủ dài và học lại định kỳ.
