import React, { useEffect, useMemo, useState } from 'react';
import {
  Plus, Cpu, WifiOff, CheckCircle2, XCircle, Sparkles, RotateCcw, History, Settings2,
  AlertTriangle, Tag, GraduationCap, ShieldCheck, Activity, Trash2, Terminal,
  Hammer, Wrench, Drill, Zap, Factory, Wind, Target, FlaskConical, SearchX, type LucideIcon,
} from 'lucide-react';
import { Card, Note, Bar, Spark } from './charts';
import type { Ack } from '../utils/mqtt';
import {
  EdgeState, LearnStatus, RecipeStatus, EdgeAlarm, MachineCfg, Mode, EdgeCycle, Profile, FieldCounts,
  MODE_META, ISSUE_VI, KIND_VI, STATUS_VI, machineMode, tsClock, tsDate, recipeLabel, profileOf, low,
} from '../utils/edge';
import { AddMachineDialog } from './AddMachineDialog';

const ICONS: Record<string, LucideIcon> = {
  press: Hammer, torque: Wrench, cnc: Drill, weld: Zap, injection: Factory, air: Wind, generic: Cpu,
};
const TypeIcon = ({ p, size = 14, className = '' }: { p: Profile; size?: number; className?: string }) => {
  const I = ICONS[p.icon] ?? Cpu;
  return <I size={size} className={className} aria-hidden="true" />;
};
const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
const featName = (p: Profile, f: { feature: string; vi: string }) => p.features[f.feature] ?? f.vi;

type Send = (op: string, body?: Record<string, unknown>) => Promise<Ack>;

interface Props {
  edge: EdgeState;
  connected: boolean;
  sample: boolean;       // đang hiện dữ liệu mẫu ghi sẵn, không gửi lệnh được
  send: Send;
  notify: (type: 'success' | 'warning' | 'info', title: string, description?: string) => void;
  addSignal?: number;    // tăng lên mỗi lần bấm "Thêm máy" ở thanh bên → mở form
}

export function FleetTab({ edge, connected, sample, send, notify, addSignal = 0 }: Props) {
  const machines = edge.registry?.machines ?? [];
  const [sel, setSel] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  useEffect(() => {
    if (!addSignal) return;
    if (sample) notify('info', 'Đây là dữ liệu mẫu', 'Chạy runtime edge để thêm máy thật.');
    else if (edge.registry) setAdding(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addSignal]);
  const cur = machines.find((m) => m.id === sel) ?? machines[0];

  const run = async (op: string, body: Record<string, unknown>, ok: string) => {
    if (sample) { notify('info', 'Đây là dữ liệu mẫu', 'Chạy runtime edge để thao tác thật.'); return null; }
    const a = await send(op, body);
    if (a.ok) notify('success', ok); else notify('warning', 'Không thực hiện được', a.error);
    return a;
  };

  if (!edge.registry) return <EmptyState connected={connected} />;

  return (
    <div className="space-y-5">
      {sample && (
        <Note tone="sky">
          Đang xem <b>dữ liệu mẫu ghi lại từ runtime mô phỏng</b> vì trang chưa nối được gateway. Các nút chỉ minh hoạ.
          Chạy <code className="font-mono">python -m edge.runtime --demo</code> cùng Mosquitto để thao tác thật.
        </Note>
      )}
      <div className="grid lg:grid-cols-[300px_minmax(0,1fr)] gap-5 items-start">
        <aside className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Máy đã khai báo <span className="text-slate-400 font-normal">· {machines.length}</span></h2>
            <button onClick={() => (sample ? notify('info', 'Đây là dữ liệu mẫu') : setAdding(true))}
              className="inline-flex items-center gap-1.5 text-xs font-medium bg-brand-600 text-white rounded-lg px-2.5 py-1.5 hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
              <Plus size={14} /> Thêm máy
            </button>
          </div>
          {machines.length === 0 && (
            <div className="border border-dashed border-slate-300 rounded-lg p-4 text-xs text-slate-500 leading-relaxed">
              Chưa có máy nào. Bấm <b>Thêm máy</b>, chọn mẫu PLC, nhập IP và thanh ghi — gateway bắt đầu học ngay.
            </div>
          )}
          {machines.map((m) => (
            <MachineCard key={m.id} cfg={m} p={profileOf(edge.registry, m)} st={edge.learn[m.id]} on={cur?.id === m.id} onClick={() => setSel(m.id)} />
          ))}
        </aside>

        {cur ? (
          <MachineDetail key={cur.id} cfg={cur} p={profileOf(edge.registry, cur)} st={edge.learn[cur.id]} cycles={edge.cycles[cur.id] ?? []} run={run} />
        ) : <div />}
      </div>
      {adding && edge.registry && (
        <AddMachineDialog templates={edge.registry.templates} profiles={edge.registry.profiles ?? {}} existing={machines.map((m) => m.id)}
          onClose={() => setAdding(false)}
          onSubmit={async (cfg) => {
            const a = await send('add_machine', { cfg });
            if (a.ok) { notify('success', `Đã thêm ${cfg.id}`, 'Gateway bắt đầu học chuẩn bình thường của máy này.'); setSel(cfg.id as string); setAdding(false); }
            return a;
          }} />
      )}
    </div>
  );
}

/* ───────────────────────── trạng thái rỗng ───────────────────────── */
function EmptyState({ connected }: { connected: boolean }) {
  return (
    <Card title="Chưa thấy runtime AI tự học" sub="Màn hình này điều khiển chương trình edge chạy trên gateway hoặc laptop.">
      <div className="grid md:grid-cols-2 gap-6 text-sm text-slate-700 leading-relaxed">
        <div className="space-y-3">
          <p>{connected
            ? 'Trang đã nối broker MQTT nhưng chưa nhận được danh sách máy. Runtime edge chưa chạy, hoặc đang chạy với mã gateway khác.'
            : 'Trang chưa nối được broker MQTT nên các màn hình khác đang chạy mô phỏng.'}</p>
          <p>Khi runtime chạy, mỗi máy tự đi qua 4 bước: <b>khai báo → tự học chuẩn bình thường → kỹ sư duyệt → giám sát</b>,
            rồi tiếp tục học lại theo phản hồi của người vận hành.</p>
        </div>
        <div className="bg-slate-900 text-slate-100 rounded-md p-4 font-mono text-xs space-y-1.5 overflow-x-auto">
          <div className="text-slate-400 flex items-center gap-1.5"><Terminal size={13} /> trên laptop / gateway</div>
          <div>mosquitto -c mosquitto.conf -v</div>
          <div>python -m edge.runtime --demo</div>
          <div className="text-slate-400 pt-2"># PLC Mitsubishi thật (cổng thập phân)</div>
          <div>python -m edge.runtime --add-plc 192.168.1.39:3000</div>
        </div>
      </div>
    </Card>
  );
}

/* ───────────────────────── thẻ máy ───────────────────────── */
function ModeChip({ mode, st }: { mode: Mode | null; st?: LearnStatus }) {
  if (!st) return <span className="text-[11px] px-2 py-0.5 rounded-full border border-slate-200 text-slate-500">Đang khởi động</span>;
  if (!st.conn.ok) return (
    <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border bg-rose-50 text-rose-800 border-rose-200">
      <WifiOff size={11} /> Mất kết nối PLC
    </span>);
  if (!mode) return null;
  const m = MODE_META[mode];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full border ${m.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${m.dot} ${mode === 'learning' ? 'animate-pulse' : ''}`} />{m.label}
    </span>);
}

const MachineCard: React.FC<{ cfg: MachineCfg; p: Profile; st?: LearnStatus; on: boolean; onClick: () => void }> = ({ cfg, p, st, on, onClick }) => {
  const mode = machineMode(st);
  const learning = st?.recipes.find((r) => r.mode === 'learning');
  return (
    <button onClick={onClick} aria-pressed={on}
      className={`w-full text-left bg-white border rounded-xl shadow-card px-4 py-3 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
        on ? 'border-brand-500 ring-2 ring-brand-500/15' : 'border-slate-200 hover:border-slate-400'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900 truncate">{cfg.name}</div>
          <div className="text-[11px] text-slate-600 truncate inline-flex items-center gap-1 mt-0.5">
            <TypeIcon p={p} size={12} className="text-slate-500 shrink-0" />{p.label}
          </div>
          <div className="text-[11px] text-slate-500 font-mono truncate">
            {cfg.id} · {cfg.plc.driver === 'simulator' ? 'mô phỏng' : `${cfg.plc.ip}:${cfg.plc.port}`}
          </div>
        </div>
        {!!st?.open_alarms && (
          <span className="shrink-0 text-[11px] font-semibold bg-rose-600 text-white rounded-full px-2 py-0.5 tabular-nums"
            title="Cảnh báo chưa xử lý">{st.open_alarms}</span>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2"><ModeChip mode={mode} st={st} />
        {st && st.recipes.length > 1 && <span className="text-[11px] text-slate-500">{st.recipes.length} {low(p.recipe)}</span>}
      </div>
      {learning && (
        <div className="mt-2.5">
          <Bar value={learning.learned / learning.target} color="#1769e8" height={5} />
          <div className="text-[11px] text-slate-500 mt-1 tabular-nums">{learning.learned}/{learning.target} {p.cycle}</div>
        </div>
      )}
    </button>
  );
}

/* ───────────────────────── chi tiết máy ───────────────────────── */
type Run = (op: string, body: Record<string, unknown>, ok: string) => Promise<Ack | null>;
type Base = Record<string, unknown>;

const MachineDetail: React.FC<{ cfg: MachineCfg; p: Profile; st?: LearnStatus; cycles: EdgeCycle[]; run: Run }> = ({ cfg, p, st, cycles, run }) => {
  const recipes = st?.recipes ?? [];
  const [rsel, setRsel] = useState<string | null>(null);
  const r = recipes.find((x) => x.recipe === rsel) ?? recipes.find((x) => x.mode === 'review') ?? recipes[recipes.length - 1];
  const rc = useMemo(() => cycles.filter((c) => !r || c.recipe === r.recipe), [cycles, r]);
  const base = { machine: cfg.id, recipe: r?.recipe ?? '*' };

  return (
    <div className="space-y-5 min-w-0">
      <Card pad={false}>
        <div className="px-5 py-4 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900">{cfg.name}</h2>
              <ModeChip mode={r?.mode ?? null} st={st} />
            </div>
            <p className="text-sm text-slate-700 mt-1 inline-flex items-center gap-1.5">
              <TypeIcon p={p} size={15} className="text-slate-500" /> {p.label} · đo <b className="font-medium">{low(p.signal)}</b>
              {p.unit ? ` (${p.unit})` : ''}
            </p>
            <p className="text-xs text-slate-500 mt-1 font-mono">
              {cfg.id}{cfg.line ? ` · ${cfg.line}` : ''} · {cfg.plc.driver === 'simulator' ? 'máy mô phỏng'
                : `Mitsubishi MC 3E · ${cfg.plc.ip}:${cfg.plc.port} · ${low(p.signal)} ${cfg.signal.register} × ${cfg.signal.scale}${
                  cfg.signal.unit ? ` ${cfg.signal.unit}` : ''} · trạng thái ${cfg.state.register}${
                  cfg.recipe_register ? ` · ${low(p.recipe)} ${cfg.recipe_register}` : ''}`}
            </p>
            {st && <p className={`text-xs mt-1 ${st.conn.ok ? 'text-slate-500' : 'text-rose-700'}`}>{st.conn.msg}</p>}
          </div>
          <div className="text-right text-xs text-slate-500">
            <div>Trạng thái máy</div>
            <div className="text-sm font-semibold text-slate-900 font-mono">{st?.state ?? '—'}</div>
          </div>
        </div>
        {recipes.length > 1 && (
          <div className="px-5 pb-3 flex flex-wrap gap-1.5" role="tablist" aria-label={p.recipe}>
            {recipes.map((x) => (
              <button key={x.recipe} role="tab" aria-selected={x.recipe === r?.recipe} onClick={() => setRsel(x.recipe)}
                className={`text-xs px-2.5 py-1 rounded border inline-flex items-center gap-1.5 ${
                  x.recipe === r?.recipe ? 'border-brand-500 bg-brand-50 text-brand-700 font-medium' : 'border-slate-200 text-slate-500 hover:text-slate-800'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${MODE_META[x.mode].dot}`} /> {p.recipe} {recipeLabel(x.recipe)}
              </button>
            ))}
          </div>
        )}
        {r && <Stepper mode={r.mode} />}
      </Card>

      {!st || !r ? (
        <Card><p className="text-sm text-slate-500">Đang chờ {p.cycle} đầu tiên từ máy…</p></Card>
      ) : (
        <>
          {r.mode === 'learning' && <LearningPanel r={r} p={p} cycles={rc} />}
          {r.mode === 'review' && r.pending && <ReviewPanel r={r} p={p} cycles={rc} base={base} run={run} />}
          {r.mode === 'monitoring' && r.active && <MonitorPanel r={r} p={p} st={st} base={base} run={run} />}
          {recipes.some((x) => x.mode === 'monitoring') && <FieldPanel st={st} p={p} run={run} machine={cfg.id} sim={cfg.plc.driver === 'simulator'} />}
          <ScorePanel cycles={rc} p={p} mode={r.mode} />
          <AlarmPanel st={st} p={p} recipe={r.recipe} base={base} run={run} />
          <div className="grid xl:grid-cols-2 gap-5">
            <VersionsPanel r={r} base={base} run={run} />
            <SettingsPanel cfg={cfg} p={p} st={st} run={run} />
          </div>
        </>
      )}
    </div>
  );
}

const STEPS: { key: string; label: string; sub: string }[] = [
  { key: 'declare', label: 'Khai báo', sub: 'PLC, thanh ghi' },
  { key: 'learning', label: 'Tự học', sub: 'chuẩn bình thường' },
  { key: 'review', label: 'Kỹ sư duyệt', sub: 'bật cảnh báo' },
  { key: 'monitoring', label: 'Giám sát', sub: 'học lại theo phản hồi' },
];

function Stepper({ mode }: { mode: Mode }) {
  const at = { learning: 1, review: 2, monitoring: 3 }[mode];
  return (
    <ol className="px-5 pb-4 pt-1 grid grid-cols-4 gap-2" aria-label="Vòng đời mô hình">
      {STEPS.map((s, i) => (
        <li key={s.key} className="min-w-0">
          <div className={`h-1 rounded-full ${i < at ? 'bg-brand-600' : i === at ? 'bg-brand-300' : 'bg-slate-200'}`} />
          <div className={`mt-1.5 text-xs font-medium ${i < at ? 'text-slate-900' : i === at ? 'text-brand-700' : 'text-slate-400'}`}>{s.label}</div>
          <div className="text-[11px] text-slate-500 truncate">{s.sub}</div>
        </li>
      ))}
    </ol>
  );
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900 tabular-nums mt-0.5">{value}</div>
      {hint && <div className="text-[11px] text-slate-500 leading-snug">{hint}</div>}
    </div>
  );
}

function rate(cycles: EdgeCycle[]) {
  const c = cycles.slice(-30);
  if (c.length < 5) return null;
  const dt = (c[c.length - 1].ts - c[0].ts) / 1000 / (c.length - 1);
  return dt > 0 ? dt : null;
}

function LearningPanel({ r, p, cycles }: { r: RecipeStatus; p: Profile; cycles: EdgeCycle[] }) {
  const per = rate(cycles);
  const left = Math.max(0, r.target - r.learned);
  const eta = per ? left * per : null;
  return (
    <Card title={<span className="inline-flex items-center gap-2"><GraduationCap size={16} /> Đang học {low(p.signal)} bình thường của máy</span>}
      sub={`Chưa bật cảnh báo AI trong lúc học. ${cap(p.cycle)} máy tự báo lỗi và ${p.cycle} lỗi tín hiệu bị loại khỏi dữ liệu học.`}>
      <div className="space-y-4">
        <div>
          <div className="flex items-baseline justify-between text-sm mb-1.5">
            <span className="font-medium text-slate-900 tabular-nums">{r.learned} / {r.target} {p.cycle}</span>
            <span className="text-xs text-slate-500">{eta != null ? `còn khoảng ${fmtDur(eta)}` : `đang đo nhịp ${p.cycle}…`}</span>
          </div>
          <Bar value={r.learned / r.target} color="#1769e8" height={10} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Stat label="Đã học" value={r.learned} />
          <Stat label="Bỏ qua · máy báo lỗi" value={r.excluded_error} />
          <Stat label="Bỏ qua · lỗi tín hiệu" value={r.excluded_dq} />
        </div>
        <Note>Nên để máy chạy qua ít nhất 2 ca hoặc 2 lô phôi khi học, để chuẩn bình thường bao được biến động giữa các ca.
          Nếu lúc học máy ra vài {p.cycle} lỗi mà không ai biết, bước huấn luyện tự lọc bỏ các {p.cycle} lệch xa trước khi học.
          {r.recipe !== '*' && <> Mỗi {low(p.recipe)} có chuẩn riêng — {low(p.recipe)} mới chạy lần đầu sẽ tự vào chế độ học.</>}</Note>
      </div>
    </Card>
  );
}

function fmtDur(s: number) {
  if (s < 90) return `${Math.round(s)} giây`;
  if (s < 5400) return `${Math.round(s / 60)} phút`;
  return `${(s / 3600).toFixed(1)} giờ`;
}

function ModelFacts({ m, p }: { m: NonNullable<RecipeStatus['active']>; p: Profile }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <Stat label={`${cap(p.cycle)} đã học`} value={m.n_train} hint={m.n_dropped ? `tự bỏ ${m.n_dropped} ${p.cycle} nghi lỗi` : `không có ${p.cycle} nghi lỗi`} />
      <Stat label="Báo nhầm ước tính" value={m.calib_false_alarm != null ? `${(m.calib_false_alarm * 100).toFixed(1)}%` : '—'}
        hint="kiểm định chéo theo khối thời gian" />
      <Stat label={`Thời gian ${p.cycle} (trung vị)`} value={m.duration_med ? `${m.duration_med.toFixed(2)} s` : '—'} />
      <Stat label="Phiên bản" value={`v${m.version}`} hint={KIND_VI[m.kind] ?? m.kind} />
    </div>
  );
}

function ReviewPanel({ r, p, cycles, base, run }: { r: RecipeStatus; p: Profile; cycles: EdgeCycle[]; base: Base; run: Run }) {
  const m = r.pending!;
  const prev = cycles.filter((c) => c.kind === 'preview');
  const would = prev.filter((c) => c.flag).length;
  return (
    <Card title={<span className="inline-flex items-center gap-2"><ShieldCheck size={16} /> Đã học xong — chờ kỹ sư duyệt</span>}
      sub={m.note}>
      <div className="space-y-4">
        <ModelFacts m={m} p={p} />
        <Note tone="amber">
          {prev.length ? (<>
            Chạy thử chuẩn mới trên {prev.length} {p.cycle} gần nhất: <b>{would}</b> {p.cycle} sẽ bị cảnh báo
            ({((would / prev.length) * 100).toFixed(1)}%). Nếu con số này cao trong khi máy đang chạy bình thường,
            hãy để máy học lại lâu hơn.</>
          ) : 'Chưa có chu kỳ nào của mã hàng này kể từ khi học xong. Khi máy chạy lại mã hàng này, trang sẽ chấm thử bằng chuẩn mới để kỹ sư xem trước khi duyệt.'}
        </Note>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => run('approve', base, 'Đã bật giám sát')}
            className="inline-flex items-center gap-1.5 text-sm font-medium bg-emerald-700 text-white rounded-md px-3.5 py-2 hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800">
            <CheckCircle2 size={16} /> Kích hoạt giám sát
          </button>
          <button onClick={() => run('reject', base, 'Đã bỏ bản này, máy học lại từ đầu')}
            className="inline-flex items-center gap-1.5 text-sm border border-slate-300 rounded-md px-3.5 py-2 hover:bg-slate-50">
            <RotateCcw size={15} /> Học lại từ đầu
          </button>
        </div>
      </div>
    </Card>
  );
}

function MonitorPanel({ r, p: prof, st, base, run }: { r: RecipeStatus; p: Profile; st: LearnStatus; base: Base; run: Run }) {
  const a = r.active!;
  const p = r.pending;
  return (
    <Card title={<span className="inline-flex items-center gap-2"><Activity size={16} /> Đang giám sát bằng chuẩn v{a.version}</span>}
      sub={a.note}
      right={<button onClick={() => run('retrain_now', base, 'Đã tạo bản học lại, chờ duyệt')}
        className="inline-flex items-center gap-1.5 text-xs border border-slate-300 rounded-md px-2.5 py-1.5 hover:bg-slate-50 shrink-0">
        <Sparkles size={13} /> Học lại ngay</button>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Stat label={`${cap(prof.cycle)} đã giám sát`} value={r.monitored} />
          <Stat label="Bị cảnh báo" value={r.flagged} hint={r.monitored ? `${((r.flagged / r.monitored) * 100).toFixed(1)}% số ${prof.cycle}` : undefined} />
          <Stat label="Chưa xử lý" value={st.open_alarms} />
          <Stat label="Học lại định kỳ" value={`${r.since_retrain}/${r.retrain_every}`} hint={`${prof.cycle} tới lần tạo bản mới`} />
        </div>
        {p && (
          <div className={`border rounded-md px-4 py-3 ${p.warn ? 'bg-rose-50 border-rose-200' : 'bg-amber-50 border-amber-200'}`}>
            <div className="text-sm font-medium text-slate-900 flex items-center gap-2">
              {p.warn ? <AlertTriangle size={15} className="text-rose-700" /> : <History size={15} />}
              Bản v{p.version} chờ duyệt · {KIND_VI[p.kind] ?? p.kind}
            </div>
            <p className="text-xs text-slate-700 mt-1 leading-relaxed">{p.note}</p>
            {p.warn && <p className="text-xs text-rose-800 mt-1">Chuẩn dịch nhiều so với bản đang chạy — có thể máy đang mòn hoặc đổi điều kiện.
              Kiểm tra máy trước khi duyệt, nếu không AI sẽ coi trạng thái mới là bình thường.</p>}
            <p className="text-[11px] text-slate-500 mt-1">Dịch so với bản gốc: {p.shift_origin?.toFixed(2) ?? '—'}σ — theo dõi số này để thấy hao mòn từ từ.</p>
            <div className="flex flex-wrap gap-2 mt-2.5">
              <button onClick={() => run('approve', base, `Đã chuyển sang v${p.version}`)}
                className="text-xs font-medium bg-brand-600 text-white rounded-lg px-3 py-1.5 hover:bg-brand-700">Duyệt bản mới</button>
              <button onClick={() => run('reject', base, 'Giữ bản đang chạy')}
                className="text-xs border border-slate-300 rounded-md px-3 py-1.5 hover:bg-white">Giữ bản cũ</button>
            </div>
          </div>
        )}
        <ModelFacts m={a} p={prof} />
      </div>
    </Card>
  );
}

/* ───────────────────────── biểu đồ điểm theo thời gian ───────────────────────── */
function ScorePanel({ cycles, p, mode }: { cycles: EdgeCycle[]; p: Profile; mode: Mode }) {
  const pts = cycles.filter((c) => c.norm != null || c.kind === 'dq').slice(-160);
  const W = 640, H = 170, P = { l: 34, r: 10, t: 10, b: 22 };
  const top = Math.min(4, Math.max(2, ...pts.map((c) => c.norm ?? 0)) * 1.08);
  const x = (i: number) => P.l + (i / Math.max(1, pts.length - 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - Math.min(v, top) / top) * (H - P.t - P.b);
  let e = 0;
  const ew = pts.map((c, i) => { const v = c.norm ?? e; e = i === 0 ? v : 0.15 * v + 0.85 * e; return e; });
  const last = [...cycles].reverse().find((c) => c.y?.length);
  const lastAlarm = [...cycles].reverse().find((c) => c.flag && c.kind === 'score');
  const dqN = pts.filter((c) => c.kind === 'dq').length;
  return (
    <Card title="Điểm bất thường theo thời gian"
      sub={mode === 'learning' ? 'Chưa có điểm: máy đang học. Điểm xuất hiện sau khi kỹ sư duyệt.'
        : mode === 'review' ? 'Chấm thử bằng bản chờ duyệt (chấm rỗng) — chưa phát cảnh báo.'
          : '1,0 = đúng ngưỡng. Đường xanh là trung bình trượt: đi lên dần nghĩa là máy đang xấu đi dù từng chu kỳ chưa vượt ngưỡng.'}>
      <div className="grid md:grid-cols-[minmax(0,1fr)_220px] gap-5 items-start">
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[420px] h-auto" role="img" aria-label="Biểu đồ điểm bất thường">
            {[0, 1, 2, 3, 4].filter((v) => v <= top).map((v) => (
              <g key={v}>
                <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} stroke={v === 1 ? '#e11d48' : '#e2e8f0'} strokeDasharray={v === 1 ? '5 4' : undefined} />
                <text x={P.l - 6} y={y(v) + 3.5} textAnchor="end" fontSize="10" fill="#64748b">{v.toFixed(1)}</text>
              </g>
            ))}
            <text x={W - P.r} y={y(1) - 4} textAnchor="end" fontSize="10" fill="#e11d48">ngưỡng</text>
            {pts.length > 1 && (
              <polyline fill="none" stroke="#1769e8" strokeWidth="1.8"
                points={ew.map((v, i) => `${x(i)},${y(v)}`).join(' ')} />
            )}
            {pts.map((c, i) => c.kind === 'dq'
              ? <text key={i} x={x(i)} y={H - P.b - 2} fontSize="9" textAnchor="middle" fill="#94a3b8">×</text>
              : c.kind === 'ng_sample'
                ? <rect key={i} x={x(i) - 3.5} y={y(c.norm!) - 3.5} width="7" height="7" fill={c.flag ? '#7c3aed' : '#fff'} stroke="#7c3aed" strokeWidth="1.4"><title>Mẫu NG kiểm tra {c.flag ? '— AI bắt được' : '— AI BỎ SÓT'}</title></rect>
              : <circle key={i} cx={x(i)} cy={y(c.norm!)} r={c.flag ? 3.4 : 2}
                fill={c.kind === 'preview' ? 'none' : c.flag ? '#e11d48' : '#64748b'}
                stroke={c.kind === 'preview' ? (c.flag ? '#e11d48' : '#64748b') : 'none'} strokeWidth="1" />)}
            {!pts.length && <text x={W / 2} y={y(top * 0.62)} textAnchor="middle" fontSize="12" fill="#94a3b8">Chưa có {p.cycle} được chấm điểm</text>}
          </svg>
          <div className="flex flex-wrap gap-4 text-[11px] text-slate-500 mt-1">
            <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-500" /> {p.cycle}</span>
            <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-600" /> bị cảnh báo</span>
            <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-brand-600" /> trung bình trượt</span>
            {dqN > 0 && <span>× lỗi tín hiệu ({dqN})</span>}
            {pts.some((c) => c.kind === 'ng_sample') && <span className="inline-flex items-center gap-1"><span className="w-2 h-2 bg-violet-600" /> mẫu NG kiểm tra</span>}
          </div>
        </div>
        <div className="space-y-2">
          <div className="text-[11px] uppercase tracking-wider text-slate-500">{cap(p.cycle)} vừa đọc · {low(p.signal)}{p.unit ? ` (${p.unit})` : ''}</div>
          <div className="border border-slate-200 rounded-md p-2 bg-slate-50">{last ? <Spark y={last.y} anomalous={!!last.flag} /> : <div className="h-8" />}</div>
          {lastAlarm?.top && (
            <div className="text-xs text-slate-600 leading-relaxed">
              <div className="font-medium text-slate-800 mb-0.5">Cảnh báo gần nhất lệch ở:</div>
              {lastAlarm.top.map((t) => <div key={t.feature}>{featName(p, t)} <span className="text-slate-400 tabular-nums">({t.z.toFixed(1)}× độ lệch thường)</span></div>)}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

/* ───────────────────────── cảnh báo + 3 nút phản hồi ───────────────────────── */
const ALARM_STATUS: Record<EdgeAlarm['status'], { label: string; cls: string }> = {
  open: { label: 'Chưa xử lý', cls: 'bg-rose-50 text-rose-800 border-rose-200' },
  fault: { label: 'Đúng là lỗi', cls: 'bg-slate-900 text-white border-slate-900' },
  false_alarm: { label: 'Báo nhầm', cls: 'bg-slate-50 text-slate-600 border-slate-200' },
  new_normal: { label: 'Bình thường mới', cls: 'bg-sky-50 text-sky-800 border-sky-200' },
  missed: { label: 'AI bỏ sót', cls: 'bg-amber-50 text-amber-900 border-amber-200' },
};

function AlarmPanel({ st, p, recipe, base, run }: { st: LearnStatus; p: Profile; recipe: string; base: Base; run: Run }) {
  const [more, setMore] = useState(false);
  const all = st.alarms.filter((a) => a.recipe === recipe);
  const list = more ? all : all.slice(0, 6);
  const known = [...new Set([...Object.keys(st.classifier.types), ...p.faults])];
  const c = st.classifier;
  return (
    <Card title="Cảnh báo và phản hồi"
      sub="Mỗi lần bấm là một nhãn: AI dùng nhãn để học lại (báo nhầm, bình thường mới) và để học phân loại loại lỗi (đúng là lỗi)."
      right={<span className={`text-[11px] px-2 py-1 rounded border shrink-0 inline-flex items-center gap-1 ${c.ready ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-slate-50 text-slate-600 border-slate-200'}`}
        title={`Bật khi đủ nhãn. Nhãn lỗi dùng chung giữa các máy cùng loại (${low(p.label)}).`}>
        <Tag size={12} /> Phân loại lỗi: {c.ready ? `đang dùng (${Object.keys(c.types).length} loại)` : `${c.n}/${c.need_total} nhãn`}
        {(c.shared_machines ?? 0) > 1 ? ` · chung ${c.shared_machines} máy` : c.n > 0 && c.own === 0 ? ' · từ máy cùng loại' : ''}
      </span>}>
      {all.length > 6 && (
        <div className="-mt-1 mb-3 text-xs text-slate-500">
          {all.filter((a) => a.status === 'open').length} cảnh báo chưa xử lý trong {all.length} cảnh báo gần nhất.
          Gặp cả loạt giống nhau thì tick "áp cho mọi cảnh báo đang mở" để gắn nhãn một lần.
        </div>
      )}
      {list.length === 0 ? (
        <p className="text-sm text-slate-500">Chưa có cảnh báo nào{recipe !== '*' ? ` cho ${low(p.recipe)} ${recipe}` : ''}.</p>
      ) : (
        <ul className="divide-y divide-slate-100 -my-2">
          {list.map((a) => <AlarmRow key={a.id} a={a} p={p} known={known} base={base} run={run} />)}
        </ul>
      )}
      {all.length > 6 && (
        <button onClick={() => setMore((v) => !v)} className="mt-3 text-xs text-slate-600 underline underline-offset-2 hover:text-slate-900">
          {more ? 'Thu gọn' : `Xem cả ${all.length} cảnh báo`}
        </button>
      )}
    </Card>
  );
}

const AlarmRow: React.FC<{ a: EdgeAlarm; p: Profile; known: string[]; base: Base; run: Run }> = ({ a, p, known, base, run }) => {
  const [askType, setAskType] = useState(false);
  const [ft, setFt] = useState(a.suggestion?.type ?? '');
  const [all, setAll] = useState(false);
  const s = ALARM_STATUS[a.status];
  const send = (label: string, extra: Record<string, unknown> = {}) =>
    run('feedback', { ...base, alarm_id: a.id, label, all_open: all, ...extra },
      label === 'fault' ? 'Đã ghi nhận lỗi' : label === 'false_alarm' ? 'Đã ghi nhận báo nhầm' : 'Đã ghi nhận chế độ bình thường mới');
  const listId = `ft-${a.id}`;
  return (
    <li className="py-3 grid sm:grid-cols-[minmax(0,1fr)_auto] gap-3 items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-mono text-xs text-slate-500 tabular-nums">{tsClock(a.ts)}</span>
          <span className="font-semibold text-slate-900 tabular-nums">điểm {a.norm.toFixed(2)}</span>
          <span className={`text-[11px] px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}{a.fault_type ? ` · ${a.fault_type}` : ''}</span>
          {a.source === 'button' && <span className="text-[11px] text-slate-500">· bấm trên hộp gateway</span>}
          {a.suggestion && a.status === 'open' && (
            <span className="text-[11px] text-slate-600">AI đoán: <b>{a.suggestion.type}</b> ({Math.round(a.suggestion.prob * 100)}%)</span>
          )}
        </div>
        <div className="text-xs text-slate-600 mt-1">
          Lệch nhiều nhất: {a.top.map((t) => `${featName(p, t)} (${t.z.toFixed(1)}×)`).join(' · ')}
        </div>
      </div>
      {a.status === 'open' && (
        <div className="flex flex-col items-stretch sm:items-end gap-1.5">
          {!askType ? (
            <div className="flex flex-wrap gap-1.5">
              <button onClick={() => setAskType(true)} className="text-xs font-medium bg-brand-600 text-white rounded-md px-2.5 py-1.5 hover:bg-brand-700">Đúng là lỗi</button>
              <button onClick={() => send('false_alarm')} className="text-xs border border-slate-300 rounded px-2.5 py-1.5 hover:bg-slate-50">Báo nhầm</button>
              <button onClick={() => send('new_normal')} className="text-xs border border-sky-300 text-sky-800 rounded px-2.5 py-1.5 hover:bg-sky-50">Bình thường mới</button>
            </div>
          ) : (
            <form className="flex flex-wrap gap-1.5 sm:justify-end max-w-sm" onSubmit={(e) => { e.preventDefault(); if (!ft.trim()) return; send('fault', { fault_type: ft.trim() }); setAskType(false); }}>
              <label className="sr-only" htmlFor={`in-${a.id}`}>Loại lỗi</label>
              <input id={`in-${a.id}`} list={listId} value={ft} onChange={(e) => setFt(e.target.value)} autoFocus
                placeholder={`Loại lỗi, vd. ${p.faults[0] ?? 'Thiếu phôi'}`} className="text-xs border border-slate-300 rounded px-2 py-1.5 w-44" />
              <datalist id={listId}>{known.map((k) => <option key={k} value={k} />)}</datalist>
              <button type="submit" className="text-xs font-medium bg-brand-600 text-white rounded-md px-2.5 py-1.5 hover:bg-brand-700">Lưu</button>
              <button type="button" onClick={() => setAskType(false)} className="text-xs text-slate-500 px-1">Huỷ</button>
              {known.length > 0 && (
                <div className="basis-full flex flex-wrap gap-1 sm:justify-end">
                  {known.slice(0, 6).map((k) => (
                    <button key={k} type="button" onClick={() => setFt(k)}
                      className={`text-[11px] rounded border px-1.5 py-0.5 ${ft === k ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-600 hover:border-slate-400'}`}>{k}</button>
                  ))}
                </div>
              )}
            </form>
          )}
          <label className="text-[11px] text-slate-500 inline-flex items-center gap-1.5">
            <input type="checkbox" id={`all-${a.id}`} checked={all} onChange={(e) => setAll(e.target.checked)} /> áp cho mọi cảnh báo đang mở
          </label>
        </div>
      )}
    </li>
  );
}

/* ───────────────────────── phiên bản mô hình ───────────────────────── */
function VersionsPanel({ r, base, run }: { r: RecipeStatus; base: Base; run: Run }) {
  const rows = [...r.versions].reverse();
  return (
    <Card title={<span className="inline-flex items-center gap-2"><History size={16} /> Phiên bản mô hình</span>}
      sub="Mọi bản đều được giữ. Bản mới làm báo nhầm nhiều thì quay về bản cũ.">
      {rows.length === 0 ? <p className="text-sm text-slate-500">Chưa có bản nào — máy đang học.</p> : (
        <ul className="space-y-2.5">
          {rows.map((v) => (
            <li key={v.version} className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm">
                  <span className="font-semibold tabular-nums">v{v.version}</span>
                  <span className="text-slate-500"> · {KIND_VI[v.kind] ?? v.kind} · {tsDate(v.created)}</span>
                </div>
                <div className="text-[11px] text-slate-500 leading-snug">{v.note}</div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className={`text-[11px] px-2 py-0.5 rounded-full border ${v.status === 'active' ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : v.status === 'pending' ? 'bg-amber-50 text-amber-900 border-amber-200' : 'bg-slate-50 text-slate-500 border-slate-200'}`}>
                  {STATUS_VI[v.status]}</span>
                {v.status === 'retired' && (
                  <button onClick={() => run('rollback', { ...base, version: v.version }, `Đã quay về v${v.version}`)}
                    className="text-[11px] border border-slate-300 rounded px-1.5 py-0.5 hover:bg-slate-50">Quay về</button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* ───────────────────────── cài đặt AI của máy ───────────────────────── */
function SettingsPanel({ cfg, p, st, run }: { cfg: MachineCfg; p: Profile; st: LearnStatus; run: Run }) {
  const [lt, setLt] = useState(String(st.ai.learn_target));
  const [re, setRe] = useState(String(st.ai.retrain_every));
  const [auto, setAuto] = useState(!!st.ai.auto_approve);
  const [confirm, setConfirm] = useState(false);
  const id = cfg.id;
  return (
    <Card title={<span className="inline-flex items-center gap-2"><Settings2 size={16} /> Cài đặt học của máy</span>}>
      <form className="space-y-3 text-sm" onSubmit={(e) => {
        e.preventDefault();
        run('set_ai', { machine: id, ai: { learn_target: Number(lt), retrain_every: Number(re), auto_approve: auto } }, 'Đã lưu cài đặt');
      }}>
        <div className="grid grid-cols-2 gap-3">
          <label className="block" htmlFor={`lt-${id}`}>
            <span className="text-xs text-slate-600">Số {p.cycle} cần học</span>
            <input id={`lt-${id}`} type="number" min={30} value={lt} onChange={(e) => setLt(e.target.value)}
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 tabular-nums" />
          </label>
          <label className="block" htmlFor={`re-${id}`}>
            <span className="text-xs text-slate-600">Học lại sau mỗi ({p.cycle})</span>
            <input id={`re-${id}`} type="number" min={50} value={re} onChange={(e) => setRe(e.target.value)}
              className="mt-1 w-full border border-slate-300 rounded px-2 py-1.5 tabular-nums" />
          </label>
        </div>
        <label className="flex items-start gap-2 text-xs text-slate-700" htmlFor={`au-${id}`}>
          <input id={`au-${id}`} type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="mt-0.5" />
          Tự duyệt bản học lại khi chuẩn dịch ít (dưới 1σ so với bản đang chạy). Bản dịch nhiều vẫn chờ người duyệt.
        </label>
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <button type="submit" className="text-xs font-medium bg-brand-600 text-white rounded-md px-3 py-1.5 hover:bg-brand-700">Lưu cài đặt</button>
          <div className="flex gap-1.5">
            <button type="button" onClick={() => run('relearn', { machine: id, recipe: st.recipes[0]?.recipe ?? '*' }, 'Máy bắt đầu học lại từ đầu')}
              className="text-xs border border-slate-300 rounded px-2.5 py-1.5 hover:bg-slate-50 inline-flex items-center gap-1"><RotateCcw size={12} /> Học lại từ đầu</button>
            {!confirm ? (
              <button type="button" onClick={() => setConfirm(true)}
                className="text-xs border border-rose-200 text-rose-700 rounded px-2.5 py-1.5 hover:bg-rose-50 inline-flex items-center gap-1"><Trash2 size={12} /> Xoá máy</button>
            ) : (
              <button type="button" onClick={() => run('remove_machine', { machine: id }, `Đã xoá ${id}`)}
                className="text-xs bg-rose-700 text-white rounded px-2.5 py-1.5 inline-flex items-center gap-1"><XCircle size={12} /> Bấm lần nữa để xoá</button>
            )}
          </div>
        </div>
      </form>
      {st.last_dq && (
        <p className="text-[11px] text-slate-500 mt-3 inline-flex items-center gap-1.5">
          <Cpu size={12} /> Lỗi tín hiệu gần nhất {tsClock(st.last_dq.ts)}: {st.last_dq.issues.map((i) => ISSUE_VI[i] ?? i).join(', ')}
        </p>
      )}
    </Card>
  );
}

/* ───────────────────────── độ chính xác thực tế tại máy ───────────────────────── */
const pctOr = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`);

function FieldPanel({ st, p, run, machine, sim }: { st: LearnStatus; p: Profile; run: Run; machine: string; sim: boolean }) {
  const f = st.field;
  const [span, setSpan] = useState<'week' | 'all'>('week');
  const [n, setN] = useState('3');
  const [missOpen, setMissOpen] = useState(false);
  const [missId, setMissId] = useState<string>('');
  const [missType, setMissType] = useState('');
  if (!f) return null;
  const c: FieldCounts = f[span];
  const judged = c.fault + c.false_alarm + c.new_normal;
  const ng = f.ng_active;
  const cand = f.recent.filter((x) => !x.flag && x.label == null);
  return (
    <Card title={<span className="inline-flex items-center gap-2"><Target size={16} /> Độ chính xác thực tế tại máy</span>}
      sub="Tính từ xác nhận của công nhân và kỹ sư (nút trên dashboard hoặc nút trên hộp gateway) — không phải từ dữ liệu thử."
      right={<div className="inline-flex rounded-lg border border-slate-200 p-0.5 text-xs shrink-0" role="tablist">
        {(['week', 'all'] as const).map((k) => (
          <button key={k} role="tab" aria-selected={span === k} onClick={() => setSpan(k)}
            className={`px-2.5 py-1 rounded-md ${span === k ? 'bg-brand-50 text-brand-700 font-medium' : 'text-slate-500'}`}>{k === 'week' ? '7 ngày' : 'Từ đầu'}</button>
        ))}
      </div>}>
      <div className="space-y-5">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Stat label="Cảnh báo đúng" value={pctOr(c.precision)} hint={judged ? `${c.fault}/${judged} cảnh báo đã xác nhận là lỗi thật` : 'chưa có cảnh báo nào được xác nhận'} />
          <Stat label="Lỗi AI bắt được" value={pctOr(c.recall)} hint={c.fault + c.missed ? `${c.fault}/${c.fault + c.missed} lỗi đã biết · ${c.missed} AI bỏ sót` : 'chưa có lỗi nào được ghi nhận'} />
          <Stat label="Báo nhầm" value={c.false_alarm} hint={c.new_normal ? `+ ${c.new_normal} chế độ bình thường mới` : 'cảnh báo bị đánh dấu nhầm'} />
          <Stat label="Chưa xác nhận" value={c.open} hint="cảnh báo đang chờ người kiểm" />
        </div>

        <div className="grid lg:grid-cols-2 gap-5">
          <div className="border border-slate-200 rounded-lg p-4">
            <div className="text-sm font-medium text-slate-900 inline-flex items-center gap-2"><FlaskConical size={15} /> Kiểm tra mẫu NG chuẩn</div>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">Đầu ca, cho máy chạy vài chi tiết lỗi chuẩn lấy từ kho mẫu NG. AI phải bắt hết.
              Các {p.cycle} này không tạo cảnh báo và không bao giờ được dùng để học.</p>
            {ng ? (
              <div className="mt-3 bg-violet-50 border border-violet-200 rounded-md px-3 py-2.5 text-sm text-violet-900">
                Đang chờ mẫu NG <b className="tabular-nums">{ng.done}/{ng.expected}</b> — cho máy chạy chi tiết lỗi chuẩn bây giờ.
                <button onClick={() => run('ng_check_cancel', { machine }, 'Đã dừng kiểm tra')} className="ml-2 text-xs underline">Huỷ</button>
                {sim && (
                  <button onClick={() => run('sim_inject', { machine, count: ng.expected - ng.done }, 'Máy mô phỏng sẽ chạy chi tiết lỗi')}
                    className="ml-2 text-xs font-medium bg-violet-700 text-white rounded px-2 py-1 hover:bg-violet-800">Mô phỏng: chạy {ng.expected - ng.done} chi tiết lỗi</button>
                )}
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <label className="text-xs text-slate-600" htmlFor={`ng-${machine}`}>Số mẫu</label>
                <select id={`ng-${machine}`} value={n} onChange={(e) => setN(e.target.value)} className="border border-slate-300 rounded-md px-2 py-1.5 text-sm">
                  {[1, 2, 3, 4, 5].map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
                <button onClick={() => run('ng_check_start', { machine, recipe: '*', expected: Number(n) }, `Chờ ${n} mẫu NG`)}
                  className="text-xs font-medium bg-brand-600 text-white rounded-md px-3 py-1.5 hover:bg-brand-700">Bắt đầu kiểm tra</button>
              </div>
            )}
            {f.checks.length > 0 && (
              <ul className="mt-3 space-y-1.5 text-xs">
                {f.checks.slice(0, 5).map((k) => {
                  const ok = k.caught === k.expected && k.done === k.expected;
                  return (
                    <li key={k.id} className="flex items-center justify-between gap-2">
                      <span className="text-slate-500 tabular-nums">{tsDate(k.started)}{k.note ? ` · ${k.note}` : ''}</span>
                      <span className={`rounded-full px-2 py-0.5 border tabular-nums ${ok ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
                        AI bắt {k.caught}/{k.done}{k.done < k.expected ? ` (dừng ở ${k.done}/${k.expected})` : ''}{ok ? ' ✓' : ''}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="border border-slate-200 rounded-lg p-4">
            <div className="text-sm font-medium text-slate-900 inline-flex items-center gap-2"><SearchX size={15} /> Báo lỗi AI bỏ sót</div>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">Trạm kiểm tra cuối chuyền hay công nhân phát hiện một chi tiết lỗi mà AI không cảnh báo?
              Chọn {p.cycle} đó để tính vào "Lỗi AI bắt được". Trên hộp gateway: bấm nút NG khi không có cảnh báo nào đang mở.</p>
            {!missOpen ? (
              <button onClick={() => { setMissOpen(true); setMissId(cand[0] ? String(cand[0].id) : ''); }} disabled={!cand.length}
                className="mt-3 text-xs border border-amber-300 text-amber-900 rounded-md px-3 py-1.5 hover:bg-amber-50 disabled:opacity-50">
                Ghi một lỗi AI bỏ sót</button>
            ) : (
              <form className="mt-3 flex flex-wrap gap-2 items-end" onSubmit={(e) => {
                e.preventDefault();
                if (!missId) return;
                run('report_missed', { machine, cycle_id: Number(missId), fault_type: missType.trim() || null }, 'Đã ghi lỗi AI bỏ sót');
                setMissOpen(false); setMissType('');
              }}>
                <label className="text-xs text-slate-600" htmlFor={`mi-${machine}`}>{cap(p.cycle)}
                  <select id={`mi-${machine}`} value={missId} onChange={(e) => setMissId(e.target.value)} className="mt-1 block border border-slate-300 rounded-md px-2 py-1.5 text-sm">
                    {cand.map((x) => <option key={x.id} value={x.id}>{tsClock(x.ts)} · điểm {x.norm?.toFixed(2) ?? '—'}{x.recipe !== '*' ? ` · ${x.recipe}` : ''}</option>)}
                  </select>
                </label>
                <label className="text-xs text-slate-600" htmlFor={`mt-${machine}`}>Loại lỗi
                  <input id={`mt-${machine}`} list={`mtl-${machine}`} value={missType} onChange={(e) => setMissType(e.target.value)}
                    placeholder={p.faults[0] ?? 'vd. Thiếu phôi'} className="mt-1 block border border-slate-300 rounded-md px-2 py-1.5 text-sm w-44" />
                  <datalist id={`mtl-${machine}`}>{p.faults.map((k) => <option key={k} value={k} />)}</datalist>
                </label>
                <button type="submit" className="text-xs font-medium bg-brand-600 text-white rounded-md px-3 py-2 hover:bg-brand-700">Lưu</button>
                <button type="button" onClick={() => setMissOpen(false)} className="text-xs text-slate-500 px-1 py-2">Huỷ</button>
              </form>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
