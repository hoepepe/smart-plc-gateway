import { MachineConfig, MachineRuntime } from '../types';

/**
 * OEE = Độ sẵn sàng × Hiệu suất × Chất lượng — công thức chuẩn.
 *
 *  Độ sẵn sàng  = thời gian chạy / thời gian kế hoạch
 *                 (chuẩn bị vận hành, dừng và báo lỗi đều tính là mất thời gian)
 *  Hiệu suất    = (thời gian chu kỳ lý tưởng × số chu kỳ) / thời gian chạy
 *  Chất lượng   = chu kỳ bình thường / tổng chu kỳ
 *
 * Lưu ý: "chất lượng" ở đây là ƯỚC TÍNH — chu kỳ bất thường chưa chắc là sản phẩm lỗi,
 * chỉ là nghi lỗi. Kết quả kiểm tra thật (QC) sẽ cho con số chính xác hơn.
 */
export function computeOee(m: MachineConfig, r: MachineRuntime) {
  const t = r.timeIn;
  const planned = Object.values(t).reduce((a, b) => a + b, 0) || 1;
  const run = t.AUTO + t.WORKING + t.DONE;
  const availability = run / planned;
  const performance = run > 0 ? Math.min(1, (m.idealCycleSec * r.totalCycles) / run) : 0;
  const quality = r.totalCycles > 0 ? (r.totalCycles - r.anomalousCycles) / r.totalCycles : 1;
  return {
    availability, performance, quality,
    oee: availability * performance * quality,
    plannedSec: planned, runSec: run,
    downSec: t.ERROR + t.STOPPED + t.READY,
  };
}

export const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;

export function fmtDuration(sec: number): string {
  if (sec < 60) return `${Math.round(sec)} giây`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m} phút`;
  return `${Math.floor(m / 60)} giờ ${m % 60} phút`;
}
