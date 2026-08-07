#  ALGORITHM.md - Chi Tiết Thuật Toán Xử Lý CSI
# LongVo
---

## **OVERVIEW: 12 Giai Đoạn Xử Lý**

```
[1] Nhận CSI từ Serial
    ↓
[2] Tách I/Q → Tính Amplitude
    ↓
[3] Lọc Subcarrier DC/Null
    ↓
[4] Kiểm Frame Hợp Lệ
    ↓
[5] Chuẩn Hóa CSI (Trừ Median)
    ↓
[6] Gom Buffer & Tính Energy
    ↓
[7] Tính Motion (Temporal Variance)
    ↓
[8] Hiệu Chuẩn Baseline (500 frame)
    ↓
[9] Tính Threshold & Phân Loại State
    ↓
[10] Smooth State (Majority Vote)
    ↓
[11] State Machine + Hysteresis
    ↓
[12] Output JSON → WebSocket
```

---

## **GIAI ĐOẠN 1-2: NHẬN & CHUYỂN ĐỔI CSI**

### **1.1 Nhận CSI từ Serial**

**Input từ ESP32 RX:**
```
CSI_DATA [100, 50, 120, 60, 110, 70, ..., 95, 45]  (384 giá trị)
```

**Ý nghĩa:**
- 96 subcarrier × 2 (I & Q) = 192 tín hiệu
- Nhận × 2 (ứng với 2 antenna) = 384 giá trị

### **1.2 Tách I & Q**

```python
I_vals = csi_amplitudes[0::2]    # Chỉ số 0, 2, 4, ...   (192 giá trị)
Q_vals = csi_amplitudes[1::2]    # Chỉ số 1, 3, 5, ...   (192 giá trị)
```

**Example:**
```
Thô:       [I0, Q0, I1, Q1, I2, Q2, ...]
           [100, 50, 120, 60, ...]

Sau tách:
I_vals = [100, 120, 110, ...]
Q_vals = [50,  60,  70,  ...]
```

### **1.3 Tính Amplitude (Magnitude)**

```python
amplitudes = √(I² + Q²)
```

**Example:**
```
amplitude[0] = √(100² + 50²) = √12500 ≈ 111.8
amplitude[1] = √(120² + 60²) = √18000 ≈ 134.2
```

**Tác dụng:** Loại bỏ thông tin pha, chỉ giữ lại độ lớn của tín hiệu

---

## **GIAI ĐOẠN 3: LỌC SUBCARRIER DC & NULL**

### **3.1 Danh Sách Loại Bỏ**

```python
invalid_index = [0, 1, 2, 3, 4, 5,        # DC (Subcarrier 0-5)
                 31, 32, 33,              # Null subcarrier (middle)
                 59, 60, 61, 62, 63, 64, 65]  # Null subcarrier (high)

valid_index = [i for i in range(96)
               if i not in invalid_index]
# Kết quả: 80 subcarrier tốt
```

### **3.2 Tại Sao Loại Bỏ?**

| Loại | Lý Do Loại Bỏ |
|------|---|
| **Subcarrier 0-5 (DC)** | Nhiễu DC offset từ RF chain, không thông tin hoạt động |
| **Subcarrier 31-33** | Null subcarrier (middle), không có dữ liệu |
| **Subcarrier 59-65** | Null subcarrier (guard band), nhiễu cao |

**Kết quả:** Từ 192 → 80 subcarrier sạch, loại bỏ ~58% nhiễu

---

## **GIAI ĐOẠN 4: KIỂM FRAME HỢP LỆ**

### **4.1 Loại Bỏ Frame Lỗi**

```python
if np.max(current_frame_features) < 5 or np.max(current_frame_features) > 1000:
    continue  # Bỏ frame này
```

### **4.2 Lý Do**

- **max < 5**: CSI quá yếu → có khả năng lỗi hardware
- **max > 1000**: Bão hòa RF chain → dữ liệu không tin cậy

**Tác dụng:** Lọc ~2-5% frame lỗi, nâng chất lượng dữ liệu

---

## **GIAI ĐOẠN 5: CHUẨN HÓA CSI (MEDIAN NORMALIZATION)**

### **5.1 Bước Thực Hiện**

```python
median_val = np.median(current_frame_features)  # Trung vị của 80 subcarrier
current_frame_features = current_frame_features - median_val
```

### **5.2 Ví Dụ Chi Tiết**

```
Trước chuẩn hóa:  [110, 105, 120, 100, 115, ...]
Median:           107
Sau chuẩn hóa:    [3, -2, 13, -7, 8, ...]  (đưa về "trung bình = 0")
```

### **5.3 Tác Dụng**

- ✅ Loại bỏ **DC offset** chung
- ✅ Giảm ảnh hưởng **AGC (Automatic Gain Control)**
- ✅ Loại bỏ **RSSI scaling** từ firmware
- ✅ Làm dữ liệu **nhất quán** giữa các frame

**Kết quả:** Accuracy tăng ~10-15%

---

## **GIAI ĐOẠN 6: GOM BUFFER & TÍNH ENERGY**

### **6.1 Buffer Sliding Window**

```python
amplitude_buffer = deque(maxlen=20)  # Lưu 20 frame gần nhất
amplitude_buffer.append(current_frame_features)
```

**Cơ chế:**
- Frame 1: buffer = [F1]
- Frame 2: buffer = [F1, F2]
- ...
- Frame 20: buffer = [F1, F2, ..., F20]
- Frame 21: buffer = [F2, F3, ..., F21]  (F1 bị xóa)

### **6.2 Tính Energy (Năng Lượng Tức Thời)**

```python
current_energy = np.std(current_frame_features)
# Standard Deviation = √(Σ(x_i - mean)²/N)
```

**Example:**
```
Frame: [-5, 0, 10, -5, 0, ...]
Mean: 0
Std: √((25 + 0 + 100 + 25 + 0 + ...)/n) ≈ 7.2
```

**Ý Nghĩa:**
- **Energy cao** (~15+): Có người / tín hiệu phức tạp
- **Energy thấp** (~3-5): Trống / tín hiệu đơn giản

---

## **GIAI ĐOẠN 7: TÍNH MOTION (CHUYỂN ĐỘNG)**

### **7.1 Khái Niệm**

Motion = **Độ biến động thời gian** của Energy

### **7.2 Tính Toán Chi Tiết**

**Bước 1:** Chuyển buffer thành matrix 20×80

```
buffer_arr = [
  [a1, a2, a3, ..., a80],     # Frame 1
  [b1, b2, b3, ..., b80],     # Frame 2
  ...
  [t1, t2, t3, ..., t80]      # Frame 20
]
```

**Bước 2:** Tính std theo thời gian (axis=0)

```python
temporal_std = np.std(buffer_arr, axis=0)  # 80 giá trị
# temporal_std[i] = std(subcarrier_i qua 20 frame)
```

**Example:**
```
Subcarrier 0:     [100, 105, 102, 108, 103] → std ≈ 3.2
Subcarrier 1:     [50, 52, 48, 55, 50]     → std ≈ 2.4
Subcarrier 2:     [200, 195, 210, 185, 220] → std ≈ 12.1
...
temporal_std = [3.2, 2.4, 12.1, ..., 5.6]  (80 giá trị)
```

**Bước 3:** Lấy Percentile 80

```python
raw_motion_score = np.percentile(temporal_std, 80) * 10
# Ví dụ: temporal_std = [0.5, 1.2, 0.8, 2.3, 1.6, ...]
#        percentile(80) ≈ 2.0 (80% của dữ liệu nhỏ hơn 2.0)
#        raw_motion_score = 2.0 * 10 = 20.0
```

**Bước 4:** Smooth Motion (Median 5 frame)

```python
motion_history.append(raw_motion_score)  # Lưu 5 giá trị gần nhất
motion_score = np.median(motion_history)  # Lấy trung vị
```

**Tác dụng:** Lọc spike, làm mịn motion score

---

## **GIAI ĐOẠN 8: HIỆU CHUẨN BASELINE (500 FRAME)**

### **8.1 Mục Đích**

Xác định "nền yên" của môi trường (không có người).

### **8.2 Công Thức EWMA**

```python
if frame_count <= 500:
    ewma_baseline_energy = 0.1 * current_energy + 0.9 * ewma_baseline_energy
    ewma_baseline_motion = 0.1 * motion_score + 0.9 * ewma_baseline_motion
# Alpha = 0.1 (10% giá trị mới, 90% giá trị cũ)
```

### **8.3 Ví Dụ Evolution**

```
Frame 1: baseline = 10.0 (giá trị khởi tạo)
Frame 2: baseline = 0.1×11 + 0.9×10.0 = 10.1
Frame 3: baseline = 0.1×9 + 0.9×10.1 = 10.09
...
Frame 100: baseline → dần dần convergence
...
Frame 500: baseline ổn định ≈ 10.5 (giá trị thực tế)
```

### **8.4 Lợi Ích**

- ✅ Tự động thích nghi với môi trường
- ✅ Không cần nhân viên hiệu chuẩn thủ công
- ✅ Latency: chỉ ~50s (500 frame × ~100ms/frame)

---

## **GIAI ĐOẠN 9: TÍNH THRESHOLD & PHÂN LOẠI STATE**

### **9.1 Tính Energy Std Dev**

```python
energy_std_dev = np.std(energy_history)  # Std của 50 frame gần nhất
# energy_history lưu 50 giá trị energy tức thời
```

### **9.2 Tính Margin (Cushion)**

```python
base_energy_margin = max(1.0, 1.5 * energy_std_dev)
# Nếu energy_std_dev = 2.0 → margin = 3.0
# Nếu energy_std_dev = 0.3 → margin = 1.0 (tối thiểu)

base_motion_margin = 4.0  # Cố định
```

**Ý Tưởng:** Margin lớn hơn khi dữ liệu biến đổi (ổn định kém)

### **9.3 Tính Final Threshold**

```python
energy_threshold_1 = ewma_baseline_energy + base_energy_margin
motion_threshold_2 = ewma_baseline_motion + base_motion_margin

# Ví dụ:
# baseline_energy = 8.0, margin = 2.0 → threshold = 10.0
# baseline_motion = 5.0, margin = 4.0 → threshold = 9.0
```

### **9.4 Phân Loại State (Raw)**

```python
if motion_score > motion_threshold_2:
    raw_state = 2    # 🟢 ĐANG HOẠT ĐỘNG (Motion cao)
elif smoothed_energy > energy_threshold_1 or motion_score > (baseline_motion + 1.5):
    raw_state = 1    # 🟡 ĐỨNG YÊN (Energy cao hoặc motion trung bình)
else:
    raw_state = 0    # 🔴 KHÔNG CÓ NGƯỜI (Cả hai thấp)
```

**Bảng Quyết Định:**

| Motion | Energy | → State |
|--------|--------|---------|
| > 9.0 | - | 2 (Hoạt động) |
| 5-9 | > 10 | 1 (Đứng yên) |
| 5-9 | < 10 | 0 (Trống) |
| < 5 | - | 0 (Trống) |

---

## **GIAI ĐOẠN 10: SMOOTH STATE (MAJORITY VOTE)**

### **10.1 Cơ Chế**

```python
state_history.append(raw_state)  # Lưu 4 frame gần nhất

if len(state_history) >= 4:
    vals, counts = np.unique(state_history, return_counts=True)
    smoothed_raw_state = vals[np.argmax(counts)]  # State xuất hiện nhiều nhất
else:
    smoothed_raw_state = raw_state
```

### **10.2 Ví Dụ**

```
state_history = [0, 0, 1, 0]
vals = [0, 1]
counts = [3, 1]
smoothed_raw_state = 0  (xuất hiện 3 lần > 1 lần)
```

### **10.3 Quy Tắc Chống Flicker 0→1**

```python
if current_state == 0 and smoothed_raw_state == 1:
    smoothed_raw_state = 0  # Bắt buộc qua state 2 trước
```

**Ý Đồ:** Tránh nhầm một cái "cảm động" khi có người = "người đứng yên"

---

## **GIAI ĐOẠN 11: STATE MACHINE + HYSTERESIS**

### **11.1 Ba Trường Hợp Transition**

**Case 1: LÊN NGAY (0→1 hoặc 1→2)**

```python
if smoothed_raw_state > current_state:
    current_state = smoothed_raw_state  # Thay đổi ngay
    down_counter = 0
```

**Case 2: XUỐNG CÓ TRỄ (Có requred_frames)**

```python
elif smoothed_raw_state < current_state:
    if smoothed_raw_state == 0:
        required_frames = 60  # 60 frame để rớt xuống trống
    else:
        required_frames = 20  # 20 frame để rớt xuống đứng yên
    
    if smoothed_raw_state == target_drop_state:
        down_counter += 1      # Tăng counter
    else:
        target_drop_state = smoothed_raw_state
        down_counter = 1       # Reset
    
    if down_counter >= required_frames:
        current_state = smoothed_raw_state  # Thực hiện transition
        down_counter = 0
```

**Case 3: NGANG (Giữ nguyên)**

```python
else:
    down_counter = 0
```

### **11.2 Timeline Ví Dụ**

```
Frame → State (raw) | State (smooth) | Down Counter | Final State
1      → 2         | 2              | -            | 2
2      → 2         | 2              | -            | 2
3      → 1         | 1              | 1/60         | 2
4      → 1         | 1              | 2/60         | 2
5      → 1         | 1              | 3/60         | 2
...
60     → 1         | 1              | 60/60        | 1 (✓ Transition OK)
```

### **11.3 Tác Dụng Hysteresis**

- ✅ **Giảm flicker**: Không thay đổi state liên tục
- ✅ **Tránh noise**: Một vài frame sai không ảnh hưởng
- ✅ **Phản ứng thực**: Đảm bảo người thực sự dừng ~2 giây mới "trống"

---

## **GIAI ĐOẠN 12: UPDATE EWMA THÍCH NGHI**

### **12.1 Ba trường hợp cập nhật**

**State 0 (TRỐNG):** Cập nhật nhanh

```python
if current_state == 0:
    alpha_val = 0.03  # 3% giá trị mới, 97% cũ
    ewma_baseline_energy = 0.03 * current_energy + 0.97 * ewma_baseline_energy
    ewma_baseline_motion = 0.03 * motion_score + 0.97 * ewma_baseline_motion
    energy_history.append(current_energy)
```

**State 1 (ĐỨNG YÊN):** Cập nhật rất chậm

```python
elif current_state == 1:
    alpha_val = 0.002  # 0.2% giá trị mới, 99.8% cũ
    ewma_baseline_motion = 0.002 * motion_score + 0.998 * ewma_baseline_motion
    # KHÔNG cập energy_history
```

**State 2 (HOẠT ĐỘNG):** Không cập gì

```python
else:
    pass  # Tránh "target shift"
```

### **12.2 Tại Sao Khác Nhau?**

| State | Alpha | Lý Do |
|-------|-------|-------|
| 0 | 0.03 | Môi trường thay đổi → cập nhanh |
| 1 | 0.002 | Người ổn định → cập chậm (tránh drift) |
| 2 | 0 | Đang hoạt động → lock baseline |

---

## **GIAI ĐOẠN 13: OUTPUT & THỐNG KÊ**

### **13.1 Đếm Frame**

```python
total_valid_frames += 1          # Tăng frame hợp lệ

if current_state == 2:
    total_active_frames += 1     # Chỉ frame hoạt động (state 2)
```

### **13.2 Tính Phần Trăm**

```python
if total_valid_frames > 0:
    percent_active = (total_active_frames / total_valid_frames) * 100.0
else:
    percent_active = 0.0
```

**Ví dụ:**
```
total_valid_frames = 1000
total_active_frames = 650
percent_active = 65.0%
```

### **13.3 Đánh Giá**

```python
is_passed = "Đạt" if percent_active >= PASS_THRESHOLD else "Không đạt"
# PASS_THRESHOLD = 50% (có thể tuỳ chỉnh)
```

---

## **GIAI ĐOẠN 14: SEND JSON → WEBSOCKET**

```python
latest_data = {
    "prediction": LABELS[current_state],    # "Không có người", "Đứng yên", "Hoạt động"
    "motion_score": float(motion_score),    # ~20.0
    "energy": float(smoothed_energy),       # ~12.0
    "rolling_mean": float(ewma_baseline_energy),  # ~10.0
    "threshold": float(energy_threshold_1),      # ~12.25
    "motion_threshold": float(motion_threshold_2),# ~9.0
    "total_valid": int(total_valid_frames),      # 1000
    "total_active": int(total_active_frames),    # 650
    "percent_active": float(percent_active),     # 65.0
    "class": int(current_state),                 # 0, 1, hoặc 2
    "evaluation": is_passed                      # "Đạt" / "Không đạt"
}
```

**Gửi mỗi 50ms qua WebSocket → Browser**

---

## **TÓMSÁT CÔNG THỨC TOÁN**

| Công Thức | Mục Đích | Code |
|-----------|---------|------|
| Magnitude | Tín hiệu | `√(I²+Q²)` |
| Chuẩn hóa | Loại DC | `x - median(x)` |
| Energy | Biến động KG | `std(frame)` |
| Motion | Biến động TG | `percentile(temporal_std, 80) × 10` |
| EWMA | Baseline | `α×new + (1-α)×old` |
| Threshold | Ngưỡng | `baseline + margin` |
| State | Phân loại | `if-else` |
| Smooth | Filter | `majority_vote(4_frame)` |
| Hysteresis | Trễ | `required_frames counter` |
| Percent | Tỷ lệ | `(active/valid) × 100` |

---

## **PARAMETERS TUNING GUIDE**

| Tham Số | Mặc Định | Tăng | Giảm |
|---------|---------|------|------|
| FEATURE_WINDOW | 20 | Mịn hơn | Nhanh hơn |
| CALIBRATION_FRAMES | 500 | Ổn định | Nhanh start |
| alpha (state 0) | 0.03 | Chậm thích nghi | Nhanh drift |
| required_frames (to 0) | 60 | Ít flicker | Phản ứng nhanh |
| required_frames (to 1) | 20 | Ít flicker | Phản ứng nhanh |
| base_energy_margin | 1.5× | Kém nhạy | Nhạy hơn |
| base_motion_margin | 4.0 | Khó phát hiện | Dễ phát hiện |

---

**Last Updated**: August 7, 2026  
**Version**: 1.0.0
