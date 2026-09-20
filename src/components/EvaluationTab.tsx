import React, { useState } from 'react';
import { BENCHMARK_METRICS, VI_NAMES } from '../data/metrics';
import {
  AlertTriangle,
  ShieldCheck,
  BarChart3,
  Info,
} from 'lucide-react';

interface EvaluationTabProps {
  isDarkMode?: boolean;
}

export const EvaluationTab: React.FC<EvaluationTabProps> = ({ isDarkMode = false }) => {
  const M = BENCHMARK_METRICS;
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);

  return (
    <div className="space-y-5">
      {/* Top Honest Engineering Warning Banner - Square Minimalist */}
      <div
        className={`p-4 rounded-md border transition-colors flex items-start gap-3.5 ${
          isDarkMode
            ? 'bg-amber-950/30 border-amber-800/60 text-amber-200'
            : 'bg-amber-50 border-amber-200 text-amber-950'
        }`}
      >
        <div className="p-1.5 rounded-sm bg-amber-500 text-white shrink-0 mt-0.5 shadow-xs">
          <AlertTriangle size={18} />
        </div>
        <div className="space-y-1">
          <h4 className="text-sm font-bold tracking-tight">
            Vì sao độ chính xác đạt 100%
          </h4>
          <p className="text-xs opacity-90 leading-relaxed">
            Toàn bộ số liệu dưới đây đo trên tín hiệu mô phỏng, được sinh bằng công thức toán nên bốn loại tín hiệu tách nhau rất rõ. Tín hiệu thật từ máy trong xưởng sẽ nhiễu hơn nhiều, và con số này chắc chắn sẽ giảm. Kết quả ở đây cho thấy quy trình huấn luyện và đánh giá chạy đúng, chưa nói lên độ tin cậy khi lắp vào nhà máy.
          </p>
        </div>
      </div>

      {/* Top 4 Key Metrics Cards - Square Minimalist */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div
          className={`p-4 rounded-md border transition-colors ${
            isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}
        >
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            TẬP MẪU KIỂM THỬ
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-slate-900 dark:text-white mt-1">
            {M.n_test} <span className="text-xs font-normal text-slate-500">cửa sổ</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Dữ liệu mô phỏng theo phiên
          </div>
        </div>

        <div
          className={`p-4 rounded-md border transition-colors ${
            isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}
        >
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            TỰ ĐỘNG HÓA GÁN NHÃN
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {(M.coverage * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Tỷ lệ mẫu vượt ngưỡng tự tin {'>'} 80%
          </div>
        </div>

        <div
          className={`p-4 rounded-md border transition-colors ${
            isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}
        >
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            TỶ LỆ BÁO ĐỘNG GIẢ
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {(M.false_alarm * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Tín hiệu bình thường bị gán nhầm OOD
          </div>
        </div>

        <div
          className={`p-4 rounded-md border transition-colors ${
            isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}
        >
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            BẮT TÍN HIỆU LẠ (OOD)
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-rose-600 dark:text-rose-400 mt-1">
            {(M.ood_with_oneclass * 100).toFixed(0)}%
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Khi kết hợp Isolation Forest One-Class
          </div>
        </div>
      </div>

      {/* Grid: Confusion Matrix & Traditional vs Edge AI Comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left 7 Cols: Interactive Confusion Matrix */}
        <div
          className={`lg:col-span-7 p-5 rounded-md border transition-colors space-y-4 ${
            isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
          }`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3 gap-2">
            <div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                Ma Trận Nhầm Lẫn Thực Nghiệm (Confusion Matrix)
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Đo trên 96 cửa sổ tín hiệu mô phỏng, tách theo phiên thu thập — chưa phải dữ liệu từ nhà máy
              </p>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded-sm bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 shrink-0 self-start sm:self-auto">
              Random Forest N=60 cây
            </span>
          </div>

          {/* Matrix Table */}
          <div className="overflow-x-auto pt-1">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr>
                  <th className="p-2 text-left text-slate-500 text-[11px] font-medium">
                    THỰC TẾ \ ĐOÁN
                  </th>
                  {M.classes.map((cls) => (
                    <th key={cls} className="p-2 text-center text-slate-700 dark:text-slate-300 text-xs font-semibold">
                      {VI_NAMES[cls]?.slice(0, 8) || cls}
                    </th>
                  ))}
                  <th className="p-2 text-center text-slate-500 text-[11px]">Độ Chính Xác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {M.confusion.map((row, rIdx) => {
                  const actualClass = M.classes[rIdx];
                  const total = row.reduce((a, b) => a + b, 0);
                  const correct = row[rIdx];
                  const accuracy = total > 0 ? (correct / total) * 100 : 0;

                  return (
                    <tr key={actualClass}>
                      <td className="p-2 font-medium text-slate-700 dark:text-slate-300 text-xs">
                        {VI_NAMES[actualClass] || actualClass}
                      </td>
                      {row.map((val, cIdx) => {
                        const isDiagonal = rIdx === cIdx;
                        const isHovered =
                          hoveredCell?.row === rIdx && hoveredCell?.col === cIdx;

                        return (
                          <td
                            key={cIdx}
                            onMouseEnter={() => setHoveredCell({ row: rIdx, col: cIdx })}
                            onMouseLeave={() => setHoveredCell(null)}
                            className={`p-2 text-center font-bold transition-all rounded-xs cursor-pointer ${
                              isDiagonal
                                ? val > 0
                                  ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                  : 'text-slate-400'
                                : val > 0
                                ? 'bg-rose-500/20 text-rose-600 dark:text-rose-400'
                                : 'text-slate-300 dark:text-slate-700'
                            } ${isHovered ? 'ring-2 ring-emerald-500' : ''}`}
                          >
                            {val}
                          </td>
                        );
                      })}
                      <td className="p-2 text-center font-bold text-emerald-600 dark:text-emerald-400">
                        {accuracy.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Cell Hover Detail Helper */}
          {hoveredCell && (
            <div
              className={`p-2.5 rounded-sm border text-xs leading-relaxed ${
                isDarkMode
                  ? 'bg-slate-950 border-slate-800 text-slate-300'
                  : 'bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <strong>Giải thích:</strong> Có{' '}
              <strong>{M.confusion[hoveredCell.row][hoveredCell.col]} mẫu</strong> thực tế là{' '}
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                &quot;{VI_NAMES[M.classes[hoveredCell.row]]}&quot;
              </span>{' '}
              được AI phân loại thành{' '}
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                &quot;{VI_NAMES[M.classes[hoveredCell.col]]}&quot;
              </span>
              .
            </div>
          )}
        </div>

        {/* Right 5 Cols: Traditional vs Edge AI Comparison */}
        <div className="lg:col-span-5 space-y-4">
          <div
            className={`p-5 rounded-md border transition-colors ${
              isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
            }`}
          >
            <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">So Sánh Phương Pháp Dò Cảm Biến</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 mb-3.5">
              Mục tiêu giải pháp khi tích hợp AI ngay tại biên Gateway
            </p>

            <div className="space-y-3 text-xs">
              {/* Traditional */}
              <div
                className={`p-3.5 rounded-sm border space-y-1.5 ${
                  isDarkMode
                    ? 'bg-slate-950/60 border-slate-800/80 text-slate-400'
                    : 'bg-slate-50 border-slate-200/80 text-slate-600'
                }`}
              >
                <div className="font-bold text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-xs bg-slate-400" />
                  <span>Cách làm truyền thống (Thủ công)</span>
                </div>
                <p>• Kỹ sư phải lật bản vẽ sơ đồ tủ điện cũ, cầm đồng hồ VOM đo từng dây.</p>
                <p>• <strong>Thời gian dò thủ công: đang chờ số liệu từ mentor DENSO</strong>.</p>
                <p>• Dễ nhầm lẫn giữa xung logic 24V và cảm biến tương tự khi tài liệu thất lạc.</p>
              </div>

              {/* Edge AI */}
              <div
                className={`p-3.5 rounded-sm border space-y-1.5 ${
                  isDarkMode
                    ? 'bg-emerald-950/20 border-emerald-800/50 text-emerald-200'
                    : 'bg-emerald-50/70 border-emerald-200/80 text-emerald-950'
                }`}
              >
                <div className="font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-xs bg-emerald-500" />
                  <span>Smart PLC Gateway (TinyML)</span>
                </div>
                <p>• Cắm dây vào cổng Gateway, <strong>AI phân tích tại biên, không cần gửi lên cloud</strong>.</p>
                <p>• <strong>Mục tiêu: dưới 30 phút (sẽ đo trên demo thật)</strong> để kỹ sư nghiệm thu và bấm xác nhận.</p>
                <p>• Cơ chế Isolation Forest giúp nhận diện và gắn cờ các xung bất thường / OOD.</p>
              </div>
            </div>
          </div>

          {/* Model Deployment Parameters */}
          <div
            className={`p-5 rounded-md border transition-colors ${
              isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-sm mb-3">
              <ShieldCheck size={16} className="text-emerald-600 dark:text-emerald-400" />
              <span>Thông Số Mô Hình Huấn Luyện (ml/train_eval.py)</span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500 dark:text-slate-400">Kiến trúc mô hình:</span>
                <strong className="font-mono">Isolation Forest + Random Forest (60 cây)</strong>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500 dark:text-slate-400">Số đặc trưng trích xuất:</span>
                <strong className="font-mono text-emerald-600 dark:text-emerald-400">16 đặc trưng tín hiệu</strong>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500 dark:text-slate-400">Thiết bị dự kiến nạp code:</span>
                <strong className="font-mono">ESP32 DevKit V1</strong>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-slate-500 dark:text-slate-400">Thời gian xử lý mục tiêu:</span>
                <strong className="text-amber-600 dark:text-amber-400">&lt; 50 ms/cửa sổ (chưa đo phần cứng)</strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Importance Chart Section with Disclaimed Note */}
      <div
        className={`p-5 rounded-md border transition-colors space-y-4 ${
          isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200 shadow-xs'
        }`}
      >
        <div className="flex items-center gap-2 font-bold text-sm">
          <BarChart3 size={17} className="text-emerald-600 dark:text-emerald-400" />
          <span>Đặc Trưng Đóng Góp Nhiều Nhất Vào Phân Loại (Feature Importance)</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {M.importance.map((item) => (
            <div
              key={item.name}
              className={`p-3 rounded-sm border space-y-1.5 ${
                isDarkMode ? 'bg-slate-950/60 border-slate-800' : 'bg-slate-50 border-slate-200/80'
              }`}
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                  {item.name}
                </span>
                <span className="font-mono text-slate-500 dark:text-slate-400">
                  {(item.score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-xs overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded-xs"
                  style={{ width: `${item.score * 100 * 3.5}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                {item.desc}
              </p>
            </div>
          ))}
        </div>

        {/* Disclaimer Note */}
        <div
          className={`p-3 rounded-sm border flex items-start gap-2.5 text-xs ${
            isDarkMode
              ? 'bg-slate-950 border-slate-800 text-slate-400'
              : 'bg-slate-100 border-slate-200 text-slate-600'
          }`}
        >
          <Info size={15} className="text-slate-400 shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            <strong>Ghi chú kỹ thuật:</strong> Số liệu từ mô hình Random Forest huấn luyện trên máy tính với 16 đặc trưng. Giao diện web hiển thị tập đặc trưng rút gọn (9 đặc trưng) để chạy realtime trong trình duyệt, nên không có <code>acf_lag1</code> và <code>acf_lag20</code> trên dashboard.
          </p>
        </div>
      </div>
    </div>
  );
};
