# CSI Activity Detection System
# Đề tài thực tập
# Võ Thái Bảo Long 2311937

## Mô Tả Dự Án

Hệ thống phát hiện **3 trạng thái hoạt động của người dùng** dựa trên **CSI (Channel State Information)** từ WiFi:
-  **Trạng thái 0**: Không có người
-  **Trạng thái 1**: Đứng yên / Ngồi tĩnh
-  **Trạng thái 2**: Đang hoạt động (vẫy tay, đi bộ, v.v.)

### 🎯 Mục Đích
Xây dựng hệ thống cảm biến thông minh không cần camera, không xâm phạm riêng tư, sử dụng tín hiệu WiFi để phát hiện chuyển động người.

---

## Cấu Trúc Dự Án

```
csi-activity-detection/
├── firmware/                   # ESP32 Firmware
│   ├── csi_send/              # TX (Transmitter) - Phát tín hiệu WiFi
│   │   ├── main/
│   │   │   └── app_main.c
│   │   ├── CMakeLists.txt
│   │   └── sdkconfig
│   │
│   └── csi_recv/              # RX (Receiver) - Nhận CSI
│       ├── main/
│       │   └── app_main.c
│       ├── CMakeLists.txt
│       └── sdkconfig
│
├── backend/                    # Python Backend
│   ├── main.py                # FastAPI + WebSocket + Logic xử lý
│   └── requirements.txt       # Dependencies
│
├── frontend/                   # Web Dashboard
│   ├── templates/
│   │   └── index.html        # SCADA Dashboard
│   └── static/
│       └── HCMUT_official_logo.png
│
├── README.md                   # File này
├── SETUP.md                    # Hướng dẫn cài đặt
├── ALGORITHM.md                # Giải thích thuật toán
└── .gitignore                  # Git ignore file
```

---

##  Quick Start 

### **Bước 1: Cài Đặt Python Dependencies**

```bash
pip install -r backend/requirements.txt
```

### **Bước 2: Chạy Backend Server**

```bash
cd backend
python main.py
```

Server chạy tại: `http://localhost:8003`

### **Bước 3: Flash Firmware lên 2 ESP32**
```
cài đặt ESP-IDF trên VS code
```
#### **ESP32 TX (Transmitter)**
```bash
cd firmware/csi_send
idf.py -p COM12 build flash monitor
```

#### **ESP32 RX (Receiver)**
```bash
cd firmware/csi_recv
idf.py -p COM12 build flash monitor
```

*(Thay `COM12` bằng cổng COM của bạn)*

### **Bước 4: Mở Dashboard**
- Truy cập: `http://localhost:8003`
- Nhấn **"Khởi Động Quét CSI"**
- Xem real-time chart & thống kê

---

## Công Nghệ & Hardware

| Thành Phần | Chi Tiết |
|-----------|---------|
| **Transmitter** | ESP32 (TX) - Phát WiFi probe frames trên kênh 6 |
| **Receiver** | ESP32 (RX) - Nhận & xử lý CSI data |
| **Backend** | Python 3.10 + FastAPI + async WebSocket |
| **Frontend** | HTML5 + JavaScript + Chart.js |
| **Connection** | Serial (UART) - Baud 921600 |
| **Latency** | ~50ms real-time |

---

##  Tham Số Chính (Có thể Tuỳ Chỉnh)

File cấu hình: `backend/main.py` (dòng 18-31)

```python
COM_PORT = "COM12"              # Cổng COM kết nối ESP32 RX
BAUD_RATE = 921600             # Tốc độ baudrate
FEATURE_WINDOW = 20            # Buffer size (20 frame CSI)
CALIBRATION_FRAMES = 500       # Số frame hiệu chuẩn nền (~50 giây)
PASS_THRESHOLD = 50.0          # % hoạt động tối thiểu để "Đạt" (0-100)
```

---

##  Luồng Xử Lý (12 Giai Đoạn)

1. **Nhận CSI** từ ESP32 RX qua Serial (384 giá trị I/Q)
2. **Tách I & Q** → Tính Amplitude
3. **Lọc subcarrier** DC/null (0,1,2,3,4,5,31,32,33,59-65) → 80 subcarrier tốt
4. **Kiểm frame hợp lệ** → Loại bỏ frame quá yếu (<5) hoặc bão hòa (>1000)
5. **Chuẩn hóa CSI** → Trừ median (giảm AGC/RSSI noise)
6. **Gom buffer** 20 frame vào deque
7. **Tính Energy** = std(subcarrier) - độ biến động không gian
8. **Tính Motion** = percentile(80) std(temporal) * 10 - độ biến động thời gian
9. **Hiệu chuẩn baseline** EWMA (500 frame đầu, alpha=0.1)
10. **Phân loại state** (0/1/2) dựa trên ngưỡng energy & motion
11. **Smooth state** = majority vote (4 frame gần nhất)
12. **State Machine** + Hysteresis (60 frame rớt xuống 0, 20 frame rớt xuống 1)
13. **Update EWMA** tuỳ theo state (alpha=0.03 ở state 0, alpha=0.002 ở state 1)
14. **Output JSON** → WebSocket → HTML Dashboard (mỗi 50ms)

📚 **Chi tiết từng giai đoạn**: xem [ALGORITHM.md](ALGORITHM.md)

---

##  Tính Năng Dashboard

-  **Biểu đồ Real-time** - Line chart năng lượng CSI cập nhật liên tục
-  **Dự đoán AI** - Hiển thị state hiện tại với màu sắc (xanh/vàng/đỏ)
-  **Biểu đồ Thống kê** - Pie chart tỷ lệ % 3 trạng thái (hiện khi bấm Dừng)
-  **Thông Số Kỹ Thuật** - Motion score, Energy, Threshold, % hoạt động
-  **Trạng thái Hệ thống** - LED status nháy, kết nối WebSocket
-  **Lưu Phiên** - Thống kê tròn, đánh giá Đạt/Không Đạt

---

## Yêu Cầu Hệ Thống

### **Hardware**
- ✅ 2x ESP32 (S3, C6, C3 hoặc Standard)
- ✅ USB Cable x2 (nạp firmware + Serial debug)
- ✅ Computer (chạy Python backend)
- ✅ WiFi Router (để TX/RX kết nối)

### **Software**
- Python 3.8+
- ESP-IDF v5.1+ (để build firmware)
- Modern Browser (Chrome, Firefox, Edge)

---

## ⚙️ Cài Đặt Chi Tiết

Xem file: **[SETUP.md](SETUP.md)**

---

##  Giải Thích Thuật Toán

Xem file: **[ALGORITHM.md](ALGORITHM.md)**

---

##  Troubleshooting

### **❌ Không nhận được CSI data**
1. Kiểm tra Device Manager → COM port của RX ESP32
2. Đảm bảo RX đã flash firmware xong (kiểm tra serial monitor)
3. Kiểm tra TX đang phát bình thường (xem LED hoặc serial output)
4. Đảm bảo 2 ESP32 trên cùng kênh WiFi (kênh 6 theo config)

### **❌ Python không kết nối ESP32**
```python
# main.py dòng 18
COM_PORT = "COM3"  # Thay bằng cổng của bạn
```
Kiểm tra trong: Device Manager → Ports (COM & LPT)

### **❌ Dashboard không hiển thị**
1. Kiểm tra server chạy: `http://localhost:8003` 
2. Mở DevTools (F12) → Console tab → xem error
3. Kiểm tra WebSocket: Network tab → WS → Status 101

### **❌ Accuracy thấp / Nhiễu nhiều**
- Tăng `FEATURE_WINDOW` (từ 20 → 30)
- Tăng `CALIBRATION_FRAMES` (từ 500 → 1000)
- Điều chỉnh threshold động trong code

---
## Cảm Ơn

- Espressif Systems (ESP-IDF framework)
- Cộng đồng CSI WiFi research
- FastAPI & uvicorn team

---

**Last Updated**: August 7, 2026  
**Version**: 1.0.0  
**Status**: Stable
