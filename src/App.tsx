import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, Gauge, ScanSearch, Cable, Lock, Radio } from 'lucide-react';
import { MachineRuntime } from './types';
import { MACHINES } from './data/machines';
import { proc } from './utils/detector';
import {
  initRuntime, prefill, step, clock,
  applyExternalState, applyExternalCycle, accrueAll,
} from './utils/sim';
import { connectMqtt, ConnStatus } from './utils/mqtt';
import { MonitorTab } from './components/MonitorTab';
import { OeeTab } from './components/OeeTab';
import { DetectionTab } from './components/DetectionTab';
import { ConnectTab } from './components/ConnectTab';
import { ToastContainer, ToastMessage } from './components/Toast';

const MQTT_URL = (import.meta as any).env?.VITE_MQTT_URL || 'ws://localhost:9001';
const GW_ID = '01';
const TICK_MS = 250;

type TabId = 'monitor' | 'oee' | 'detect' | 'connect';

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'monitor', label: 'Giám sát máy', icon: Activity },
  { id: 'oee', label: 'OEE và dừng máy', icon: Gauge },
  { id: 'detect', label: 'Phát hiện bất thường', icon: ScanSearch },
  { id: 'connect', label: 'Kết nối và chi phí', icon: Cable },
];

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
  const [selected, setSelected] = useState(MACHINES[0].id);
  const [conn, setConn] = useState<ConnStatus>('connecting');
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const connRef = useRef<ConnStatus>('connecting');

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
        const m = MACHINES.find((x) => x.id === id);
        const r = rtRef.current![id];
        if (m && r) applyExternalCycle(m, r, nowRef.current, p.y, p.f);
      },
    });
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

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-5 lg:px-8 pt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Smart PLC Gateway</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Đọc dữ liệu từ PLC đời cũ, không đụng vào máy — đề D1, DENSO Factory Hacks 2026
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 pb-0.5 text-xs">
            <span className="font-mono text-slate-600 tabular-nums px-2">{clock(now)}</span>
            {errors > 0 && (
              <span className="flex items-center gap-1.5 bg-rose-50 text-rose-700 border border-rose-200 rounded-md px-2.5 py-1 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                {errors} máy đang báo lỗi
              </span>
            )}
            <span className="flex items-center gap-1.5 border border-slate-200 text-slate-600 rounded-md px-2.5 py-1"
              title="Gateway chỉ gửi lệnh đọc, không có lệnh ghi nào tới PLC">
              <Lock size={12} /> Chỉ đọc
            </span>
            <span className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 border ${
              conn === 'connected'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-slate-50 text-slate-600 border-slate-200'
            }`} title={conn === 'connected' ? MQTT_URL : 'Không có broker, đang dùng dữ liệu mô phỏng'}>
              <Radio size={12} />
              {conn === 'connected' ? 'Đã nối gateway' : conn === 'connecting' ? 'Đang nối…' : 'Chế độ mô phỏng'}
            </span>
          </div>
        </div>

        <nav className="max-w-7xl mx-auto px-5 lg:px-8 mt-3 flex gap-1 overflow-x-auto" aria-label="Các màn hình">
          {TABS.map((t) => {
            const Icon = t.icon;
            const on = tab === t.id;
            return (
              <button key={t.id} onClick={() => setTab(t.id)} aria-current={on ? 'page' : undefined}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm border-b-2 whitespace-nowrap transition-colors
                  focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-slate-900 ${
                  on ? 'border-slate-900 text-slate-900 font-medium'
                     : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
                <Icon size={15} /> {t.label}
              </button>
            );
          })}
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-5 lg:px-8 py-6">
        {tab === 'monitor' && (
          <MonitorTab rt={rt} now={now} selected={selected} onSelect={setSelected}
            onInjectFault={injectFault} onForceStop={forceStop} live={conn === 'connected'} />
        )}
        {tab === 'oee' && <OeeTab rt={rt} now={now} />}
        {tab === 'detect' && <DetectionTab />}
        {tab === 'connect' && <ConnectTab />}

        <footer className="mt-10 pt-5 border-t border-slate-200 text-xs text-slate-500 leading-relaxed max-w-3xl">
          {conn === 'connected'
            ? 'Trạng thái máy và chu kỳ gia công đang đến từ gateway qua MQTT.'
            : 'Chưa có PLC thật nên trạng thái máy là mô phỏng. Đường cong mỗi chu kỳ lấy từ tập kiểm tra của ml/cycles.py, và điểm bất thường tính bằng đúng mô hình đã huấn luyện.'}
        </footer>
      </main>

      <ToastContainer toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  );
}
