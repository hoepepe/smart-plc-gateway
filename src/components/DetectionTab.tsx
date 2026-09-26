import React, { useState } from 'react';
import { ProcessType } from '../types';
import { DATA, proc, threshold, mahalanobis } from '../utils/detector';
import { pct } from '../utils/oee';
import { Card, CycleChart, Bar, Note } from './charts';

const PROCS: ProcessType[] = ['PRESS_FORCE', 'TORQUE', 'AIR_PRESSURE'];

// Giả thuyết cho các dạng lỗi mô hình còn bắt kém — ghi rõ là giả thuyết, chưa kiểm chứng.
const WEAK_NOTE: Record<string, string> = {
  VALVE_STICK:
    'Van kẹt tạo dao động giật cục rất ngắn. Các đặc trưng hiện tại tính trên cả chu kỳ nên dao động này bị làm mượt đi. Giả thuyết: thêm đặc trưng bắt biến thiên nhanh (ví dụ năng lượng dải tần cao) sẽ cải thiện.',
  LOW_SUPPLY:
    'Nguồn khí yếu chỉ hạ mức áp nền, còn hình dạng chu kỳ gần như giữ nguyên, nên một phần chu kỳ vẫn rơi vào vùng bình thường. Isolation Forest bắt tốt hơn ở dạng này. Giả thuyết: thêm một luật ngưỡng áp nền tuyệt đối sẽ bắt đủ, giống cách luật kiểm tra dải bắt lỗi đấu ngược cực.',
};

export function DetectionTab() {
  const [p, setP] = useState<ProcessType>('PRESS_FORCE');
  const model = proc(p);
  const met = model.metrics;
  const avgM = met.faults.reduce((a, f) => a + f.detect_mahalanobis, 0) / met.faults.length;
  const avgI = met.faults.reduce((a, f) => a + f.detect_isoforest, 0) / met.faults.length;
  const weak = met.faults.filter((f) => f.detect_mahalanobis < 0.8);

  // Đếm trên cả ba đại lượng để nói đúng mức độ, không khái quát quá
  const all = PROCS.flatMap((x) => proc(x).metrics.faults);
  const better = all.filter((f) => f.detect_mahalanobis > f.detect_isoforest + 0.01).length;
  const worse = all.filter((f) => f.detect_isoforest > f.detect_mahalanobis + 0.01).length;
  const tie = all.length - better - worse;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Chọn đại lượng">
        {PROCS.map((x) => (
          <button key={x} role="tab" aria-selected={p === x} onClick={() => setP(x)}
            className={`px-4 py-2 rounded-md text-sm border transition-colors
              focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 ${
              p === x ? 'bg-slate-900 text-white border-slate-900'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'}`}>
            {proc(x).vi}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { l: 'Chu kỳ bình thường để học', v: met.n_train.toLocaleString('vi-VN') },
          { l: 'Chu kỳ để kiểm tra', v: met.n_test_normal.toLocaleString('vi-VN') },
          { l: 'Bắt được lỗi, trung bình', v: pct(avgM) },
          { l: 'Báo động giả', v: pct(met.false_alarm_mahalanobis) },
        ].map((k) => (
          <div key={k.l} className="bg-white border border-slate-200 rounded-lg px-4 py-3.5">
            <div className="text-xs text-slate-500">{k.l}</div>
            <div className="font-mono tabular-nums text-xl font-semibold text-slate-900 mt-1">{k.v}</div>
          </div>
        ))}
      </div>

      <Card title={`Từng dạng lỗi của ${model.vi.toLowerCase()}`}
        sub="Tỷ lệ chu kỳ lỗi bị gắn cờ, đo trên các ca làm việc mô hình chưa từng thấy. So sánh hai mô hình cùng học trên đúng một bộ dữ liệu.">
        <div className="overflow-x-auto -mx-5">
          <table className="w-full text-sm min-w-[620px]">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                <th className="font-medium px-5 pb-2.5">Dạng lỗi</th>
                <th className="font-medium pb-2.5 w-[26%]">Mahalanobis (đang dùng)</th>
                <th className="font-medium pb-2.5 pr-5 w-[26%]">Isolation Forest</th>
              </tr>
            </thead>
            <tbody>
              {met.faults.map((f) => (
                <tr key={f.code} className="border-b border-slate-100 last:border-0">
                  <td className="px-5 py-3 text-slate-800">{f.vi}</td>
                  <td className="py-3 pr-6">
                    <div className={`font-mono tabular-nums text-xs mb-1 ${f.detect_mahalanobis < 0.8 ? 'text-amber-700 font-semibold' : 'text-slate-700'}`}>
                      {pct(f.detect_mahalanobis, 0)}
                    </div>
                    <Bar value={f.detect_mahalanobis} color={f.detect_mahalanobis < 0.8 ? '#d97706' : '#475569'} height={6} />
                  </td>
                  <td className="py-3 pr-5">
                    <div className="font-mono tabular-nums text-xs mb-1 text-slate-500">{pct(f.detect_isoforest, 0)}</div>
                    <Bar value={f.detect_isoforest} color="#cbd5e1" height={6} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 text-xs">
                <td className="px-5 py-2.5 text-slate-600">Báo động giả trên chu kỳ bình thường</td>
                <td className="py-2.5 font-mono tabular-nums text-slate-800">{pct(met.false_alarm_mahalanobis)}</td>
                <td className="py-2.5 pr-5 font-mono tabular-nums text-slate-500">{pct(met.false_alarm_isoforest)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>

      <Card title="Chu kỳ lỗi trông khác chu kỳ bình thường thế nào"
        sub="Vùng xám nhạt là dải 5–95% của chu kỳ bình thường. Mỗi hình là một chu kỳ lỗi thật trong tập kiểm tra.">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {met.faults.map((f) => {
            const s = model.samples.faults[f.code]?.[0];
            if (!s) return null;
            const score = mahalanobis(s.f, p);
            const flagged = score > threshold(p);
            return (
              <figure key={f.code}>
                <CycleChart y={s.y} process={p} anomalous={flagged} unit={model.unit} height={230} width={400} />
                <figcaption className="mt-1.5 text-xs">
                  <div className="text-slate-800">{f.vi}</div>
                  <div className="text-slate-500 mt-0.5 font-mono tabular-nums">
                    điểm {score.toFixed(1)} / ngưỡng {threshold(p).toFixed(1)} — {flagged ? 'bị gắn cờ' : 'lọt qua'}
                  </div>
                </figcaption>
              </figure>
            );
          })}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="Vì sao chọn Mahalanobis">
          <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
            <p>
              Trên {all.length} dạng lỗi của cả ba đại lượng, Mahalanobis bắt tốt hơn Isolation Forest ở {better} dạng,
              ngang nhau ở {tie} dạng, và kém hơn ở {worse} dạng.
              {avgM >= avgI
                ? ` Với ${model.vi.toLowerCase()}, trung bình ${pct(avgM, 0)} so với ${pct(avgI, 0)}.`
                : ` Riêng ${model.vi.toLowerCase()} thì Isolation Forest nhỉnh hơn (${pct(avgI, 0)} so với ${pct(avgM, 0)}) — xem mục chỗ còn yếu.`}
            </p>
            <p>
              Nó cũng nhẹ: chỉ cần một vector trung bình và một ma trận 9×9, chạy được trên ESP32 mà không cần thư viện học máy.
            </p>
            <p>
              Và nó giải thích được: với mỗi chu kỳ bị gắn cờ, giao diện chỉ ra đặc trưng nào lệch bao nhiêu độ lệch chuẩn so
              với bình thường, nên kỹ sư biết vì sao máy bị cảnh báo.
            </p>
          </div>
        </Card>

        <Card title="Chỗ mô hình còn yếu">
          {weak.length === 0 ? (
            <p className="text-sm text-slate-700 leading-relaxed">
              Với {model.vi.toLowerCase()}, mọi dạng lỗi đều bị bắt từ 80% trở lên. Nhưng đây là dữ liệu mô phỏng —
              tín hiệu thật sẽ nhiễu hơn và con số sẽ giảm.
            </p>
          ) : (
            <div className="space-y-3">
              {weak.map((f) => (
                <div key={f.code}>
                  <Note tone="amber">
                    <strong>{f.vi}: bắt {pct(f.detect_mahalanobis, 0)}.</strong>{' '}
                    {WEAK_NOTE[f.code] ?? 'Chưa rõ nguyên nhân, cần phân tích thêm.'}
                  </Note>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="Cách huấn luyện và kiểm tra">
        <ul className="space-y-2 text-sm text-slate-700 leading-relaxed">
          <li>{DATA.policy.split}.</li>
          <li>{DATA.policy.training}.</li>
          <li>{DATA.policy.threshold}.</li>
        </ul>
        <div className="mt-4">
          <Note tone="sky">
            <strong>Dữ liệu mô phỏng.</strong> Theo mentor DENSO, đội có thể tự tạo dữ liệu từ PLC và xuất ra CSV.
            Khi có PLC thật, chạy lại <span className="font-mono">ml/cycles.py</span> trên dữ liệu đó — mọi con số ở màn hình này sẽ cập nhật theo.
          </Note>
        </div>
      </Card>
    </div>
  );
}
