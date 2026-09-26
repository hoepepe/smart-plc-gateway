import { MachineConfig, MachineState } from '../types';

/**
 * Bốn máy mô phỏng, phủ đúng ba dòng PLC mentor DENSO nêu:
 *   Keyence KV-8000 · Omron CJ2M-CPU33 và CPM2C · Mitsubishi Q10UDEHCPU
 *
 * Địa chỉ thanh ghi dưới đây là VÍ DỤ. Khi triển khai, thay bằng danh sách
 * tín hiệu DENSO đã có — gateway chỉ cần sửa file cấu hình này, không sửa code.
 *
 * Giao thức và lệnh đọc từng dòng cần đối chiếu lại với manual của hãng.
 */
export const MACHINES: MachineConfig[] = [
  {
    id: 'M01',
    name: 'Máy ép vòng bi',
    line: 'Line 2 · Lắp ráp',
    process: 'PRESS_FORCE',
    idealCycleSec: 3.2,
    plc: {
      vendor: 'Mitsubishi',
      model: 'Q10UDEHCPU',
      port: 'Ethernet tích hợp trên CPU',
      protocol: 'MC protocol (3E frame)',
      readCommand: '0401 — Batch Read',
      ip: '192.168.10.21',
    },
    registers: [
      { address: 'D100', name: 'Lực ép', unit: 'kN' },
      { address: 'D102', name: 'Chiều cao ép', unit: 'mm' },
      { address: 'D110', name: 'Mã lỗi' },
      { address: 'M0–M5', name: 'Cờ trạng thái máy' },
    ],
    errorCodes: [
      { code: 'E101', vi: 'Quá lực ép' },
      { code: 'E102', vi: 'Cảm biến phôi không tác động' },
      { code: 'E103', vi: 'Hết phôi đầu vào' },
    ],
  },
  {
    id: 'M02',
    name: 'Máy siết bu-lông',
    line: 'Line 2 · Lắp ráp',
    process: 'TORQUE',
    idealCycleSec: 3.6,
    plc: {
      vendor: 'Omron',
      model: 'CJ2M-CPU33',
      port: 'EtherNet/IP tích hợp trên CPU',
      protocol: 'FINS/UDP',
      readCommand: '0101 — Memory Area Read',
      ip: '192.168.10.22',
    },
    registers: [
      { address: 'D200', name: 'Lực xiết', unit: 'N·m' },
      { address: 'D202', name: 'Góc xoay', unit: '°' },
      { address: 'D210', name: 'Mã lỗi' },
      { address: 'W0.00–W0.05', name: 'Cờ trạng thái máy' },
    ],
    errorCodes: [
      { code: 'E201', vi: 'Không đạt lực mục tiêu' },
      { code: 'E202', vi: 'Kẹt đầu siết' },
      { code: 'E203', vi: 'Hết bu-lông cấp phôi' },
    ],
  },
  {
    id: 'M03',
    name: 'Cụm xi-lanh khí nén',
    line: 'Line 3 · Gia công',
    process: 'AIR_PRESSURE',
    idealCycleSec: 2.8,
    plc: {
      vendor: 'Keyence',
      model: 'KV-8000',
      port: 'Ethernet tích hợp trên CPU',
      protocol: 'KV Host Link',
      readCommand: 'RDS — Đọc liên tiếp',
      ip: '192.168.10.23',
    },
    registers: [
      { address: 'DM300', name: 'Áp lực khí nén', unit: 'bar' },
      { address: 'DM302', name: 'Tải trọng', unit: 'kg' },
      { address: 'DM310', name: 'Mã lỗi' },
      { address: 'MR000–MR005', name: 'Cờ trạng thái máy' },
    ],
    errorCodes: [
      { code: 'E301', vi: 'Áp khí thấp' },
      { code: 'E302', vi: 'Xi-lanh không về hành trình' },
      { code: 'E303', vi: 'Cửa an toàn mở' },
    ],
  },
  {
    id: 'M04',
    name: 'Máy ép đời cũ',
    line: 'Line 1 · Gia công',
    process: 'PRESS_FORCE',
    idealCycleSec: 4.0,
    plc: {
      vendor: 'Omron',
      model: 'CPM2C',
      port: 'Cổng serial RS-232C (không có Ethernet)',
      protocol: 'Host Link (C-mode)',
      readCommand: 'RD — Đọc vùng DM',
    },
    registers: [
      { address: 'DM0100', name: 'Lực ép', unit: 'kN' },
      { address: 'DM0110', name: 'Mã lỗi' },
      { address: 'IR 10.00–10.05', name: 'Cờ trạng thái máy' },
    ],
    errorCodes: [
      { code: 'E401', vi: 'Quá lực ép' },
      { code: 'E402', vi: 'Dừng khẩn cấp' },
    ],
  },
];

export const STATE_META: Record<MachineState, { vi: string; color: string; bg: string; dot: string; running: boolean }> = {
  // Theo nguyên tắc giao diện vận hành ISA-101: trạng thái bình thường dùng màu trung tính,
  // màu nổi chỉ dành cho trạng thái cần người vận hành chú ý. Nhờ vậy màu đỏ luôn đập vào mắt.
  STOPPED: { vi: 'Dừng', color: 'text-amber-800', bg: 'bg-amber-50', dot: 'bg-amber-500', running: false },
  READY:   { vi: 'Chuẩn bị vận hành', color: 'text-slate-700', bg: 'bg-slate-100', dot: 'bg-slate-400', running: false },
  AUTO:    { vi: 'Auto running', color: 'text-slate-700', bg: 'bg-slate-100', dot: 'bg-slate-600', running: true },
  WORKING: { vi: 'Đang làm việc', color: 'text-slate-700', bg: 'bg-slate-100', dot: 'bg-slate-700', running: true },
  DONE:    { vi: 'Hoàn thành', color: 'text-slate-700', bg: 'bg-slate-100', dot: 'bg-slate-600', running: true },
  ERROR:   { vi: 'Báo lỗi', color: 'text-rose-700', bg: 'bg-rose-50', dot: 'bg-rose-600', running: false },
};

// màu hex cho biểu đồ dòng thời gian
export const STATE_HEX: Record<MachineState, string> = {
  STOPPED: '#f59e0b', READY: '#dbe2ea', AUTO: '#94a3b8',
  WORKING: '#94a3b8', DONE: '#94a3b8', ERROR: '#e11d48',
};

export const FEATURE_VI: Record<string, string> = {
  peak: 'Giá trị đỉnh',
  trough: 'Giá trị đáy',
  t_peak: 'Thời điểm đạt đỉnh',
  mean_level: 'Mức trung bình',
  rise_slope: 'Độ dốc tăng lớn nhất',
  roughness: 'Độ gồ ghề',
  n_peaks: 'Số đỉnh',
  early_level: 'Mức đầu chu kỳ',
  mid_level: 'Mức giữa chu kỳ',
};
