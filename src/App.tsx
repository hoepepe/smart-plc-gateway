import React, { useCallback, useEffect, useRef, useState } from 'react';
import { LayoutDashboard, Gauge, ScanSearch, Cable, BrainCircuit, Activity, BellRing, CircleGauge, Plus } from 'lucide-react';
import { MachineRuntime } from './types';
import { MACHINES } from './data/machines';
import { proc } from './utils/detector';
import {
  initRuntime, prefill, step, clock,
  applyExternalState, applyExternalCycle, accrueAll,
} from './utils/sim';
import { connectMqtt, ConnStatus, MqttConn, Ack } from './utils/mqtt';
import { EdgeState, LearnStatus, emptyEdge, pushCycle } from './utils/edge';
import sampleEdge from './data/edge_sample.json';
import { FleetTab } from './components/FleetTab';
import { MonitorTab } from './components/MonitorTab';
import { OeeTab } from './components/OeeTab';
import { DetectionTab } from './components/DetectionTab';
import { ConnectTab } from './components/ConnectTab';
import { ToastContainer, ToastMessage } from './components/Toast';
import { Sidebar, Topbar, PageHeader, DateChip, PrimaryButton, KpiCard, NavItem, Notice } from './components/Shell';
import { computeOee } from './utils/oee';

const MQTT_URL = (import.meta as any).env?.VITE_MQTT_URL || 'ws://localhost:9001';
const GW_ID = '01';
const TICK_MS = 250;

type TabId = 'monitor' | 'fleet' | 'oee' | 'detect' | 'connect';

const TABS: { id: TabId; label: string; icon: React.ElementType; title: string; sub: string }[] = [
  { id: 'monitor', label: 'Tổng quan', icon: LayoutDashboard, title: '', sub: 'Đây là những gì cần chú ý trên các máy lúc này.' },
  { id: 'fleet', label: 'Máy và AI tự học', icon: BrainCircuit, title: 'Máy và AI tự học',
    sub: 'Mỗi máy tự học chuẩn bình thường của riêng nó, kỹ sư duyệt rồi mới giám sát.' },
  { id: 'oee', label: 'OEE và dừng máy', icon: Gauge, title: 'OEE và dừng máy', sub: 'Độ sẵn sàng × hiệu suất × chất lượng, và nguyên nhân dừng máy xếp theo thời gian mất.' },
  { id: 'detect', label: 'Kiểm chứng AI', icon: ScanSearch, title: 'Kiểm chứng độ chính xác AI', sub: 'So với giới hạn PLC trên cùng dữ liệu — mô phỏng 4 loại máy, dữ liệu thật Bosch và PLC thật.' },
  { id: 'connect', label: 'Kết nối và chi phí', icon: Cable, title: 'Kết nối và chi phí', sub: 'Gateway chỉ đọc, không đụng vào máy — và rẻ hơn nhiều so với thay PLC.' },
];

function greeting() {
  const h = new Date().getHours();
  return h < 11 ? 'Chào buổi sáng' : h < 13 ? 'Chào buổi trưa' : h < 18 ? 'Chào buổi chiều' : 'Chào buổi tối';
}

export default function App() {
  // Trạng thái vận hành được cập nhật tại chỗ trong ref (nhanh, không sao chép),
  // còn `tick` chỉ để báo React vẽ lại.
  const rtRef = useRef<Record<string, MachineRuntime> | null>(null);
  const nowRef = useRef(0);
  if (!rtRef.current) {
    rtRef.current = initRuntime();
    nowRef.current = prefill(rtRef.current);
  }
  const [, setTick] = useState(0);
  const [tab, setTab] = useState<TabId>('monitor');
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [addSignal, setAddSignal] = useState(0);
  const go = (t: TabId) => { setTab(t); setMobileNav(false); };
  const addMachine = () => { go('fleet'); setAddSignal((k) => k + 1); };
  // Mở thẳng một máy qua đường link, ví dụ http://192.168.10.10:3000/?may=M02
  // — đây là đường link nằm trong mã QR hiện trên OLED của gateway gắn ở máy đó.
  const [selected, setSelected] = useState(() => {
    const may = new URLSearchParams(window.location.search).get('may');
    return MACHINES.some((m) => m.id === may) ? (may as string) : MACHINES[0].id;
  });

  // Đổi máy thì cập nhật đường link, để kỹ sư gửi link cho người khác vẫn mở đúng máy
  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set('may', selected);
    window.history.replaceState(null, '', url);
  }, [selected]);
  const [conn, setConn] = useState<ConnStatus>('connecting');
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const connRef = useRef<ConnStatus>('connecting');
  // Trạng thái runtime edge (AI tự học tại chỗ) — cập nhật tại chỗ, vẽ lại theo nhịp `tick`
  const edgeRef = useRef<EdgeState>(emptyEdge());
  const mqttRef = useRef<MqttConn | null>(null);
  const send = useCallback(async (op: string, body?: Record<string, unknown>): Promise<Ack> =>
    mqttRef.current ? mqttRef.current.send(op, body) : { id: '', ok: false, error: 'Chưa nối gateway' }, []);

  const notify = useCallback((type: ToastMessage['type'], title: string, description?: string) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t.slice(-3), { id, type, title, description }]);
  }, []);

  // Vòng lặp chính: chế độ mô phỏng thì tự sinh sự kiện,
  // có gateway thật thì chỉ cộng dồn thời gian, sự kiện đến từ MQTT.
  useEffect(() => {
    let last = performance.now();
    const id = setInterval(() => {
      const t = performance.now();
      const dt = Math.min(1, (t - last) / 1000);
      last = t;
      nowRef.current += dt;
      if (connRef.current === 'connected') accrueAll(rtRef.current!, nowRef.current);
      else step(rtRef.current!, nowRef.current, dt, true);
      setTick((k) => k + 1);
    }, TICK_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const c = connectMqtt(MQTT_URL, GW_ID, {
      onStatus: (s) => {
        connRef.current = s;
        setConn(s);
        if (s === 'connected') notify('success', 'Đã nối gateway', 'Trạng thái máy và chu kỳ giờ đến từ gateway qua MQTT.');
      },
      onState: (id, p) => {
        const r = rtRef.current![id];
        if (r) applyExternalState(r, p.state, nowRef.current, p.errorCode);
      },
      onCycle: (id, p) => {
        if (p.kind) { pushCycle(edgeRef.current, id, p); return; }   // bản tin từ runtime edge
        const m = MACHINES.find((x) => x.id === id);
        const r = rtRef.current![id];
        if (m && r && p.f?.length === 9) applyExternalCycle(m, r, nowRef.current, p.y, p.f);
      },
      onLearn: (id, p) => {
        if (p) edgeRef.current.learn[id] = p;
        else { delete edgeRef.current.learn[id]; delete edgeRef.current.cycles[id]; }
      },
      onRegistry: (p) => { edgeRef.current.registry = p; },
      onOnline: (on) => { edgeRef.current.online = on; },
    });
    mqttRef.current = c;
    return () => c.disconnect();
  }, [notify]);

  const injectFault = (machineId: string, fault: string) => {
    const m = MACHINES.find((x) => x.id === machineId)!;
    rtRef.current![machineId].pendingFault = fault;
    const vi = proc(m.process).metrics.faults.find((f) => f.code === fault)?.vi ?? fault;
    notify('warning', `${m.name}: chu kỳ kế tiếp mang lỗi`, vi);
  };

  const forceStop = (machineId: string) => {
    const m = MACHINES.find((x) => x.id === machineId)!;
    rtRef.current![machineId].pendingStop = true;
    notify('warning', `${m.name}: mô phỏng máy báo lỗi`, 'Máy sẽ dừng, rồi chuẩn bị vận hành lại.');
  };

  const rt = rtRef.current!;
  const now = nowRef.current;
  const errors = MACHINES.filter((m) => rt[m.id].state === 'ERROR').length;

  const edge = conn === 'demo' ? (sampleEdge as unknown as EdgeState) : edgeRef.current;
  const learns = Object.values(edge.learn).filter(Boolean) as LearnStatus[];
  const openAlarms = learns.reduce((n, l) => n + (l?.open_alarms ?? 0), 0);
  const fleetN = edge.registry?.machines.length ?? 0;

  // Thông báo trên chuông: máy đang báo lỗi, mô hình chờ duyệt, cảnh báo AI chưa xử lý
  const notices: Notice[] = [
    ...MACHINES.filter((m) => rt[m.id].state === 'ERROR').map((m) => ({
      id: `err-${m.id}`, tone: 'red' as const, title: `${m.name} đang báo lỗi`,
      sub: `${m.id}${rt[m.id].errorCode ? ` · mã ${rt[m.id].errorCode}` : ''} · bấm để xem dòng thời gian`,
      go: () => { setSelected(m.id); go('monitor'); },
    })),
    ...learns.flatMap((l) => l.recipes.filter((x) => x.mode === 'review').map((x) => ({
      id: `rev-${l.machine}-${x.recipe}`, tone: 'blue' as const, title: `${l.machine} đã học xong, chờ kỹ sư duyệt`,
      sub: `${x.recipe === '*' ? '' : `${x.recipe} · `}học ${x.learned} chu kỳ`, go: () => go('fleet'),
    }))),
    ...learns.filter((l) => l.open_alarms > 0).map((l) => ({
      id: `al-${l.machine}`, tone: 'amber' as const, title: `${l.machine}: ${l.open_alarms} cảnh báo AI chưa xử lý`,
      sub: 'Bấm Đúng là lỗi / Báo nhầm / Bình thường mới để AI học tiếp', go: () => go('fleet'),
    })),
  ];

  const nav: NavItem[] = TABS.map((t) => ({
    id: t.id, label: t.label, icon: t.icon,
    badge: t.id === 'monitor' && errors > 0 ? { text: String(errors), tone: 'red' }
      : t.id === 'fleet' && fleetN > 0 ? { text: String(fleetN), tone: openAlarms ? 'blue' : 'gray' } : undefined,
  }));
  const cur = TABS.find((t) => t.id === tab)!;

  // Chỉ số tổng quan
  const oees = MACHINES.map((m) => computeOee(m, rt[m.id]));
  const avg = (k: 'oee' | 'availability' | 'quality') => oees.reduce((a, o) => a + o[k], 0) / oees.length;
  const running = MACHINES.filter((m) => ['AUTO', 'WORKING', 'DONE'].includes(rt[m.id].state)).length;
  const cycles = MACHINES.reduce((n, m) => n + rt[m.id].totalCycles, 0);
  const bad = MACHINES.reduce((n, m) => n + rt[m.id].anomalousCycles, 0);
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="min-h-screen bg-canvas text-slate-900">
      <Sidebar items={nav} active={tab} onNav={(id) => go(id as TabId)} onPrimary={addMachine}
        collapsed={collapsed} mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <div className={`transition-[padding] duration-200 ${collapsed ? 'lg:pl-[76px]' : 'lg:pl-64'}`}>
        <Topbar title={cur.label}
          onToggle={() => (window.matchMedia('(min-width: 1024px)').matches ? setCollapsed((v) => !v) : setMobileNav(true))}
          clock={clock(now)} live={conn === 'connected'}
          connLabel={conn === 'connected' ? 'Đã nối gateway' : conn === 'connecting' ? 'Đang nối…' : 'Chế độ mô phỏng'}
          connTitle={conn === 'connected' ? MQTT_URL : 'Không có broker, đang dùng dữ liệu mô phỏng'}
          notices={notices} />

        <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-7">
          <PageHeader
            title={tab === 'monitor' ? `${greeting()}, UET-BigHero` : cur.title}
            sub={cur.sub}
            right={tab === 'monitor' ? <><DateChip /><PrimaryButton onClick={addMachine}><Plus size={16} /> Thêm máy</PrimaryButton></> : undefined} />

          {tab === 'monitor' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
              <KpiCard label="Máy đang chạy" value={`${running}/${MACHINES.length}`} icon={Activity}
                foot={errors ? `${errors} máy đang báo lỗi` : 'Không máy nào báo lỗi'} footTone={errors ? 'rose' : 'emerald'} />
              <KpiCard label="OEE trung bình" value={pct(avg('oee'))} icon={CircleGauge} tone="emerald"
                foot={`Sẵn sàng ${pct(avg('availability'))} · chất lượng ${pct(avg('quality'))}`} footTone="slate" onClick={() => go('oee')} />
              <KpiCard label="Chu kỳ đã đọc" value={cycles.toLocaleString('vi-VN')} icon={ScanSearch} tone="amber"
                foot={`${bad} chu kỳ bất thường (${cycles ? pct(bad / cycles) : '0%'})`} footTone="amber" onClick={() => go('detect')} />
              <KpiCard label="Cảnh báo AI chưa xử lý" value={openAlarms} icon={BellRing} tone="rose"
                foot={fleetN ? `Trên ${fleetN} máy tự học · bấm để phản hồi` : 'Chưa có máy tự học nào'} footTone="blue" onClick={() => go('fleet')} />
            </div>
          )}

          {tab === 'monitor' && (
            <MonitorTab rt={rt} now={now} selected={selected} onSelect={setSelected}
              onInjectFault={injectFault} onForceStop={forceStop} live={conn === 'connected'} />
          )}
          {tab === 'fleet' && (
            <FleetTab edge={edge} connected={conn === 'connected'} sample={conn === 'demo'} send={send} notify={notify}
              addSignal={addSignal} />
          )}
          {tab === 'oee' && <OeeTab rt={rt} now={now} />}
          {tab === 'detect' && <DetectionTab />}
          {tab === 'connect' && <ConnectTab />}

          <footer className="mt-10 pt-5 border-t border-slate-200 text-xs text-slate-500 leading-relaxed max-w-3xl">
            {conn === 'connected'
              ? 'Trạng thái máy và chu kỳ đang đến từ gateway qua MQTT.'
              : 'Chưa có PLC thật nên trạng thái máy là mô phỏng. Đường cong mỗi chu kỳ lấy từ tập kiểm tra của ml/cycles.py, và điểm bất thường tính bằng đúng mô hình đã huấn luyện.'}
          </footer>
        </main>
      </div>

      <ToastContainer toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  );
}
