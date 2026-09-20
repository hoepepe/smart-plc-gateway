/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback } from 'react';
import { ChannelData, LabelLogEntry } from './types';
import { sampleSignal, extractFeatures, classifySignal, checkWiring, CONF_TH, OOD_TH, WINDOW_SIZE } from './utils/signal';
import { connectMqtt, MqttPredPayload } from './utils/mqtt';
import { Navbar } from './components/Navbar';
import { ConsoleTab } from './components/ConsoleTab';
import { EvaluationTab } from './components/EvaluationTab';
import { RoiTab } from './components/RoiTab';
import { InsightsTab } from './components/InsightsTab';
import { HardwareModal } from './components/HardwareModal';
import { ToastContainer, ToastMessage } from './components/Toast';

const INITIAL_CHANNELS: ChannelData[] = [
  {
    id: 1,
    name: 'Cảm biến Gia tốc Rung',
    kind: 'vibration',
    buf: [],
    t: 0,
    status: 'analyzing',
    pred: null,
    conf: 0,
    oodScore: 0,
    final: null,
    lastUpdated: '--',
  },
  {
    id: 2,
    name: 'Cảm biến Nhiệt độ Khuôn',
    kind: 'temperature',
    buf: [],
    t: 0,
    status: 'analyzing',
    pred: null,
    conf: 0,
    oodScore: 0,
    final: null,
    lastUpdated: '--',
  },
  {
    id: 3,
    name: 'Bộ đếm xung PLC (24V)',
    kind: 'counter',
    buf: [],
    t: 0,
    status: 'analyzing',
    pred: null,
    conf: 0,
    oodScore: 0,
    final: null,
    lastUpdated: '--',
  },
  {
    id: 4,
    name: 'Áp suất van & Tải Động cơ',
    kind: 'exotic',
    buf: [],
    t: 0,
    status: 'analyzing',
    pred: null,
    conf: 0,
    oodScore: 0,
    final: null,
    lastUpdated: '--',
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('console');
  const [activeChannelId, setActiveChannelId] = useState<number>(1);
  const [channels, setChannels] = useState<ChannelData[]>(INITIAL_CHANNELS);
  const [log, setLog] = useState<LabelLogEntry[]>([]);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isHardwareModalOpen, setIsHardwareModalOpen] = useState<boolean>(false);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [mqttStatus, setMqttStatus] = useState<'connected' | 'demo' | 'connecting'>('connecting');

  // Synchronize document.documentElement 'dark' class with isDarkMode
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Toast Helper
  const addToast = useCallback(
    (title: string, description?: string, type: 'success' | 'warning' | 'info' = 'info') => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, title, description, type }]);
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Initialize MQTT connection to Edge Broker with 3-second fallback to demo mode
  useEffect(() => {
    const { disconnect } = connectMqtt('ws://localhost:9001', {
      onStatusChange: (status) => {
        setMqttStatus(status);
        if (status === 'connected') {
          addToast('Đã kết nối MQTT Broker', 'Đang nhận telemetry từ broker tại gw/01/ch/+/pred', 'success');
        }
      },
      onPredMessage: (channelId: number, payload: MqttPredPayload) => {
        setChannels((prev) =>
          prev.map((ch) => {
            if (ch.id !== channelId) return ch;
            const isOod = payload.ood;
            const newStatus = isOod ? 'unknown' : payload.conf >= CONF_TH ? 'confirmed' : 'pending';
            return {
              ...ch,
              pred: payload.cls,
              conf: payload.conf,
              oodScore: isOod ? 0.9 : 0.1,
              status: ch.status === 'confirmed' ? 'confirmed' : newStatus,
              final: ch.status === 'confirmed' ? ch.final : newStatus === 'confirmed' ? payload.cls : null,
              lastUpdated: new Date(payload.ts).toLocaleTimeString('vi-VN'),
            };
          })
        );
      },
    });

    return () => disconnect();
  }, [addToast]);

  // Real-time signal loop (Demo simulation mode when live)
  useEffect(() => {
    if (isPaused) return;

    const intervalId = setInterval(() => {
      setChannels((prevChannels) =>
        prevChannels.map((c) => {
          const nextVal = sampleSignal(c.kind, c.t, false, c.wiringFault);
          const buf = [...c.buf, nextVal].slice(-WINDOW_SIZE);
          const nextChannel: ChannelData = {
            ...c,
            buf,
            t: c.t + 1,
            lastUpdated: new Date().toLocaleTimeString('vi-VN'),
          };

          // Luật kiểm tra dải tuyệt đối chạy TRƯỚC mọi thứ khác, kể cả với kênh
          // đã được xác nhận nhãn — vì lỗi đấu nối là sự cố vật lý có thể xảy ra
          // bất cứ lúc nào (va chạm dây, đấu lại sai khi bảo trì).
          // Mô hình không phát hiện được lỗi này vì nó chuẩn hóa biên độ.
          const wiring = checkWiring(buf);
          if (!wiring.ok) {
            nextChannel.status = 'wiring_fault';
            nextChannel.pred = null;
            nextChannel.conf = 0;
            nextChannel.oodScore = 1;
            return nextChannel;
          }

          // Kênh đã xác nhận thủ công, hoặc bộ đệm chưa đủ mẫu
          if (c.status === 'confirmed' || buf.length < 50) {
            return nextChannel;
          }

          const features = extractFeatures(buf);
          const verdict = classifySignal(features);

          nextChannel.pred = verdict.cls;
          nextChannel.conf = verdict.conf;
          nextChannel.oodScore = verdict.oodScore;

          // Two-tier decision boundary:
          if (verdict.oodScore > 0.6 || verdict.conf < OOD_TH) {
            nextChannel.status = 'unknown';
          } else if (verdict.conf < CONF_TH) {
            nextChannel.status = 'pending';
          } else if (c.status !== 'pending') {
            // Auto-confirm high-confidence signals
            nextChannel.status = 'confirmed';
            nextChannel.final = verdict.cls;

            // Log auto-confirmation
            setTimeout(() => {
              setLog((prev) => [
                {
                  id: Math.random().toString(36).substring(2, 9),
                  time: new Date().toLocaleTimeString('vi-VN'),
                  ch: c.id,
                  channelName: c.name,
                  pred: verdict.cls,
                  conf: verdict.conf,
                  final: verdict.cls,
                  src: 'auto',
                  featuresSummary: `ZCR: ${features.zcr.toFixed(3)} | Slew: ${features.slew.toFixed(2)} | Kurt: ${features.kurt.toFixed(2)}`,
                },
                ...prev,
              ]);
            }, 0);
          }

          return nextChannel;
        })
      );
    }, 120);

    return () => clearInterval(intervalId);
  }, [isPaused]);

  // Reset entire gateway simulation
  const handleReset = useCallback(() => {
    setChannels(
      INITIAL_CHANNELS.map((ch) => ({
        ...ch,
        buf: [],
        t: 0,
        status: 'analyzing',
        pred: null,
        conf: 0,
        oodScore: 0,
        final: null,
        lastUpdated: '--',
      }))
    );
    setLog([]);
    addToast('Đã khởi tạo lại hệ thống', 'Toàn bộ 4 kênh đã được đưa về trạng thái đọc dữ liệu ban đầu.', 'info');
  }, [addToast]);

  // Summary counts for Header
  const pendingCount = channels.filter((c) => c.status === 'pending').length;
  const oodCount = channels.filter((c) => c.status === 'unknown').length;
  const confirmedCount = channels.filter((c) => c.status === 'confirmed').length;

  return (
    <div
      className={`min-h-screen flex flex-col font-sans transition-colors ${
        isDarkMode ? 'bg-slate-950 text-slate-100' : 'bg-slate-100/70 text-slate-800'
      }`}
    >
      {/* Top Navbar Header */}
      <Navbar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onReset={handleReset}
        onOpenHardwareModal={() => setIsHardwareModalOpen(true)}
        pendingCount={pendingCount}
        oodCount={oodCount}
        confirmedCount={confirmedCount}
        isLive={!isPaused}
        onToggleLive={() => setIsPaused(!isPaused)}
        isDarkMode={isDarkMode}
        onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        mqttStatus={mqttStatus}
      />

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {activeTab === 'console' && (
          <ConsoleTab
            channels={channels}
            setChannels={setChannels}
            activeId={activeChannelId}
            setActiveId={setActiveChannelId}
            log={log}
            setLog={setLog}
            isPaused={isPaused}
            onTogglePause={() => setIsPaused(!isPaused)}
            isDarkMode={isDarkMode}
            onNotify={addToast}
          />
        )}

        {activeTab === 'eval' && <EvaluationTab isDarkMode={isDarkMode} />}

        {activeTab === 'insights' && <InsightsTab isDarkMode={isDarkMode} />}

        {activeTab === 'roi' && <RoiTab isDarkMode={isDarkMode} />}
      </main>

      {/* Hardware Specs Modal */}
      <HardwareModal
        isOpen={isHardwareModalOpen}
        onClose={() => setIsHardwareModalOpen(false)}
        isDarkMode={isDarkMode}
      />

      {/* Toast Feedback System */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
