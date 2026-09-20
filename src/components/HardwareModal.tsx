import React from 'react';
import { Cpu, X, Terminal, AlertCircle } from 'lucide-react';

interface HardwareModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDarkMode?: boolean;
}

export const HardwareModal: React.FC<HardwareModalProps> = ({ isOpen, onClose, isDarkMode = false }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
      <div
        className={`rounded-md border w-full max-w-2xl overflow-hidden shadow-xl transition-colors ${
          isDarkMode ? 'bg-slate-900 border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-800'
        }`}
      >
        {/* Header - Square Minimalist */}
        <div
          className={`flex items-center justify-between px-5 py-3.5 border-b ${
            isDarkMode ? 'border-slate-800 bg-slate-950/40' : 'border-slate-100 bg-slate-50/80'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-sm bg-emerald-600 text-white shadow-xs">
              <Cpu size={18} />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                Kiến Trúc Phần Cứng &amp; Thông Số Kỹ Thuật Smart PLC Gateway
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                DENSO Factory Hacks 2026 • Cấu hình vi điều khiển ESP32 TinyML
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-sm text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-3.5 text-xs max-h-[80vh] overflow-y-auto">
          {/* Warning Banner */}
          <div
            className={`p-3 rounded-sm border flex items-start gap-2.5 ${
              isDarkMode
                ? 'bg-amber-950/30 border-amber-800/60 text-amber-200'
                : 'bg-amber-50 border-amber-200 text-amber-900'
            }`}
          >
            <AlertCircle size={15} className="text-amber-500 shrink-0 mt-0.5" />
            <p className="text-xs leading-relaxed">
              <strong>Lưu ý:</strong> Các thông số dưới đây là thiết kế dự kiến. Phần đánh dấu &quot;chưa đo&quot; sẽ được cập nhật sau khi lắp ráp và nạp firmware thật.
            </p>
          </div>

          {/* Spec Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div
              className={`p-3 rounded-sm border ${
                isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
              }`}
            >
              <span className="text-slate-400 text-[11px] font-semibold">VI ĐIỀU KHIỂN CHÍNH (MCU)</span>
              <div className="font-bold text-sm mt-0.5">ESP32 DevKit V1 (dự kiến)</div>
              <div className="text-slate-500 text-[11px] mt-0.5">BOM thực tế của nhóm dùng ESP32 thường, không phải S3</div>
            </div>

            <div
              className={`p-3 rounded-sm border ${
                isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
              }`}
            >
              <span className="text-slate-400 text-[11px] font-semibold">BỘ NHỚ RAM / FLASH</span>
              <div className="text-amber-600 dark:text-amber-400 font-bold text-sm mt-0.5">
                Chưa đo — sẽ đo sau khi nạp firmware
              </div>
              <div className="text-slate-500 text-[11px] mt-0.5">Tối ưu bộ đệm tròn theo cửa sổ trượt</div>
            </div>

            <div
              className={`p-3 rounded-sm border ${
                isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
              }`}
            >
              <span className="text-slate-400 text-[11px] font-semibold">TỐC ĐỘ XỬ LÝ (LATENCY)</span>
              <div className="text-amber-600 dark:text-amber-400 font-bold text-sm mt-0.5">
                Mục tiêu thiết kế: dưới 50 ms/cửa sổ (chưa đo)
              </div>
              <div className="text-slate-500 text-[11px] mt-0.5">Sẽ đo đạc thời gian thực thi trên xung clock thực tế</div>
            </div>

            <div
              className={`p-3 rounded-sm border ${
                isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
              }`}
            >
              <span className="text-slate-400 text-[11px] font-semibold">GIAO THỨC KẾT NỐI</span>
              <div className="font-bold text-sm mt-0.5">
                MQTT (dự kiến bổ sung Modbus RTU qua module MAX485)
              </div>
              <div className="text-slate-500 text-[11px] mt-0.5">Truyền telemetry và nhận lệnh xác nhận nhãn</div>
            </div>
          </div>

          {/* MQTT Topic Mapping */}
          <div
            className={`p-3.5 rounded-sm border space-y-2 ${
              isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-slate-700 dark:text-slate-300">
              <Terminal size={14} className="text-emerald-600 dark:text-emerald-400" />
              <span>Sơ đồ định tuyến MQTT Topic (Schema thiết kế của nhóm):</span>
            </div>
            <div className="space-y-1.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
              <div className="p-2 rounded-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <code>gw/01/ch/{'{n}'}/pred</code> → Bản tin nhãn dự đoán và độ tin cậy từ Gateway
              </div>
              <div className="p-2 rounded-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <code>gw/01/ch/{'{n}'}/label</code> → Bản tin kỹ sư xác nhận / chuẩn hóa nhãn kênh
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          className={`px-5 py-2.5 border-t flex justify-end ${
            isDarkMode ? 'border-slate-800 bg-slate-950/40' : 'border-slate-100 bg-slate-50/80'
          }`}
        >
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs transition-colors shadow-xs"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
