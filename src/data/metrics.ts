export interface ClassMeta {
  code: string;
  nameVi: string;
  nameEn: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
  sampleUnit: string;
  typicalRange: string;
}

export const SIGNAL_CLASSES: Record<string, ClassMeta> = {
  TEMPERATURE: {
    code: 'TEMPERATURE',
    nameVi: 'Cảm biến Nhiệt độ',
    nameEn: 'Temperature Sensor',
    description: 'Tín hiệu tần số thấp, biến thiên mượt mà dạng quán tính nhiệt, độ lệch chuẩn thấp.',
    color: '#06b6d4', // cyan-500
    bgColor: 'rgba(6, 182, 212, 0.1)',
    borderColor: 'rgba(6, 182, 212, 0.3)',
    sampleUnit: '°C (4-20mA)',
    typicalRange: '40 - 75 °C',
  },
  VIBRATION: {
    code: 'VIBRATION',
    nameVi: 'Cảm biến Rung động',
    nameEn: 'Vibration / Accelerometer',
    description: 'Tần số dao động cao, zero-crossing rate lớn, biến thiên dốc và liên tục.',
    color: '#8b5cf6', // violet-500
    bgColor: 'rgba(139, 92, 246, 0.1)',
    borderColor: 'rgba(139, 92, 246, 0.3)',
    sampleUnit: 'mm/s² (0-10V)',
    typicalRange: '20 - 85 mm/s²',
  },
  COUNTER: {
    code: 'COUNTER',
    nameVi: 'Bộ đếm xung PLC',
    nameEn: 'Discrete Step Counter',
    description: 'Tín hiệu số bậc thang phân mảnh, số mức rời rạc thấp, độ dốc thay đổi tức thời.',
    color: '#10b981', // emerald-500
    bgColor: 'rgba(16, 185, 129, 0.1)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
    sampleUnit: 'Xung (24V Logic)',
    typicalRange: '0 - 80 Pulse',
  },
  MOTOR_LOAD: {
    code: 'MOTOR_LOAD',
    nameVi: 'Tải động cơ / Dòng điện',
    nameEn: 'Motor Current Load',
    description: 'Biến thiên trung bình theo chu kỳ tải cơ học, độ dốc vừa phải, kurtosis chuẩn.',
    color: '#f59e0b', // amber-500
    bgColor: 'rgba(245, 158, 11, 0.1)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
    sampleUnit: 'Amperes (CT)',
    typicalRange: '15 - 45 A',
  },
  PRESSURE_BURST: {
    code: 'PRESSURE_BURST',
    nameVi: 'Dị biệt: Xung áp suất đột biến',
    nameEn: 'Out-of-Distribution Pressure Burst',
    description: 'Tín hiệu lạ hoàn toàn chưa có trong dữ liệu huấn luyện (OOD Anomaly), biên độ xung cực lớn.',
    color: '#f43f5e', // rose-500
    bgColor: 'rgba(244, 63, 94, 0.1)',
    borderColor: 'rgba(244, 63, 94, 0.3)',
    sampleUnit: 'Bar (Transducer)',
    typicalRange: '0 - 120 Bar',
  },
  OTHER: {
    code: 'OTHER',
    nameVi: 'Loại tín hiệu khác',
    nameEn: 'Unspecified Signal',
    description: 'Tín hiệu do kỹ sư thủ công gán nhãn tùy biến.',
    color: '#64748b',
    bgColor: 'rgba(100, 116, 139, 0.1)',
    borderColor: 'rgba(100, 116, 139, 0.3)',
    sampleUnit: 'Raw',
    typicalRange: '0 - 100',
  }
};

export const VI_NAMES: Record<string, string> = {
  TEMPERATURE: 'Nhiệt độ',
  VIBRATION: 'Rung động',
  COUNTER: 'Bộ đếm xung',
  MOTOR_LOAD: 'Tải động cơ',
  PRESSURE_BURST: 'Xung áp suất (OOD)',
  UNKNOWN: 'Tín hiệu lạ (OOD)',
  OTHER: 'Loại khác',
};

export const BENCHMARK_METRICS = {
  n_train: 192,
  n_test: 96,
  n_ood: 36,
  classes: ['COUNTER', 'MOTOR_LOAD', 'TEMPERATURE', 'VIBRATION'],
  ood_class: 'PRESSURE_BURST',
  baseline_accuracy: 0.25,
  coverage: 0.875, // 87.5% tự động trả lời, phần còn lại chuyển kỹ sư
  false_alarm: 0.0104, // 1.0% báo động nhầm trên tín hiệu bình thường
  ood_conf_only: 0.083, // 8.3% nếu chỉ dựa vào ngưỡng tin cậy
  ood_with_oneclass: 1.0, // 100% khi thêm mô hình one-class Isolation Forest
  conf_threshold: 0.728,
  iso_threshold: -0.6294,
  confusion: [
    [24, 0, 0, 0],
    [0, 24, 0, 0],
    [0, 0, 24, 0],
    [0, 0, 0, 24],
  ],
  class_performance: [
    { code: 'COUNTER', name: 'Bộ đếm xung', precision: 1.0, recall: 1.0, f1: 1.0, samples: 24 },
    { code: 'MOTOR_LOAD', name: 'Tải động cơ', precision: 1.0, recall: 1.0, f1: 1.0, samples: 24 },
    { code: 'TEMPERATURE', name: 'Cảm biến Nhiệt độ', precision: 1.0, recall: 1.0, f1: 1.0, samples: 24 },
    { code: 'VIBRATION', name: 'Cảm biến Rung động', precision: 1.0, recall: 1.0, f1: 1.0, samples: 24 },
  ],
  importance: [
    { name: 'acf_lag20', score: 0.2184, desc: 'Tự tương quan trễ 20 — đo tính tuần hoàn chu kỳ dài của tải động cơ' },
    { name: 'slew_mean', score: 0.1832, desc: 'Tốc độ biến thiên trung bình — nhận diện quán tính nhiệt với rung tần cao' },
    { name: 'acf_lag1', score: 0.1314, desc: 'Tự tương quan trễ 1 — phân biệt dao động liên tục với tín hiệu rời rạc' },
    { name: 'lowband_ratio', score: 0.1002, desc: 'Tỷ lệ năng lượng dải tần thấp — tín hiệu quá trình tập trung ở tần thấp' },
    { name: 'zcr', score: 0.0977, desc: 'Tần suất cắt mức trung bình — xác định dải tần rung động' },
    { name: 'spec_centroid', score: 0.0946, desc: 'Trọng tâm phổ — vị trí trung bình của năng lượng trên trục tần số' },
    { name: 'spec_entropy', score: 0.0562, desc: 'Entropy phổ — tín hiệu tuần hoàn có entropy thấp, nhiễu có entropy cao' },
    { name: 'kurtosis', score: 0.0240, desc: 'Độ nhọn phân phối — nhạy với xung đột biến' },
  ],
};
