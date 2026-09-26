import React from 'react';
import { ProcessType, StateSpan } from '../types';
import { envelope, resample } from '../utils/detector';
import { STATE_HEX } from '../data/machines';

/* ─────────── Đường cong một chu kỳ, vẽ chồng lên dải bình thường ─────────── */
export function CycleChart({
  y, process, anomalous, unit, height = 250, width = 720,
}: { y: number[]; process: ProcessType; anomalous: boolean; unit: string; height?: number; width?: number }) {
  const N = 110;
  const env = envelope(process, N);
  const cur = resample(y, N);
  const W = width, H = height, pl = 46, pr = 14, pt = 14, pb = 30;
  const all = [...env.lo, ...env.hi, ...cur];
  let mn = Math.min(...all), mx = Math.max(...all);
  const pad = (mx - mn) * 0.08 || 1;
  mn -= pad; mx += pad;
  const X = (i: number) => pl + ((W - pl - pr) * i) / (N - 1);
  const Y = (v: number) => pt + (H - pt - pb) * (1 - (v - mn) / (mx - mn));
  const line = (arr: number[]) => arr.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
  const band = `${line(env.hi)} ${env.lo.map((v, i) => `L${X(N - 1 - i).toFixed(1)},${Y(env.lo[N - 1 - i]).toFixed(1)}`).join(' ')} Z`;
  const color = anomalous ? '#e11d48' : '#1e293b';
  const ticks = [0, 1, 2, 3, 4].map((k) => mn + ((mx - mn) * k) / 4);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
      aria-label="Đường cong chu kỳ gia công so với dải bình thường">
      {ticks.map((v, k) => (
        <g key={k}>
          <line x1={pl} x2={W - pr} y1={Y(v)} y2={Y(v)} stroke="#e2e8f0" strokeWidth="1" />
          <text x={pl - 6} y={Y(v) + 3.5} textAnchor="end" fontSize="10" fill="#94a3b8"
            fontFamily="JetBrains Mono, monospace">{v.toFixed(v < 10 ? 1 : 0)}</text>
        </g>
      ))}
      <path d={band} fill="#64748b" opacity="0.13" />
      <path d={line(env.mid)} fill="none" stroke="#64748b" strokeWidth="1.2" strokeDasharray="4 4" opacity="0.7" />
      <path d={line(cur)} fill="none" stroke={color} strokeWidth="2.4" strokeLinejoin="round" />
      <text x={pl} y={H - 8} fontSize="10" fill="#94a3b8">bắt đầu chu kỳ</text>
      <text x={W - pr} y={H - 8} fontSize="10" fill="#94a3b8" textAnchor="end">kết thúc</text>
      <text x={pl + 4} y={pt + 11} fontSize="10" fill="#64748b" fontFamily="JetBrains Mono, monospace">{unit}</text>
    </svg>
  );
}

/* ─────────── Đường cong thu nhỏ cho dải chu kỳ gần đây ─────────── */
export function Spark({ y, anomalous }: { y: number[]; anomalous: boolean }) {
  const W = 64, H = 28;
  const mn = Math.min(...y), mx = Math.max(...y), r = mx - mn || 1;
  const d = y.map((v, i) => `${i ? 'L' : 'M'}${((W * i) / (y.length - 1)).toFixed(1)},${(H - 2 - ((H - 4) * (v - mn)) / r).toFixed(1)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-7">
      <path d={d} fill="none" stroke={anomalous ? '#e11d48' : '#64748b'} strokeWidth="1.4" />
    </svg>
  );
}

/* ─────────── Dòng thời gian trạng thái máy ─────────── */
const KIND_HEX: Record<StateSpan['kind'], string> = {
  RUN: STATE_HEX.WORKING, READY: STATE_HEX.READY, STOPPED: STATE_HEX.STOPPED, ERROR: STATE_HEX.ERROR,
};
export const KIND_VI: Record<StateSpan['kind'], string> = {
  RUN: 'Đang chạy', READY: 'Chuẩn bị vận hành', STOPPED: 'Dừng', ERROR: 'Báo lỗi',
};

export function Timeline({ spans, t0, t1, height = 22 }: { spans: StateSpan[]; t0: number; t1: number; height?: number }) {
  const W = 1000;
  const X = (t: number) => ((Math.max(t0, Math.min(t1, t)) - t0) / (t1 - t0 || 1)) * W;
  return (
    <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" className="w-full rounded-sm overflow-hidden"
      style={{ height }}>
      <rect x="0" y="0" width={W} height={height} fill="#f1f5f9" />
      {spans.filter((s) => s.end > t0 && s.start < t1).map((s, i) => (
        <rect key={i} x={X(s.start)} y="0" width={Math.max(0.8, X(s.end) - X(s.start))} height={height}
          fill={KIND_HEX[s.kind]}>
          <title>{KIND_VI[s.kind]}{s.errorCode ? ` — ${s.errorCode}` : ''}</title>
        </rect>
      ))}
    </svg>
  );
}

export function TimelineLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
      {(Object.keys(KIND_HEX) as StateSpan['kind'][]).map((k) => (
        <span key={k} className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: KIND_HEX[k] }} />{KIND_VI[k]}
        </span>
      ))}
    </div>
  );
}

/* ─────────── Thanh phần trăm ─────────── */
export function Bar({ value, color = '#475569', height = 8 }: { value: number; color?: string; height?: number }) {
  return (
    <div className="w-full bg-slate-100 rounded-full overflow-hidden" style={{ height }}>
      <div className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} />
    </div>
  );
}

/* ─────────── Khung thẻ dùng chung ─────────── */
export function Card({ title, sub, right, children, className = '', pad = true }: {
  title?: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode;
  children: React.ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={`bg-white border border-slate-200 rounded-lg shadow-xs ${className}`}>
      {(title || right) && (
        <header className="px-5 pt-4 pb-3 border-b border-slate-100 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
            {sub && <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{sub}</p>}
          </div>
          {right}
        </header>
      )}
      <div className={pad ? 'p-5' : ''}>{children}</div>
    </section>
  );
}

export function Note({ tone = 'slate', children }: { tone?: 'slate' | 'amber' | 'sky' | 'rose' | 'emerald'; children: React.ReactNode }) {
  const t = {
    slate: 'bg-slate-50 border-slate-200 text-slate-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-900',
    sky: 'bg-sky-50 border-sky-200 text-sky-900',
    rose: 'bg-rose-50 border-rose-200 text-rose-900',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-900',
  }[tone];
  return <div className={`border rounded-md px-4 py-3 text-xs leading-relaxed ${t}`}>{children}</div>;
}
