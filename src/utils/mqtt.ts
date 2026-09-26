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
  f: number[];       // 9 đặc trưng, gateway tính sẵn theo đúng ml/cycles.py
  score?: number;    // điểm Mahalanobis gateway tính — giao diện tính lại để đối chiếu
}

export type ConnStatus = 'connecting' | 'connected' | 'demo';

export interface Handlers {
  onStatus: (s: ConnStatus) => void;
  onState?: (machineId: string, p: StatePayload) => void;
  onCycle?: (machineId: string, p: CyclePayload) => void;
}

export function connectMqtt(url: string, gwId: string, h: Handlers): { disconnect: () => void } {
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
      client?.subscribe([`gw/${gwId}/m/+/state`, `gw/${gwId}/m/+/cycle`]);
    });

    client.on('message', (topic, msg) => {
      const parts = topic.split('/');
      const i = parts.indexOf('m');
      const machineId = i >= 0 ? parts[i + 1] : undefined;
      const kind = parts[parts.length - 1];
      if (!machineId) return;
      try {
        const payload = JSON.parse(msg.toString());
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
  };
}
