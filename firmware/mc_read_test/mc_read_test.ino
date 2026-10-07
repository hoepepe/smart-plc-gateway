// mc_read_test.ino — ESP32 + W5500 đọc PLC Mitsubishi dòng Q qua MC protocol (khung 3E nhị phân).
//
// SƠ ĐỒ THỬ, CHƯA CẦN SWITCH:
//   PLC ══ cáp mạng ══ W5500 ── ESP32 ── cáp USB ── Laptop (Serial Monitor, 115200)
//   Cáp USB vừa cấp nguồn vừa xem kết quả → KHÔNG nối LM2596 vào VIN lúc này.
//
// TRƯỚC KHI CHẠY, phía PLC phải (nhờ thầy làm trong GX Works2, sao lưu chương trình cũ trước):
//   1. Đặt IP cho cổng Ethernet tích hợp, ví dụ 192.168.10.21
//   2. Open Setting: thêm 1 kết nối TCP, kiểu "MC Protocol", chọn số cổng (ví dụ 5000)
//   3. Mã dữ liệu truyền: Binary
//   4. Ghi tham số xuống PLC, khởi động lại CPU
//
// CHỈ ĐỌC — code này không có lệnh ghi nào vào PLC.
//
// Khung lệnh đã được so từng byte với thư viện pymcprotocol (khớp hoàn toàn).
// Chưa chạy thử trên phần cứng thật.
//
// Thư viện: "Ethernet" (Arduino) — có sẵn trong Library Manager.

#include <SPI.h>
#include <Ethernet.h>

// ───────── Cấu hình ─────────
byte      MAC[]    = { 0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x50 };
IPAddress MY_IP(192, 168, 10, 50);     // IP của gateway
IPAddress PLC_IP(192, 168, 10, 21);    // IP của PLC — phải cùng dải 192.168.10.x
const uint16_t PLC_PORT = 5000;        // đúng số cổng đã đặt trong Open Setting

const int W5500_CS  = 5;
const int W5500_RST = 26;

// Mã loại thanh ghi trong MC protocol
const uint8_t DEV_D = 0xA8;   // thanh ghi dữ liệu D
const uint8_t DEV_M = 0x90;   // bit nội M

EthernetClient plc;

// Dựng khung 3E nhị phân "đọc liên tiếp theo word" (lệnh 0x0401, lệnh phụ 0x0000).
// Trả về số byte của khung (luôn là 21).
size_t buildReadFrame(uint8_t* f, uint32_t devNo, uint8_t devCode, uint16_t points) {
  size_t i = 0;
  f[i++] = 0x50; f[i++] = 0x00;          // subheader yêu cầu
  f[i++] = 0x00;                          // network số 0
  f[i++] = 0xFF;                          // PC số FF (chính CPU này)
  f[i++] = 0xFF; f[i++] = 0x03;          // module đích 0x03FF
  f[i++] = 0x00;                          // trạm số 0
  f[i++] = 0x0C; f[i++] = 0x00;          // độ dài phần còn lại = 12 byte
  f[i++] = 0x04; f[i++] = 0x00;          // thời gian chờ: 4 × 250ms = 1 giây
  f[i++] = 0x01; f[i++] = 0x04;          // lệnh 0x0401: đọc liên tiếp
  f[i++] = 0x00; f[i++] = 0x00;          // lệnh phụ 0x0000: theo word
  f[i++] = devNo & 0xFF;                  // số thanh ghi bắt đầu, 3 byte
  f[i++] = (devNo >> 8) & 0xFF;
  f[i++] = (devNo >> 16) & 0xFF;
  f[i++] = devCode;                       // loại thanh ghi
  f[i++] = points & 0xFF;                 // số word cần đọc
  f[i++] = (points >> 8) & 0xFF;
  return i;
}

// Đọc `points` word bắt đầu từ thanh ghi devNo. Trả về true nếu thành công.
bool mcReadWords(uint32_t devNo, uint8_t devCode, uint16_t points, uint16_t* out) {
  if (!plc.connected()) {
    if (!plc.connect(PLC_IP, PLC_PORT)) {
      Serial.println("  ! Khong ket noi duoc PLC");
      return false;
    }
  }

  uint8_t req[21];
  size_t n = buildReadFrame(req, devNo, devCode, points);
  plc.write(req, n);

  // Phản hồi: 9 byte đầu + 2 byte mã kết thúc + 2 byte mỗi word
  const size_t expected = 11 + 2 * points;
  uint8_t resp[11 + 2 * 64];
  if (expected > sizeof(resp)) return false;

  size_t got = 0;
  unsigned long t0 = millis();
  while (got < expected && millis() - t0 < 1500) {
    while (plc.available() && got < expected) resp[got++] = plc.read();
  }
  if (got < expected) {
    Serial.printf("  ! PLC tra loi thieu: %u/%u byte\n", got, expected);
    plc.stop();
    return false;
  }

  uint16_t endCode = resp[9] | (resp[10] << 8);
  if (endCode != 0) {
    // Mã lỗi khác 0 — tra trong manual MC protocol của Mitsubishi
    Serial.printf("  ! PLC bao loi, end code = 0x%04X\n", endCode);
    return false;
  }

  for (uint16_t k = 0; k < points; k++) {
    out[k] = resp[11 + 2 * k] | (resp[12 + 2 * k] << 8);
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Thu doc PLC Mitsubishi qua MC protocol ===");

  pinMode(W5500_RST, OUTPUT);
  digitalWrite(W5500_RST, LOW);  delay(50);
  digitalWrite(W5500_RST, HIGH); delay(200);

  Ethernet.init(W5500_CS);
  Ethernet.begin(MAC, MY_IP);
  delay(1000);

  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("! Khong thay W5500 — kiem tra day SPI va chan CS");
  }
  if (Ethernet.linkStatus() == LinkOFF) {
    Serial.println("! Chua co ket noi mang — kiem tra cap mang, den tren W5500 va PLC");
  }
  Serial.print("IP gateway: ");
  Serial.println(Ethernet.localIP());
}

void loop() {
  uint16_t d[4];
  uint16_t m;

  if (mcReadWords(100, DEV_D, 4, d)) {
    Serial.printf("D100..D103 = %u  %u  %u  %u\n", d[0], d[1], d[2], d[3]);
  }
  if (mcReadWords(0, DEV_M, 1, &m)) {
    // Đọc M0–M15 trong một word: bit 0 là M0, bit 1 là M1...
    Serial.print("M0..M5     = ");
    for (int b = 0; b < 6; b++) Serial.print((m >> b) & 1);
    Serial.println();
  }

  delay(1000);
}
