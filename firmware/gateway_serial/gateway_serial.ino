// gateway_serial.ino — ESP32 + W5500 đọc PLC Mitsubishi rồi gửi số liệu lên laptop qua cáp USB.
// Dùng khi CHƯA có switch:
//
//   PLC ══ cáp mạng ══ W5500 ── ESP32 ── cáp USB ── Laptop chạy tools/plc_to_mqtt.py --serial COMx
//
// Mỗi lần đọc in một dòng:   S,<millis>,<D100>,<D102>,<D110>,<M0..M15>
// Script trên laptop cắt chu kỳ theo cờ M3, nội suy, tính đặc trưng và đẩy lên MQTT cho dashboard.
//
// Khi có switch: thay phần in ra Serial bằng gửi MQTT qua W5500 — phần đọc PLC giữ nguyên.
//
// Đọc nhanh nhất có thể, mục tiêu 100 lần/giây. Đạt được bao nhiêu phụ thuộc thời gian quét
// của PLC — không sao, laptop nội suy theo dấu thời gian thật.
// CHỈ ĐỌC — không có lệnh ghi nào vào PLC.
// Khung lệnh đã so từng byte với thư viện pymcprotocol. Chưa chạy thử trên phần cứng thật.

#include <SPI.h>
#include <Ethernet.h>

byte      MAC[]    = { 0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x50 };
IPAddress MY_IP(192, 168, 10, 50);
IPAddress PLC_IP(192, 168, 10, 21);
const uint16_t PLC_PORT = 5000;
const int W5500_CS = 5, W5500_RST = 26;
const uint8_t DEV_D = 0xA8, DEV_M = 0x90;
const unsigned long PERIOD_MS = 10;          // mục tiêu 100 lần/giây

EthernetClient plc;

size_t buildReadFrame(uint8_t* f, uint32_t devNo, uint8_t devCode, uint16_t points) {
  size_t i = 0;
  f[i++] = 0x50; f[i++] = 0x00;
  f[i++] = 0x00; f[i++] = 0xFF;
  f[i++] = 0xFF; f[i++] = 0x03; f[i++] = 0x00;
  f[i++] = 0x0C; f[i++] = 0x00;
  f[i++] = 0x04; f[i++] = 0x00;
  f[i++] = 0x01; f[i++] = 0x04;
  f[i++] = 0x00; f[i++] = 0x00;
  f[i++] = devNo & 0xFF; f[i++] = (devNo >> 8) & 0xFF; f[i++] = (devNo >> 16) & 0xFF;
  f[i++] = devCode;
  f[i++] = points & 0xFF; f[i++] = (points >> 8) & 0xFF;
  return i;
}

bool mcReadWords(uint32_t devNo, uint8_t devCode, uint16_t points, uint16_t* out) {
  if (!plc.connected() && !plc.connect(PLC_IP, PLC_PORT)) return false;
  uint8_t req[21];
  plc.write(req, buildReadFrame(req, devNo, devCode, points));

  const size_t expected = 11 + 2 * points;
  uint8_t resp[11 + 2 * 16];
  if (expected > sizeof(resp)) return false;
  size_t got = 0;
  unsigned long t0 = millis();
  while (got < expected && millis() - t0 < 500) {
    while (plc.available() && got < expected) resp[got++] = plc.read();
  }
  if (got < expected) { plc.stop(); return false; }
  if ((resp[9] | (resp[10] << 8)) != 0) return false;      // PLC báo lỗi
  for (uint16_t k = 0; k < points; k++) out[k] = resp[11 + 2 * k] | (resp[12 + 2 * k] << 8);
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(W5500_RST, OUTPUT);
  digitalWrite(W5500_RST, LOW); delay(50); digitalWrite(W5500_RST, HIGH); delay(200);
  Ethernet.init(W5500_CS);
  Ethernet.begin(MAC, MY_IP);
  delay(1000);
  if (Ethernet.hardwareStatus() == EthernetNoHardware) Serial.println("! Khong thay W5500");
  if (Ethernet.linkStatus() == LinkOFF) Serial.println("! Chua co ket noi mang toi PLC");
}

void loop() {
  static unsigned long next = millis();
  uint16_t d[11], m;
  // D100..D110 trong một lệnh, M0..M15 trong một lệnh
  if (mcReadWords(100, DEV_D, 11, d) && mcReadWords(0, DEV_M, 1, &m)) {
    Serial.printf("S,%lu,%u,%u,%u,%u\n", millis(), d[0], d[2], d[10], m);
  } else {
    Serial.println("! Doc PLC that bai — kiem tra IP, cong, Open Setting");
    delay(500);
  }
  next += PERIOD_MS;
  long wait = (long)(next - millis());
  if (wait > 0) delay(wait); else next = millis();
}
