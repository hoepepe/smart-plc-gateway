import React, { useMemo, useState } from 'react';
import { MachineRuntime } from '../types';
import { MACHINES } from '../data/machines';
import { computeOee, pct, fmtDuration } from '../utils/oee';
import { clock } from '../utils/sim';
import { Card, Bar, Timeline, TimelineLegend, Note } from './charts';

interface Props {
  rt: Record<string, MachineRuntime>;
  now: number;
}

const ERROR_VI: Record<string, { vi: string; machine: string }> = Object.fromEntries(
  MACHINES.flatMap((m) => m.errorCodes.map((e) => [e.code, { vi: e.vi, machine: m.name }])),
);

const WINDOW_SEC = 4 * 3600;

export function OeeTab({ rt, now }: Props) {
  const rows = MACHINES.map((m) => ({ m, o: computeOee(m, rt[m.id]), r: rt[m.id] }));

  // Gộp thời gian kế hoạch để ra OEE toàn khu vực theo trọng số thời gian
  const plant = useMemo(() => {
    const planned = rows.reduce((a, x) => a + x.o.plannedSec, 0) || 1;
    const w = (k: 'availability' | 'performance' | 'quality' | 'oee') =>
      rows.reduce((a, x) => a + x.o[k] * x.o.plannedSec, 0) / planned;
    return {
      oee: w('oee'), availability: w('availability'), performance: w('performance'), quality: w('quality'),
      down: rows.reduce((a, x) => a + x.o.downSec, 0),
    };
  }, [rows]);

  const stops = useMemo(() => {
    const agg: { code: string; count: number; seconds: number }[] = [];
    for (const { r } of rows) {
      for (const [code, s] of Object.entries(r.errorStats)) {
        agg.push({ code, count: s.count, seconds: s.seconds });
      }
    }
    return agg.sort((a, b) => b.seconds - a.seconds);
  }, [rows]);
  const maxStop = stops[0]?.seconds || 1;
  const totalStop = stops.reduce((a, s) => a + s.seconds, 0) || 1;

  const [cardHours, setCardHours] = useState(24);

  const t0 = Math.max(0, now - WINDOW_SEC);

  return (
    <div className="space-y-5">
      <Card
        title="OEE theo từng máy"
        sub="OEE = độ sẵn sàng × hiệu suất × chất lượng, tính từ trạng thái máy và chu kỳ gia công đọc được từ PLC.">
        <div className="overflow-x-auto -mx-5">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                <th className="font-medium px-5 pb-2.5">Máy</th>
                <th className="font-medium pb-2.5 w-[18%]">Độ sẵn sàng</th>
                <th className="font-medium pb-2.5 w-[18%]">Hiệu suất</th>
                <th className="font-medium pb-2.5 w-[18%]">Chất lượng (ước tính)</th>
                <th className="font-medium pb-2.5 pr-5 text-right">OEE</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ m, o }) => (
                <tr key={m.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-5 py-3">
                    <div className="font-medium text-slate-900">{m.name}</div>
                    <div className="text-xs text-slate-500">{m.plc.vendor} {m.plc.model}</div>
                  </td>
                  {[o.availability, o.performance, o.quality].map((v, i) => (
                    <td key={i} className="py-3 pr-6">
                      <div className="font-mono tabular-nums text-xs text-slate-700 mb-1">{pct(v)}</div>
                      <Bar value={v} color="#475569" height={6} />
                    </td>
                  ))}
                  <td className="py-3 pr-5 text-right font-mono tabular-nums text-base font-semibold text-slate-900">
                    {pct(o.oee)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50">
                <td className="px-5 py-3 font-medium text-slate-700">Cả khu vực</td>
                {[plant.availability, plant.performance, plant.quality].map((v, i) => (
                  <td key={i} className="py-3 font-mono tabular-nums text-xs text-slate-700">{pct(v)}</td>
                ))}
                <td className="py-3 pr-5 text-right font-mono tabular-nums text-base font-semibold">{pct(plant.oee)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div className="mt-4">
          <Note tone="amber">
            <strong>Chất lượng ở đây là ước tính.</strong> Nó đếm chu kỳ bị mô hình gắn cờ bất thường, mà chu kỳ bất thường
            mới là nghi lỗi, chưa chắc là sản phẩm lỗi. Nối thêm kết quả kiểm tra QC sẽ cho con số chính xác.
            Độ sẵn sàng và hiệu suất tính trực tiếp từ trạng thái máy nên không có sai lệch này.
          </Note>
        </div>
      </Card>

      <Card
        title="Máy đã làm gì trong 4 giờ qua"
        sub={`Từ ${clock(t0)} đến ${clock(now)}. Mỗi đoạn là một trạng thái đọc từ cờ trạng thái trong PLC.`}
        right={<TimelineLegend />}>
        <div className="space-y-3">
          {rows.map(({ m, r, o }) => (
            <div key={m.id} className="grid grid-cols-[150px_1fr_90px] items-center gap-3">
              <div className="text-xs text-slate-700 truncate">{m.name}</div>
              <Timeline spans={r.timeline} t0={t0} t1={now} />
              <div className="text-xs text-right text-slate-500">
                dừng <span className="font-mono tabular-nums text-slate-700">{fmtDuration(o.downSec)}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <Card className="lg:col-span-3"
          title="Nguyên nhân dừng máy, xếp theo thời gian mất"
          sub="Mã lỗi đọc từ thanh ghi lỗi của PLC. Lỗi gây mất nhiều thời gian nhất nằm trên cùng — đó là chỗ nên sửa trước.">
          {stops.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">Chưa có lần dừng máy nào trong ca.</p>
          ) : (
            <div className="space-y-3">
              {stops.map((s) => {
                const info = ERROR_VI[s.code];
                return (
                  <div key={s.code}>
                    <div className="flex items-baseline justify-between gap-3 text-xs mb-1">
                      <span className="text-slate-800">
                        <span className="font-mono text-slate-400 mr-2">{s.code}</span>
                        {info?.vi ?? s.code}
                        <span className="text-slate-400"> — {info?.machine}</span>
                      </span>
                      <span className="font-mono tabular-nums text-slate-600 shrink-0">
                        {fmtDuration(s.seconds)} · {s.count} lần · {pct(s.seconds / totalStop, 0)}
                      </span>
                    </div>
                    <Bar value={s.seconds / maxStop} color="#e11d48" height={6} />
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2"
          title="Bao lâu thì biết máy dừng"
          sub="Hiện DENSO lấy dữ liệu PLC cũ bằng cách rút thẻ nhớ. So sánh độ trễ giữa hai cách.">
          <label className="block text-xs text-slate-600 mb-2" htmlFor="card-hours">
            Thẻ nhớ được rút mỗi <span className="font-mono tabular-nums font-semibold text-slate-900">{cardHours} giờ</span>
          </label>
          <input id="card-hours" type="range" min={1} max={72} value={cardHours}
            onChange={(e) => setCardHours(Number(e.target.value))}
            className="w-full accent-slate-800" />

          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="text-xs text-slate-500">Rút thẻ nhớ — độ trễ trung bình</dt>
              <dd className="font-mono tabular-nums text-xl font-semibold text-slate-900 mt-0.5">
                {fmtDuration((cardHours * 3600) / 2)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Gateway đọc liên tục</dt>
              <dd className="font-mono tabular-nums text-xl font-semibold text-slate-900 mt-0.5">khoảng 1 giây</dd>
            </div>
          </dl>

          <div className="mt-5">
            <Note tone="sky">
              Chu kỳ rút thẻ là <strong>giả định</strong>, kéo thanh trượt để thử. Số thật cần hỏi DENSO:
              thẻ nhớ được rút bao lâu một lần.
            </Note>
          </div>
        </Card>
      </div>
    </div>
  );
}
