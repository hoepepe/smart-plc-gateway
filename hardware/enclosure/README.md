# Vỏ hộp Smart PLC Gateway (in 3D)

| File | Dùng để |
|---|---|
| `out/gateway_base.stl` | Đế hộp — in thẳng, miệng hộp hướng lên, không cần support |
| `out/gateway_lid_print.stl` | Nắp — đã lật sẵn để mặt ngoài nằm trên bàn in |
| `out/gateway_lid.stl` | Nắp ở tư thế lắp (để xem/ghép trong CAD) |
| `out/viewer.html` | Trình xem 3D xoay được (mở bằng trình duyệt, cần mạng để tải Three.js) |
| `gen_enclosure.py` | Mã tạo hình — mọi kích thước nằm ở các bảng đầu file |

Kích thước ngoài 165 × 110 × 60,5 mm (+ 2 tai bắt vít 12 mm hai đầu). Vừa bàn in 220 × 220.

**Trước khi in:** đo module thật bằng thước kẹp, sửa bảng `MODULES`, `CUTS`, `OLED`, rồi chạy
`python gen_enclosure.py && python build_viewer.py`.

Vật tư kèm theo: 4 vít M3×10 tự ren (nắp), 4 vít M2×6 (OLED), 3 ốc siết cáp PG7, jack DC cái bắt panel ren M8,
2 LED 5 mm, (tuỳ chọn) kẹp DIN rail 35 mm bắt 2 vít M3 dưới đáy.

In: PETG (chịu nhiệt tốt hơn PLA trong tủ điện), lớp 0,2 mm, 3 vách, infill 20%.

**Chỗ cho dây dupont (bản demo):** module có header hàn sẵn hướng xuống (ESP32, W5500, RS232, PC817, HW-685)
được kê cao 28 mm để đầu dupont cái (14 mm) và chỗ uốn dây nằm gọn bên dưới. ADS1115 và MPU6050 thường bán
kèm header rời: hàn header **hướng lên**, module kê thấp 6 mm, dây đi phía trên. Đổi trong bảng `MODULES` (DOWN/UP).
