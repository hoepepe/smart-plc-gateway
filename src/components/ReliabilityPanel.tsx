import React from 'react';
import { ShieldCheck, FlaskConical } from 'lucide-react';
import data from '../data/do_tin_cay.json';
import { Card, Note } from './charts';

/* Kết quả kiểm chứng độ chính xác (ml/danh_gia_do_tin_cay.py → src/data/do_tin_cay.json):
   AI của gateway so với giới hạn PLC (cách OK/NG hiện nay) và Isolation Forest, cùng dữ liệu, có khoảng tin cậy 95%. */

interface Rate { k: number; n: number; p: number; lo: number; hi: number }
interface Method { name: string; fa: Rate; det: Rate; faults: ({ name: string } & Rate)[] }
interface BoschRow { mode: string; name: string; auc: number; auc_lo: number; auc_hi: number; fa: Rate; det: Rate }
const D = data as unknown as { sim: { machine: string; methods: Method[] }[]; bosch: BoschRow[]; made: string };

const GATEWAY = 'AI của gateway';
const pc = (v: number) => `${(v * 100).toFixed(v > 0 && v < 0.1 ? 1 : 0)}%`;
const ci = (r: Rate) => `${pc(r.lo)}–${pc(r.hi)}`;

/** Thanh tỉ lệ bắt lỗi có vạch khoảng tin cậy. Tên phương pháp và con số luôn ghi bằng chữ — không dựa vào màu. */
function RateBar({ r, main }: { r: Rate; main: boolean }) {
  return (
    <div className="relative h-2.5 rounded-full bg-slate-100" title={`${pc(r.p)} (khoảng tin cậy 95%: ${ci(r)}) · ${r.k}/${r.n}`}>
      <div className={`absolute inset-y-0 left-0 rounded-full ${main ? 'bg-brand-600' : 'bg-slate-400'}`} style={{ width: `${r.p * 100}%` }} />
      <div className="absolute top-1/2 h-[2px] -translate-y-1/2 bg-slate-900/50" style={{ left: `${r.lo * 100}%`, width: `${Math.max(0.5, (r.hi - r.lo) * 100)}%` }} />
    </div>
  );
}

export function ReliabilityPanel() {
  const gw = D.bosch.filter((b) => b.name === GATEWAY);
  return (
    <div className="space-y-5">
      <Card title={<span className="inline-flex items-center gap-2"><ShieldCheck size={16} /> Kiểm chứng độ chính xác: AI của gateway so với cách đang làm</span>}
        sub={<>Cùng dữ liệu, ba cách phát hiện: <b>giới hạn PLC</b> (đỉnh và thời gian chu kỳ trong khoảng cho phép — cách OK/NG phổ biến hiện nay),
          <b> Isolation Forest</b> và <b>AI của gateway</b> (đúng bản chạy trong gateway). Lúc học không biết nhãn, có lẫn 2% chu kỳ lỗi;
          kiểm tra trên 10 ca chưa từng thấy. Vạch đen trên thanh là khoảng tin cậy 95%.</>}>
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
          {D.sim.map((m) => (
            <div key={m.machine} className="border border-slate-200 rounded-lg p-4">
              <div className="text-sm font-semibold text-slate-900">{m.machine}</div>
              <div className="text-[11px] text-slate-500 mb-3">Bắt lỗi · báo nhầm</div>
              <ul className="space-y-3">
                {[...m.methods].sort((a, b) => (a.name === GATEWAY ? -1 : b.name === GATEWAY ? 1 : 0)).map((x) => (
                  <li key={x.name}>
                    <div className="flex items-baseline justify-between gap-2 text-xs mb-1">
                      <span className={x.name === GATEWAY ? 'font-semibold text-slate-900' : 'text-slate-600'}>{x.name}</span>
                      <span className="tabular-nums text-slate-700"><b className="text-slate-900">{pc(x.det.p)}</b> · {pc(x.fa.p)}</span>
                    </div>
                    <RateBar r={x.det} main={x.name === GATEWAY} />
                  </li>
                ))}
              </ul>
              <details className="mt-3 text-[11px] text-slate-600">
                <summary className="cursor-pointer text-slate-500 hover:text-slate-800">Từng loại lỗi</summary>
                <table className="w-full mt-2">
                  <thead><tr className="text-slate-400"><th className="text-left font-normal">Lỗi</th>{m.methods.map((x) => <th key={x.name} className="text-right font-normal">{x.name === GATEWAY ? 'AI' : x.name.startsWith('Giới') ? 'PLC' : 'IF'}</th>)}</tr></thead>
                  <tbody>
                    {m.methods[0].faults.map((f, i) => (
                      <tr key={f.name}><td className="pr-2 py-0.5">{f.name}</td>
                        {m.methods.map((x) => <td key={x.name} className={`text-right tabular-nums ${x.name === GATEWAY ? 'font-semibold text-slate-900' : ''}`}>{pc(x.faults[i].p)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-slate-500 mt-3">Dữ liệu mô phỏng do nhóm tạo, nên đây là cận trên. Con số thật nằm ở bảng Bosch bên dưới.</p>
      </Card>

      <Card title="Dữ liệu thật: máy phay CNC trong nhà máy Bosch"
        sub="Rung động 3 máy phay 2018–2021, lỗi do kỹ sư Bosch gắn nhãn (công khai, CC BY 4.0). Học nửa đầu theo thời gian không biết nhãn, kiểm tra nửa sau.">
        <div className="overflow-x-auto -mx-5">
          <table className="w-full text-sm min-w-[620px]">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                <th className="px-5 py-2 font-medium">Cách chạy</th><th className="py-2 font-medium">Cách phát hiện</th>
                <th className="py-2 font-medium text-right">AUC</th><th className="py-2 font-medium text-right">Báo nhầm</th>
                <th className="px-5 py-2 font-medium text-right">Bắt lỗi</th>
              </tr>
            </thead>
            <tbody>
              {D.bosch.map((b, i) => (
                <tr key={i} className={`border-b border-slate-50 ${b.name === GATEWAY ? 'bg-brand-50/50' : ''}`}>
                  <td className="px-5 py-2 text-slate-600">{b.mode}</td>
                  <td className={`py-2 ${b.name === GATEWAY ? 'font-semibold' : ''}`}>{b.name}</td>
                  <td className="py-2 text-right tabular-nums">{b.auc.toFixed(2)} <span className="text-slate-400 text-xs">({b.auc_lo.toFixed(2)}–{b.auc_hi.toFixed(2)})</span></td>
                  <td className="py-2 text-right tabular-nums">{pc(b.fa.p)}</td>
                  <td className="px-5 py-2 text-right tabular-nums">{b.det.k}/{b.det.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {gw.length > 1 && (
          <Note tone="amber">
            Nói thật: trên dữ liệu thật, máy trôi theo nhiều năm làm báo nhầm cao ({pc(gw[0].fa.p)} nếu học một lần rồi để nguyên).
            Khi kỹ sư bấm "Báo nhầm" để AI học lại, AUC lên {gw[1].auc.toFixed(2)} — cao nhất trong ba cách — nhưng báo nhầm vẫn {pc(gw[1].fa.p)}.
            Chỉ có {gw[1].det.n} lần chạy lỗi nên tỉ lệ bắt lỗi còn rất rộng. Vì vậy kỹ sư duyệt mọi chuẩn mới và độ chính xác thực tế
            được đo ngay tại máy (tab Máy và AI tự học → Độ chính xác thực tế).
          </Note>
        )}
      </Card>

      <div className="grid md:grid-cols-2 gap-5">
        <Card title="Chuỗi thật: PLC Mitsubishi Q06UDEHCPU → gateway">
          <p className="text-sm text-slate-700 leading-relaxed">Phát lại chu kỳ siết bu-lông thật (PyScrew) vào thanh ghi PLC thật, gateway đọc lại qua MC protocol:
            <b> 20/20 kết luận trùng</b> với chấm trực tiếp trên dữ liệu gốc, đọc ổn định 99,8 mẫu/giây.
            Chứng minh đường PLC → gateway không làm sai kết luận của AI.</p>
        </Card>
        <Card title={<span className="inline-flex items-center gap-2"><FlaskConical size={16} /> Tại nhà máy kiểm chứng thế nào</span>}>
          <ul className="text-sm text-slate-700 space-y-1.5 list-disc pl-4">
            <li>Mẫu NG chuẩn đầu ca: AI phải bắt hết (nút "Kiểm tra mẫu NG").</li>
            <li>Công nhân xác nhận từng cảnh báo bằng nút trên dashboard hoặc nút OK/NG trên hộp gateway.</li>
            <li>Lỗi AI bỏ sót do trạm kiểm tra cuối chuyền phát hiện được ghi lại → tính tỉ lệ bắt lỗi thật.</li>
            <li>Chạy song song 2–4 tuần: gateway chỉ đọc, chỉ cảnh báo, không dừng chuyền.</li>
          </ul>
        </Card>
      </div>
      <p className="text-[11px] text-slate-500">Tạo ngày {D.made} bằng <code className="font-mono">python ml/danh_gia_do_tin_cay.py</code> · báo cáo đầy đủ: ml/reports/do_tin_cay.md</p>
    </div>
  );
}
