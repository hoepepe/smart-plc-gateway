/**
 * Kiểu dữ liệu và kho trạng thái cho runtime edge (python -m edge.runtime):
 * mỗi máy tự học chuẩn bình thường tại chỗ → kỹ sư duyệt → giám sát → nhận phản hồi → học lại.
 */
import type { CyclePayload } from './mqtt';

export type Mode = 'learning' | 'review' | 'monitoring';

export interface ModelInfo {
  version: number; kind: string; note: string; created: number;
  n_train: number; n_calib: number; n_dropped?: number; calib_false_alarm?: number;
  t_maha: number; t_robz: number; duration_med?: number;
  shift?: number | null; shift_origin?: number | null; warn?: boolean;
}

export interface VersionRow { version: number; status: 'pending' | 'active' | 'retired' | 'rejected'; kind: string; note: string; created: number }

export interface RecipeStatus {
  recipe: string; mode: Mode;
  learned: number; target: number; excluded_error: number; excluded_dq: number;
  monitored: number; flagged: number; since_retrain: number; retrain_every: number;
  active?: ModelInfo; pending?: ModelInfo; versions: VersionRow[];
}

export interface TopFeature { feature: string; vi: string; z: number; value: number; normal: number }

export interface EdgeAlarm {
  id: number; machine: string; recipe: string; ts: number; cycle_id: number; norm: number;
  top: TopFeature[]; status: 'open' | 'fault' | 'false_alarm' | 'new_normal';
  fault_type: string | null; suggestion: { type: string; prob: number } | null; resolved: number | null;
}

export interface LearnStatus {
  machine: string; recipes: RecipeStatus[]; open_alarms: number;
  classifier: {
    n: number; types: Record<string, number>; need_total: number; need_per_type: number; ready: boolean;
    machine_type?: string; shared_machines?: number; own?: number;
  };
  last_dq: { ts: number; issues: string[] } | null;
  ai: { learn_target: number; retrain_every: number; auto_approve: boolean; [k: string]: unknown };
  conn: { ok: boolean; msg: string; ts?: number }; state: string | null;
  cycles_seen: number; ts: number; alarms: EdgeAlarm[];
}

export interface Profile {
  label: string; icon: string; signal: string; unit: string; cycle: string; recipe: string;
  features: Record<string, string>; faults: string[]; sim: boolean;
}

export interface MachineCfg {
  id: string; name: string; line: string; process: string; machine_type?: string;
  plc: { driver: 'mitsubishi_mc' | 'simulator'; ip: string; port: number; plctype?: string };
  signal: { register: string; scale: number; unit: string; min: number | null; max: number | null };
  state: { register: string; bits: Record<string, number> };
  error_register: string | null; recipe_register: string | null;
  segment: { mode: 'bit' | 'window'; window_s: number };
  rate_hz: number;
  ai: { learn_target: number; retrain_every: number; auto_approve: boolean };
  simulator?: Record<string, unknown>;
}

export interface Template { label: string; machine_type?: string; driver?: string; cfg: MachineCfg }

export interface Registry {
  machines: MachineCfg[]; templates: Record<string, Template>; profiles?: Record<string, Profile>; ts?: number;
}

const GENERIC: Profile = {
  label: 'Máy khác', icon: 'generic', signal: 'Tín hiệu quá trình', unit: '', cycle: 'chu kỳ', recipe: 'Mã hàng',
  features: {}, faults: [], sim: false,
};

/** Hồ sơ loại máy: dashboard đổi tên tín hiệu, đơn vị, cách gọi chu kỳ, mã hàng, đặc trưng, gợi ý lỗi theo loại máy. */
export function profileOf(reg: Registry | null, cfg?: MachineCfg): Profile {
  const p = (cfg?.machine_type && reg?.profiles?.[cfg.machine_type]) || GENERIC;
  return { ...p, unit: cfg?.signal.unit || p.unit };
}

export interface EdgeCycle {
  ts: number; kind: string; mode?: Mode; recipe: string; norm?: number; flag?: boolean;
  alarm_id?: number; y: number[]; issues?: string[]; injected?: string; top?: TopFeature[];
}

export interface EdgeState {
  online: boolean | null;
  registry: Registry | null;
  learn: Record<string, LearnStatus>;
  cycles: Record<string, EdgeCycle[]>;
}

export const KEEP = 240;

export const emptyEdge = (): EdgeState => ({ online: null, registry: null, learn: {}, cycles: {} });

export function pushCycle(e: EdgeState, id: string, p: CyclePayload) {
  const sc = typeof p.score === 'object' && p.score ? p.score : undefined;
  const c: EdgeCycle = {
    ts: p.ts, kind: p.kind || 'score', mode: p.mode, recipe: p.recipe || '*',
    norm: p.norm ?? sc?.norm, flag: sc?.flag, alarm_id: p.alarm_id,
    y: p.y || [], issues: p.issues, injected: p.injected, top: sc?.top,
  };
  const arr = (e.cycles[id] ||= []);
  arr.push(c);
  if (arr.length > KEEP) arr.splice(0, arr.length - KEEP);
}

export const ISSUE_VI: Record<string, string> = {
  too_short: 'chu kỳ quá ngắn',
  frozen: 'tín hiệu đứng im',
  out_of_range: 'vượt dải vật lý',
  gaps: 'đọc PLC bị hụt mẫu',
};

export const MODE_META: Record<Mode, { label: string; cls: string; dot: string }> = {
  learning: { label: 'Đang học', cls: 'bg-brand-50 text-brand-700 border-brand-100', dot: 'bg-brand-500' },
  review: { label: 'Chờ duyệt', cls: 'bg-amber-50 text-amber-900 border-amber-200', dot: 'bg-amber-500' },
  monitoring: { label: 'Đang giám sát', cls: 'bg-emerald-50 text-emerald-800 border-emerald-200', dot: 'bg-emerald-500' },
};

/** Chế độ đại diện cho cả máy: có mã hàng chờ duyệt → chờ duyệt; còn đang học → đang học; còn lại giám sát. */
export function machineMode(s?: LearnStatus): Mode | null {
  if (!s || !s.recipes.length) return null;
  const modes = s.recipes.map((r) => r.mode);
  if (modes.includes('review')) return 'review';
  if (modes.includes('learning')) return 'learning';
  return 'monitoring';
}

export const tsClock = (ms: number) =>
  new Date(ms > 1e12 ? ms : ms * 1000).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const tsDate = (s: number) =>
  new Date(s * 1000).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });

export const recipeLabel = (r: string) => (r === '*' ? 'Mặc định' : r);

export const KIND_VI: Record<string, string> = {
  initial: 'Học lần đầu', drift: 'Học lại định kỳ', new_normal: 'Thêm chế độ mới', relearn: 'Học lại',
};

export const STATUS_VI: Record<VersionRow['status'], string> = {
  pending: 'Chờ duyệt', active: 'Đang chạy', retired: 'Đã thay', rejected: 'Bỏ qua',
};

/** Viết thường chữ đầu nhưng giữ chữ viết tắt: "Chương trình NC" → "chương trình NC". */
export const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1);
