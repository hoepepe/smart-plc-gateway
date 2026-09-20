import React from 'react';
import {
  Radio,
  BarChart3,
  Calculator,
  RotateCcw,
  Cpu,
  Server,
  Sun,
  Moon,
  Info,
  Wifi,
  Microscope,
} from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onReset: () => void;
  onOpenHardwareModal: () => void;
  pendingCount: number;
  oodCount: number;
  confirmedCount: number;
  isLive: boolean;
  onToggleLive: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  mqttStatus?: 'connected' | 'demo' | 'connecting';
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  onReset,
  onOpenHardwareModal,
  pendingCount,
  oodCount,
  confirmedCount,
  isLive,
  onToggleLive,
  isDarkMode,
  onToggleDarkMode,
  mqttStatus = 'demo',
}) => {
  const navTabs = [
    {
      id: 'console',
      label: 'Giám sát & Gán nhãn',
      badge: pendingCount + oodCount > 0 ? pendingCount + oodCount : undefined,
      badgeColor: oodCount > 0 ? 'bg-rose-500' : 'bg-amber-500',
      icon: Radio,
    },
    {
      id: 'eval',
      label: 'Đánh giá mô hình',
      icon: BarChart3,
    },
    {
      id: 'insights',
      label: 'Phân tích chuyên sâu',
      icon: Microscope,
    },
    {
      id: 'roi',
      label: 'Tính toán Tiết kiệm (ROI)',
      icon: Calculator,
    },
  ];

  return (
    <header
      className={`sticky top-0 z-40 transition-colors border-b ${
        isDarkMode
          ? 'bg-slate-900/95 border-slate-800 text-slate-100'
          : 'bg-white/95 border-slate-200 text-slate-800 shadow-xs'
      } backdrop-blur-md`}
    >
      {/* Top Status Bar - Square & Minimalist */}
      <div
        className={`px-4 sm:px-6 py-1.5 text-xs transition-colors border-b ${
          isDarkMode
            ? 'bg-slate-950/90 border-slate-800/80 text-slate-400'
            : 'bg-slate-50/90 border-slate-200/80 text-slate-600'
        }`}
      >
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
          {/* Status Left */}
          <div className="flex items-center gap-3 sm:gap-4">
            <button
              onClick={onToggleLive}
              className={`flex items-center gap-1.5 font-medium px-2 py-0.5 rounded-sm transition-colors ${
                isLive
                  ? 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200/70 dark:border-emerald-800/50'
                  : 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50'
              }`}
              title="Bấm để tạm dừng hoặc tiếp tục thu thập tín hiệu"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isLive ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                }`}
              />
              <span>{isLive ? 'Tín hiệu Live' : 'Đang tạm dừng'}</span>
            </button>

            <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">•</span>

            {/* MQTT status indicator */}
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11px] font-medium border ${
                mqttStatus === 'connected'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800'
                  : mqttStatus === 'connecting'
                  ? 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800'
                  : 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
              }`}
            >
              <Wifi size={11} className={mqttStatus === 'connected' ? 'text-emerald-600' : 'text-slate-400'} />
              <span>
                {mqttStatus === 'connected'
                  ? 'MQTT: đã kết nối'
                  : mqttStatus === 'connecting'
                  ? 'MQTT: đang thử...'
                  : 'Chế độ demo'}
              </span>
            </span>

            <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">•</span>

            <span className="hidden sm:inline-flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              <Server size={13} className="text-emerald-600 dark:text-emerald-400" />
              <span>Thiết bị:</span>
              <strong className="text-slate-700 dark:text-slate-300 font-mono">GW-01 (demo)</strong>
            </span>

            <span className="text-slate-300 dark:text-slate-700 hidden md:inline">•</span>

            <span className="hidden md:inline-flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              <Cpu size={13} className="text-emerald-600 dark:text-emerald-400" />
              <span>ESP32 · TinyML tại biên</span>
            </span>
          </div>

          {/* Status Right */}
          <div className="flex items-center gap-3 sm:gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>
                Đã duyệt: <strong className="text-emerald-600 dark:text-emerald-400 font-mono">{confirmedCount}/4</strong>
              </span>
            </span>

            {pendingCount > 0 && (
              <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                <span>
                  Chờ duyệt: <strong className="font-mono">{pendingCount}</strong>
                </span>
              </span>
            )}

            {oodCount > 0 && (
              <span className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
                <span>
                  Tín hiệu lạ: <strong className="font-mono">{oodCount}</strong>
                </span>
              </span>
            )}

            <button
              onClick={onOpenHardwareModal}
              className="text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-1 text-xs font-medium"
            >
              <Info size={12} />
              <span>Phần cứng</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Navigation Row - Square & Minimalist */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between py-3 gap-3">
          {/* Brand Info (No icon logo, Clean Minimalist Typography, "Smart PLC Gateway") */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg sm:text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                Smart PLC Gateway
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Tự động nhận diện tín hiệu cảm biến PLC &amp; Phát hiện dị biệt OOD
              </p>
            </div>

            {/* Quick Actions Mobile */}
            <div className="flex md:hidden items-center gap-1.5">
              <button
                onClick={onToggleDarkMode}
                className="p-2 rounded-md border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300"
                title="Chuyển chế độ Sáng / Tối"
              >
                {isDarkMode ? <Sun size={15} /> : <Moon size={15} />}
              </button>
              <button
                onClick={onReset}
                className="p-2 rounded-md border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300"
                title="Khởi động lại toàn bộ kênh"
              >
                <RotateCcw size={15} />
              </button>
            </div>
          </div>

          {/* Navigation Tabs & Theme Toggle - Square Minimalist */}
          <div className="flex items-center justify-between md:justify-end gap-2">
            <nav
              className={`flex items-center gap-1 p-1 rounded-md border ${
                isDarkMode ? 'bg-slate-950 border-slate-800' : 'bg-slate-100 border-slate-200'
              }`}
            >
              {navTabs.map((t) => {
                const Icon = t.icon;
                const isActive = activeTab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => onSelectTab(t.id)}
                    className={`relative flex items-center gap-2 px-3 sm:px-3.5 py-1.5 rounded-sm text-xs sm:text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/70 dark:hover:bg-slate-800/60'
                    }`}
                  >
                    <Icon size={15} />
                    <span>{t.label}</span>
                    {t.badge && (
                      <span
                        className={`ml-1 px-1.5 py-0.2 rounded-xs text-[10px] font-bold text-white ${t.badgeColor}`}
                      >
                        {t.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Desktop Actions: Theme & Reset */}
            <div className="hidden md:flex items-center gap-1.5">
              <button
                onClick={onToggleDarkMode}
                className={`p-2 rounded-md border transition-colors ${
                  isDarkMode
                    ? 'bg-slate-800 border-slate-700 text-amber-300 hover:bg-slate-700'
                    : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100 shadow-xs'
                }`}
                title={isDarkMode ? 'Chuyển sang giao diện Sáng' : 'Chuyển sang giao diện Tối'}
              >
                {isDarkMode ? <Sun size={15} /> : <Moon size={15} />}
              </button>

              <button
                onClick={onReset}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                  isDarkMode
                    ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'
                    : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100 hover:text-slate-900 shadow-xs'
                }`}
                title="Khởi tạo lại toàn bộ 4 kênh về trạng thái ban đầu"
              >
                <RotateCcw size={13} />
                <span>Khởi tạo lại</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
