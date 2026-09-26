import React, { useState } from 'react';
import { Lock, Cpu, Cable, AlertOctagon, Zap, PauseCircle } from 'lucide-react';
import { MachineRuntime } from '../types';
import { MACHINES, STATE_META, FEATURE_VI } from '../data/machines';
import { explain, proc, threshold } from '../utils/detector';
import { computeOee, pct } from '../utils/oee';
import { clock } from '../utils/sim';
import { Card, CycleChart, Spark, Timeline, TimelineLegend, Bar, Note } from './charts';

interface Props {
  rt: Record<string, MachineRuntime>;
  now: number;
  selected: string;
  onSelect: (id: string) => void;
  onInjectFault: (machineId: string, fault: string) => void;
  onForceStop: (machineId: string) => void;
  live?: boolean;   // đang nhận dữ liệu thật từ gateway — nút mô phỏng không còn tác dụng
}

export function MonitorTab({ rt, now, selected, onSelect, onInjectFault, onForceStop, live = false }: Props) {
  const m = MACHINES.find((x) => x.id === selected)!;
  const r = rt[m.id];
  const p = proc(m.process);
  const last = r.cycles[r.cycles.length - 1];
  const thr = threshold(m.process);
  const meta = STATE_META[r.state];
  const [fault, setFault] = useState<string>(Object.keys(p.samples.faults)[0]);
  const faults = p.metrics.faults;

  return (
    <div className="space-y-5">
      {/* ─── Bốn máy ─── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {MACHINES.map((mc) => {
          const rr = rt[mc.id];
          const st = STATE_META[rr.state];
          const o = computeOee(mc, rr);
          const on = mc.id === selected;
          const lastC = rr.cycles[rr.cycles.length - 1];
          return (
            <button key={mc.id} onClick={() => onSelect(mc.id)}
              className={`text-left bg-white border rounded-lg p-4 transition-all shadow-xs ${
                on ? 'border-slate-900 ring-2 ring-slate-900/10' : 'border-slate-200 hover:border-slate-300'}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[11px] font-mono text-slate-400">{mc.id} · {mc.line}</div>
                  <div className="text-sm font-semibold text-slate-900 mt-0.5">{mc.name}</div>
                </div>
                <span className={`flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full ${st.bg} ${st.color}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${rr.state === 'ERROR' ? 'animate-pulse' : ''}`} />
                  {st.vi}
                </span>
              </div>
              <div className="flex items-center gap-1.5 mt-2.5 text-[11px] text-slate-500">
                <Cpu size={12} className="text-slate-400" />
                <span>{mc.plc.vendor} {mc.plc.model}</span>
              </div>
              <div className="mt-3 h-7">
                {lastC && <Spark y={lastC.y} anomalous={lastC.anomalous} />}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2 pt-2.5 border-t border-slate-100">
                <div>
                  <div className="text-[10px] text-slate-400">OEE</div>
                  <div className="text-sm font-semibold font-mono text-slate-800">{pct(o.oee)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Chu kỳ</div>
                  <div className="text-sm font-semibold font-mono text-slate-800">{rr.totalCycles.toLocaleString('vi-VN')}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Bất thường</div>
                  <div className={`text-sm font-semibold font-mono ${rr.anomalousCycles ? 'text-rose-600' : 'text-slate-800'}`}>
                    {rr.anomalousCycles}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* ─── Máy đang chọn ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2"
          title={<span>{m.name} — {p.vi} từng chu kỳ</span>}
          sub={`Đường đậm là chu kỳ vừa đọc từ PLC. Vùng xám nhạt là dải 90% chu kỳ bình thường (${p.metrics.n_test_normal} chu kỳ từ tập kiểm tra).`}
          right={
            last && (
              <div className="text-right shrink-0">
                <div className="text-[10px] text-slate-400">Chu kỳ #{last.id}</div>
                <div className="text-xs font-mono text-slate-600">{clock(last.at)}</div>
              </div>
            )
          }>
          {last ? (
            <CycleChart y={last.y} process={m.process} anomalous={last.anomalous} unit={p.unit} />
          ) : (
            <div className="h-60 grid place-items-center text-sm text-slate-400">Đang chờ chu kỳ đầu tiên…</div>
          )}

          <div className="mt-4">
            <div className="text-[11px] font-medium text-slate-500 mb-2">24 chu kỳ gần nhất — đỏ là bất thường</div>
            <div className="grid grid-cols-8 sm:grid-cols-12 gap-1.5">
              {r.cycles.slice(-24).map((c) => (
                <div key={c.id} title={`#${c.id} · điểm ${c.score.toFixed(2)}`}
                  className={`rounded border px-1 ${c.anomalous ? 'border-rose-300 bg-rose-50' : 'border-slate-200 bg-slate-50'}`}>
                  <Spark y={c.y} anomalous={c.anomalous} />
                </div>
              ))}
            </div>
          </div>
        </Card>

        <div className="space-y-5">
          <Card title="Kết luận của bộ phát hiện" sub="Khoảng cách từ chu kỳ này tới vùng chu kỳ bình thường">
            {last ? (
              <>
                <div className={`rounded-md border px-4 py-3 ${last.anomalous ? 'bg-rose-50 border-rose-200' : 'bg-slate-50 border-slate-200'}`}>
                  <div className={`text-xs font-semibold uppercase tracking-wide ${last.anomalous ? 'text-rose-700' : 'text-slate-600'}`}>
                    {last.anomalous ? 'Chu kỳ bất thường — nghi lỗi' : 'Chu kỳ bình thường'}
                  </div>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl font-semibold font-mono text-slate-900">{last.score.toFixed(2)}</span>
                    <span className="text-xs text-slate-500">ngưỡng {thr.toFixed(2)}</span>
                  </div>
                  <div className="mt-2">
                    <Bar value={Math.min(1, last.score / (thr * 2.5))} color={last.anomalous ? '#e11d48' : '#475569'} height={6} />
                  </div>
                  {last.injected && (
                    <div className="text-[11px] text-slate-500 mt-2">
                      Chu kỳ chèn thử: {faults.find((f) => f.code === last.injected)?.vi}
                    </div>
                  )}
                </div>

                <div className="mt-4">
                  <div className="text-[11px] font-medium text-slate-500 mb-2">Đặc trưng lệch nhiều nhất so với bình thường</div>
                  <div className="space-y-1.5">
                    {explain(last.f, m.process).map((e) => (
                      <div key={e.name} className="flex items-center justify-between text-xs">
                        <span className="text-slate-600">{FEATURE_VI[e.name] || e.name}</span>
                        <span className={`font-mono ${Math.abs(e.z) > 3 ? 'text-rose-600 font-semibold' : 'text-slate-500'}`}>
                          {e.z >= 0 ? '+' : ''}{e.z.toFixed(1)}σ
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                    σ = số độ lệch chuẩn so với trung bình chu kỳ bình thường. Trên 3σ là lệch đáng kể.
                  </p>
                </div>
              </>
            ) : <div className="text-sm text-slate-400">Chưa có dữ liệu</div>}
          </Card>

          <Card title="Thử nghiệm khi demo" sub="Giám khảo tự chọn và bấm — hệ thống không biết trước">
            <label className="text-[11px] text-slate-500">Chèn một chu kỳ lỗi vào lần gia công kế tiếp</label>
            <select value={fault} onChange={(e) => setFault(e.target.value)}
              className="mt-1.5 w-full text-sm border border-slate-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:border-slate-900">
              {faults.map((f) => <option key={f.code} value={f.code}>{f.vi}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-2 mt-3">
              <button onClick={() => onInjectFault(m.id, fault)} disabled={live}
                className="flex items-center justify-center gap-1.5 text-xs font-medium bg-slate-900 text-white rounded-md px-3 py-2 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed">
                <Zap size={13} /> Chèn chu kỳ lỗi
              </button>
              <button onClick={() => onForceStop(m.id)} disabled={live}
                className="flex items-center justify-center gap-1.5 text-xs font-medium border border-slate-300 text-slate-700 rounded-md px-3 py-2 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed">
                <PauseCircle size={13} /> Giả lập báo lỗi
              </button>
            </div>
            {live && (
              <p className="text-xs text-slate-500 mt-2.5 leading-relaxed">
                Đang nhận dữ liệu thật từ gateway nên không chèn lỗi giả được. Để thử, tạo lỗi ngay trên máy hoặc tắt broker để về chế độ mô phỏng.
              </p>
            )}
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2" title="Dòng thời gian trạng thái máy — cả ca"
          sub={`Từ ${clock(0)} đến ${clock(now)}. Trước đây dữ liệu này chỉ có khi rút thẻ nhớ PLC.`}>
          <Timeline spans={r.timeline} t0={0} t1={now} height={26} />
          <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-1">
            <span>{clock(0)}</span><span>{clock(now / 2)}</span><span>{clock(now)}</span>
          </div>
          <div className="mt-3"><TimelineLegend /></div>
          {r.state === 'ERROR' && r.errorCode && (
            <div className="mt-4">
              <Note tone="rose">
                <span className="flex items-center gap-1.5 font-semibold">
                  <AlertOctagon size={13} /> Máy đang báo lỗi {r.errorCode}:
                  {' '}{m.errorCodes.find((e) => e.code === r.errorCode)?.vi}
                </span>
                <span className="block mt-1 opacity-80">
                  Phát hiện lúc {clock(r.stateSince)} — ngay khi PLC chuyển trạng thái, không phải chờ ai đi rút thẻ nhớ.
                </span>
              </Note>
            </div>
          )}
        </Card>

        <Card title="Đọc từ PLC" sub="Chỉ gửi lệnh đọc — không bao giờ ghi vào PLC"
          right={<span className="flex items-center gap-1 text-[10px] font-medium text-slate-700 bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5"><Lock size={10} />Chỉ đọc</span>}>
          <dl className="text-xs space-y-2">
            <div className="flex justify-between gap-3"><dt className="text-slate-500">PLC</dt><dd className="text-slate-800 text-right">{m.plc.vendor} {m.plc.model}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Cổng</dt><dd className="text-slate-800 text-right">{m.plc.port}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Giao thức</dt><dd className="text-slate-800 text-right">{m.plc.protocol}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Lệnh dùng</dt><dd className="font-mono text-slate-800 text-right">{m.plc.readCommand}</dd></div>
            {m.plc.ip && <div className="flex justify-between gap-3"><dt className="text-slate-500">Địa chỉ</dt><dd className="font-mono text-slate-800">{m.plc.ip}</dd></div>}
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Trạng thái</dt><dd className={`font-medium ${meta.color}`}>{meta.vi}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Lần đọc cuối</dt><dd className="font-mono text-slate-800">{clock(r.lastRead)}</dd></div>
          </dl>
          <div className="mt-4 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500 mb-2"><Cable size={12} />Thanh ghi đang đọc</div>
            <table className="w-full text-xs">
              <tbody>
                {m.registers.map((g) => (
                  <tr key={g.address} className="border-b border-slate-50 last:border-0">
                    <td className="py-1 font-mono text-slate-500 pr-3">{g.address}</td>
                    <td className="py-1 text-slate-700">{g.name}{g.unit ? ` (${g.unit})` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[10px] text-slate-400 mt-2 leading-relaxed">
              Địa chỉ là ví dụ — thay bằng danh sách tín hiệu DENSO cung cấp. Thêm máy chỉ cần sửa file cấu hình.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
