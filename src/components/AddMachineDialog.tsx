import React, { useEffect, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import type { Ack } from '../utils/mqtt';
import { low, type MachineCfg, type Profile, type Template } from '../utils/edge';

interface Props {
  templates: Record<string, Template>;
  profiles: Record<string, Profile>;
  existing: string[];
  onClose: () => void;
  onSubmit: (cfg: Record<string, unknown>) => Promise<Ack>;
}

const STATE_VI: [string, string][] = [
  ['STOPPED', 'Dừng'], ['READY', 'Chuẩn bị'], ['AUTO', 'Auto'], ['WORKING', 'Đang làm việc'], ['DONE', 'Hoàn thành'], ['ERROR', 'Báo lỗi'],
];

function nextId(existing: string[]) {
  for (let i = 1; i < 100; i++) {
    const id = `M${String(i).padStart(2, '0')}`;
    if (!existing.includes(id)) return id;
  }
  return 'M99';
}

/** Form khai báo máy mới. Chọn mẫu → sửa vài ô → gửi. Runtime kiểm tra lại và trả lỗi bằng tiếng Việt. */
export function AddMachineDialog({ templates, profiles, existing, onClose, onSubmit }: Props) {
  const keys = Object.keys(templates);
  // Loại máy lấy từ các mẫu runtime gửi lên; mỗi loại có mẫu PLC Mitsubishi và (nếu có) mẫu mô phỏng
  const types = useMemo(() => [...new Set(keys.map((k) => templates[k].machine_type).filter(Boolean))] as string[], [templates]);
  const keyOf = (t: string, sim: boolean) => keys.find((k) => templates[k].machine_type === t && (templates[k].driver === 'simulator') === sim);
  const firstKey = keyOf(types[0] ?? '', false) ?? keys[0];
  const [tpl, setTpl] = useState(firstKey);
  const [f, setF] = useState<MachineCfg>(() => ({ ...templates[firstKey].cfg, id: nextId(existing), name: '' }));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLSelectElement>(null);

  useEffect(() => { first.current?.focus(); }, []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onClose]);

  const pick = (k: string) => {
    setTpl(k);
    setF((cur) => ({ ...templates[k].cfg, id: cur.id, name: cur.name, line: cur.line }));
  };
  const sim = f.plc.driver === 'simulator';
  const mtype = templates[tpl]?.machine_type ?? '';
  const prof = profiles[mtype];
  const canSim = !!keyOf(mtype, true);
  const set = (path: string, v: unknown) => setF((cur) => {
    const n: any = structuredClone(cur);
    const ks = path.split('.');
    let o = n;
    ks.slice(0, -1).forEach((k) => { o = o[k] ??= {}; });
    o[ks[ks.length - 1]] = v;
    return n;
  });
  const bits = useMemo(() => f.state.bits ?? {}, [f]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    const a = await onSubmit({ ...f, name: f.name || f.id });
    setBusy(false);
    if (!a.ok) setErr(a.error ?? 'Không thêm được máy');
  };

  const inp = 'mt-1 w-full border border-slate-300 rounded px-2 py-1.5 text-sm';
  const lab = 'block text-xs text-slate-600';
  return (
    <div className="fixed inset-0 z-40 bg-slate-900/40 flex items-start sm:items-center justify-center p-4 overflow-y-auto" role="dialog"
      aria-modal="true" aria-labelledby="add-title" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form onSubmit={submit} className="bg-white rounded-lg shadow-xl w-full max-w-2xl my-8">
        <header className="px-5 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
          <div>
            <h2 id="add-title" className="text-base font-semibold text-slate-900">Thêm máy</h2>
            <p className="text-xs text-slate-500 mt-0.5">Gateway bắt đầu đọc và tự học chuẩn bình thường ngay sau khi lưu. Chỉ có lệnh đọc tới PLC.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Đóng" className="text-slate-400 hover:text-slate-700"><X size={18} /></button>
        </header>

        <div className="px-5 py-4 space-y-5">
          {types.length ? (
            <div className="grid sm:grid-cols-2 gap-3">
              <label className={lab} htmlFor="mtype">Loại máy
                <select id="mtype" ref={first} value={mtype} className={inp}
                  onChange={(e) => pick(keyOf(e.target.value, sim) ?? keyOf(e.target.value, false)!)}>
                  {types.map((t) => <option key={t} value={t}>{profiles[t]?.label ?? t}</option>)}
                </select>
              </label>
              <label className={lab} htmlFor="drv">Nguồn dữ liệu
                <select id="drv" value={sim ? 'sim' : 'plc'} className={inp}
                  onChange={(e) => pick(keyOf(mtype, e.target.value === 'sim') ?? tpl)}>
                  <option value="plc">PLC Mitsubishi Q/L · MC protocol 3E</option>
                  <option value="sim" disabled={!canSim}>Mô phỏng (không cần PLC){canSim ? '' : ' · chưa có cho loại này'}</option>
                  <option value="omron" disabled>Omron FINS · đang làm</option>
                  <option value="keyence" disabled>Keyence KV · đang làm</option>
                </select>
              </label>
              {prof && (
                <p className="sm:col-span-2 text-[11px] text-slate-500 leading-relaxed">
                  Dashboard sẽ gọi tín hiệu là <b>{low(prof.signal)}</b>{prof.unit ? ` (${prof.unit})` : ''}, mỗi chu kỳ là
                  một <b>{prof.cycle}</b>, mã hàng là <b>{low(prof.recipe)}</b>
                  {prof.faults.length ? <>, gợi ý loại lỗi: {prof.faults.join(', ')}</> : ''}. Thuật toán AI giống nhau cho mọi loại máy.
                </p>
              )}
            </div>
          ) : (
            <label className={lab} htmlFor="tpl">Mẫu
              <select id="tpl" ref={first as React.Ref<HTMLSelectElement>} value={tpl} onChange={(e) => pick(e.target.value)} className={inp}>
                {keys.map((k) => <option key={k} value={k}>{templates[k].label}</option>)}
              </select>
            </label>
          )}

          <fieldset className="grid sm:grid-cols-3 gap-3">
            <legend className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Máy</legend>
            <label className={lab} htmlFor="mid">Mã máy<input id="mid" required value={f.id} onChange={(e) => set('id', e.target.value.toUpperCase())} className={`${inp} font-mono`} /></label>
            <label className={`${lab} sm:col-span-2`} htmlFor="mname">Tên<input id="mname" value={f.name} placeholder={`vd. ${prof?.label ?? 'Máy'} số 3`} onChange={(e) => set('name', e.target.value)} className={inp} /></label>
            <label className={lab} htmlFor="mline">Chuyền<input id="mline" value={f.line ?? ''} placeholder="vd. Line 2" onChange={(e) => set('line', e.target.value)} className={inp} /></label>
          </fieldset>

          {!sim && (
            <fieldset className="grid sm:grid-cols-3 gap-3">
              <legend className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">PLC (MC protocol 3E, khung nhị phân)</legend>
              <label className={lab} htmlFor="ip">IP<input id="ip" required value={f.plc.ip} onChange={(e) => set('plc.ip', e.target.value)} className={`${inp} font-mono`} /></label>
              <label className={lab} htmlFor="port">Cổng (thập phân)<input id="port" type="number" required value={f.plc.port} onChange={(e) => set('plc.port', Number(e.target.value))} className={`${inp} font-mono`} /></label>
              <label className={lab} htmlFor="ptype">Dòng PLC
                <select id="ptype" value={f.plc.plctype ?? 'Q'} onChange={(e) => set('plc.plctype', e.target.value)} className={inp}>
                  <option value="Q">Q series</option><option value="L">L series</option><option value="iQ-R">iQ-R</option>
                </select>
              </label>
              <p className="sm:col-span-3 text-[11px] text-slate-500">GX Works2 nhập cổng bằng hex nếu ô Input Format là HEX (1388 hex = 5000). Mỗi dòng Open Setting chỉ nhận một kết nối.</p>
            </fieldset>
          )}

          <fieldset className="grid sm:grid-cols-4 gap-3">
            <legend className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Tín hiệu quá trình</legend>
            {!sim && <label className={lab} htmlFor="reg">Thanh ghi {prof ? low(prof.signal) : ''}<input id="reg" value={f.signal.register} onChange={(e) => set('signal.register', e.target.value.toUpperCase())} className={`${inp} font-mono`} /></label>}
            {!sim && <label className={lab} htmlFor="scale">Hệ số<input id="scale" type="number" step="any" value={f.signal.scale} onChange={(e) => set('signal.scale', Number(e.target.value))} className={`${inp} font-mono`} /></label>}
            <label className={lab} htmlFor="unit">Đơn vị<input id="unit" value={f.signal.unit ?? ''} onChange={(e) => set('signal.unit', e.target.value)} className={inp} /></label>
            <label className={lab} htmlFor="vmax">Giới hạn trên<input id="vmax" type="number" step="any" value={f.signal.max ?? ''} placeholder="không"
              onChange={(e) => set('signal.max', e.target.value === '' ? null : Number(e.target.value))} className={`${inp} font-mono`} /></label>
          </fieldset>

          {!sim && (
            <fieldset className="space-y-3">
              <legend className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Trạng thái máy và cắt chu kỳ</legend>
              <div className="grid sm:grid-cols-4 gap-3">
                <label className={lab} htmlFor="sreg">Word trạng thái<input id="sreg" value={f.state.register} onChange={(e) => set('state.register', e.target.value.toUpperCase())} className={`${inp} font-mono`} /></label>
                <label className={lab} htmlFor="ereg">Thanh ghi mã lỗi<input id="ereg" value={f.error_register ?? ''} placeholder="không"
                  onChange={(e) => set('error_register', e.target.value.toUpperCase() || null)} className={`${inp} font-mono`} /></label>
                <label className={lab} htmlFor="rreg">Thanh ghi {low(prof?.recipe ?? 'mã hàng')}<input id="rreg" value={f.recipe_register ?? ''} placeholder="không"
                  onChange={(e) => set('recipe_register', e.target.value.toUpperCase() || null)} className={`${inp} font-mono`} /></label>
                <label className={lab} htmlFor="seg">Cắt chu kỳ
                  <select id="seg" value={f.segment.mode} onChange={(e) => set('segment.mode', e.target.value)} className={inp}>
                    <option value="bit">Theo bit đang làm việc</option><option value="window">Theo khung thời gian</option>
                  </select>
                </label>
              </div>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                {STATE_VI.map(([k, vi]) => (
                  <label key={k} className={lab} htmlFor={`bit-${k}`}>{vi}
                    <input id={`bit-${k}`} type="number" min={0} max={15} value={bits[k] ?? ''} placeholder="—"
                      onChange={(e) => set(`state.bits.${k}`, e.target.value === '' ? null : Number(e.target.value))}
                      className={`${inp} font-mono`} />
                  </label>
                ))}
              </div>
              <p className="text-[11px] text-slate-500">Số thứ tự bit trong word trạng thái (0–15). Có thanh ghi {low(prof?.recipe ?? 'mã hàng')} thì mỗi {low(prof?.recipe ?? 'mã hàng')} tự học một chuẩn riêng.</p>
            </fieldset>
          )}

          <fieldset className="grid sm:grid-cols-3 gap-3">
            <legend className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">AI</legend>
            <label className={lab} htmlFor="lt">Số chu kỳ cần học<input id="lt" type="number" min={30} value={f.ai.learn_target} onChange={(e) => set('ai.learn_target', Number(e.target.value))} className={`${inp} tabular-nums`} /></label>
            <label className={lab} htmlFor="re">Học lại sau mỗi<input id="re" type="number" min={50} value={f.ai.retrain_every} onChange={(e) => set('ai.retrain_every', Number(e.target.value))} className={`${inp} tabular-nums`} /></label>
            <p className="text-[11px] text-slate-500 self-end">300 chu kỳ ≈ 1 ca ở máy chu kỳ 60–90 giây. Nên học qua 2 ca nếu được.</p>
          </fieldset>

          {err && <div role="alert" className="text-sm bg-rose-50 border border-rose-200 text-rose-800 rounded-md px-3 py-2">{err}</div>}
        </div>

        <footer className="px-5 py-3 border-t border-slate-100 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="text-sm border border-slate-300 rounded-md px-3.5 py-2 hover:bg-slate-50">Huỷ</button>
          <button type="submit" disabled={busy}
            className="text-sm font-medium bg-slate-900 text-white rounded-md px-3.5 py-2 hover:bg-slate-700 disabled:opacity-60">
            {busy ? 'Đang gửi…' : 'Lưu và bắt đầu học'}
          </button>
        </footer>
      </form>
    </div>
  );
}
