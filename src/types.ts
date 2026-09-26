// Trạng thái máy — đúng sáu trạng thái mentor DENSO liệt kê ngày 21/09/2026
export type MachineState =
  | 'STOPPED'   // máy dừng
  | 'READY'     // máy chuẩn bị vận hành
  | 'AUTO'      // máy chế độ auto running (chờ phôi)
  | 'WORKING'   // máy đang làm việc
  | 'DONE'      // máy hoàn thành
  | 'ERROR';    // máy báo lỗi

export type ProcessType = 'PRESS_FORCE' | 'TORQUE' | 'AIR_PRESSURE';

export interface PlcInfo {
  vendor: string;
  model: string;
  port: string;          // cổng vật lý dùng để đọc
  protocol: string;
  readCommand: string;   // lệnh ĐỌC duy nhất gateway được phép gửi
  ip?: string;
}

export interface RegisterMap {
  address: string;
  name: string;
  unit?: string;
}

export interface MachineConfig {
  id: string;
  name: string;
  line: string;
  process: ProcessType;
  idealCycleSec: number;     // thời gian chu kỳ lý tưởng, dùng tính hiệu suất OEE
  plc: PlcInfo;
  registers: RegisterMap[];
  errorCodes: { code: string; vi: string }[];
}

export interface Cycle {
  id: number;
  machineId: string;
  at: number;                // thời điểm mô phỏng (giây)
  y: number[];               // đường cong để hiển thị
  f: number[];               // 9 đặc trưng — tính sẵn trên chu kỳ gốc
  score: number;             // khoảng cách Mahalanobis
  anomalous: boolean;
  injected?: string;         // mã lỗi nếu là chu kỳ do người demo chèn vào
}

// Dòng thời gian gộp các trạng thái chạy (AUTO/WORKING/DONE) thành RUN,
// vì mỗi chu kỳ chỉ vài giây — ở thang cả ca làm việc không thể vẽ riêng từng cái.
export type SpanKind = 'RUN' | 'READY' | 'STOPPED' | 'ERROR';

export interface StateSpan {
  kind: SpanKind;
  start: number;
  end: number;
  errorCode?: string;
}

export interface MachineRuntime {
  state: MachineState;
  stateSince: number;
  errorCode?: string;
  timeline: StateSpan[];
  timeIn: Record<MachineState, number>;              // tổng giây ở mỗi trạng thái
  errorStats: Record<string, { count: number; seconds: number }>;
  cycles: Cycle[];           // chu kỳ gần nhất, mới nhất ở cuối
  totalCycles: number;
  anomalousCycles: number;
  lastRead: number;
  pendingFault?: string;
  pendingStop?: boolean;
}
