import React, { useState } from 'react';
import { ChannelData, LabelLogEntry, SignalFeatures, SignalClass } from '../types';
import { Oscilloscope } from './Oscilloscope';
import { SIGNAL_CLASSES, VI_NAMES } from '../data/metrics';
import { CONF_TH, OOD_TH, extractFeatures } from '../utils/signal';
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  ShieldCheck,
  BrainCircuit,
  Sliders,
  Sparkles,
  Check,
  X,
  Search,
  FileSpreadsheet,
} from 'lucide-react';

interface ConsoleTabProps {
  channels: ChannelData[];
  setChannels: React.Dispatch<React.SetStateAction<ChannelData[]>>;
  activeId: number;
  setActiveId: (id: number) => void;
  log: LabelLogEntry[];
  setLog: React.Dispatch<React.SetStateAction<LabelLogEntry[]>>;
  isPaused: boolean;
  onTogglePause: () => void;
  isDarkMode?: boolean;
  onNotify?: (title: string, description?: string, type?: 'success' | 'warning' | 'info') => void;
}

export const ConsoleTab: React.FC<ConsoleTabProps> = ({
  channels,
  setChannels,
  activeId,
  setActiveId,
  log,
  setLog,
  isPaused,
  onTogglePause,
  isDarkMode = false,
  onNotify,
}) => {
  const activeChannel = channels.find((c) => c.id === activeId) || channels[0];
  const [selectedClass, setSelectedClass] = useState<SignalClass>('TEMPERATURE');
  const [logFilter, setLogFilter] = useState<'all' | 'auto' | 'engineer'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [anomalyMode, setAnomalyMode] = useState(false);
  const [wiringMode, setWiringMode] = useState(false);
  const [showGuide, setShowGuide] = useState(true);

  const features: SignalFeatures | null =
    activeChannel.buf.length >= 15 ? extractFeatures(activeChannel.buf) : null;

  // Status Tone Configurations - Square & Emerald Green
  const getStatusBadge = (status: ChannelData['status'], conf: number) => {
    switch (status) {
      case 'confirmed':
        return {
          label: 'ĐÃ XÁC NHẬN NHÃN',
          sub: 'Cấu hình đã sẵn sàng và được đồng bộ vào PLC',
          color: 'text-emerald-700 dark:text-emerald-400',
          bg: 'bg-emerald-50 dark:bg-emerald-950/40',
          border: 'border-emerald-300 dark:border-emerald-800',
          dot: 'bg-emerald-500',
        };
      case 'pending':
        return {
          label: 'CHỜ KỸ SƯ DUYỆT',
          sub: `Độ tin cậy ${(conf * 100).toFixed(0)}% chưa đạt ngưỡng tự động ${CONF_TH * 100}%`,
          color: 'text-amber-700 dark:text-amber-400',
          bg: 'bg-amber-50 dark:bg-amber-950/40',
          border: 'border-amber-300 dark:border-amber-800',
          dot: 'bg-amber-500',
        };
      case 'unknown':
        return {
          label: 'TÍN HIỆU LẠ (DỊ BIỆT OOD)',
          sub: 'Phát hiện dạng sóng chưa từng thấy trong tập mẫu huấn luyện',
          color: 'text-rose-700 dark:text-rose-400',
          bg: 'bg-rose-50 dark:bg-rose-950/40',
          border: 'border-rose-300 dark:border-rose-800',
          dot: 'bg-rose-500 animate-ping',
        };
      case 'wiring_fault':
        return {
          label: 'LỖI ĐẤU NỐI',
          sub: 'Tín hiệu ra ngoài dải hợp lệ — kiểm tra lại cực và loại cổng trước khi đo',
          color: 'text-orange-700 dark:text-orange-400',
          bg: 'bg-orange-50 dark:bg-orange-950/40',
          border: 'border-orange-300 dark:border-orange-800',
          dot: 'bg-orange-500 animate-pulse',
        };
      case 'analyzing':
      default:
        return {
          label: 'ĐANG ĐỌC DỮ LIỆU',
          sub: 'Hệ thống đang tích lũy đủ mẫu sóng để phân tích',
          color: 'text-emerald-700 dark:text-emerald-400',
          bg: 'bg-emerald-50 dark:bg-emerald-950/40',
          border: 'border-emerald-300 dark:border-emerald-800',
          dot: 'bg-emerald-500',
        };
    }
  };

  const currentBadge = getStatusBadge(activeChannel.status, activeChannel.conf);

  // Commit label action (Engineer Confirmation or Correction)
  const commitLabel = (label: SignalClass, source: 'auto' | 'engineer') => {
    setChannels((prev) =>
      prev.map((c) =>
        c.id === activeId
          ? {
              ...c,
              status: 'confirmed',
              final: label,
              lastUpdated: new Date().toLocaleTimeString('vi-VN'),
            }
          : c
      )
    );

    const featSummary = features
      ? `ZCR: ${features.zcr.toFixed(3)} | Slew: ${features.slew.toFixed(2)} | Kurt: ${features.kurt.toFixed(2)}`
      : undefined;

    const newLogEntry: LabelLogEntry = {
      id: Math.random().toString(36).substring(2, 9),
      time: new Date().toLocaleTimeString('vi-VN'),
      ch: activeId,
      channelName: activeChannel.name,
      pred: activeChannel.pred,
      conf: activeChannel.conf,
      final: label,
      src: source,
      featuresSummary: featSummary,
    };

    setLog((prev) => [newLogEntry, ...prev]);

    if (onNotify) {
      const sensorName = VI_NAMES[label] || label;
      onNotify(
        `Đã gán nhãn: Kênh ${activeId} → ${sensorName}`,
        source === 'auto' ? 'Hệ thống tự động duyệt do độ tin cậy cao.' : 'Kỹ sư trực tiếp xác nhận.',
        'success'
      );
    }
  };

  // Reject / Retest signal
  const rejectPrediction = () => {
    setChannels((prev) =>
      prev.map((c) =>
        c.id === activeId
          ? {
              ...c,
              status: 'pending',
              pred: null,
              conf: 0,
              buf: [],
              lastUpdated: new Date().toLocaleTimeString('vi-VN'),
            }
          : c
      )
    );

    if (onNotify) {
      onNotify(
        `Kênh ${activeId}: Đã xóa nhãn`,
        'Hệ thống đang xóa bộ đệm và đọc lại chu kỳ tín hiệu mới.',
        'warning'
      );
    }
  };

  // Bơm tín hiệu đảo cực vào kênh đang chọn.
  // Khác với nút giả lập OOD: ở đây KHÔNG gán trạng thái sẵn — tín hiệu thật sự
  // rơi xuống dưới 0V và luật checkWiring tự phát hiện trong vòng lặp chính.
  const handleToggleWiring = () => {
    const next = !wiringMode;
    setWiringMode(next);
    setChannels((prev) =>
      prev.map((c) => (c.id === activeId
        ? { ...c, wiringFault: next, buf: [], status: 'analyzing', final: null, pred: null }
        : c))
    );
    if (onNotify) {
      onNotify(
        next ? `Kênh ${activeId}: đang bơm tín hiệu đảo cực` : `Kênh ${activeId}: đã ngắt`,
        next
          ? 'Điện áp rơi xuống dưới 0V. Mô hình không phát hiện được lỗi này — luật kiểm tra dải sẽ bắt.'
          : 'Kênh quay về tín hiệu bình thường.',
        next ? 'warning' : 'info'
      );
    }
  };

  // Toggle Anomaly mode on active channel
  const handleToggleAnomaly = () => {
    setAnomalyMode(!anomalyMode);
    if (!anomalyMode) {
      setChannels((prev) =>
        prev.map((c) =>
          c.id === activeId
            ? {
                ...c,
                status: 'unknown',
                oodScore: 0.92,
                conf: 0.28,
              }
            : c
        )
      );
      if (onNotify) {
        onNotify(
          'Đã kích hoạt giả lập xung dị biệt OOD!',
          'Đang bơm tín hiệu áp suất đột biến để kiểm tra cơ chế phát hiện tín hiệu lạ.',
          'warning'
        );
      }
    } else {
      if (onNotify) {
        onNotify('Đã ngắt xung dị biệt OOD', 'Kênh quay về chu kỳ đọc sóng bình thường.', 'info');
      }
    }
  };

  // Export audit logs as CSV
  const handleExportCSV = () => {
    if (log.length === 0) {
      if (onNotify) {
        onNotify('Chưa có dữ liệu để xuất', 'Hãy gán nhãn ít nhất 1 kênh trước khi xuất file CSV.', 'info');
      }
      return;
    }

    const headers = ['Thời gian', 'Kênh', 'Tên kênh', 'AI Dự đoán', 'Độ tin cậy', 'Nhãn chốt', 'Nguồn duyệt', 'Đặc trưng sóng'];
    const rows = log.map((r) => [
      r.time,
      `Kênh ${r.ch}`,
      r.channelName,
      VI_NAMES[r.pred || ''] || r.pred || 'Chưa rõ',
      `${(r.conf * 100).toFixed(1)}%`,
      VI_NAMES[r.final] || r.final,
      r.src === 'auto' ? 'AI tự động' : 'Kỹ sư duyệt',
      `"${r.featuresSummary || ''}"`,
    ]);

    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Smart_PLC_Gateway_Audit_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    if (onNotify) {
      onNotify('Đã xuất file báo cáo CSV', 'File lịch sử gán nhãn đã được tải về máy của bạn.', 'success');
    }
  };

  // Filtered log items
  const filteredLog = log.filter((r) => {
    if (logFilter !== 'all' && r.src !== logFilter) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchCh = `kênh ${r.ch}`.includes(term) || r.channelName.toLowerCase().includes(term);
      const matchFinal = (VI_NAMES[r.final] || r.final).toLowerCase().includes(term);
      return matchCh || matchFinal;
    }
    return true;
  });

  return (
    <div className="space-y-5">
      {/* Quick Start Guide Banner (Collapsible) - Square Minimalist */}
      {showGuide && (
        <div
          className={`p-4 rounded-md border transition-all ${
            isDarkMode
              ? 'bg-slate-900 border-slate-800 text-slate-200'
              : 'bg-emerald-50/70 border-emerald-200/80 text-emerald-950'
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="p-1.5 rounded-sm bg-emerald-600 text-white shrink-0 mt-0.5 shadow-xs">
                <Sparkles size={16} />
              </div>
              <div className="space-y-1">
                <h4 className="font-bold text-sm tracking-tight">
                  Hướng Dẫn Sử Dụng Nhanh (3 Bước Đơn Giản)
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1.5 text-xs">
                  <div className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-xs bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0">
                      1
                    </span>
                    <p className="leading-relaxed">
                      <strong>Chọn kênh tín hiệu:</strong> Bấm vào 1 trong 4 cổng bên dưới để kiểm tra dạng sóng từ PLC.
                    </p>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-xs bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0">
                      2
                    </span>
                    <p className="leading-relaxed">
                      <strong>AI tự động nhận diện:</strong> Mô hình đọc sóng và tính xác suất phân loại (bản triển khai chạy tại biên trên thiết bị).
                    </p>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-xs bg-emerald-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0">
                      3
                    </span>
                    <p className="leading-relaxed">
                      <strong>Xác nhận 1-chạm:</strong> Bấm nút xanh để duyệt hoặc đổi sang loại cảm biến khác nếu muốn.
                    </p>
                  </div>
                </div>
              </div>
            </div>
            <button
              onClick={() => setShowGuide(false)}
              className="text-slate-400 hover:text-slate-700 p-1 rounded-sm transition-colors"
              title="Ẩn hướng dẫn"
            >
              <X size={15} />
            </button>
          </div>
        </div>
      )}

      {/* 4-Channel Live Selector Bar - Square Minimalist */}
      <div>
        <div className="flex items-center justify-between mb-2 px-0.5">
          <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Chọn kênh tín hiệu đang giám sát (4 Cổng Vào PLC)
          </label>
          <span className="text-xs text-slate-400">Bấm vào thẻ để chuyển kênh</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {channels.map((c) => {
            const isActive = c.id === activeId;
            const isConfirmed = c.status === 'confirmed';
            const isOod = c.status === 'unknown';
            const isPending = c.status === 'pending';

            return (
              <button
                key={c.id}
                onClick={() => setActiveId(c.id)}
                className={`flex flex-col text-left p-3.5 rounded-md border transition-all relative overflow-hidden ${
                  isActive
                    ? isDarkMode
                      ? 'bg-slate-900 border-emerald-500 shadow-sm ring-1 ring-emerald-500/40'
                      : 'bg-white border-emerald-600 shadow-xs ring-1 ring-emerald-500/30'
                    : isDarkMode
                    ? 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
                }`}
              >
                {/* Header of card: Channel ID & Status Tag */}
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-5 h-5 rounded-xs flex items-center justify-center font-bold text-xs ${
                        isActive
                          ? 'bg-emerald-600 text-white'
                          : isDarkMode
                          ? 'bg-slate-800 text-slate-300'
                          : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      K{c.id}
                    </span>
                    <span className="font-semibold text-sm">Cổng {c.id}</span>
                  </div>

                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-xs flex items-center gap-1 border ${
                      isConfirmed
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-400 dark:border-emerald-800'
                        : isOod
                        ? 'bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/60 dark:text-rose-400 dark:border-rose-800 animate-pulse'
                        : isPending
                        ? 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-400 dark:border-amber-800'
                        : 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-400 dark:border-emerald-800'
                    }`}
                  >
                    {isConfirmed ? (
                      <>
                        <Check size={10} />
                        <span>Đã duyệt</span>
                      </>
                    ) : isOod ? (
                      <>
                        <AlertOctagon size={10} />
                        <span>Tín hiệu lạ</span>
                      </>
                    ) : isPending ? (
                      <>
                        <AlertTriangle size={10} />
                        <span>Chờ duyệt</span>
                      </>
                    ) : (
                      <span>Đang đọc</span>
                    )}
                  </span>
                </div>

                {/* Sensor Name */}
                <div className="mt-2.5">
                  <div className="text-xs text-slate-500 dark:text-slate-400 truncate">{c.name}</div>
                  <div className="text-sm font-bold truncate mt-0.5">
                    {c.final
                      ? VI_NAMES[c.final] || c.final
                      : c.pred
                      ? VI_NAMES[c.pred] || c.pred
                      : 'Đang nhận diện...'}
                  </div>
                </div>

                {/* Signal mini sparkline */}
                <div className="mt-2 h-7 w-full flex items-end gap-0.5 overflow-hidden">
                  {c.buf.slice(-20).map((v, i) => (
                    <div
                      key={i}
                      className={`flex-1 transition-all ${
                        isOod
                          ? 'bg-rose-400'
                          : isActive
                          ? 'bg-emerald-500'
                          : isDarkMode
                          ? 'bg-slate-700'
                          : 'bg-slate-300'
                      }`}
                      style={{ height: `${Math.min(100, Math.max(10, (v / 100) * 100))}%` }}
                    />
                  ))}
                </div>

                {/* Bottom Confidence Bar */}
                <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">Độ tin cậy:</span>
                  <span
                    className={`font-mono font-bold ${
                      c.conf >= CONF_TH
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : c.conf < OOD_TH
                        ? 'text-rose-600 dark:text-rose-400'
                        : 'text-amber-600 dark:text-amber-400'
                    }`}
                  >
                    {(c.conf * 100).toFixed(0)}%
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Signal Display & Quick Decision Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left 7 Cols: Real-time Oscilloscope Canvas & Extracted Features */}
        <div className="lg:col-span-7 space-y-4">
          <Oscilloscope
            buf={activeChannel.buf}
            toneColor={activeChannel.status === 'unknown' ? '#f43f5e' : '#10b981'}
            features={features}
            channelName={activeChannel.name}
            channelId={activeChannel.id}
            isPaused={isPaused}
            onTogglePause={onTogglePause}
            onInjectAnomaly={handleToggleAnomaly}
            isAnomalyActive={anomalyMode}
            onInjectWiring={handleToggleWiring}
            isWiringActive={wiringMode}
            isDarkMode={isDarkMode}
          />

          {/* Extracted Features - Square Minimalist */}
          <div
            className={`p-4 rounded-md border transition-colors ${
              isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
            }`}
          >
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Sliders size={15} className="text-emerald-600 dark:text-emerald-400" />
                <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">Đặc trưng trích xuất từ dạng sóng</h3>
              </div>
              <span className="text-xs text-slate-400">
                Xử lý trực tiếp trên vi điều khiển
              </span>
            </div>

            {features ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-3">
                <div
                  className={`p-2.5 rounded-sm border ${
                    isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
                  }`}
                >
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">Tần số đổi dấu (ZCR)</div>
                  <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                    {features.zcr.toFixed(3)}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {features.zcr > 0.18 ? '⚡ Dao động nhanh' : 'Trôi chậm'}
                  </div>
                </div>

                <div
                  className={`p-2.5 rounded-sm border ${
                    isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
                  }`}
                >
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">Tốc độ dốc (Slew)</div>
                  <div className="text-base font-bold font-mono mt-1">{features.slew.toFixed(2)}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {features.slew < 1.6 ? 'Quán tính nhiệt' : 'Biến thiên nhanh'}
                  </div>
                </div>

                <div
                  className={`p-2.5 rounded-sm border ${
                    isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
                  }`}
                >
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">Mức rời rạc (Levels)</div>
                  <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                    {features.levels}{' '}
                    <span className="text-xs font-normal text-slate-500">mức</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {features.levels <= 5 ? 'Xung số PLC' : 'Tín hiệu Analog'}
                  </div>
                </div>

                <div
                  className={`p-2.5 rounded-sm border ${
                    isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
                  }`}
                >
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">Độ nhọn đỉnh (Kurtosis)</div>
                  <div
                    className={`text-base font-bold font-mono mt-1 ${
                      features.kurt > 4.2
                        ? 'text-rose-600 dark:text-rose-400'
                        : 'text-slate-700 dark:text-slate-200'
                    }`}
                  >
                    {features.kurt.toFixed(2)}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {features.kurt > 4.2 ? '⚠️ Xung lạ đột biến' : 'Phân phối chuẩn'}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                Đang đọc tín hiệu để trích xuất đặc trưng...
              </div>
            )}
          </div>
        </div>

        {/* Right 5 Cols: Fast Action Decision Panel */}
        <div className="lg:col-span-5 space-y-4">
          {/* Main AI Verdict Card - Square Minimalist */}
          <div
            className={`rounded-md border p-5 transition-all shadow-xs ${
              isDarkMode
                ? 'bg-slate-900 border-slate-800'
                : 'bg-white border-slate-200'
            }`}
          >
            {/* Status Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${currentBadge.dot}`} />
                <span className={`text-xs font-bold tracking-wide ${currentBadge.color}`}>
                  {currentBadge.label}
                </span>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono">
                Cổng {activeId}
              </span>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{currentBadge.sub}</p>

            {/* Verdict Sensor Name Title */}
            <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Kết quả AI nhận diện
              </span>
              <div className="text-xl font-bold tracking-tight mt-1 flex items-center gap-2.5">
                {activeChannel.status === 'unknown' ? (
                  <span className="text-rose-600 dark:text-rose-400 flex items-center gap-2">
                    <AlertOctagon size={22} />
                    Tín hiệu lạ ngoài phân phối
                  </span>
                ) : activeChannel.final ? (
                  <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                    <CheckCircle2 size={22} />
                    {VI_NAMES[activeChannel.final] || activeChannel.final}
                  </span>
                ) : activeChannel.pred ? (
                  <span className="text-slate-800 dark:text-slate-100">
                    {VI_NAMES[activeChannel.pred] || activeChannel.pred}
                  </span>
                ) : (
                  <span className="text-slate-400 text-base font-normal">Đang phân tích...</span>
                )}
              </div>

              {/* Sensor Description Helper */}
              {activeChannel.pred && SIGNAL_CLASSES[activeChannel.pred] && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 leading-relaxed bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-sm border border-slate-100 dark:border-slate-800">
                  💡 <strong>Đặc điểm:</strong> {SIGNAL_CLASSES[activeChannel.pred].description}
                </p>
              )}

              {/* Confidence Meter */}
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="text-slate-500 dark:text-slate-400">Độ tin cậy của thuật toán:</span>
                  <strong
                    className={`font-bold font-mono text-sm ${
                      activeChannel.conf >= CONF_TH
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : activeChannel.conf < OOD_TH
                        ? 'text-rose-600 dark:text-rose-400'
                        : 'text-amber-600 dark:text-amber-400'
                    }`}
                  >
                    {(activeChannel.conf * 100).toFixed(1)}%
                  </strong>
                </div>

                <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-xs overflow-hidden">
                  <div
                    className={`h-full rounded-xs transition-all duration-300 ${
                      activeChannel.conf >= CONF_TH
                        ? 'bg-emerald-500'
                        : activeChannel.conf < OOD_TH
                        ? 'bg-rose-500'
                        : 'bg-amber-500'
                    }`}
                    style={{ width: `${Math.max(5, activeChannel.conf * 100)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* ACTION BUTTONS (Clean Square Minimalist) */}
            <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
                Thao tác kỹ sư xác nhận:
              </span>

              {/* Big 1-Click Confirm Button */}
              {activeChannel.pred && (
                <button
                  onClick={() => commitLabel(activeChannel.pred!, 'engineer')}
                  className="w-full py-2.5 px-4 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs sm:text-sm shadow-xs transition-all flex items-center justify-center gap-2 active:scale-[0.99]"
                >
                  <Check size={16} />
                  <span>Xác nhận: {VI_NAMES[activeChannel.pred] || activeChannel.pred}</span>
                </button>
              )}

              {/* Change Sensor Type Option */}
              <div className="space-y-1.5 pt-1">
                <label className="text-xs text-slate-500 dark:text-slate-400 flex items-center justify-between">
                  <span>Hoặc tự chọn loại cảm biến khác:</span>
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={selectedClass}
                    onChange={(e) => setSelectedClass(e.target.value as SignalClass)}
                    className={`flex-1 text-xs py-2 px-3 rounded-md border font-medium focus:ring-1 focus:ring-emerald-500 outline-none transition-colors ${
                      isDarkMode
                        ? 'bg-slate-950 border-slate-700 text-slate-200'
                        : 'bg-white border-slate-300 text-slate-800'
                    }`}
                  >
                    {Object.keys(SIGNAL_CLASSES).map((key) => (
                      <option key={key} value={key}>
                        {SIGNAL_CLASSES[key].nameVi} ({SIGNAL_CLASSES[key].sampleUnit})
                      </option>
                    ))}
                  </select>

                  <button
                    onClick={() => commitLabel(selectedClass, 'engineer')}
                    className={`px-3 py-2 rounded-md text-xs font-semibold border transition-colors whitespace-nowrap ${
                      isDarkMode
                        ? 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
                        : 'bg-slate-100 border-slate-300 text-slate-800 hover:bg-slate-200'
                    }`}
                  >
                    Lưu nhãn này
                  </button>
                </div>
              </div>

              {/* Reject / Reset Button */}
              <div className="pt-1">
                <button
                  onClick={rejectPrediction}
                  className="w-full py-1.5 px-3 rounded-md text-xs text-slate-500 hover:text-rose-600 dark:hover:text-rose-400 transition-colors flex items-center justify-center gap-1.5"
                >
                  <AlertTriangle size={13} />
                  <span>Đánh dấu cần đo lại / Nghi ngờ sai tín hiệu</span>
                </button>
              </div>
            </div>
          </div>

          {/* Quick Info Box: Two-Tier Pipeline */}
          <div
            className={`p-3.5 rounded-md border text-xs space-y-1.5 ${
              isDarkMode
                ? 'bg-slate-900/60 border-slate-800/80 text-slate-400'
                : 'bg-slate-50 border-slate-200/80 text-slate-600'
            }`}
          >
            <div className="flex items-center gap-2 font-semibold text-slate-700 dark:text-slate-300">
              <BrainCircuit size={14} className="text-emerald-600 dark:text-emerald-400" />
              <span>Ba tầng xử lý, mỗi tầng bắt một loại vấn đề khác nhau</span>
            </div>
            <p className="leading-relaxed">
              • <strong>Tầng 1 — Luật kiểm tra dải:</strong> Tín hiệu ra ngoài dải hợp lệ là lỗi đấu nối vật lý.
              Không dùng mô hình, vì mô hình chuẩn hóa biên độ nên mù trước lỗi này (bắt 0%, luật bắt 100%).
            </p>
            <p className="leading-relaxed">
              • <strong>Tầng 2 — Phát hiện ngoài phân phối:</strong> Dạng sóng không giống bất kỳ loại nào đã học
              thì báo tín hiệu lạ thay vì đoán bừa.
            </p>
            <p className="leading-relaxed">
              • <strong>Tầng 3 — Phân loại:</strong> Gán nhãn nhiệt độ, rung động, bộ đếm hay tải động cơ.
              Dưới ngưỡng tin cậy thì chuyển cho kỹ sư xác nhận.
            </p>
            <p className="leading-relaxed opacity-75 pt-1">
              Giao diện này mô phỏng hành vi ba tầng bằng luật ngưỡng để chạy realtime trong trình duyệt.
              Mô hình thật (Random Forest + Isolation Forest) chạy trên thiết bị.
            </p>
          </div>
        </div>
      </div>

      {/* Audit Log Table Section - Square Minimalist */}
      <div
        className={`rounded-md border transition-colors overflow-hidden ${
          isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
        }`}
      >
        {/* Table Controls Header */}
        <div
          className={`p-4 border-b flex flex-wrap items-center justify-between gap-3 ${
            isDarkMode ? 'border-slate-800 bg-slate-950/40' : 'border-slate-100 bg-slate-50/70'
          }`}
        >
          <div>
            <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">Nhật Ký Gán Nhãn &amp; Lịch Sử Duyệt (Audit Trail)</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Ghi lại quyết định của AI và thao tác của kỹ sư để phục vụ nghiệm thu
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search Bar */}
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Tìm kênh, loại cảm biến..."
                className={`pl-7 pr-3 py-1.5 text-xs rounded-md border outline-none transition-colors ${
                  isDarkMode
                    ? 'bg-slate-900 border-slate-700 text-slate-200 focus:border-emerald-500'
                    : 'bg-white border-slate-300 text-slate-800 focus:border-emerald-600'
                }`}
              />
            </div>

            {/* Filter Pills */}
            <div
              className={`flex items-center gap-1 p-0.5 rounded-md border ${
                isDarkMode ? 'bg-slate-950 border-slate-800' : 'bg-slate-100 border-slate-200'
              }`}
            >
              <button
                onClick={() => setLogFilter('all')}
                className={`px-2.5 py-1 rounded-sm text-xs font-medium transition-colors ${
                  logFilter === 'all'
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-white'
                }`}
              >
                Tất cả ({log.length})
              </button>
              <button
                onClick={() => setLogFilter('auto')}
                className={`px-2.5 py-1 rounded-sm text-xs font-medium transition-colors ${
                  logFilter === 'auto'
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-white'
                }`}
              >
                AI tự động
              </button>
              <button
                onClick={() => setLogFilter('engineer')}
                className={`px-2.5 py-1 rounded-sm text-xs font-medium transition-colors ${
                  logFilter === 'engineer'
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-white'
                }`}
              >
                Kỹ sư duyệt
              </button>
            </div>

            {/* Export CSV Button */}
            <button
              onClick={handleExportCSV}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors ${
                isDarkMode
                  ? 'bg-slate-800 border-slate-700 text-emerald-400 hover:bg-slate-700'
                  : 'bg-white border-slate-300 text-emerald-700 hover:bg-slate-50 shadow-xs'
              }`}
              title="Tải toàn bộ nhật ký về máy định dạng Excel/CSV"
            >
              <FileSpreadsheet size={13} />
              <span>Xuất Excel / CSV</span>
            </button>
          </div>
        </div>

        {/* Table Content */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead
              className={`border-b ${
                isDarkMode
                  ? 'bg-slate-950/60 border-slate-800 text-slate-400'
                  : 'bg-slate-50 border-slate-200 text-slate-600'
              }`}
            >
              <tr>
                <th className="py-2.5 px-4 font-semibold">Thời Gian</th>
                <th className="py-2.5 px-4 font-semibold">Kênh Tín Hiệu</th>
                <th className="py-2.5 px-4 font-semibold">AI Dự Đoán</th>
                <th className="py-2.5 px-4 font-semibold">Độ Tin Cậy</th>
                <th className="py-2.5 px-4 font-semibold">Nhãn Đã Gán</th>
                <th className="py-2.5 px-4 font-semibold">Nguồn Duyệt</th>
                <th className="py-2.5 px-4 font-semibold">Đặc Trưng Sóng</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filteredLog.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    Chưa có thao tác nào được ghi nhận. Hãy bấm nút "Xác nhận" ở trên để ghi nhãn.
                  </td>
                </tr>
              ) : (
                filteredLog.map((r) => (
                  <tr
                    key={r.id}
                    className={`transition-colors ${
                      isDarkMode ? 'hover:bg-slate-800/40' : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="py-2.5 px-4 font-mono text-slate-500 whitespace-nowrap">{r.time}</td>
                    <td className="py-2.5 px-4 font-medium whitespace-nowrap">
                      Cổng {r.ch} ({r.channelName})
                    </td>
                    <td className="py-2.5 px-4 font-medium whitespace-nowrap">
                      {VI_NAMES[r.pred || ''] || r.pred || 'Chưa rõ'}
                    </td>
                    <td className="py-2.5 px-4 font-mono whitespace-nowrap">
                      <span
                        className={
                          r.conf >= CONF_TH
                            ? 'text-emerald-600 dark:text-emerald-400 font-bold'
                            : 'text-amber-600 dark:text-amber-400 font-bold'
                        }
                      >
                        {(r.conf * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2.5 px-4 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded-xs text-[11px] font-semibold bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60">
                        {VI_NAMES[r.final] || r.final}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 whitespace-nowrap">
                      {r.src === 'auto' ? (
                        <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                          <Sparkles size={12} />
                          AI Tự động
                        </span>
                      ) : (
                        <span className="text-slate-600 dark:text-slate-300 flex items-center gap-1 font-medium">
                          <ShieldCheck size={12} />
                          Kỹ sư duyệt
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-slate-400 text-[11px]">
                      {r.featuresSummary || '--'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
