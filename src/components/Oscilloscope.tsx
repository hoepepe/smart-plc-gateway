import React, { useRef, useEffect, useState } from 'react';
import { SignalFeatures } from '../types';
import { Pause, Play, Zap, Grid, Eye, Sliders, ArrowUpRight } from 'lucide-react';

interface OscilloscopeProps {
  buf: number[];
  toneColor?: string;
  features: SignalFeatures | null;
  channelName: string;
  channelId: number;
  isPaused: boolean;
  onTogglePause: () => void;
  onInjectAnomaly?: () => void;
  isAnomalyActive?: boolean;
  onInjectWiring?: () => void;
  isWiringActive?: boolean;
  isDarkMode?: boolean;
}

export const Oscilloscope: React.FC<OscilloscopeProps> = ({
  buf,
  toneColor = '#10b981',
  features,
  channelName,
  channelId,
  isPaused,
  onTogglePause,
  onInjectAnomaly,
  isAnomalyActive = false,
  onInjectWiring,
  isWiringActive = false,
  isDarkMode = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [showGrid, setShowGrid] = useState(true);
  const [hoverData, setHoverData] = useState<{ x: number; y: number; val: number } | null>(null);

  // Resize canvas according to container
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;

      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    handleResize();
    const observer = new ResizeObserver(handleResize);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Draw waveform
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;

    ctx.save();
    ctx.scale(dpr, dpr);

    // Canvas Background
    if (isDarkMode) {
      const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
      bgGrad.addColorStop(0, '#090d16');
      bgGrad.addColorStop(1, '#050811');
      ctx.fillStyle = bgGrad;
    } else {
      ctx.fillStyle = '#f8fafc'; // Crisp clean laboratory off-white
    }
    ctx.fillRect(0, 0, w, h);

    const pLeft = 45; // space for voltage scale
    const pRight = 15;
    const pTop = 20;
    const pBottom = 28; // space for time scale
    const plotW = Math.max(10, w - pLeft - pRight);
    const plotH = Math.max(10, h - pTop - pBottom);

    // Fixed or auto dynamic range (0 to 120 V/Unit scale)
    const maxVal = 120;
    const minVal = 0;

    // Draw Grid Lines
    if (showGrid) {
      const vDivs = 8;
      const hDivs = 5;

      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.strokeStyle = isDarkMode ? '#1e293b' : '#e2e8f0';

      // Horizontal grid lines (Voltage levels)
      for (let i = 0; i <= hDivs; i++) {
        const y = pTop + (plotH * i) / hDivs;
        ctx.beginPath();
        ctx.moveTo(pLeft, y);
        ctx.lineTo(w - pRight, y);
        ctx.stroke();

        // Voltage text label on left axis
        const voltVal = Math.round(maxVal - (i * (maxVal - minVal)) / hDivs);
        ctx.fillStyle = isDarkMode ? '#64748b' : '#94a3b8';
        ctx.font = '10px Lexend, sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(`${voltVal}V`, pLeft - 6, y);
      }

      // Vertical grid lines (Time slices)
      for (let j = 0; j <= vDivs; j++) {
        const x = pLeft + (plotW * j) / vDivs;
        ctx.beginPath();
        ctx.moveTo(x, pTop);
        ctx.lineTo(x, h - pBottom);
        ctx.stroke();
      }

      ctx.setLineDash([]); // Reset line dash
    }

    // Baseline axis lines
    ctx.strokeStyle = isDarkMode ? '#334155' : '#cbd5e1';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(pLeft, pTop);
    ctx.lineTo(pLeft, h - pBottom);
    ctx.lineTo(w - pRight, h - pBottom);
    ctx.stroke();

    // Time axis label at bottom
    ctx.fillStyle = isDarkMode ? '#64748b' : '#94a3b8';
    ctx.font = '10px Lexend, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('0 ms', pLeft, h - 10);
    ctx.textAlign = 'center';
    ctx.fillText('Cửa sổ đo thời gian thực (~200ms)', pLeft + plotW / 2, h - 10);
    ctx.textAlign = 'right';
    ctx.fillText('Hiện tại', w - pRight, h - 10);

    // Render Signal Waveform
    if (buf && buf.length > 1) {
      const step = plotW / (buf.length - 1);

      // 1. Under-curve fill gradient
      ctx.beginPath();
      for (let i = 0; i < buf.length; i++) {
        const x = pLeft + i * step;
        const norm = (buf[i] - minVal) / (maxVal - minVal);
        const clampedNorm = Math.max(0, Math.min(1, norm));
        const y = pTop + plotH * (1 - clampedNorm);

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }

      ctx.lineTo(pLeft + plotW, h - pBottom);
      ctx.lineTo(pLeft, h - pBottom);
      ctx.closePath();

      const fillGrad = ctx.createLinearGradient(0, pTop, 0, h - pBottom);
      if (isAnomalyActive) {
        fillGrad.addColorStop(0, 'rgba(244, 63, 94, 0.25)');
        fillGrad.addColorStop(1, 'rgba(244, 63, 94, 0.01)');
      } else {
        fillGrad.addColorStop(0, isDarkMode ? 'rgba(13, 148, 136, 0.3)' : 'rgba(13, 148, 136, 0.15)');
        fillGrad.addColorStop(1, 'rgba(13, 148, 136, 0.0)');
      }
      ctx.fillStyle = fillGrad;
      ctx.fill();

      // 2. High-clarity sharp stroke
      ctx.beginPath();
      for (let i = 0; i < buf.length; i++) {
        const x = pLeft + i * step;
        const norm = (buf[i] - minVal) / (maxVal - minVal);
        const clampedNorm = Math.max(0, Math.min(1, norm));
        const y = pTop + plotH * (1 - clampedNorm);

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }

      ctx.strokeStyle = isAnomalyActive ? '#f43f5e' : toneColor;
      ctx.lineWidth = 2.2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.stroke();

      // 3. Leading Pulse Dot at the latest sample point
      const lastX = pLeft + plotW;
      const lastVal = buf[buf.length - 1];
      const lastNorm = Math.max(0, Math.min(1, (lastVal - minVal) / (maxVal - minVal)));
      const lastY = pTop + plotH * (1 - lastNorm);

      ctx.beginPath();
      ctx.arc(lastX, lastY, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = isAnomalyActive ? '#f43f5e' : toneColor;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    ctx.restore();
  }, [buf, showGrid, isAnomalyActive, toneColor, isDarkMode]);

  // Handle Mouse move to inspect waveform points
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container || !buf || buf.length === 0) return;
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pLeft = 45;
    const pRight = 15;
    const plotW = rect.width - pLeft - pRight;

    if (x >= pLeft && x <= rect.width - pRight) {
      const ratio = (x - pLeft) / plotW;
      const index = Math.min(buf.length - 1, Math.max(0, Math.floor(ratio * buf.length)));
      setHoverData({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        val: buf[index],
      });
    } else {
      setHoverData(null);
    }
  };

  const currentVal = buf.length > 0 ? buf[buf.length - 1].toFixed(1) : '--';

  return (
    <div
      className={`rounded-md border transition-colors overflow-hidden ${
        isDarkMode
          ? 'bg-slate-900 border-slate-800 text-slate-100 shadow-sm'
          : 'bg-white border-slate-200 text-slate-800 shadow-xs'
      }`}
    >
      {/* Oscilloscope Header Bar */}
      <div
        className={`px-4 sm:px-5 py-2.5 border-b flex flex-wrap items-center justify-between gap-3 ${
          isDarkMode ? 'border-slate-800 bg-slate-950/60' : 'border-slate-100 bg-slate-50/70'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isAnomalyActive
                  ? 'bg-rose-500 animate-ping'
                  : isPaused
                  ? 'bg-amber-500'
                  : 'bg-emerald-500 animate-pulse'
              }`}
            />
            <h3 className="font-bold text-sm tracking-tight">
              Kênh {channelId}: {channelName}
            </h3>
          </div>
          <span
            className={`text-xs px-2 py-0.5 rounded-sm font-medium font-mono ${
              isDarkMode ? 'bg-slate-800 text-slate-300' : 'bg-slate-200/80 text-slate-700'
            }`}
          >
            {buf.length} mẫu / cửa sổ
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Inject Anomaly Button */}
          {onInjectAnomaly && (
            <button
              onClick={onInjectAnomaly}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-all ${
                isAnomalyActive
                  ? 'bg-rose-600 text-white shadow-xs ring-2 ring-rose-400/40'
                  : isDarkMode
                  ? 'bg-slate-800 text-rose-400 border border-rose-900/50 hover:bg-rose-950/30'
                  : 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
              }`}
              title="Tạo xung bất thường để kiểm tra thuật toán OOD"
            >
              <Zap size={13} className={isAnomalyActive ? 'animate-bounce' : ''} />
              <span>{isAnomalyActive ? 'Đang tạo tín hiệu lạ!' : '⚡ Thử tạo xung lạ (OOD)'}</span>
            </button>
          )}

          {/* Nút bơm tín hiệu đảo cực — kiểm tra luật kiểm tra dải */}
          {onInjectWiring && (
            <button
              onClick={onInjectWiring}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-semibold transition-all ${
                isWiringActive
                  ? 'bg-orange-600 text-white shadow-xs ring-2 ring-orange-400/40'
                  : isDarkMode
                  ? 'bg-slate-800 text-orange-400 border border-orange-900/50 hover:bg-orange-950/30'
                  : 'bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100'
              }`}
              title="Bơm tín hiệu đảo cực để kiểm tra luật kiểm tra dải tuyệt đối"
            >
              <Zap size={13} className={isWiringActive ? 'animate-bounce' : ''} />
              <span>{isWiringActive ? 'Đang đảo cực!' : 'Thử đấu ngược cực'}</span>
            </button>
          )}

          {/* Grid Toggle */}
          <button
            onClick={() => setShowGrid(!showGrid)}
            className={`p-1 rounded-sm border text-xs transition-colors ${
              showGrid
                ? isDarkMode
                  ? 'bg-slate-800 border-slate-700 text-emerald-400'
                  : 'bg-slate-100 border-slate-300 text-emerald-700'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
            title="Bật/Tắt lưới tọa độ"
          >
            <Grid size={15} />
          </button>

          {/* Pause/Play Button */}
          <button
            onClick={onTogglePause}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-medium border transition-colors ${
              isPaused
                ? 'bg-amber-500 text-white border-amber-600'
                : isDarkMode
                ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100 shadow-xs'
            }`}
            title={isPaused ? 'Tiếp tục đọc sóng' : 'Tạm dừng để soi mẫu'}
          >
            {isPaused ? (
              <>
                <Play size={13} />
                <span>Tiếp tục</span>
              </>
            ) : (
              <>
                <Pause size={13} />
                <span>Tạm dừng</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div
        ref={containerRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverData(null)}
        className="relative w-full h-64 sm:h-72 cursor-crosshair select-none"
      >
        <canvas ref={canvasRef} className="block w-full h-full" />

        {/* Live Value Badge overlay top-right */}
        <div
          className={`absolute top-3 right-3 px-2.5 py-1 rounded-sm border backdrop-blur-md font-mono text-xs flex items-center gap-2 ${
            isDarkMode
              ? 'bg-slate-900/90 border-slate-700 text-slate-200'
              : 'bg-white/90 border-slate-200 text-slate-800 shadow-xs'
          }`}
        >
          <span className="text-slate-400 text-[11px]">Giá trị tức thời:</span>
          <strong className="text-emerald-600 dark:text-emerald-400 text-sm">{currentVal} V</strong>
        </div>

        {/* Hover Tooltip */}
        {hoverData && (
          <div
            className={`absolute pointer-events-none z-20 px-2 py-1 rounded-xs text-[11px] font-mono shadow-md border -translate-x-1/2 -translate-y-8 transition-transform ${
              isDarkMode
                ? 'bg-slate-950 border-slate-700 text-emerald-300'
                : 'bg-slate-900 border-slate-800 text-white'
            }`}
            style={{ left: hoverData.x, top: hoverData.y }}
          >
            {hoverData.val.toFixed(2)} V
          </div>
        )}
      </div>

      {/* Oscilloscope Mini Stats Bar */}
      {features && (
        <div
          className={`px-4 sm:px-5 py-2.5 border-t text-xs flex flex-wrap items-center justify-between gap-3 ${
            isDarkMode ? 'border-slate-800 bg-slate-950/40 text-slate-400' : 'border-slate-100 bg-slate-50 text-slate-600'
          }`}
        >
          <div className="flex items-center gap-4">
            <span>
              Điện áp đỉnh-đỉnh (Vpp):{' '}
              <strong className="text-slate-800 dark:text-slate-200 font-mono">
                {features.vpp.toFixed(1)} V
              </strong>
            </span>
            <span>
              Giá trị hiệu dụng (RMS):{' '}
              <strong className="text-slate-800 dark:text-slate-200 font-mono">
                {features.rms.toFixed(1)} V
              </strong>
            </span>
          </div>

          <div className="text-[11px] text-slate-500">
            Hiển thị <span className="font-mono">{buf.length}</span> mẫu gần nhất của cửa sổ trượt
          </div>
        </div>
      )}
    </div>
  );
};
