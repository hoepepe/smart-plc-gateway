import mqtt, { MqttClient } from 'mqtt';
import { SignalClass } from '../types';

export interface MqttPredPayload {
  ts: number;
  cls: SignalClass;
  conf: number;
  ood: boolean;
  state: 'auto' | 'pending' | 'confirmed';
  feat?: {
    mean?: number;
    std?: number;
    zcr?: number;
    slew?: number;
    kurt?: number;
    [key: string]: number | undefined;
  };
}

export interface MqttConnectionHandlers {
  onStatusChange: (status: 'connected' | 'demo' | 'connecting') => void;
  onPredMessage?: (channelId: number, payload: MqttPredPayload) => void;
  onError?: (err: Error) => void;
}

/**
 * Module kết nối MQTT WebSocket tới Broker tại biên (Edge Broker).
 * Topic quy chuẩn: gw/01/ch/{n}/pred
 *
 * Nếu không kết nối được sau 3 giây (ví dụ chạy trên máy tính phát triển không có broker),
 * hệ thống tự động rơi về Chế độ demo (mô phỏng tín hiệu).
 */
export function connectMqtt(
  brokerUrl: string = 'ws://localhost:9001',
  handlers: MqttConnectionHandlers
): { disconnect: () => void } {
  let isConnected = false;
  let client: MqttClient | null = null;
  handlers.onStatusChange('connecting');

  // Timer 3 giây: nếu chưa kết nối được thì tự động rơi về chế độ demo
  const fallbackTimer = setTimeout(() => {
    if (!isConnected) {
      handlers.onStatusChange('demo');
      if (client) {
        try {
          client.end(true);
        } catch {
          // ignore
        }
      }
    }
  }, 3000);

  try {
    client = mqtt.connect(brokerUrl, {
      connectTimeout: 3000,
      reconnectPeriod: 0, // Không thử reconnect liên tục để tránh spam console khi chạy web demo
      clean: true,
    });

    client.on('connect', () => {
      isConnected = true;
      clearTimeout(fallbackTimer);
      handlers.onStatusChange('connected');

      // Subscribe topic tất cả các kênh: gw/01/ch/+/pred
      client?.subscribe('gw/01/ch/+/pred', (err) => {
        if (err) {
          console.warn('[MQTT] Lỗi khi subscribe topic:', err);
        }
      });
    });

    client.on('message', (topic, message) => {
      try {
        // Parse channel id từ topic gw/01/ch/{id}/pred
        const parts = topic.split('/');
        const chIdx = parts.indexOf('ch');
        const channelId = chIdx !== -1 && parts[chIdx + 1] ? parseInt(parts[chIdx + 1], 10) : 1;

        const payload: MqttPredPayload = JSON.parse(message.toString());
        if (handlers.onPredMessage) {
          handlers.onPredMessage(channelId, payload);
        }
      } catch (e) {
        console.warn('[MQTT] Lỗi parse payload JSON:', e);
      }
    });

    client.on('error', (err) => {
      if (!isConnected) {
        clearTimeout(fallbackTimer);
        handlers.onStatusChange('demo');
      }
      if (handlers.onError) {
        handlers.onError(err);
      }
    });

    client.on('close', () => {
      if (!isConnected) {
        handlers.onStatusChange('demo');
      }
    });
  } catch (err) {
    clearTimeout(fallbackTimer);
    handlers.onStatusChange('demo');
  }

  return {
    disconnect: () => {
      clearTimeout(fallbackTimer);
      if (client) {
        try {
          client.end(true);
        } catch {
          // ignore
        }
      }
    },
  };
}
