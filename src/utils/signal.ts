import { SignalFeatures, SignalClass } from '../types';

export const CONF_TH = 0.75;
export const OOD_TH = 0.45;
export const WINDOW_SIZE = 160;

// Dải điện áp hợp lệ sau mạch hạ áp (chuẩn analog công nghiệp 0-10V quy về thang 0-120).
// Luật này KHÔNG dùng mô hình — nó bắt đúng thứ mô hình không bắt được:
// đấu ngược cực làm dạng sóng lật quanh trung bình nhưng giữ nguyên mọi đặc trưng
// thống kê, nên chỉ có kiểm tra mức tuyệt đối mới phát hiện ra.
export const VALID_MIN = 0;
export const VALID_MAX = 120;

/**
 * Tạo mẫu tín hiệu thời gian thực từ PLC mô phỏng các thiết bị trong nhà máy
 */
export function sampleSignal(
  kind: string,
  t: number,
  anomalyMode: boolean = false,
  wiringFault: boolean = false,
): number {
  if (wiringFault) {
    // Giả lập đấu ngược cực: dạng sóng lật quanh mức giữa, tràn xuống dưới 0V.
    // Mô hình KHÔNG phát hiện được (mọi đặc trưng thống kê giữ nguyên),
    // chỉ luật kiểm tra dải tuyệt đối mới bắt được.
    return 60 - (52 + 9.5 * Math.sin(t / 95) + 2.8 * Math.sin(t / 31)) * 2.4
           + (Math.random() - 0.5) * 2;
  }
  if (anomalyMode) {
    // Chế độ mô phỏng xung dị biệt OOD (Áp suất vọt đỉnh, nhiễu hồ quang, chạm chập)
    if (t % 45 < 8) {
      return 85 + Math.random() * 45 + Math.sin(t * 1.8) * 20;
    }
    return 15 + (Math.random() - 0.5) * 8;
  }

  switch (kind) {
    case 'temperature':
      // Tín hiệu nhiệt độ lò sấy / khuôn đúc: Quán tính nhiệt lớn, trôi chậm, nhiễu đo lường nhỏ
      return 52 + 9.5 * Math.sin(t / 95) + 2.8 * Math.sin(t / 31) + (Math.random() - 0.5) * 0.65;

    case 'vibration':
      // Cảm biến gia tốc rung động ổ bi / động cơ: Tần số cao, dải động lớn, zero-crossing dồn dập
      return 50 + 17.5 * Math.sin(t / 1.12) + 6.8 * Math.sin(t / 0.58) + 3.2 * Math.sin(t / 0.23) + (Math.random() - 0.5) * 5.2;

    case 'counter':
      // Bộ đếm sản phẩm băng chuyền PLC (24V Logic chuyển qua ADC): Bậc thang 4 mức rõ rệt
      const stepPhase = Math.floor((t % 64) / 16);
      return 16 + stepPhase * 21 + (Math.random() - 0.5) * 0.9;

    case 'motor':
      // Tải dòng điện động cơ máy dập / tiện: Chu kỳ tải làm việc cơ học có trễ
      const loadCycle = Math.sin(t / 24);
      const ripple = Math.sin(t / 2.3) * 3.5;
      return 36 + loadCycle * 14 + ripple + (Math.random() - 0.5) * 1.8;

    case 'exotic':
    default:
      // Tín hiệu van áp suất xung đột biến ngẫu nhiên (OOD - Chưa từng huấn luyện trong tập train)
      if (t % 65 < 14) {
        return 32 + Math.random() * 62 + Math.sin(t * 0.9) * 15;
      }
      return 21 + (Math.random() - 0.5) * 3.5;
  }
}

/**
 * Trích xuất vector đặc trưng thống kê thời gian thực (bản TypeScript dùng cho giao diện; bản chuẩn là features.py)
 */
export function extractFeatures(buf: number[]): SignalFeatures {
  const n = buf.length;
  if (n === 0) {
    return { mean: 0, std: 0, zcr: 0, slew: 0, maxSlew: 0, levels: 0, kurt: 3,
             vpp: 0, rms: 0, acfLag1: 0, acfLag20: 0 };
  }

  let sum = 0;
  let min = buf[0];
  let max = buf[0];
  let sumSq = 0;

  for (let i = 0; i < n; i++) {
    const val = buf[i];
    sum += val;
    sumSq += val * val;
    if (val < min) min = val;
    if (val > max) max = val;
  }

  const mean = sum / n;
  const rms = Math.sqrt(sumSq / n);
  const vpp = max - min;

  let varSum = 0;
  let crossCount = 0;
  let slewSum = 0;
  let maxSlew = 0;

  for (let i = 0; i < n; i++) {
    const diff = buf[i] - mean;
    varSum += diff * diff;

    if (i > 0) {
      if ((buf[i - 1] - mean) * diff < 0) {
        crossCount++;
      }
      const d = Math.abs(buf[i] - buf[i - 1]);
      slewSum += d;
      if (d > maxSlew) maxSlew = d;
    }
  }

  const std = Math.sqrt(varSum / n);
  const zcr = crossCount / n;
  const slew = n > 1 ? slewSum / (n - 1) : 0;

  // Đếm số lượng mức giá trị phân mảnh (discrete quantised levels)
  const quantized = new Set<number>();
  for (let i = 0; i < n; i++) {
    quantized.add(Math.round(buf[i] / 8.5));
  }
  const levels = quantized.size;

  // Tính Kurtosis (Độ nhọn phân phối)
  let kurtSum = 0;
  const safeStd = std || 1;
  for (let i = 0; i < n; i++) {
    kurtSum += Math.pow((buf[i] - mean) / safeStd, 4);
  }
  const kurt = kurtSum / n;

  // Tự tương quan: so tín hiệu với chính nó sau một độ trễ.
  // Cao ở trễ ngắn = biến thiên mượt; cao ở trễ dài = có chu kỳ lặp.
  // acf_lag20 là đặc trưng đóng góp nhiều nhất theo mô hình đã huấn luyện.
  const acf = (lag: number): number => {
    if (n <= lag) return 0;
    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i++) den += (buf[i] - mean) ** 2;
    for (let i = 0; i < n - lag; i++) num += (buf[i] - mean) * (buf[i + lag] - mean);
    return den === 0 ? 0 : num / den;
  };

  return { mean, std, zcr, slew, maxSlew, levels, kurt, vpp, rms,
           acfLag1: acf(1), acfLag20: acf(20) };
}

/**
 * Kiểm tra dải tuyệt đối — luật cứng, không dùng mô hình.
 *
 * Mô hình mù trước lỗi đấu ngược cực vì extractFeatures chuẩn hóa biên độ,
 * và lật dạng sóng quanh trung bình giữ nguyên độ lệch chuẩn, tần suất cắt mức,
 * tốc độ biến thiên. Luật này bắt đúng chỗ đó: nếu tín hiệu ra ngoài dải hợp lệ
 * thì gần như chắc chắn là lỗi đấu nối, không phải tín hiệu lạ cần kỹ sư định danh.
 */
export function checkWiring(buf: number[]): { ok: boolean; reason?: string } {
  if (buf.length < 10) return { ok: true };
  const below = buf.filter((v) => v < VALID_MIN).length / buf.length;
  const above = buf.filter((v) => v > VALID_MAX).length / buf.length;
  if (below > 0.05) return { ok: false, reason: 'Tín hiệu xuống dưới 0V — nghi đấu ngược cực' };
  if (above > 0.05) return { ok: false, reason: 'Tín hiệu vượt dải đo — nghi sai loại cổng hoặc quá áp' };
  return { ok: true };
}

/**
 * Mô phỏng hành vi của pipeline Edge AI bằng luật ngưỡng viết tay,
 * để giao diện chạy được realtime trong trình duyệt.
 *
 * Mô hình THẬT (Random Forest + Isolation Forest, scikit-learn) nằm ở
 * ml/train_eval.py và chạy trên thiết bị. Các con số ở tab Đánh giá
 * lấy từ mô hình thật đó, không phải từ hàm này.
 */
export function classifySignal(f: SignalFeatures): { cls: SignalClass; conf: number; oodScore: number } {
  // 1. Ước lượng điểm bất thường bằng luật ngưỡng (thay cho Isolation Forest ở bản thiết bị)
  let oodScore = 0.12;
  if (f.kurt > 4.5 || (f.maxSlew > 28 && f.levels > 7)) {
    oodScore = 0.88;
  } else if (f.kurt > 3.8 || f.maxSlew > 22) {
    oodScore = 0.65;
  } else if (f.zcr < 0.01 && f.slew > 4) {
    oodScore = 0.55;
  }

  // 2. Điểm từng lớp bằng luật ngưỡng (thay cho Random Forest ở bản thiết bị)
  const scores: Record<SignalClass, number> = {
    TEMPERATURE: 0,
    VIBRATION: 0,
    COUNTER: 0,
    MOTOR_LOAD: 0,
    PRESSURE_BURST: 0,
    OTHER: 0,
  };

  // Luật phân loại dựa trên đặc trưng vật lý:
  // - Nhiệt độ: ZCR rất thấp (<0.06), slew chậm (<1.6), std vừa phải
  scores.TEMPERATURE =
    (f.zcr < 0.055 ? 0.45 : 0) +
    (f.slew < 1.75 ? 0.35 : 0) +
    (f.std < 10.5 && f.std > 3 ? 0.20 : 0);

  // - Rung động: ZCR cực cao (>0.18), slew rất lớn (>4.2), std > 9
  scores.VIBRATION =
    (f.zcr > 0.17 ? 0.48 : 0) +
    (f.slew > 4.2 ? 0.34 : 0) +
    (f.std > 9.5 ? 0.18 : 0);

  // - Bộ đếm xung: Số mức rời rạc thấp (<=5), slew bình quân thấp nhưng maxSlew bước nhảy cao
  scores.COUNTER =
    (f.levels <= 5 ? 0.44 : 0) +
    (f.slew < 3.2 ? 0.28 : 0) +
    (f.maxSlew > 13 ? 0.28 : 0);

  // - Tải động cơ: ZCR trung bình (0.07 - 0.17), std 7 - 15, kurtosis bình thường ~2-3.5
  scores.MOTOR_LOAD =
    (f.zcr >= 0.06 && f.zcr <= 0.18 ? 0.46 : 0) +
    (f.std >= 6.5 && f.std <= 15 ? 0.32 : 0) +
    (f.kurt >= 1.8 && f.kurt <= 3.8 ? 0.22 : 0);

  let bestClass: SignalClass = 'TEMPERATURE';
  let bestScore = 0;
  let secondScore = 0;

  for (const key of ['TEMPERATURE', 'VIBRATION', 'COUNTER', 'MOTOR_LOAD'] as SignalClass[]) {
    const s = scores[key];
    if (s > bestScore) {
      secondScore = bestScore;
      bestScore = s;
      bestClass = key;
    } else if (s > secondScore) {
      secondScore = s;
    }
  }

  // Margin tin cậy (Confidence)
  let conf = bestScore - secondScore * 0.22;

  // Nếu điểm bất thường vượt ngưỡng, hạ độ tin cậy để đẩy sang trạng thái Unknown
  if (oodScore > 0.6) {
    conf = Math.max(0.1, conf - oodScore * 0.65);
    if (oodScore > 0.75) {
      bestClass = 'PRESSURE_BURST';
    }
  }

  conf = Math.min(Math.max(0.15, conf), 0.98);

  return { cls: bestClass, conf, oodScore };
}
