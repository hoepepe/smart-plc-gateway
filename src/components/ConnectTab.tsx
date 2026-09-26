import React, { useState } from 'react';
import { Lock, Plug, FileCode2 } from 'lucide-react';
import { MACHINES } from '../data/machines';
import { Card, Note } from './charts';

// Linh kiện cho MỘT gateway. Không tính cảm biến demo (MPU6050, biến trở, nút nhấn),
// phí vận chuyển và công lắp đặt.
const BOM: { part: string; role: string; price: number }[] = [
  { part: 'ESP32 DevKit V1', role: 'Bộ xử lý, chạy bộ phát hiện bất thường', price: 100_000 },
  { part: 'Module Ethernet W5500', role: 'Nối cổng Ethernet của PLC, đi dây theo khuyến nghị DENSO', price: 90_000 },
  { part: 'MAX485', role: 'Cổng RS485 của Keyence KV-8000 — chân RO qua cầu chia áp 10k/20k', price: 30_000 },
  { part: 'MAX3232', role: 'Cổng RS-232C của Omron CPM2C (RS-232 khác RS-485, không dùng chung MAX485)', price: 25_000 },
  { part: 'ADS1115', role: 'Đọc tín hiệu analog nằm ngoài PLC', price: 70_000 },
  { part: 'Module hạ áp 0–10V', role: 'Chuẩn hóa tín hiệu 0–10V', price: 50_000 },
  { part: 'Điện trở 150Ω sai số 0,1%', role: 'Chuyển 4–20mA thành 0,6–3,0V, vừa dải ADC 3,3V', price: 10_000 },
  { part: 'PC817 cách ly quang', role: 'Đọc cờ trạng thái 24V, cách ly khỏi máy', price: 40_000 },
  { part: 'Adapter 24V riêng', role: 'Nguồn ngoài, không lấy từ nguồn của máy', price: 120_000 },
  { part: 'LM2596', role: 'Hạ 24V xuống 5V cho mạch', price: 30_000 },
  { part: 'Màn hình OLED 0,96"', role: 'Hiện trạng thái tại chỗ', price: 45_000 },
  { part: 'Vỏ ray DIN, domino, PCB, dây', role: 'Lắp vào tủ điện', price: 160_000 },
];
const BOM_TOTAL = BOM.reduce((a, b) => a + b.price, 0);

const vnd = (n: number) => `${Math.round(n).toLocaleString('vi-VN')} đ`;

function NumInput({ id, label, value, onChange, unit, step = 1, note }: {
  id: string; label: string; value: number; onChange: (v: number) => void;
  unit: string; step?: number; note?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm text-slate-700 mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <input id={id} type="number" min={0} step={step} value={value}
          onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))}
          className="w-full bg-white border border-slate-300 rounded-md px-3 py-2 font-mono tabular-nums text-sm
            focus:outline-2 focus:outline-slate-900 focus:border-slate-900" />
        <span className="text-xs text-slate-500 w-14 shrink-0">{unit}</span>
      </div>
      {note && <p className="text-xs text-slate-500 mt-1">{note}</p>}
    </div>
  );
}

export function ConnectTab() {
  const [machines, setMachines] = useState(20);
  const [moduleCost, setModuleCost] = useState(30_000_000);
  const [gwCost, setGwCost] = useState(BOM_TOTAL);
  const [perGw, setPerGw] = useState(1);

  const gateways = Math.ceil(machines / Math.max(1, perGw));
  const current = machines * moduleCost;
  const ours = gateways * gwCost;
  const saving = current - ours;
  const ratio = ours > 0 ? current / ours : 0;

  return (
    <div className="space-y-5">
      <Card title="Không đụng vào máy"
        sub="Nỗi lo lớn nhất khi lắp thêm thiết bị vào dây chuyền đang chạy là làm dừng máy. Gateway được thiết kế để không thể gây ra điều đó.">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            { icon: Plug, t: 'Nguồn điện riêng', d: 'Gateway dùng adapter 24V riêng, không lấy điện từ máy — đúng như mentor DENSO yêu cầu.' },
            { icon: Lock, t: 'Chỉ đọc, không ghi', d: 'Gateway chỉ được phép gửi lệnh đọc tới PLC. Quy tắc thiết kế: mã nguồn gateway không chứa lệnh ghi nào — ai cũng kiểm tra được bằng cách đọc mã.' },
            { icon: FileCode2, t: 'Không sửa chương trình PLC', d: 'Chương trình đang chạy trên PLC giữ nguyên. Một số dòng có thể cần bật cổng truyền thông một lần trong phần tham số — cần xác nhận theo manual.' },
          ].map(({ icon: Icon, t, d }) => (
            <div key={t}>
              <div className="flex items-center gap-2 text-slate-900 font-medium text-sm">
                <Icon size={16} className="text-slate-500" /> {t}
              </div>
              <p className="text-sm text-slate-600 leading-relaxed mt-1.5">{d}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Ba dòng PLC DENSO đang dùng"
        sub="Mỗi máy được mô tả bằng một file cấu hình. Thêm máy mới là thêm một file, không phải viết lại chương trình.">
        <div className="overflow-x-auto -mx-5">
          <table className="w-full text-sm min-w-[760px]">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                <th className="font-medium px-5 pb-2.5">Máy</th>
                <th className="font-medium pb-2.5">PLC</th>
                <th className="font-medium pb-2.5">Cổng đọc</th>
                <th className="font-medium pb-2.5">Giao thức</th>
                <th className="font-medium pb-2.5 pr-5">Lệnh đọc</th>
              </tr>
            </thead>
            <tbody>
              {MACHINES.map((m) => (
                <tr key={m.id} className="border-b border-slate-100 last:border-0 align-top">
                  <td className="px-5 py-3">
                    <div className="text-slate-900">{m.name}</div>
                    <div className="text-xs text-slate-500">{m.registers.length} tín hiệu đọc</div>
                  </td>
                  <td className="py-3 text-slate-800">{m.plc.vendor} {m.plc.model}</td>
                  <td className="py-3 text-slate-600 pr-4">{m.plc.port}</td>
                  <td className="py-3 text-slate-800">{m.plc.protocol}</td>
                  <td className="py-3 pr-5 font-mono text-xs text-slate-600">{m.plc.readCommand}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4">
          <Note tone="amber">
            Giao thức và lệnh đọc từng dòng <strong>cần đối chiếu lại với manual của hãng</strong> trước khi triển khai.
            Địa chỉ thanh ghi trong cấu hình là ví dụ, sẽ thay bằng danh sách tín hiệu DENSO đã có.
          </Note>
        </div>
      </Card>

      <Card title="Dữ liệu đi đường nào" sub="Toàn bộ chạy trong mạng nội bộ nhà máy. Dữ liệu vận hành không ra internet.">
        <ol className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
          {[
            { t: 'PLC', d: 'Cờ trạng thái, mã lỗi, lực ép, lực xiết, áp lực khí nén — đã có sẵn trong bộ nhớ PLC.' },
            { t: 'Gateway', d: 'Đọc theo giao thức gốc của từng hãng, tính đặc trưng chu kỳ và chấm điểm bất thường tại chỗ.' },
            { t: 'Broker MQTT', d: 'Nhận bản tin trạng thái và chu kỳ, chuyển tiếp cho giao diện và máy chủ.' },
            { t: 'Giao diện và máy chủ', d: 'Hiển thị thời gian thực, tính OEE, lưu lịch sử vào SQLite.' },
          ].map((s, i) => (
            <li key={s.t} className="border border-slate-200 rounded-md p-3.5 bg-slate-50">
              <div className="text-xs text-slate-400 font-mono">bước {i + 1}</div>
              <div className="font-medium text-slate-900 mt-0.5">{s.t}</div>
              <p className="text-xs text-slate-600 leading-relaxed mt-1">{s.d}</p>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <Card className="lg:col-span-2" title="Chi phí so với bộ mở rộng truyền thông"
          sub="Mentor DENSO xác nhận: bộ mở rộng truyền thông cho PLC tốn khoảng 30 triệu mỗi máy, chưa tính công và layout.">
          <div className="space-y-4">
            <NumInput id="n-machines" label="Số máy PLC đời cũ cần kết nối" value={machines} onChange={setMachines} unit="máy" />
            <NumInput id="module-cost" label="Chi phí bộ mở rộng mỗi máy" value={moduleCost} onChange={setModuleCost}
              unit="đ" step={1_000_000} note="Theo trả lời của mentor DENSO ngày 21/09/2026." />
            <NumInput id="gw-cost" label="Chi phí một gateway" value={gwCost} onChange={setGwCost}
              unit="đ" step={10_000} note="Tổng linh kiện ở bảng bên, chưa tính vận chuyển và công lắp." />
            <NumInput id="per-gw" label="Số máy một gateway phục vụ" value={perGw} onChange={(v) => setPerGw(Math.max(1, v))}
              unit="máy" note="Để 1 nếu mỗi máy một gateway. Tăng lên nếu nhiều máy đặt gần nhau." />
          </div>
        </Card>

        <div className="lg:col-span-3 space-y-5">
          <Card>
            <dl className="grid grid-cols-2 gap-5">
              <div>
                <dt className="text-xs text-slate-500">Bộ mở rộng cho {machines} máy</dt>
                <dd className="font-mono tabular-nums text-lg font-semibold text-slate-900 mt-1">{vnd(current)}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">{gateways} gateway</dt>
                <dd className="font-mono tabular-nums text-lg font-semibold text-slate-900 mt-1">{vnd(ours)}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Chênh lệch chi phí thiết bị</dt>
                <dd className={`font-mono tabular-nums text-2xl font-semibold mt-1 ${saving >= 0 ? 'text-slate-900' : 'text-rose-600'}`}>
                  {vnd(saving)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Rẻ hơn</dt>
                <dd className="font-mono tabular-nums text-2xl font-semibold text-slate-900 mt-1">
                  {ratio > 0 ? `${ratio.toFixed(0)} lần` : '—'}
                </dd>
              </div>
            </dl>
            <div className="mt-5">
              <Note tone="rose">
                <strong>Câu chưa có đáp án:</strong> ba dòng Q10UDEHCPU, CJ2M-CPU33 và KV-8000 đều có cổng Ethernet trên CPU,
                vậy vì sao vẫn cần bộ mở rộng 30 triệu? Nếu cổng đó đang bận cho màn hình HMI hoặc thiết bị khác,
                gateway cũng phải thêm phần cứng và khoản chênh lệch sẽ nhỏ đi. Cần hỏi mentor trước khi dùng con số này.
              </Note>
            </div>
          </Card>

          <Card title="Linh kiện cho một gateway" pad={false}>
            <table className="w-full text-sm">
              <tbody>
                {BOM.map((b) => (
                  <tr key={b.part} className="border-b border-slate-100">
                    <td className="px-5 py-2.5">
                      <div className="text-slate-800">{b.part}</div>
                      <div className="text-xs text-slate-500">{b.role}</div>
                    </td>
                    <td className="px-5 py-2.5 text-right font-mono tabular-nums text-slate-700 whitespace-nowrap">{vnd(b.price)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-50">
                  <td className="px-5 py-3 font-medium">Tổng</td>
                  <td className="px-5 py-3 text-right font-mono tabular-nums font-semibold">{vnd(BOM_TOTAL)}</td>
                </tr>
              </tfoot>
            </table>
          </Card>
        </div>
      </div>

      <Card title="Giá trị không nằm ở chỗ rẻ hơn">
        <p className="text-sm text-slate-700 leading-relaxed max-w-3xl">
          Mentor DENSO cho biết máy PLC đời cũ hiện <strong>chưa được đưa lên hệ thống giám sát</strong>, dữ liệu vẫn lấy bằng
          cách rút thẻ nhớ. Nghĩa là DENSO không đang trả 30 triệu cho từng máy — họ chưa làm, vì làm như vậy quá đắt.
          Gateway biến một việc trước đây quá đắt để làm thành việc làm được.
        </p>
      </Card>
    </div>
  );
}
