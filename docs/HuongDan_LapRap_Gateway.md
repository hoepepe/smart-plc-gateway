# Hướng dẫn lắp ráp Smart PLC Gateway

*Từ linh kiện rời đến thiết bị hoàn chỉnh trong vỏ ray DIN — DENSO Factory Hacks 2026, đề D1*

---

## Đọc trước khi bắt đầu

**Nguyên tắc số một: lắp từng khối, thử từng khối.** Không hàn tất cả rồi mới cắm điện. Mỗi bước dưới đây kết thúc bằng một phép thử — chỉ sang bước sau khi phép thử đạt. Lắp một lèo rồi hỏng thì không biết hỏng ở đâu.

**Ba điều có thể làm cháy linh kiện ngay lập tức:**

1. Nối ESP32 vào LM2596 **trước khi** chỉnh đầu ra về 5V. LM2596 xuất xưởng có thể ra gần bằng điện áp vào — 24V vào chân VIN là ESP32 chết ngay.
2. Đưa điện áp trên 3,3V vào bất kỳ chân GPIO nào của ESP32. Chân GPIO không chịu 5V.
3. Đấu ngược cực nguồn 24V. Luôn đo bằng đồng hồ trước khi cắm.

**Luôn rút nguồn khi đấu dây.** Chỉ cắm lại khi đã kiểm tra xong.

---

## Phần 1 — Linh kiện

### Linh kiện chính (tổng khoảng 770.000đ)

| # | Linh kiện | Số lượng | Vai trò | Giá |
|---|---|---|---|---|
| 1 | ESP32 DevKit V1 (38 chân) | 1 | Bộ xử lý | 100.000 |
| 2 | Module Ethernet W5500 | 1 | Nối cổng Ethernet của PLC | 90.000 |
| 3 | Module MAX485 | 1 | Cổng RS485 (Keyence KV-8000) | 30.000 |
| 4 | Module MAX3232 | 1 | Cổng RS-232C (Omron CPM2C) | 25.000 |
| 5 | Module ADS1115 | 1 | Đọc tín hiệu analog | 70.000 |
| 6 | Module hạ áp 0–10V → 0–3,3V | 1 | Chuẩn hóa tín hiệu 0–10V | 50.000 |
| 7 | Điện trở **150Ω, sai số 0,1%** | 2 | Đọc tín hiệu 4–20mA | 10.000 |
| 8 | Module PC817 cách ly 4 kênh | 1 | Đọc cờ trạng thái 24V | 40.000 |
| 9 | Adapter 24V DC, 2A | 1 | Nguồn riêng, không lấy từ máy | 120.000 |
| 10 | Module LM2596 (hạ áp chỉnh được) | 1 | 24V → 5V | 30.000 |
| 11 | OLED 0,96" SSD1306 I2C | 1 | Hiện trạng thái tại chỗ | 45.000 |
| 12 | Vỏ ray DIN, domino, PCB lỗ, dây, jack DC | 1 bộ | Đóng gói | 160.000 |

### Linh kiện phụ (thường có sẵn hoặc vài nghìn đồng)

- Điện trở 10kΩ và 20kΩ — cầu chia áp cho chân RO của MAX485
- Header cái 2,54mm — cắm module lên PCB, tháo ra được khi hỏng
- Dây cáp mạng RJ45 ngắn
- Ống co nhiệt, băng keo cách điện

### Linh kiện chỉ dùng khi demo trên bàn

Biến trở 10kΩ, nút nhấn, MPU6050 — tạo tín hiệu giả khi chưa có máy thật. Không nằm trong thiết bị cuối.

### Dụng cụ

- Mỏ hàn (khuyên dùng loại chỉnh nhiệt), thiếc hàn có nhựa thông
- **Đồng hồ vạn năng** — bắt buộc, dùng ở gần như mọi bước
- Kìm tuốt dây, kìm cắt, tua vít nhỏ đầu dẹt và đầu bake
- Breadboard và dây cắm (để thử trước khi hàn)
- Cáp USB micro-B có truyền dữ liệu (không phải cáp chỉ sạc)

---

## ⚠️ Ba chỗ BOM cũ bị sai — đã sửa trong bảng trên

Nếu Đạt đã mua theo danh sách cũ, cần điều chỉnh:

**1. Điện trở 4–20mA phải là 150Ω, không phải 250Ω.**
Dòng 20mA qua 250Ω tạo ra 5V, trong khi ADS1115 cấp 3,3V chỉ chịu tối đa khoảng 3,6V ở đầu vào. Với 150Ω: 4mA → 0,6V, 20mA → 3,0V, nằm gọn trong dải. *Đây là lỗi trong lời khuyên trước đó của mình.*

**2. MAX485 cần cầu chia áp ở chân RO.**
MAX485 chạy ở 5V nên chân RO xuất ra khoảng 5V — đưa thẳng vào ESP32 sẽ hỏng chân. Thêm cầu chia 10kΩ/20kΩ hạ về 3,3V. Nếu mua mới, chọn **MAX3485** (bản 3,3V) thì không cần cầu chia.

**3. Omron CPM2C cần MAX3232, không phải MAX485.**
CPM2C dùng cổng RS-232C. RS-232 dùng mức điện áp khoảng ±12V, hoàn toàn khác RS-485. MAX485 không nói chuyện được với RS-232. Cần mua thêm module MAX3232 (khoảng 25.000đ). *Cũng là lỗi trong lời khuyên trước đó.*

---

## Phần 2 — Sơ đồ tổng quát

```
                    ┌─────────────────────────────────────────┐
  Adapter 24V ──────┤ LM2596 ──5V──┬── ESP32 (VIN)             │
                    │              └── MAX485 (VCC)            │
                    │                                          │
                    │  ESP32 3V3 ──┬── W5500                   │
                    │              ├── ADS1115                 │
                    │              ├── OLED                    │
                    │              ├── MAX3232                 │
                    │              └── PC817 (phía ESP32)      │
                    │                                          │
   PLC Ethernet ────┤ W5500 ──SPI──── ESP32                    │
   PLC RS485 ───────┤ MAX485 ─UART2── ESP32                    │
   PLC RS-232C ─────┤ MAX3232 ─UART1─ ESP32                    │
   Cảm biến 0–10V ──┤ Hạ áp ──┐                                │
   Cảm biến 4–20mA ─┤ 150Ω ───┼─ ADS1115 ─I2C── ESP32          │
   Cờ trạng thái 24V┤ PC817 (cách ly) ──── ESP32 GPIO          │
                    └─────────────────────────────────────────┘
```

### Bảng gán chân ESP32 — dán lên bàn làm việc

| Chân ESP32 | Nối tới | Ghi chú |
|---|---|---|
| VIN | LM2596 OUT+ (5V) | Chỉ cấp 5V |
| GND | GND chung | Trừ phía hiện trường của PC817 |
| 3V3 | VCC các module 3,3V | |
| GPIO 21 | SDA — ADS1115 và OLED | Dùng chung bus I2C |
| GPIO 22 | SCL — ADS1115 và OLED | |
| GPIO 18 | W5500 SCK | SPI |
| GPIO 19 | W5500 MISO | |
| GPIO 23 | W5500 MOSI | |
| GPIO 5 | W5500 CS | |
| GPIO 26 | W5500 RST | Không bắt buộc |
| GPIO 17 | MAX485 DI | UART2 TX |
| GPIO 16 | MAX485 RO **qua cầu chia áp** | UART2 RX |
| GPIO 25 | MAX485 DE + RE (nối chung) | Chọn chiều truyền |
| GPIO 32 | MAX3232 T1IN | UART1 TX |
| GPIO 33 | MAX3232 R1OUT | UART1 RX |
| GPIO 34, 35, 36, 39 | 4 đầu ra PC817 | Chân chỉ-nhập, không có pull-up trong |

**Không dùng** GPIO 0, 2, 12, 15 — đây là chân quyết định chế độ khởi động của ESP32, nối linh kiện vào dễ làm chip không boot được.

### Địa chỉ I2C

| Thiết bị | Địa chỉ | Cách đặt |
|---|---|---|
| ADS1115 | 0x48 | Chân ADDR nối GND |
| OLED SSD1306 | 0x3C | Mặc định |

Hai địa chỉ khác nhau nên dùng chung một bus được.

---

## Phần 3 — Lắp từng khối trên breadboard

### Bước 1: Khối nguồn

**Chưa cắm ESP32 vào ở bước này.**

1. Đấu adapter 24V vào LM2596: dây dương vào `IN+`, dây âm vào `IN-`. Dùng jack DC cái để sau này tháo ra dễ.
2. Cắm adapter.
3. Đặt đồng hồ ở thang DC 20V, đo giữa `OUT+` và `OUT-`.
4. Vặn biến trở trên LM2596 (thường là con ốc nhỏ màu xanh dương) cho đến khi đồng hồ chỉ **5,0V**. Vặn nhiều vòng mới thấy thay đổi — bình thường.
5. Rút adapter, cắm lại, đo lần nữa cho chắc vẫn là 5,0V.

**Kiểm tra đạt:** đầu ra ổn định 4,9–5,1V qua nhiều lần cắm rút.

> Nếu không chỉnh được xuống dưới vài vôn: LM2596 có thể là bản đầu ra cố định. Kiểm tra lại loại module.

### Bước 2: ESP32 chạy một mình

1. Cắm ESP32 vào máy tính bằng cáp USB (chưa nối LM2596).
2. Cài Arduino IDE, thêm board ESP32 (Boards Manager → tìm "esp32" của Espressif).
3. Chọn board **"ESP32 Dev Module"**, nạp chương trình thử:

```cpp
void setup() {
  Serial.begin(115200);
  pinMode(2, OUTPUT);  // LED xanh trên board
}
void loop() {
  digitalWrite(2, !digitalRead(2));
  Serial.println("ESP32 dang chay");
  delay(500);
}
```

**Kiểm tra đạt:** LED trên board nhấp nháy, Serial Monitor in ra dòng chữ.

> Không nạp được: giữ nút **BOOT** trên board khi IDE hiện "Connecting...". Vẫn không được: đổi cáp USB — nhiều cáp chỉ sạc, không truyền dữ liệu.

### Bước 3: Cấp nguồn ESP32 từ LM2596

1. Rút USB. Rút adapter.
2. Nối `OUT+` của LM2596 → chân **VIN** của ESP32. `OUT-` → **GND**.
3. Cắm adapter. LED nguồn trên ESP32 phải sáng, LED chương trình nhấp nháy như bước 2.
4. Đo chân **3V3** của ESP32 so với GND: phải ra khoảng 3,3V.

**Kiểm tra đạt:** ESP32 chạy bằng nguồn 24V qua LM2596, chân 3V3 đúng 3,3V.

> **Lưu ý khi nạp code sau này:** rút dây VIN khỏi LM2596 trước khi cắm USB. Tránh cấp hai nguồn 5V cùng lúc vào một board — nhiều bản ESP32 giá rẻ không có diode chống ngược.

### Bước 4: Bus I2C — OLED trước, ADS1115 sau

**4a. OLED**

| OLED | ESP32 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

Nạp chương trình quét I2C:

```cpp
#include <Wire.h>
void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  for (byte a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) Serial.printf("Tim thay: 0x%02X\n", a);
  }
}
void loop() {}
```

**Kiểm tra đạt:** in ra `0x3C`.

**4b. Thêm ADS1115 vào cùng bus**

| ADS1115 | ESP32 |
|---|---|
| VDD | 3V3 |
| GND | GND |
| SDA | GPIO 21 (chung với OLED) |
| SCL | GPIO 22 (chung với OLED) |
| ADDR | GND |

Chạy lại chương trình quét.

**Kiểm tra đạt:** in ra **cả hai** `0x3C` và `0x48`. Thiếu cái nào thì kiểm tra lại dây cái đó.

### Bước 5: Đầu vào analog

Làm theo thứ tự từ an toàn đến nguy hiểm dần.

**5a. Thử bằng biến trở (an toàn nhất)**

Biến trở 10kΩ: một đầu vào 3V3, một đầu vào GND, chân giữa vào `A0` của ADS1115. Cài thư viện **Adafruit ADS1X15**, đọc kênh 0 rồi vặn biến trở.

**Kiểm tra đạt:** giá trị đọc thay đổi mượt từ 0 đến khoảng 3,3V theo vòng vặn.

**5b. Tín hiệu 0–10V**

Tín hiệu 0–10V **không bao giờ** được đưa thẳng vào ADS1115. Luôn đi qua module hạ áp:

```
Cảm biến 0–10V ──► [Module hạ áp] ──► 0–3,3V ──► ADS1115 A1
```

Trước khi nối vào ADS1115: cấp 10V vào đầu vào module, đo đầu ra bằng đồng hồ, phải **không quá 3,3V**.

**5c. Tín hiệu 4–20mA**

Điện trở 150Ω mắc nối tiếp trong vòng dòng, đo điện áp rơi trên nó:

```
+24V ──► Cảm biến 4–20mA ──► ┬── ADS1115 A2
                              │
                           [150Ω]
                              │
                             GND
```

Dòng 4mA cho 0,6V, 20mA cho 3,0V. Phần mềm đổi ngược: `dong_mA = dien_ap / 150 * 1000`.

> Cách mắc này nối đất của vòng cảm biến với đất của gateway — chấp nhận được khi demo. Khi lắp trong nhà máy, cân nhắc bộ cách ly tín hiệu analog để tránh vòng lặp đất.

### Bước 6: Đầu vào số 24V qua PC817 — điểm cách ly quan trọng nhất

Module PC817 có **hai phía tách biệt về điện**. Đây là toàn bộ lý do dùng nó.

| Phía hiện trường (máy) | Phía ESP32 |
|---|---|
| IN1–IN4: tín hiệu 24V từ máy | OUT1–OUT4 → GPIO 34, 35, 36, 39 |
| GND hiện trường: đất của tín hiệu 24V | VCC → 3V3, GND → GND của ESP32 |

**Tuyệt đối không nối GND hiện trường với GND của ESP32.** Nối vào là mất cách ly, và sự cố điện phía máy có thể truyền sang gateway.

Kiểm tra module trước khi dùng: xem điện trở ở phía đầu vào có phù hợp mức 24V không (module ghi 12–24V là được). Loại chỉ ghi 3,3–5V dùng với 24V sẽ cháy LED bên trong.

**Kiểm tra đạt:** dùng adapter 24V riêng và một nút nhấn làm "cờ trạng thái giả". Nhấn nút, GPIO tương ứng đổi mức; nhả ra, đổi lại.

### Bước 7: Ethernet W5500

| W5500 | ESP32 |
|---|---|
| VCC | 3V3 (kiểm tra module của bạn — một số loại có chân 5V riêng) |
| GND | GND |
| SCK | GPIO 18 |
| MISO | GPIO 19 |
| MOSI | GPIO 23 |
| CS (hoặc SS/SCS) | GPIO 5 |
| RST | GPIO 26 |

Cắm dây mạng từ W5500 vào router hoặc thẳng vào laptop. Dùng thư viện **Ethernet** của Arduino, gọi `Ethernet.init(5)` trước `Ethernet.begin()`.

**Kiểm tra đạt:** ESP32 nhận được địa chỉ IP (in ra Serial), và từ máy tính `ping` được tới địa chỉ đó.

> Tắt WiFi trong firmware (`WiFi.mode(WIFI_OFF)`). Vừa đúng khuyến nghị đi dây của DENSO, vừa giảm tải cho bộ ổn áp 3,3V trên ESP32 đang phải nuôi cả W5500.

Sau khi ping được, thử gửi một bản tin MQTT tới broker Mosquitto trên laptop bằng thư viện **PubSubClient**, topic `gw/01/status`. Mở dashboard, thấy nhận được là đạt.

### Bước 8: Cổng serial — RS485 và RS-232C

**8a. MAX485 cho Keyence KV-8000**

| MAX485 | ESP32 |
|---|---|
| VCC | 5V (từ LM2596) |
| GND | GND |
| DI | GPIO 17 |
| RO | GPIO 16 **qua cầu chia áp** |
| DE + RE | Nối chung với nhau → GPIO 25 |
| A, B | Nối vào cổng RS485 của PLC |

Cầu chia áp cho chân RO — **bắt buộc**:

```
MAX485 RO ──[10kΩ]──┬──► GPIO 16
                    │
                 [20kΩ]
                    │
                   GND
```

Trước khi nối GPIO 16: cấp nguồn, đo điểm giữa cầu chia khi đường truyền rảnh — phải khoảng **3,3V, không phải 5V**.

**8b. MAX3232 cho Omron CPM2C**

| MAX3232 | ESP32 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| T1IN (TXD) | GPIO 32 |
| R1OUT (RXD) | GPIO 33 |
| Cổng DB9 | Nối vào cổng RS-232C của PLC |

MAX3232 chạy tốt ở 3,3V nên không cần cầu chia.

**Kiểm tra đạt (cả hai):** thử vòng lặp — nối chân phát với chân nhận ở phía cổng ra (A với B qua một module MAX485 thứ hai, hoặc chân 2 với chân 3 của DB9), gửi một chuỗi, nhận lại đúng chuỗi đó.

### Bước 9: OLED hiển thị trạng thái

Cài thư viện **Adafruit SSD1306** và **Adafruit GFX**. Hiện tối thiểu: địa chỉ IP, trạng thái kết nối MQTT, trạng thái máy đang đọc.

Cập nhật màn hình **mỗi 500ms trở lên**, không cập nhật liên tục — OLED dùng chung bus I2C với ADS1115, cập nhật dày sẽ chiếm bus và làm chậm việc đọc analog.

---

## Phần 4 — Chuyển từ breadboard sang PCB

Chỉ làm khi **mọi bước ở Phần 3 đều đạt** trên breadboard.

### Bố trí

1. Xếp module lên PCB lỗ trước khi hàn. Đặt LM2596 xa ADS1115 nhất có thể — bộ nguồn xung tạo nhiễu, ADS1115 đo điện áp nhỏ rất nhạy với nhiễu.
2. Hàn **header cái** lên PCB rồi cắm module vào, thay vì hàn chết module. Hỏng module nào thì rút ra thay, không phải tháo mạch.
3. Chia PCB thành hai vùng rõ ràng: vùng hiện trường (đầu vào PC817, domino) và vùng ESP32. Khoảng cách giữa hai vùng ít nhất 5mm — đây là khe cách ly.

### Hàn

- Hàn nguồn trước, kiểm tra điện áp, rồi mới hàn phần còn lại.
- Dây nguồn dùng dây to hơn dây tín hiệu.
- Sau khi hàn xong mỗi khối, **đo thông mạch** giữa 5V và GND, giữa 3V3 và GND — không được chạm nhau (đồng hồ không kêu bíp).

### Kiểm tra sau khi hàn

Lặp lại toàn bộ các phép thử ở Phần 3, theo đúng thứ tự. Mạch trên breadboard chạy được không có nghĩa mạch hàn chạy được.

---

## Phần 5 — Đóng gói vào vỏ ray DIN

1. **Domino đấu dây** gắn ở cạnh dưới vỏ, xếp theo nhóm và dán nhãn:

```
[24V+][24V-] │ [A][B] │ [TX][RX][GND] │ [AI1][AI2][GND] │ [DI1][DI2][DI3][DI4][GND-HT]
  Nguồn      │ RS485  │   RS-232C     │    Analog       │   Cờ trạng thái (cách ly)
```

2. **Cổng RJ45** của W5500 khoét lỗ ra ngoài vỏ, để cắm cáp mạng không phải mở nắp.
3. **OLED** khoét lỗ mặt trước, dán kính hoặc mica mỏng che bụi.
4. Cố định PCB bằng ốc và trụ đồng, không dán keo — để sau này mở ra sửa được.
5. Chừa lỗ thoáng khí gần LM2596 — nó tỏa nhiệt khi hạ từ 24V xuống 5V.

---

## Phần 6 — Kiểm tra cuối cùng

### Kiểm tra điện (chưa cắm vào PLC)

| Phép đo | Giá trị đúng |
|---|---|
| Đầu ra LM2596 | 4,9–5,1V |
| Chân 3V3 của ESP32 | 3,2–3,4V |
| Điểm giữa cầu chia MAX485 | ≤ 3,3V |
| Đầu ra module hạ áp khi vào 10V | ≤ 3,3V |
| GND hiện trường với GND ESP32 | **Hở mạch** (không thông) |

### Kiểm tra chức năng

- [ ] OLED hiện IP và trạng thái
- [ ] Dashboard hiện "MQTT: đã kết nối"
- [ ] Vặn biến trở, giá trị analog trên dashboard thay đổi theo
- [ ] Nhấn nút 24V, cờ trạng thái trên dashboard đổi theo
- [ ] Rút dây mạng rồi cắm lại, gateway tự kết nối lại
- [ ] Chạy liên tục 1 giờ không treo, LM2596 không quá nóng (đặt tay giữ được)

### Kiểm tra với PLC

Chưa có PLC thật: dùng phần mềm giả lập trên laptop.

- **Modbus TCP:** phần mềm giả lập Modbus slave miễn phí
- **Mitsubishi MC protocol:** GX Works2/3 có chế độ mô phỏng (cần bản quyền) hoặc thư viện giả lập mã nguồn mở

Có PLC thật: xin mượn ở lab tự động hóa của khoa.

**Trước khi cắm vào PLC thật lần đầu:** đảm bảo firmware **chỉ có lệnh đọc**, không có lệnh ghi. Đây là cam kết "không đụng vào máy" đã ghi trên dashboard — phải đúng từ lần cắm đầu tiên.

---

## Phần 7 — Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| ESP32 không sáng khi cấp 24V | LM2596 chưa chỉnh về 5V, hoặc đấu ngược cực | Đo lại đầu ra LM2596 |
| ESP32 chạy rồi tự khởi động lại liên tục | Nguồn không đủ, hoặc nối nhầm chân boot (0, 2, 12, 15) | Kiểm tra chân đang dùng; thử adapter mạnh hơn |
| Quét I2C không thấy thiết bị | Đảo SDA/SCL, hoặc dây lỏng | Đổi chỗ hai dây, ấn chặt |
| Đọc analog nhảy lung tung | Nhiễu từ LM2596, hoặc chân analog bỏ trống | Đặt ADS1115 xa LM2596; nối đất các kênh không dùng |
| W5500 không nhận IP | Sai chân CS, hoặc thiếu `Ethernet.init(5)` | Kiểm tra lại dây SPI và lệnh khởi tạo |
| Cổng RS485 không nhận gì | Đảo dây A/B | Đổi chỗ A và B — rất hay gặp |
| RS-232C không nhận gì | Đảo TX/RX, hoặc dùng nhầm MAX485 | TX của bên này nối RX của bên kia; dùng MAX3232 |
| Cờ trạng thái không đổi khi có 24V | Module PC817 là loại 5V, đã cháy LED | Kiểm tra loại module; thay loại 12–24V |

---

## Phân công gợi ý

| Người | Phần |
|---|---|
| Đạt | Phần 1–6: mua, lắp, hàn, đóng gói |
| Tuấn | Firmware các bước 2–9, đặc biệt driver đọc PLC |
| Hưng | Nối firmware với dashboard qua MQTT (bước 7) |

Đạt và Tuấn nên làm song song từ bước 4 trở đi: Đạt lắp xong khối nào, Tuấn viết code thử khối đó ngay.
