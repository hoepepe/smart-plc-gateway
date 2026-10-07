// qr_oled.ino — Hiện mã QR mở trang dữ liệu của đúng máy này trên dashboard,
// kèm trạng thái máy ngay trên màn hình OLED của gateway.
//
// Kỹ sư đứng ở tủ điện quét mã bằng điện thoại → mở thẳng trang chi tiết của máy.
// Ý tưởng khớp giai đoạn "Kết nối & Hiển thị hóa — One-touch QR code" trong lộ trình của DENSO.
//
// THƯ VIỆN (Arduino IDE → Library Manager):
//   - Adafruit SSD1306
//   - Adafruit GFX Library
//   - QRCode (tác giả Richard Moore)
//
// LƯU Ý: một số bản ESP32 core có sẵn file tên qrcode.h, có thể báo trùng tên khi biên dịch.
// Nếu gặp lỗi đó, đổi sang một thư viện tạo QR khác — phần vẽ bên dưới giữ nguyên,
// chỉ cần hàm cho biết ô (x, y) của mã QR là đen hay trắng.
//
// Chưa nạp thử trên phần cứng thật — kiểm tra lại khi lắp mạch.

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <qrcode.h>

// ───────── Cấu hình riêng cho từng gateway ─────────
const char* MACHINE_ID  = "M01";            // trùng với id trong src/data/machines.ts
const char* SERVER_IP   = "192.168.10.10";  // IP của laptop / máy chủ nội bộ
const int   SERVER_PORT = 3000;             // cổng dashboard khi chạy `npm run dev`

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
char url[64];

// Vẽ mã QR ở nửa trái màn hình.
// Phiên bản 3 = lưới 29×29 ô, chứa được đường link khoảng 50 ký tự.
// Mỗi ô phóng thành 2×2 điểm ảnh → 58×58, vừa chiều cao 64 của OLED.
void drawQR(const char* text) {
  QRCode qr;
  uint8_t buf[qrcode_getBufferSize(3)];
  qrcode_initText(&qr, buf, 3, ECC_LOW, text);

  const int s = 2, x0 = 3, y0 = 3;
  // Nền trắng làm viền: điện thoại cần khoảng trống sáng quanh mã mới nhận ra
  oled.fillRect(0, 0, qr.size * s + 6, 64, SSD1306_WHITE);
  for (uint8_t y = 0; y < qr.size; y++) {
    for (uint8_t x = 0; x < qr.size; x++) {
      if (qrcode_getModule(&qr, x, y)) {
        oled.fillRect(x0 + x * s, y0 + y * s, s, s, SSD1306_BLACK);
      }
    }
  }
}

// Nửa phải: mã máy và trạng thái. Font mặc định không có dấu tiếng Việt.
// Phần này rộng 60 điểm ảnh ≈ 10 ký tự mỗi dòng.
void drawStatus(const char* state) {
  const int x = 68;
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(x, 4);  oled.print(MACHINE_ID);
  oled.setCursor(x, 18); oled.print(state);
  oled.setCursor(x, 40); oled.print("Quet QR");
  oled.setCursor(x, 50); oled.print("de xem");
}

void setup() {
  Wire.begin(21, 22);   // SDA, SCL — chung bus với ADS1115
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  snprintf(url, sizeof(url), "http://%s:%d/?may=%s", SERVER_IP, SERVER_PORT, MACHINE_ID);
}

void loop() {
  // Tạm để cố định — khi ghép với driver đọc PLC, thay bằng trạng thái thật
  const char* state = "Dang chay";

  oled.clearDisplay();
  drawQR(url);
  drawStatus(state);
  oled.display();

  // Cập nhật thưa: OLED dùng chung bus I2C, cập nhật dày làm chậm việc đọc ADS1115
  delay(500);
}
