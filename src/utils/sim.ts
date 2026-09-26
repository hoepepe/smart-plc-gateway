import { Cycle, MachineConfig, MachineRuntime, MachineState, SpanKind } from '../types';
import { MACHINES } from '../data/machines';
import { mahalanobis, proc, threshold } from './detector';

/**
 * Mô phỏng vận hành máy — thay thế cho dữ liệu đọc từ PLC khi chưa có PLC thật.
 *
 * Trạng thái máy và thời gian mô phỏng ở đây là giả lập. Còn đường cong mỗi chu kỳ
 * lấy từ bộ mẫu trong TẬP KIỂM TRA mà ml/cycles.py đã dùng để đánh giá mô hình, và
 * bộ phát hiện chạy đúng tham số đã huấn luyện.
 *
 * Khi nối gateway thật qua MQTT, các hàm applyState / applyCycle nhận dữ liệu thật
 * thay cho vòng lặp mô phỏng.
 */

export const SHIFT_START_HOUR = 6;       // ca bắt đầu 06:00
export const PREFILL_SECONDS = 4 * 3600; // khởi tạo sẵn 4 giờ lịch sử để OEE có số ngay
const ERROR_PROB_PER_CYCLE = 0.002;
const ORGANIC_FAULT_PROB = 0.012;

let cycleSeq = 1;
let rngState = 20260921;
function rnd(): number {
  // bộ sinh số ngẫu nhiên có hạt giống — mỗi lần tải trang ra cùng một lịch sử
  rngState = (rngState * 1664525 + 1013904223) % 4294967296;
  return rngState / 4294967296;
}
const between = (a: number, b: number) => a + (b - a) * rnd();
const pick = <T,>(arr: T[]) => arr[Math.floor(rnd() * arr.length)];

const kindOf = (s: MachineState): SpanKind =>
  s === 'AUTO' || s === 'WORKING' || s === 'DONE' ? 'RUN' : (s as SpanKind);

const emptyTimeIn = (): Record<MachineState, number> =>
  ({ STOPPED: 0, READY: 0, AUTO: 0, WORKING: 0, DONE: 0, ERROR: 0 });

interface Sched { until: number }
const schedule: Record<string, Sched> = {};

export function initRuntime(): Record<string, MachineRuntime> {
  const rt: Record<string, MachineRuntime> = {};
  for (const m of MACHINES) {
    rt[m.id] = {
      state: 'AUTO', stateSince: 0, timeline: [{ kind: 'RUN', start: 0, end: 0 }],
      timeIn: emptyTimeIn(), errorStats: {}, cycles: [],
      totalCycles: 0, anomalousCycles: 0, lastRead: 0,
    };
    schedule[m.id] = { until: between(0.4, 1.2) };
  }
  return rt;
}

function setState(r: MachineRuntime, s: MachineState, now: number, code?: string) {
  r.state = s;
  r.stateSince = now;
  r.errorCode = s === 'ERROR' ? code : undefined;
  const k = kindOf(s);
  const last = r.timeline[r.timeline.length - 1];
  if (last && last.kind === k && last.errorCode === (s === 'ERROR' ? code : undefined)) return;
  r.timeline.push({ kind: k, start: now, end: now, errorCode: s === 'ERROR' ? code : undefined });
  if (r.timeline.length > 600) r.timeline.splice(0, r.timeline.length - 600);
}

export function makeCycle(m: MachineConfig, now: number, fault?: string): Cycle {
  const p = proc(m.process);
  let sample, injected: string | undefined;
  if (fault && p.samples.faults[fault]) {
    sample = pick(p.samples.faults[fault]);
    injected = fault;
  } else if (!fault && rnd() < ORGANIC_FAULT_PROB) {
    const code = pick(Object.keys(p.samples.faults));
    sample = pick(p.samples.faults[code]);
  } else {
    sample = pick(p.samples.normal);
  }
  const score = mahalanobis(sample.f, m.process);
  return {
    id: cycleSeq++, machineId: m.id, at: now, y: sample.y, f: sample.f,
    score, anomalous: score > threshold(m.process), injected,
  };
}

export function applyCycle(r: MachineRuntime, c: Cycle, keepCurves: boolean) {
  r.totalCycles += 1;
  if (c.anomalous) r.anomalousCycles += 1;
  if (keepCurves) {
    r.cycles.push(c);
    if (r.cycles.length > 40) r.cycles.shift();
  } else {
    // khi dựng lịch sử chỉ giữ lại vài chu kỳ cuối để tiết kiệm bộ nhớ
    r.cycles.push(c);
    if (r.cycles.length > 12) r.cycles.shift();
  }
}

/** Cộng dồn thời gian ở trạng thái hiện tại từ `from` đến `to`. */
function accrue(r: MachineRuntime, from: number, to: number) {
  const dt = to - from;
  if (dt <= 0) return;
  r.timeIn[r.state] += dt;
  if (r.state === 'ERROR' && r.errorCode) {
    r.errorStats[r.errorCode] = r.errorStats[r.errorCode] || { count: 0, seconds: 0 };
    r.errorStats[r.errorCode].seconds += dt;
  }
  const tl = r.timeline[r.timeline.length - 1];
  if (tl) tl.end = to;
}

function raiseError(m: MachineConfig, r: MachineRuntime, at: number, sc: Sched, dur: [number, number]) {
  const code = pick(m.errorCodes).code;
  setState(r, 'ERROR', at, code);
  r.errorStats[code] = r.errorStats[code] || { count: 0, seconds: 0 };
  r.errorStats[code].count += 1;
  sc.until = at + between(dur[0], dur[1]);
}

/** Chuyển sang trạng thái kế tiếp tại đúng thời điểm `at`. */
function transition(m: MachineConfig, r: MachineRuntime, at: number, sc: Sched, keepCurves: boolean) {
  switch (r.state) {
    case 'AUTO':
      if (rnd() < ERROR_PROB_PER_CYCLE) {
        raiseError(m, r, at, sc, [45, 240]);
      } else {
        setState(r, 'WORKING', at);
        sc.until = at + m.idealCycleSec * between(0.92, 0.98);
      }
      break;
    case 'WORKING': {
      const c = makeCycle(m, at, r.pendingFault);
      r.pendingFault = undefined;
      applyCycle(r, c, keepCurves);
      setState(r, 'DONE', at);
      sc.until = at + between(0.1, 0.2);
      break;
    }
    case 'DONE':
      setState(r, 'AUTO', at);
      sc.until = at + between(0.1, 0.3);
      break;
    case 'ERROR':
      setState(r, 'STOPPED', at);
      sc.until = at + between(10, 40);
      break;
    case 'STOPPED':
      setState(r, 'READY', at);
      sc.until = at + between(8, 20);
      break;
    case 'READY':
      setState(r, 'AUTO', at);
      sc.until = at + between(0.2, 0.6);
      break;
  }
}

/**
 * Tiến mô phỏng từ t0 đến t1 cho một máy.
 * Xử lý từng sự kiện tại đúng thời điểm của nó, không làm tròn theo bước —
 * nếu làm tròn, mỗi trạng thái ngắn bị kéo dài giả tạo và hiệu suất OEE bị sai.
 */
function stepMachine(m: MachineConfig, r: MachineRuntime, t0: number, t1: number, keepCurves: boolean) {
  const sc = schedule[m.id];
  let cursor = t0;

  if (r.pendingStop && r.state !== 'ERROR') {
    r.pendingStop = false;
    raiseError(m, r, cursor, sc, [40, 90]);
  }

  let guard = 0;
  while (sc.until <= t1 && guard++ < 10000) {
    accrue(r, cursor, sc.until);
    cursor = sc.until;
    transition(m, r, cursor, sc, keepCurves);
  }
  accrue(r, cursor, t1);
  r.lastRead = t1;
}

export function step(rt: Record<string, MachineRuntime>, now: number, dt: number, keepCurves = true) {
  for (const m of MACHINES) stepMachine(m, rt[m.id], now - dt, now, keepCurves);
}

/** Dựng sẵn lịch sử vài giờ để OEE và biểu đồ có dữ liệu ngay khi mở trang. */
export function prefill(rt: Record<string, MachineRuntime>): number {
  const dt = 0.5;
  let t = 0;
  while (t < PREFILL_SECONDS) {
    t += dt;
    step(rt, t, dt, false);
  }
  return t;
}

export function clock(simSeconds: number): string {
  const total = SHIFT_START_HOUR * 3600 + simSeconds;
  const h = Math.floor(total / 3600) % 24;
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/* ───────────── Dữ liệu thật từ gateway qua MQTT ───────────── */

/** Ghi nhận trạng thái máy do gateway báo lên. */
export function applyExternalState(
  r: MachineRuntime, state: MachineState, now: number, errorCode?: string,
) {
  accrue(r, r.lastRead || now, now);
  if (state === 'ERROR' && errorCode) {
    r.errorStats[errorCode] = r.errorStats[errorCode] || { count: 0, seconds: 0 };
    if (r.state !== 'ERROR' || r.errorCode !== errorCode) r.errorStats[errorCode].count += 1;
  }
  setState(r, state, now, errorCode);
  r.lastRead = now;
}

/** Ghi nhận một chu kỳ gia công do gateway gửi lên, chấm điểm bằng đúng mô hình đã huấn luyện. */
export function applyExternalCycle(
  m: MachineConfig, r: MachineRuntime, now: number, y: number[], f: number[],
): Cycle {
  const score = mahalanobis(f, m.process);
  const c: Cycle = {
    id: cycleSeq++, machineId: m.id, at: now, y, f,
    score, anomalous: score > threshold(m.process),
  };
  applyCycle(r, c, true);
  return c;
}

/** Tiến thời gian cho mọi máy mà không sinh sự kiện mới — dùng khi dữ liệu đến từ gateway thật. */
export function accrueAll(rt: Record<string, MachineRuntime>, now: number) {
  for (const m of MACHINES) {
    const r = rt[m.id];
    accrue(r, r.lastRead || now, now);
    r.lastRead = now;
  }
}
