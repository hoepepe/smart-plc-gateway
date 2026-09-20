import React, { useState } from 'react';
import { RoiParams } from '../types';
import {
  TrendingUp,
  Clock,
  Coins,
  Sparkles,
  Server,
  Layers,
} from 'lucide-react';

interface RoiTabProps {
  isDarkMode?: boolean;
}

export const RoiTab: React.FC<RoiTabProps> = ({ isDarkMode = false }) => {
  const [params, setParams] = useState<RoiParams>({
    machines: 50,
    machinesPerDevice: 1, // 1 to 8, default 1
    hManual: 4.0,
    hGw: 0.5,
    rate: 180000, // 180,000 VNĐ / giờ công kỹ sư
    deviceCost: 995000, // 995,000 VNĐ / gateway node (BOM cập nhật: ESP32 + MAX485 + Mux + Nguồn 24V)
    baselineDeviceCost: 30000000, // 30,000,000 VNĐ / thiết bị theo đề bài D1 của ban tổ chức
    months: 12,
  });

  // Calculate ROI figures
  const devicesNeeded = Math.ceil(params.machines / Math.max(1, params.machinesPerDevice));
  const hoursSavedPerMachine = Math.max(0, params.hManual - params.hGw);
  const totalHoursSaved = hoursSavedPerMachine * params.machines;
  const totalCostSaved = totalHoursSaved * params.rate;
  const totalCapex = devicesNeeded * params.deviceCost;
  const baselineTotalCapex = params.machines * params.baselineDeviceCost;
  const netSavings = totalCostSaved - totalCapex;
  const roiPct = totalCapex > 0 ? (totalCostSaved / totalCapex) * 100 : 0;
  const costRatio = params.deviceCost > 0 ? params.baselineDeviceCost / params.deviceCost : 0;

  const fmtVND = (val: number) =>
    new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(
      Math.round(val)
    );

  const fmtNumber = (val: number) =>
    new Intl.NumberFormat('vi-VN').format(Math.round(val));

  // Quick Preset Scenarios
  const applyPreset = (machines: number, machinesPerDevice: number, hManual: number, hGw: number) => {
    setParams((prev) => ({
      ...prev,
      machines,
      machinesPerDevice,
      hManual,
      hGw,
    }));
  };

  return (
    <div className="space-y-5">
      {/* Top Value Proposition Card - Square & Minimalist */}
      <div
        className={`p-5 rounded-md border transition-colors flex items-start gap-4 ${
          isDarkMode
            ? 'bg-emerald-950/20 border-emerald-900/60 text-emerald-200'
            : 'bg-emerald-50/60 border-emerald-200/80 text-emerald-950'
        }`}
      >
        <div className="p-2 rounded-md bg-emerald-600 text-white shrink-0 mt-0.5 shadow-xs">
          <TrendingUp size={20} />
        </div>
        <div className="space-y-1">
          <h4 className="text-base font-bold tracking-tight">
            Hiệu Quả Kinh Tế &amp; Tiết Kiệm Chi Phí Đầu Tư (ROI)
          </h4>
          <p className="text-xs sm:text-sm font-medium opacity-90 leading-relaxed max-w-4xl">
            Smart PLC Gateway tự động phân tích và hỗ trợ gán nhãn, giảm chi phí đầu tư thiết bị và thời gian triển khai cho từng máy
          </p>
        </div>
      </div>

      {/* Prominent Highlight Banner: Cheaper by X times */}
      <div
        className={`p-4 rounded-md border flex flex-col sm:flex-row items-center justify-between gap-3 ${
          isDarkMode
            ? 'bg-slate-900 border-emerald-800/80 text-emerald-200'
            : 'bg-white border-emerald-300 text-emerald-950 shadow-xs'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-md bg-emerald-600 text-white shadow-xs">
            <Sparkles size={18} />
          </div>
          <div>
            <div className="text-sm font-bold">
              Rẻ hơn <span className="text-lg font-mono text-emerald-600 dark:text-emerald-400 font-extrabold">{costRatio.toFixed(1)} lần</span> so với chi phí thiết bị hiện tại
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              So sánh giữa đơn giá {fmtVND(params.baselineDeviceCost)} (theo đề bài D1) và BOM {fmtVND(params.deviceCost)} của nhóm.
            </p>
          </div>
        </div>
        <div className="text-xs font-mono px-3 py-1.5 rounded-md bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200">
          Tiết kiệm phần cứng: <strong>{fmtVND(baselineTotalCapex - totalCapex)}</strong>
        </div>
      </div>

      {/* Quick Preset Buttons - Square Minimalist */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 mr-1">
          Kịch bản mẫu:
        </span>
        <button
          onClick={() => applyPreset(10, 1, 4.0, 0.5)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            params.machines === 10
              ? 'bg-emerald-600 text-white shadow-xs'
              : isDarkMode
              ? 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
              : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 shadow-xs'
          }`}
        >
          Xưởng Pilot (10 máy)
        </button>
        <button
          onClick={() => applyPreset(50, 2, 4.0, 0.5)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            params.machines === 50
              ? 'bg-emerald-600 text-white shadow-xs'
              : isDarkMode
              ? 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
              : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 shadow-xs'
          }`}
        >
          Dây Chuyền Chuẩn (50 máy · 2 máy/GW)
        </button>
        <button
          onClick={() => applyPreset(200, 4, 4.0, 0.4)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            params.machines === 200
              ? 'bg-emerald-600 text-white shadow-xs'
              : isDarkMode
              ? 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
              : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 shadow-xs'
          }`}
        >
          Toàn Phân Xưởng (200 máy · 4 máy/GW)
        </button>
      </div>

      {/* Main ROI Calculation Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left 6 Cols: Sliders / Input Parameters */}
        <div
          className={`lg:col-span-6 p-5 rounded-md border transition-colors space-y-4 ${
            isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}
        >
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">Tham Số Đầu Vào</h3>
            <span className="text-xs text-slate-400 font-mono">Tùy biến trực tiếp</span>
          </div>

          {/* Slider 1: Number of Machines */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-700 dark:text-slate-300">
                1. Số lượng máy PLC cần giám sát:
              </span>
              <span className="font-bold font-mono text-base text-emerald-600 dark:text-emerald-400">
                {params.machines} máy
              </span>
            </div>
            <input
              type="range"
              min={5}
              max={300}
              step={5}
              value={params.machines}
              onChange={(e) => setParams({ ...params, machines: Number(e.target.value) })}
              className="w-full accent-emerald-600 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-sm cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>5 máy</span>
              <span>150 máy</span>
              <span>300 máy</span>
            </div>
          </div>

          {/* Slider 2: Machines per Device */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <div>
                <span className="font-medium text-slate-700 dark:text-slate-300">
                  2. Số máy mỗi thiết bị phục vụ:
                </span>
                <p className="text-[11px] text-slate-500">Gateway phục vụ nhiều máy qua multiplexer</p>
              </div>
              <span className="font-bold font-mono text-base text-emerald-600 dark:text-emerald-400">
                {params.machinesPerDevice} máy / bộ
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={8}
              step={1}
              value={params.machinesPerDevice}
              onChange={(e) => setParams({ ...params, machinesPerDevice: Number(e.target.value) })}
              className="w-full accent-emerald-600 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-sm cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>1 máy/bộ</span>
              <span>4 máy/bộ</span>
              <span>8 máy/bộ</span>
            </div>
            <div className="text-[11px] text-emerald-700 dark:text-emerald-400 font-medium">
              → Cần đầu tư: <strong>{devicesNeeded} thiết bị Gateway</strong> (Math.ceil({params.machines} / {params.machinesPerDevice}))
            </div>
          </div>

          {/* Slider 3: Manual hours */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <div>
                <span className="font-medium text-slate-700 dark:text-slate-300">
                  3. Thời gian dò thủ công mỗi máy:
                </span>
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  (đang chờ số liệu từ mentor DENSO)
                </p>
              </div>
              <span className="font-bold font-mono text-base text-slate-800 dark:text-slate-200">
                {params.hManual.toFixed(1)} giờ / máy
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={8}
              step={0.5}
              value={params.hManual}
              onChange={(e) => setParams({ ...params, hManual: Number(e.target.value) })}
              className="w-full accent-emerald-600 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-sm cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>1.0h</span>
              <span>4.0h (Tạm tính)</span>
              <span>8.0h</span>
            </div>
          </div>

          {/* Slider 4: Gateway hours */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-700 dark:text-slate-300">
                4. Thời gian khi dùng Smart Gateway:
              </span>
              <span className="font-bold font-mono text-base text-emerald-600 dark:text-emerald-400">
                {params.hGw.toFixed(1)} giờ (~{params.hGw * 60} phút)
              </span>
            </div>
            <input
              type="range"
              min={0.2}
              max={1.5}
              step={0.1}
              value={params.hGw}
              onChange={(e) => setParams({ ...params, hGw: Number(e.target.value) })}
              className="w-full accent-emerald-600 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-sm cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>0.2h (12 phút)</span>
              <span>0.5h (30 phút mục tiêu)</span>
              <span>1.5h</span>
            </div>
          </div>

          {/* Baseline & Unit Costs Comparison */}
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2.5 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-600 dark:text-slate-300">Chi phí thiết bị hiện tại (baseline):</span>
                <span className="block text-[10px] text-slate-400">theo đề bài D1 của ban tổ chức</span>
              </div>
              <strong className="font-mono text-slate-800 dark:text-slate-200">
                {fmtVND(params.baselineDeviceCost)} / máy
              </strong>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-600 dark:text-slate-300">Chi phí thiết bị của nhóm:</span>
                <span className="block text-[10px] text-slate-400">BOM: ESP32 + MAX485 + Mux + Nguồn 24V</span>
              </div>
              <strong className="font-mono text-emerald-600 dark:text-emerald-400">
                {fmtVND(params.deviceCost)} / bộ
              </strong>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-500">Đơn giá nhân công kỹ sư:</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">
                {fmtVND(params.rate)} / giờ
              </span>
            </div>
          </div>
        </div>

        {/* Right 6 Cols: Result Visual Cards */}
        <div className="lg:col-span-6 space-y-4">
          {/* Key Figures: Hours & Labor Cost Saved */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Hours Saved */}
            <div
              className={`p-5 rounded-md border transition-colors ${
                isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
              }`}
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                <Clock size={16} className="text-emerald-600 dark:text-emerald-400" />
                <span>GIỜ CÔNG TIẾT KIỆM</span>
              </div>
              <div className="text-3xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-2">
                {fmtNumber(totalHoursSaved)}{' '}
                <span className="text-sm font-normal text-slate-500">giờ</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Tiết kiệm {hoursSavedPerMachine.toFixed(1)} giờ trên mỗi máy
              </p>
            </div>

            {/* Money Saved */}
            <div
              className={`p-5 rounded-md border transition-colors ${
                isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
              }`}
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                <Coins size={16} className="text-emerald-600 dark:text-emerald-400" />
                <span>TIỀN CÔNG TIẾT KIỆM</span>
              </div>
              <div className="text-3xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-2">
                {fmtVND(totalCostSaved)}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Ước tính từ giờ công kỹ sư
              </p>
            </div>
          </div>

          {/* Investment & Comparison Summary Card */}
          <div
            className={`p-5 rounded-md border transition-colors space-y-4 ${
              isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
            }`}
          >
            <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">So Sánh Đầu Tư &amp; Thu Hồi Vốn</h3>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500 dark:text-slate-400">
                  Chi phí phần cứng baseline ({params.machines} máy):
                </span>
                <strong className="font-mono text-slate-800 dark:text-slate-200 text-sm">
                  {fmtVND(baselineTotalCapex)}
                </strong>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500 dark:text-slate-400">
                  Chi phí phần cứng nhóm ({devicesNeeded} bộ Gateway):
                </span>
                <strong className="font-mono text-emerald-600 dark:text-emerald-400 text-sm">
                  {fmtVND(totalCapex)}
                </strong>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500 dark:text-slate-400">
                  Chênh lệch phần cứng tiết kiệm:
                </span>
                <strong className="font-mono text-emerald-600 dark:text-emerald-400 text-sm font-bold">
                  {fmtVND(baselineTotalCapex - totalCapex)}
                </strong>
              </div>

              <div className="flex items-center justify-between py-1">
                <span className="text-slate-500 dark:text-slate-400">
                  Tỷ suất thu hồi vốn nhân công (ROI):
                </span>
                <strong className="font-mono text-lg font-bold text-emerald-600 dark:text-emerald-400">
                  {roiPct.toFixed(0)}%
                </strong>
              </div>
            </div>

            {/* Payback Verdict */}
            <div
              className={`p-4 rounded-md border text-xs leading-relaxed ${
                netSavings >= 0
                  ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950 dark:bg-emerald-950/20 dark:border-emerald-800 dark:text-emerald-200'
                  : 'bg-amber-50 border-amber-200 text-amber-950 dark:bg-amber-950/20 dark:border-amber-800 dark:text-amber-200'
              }`}
            >
              <strong>Đánh giá thu hồi vốn:</strong>{' '}
              {netSavings >= 0 ? (
                <span>
                  Tiền công dò dây tiết kiệm ước tính ({fmtVND(totalCostSaved)}) vượt toàn bộ chi phí mua {devicesNeeded} thiết bị Gateway ({fmtVND(totalCapex)}).
                  Hệ thống tiết kiệm thêm <strong>{fmtVND(baselineTotalCapex - totalCapex)}</strong> chi phí phần cứng so với baseline 30 triệu đồng theo đề bài D1.
                </span>
              ) : (
                <span>
                  Hệ thống cần xem xét thêm số máy phục vụ để tối ưu chi phí đầu tư Gateway.
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
