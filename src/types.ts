export type SignalClass = 'COUNTER' | 'MOTOR_LOAD' | 'TEMPERATURE' | 'VIBRATION' | 'PRESSURE_BURST' | 'OTHER';

export type ChannelStatus = 'analyzing' | 'confirmed' | 'pending' | 'unknown' | 'wiring_fault';

export interface SignalFeatures {
  mean: number;
  std: number;
  zcr: number;
  slew: number;
  maxSlew: number;
  levels: number;
  kurt: number;
  vpp: number;
  rms: number;
  acfLag1: number;   // tự tương quan trễ 1
  acfLag20: number;  // tự tương quan trễ 20 — đặc trưng quan trọng nhất theo mô hình
}

export interface ChannelData {
  id: number;
  name: string;
  kind: 'vibration' | 'temperature' | 'counter' | 'exotic' | 'motor';
  buf: number[];
  t: number;
  status: ChannelStatus;
  pred: SignalClass | null;
  conf: number;
  oodScore: number; // 0 to 1, higher means abnormal/OOD
  final: SignalClass | null;
  lastUpdated: string;
  wiringFault?: boolean;   // bật để bơm tín hiệu đảo cực, kiểm tra luật kiểm tra dải
}

export interface LabelLogEntry {
  id: string;
  time: string;
  ch: number;
  channelName: string;
  pred: SignalClass | null;
  conf: number;
  final: SignalClass;
  src: 'auto' | 'engineer';
  featuresSummary?: string;
}

export interface RoiParams {
  machines: number;
  machinesPerDevice: number;
  hManual: number;
  hGw: number;
  rate: number;
  deviceCost: number;
  baselineDeviceCost: number;
  months: number;
}
