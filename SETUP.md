# 📚 Hướng Dẫn Cài Đặt Chi Tiết
# LongVo

---

## **PHẦN 1: CÀI ĐẶT PYTHON BACKEND**

### **1.1 Yêu Cầu Môi Trường**
- Python 3.8 trở lên
- pip (Python package manager)
- Virtual Environment (tuỳ chọn nhưng khuyến khích)

### **1.2 Bước Cài Đặt**

**Cách 1: Dùng Virtual Environment (Khuyến Khích)**

```bash
# 1. CD vào folder backend
cd backend

# 2. Tạo virtual environment
python -m venv venv

# 3. Activate virtual environment
# Trên Windows:
venv\Scripts\activate
# Trên Linux/Mac:
source venv/bin/activate

# 4. Cài dependencies
pip install -r requirements.txt

# 5. Chạy server
python main.py
```

**Cách 2: Cài Global (Không Khuyến Khích nhưng Nhanh)**

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### **1.3 Kiểm Tra Cài Thành Công**

Khi chạy `python main.py`, bạn sẽ thấy:
```
INFO:     Uvicorn running on http://0.0.0.0:8003
Press CTRL+C to quit
```

✅ Truy cập: http://localhost:8003

---

## **PHẦN 2: CÀI ĐẶT ESP-IDF & FLASH FIRMWARE**

### **2.1 Cài Đặt ESP-IDF (Lần Đầu)**

**Windows PowerShell:**
```bash
# 1. CD vào thư mục muốn cài ESP-IDF
cd C:\

# 2. Clone ESP-IDF repository
git clone -b v5.1.2 https://github.com/espressif/esp-idf.git

# 3. Chuyển vào folder ESP-IDF
cd esp-idf

# 4. Chạy install script
.\install.ps1

# 5. Export environment variables
.\export.ps1
```

**Linux/Mac:**
```bash
git clone -b v5.1.2 https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh
source export.sh
```

⚠️ Lần đầu mất khoảng 5-10 phút để download toolchain

### **2.2 Kiểm Tra ESP-IDF**

```bash
idf.py --version
# Nên thấy: IDF version 5.x.x
```

### **2.3 Flash Firmware ESP32**

#### **ESP32 TX (Transmitter)**

```bash
# 1. CD vào folder TX
cd firmware/csi_send

# 2. Build firmware
idf.py build

# 3. Flash lên ESP32
# Tìm cổng COM của TX ESP32 (Device Manager)
idf.py -p COM12 flash

# 4. Xem Serial output (optional)
idf.py -p COM12 monitor

# Hoặc all-in-one:
idf.py -p COM12 build flash monitor
```

#### **ESP32 RX (Receiver)**

```bash
# 1. CD vào folder RX
cd firmware/csi_recv

# 2. Build + Flash + Monitor
idf.py -p COM12 build flash monitor
```

### **2.4 Lỗi Phổ Biến & Cách Khắc Phục**

| Lỗi | Nguyên Nhân | Cách Khắc Phục |
|-----|-----------|---|
| `Failed to connect to ESP32` | ESP32 không ở chế độ download | Giữ nút BOOT, bấm RST, release BOOT |
| `Port COM12 not found` | Sai cổng COM | Kiểm tra Device Manager, thay COM |
| `Error: address not in dram` | Firmware lỗi | Xóa build folder, build lại: `idf.py fullclean && idf.py build` |
| `USB device is not connected` | Cáp USB lỏng | Thử cáp USB khác hoặc port USB khác |

---

## **PHẦN 3: CẤU HÌNH KẾT NỐI SERIAL**

### **3.1 Kiểm Tra Cổng COM**

**Windows (Device Manager):**
1. Mở Device Manager (Devmgmt.msc)
2. Expand "Ports (COM & LPT)"
3. Tìm "USB Serial Device" hoặc "CH340" (tuỳ chip)
4. Ghi nhớ cổng (ví dụ: COM3, COM12)

**Linux:**
```bash
ls /dev/ttyUSB*
# hoặc
ls /dev/ttyACM*
```

### **3.2 Cảu Hình Cổng trong Python**

File: `backend/main.py` (dòng 18)

```python
COM_PORT = "COM12"  # Thay bằng cổng của bạn
```

---

## **PHẦN 4: CHẠY HỆ THỐNG HOÀN CHỈNH**

### **4.1 Bật Hệ Thống (Thứ Tự)**

```bash
# Terminal 1: Chạy Python Backend
cd backend
python main.py
# Trông thấy: "Uvicorn running on http://0.0.0.0:8003"

# Terminal 2: Monitor RX ESP32 Serial Output (tuỳ chọn)
# Để xem debug info từ ESP32 RX
idf.py -p COM12 monitor
```

**Hoặc một lệnh duy nhất:**
```bash
# Chạy backend (giả sử đã ở folder csi-activity-detection)
cd backend && python main.py &
# Lệnh trên sẽ chạy backend ở background
```

### **4.2 Kiểm Tra Khởi Động Thành Công**

**Console Python:**
```
Đã kết nối với ESP qua cổng COM12
```

**Browser (http://localhost:8003):**
- Xem trang HTML dashboard
- Trạng thái: "STANDBY"
- Nút "Khởi Động Quét CSI" hiệu lực

### **4.3 Bắt Đầu Thu Thập Dữ Liệu**

1. Nhấn **"Khởi Động Quét CSI"** trong dashboard
2. Xem chart năng lượng cập nhật real-time
3. Xem trạng thái (Không có người / Đứng yên / Hoạt động)
4. Tấy cửa động, vẫy tay → chart sẽ thay đổi
5. Nhấn **"Dừng & Báo Cáo"** → xem thống kê pie chart

---

## **PHẦN 5: TUỲ CHỈNH TÀM SỐ**

### **5.1 Cấu Hình Chính (backend/main.py)**

```python
# Dòng 18-31
COM_PORT = "COM12"              # Cổng kết nối ESP32 RX
BAUD_RATE = 921600             # Tốc độ Serial (không thay đổi)

FEATURE_WINDOW = 20             # Kích thước buffer CSI
                                # Tăng → mịn hơn, chậm hơn
                                # Giảm → nhanh hơn, nhiễu hơn

CALIBRATION_FRAMES = 500        # Số frame hiệu chuẩn
                                # Tăng → baseline ổn định hơn
                                # Giảm → bắt đầu phân loại nhanh hơn

PASS_THRESHOLD = 50.0           # % hoạt động tối thiểu "Đạt"
                                # Ví dụ: 50 = phải hoạt động ≥50%
```

### **5.2 Điều Chỉnh Threshold Động (Tuỳ Chỉnh Cao Cấp)**

File: `backend/main.py` (dòng 197-199)

```python
# Threshold Energy
base_energy_margin = max(1.0, 1.5 * energy_std_dev)
energy_threshold_1 = ewma_baseline_energy + base_energy_margin

# Threshold Motion
base_motion_margin = max(4.0, 2.5)  # Tăng → khó phát hiện hoạt động
motion_threshold_2 = ewma_baseline_motion + base_motion_margin

# Điều chỉnh:
# - Muốn nhạy hơn → giảm margin (1.5 → 1.2)
# - Muốn kém nhạy hơn → tăng margin (1.5 → 2.0)
```

### **5.3 Điều Chỉnh Trễ Hysteresis**

File: `backend/main.py` (dòng 209-214)

```python
if smoothed_raw_state == 0:
    required_frames = 60  # 60 frame để từ "có người" → "trống"
else:
    required_frames = 20  # 20 frame để từ "hoạt động" → "đứng yên"

# Tăng required_frames → ít flicker, chậm phản ứng
# Giảm required_frames → phản ứng nhanh, dễ flicker
```

---

## **PHẦN 6: DEBUG & LOGGING**

### **6.1 Mở Console Log Python**

```bash
cd backend
python main.py
# Xem output, log mỗi frame (có thể comment để tốc độ nhanh hơn)
```

### **6.2 Kiểm Tra WebSocket Connection**

Browser (F12 → Network tab):
1. Filter: WS
2. Click vào `/ws` connection
3. Xem Messages tab
4. Nên thấy JSON data gửi liên tục

### **6.3 Serial Monitor (Debug ESP32)**

```bash
cd firmware/csi_recv
idf.py -p COM12 monitor

# Bạn sẽ thấy:
# I (1000) csi_recv: Received CSI from TX...
# CSI_DATA [100, 95, 120, ...]
```

---

## **PHẦN 7: RESET & TROUBLESHOOT TOÀN BỘ**

### **7.1 Reset Cơ Sở Dữ Liệu (Nếu Lỗi)**

```bash
# Xóa build folder ESP-IDF
cd firmware/csi_recv
idf.py fullclean

# Xóa Python cache
cd backend
rm -rf __pycache__
rm -rf .pytest_cache

# Re-build + Flash
cd firmware/csi_recv
idf.py -p COM12 build flash monitor
```

### **7.2 Kiểm Tra Lại Toàn Bộ**

```
✅ Python backend chạy ổn định
✅ 2 ESP32 (TX + RX) được flash
✅ RX ESP32 nhận CSI (xem serial monitor)
✅ Dashboard hiểu thị http://localhost:8003
✅ Nút "Khởi Động" OK → chart cập nhật
✅ Di động trong phòng → chart thay đổi
```

---

## **PHẦN 8: VĂN BẢN TÀI LIỆU THAM KHẢO**

- **ESP-IDF Offical Docs**: https://docs.espressif.com/projects/esp-idf/
- **CSI WiFi Research**: https://github.com/espressif/esp-csi
- **FastAPI Docs**: https://fastapi.tiangolo.com/

---

**Hoàn tất! Hệ thống đã sẵn sàng sử dụng.** 🎉

