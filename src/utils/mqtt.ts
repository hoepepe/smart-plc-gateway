import mqtt, { MqttClient } from 'mqtt';
import { MachineState } from '../types';

/**
 * Kết nối MQTT (WebSocket) tới broker trong mạng nội bộ.
 *
 * Gateway phát hai loại bản tin cho mỗi máy:
 *   gw/{gw}/m/{machineId}/state   — mỗi khi trạng thái máy thay đổi
 *   gw/{gw}/m/{machineId}/cycle   — mỗi khi một chu kỳ gia công kết thúc
 *
 * Không nối được broker sau 3 giây thì giao diện tự chạy chế độ mô phỏng.
 */

export interface StatePayload {
  ts: number;
  state: MachineState;
  errorCode?: string;
}

export interface CyclePayload {
  ts: number;
  y: number[];       // đường cong chu kỳ đọc từ thanh ghi PLC
  f: number[];       // đặc trưng, gateway tính sẵn theo đúng ml/cycles.py
  score?: number | EdgeScore;   // cầu nối cũ: số; runtime edge: điểm chi tiết
  // các trường dưới chỉ có khi chạy runtime edge (python -m edge.runtime)
  kind?: 'learn' | 'preview' | 'score' | 'dq' | 'excluded';
  mode?: 'learning' | 'review' | 'monitoring';
  recipe?: string;
  norm?: number;
  anomalous?: boolean;
  alarm_id?: number;
  n?: number;
  target?: number;
  version?: number;
  issues?: string[];
  reason?: string;
  injected?: string;
}

export interface EdgeScore {
  maha: number; robz: number; norm: number; flag: boolean;
  top: { feature: string; vi: string; z: number; value: number; normal: number }[];
}

export type ConnStatus = 'connecting' | 'connected' | 'demo';

export interface Handlers {
  onStatus: (s: ConnStatus) => void;
  onState?: (machineId: string, p: StatePayload) => void;
  onCycle?: (machineId: string, p: CyclePayload) => void;
  onLearn?: (machineId: string, p: any | null) => void;   // null = máy đã bị xoá
  onRegistry?: (p: any) => void;
  onOnline?: (online: boolean) => void;
}

export interface Ack { id: string; ok: boolean; op?: string; error?: string; result?: any }

export interface MqttConn {
  disconnect: () => void;
  /** Gửi lệnh tới runtime edge, chờ trả lời (ack) tối đa 8 giây */
  send: (op: string, body?: Record<string, unknown>) => Promise<Ack>;
}

export function connectMqtt(url: string, gwId: string, h: Handlers): MqttConn {
  const waiting = new Map<string, (a: Ack) => void>();
  let connected = false;
  let client: MqttClient | null = null;
  h.onStatus('connecting');

  const fallback = setTimeout(() => {
    if (!connected) {
      h.onStatus('demo');
      try { client?.end(true); } catch { /* bỏ qua */ }
    }
  }, 3000);

  try {
    client = mqtt.connect(url, { connectTimeout: 3000, reconnectPeriod: 0, clean: true });

    client.on('connect', () => {
      connected = true;
      clearTimeout(fallback);
      h.onStatus('connected');
      client?.subscribe([`gw/${gwId}/m/+/state`, `gw/${gwId}/m/+/cycle`, `gw/${gwId}/m/+/learn`,
        `gw/${gwId}/registry`, `gw/${gwId}/ack`, `gw/${gwId}/online`]);
    });

    client.on('message', (topic, msg) => {
      const parts = topic.split('/');
      const tail = parts[parts.length - 1];
      if (parts.length === 3) {
        try {
          const p = msg.length ? JSON.parse(msg.toString()) : null;
          if (tail === 'registry' && p) h.onRegistry?.(p);
          if (tail === 'online' && p) h.onOnline?.(!!p.online);
          if (tail === 'ack' && p) { waiting.get(p.id)?.(p); waiting.delete(p.id); }
        } catch { /* bỏ qua */ }
        return;
      }
      const i = parts.indexOf('m');
      const machineId = i >= 0 ? parts[i + 1] : undefined;
      const kind = parts[parts.length - 1];
      if (!machineId) return;
      try {
        if (kind === 'learn' && msg.length === 0) { h.onLearn?.(machineId, null); return; }
        const payload = JSON.parse(msg.toString());
        if (kind === 'learn') h.onLearn?.(machineId, payload);
        if (kind === 'state') h.onState?.(machineId, payload as StatePayload);
        if (kind === 'cycle') h.onCycle?.(machineId, payload as CyclePayload);
      } catch {
        // bản tin hỏng thì bỏ qua, không làm sập giao diện
      }
    });

    const giveUp = () => {
      if (!connected) { clearTimeout(fallback); h.onStatus('demo'); }
    };
    client.on('error', giveUp);
    client.on('close', () => {
      if (connected) { connected = false; h.onStatus('demo'); } else giveUp();
    });
  } catch {
    clearTimeout(fallback);
    h.onStatus('demo');
  }

  return {
    disconnect: () => {
      clearTimeout(fallback);
      try { client?.end(true); } catch { /* bỏ qua */ }
    },
    send: (op, body = {}) => new Promise<Ack>((resolve) => {
      const id = Math.random().toString(36).slice(2, 10);
      if (!client || !connected) { resolve({ id, ok: false, error: 'Chưa nối gateway' }); return; }
      const timer = setTimeout(() => {
        waiting.delete(id);
        resolve({ id, ok: false, error: 'Gateway không trả lời. Runtime edge có đang chạy không?' });
      }, 8000);
      waiting.set(id, (a) => { clearTimeout(timer); resolve(a); });
      client.publish(`gw/${gwId}/cmd`, JSON.stringify({ id, op, ...body }));
    }),
  };
}
