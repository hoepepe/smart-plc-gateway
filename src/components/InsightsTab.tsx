import React, { useState, useMemo } from 'react';
import analysis from '../data/analysis.json';
import { VI_NAMES } from '../data/metrics';
import {
  Map, TrendingDown, ShieldAlert, Activity, Info, AlertTriangle, Wrench,
} from 'lucide-react';

interface Props {
  isDarkMode?: boolean;
}

const CLASS_COLOR: Record<string, string> = {
  TEMPERATURE: '#06b6d4',
  VIBRATION: '#8b5cf6',
  COUNTER: '#10b981',
  MOTOR_LOAD: '#f59e0b',
};

const FAULT_VI: Record<string, string> = {
  REVERSED_POLARITY: 'Đấu ngược cực',
  LOOSE_WIRE: 'Dây lỏng, tiếp xúc kém',
  SATURATED: 'Tín hiệu bão hòa',
  DEAD_CHANNEL: 'Kênh chết',
  WHITE_NOISE: 'Nhiễu trắng',
};

/* ═══════════════ Bản đồ không gian đặc trưng ═══════════════ */
function FeatureMap({ isDarkMode }: { isDarkMode: boolean }) {
  const fm = analysis.feature_map as any;
  const [showFaults, setShowFaults] = useState(false);
  const [hover, setHover] = useState<string | null>(null);

  const { W, H, sx, sy } = useMemo(() => {
    const all: number[][] = [
      ...Object.values(fm.classes).flat() as number[][],
      ...fm.ood as number[][],
      ...Object.values(fm.faults).flat() as number[][],
    ];
    const xs = all.map((p) => p[0]);
    const ys = all.map((p) => p[1]);
    const pad = 26;
    const W = 640;
    const H = 380;
    const x0 = Math.min(...xs);
    const x1 = Math.max(...xs);
    const y0 = Math.min(...ys);
    const y1 = Math.max(...ys);
    return {
      W, H,
      sx: (v: number) => pad + ((W - 2 * pad) * (v - x0)) / (x1 - x0 || 1),
      sy: (v: number) => H - pad - ((H - 2 * pad) * (v - y0)) / (y1 - y0 || 1),
    };
  }, [fm]);

  const grid = isDarkMode ? '#1e293b' : '#e2e8f0';
  const dim = (key: string) => hover !== null && hover !== key;

  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto rounded-sm"
        style={{ background: isDarkMode ? '#0b1220' : '#f8fafc' }}>
        {[0, 1, 2, 3, 4].map((g) => (
          <g key={g}>
            <line x1={26} y1={26 + ((H - 52) * g) / 4} x2={W - 26} y2={26 + ((H - 52) * g) / 4}
              stroke={grid} strokeWidth="1" strokeDasharray="3 4" />
            <line x1={26 + ((W - 52) * g) / 4} y1={26} x2={26 + ((W - 52) * g) / 4} y2={H - 26}
              stroke={grid} strokeWidth="1" strokeDasharray="3 4" />
          </g>
        ))}

        {/* 4 lớp đã huấn luyện */}
        {Object.entries(fm.classes as Record<string, number[][]>).map(([cls, pts]) => (
          <g key={cls} opacity={dim(cls) ? 0.15 : 1}>
            {pts.map((p, i) => (
              <circle key={i} cx={sx(p[0])} cy={sy(p[1])} r={4}
                fill={CLASS_COLOR[cls]} fillOpacity={0.55}
                stroke={CLASS_COLOR[cls]} strokeWidth="1" />
            ))}
          </g>
        ))}

        {/* lớp lạ chưa từng huấn luyện */}
        <g opacity={dim('ood') ? 0.15 : 1}>
          {(fm.ood as number[][]).map((p, i) => (
            <g key={i}>
              <circle cx={sx(p[0])} cy={sy(p[1])} r={5.5} fill="none"
                stroke="#f43f5e" strokeWidth="2" />
              <circle cx={sx(p[0])} cy={sy(p[1])} r={1.5} fill="#f43f5e" />
            </g>
          ))}
        </g>

        {/* các dạng lỗi lắp đặt */}
        {showFaults && Object.entries(fm.faults as Record<string, number[][]>).map(([k, pts]) => (
          <g key={k} opacity={dim(k) ? 0.15 : 0.9}>
            {pts.map((p, i) => (
              <rect key={i} x={sx(p[0]) - 3.5} y={sy(p[1]) - 3.5} width={7} height={7}
                fill="none" stroke="#f97316" strokeWidth="1.6" />
            ))}
          </g>
        ))}
      </svg>

      {/* chú giải */}
      <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
        {Object.keys(fm.classes).map((cls) => (
          <button key={cls} onMouseEnter={() => setHover(cls)} onMouseLeave={() => setHover(null)}
            className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: CLASS_COLOR[cls] }} />
            {VI_NAMES[cls] || cls}
          </button>
        ))}
        <button onMouseEnter={() => setHover('ood')} onMouseLeave={() => setHover(null)}
          className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400 font-medium">
          <span className="w-2.5 h-2.5 rounded-full border-2 border-rose-500" />
          Tín hiệu lạ (chưa huấn luyện)
        </button>
        <button onClick={() => setShowFaults(!showFaults)}
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded-sm border transition-colors ${
            showFaults
              ? 'border-orange-400 text-orange-700 bg-orange-50 dark:bg-orange-950/40 dark:text-orange-300'
              : 'border-slate-300 text-slate-500 dark:border-slate-700'
          }`}>
          <span className="w-2.5 h-2.5 border-2 border-orange-500" />
          {showFaults ? 'Đang hiện lỗi lắp đặt' : 'Hiện thêm lỗi lắp đặt'}
        </button>
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
        Mỗi chấm là một cửa sổ tín hiệu, được chiếu từ 16 đặc trưng xuống 2 chiều bằng PCA
        (giữ lại {(fm.explained_total * 100).toFixed(1)}% phương sai). Bốn lớp đã huấn luyện tụ thành từng cụm
        riêng. Tín hiệu lạ nằm tách khỏi mọi cụm — đây chính là căn cứ để hệ thống nói
        &quot;tôi chưa gặp dạng này bao giờ&quot; thay vì đoán bừa.
      </p>
    </div>
  );
}

/* ═══════════════ Đường cong học ═══════════════ */
function LearningCurve({ isDarkMode }: { isDarkMode: boolean }) {
  const lc = analysis.learning_curve as any;
  const W = 560;
  const H = 210;
  const pad = 34;
  const maxV = Math.max(...lc.interventions_mean, lc.machines_per_round);
  const bw = (W - 2 * pad) / lc.rounds.length;

  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {/* mốc so sánh: cách thủ công luôn cần 1 lần/máy */}
        <line x1={pad} y1={H - pad - ((H - 2 * pad) * lc.machines_per_round) / maxV}
          x2={W - pad} y2={H - pad - ((H - 2 * pad) * lc.machines_per_round) / maxV}
          stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="5 4" />
        <text x={W - pad} y={H - pad - ((H - 2 * pad) * lc.machines_per_round) / maxV - 6}
          textAnchor="end" fontSize="10" fill="#94a3b8">
          cách thủ công: {lc.machines_per_round} lần mỗi đợt
        </text>

        {lc.interventions_mean.map((v: number, i: number) => {
          const h = ((H - 2 * pad) * v) / maxV;
          const x = pad + bw * i + bw * 0.22;
          return (
            <g key={i}>
              <rect x={x} y={H - pad - h} width={bw * 0.56} height={Math.max(h, 1.5)}
                rx="2" fill="#10b981" />
              <text x={x + bw * 0.28} y={H - pad - h - 6} textAnchor="middle"
                fontSize="11" fontWeight="600" fill={isDarkMode ? '#e2e8f0' : '#334155'}>
                {v}
              </text>
              <text x={x + bw * 0.28} y={H - pad + 15} textAnchor="middle"
                fontSize="10" fill="#94a3b8">Đợt {lc.rounds[i]}</text>
            </g>
          );
        })}
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad}
          stroke={isDarkMode ? '#334155' : '#cbd5e1'} strokeWidth="1" />
      </svg>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className={`p-2.5 rounded-sm border ${isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-emerald-50 border-emerald-200'}`}>
          <div className="text-slate-500 dark:text-slate-400">Tổng số lần kỹ sư can thiệp</div>
          <div className="font-mono font-bold text-emerald-700 dark:text-emerald-400 text-lg">
            {lc.total_interventions_mean} / {lc.total_machines} máy
          </div>
        </div>
        <div className={`p-2.5 rounded-sm border ${isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200'}`}>
          <div className="text-slate-500 dark:text-slate-400">Nếu làm thủ công</div>
          <div className="font-mono font-bold text-slate-700 dark:text-slate-300 text-lg">
            {lc.baseline_interventions} / {lc.total_machines} máy
          </div>
        </div>
      </div>

      <div className={`p-3 rounded-sm border text-xs leading-relaxed ${
        isDarkMode ? 'bg-amber-950/25 border-amber-800/60 text-amber-200' : 'bg-amber-50 border-amber-200 text-amber-900'
      }`}>
        <strong>Đây là mô phỏng cơ chế, chưa phải số đo từ triển khai thật.</strong>
        <ul className="mt-1.5 space-y-0.5 opacity-90">
          {lc.assumptions.map((a: string, i: number) => <li key={i}>• {a}</li>)}
        </ul>
        <p className="mt-1.5 opacity-90">
          Thứ tự loại tín hiệu được chọn ngẫu nhiên, không sắp đặt — nếu sắp đặt thì
          đường cong chắc chắn đi xuống nhưng do người làm, không phải do hệ thống học được.
        </p>
      </div>
    </div>
  );
}

/* ═══════════════ Phát hiện lỗi lắp đặt ═══════════════ */
function FaultDetection({ isDarkMode }: { isDarkMode: boolean }) {
  const fd = analysis.fault_detection as any;
  const lim = fd.known_limitation;

  return (
    <div className="space-y-3">
      <div className="flex gap-4 text-xs text-slate-500 dark:text-slate-400 pb-1">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />Mô hình one-class
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-sky-500" />Luật kiểm tra dải
        </span>
      </div>

      {fd.faults.map((f: any) => {
        const model = f.by_model * 100;
        const rule = f.by_rule * 100;
        const total = f.detection_rate * 100;
        return (
          <div key={f.code}>
            <div className="flex justify-between items-baseline text-xs mb-1">
              <span className="text-slate-700 dark:text-slate-300">
                {FAULT_VI[f.code] || f.code}
              </span>
              <span className="font-mono font-semibold"
                style={{ color: total >= 80 ? '#10b981' : total >= 40 ? '#f59e0b' : '#f43f5e' }}>
                {total.toFixed(0)}%
              </span>
            </div>
            <div className={`h-2 rounded-sm overflow-hidden flex ${isDarkMode ? 'bg-slate-800' : 'bg-slate-100'}`}>
              <div className="h-full bg-emerald-500" style={{ width: `${model}%` }} />
              <div className="h-full bg-sky-500" style={{ width: `${Math.max(0, total - model)}%` }} />
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5 font-mono">
              mô hình {model.toFixed(0)}% · luật {rule.toFixed(0)}%
            </div>
          </div>
        );
      })}

      <div className={`flex items-center justify-between p-2.5 rounded-sm border text-xs ${
        isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200'
      }`}>
        <span className="text-slate-500 dark:text-slate-400">Báo động giả trên tín hiệu bình thường</span>
        <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
          {(fd.false_alarm_on_normal * 100).toFixed(1)}%
        </span>
      </div>

      <div className={`p-3 rounded-sm border text-xs leading-relaxed space-y-1.5 ${
        isDarkMode ? 'bg-sky-950/25 border-sky-800/60 text-sky-200' : 'bg-sky-50 border-sky-200 text-sky-900'
      }`}>
        <div className="flex items-center gap-1.5 font-bold">
          <AlertTriangle size={13} />
          <span>{FAULT_VI[lim.code]}: mô hình bắt 0%, luật kiểm tra dải bắt 100%</span>
        </div>
        <p className="opacity-90"><strong>Vì sao:</strong> {lim.why}</p>
        <p className="opacity-90 flex gap-1.5">
          <Wrench size={13} className="shrink-0 mt-0.5" />
          <span><strong>Cách xử lý:</strong> {lim.fix}</span>
        </p>
      </div>
    </div>
  );
}

/* ═══════════════ Suy giảm cảm biến ═══════════════ */
function Degradation({ isDarkMode }: { isDarkMode: boolean }) {
  const dg = analysis.degradation as any;
  const W = 560;
  const H = 200;
  const pad = 34;
  const series = dg.series as { month: number; iso_score: number; flag_rate: number }[];
  const vals = series.map((s) => s.iso_score).concat([dg.threshold]);
  const mn = Math.min(...vals) - 0.02;
  const mx = Math.max(...vals) + 0.02;
  const X = (i: number) => pad + ((W - 2 * pad) * i) / (series.length - 1);
  const Y = (v: number) => H - pad - ((H - 2 * pad) * (v - mn)) / (mx - mn);
  const path = series.map((s, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(s.iso_score).toFixed(1)}`).join(' ');

  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        <line x1={pad} y1={Y(dg.threshold)} x2={W - pad} y2={Y(dg.threshold)}
          stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="5 4" />
        <text x={pad + 4} y={Y(dg.threshold) - 5} fontSize="10" fill="#f43f5e">
          ngưỡng cảnh báo
        </text>

        <path d={path} fill="none" stroke="#0ea5e9" strokeWidth="2" strokeLinejoin="round" />
        {series.map((s, i) => (
          <circle key={i} cx={X(i)} cy={Y(s.iso_score)} r={s.flag_rate > 0 ? 4 : 2.5}
            fill={s.flag_rate > 0 ? '#f43f5e' : '#0ea5e9'} />
        ))}

        {[0, 3, 6, 9, 12].map((m) => (
          <text key={m} x={X(m)} y={H - pad + 15} textAnchor="middle" fontSize="10" fill="#94a3b8">
            T{m}
          </text>
        ))}
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad}
          stroke={isDarkMode ? '#334155' : '#cbd5e1'} strokeWidth="1" />
      </svg>

      <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
        Mô phỏng một cảm biến nhiệt độ xuống cấp dần: nhiễu tăng so với biên độ tín hiệu,
        xuất hiện hiện tượng kẹt giá trị. Điểm bất thường đi xuống đều từ tháng thứ 4,
        có cảnh báo lẻ tẻ từ tháng {series.find((s) => s.flag_rate > 0)?.month},
        và vượt ngưỡng ở tháng {dg.first_alert_month}.
      </p>

      <div className={`p-3 rounded-sm border text-xs leading-relaxed ${
        isDarkMode ? 'bg-sky-950/25 border-sky-800/60 text-sky-200' : 'bg-sky-50 border-sky-200 text-sky-900'
      }`}>
        <strong>Điểm đáng chú ý:</strong> xu hướng đi xuống xuất hiện nhiều tháng trước khi
        vượt ngưỡng, nên có thể cảnh báo sớm dựa trên độ dốc thay vì chờ chạm ngưỡng.
        Đây vẫn là mô hình one-class dùng lúc lắp đặt, không cần thuật toán mới.
      </div>
    </div>
  );
}

/* ═══════════════ Tab chính ═══════════════ */
const Section: React.FC<{
  icon: React.ReactNode; title: string; sub: string;
  isDarkMode: boolean; children: React.ReactNode;
}> = ({ icon, title, sub, isDarkMode, children }) => (
  <div className={`rounded-md border transition-colors ${
    isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
  }`}>
    <div className={`px-5 py-3 border-b flex items-start gap-2.5 ${
      isDarkMode ? 'border-slate-800' : 'border-slate-100'
    }`}>
      <div className="p-1.5 rounded-sm bg-emerald-600 text-white shrink-0">{icon}</div>
      <div>
        <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">{title}</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sub}</p>
      </div>
    </div>
    <div className="p-5">{children}</div>
  </div>
);

export const InsightsTab: React.FC<Props> = ({ isDarkMode = false }) => (
  <div className="space-y-5">
    <div className={`p-4 rounded-md border flex items-start gap-3 ${
      isDarkMode ? 'bg-slate-900 border-slate-800 text-slate-300' : 'bg-white border-slate-200 text-slate-700 shadow-xs'
    }`}>
      <Info size={18} className="text-emerald-600 shrink-0 mt-0.5" />
      <p className="text-xs leading-relaxed">
        Bốn phân tích dưới đây đo bằng <span className="font-mono">ml/analysis.py</span> trên dữ liệu mô phỏng.
        Cùng một mô hình phát hiện bất thường được dùng cho cả bốn mục đích: nhận diện tín hiệu,
        phát hiện lỗi lắp đặt, và theo dõi cảm biến suy giảm. Chạy lại script khi có dữ liệu thật để cập nhật.
      </p>
    </div>

    <Section isDarkMode={isDarkMode} icon={<Map size={16} />}
      title="Bản đồ không gian đặc trưng"
      sub="Vì sao hệ thống biết một tín hiệu là lạ">
      <FeatureMap isDarkMode={isDarkMode} />
    </Section>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Section isDarkMode={isDarkMode} icon={<TrendingDown size={16} />}
        title="Công kỹ sư giảm dần qua từng đợt"
        sub="Số lần phải gán nhãn thủ công mỗi đợt triển khai">
        <LearningCurve isDarkMode={isDarkMode} />
      </Section>

      <Section isDarkMode={isDarkMode} icon={<ShieldAlert size={16} />}
        title="Phát hiện lỗi lắp đặt"
        sub="Hai lớp bảo vệ bổ sung nhau — không lớp nào thay được lớp kia">
        <FaultDetection isDarkMode={isDarkMode} />
      </Section>
    </div>

    <Section isDarkMode={isDarkMode} icon={<Activity size={16} />}
      title="Theo dõi cảm biến suy giảm"
      sub="Cùng cơ chế, dùng lại cho giai đoạn vận hành">
      <Degradation isDarkMode={isDarkMode} />
    </Section>
  </div>
);
