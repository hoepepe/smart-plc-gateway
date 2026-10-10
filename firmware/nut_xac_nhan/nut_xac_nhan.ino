// nut_xac_nhan.ino — 2 nút OK/NG và đèn báo trên hộp gateway, để công nhân xác nhận cảnh báo AI
// mà không cần điện thoại hay đồ đo: kiểm chi tiết bằng cách quen thuộc ở chuyền rồi bấm một nút.
//
//   Nút NG (đỏ)  = "Đúng là lỗi"  — áp cho cảnh báo đang mở gần nhất (trong 15 phút).
//                  Không có cảnh báo nào mở → ghi "AI bỏ sót" cho chu kỳ vừa chạy.
//   Nút OK (xanh)= "Báo nhầm"     — áp cho cảnh báo đang mở gần nhất.
//   Đèn: xanh = bình thường · vàng = đang học / chờ duyệt / đang kiểm tra mẫu NG · đỏ nháy = có cảnh báo AI chưa xác nhận
//        đỏ sáng liền = mất kết nối PLC. Bấm nút → đèn nháy 2 lần nếu gateway đã ghi nhận, nháy nhanh 6 lần nếu lỗi.
//
// Giao tiếp qua cáp USB (Serial 115200) với tools/nut_bam_bridge.py trên laptop:
//   ESP32 → laptop:  "BTN,NG"  |  "BTN,OK"
//   laptop → ESP32:  "ANDON,<green|yellow|red|off>,<0|1 nháy>"   |   "ACK,<1|0>"
// Khi có switch và gửi MQTT thẳng qua W5500: thay Serial bằng publish gw/01/m/M01/button {"label":"fault"} và
// subscribe gw/01/m/M01/andon, gw/01/m/M01/button_ack — phần nút và đèn giữ nguyên.
//
// Gộp vào gateway_serial.ino: gọi nutSetup() trong setup() và nutLoop() trong loop(); dòng "BTN,..." không
// trùng định dạng dòng "S,..." nên laptop tách được.
//
// CHÂN (đổi nếu trùng với sơ đồ mạch thật — W5500 dùng 5/18/19/23/26, OLED và cảm biến I2C dùng 21/22):
//   Nút NG → GPIO32, nút OK → GPIO33 (nối xuống GND, dùng điện trở kéo lên trong ESP32)
//   LED đỏ → GPIO25, LED xanh → GPIO27 (qua điện trở 330 Ω). Vàng = bật cả hai (LED 2 màu) hoặc thêm LED vàng.
//   Còi (tuỳ chọn) → GPIO14
// Chưa nạp thử trên phần cứng thật.

const int PIN_NG = 32, PIN_OK = 33, PIN_RED = 25, PIN_GREEN = 27, PIN_BUZ = 14;
const unsigned long DEBOUNCE_MS = 30, LOCKOUT_MS = 800;   // chống dội phím, chống bấm đúp

String andonColor = "yellow";
bool andonBlink = false;
int ackFlashes = 0;               // số lần nháy xác nhận còn lại
unsigned long ackT = 0, ackPeriod = 150;
String rx;

struct Btn { int pin; const char* msg; bool last; unsigned long t; unsigned long fired; };
Btn btns[2] = { {PIN_NG, "BTN,NG", true, 0, 0}, {PIN_OK, "BTN,OK", true, 0, 0} };

void setLeds(bool red, bool green) {
  digitalWrite(PIN_RED, red ? HIGH : LOW);
  digitalWrite(PIN_GREEN, green ? HIGH : LOW);
}

void showAndon(unsigned long now) {
  if (ackFlashes > 0) {                         // đang nháy xác nhận sau khi bấm nút
    if (now - ackT >= ackPeriod) { ackT = now; ackFlashes--; }
    bool on = ackFlashes % 2;
    setLeds(on, on);
    return;
  }
  bool phase = !andonBlink || ((now / 400) % 2 == 0);
  if (andonColor == "green")       setLeds(false, phase);
  else if (andonColor == "yellow") setLeds(phase, phase);
  else if (andonColor == "red")    setLeds(phase, false);
  else                             setLeds(false, false);
}

void handleLine(const String& l) {
  if (l.startsWith("ANDON,")) {
    int c = l.indexOf(',', 6);
    andonColor = c > 0 ? l.substring(6, c) : l.substring(6);
    andonBlink = c > 0 && l.substring(c + 1).toInt() == 1;
  } else if (l.startsWith("ACK,")) {
    bool ok = l.substring(4).toInt() == 1;
    ackFlashes = ok ? 4 : 12;  ackPeriod = ok ? 150 : 60;  ackT = millis();
    if (!ok) { tone(PIN_BUZ, 2000, 300); }
  }
}

void nutSetup() {
  pinMode(PIN_NG, INPUT_PULLUP);
  pinMode(PIN_OK, INPUT_PULLUP);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BUZ, OUTPUT);
}

void nutLoop() {
  unsigned long now = millis();
  for (auto& b : btns) {
    bool v = digitalRead(b.pin);                  // LOW = đang bấm
    if (v != b.last) { b.last = v; b.t = now; }
    if (!v && now - b.t >= DEBOUNCE_MS && now - b.fired >= LOCKOUT_MS && b.t > b.fired) {
      b.fired = now;
      Serial.println(b.msg);
      tone(PIN_BUZ, 3000, 40);                    // tiếng bíp ngắn: đã bấm
    }
  }
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') { rx.trim(); if (rx.length()) handleLine(rx); rx = ""; }
    else if (rx.length() < 64) rx += ch;
  }
  showAndon(now);
}

void setup() {
  Serial.begin(115200);
  nutSetup();
}

void loop() {
  nutLoop();
}
