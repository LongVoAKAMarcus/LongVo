import asyncio
from collections import deque
import os
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import serial
import uvicorn

current_dir = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(current_dir, "static")

app = FastAPI()
app.mount("/static", StaticFiles(directory=static_path), name="static")

COM_PORT = "COM12"
BAUD_RATE = 921600

FEATURE_WINDOW = 20        
CALIBRATION_FRAMES = 500   

LABELS = {
    0: "Không có người",
    1: "Đứng yên",
    2: "Đang hoạt động",
}

total_valid_frames = 0
total_active_frames = 0
PASS_THRESHOLD = 50.0  

latest_data = {
    "prediction": "Đang khởi động...",
    "motion_score": 0.0,
    "class": -1,
    "total_valid": 0,       
    "total_active": 0,     
    "percent_active": 0.0, 
    "evaluation": "Chưa có"
}

amplitude_buffer = deque(maxlen=FEATURE_WINDOW)
energy_history = deque(maxlen=50)
motion_history = deque(maxlen=5)
state_history = deque(maxlen=4) 

ewma_baseline_energy = None
ewma_baseline_motion = None

current_state = 0
down_counter = 0 
target_drop_state = 0


async def serial_worker():
    global latest_data, ewma_baseline_energy, ewma_baseline_motion, current_state
    global down_counter, target_drop_state
    global total_valid_frames, total_active_frames

    while True:
        try:
            ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.05)
            try:
                ser.set_buffer_size(rx_size=4096, tx_size=4096)
            except Exception:
                pass
            ser.reset_input_buffer()
            print(f"Đã kết nối với ESP qua cổng {COM_PORT}")
            
            frame_count = 0

            while True:
                if ser.in_waiting > 2000:
                    ser.reset_input_buffer()

                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()

                    if "CSI_DATA" in line:
                        match = re.search(r"\[(.*?)\]", line)
                        if match:
                            raw_csi_data = match.group(1)
                            csi_amplitudes = [int(x) for x in raw_csi_data.split(",")]
                            if len(csi_amplitudes) != 384:
                                continue

                            if len(csi_amplitudes) >= 96:
                                I_vals = np.array(csi_amplitudes[0::2])
                                Q_vals = np.array(csi_amplitudes[1::2])
                                amplitudes = np.sqrt(I_vals**2 + Q_vals**2)

              
                                valid_index = [
                                    i for i in range(96)
                                    if i not in [0, 1, 2, 3, 4, 5, 31, 32, 33, 59, 60, 61, 62, 63, 64, 65]
                                ]

                                current_frame_features = amplitudes[valid_index]

                                # Cải tiến: Loại bỏ frame lỗi/bão hòa biên độ
                                if np.max(current_frame_features) < 5 or np.max(current_frame_features) > 1000:
                                    continue

                             
                                # Cải tiến: Chuẩn hóa CSI trừ median để giảm nhiễu AGC/RSSI
                                current_frame_features = current_frame_features - np.median(current_frame_features)
                               

                                amplitude_buffer.append(current_frame_features)
                                current_energy = np.std(current_frame_features)

                                if len(amplitude_buffer) < FEATURE_WINDOW:
                                    latest_data = {
                                        "prediction": f"Đang gom buffer ({len(amplitude_buffer)}/{FEATURE_WINDOW})...",
                                        "motion_score": 0.0,
                                        "smooth_std": 0.0,
                                        "energy": float(current_energy),
                                        "rolling_mean": 0.0,
                                        "threshold": 0.0,
                                        "percent_active": 0.0,
                                        "total_valid": int(total_valid_frames),
                                        "total_active": int(total_active_frames),
                                        "evaluation": "Chờ gom data",
                                        "class": -1,
                                    }
                                    await asyncio.sleep(0.001)
                                    continue
                                
                                buffer_arr = np.array(amplitude_buffer)
                                smoothed_energy = np.mean(
                                    np.std(buffer_arr, axis=0)
                                    )

                                temporal_std = np.std(buffer_arr, axis=0)
                                
                                # Cải tiến: Dùng percentile(80) lấy top subcarrier biến động mạnh thay vì median thuần túy
                                raw_motion_score = np.percentile(temporal_std, 80) * 10
                                motion_history.append(raw_motion_score)

                                if len(motion_history) > 0:
                                    motion_score = np.median(motion_history)
                                else:
                                    motion_score = raw_motion_score

                                if ewma_baseline_energy is None:
                                    ewma_baseline_energy = smoothed_energy
                                    ewma_baseline_motion = motion_score
                                 

                                frame_count += 1
                                if frame_count <= CALIBRATION_FRAMES:
                                    ewma_baseline_energy = 0.1 * current_energy + 0.9 * ewma_baseline_energy
                                    ewma_baseline_motion = 0.1 * motion_score + 0.9 * ewma_baseline_motion
                                 
                                    energy_history.append(current_energy)

                                    latest_data = {
                                        "prediction": f"Đang hiệu chuẩn nền ({frame_count}/{CALIBRATION_FRAMES})...",
                                        "motion_score": float(motion_score),
                                        "smooth_std": float(motion_score),
                                        "energy": float(smoothed_energy),
                                        "rolling_mean": float(ewma_baseline_energy),
                                        "threshold": float(ewma_baseline_energy + 1.0),
                                        "percent_active": 0.0,
                                        "total_valid": int(total_valid_frames),
                                        "total_active": int(total_active_frames),
                                        "evaluation": "Đang hiệu chuẩn",
                                        "class": -1,
                                    }
                                    await asyncio.sleep(0.001)
                                    continue

                                energy_std_dev = np.std(energy_history) if len(energy_history) > 5 else 0.5
                                
                                
                                base_energy_margin = max(1.0, 1.5 * energy_std_dev)
                                base_motion_margin = max(4.0, 2.5) 
                                
                                energy_threshold_1 = ewma_baseline_energy + base_energy_margin
                                motion_threshold_2 = ewma_baseline_motion + base_motion_margin

                   
                                if motion_score > motion_threshold_2:
                                    raw_state = 2
                                elif smoothed_energy > energy_threshold_1 or motion_score > (ewma_baseline_motion + 1.5):
                                    raw_state = 1
                                else:
                                    raw_state = 0

                                state_history.append(raw_state)
                                if len(state_history) >= 4:
                                    vals, counts = np.unique(state_history, return_counts=True)
                                    smoothed_raw_state = vals[np.argmax(counts)]
                                else:
                                    smoothed_raw_state = raw_state
                                if current_state == 0 and smoothed_raw_state == 1:
                                    smoothed_raw_state = 0
                    
                                if smoothed_raw_state > current_state:
                                    current_state = smoothed_raw_state
                                    down_counter = 0
                                elif smoothed_raw_state < current_state:
                                    if smoothed_raw_state == 0:
                                        required_frames = 60  # thời gian rớt từ có người sang không có người 
                                    else:
                                        required_frames = 20 # tg rớt từ đang hoạt động sang đứng yên
                                    
                                    if smoothed_raw_state == target_drop_state:
                                        down_counter += 1
                                    else:
                                        target_drop_state = smoothed_raw_state
                                        down_counter = 1
                                    
                                    if down_counter >= required_frames:
                                        current_state = smoothed_raw_state
                                        down_counter = 0
                                else:
                                    down_counter = 0

                                if current_state == 0:
                                    alpha_val = 0.03
                                    ewma_baseline_energy = alpha_val * current_energy + (1 - alpha_val) * ewma_baseline_energy
                                    ewma_baseline_motion = alpha_val * motion_score + (1 - alpha_val) * ewma_baseline_motion
                                    
                                    energy_history.append(current_energy)
                                elif current_state == 1:
                                    alpha_val = 0.002
                                    ewma_baseline_motion = alpha_val * motion_score + (1 - alpha_val) * ewma_baseline_motion

                              
                                total_valid_frames += 1
                                if current_state == 2:
                                    total_active_frames += 1
                                
                                if total_valid_frames > 0:
                                    percent_active = (total_active_frames / total_valid_frames) * 100.0
                                else:
                                    percent_active = 0.0

                                is_passed = "Đạt" if percent_active >= PASS_THRESHOLD else "Không đạt"

                               
                                latest_data = {
                                    "prediction": LABELS[current_state],
                                    "motion_score": float(motion_score),
                                    "smooth_std": float(motion_score),
                                    "energy": float(smoothed_energy),  
                                    "rolling_mean": float(ewma_baseline_energy),
                                    "threshold": float(energy_threshold_1),
                                    "motion_threshold": float(motion_threshold_2),
                                    "total_valid": int(total_valid_frames),      
                                    "total_active": int(total_active_frames),   
                                    "percent_active": float(percent_active),     
                                    "class": int(current_state),
                                    "evaluation": is_passed                     
                                }

                await asyncio.sleep(0.001)

        except serial.SerialException as e:
            print(f"Mất kết nối Serial, đang thử kết nối lại... ({e})")
            await asyncio.sleep(2.0)
        except Exception as e:
            print(f"Lỗi vòng lặp worker: {e}")
            await asyncio.sleep(0.01)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(serial_worker())

@app.get("/")
async def get():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "templates", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - File not found</h1>", status_code=404)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(latest_data)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Ngắt kết nối WS: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)