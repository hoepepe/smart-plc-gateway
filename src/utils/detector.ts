import cyclesData from '../data/cycles.json';
import { ProcessType } from '../types';

/**
 * Bộ phát hiện chu kỳ bất thường — khoảng cách Mahalanobis.
 *
 * Dùng ĐÚNG tham số (vector trung bình, ma trận nghịch đảo hiệp phương sai, ngưỡng)
 * do ml/cycles.py huấn luyện và xuất ra. Đặc trưng của mỗi chu kỳ cũng được tính
 * sẵn bên Python trên đường cong gốc. Vì vậy điểm số ở đây trùng khớp tuyệt đối
 * với điểm số dùng để đánh giá mô hình — không có bản "mô phỏng" nào chen giữa.
 */

interface ProcModel {
  vi: string;
  unit: string;
  nominal: number;
  model: { type: string; mu: number[]; std: number[]; inv_cov: number[][]; threshold: number };
  metrics: {
    n_train: number; n_calib: number; n_test_normal: number;
    false_alarm_mahalanobis: number; false_alarm_isoforest: number;
    faults: { code: string; vi: string; detect_mahalanobis: number; detect_isoforest: number; n: number }[];
  };
  samples: {
    normal: { y: number[]; f: number[] }[];
    faults: Record<string, { y: number[]; f: number[] }[]>;
  };
}

export const DATA = cyclesData as unknown as {
  sample_rate_hz: number;
  features: string[];
  processes: Record<ProcessType, ProcModel>;
  policy: Record<string, string>;
};

export const FEATURES = DATA.features;

export function proc(p: ProcessType): ProcModel {
  return DATA.processes[p];
}

/** Khoảng cách Mahalanobis: sqrt((f − μ)ᵀ Σ⁻¹ (f − μ)) */
export function mahalanobis(f: number[], p: ProcessType): number {
  const { mu, inv_cov } = proc(p).model;
  const d = f.map((v, i) => v - mu[i]);
  let s = 0;
  for (let i = 0; i < d.length; i++) {
    let row = 0;
    for (let j = 0; j < d.length; j++) row += inv_cov[i][j] * d[j];
    s += d[i] * row;
  }
  return Math.sqrt(Math.max(0, s));
}

export function threshold(p: ProcessType): number {
  return proc(p).model.threshold;
}

/**
 * Đặc trưng nào lệch nhiều nhất so với chu kỳ bình thường, tính theo số độ lệch chuẩn.
 * Để kỹ sư biết VÌ SAO một chu kỳ bị gắn cờ, không chỉ biết là nó bị gắn cờ.
 */
export function explain(f: number[], p: ProcessType, top = 3) {
  const { mu, std } = proc(p).model;
  return f
    .map((v, i) => ({
      name: FEATURES[i],
      value: v,
      normal: mu[i],
      z: std[i] > 0 ? (v - mu[i]) / std[i] : 0,
    }))
    .sort((a, b) => Math.abs(b.z) - Math.abs(a.z))
    .slice(0, top);
}

/** Dải bình thường (phân vị 5–95) của đường cong, để vẽ nền so sánh. */
const envCache: Partial<Record<ProcessType, { lo: number[]; hi: number[]; mid: number[] }>> = {};

export function resample(y: number[], n: number): number[] {
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * (y.length - 1);
    const a = Math.floor(x);
    const b = Math.min(y.length - 1, a + 1);
    out.push(y[a] + (y[b] - y[a]) * (x - a));
  }
  return out;
}

export function envelope(p: ProcessType, n = 110) {
  if (envCache[p]) return envCache[p]!;
  const curves = proc(p).samples.normal.map((s) => resample(s.y, n));
  const lo: number[] = [], hi: number[] = [], mid: number[] = [];
  for (let i = 0; i < n; i++) {
    const col = curves.map((c) => c[i]).sort((a, b) => a - b);
    const q = (k: number) => col[Math.min(col.length - 1, Math.max(0, Math.round(k * (col.length - 1))))];
    lo.push(q(0.05)); hi.push(q(0.95)); mid.push(q(0.5));
  }
  envCache[p] = { lo, hi, mid };
  return envCache[p]!;
}
