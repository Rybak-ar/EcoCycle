import cv2
import numpy as np
from ultralytics import YOLO
import edge_tts
import asyncio
import os
import sys
import time
import threading
import serial
import serial.tools.list_ports
import re
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

classes = ["colored", "clear", "opaque"]
thai_labels = {
    "colored": "ตรวจพบขวดสี", 
    "clear": "ตรวจพบขวดใส",
    "opaque": "ตรวจพบขวดสีขุ่น"
}

def set_thread_affinity(core_ids):
    """
    กำหนด CPU Affinity ให้กับ Thread/Process ปัจจุบัน (สำหรับ Raspberry Pi 5 / Linux)
    - Raspberry Pi 5 มี 4 cores: 0, 1, 2, 3
    - Core 3: กล้องโดยเฉพาะ (Camera Frame Grabber)
    - Cores 1, 2: โมเดล AI (PyTorch / YOLO)
    - Core 0: หน้าจอ GUI (Flet) และการเชื่อมต่อ Serial
    """
    try:
        import os
        if hasattr(os, 'sched_setaffinity'):
            os.sched_setaffinity(0, set(core_ids))
            print(f"[Pi5 Multi-Core] Pinned thread to CPU Core(s): {core_ids}")
    except Exception:
        pass

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_config.json")

def load_camera_config():
    cfg = {"rotate": 270}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg.update(loaded)
        except Exception as e:
            print(f"[Camera Config] Error reading {CONFIG_PATH}: {e}")
    if "CAMERA_ROTATE" in os.environ:
        try:
            cfg["rotate"] = int(os.environ["CAMERA_ROTATE"])
        except ValueError:
            pass
    return cfg

def save_camera_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Camera Config] Error saving {CONFIG_PATH}: {e}")

def get_viewer_html():
    return """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BotteProject AI Camera Viewer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
    .container { max-width: 1200px; margin: 0 auto; }
    header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 16px; border-bottom: 1px solid #334155; margin-bottom: 20px; }
    .title { font-size: 24px; font-weight: bold; color: #10b981; display: flex; align-items: center; gap: 10px; }
    .status-badge { background: #1e293b; padding: 6px 14px; border-radius: 20px; font-size: 14px; border: 1px solid #475569; }
    .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
    @media (max-width: 850px) { .grid { grid-template-columns: 1fr; } }
    .video-card { background: #1e293b; border-radius: 16px; overflow: hidden; border: 1px solid #334155; display: flex; flex-direction: column; }
    .video-container { width: 100%; aspect-ratio: 4/3; background: #000; position: relative; display: flex; align-items: center; justify-content: center; }
    .video-container img { width: 100%; height: 100%; object-fit: contain; }
    .info-card { background: #1e293b; border-radius: 16px; padding: 20px; border: 1px solid #334155; display: flex; flex-direction: column; gap: 16px; }
    .card-title { font-size: 16px; font-weight: 600; color: #94a3b8; border-bottom: 1px solid #334155; padding-bottom: 8px; }
    .metric-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #1e293b; }
    .metric-label { font-size: 14px; color: #cbd5e1; }
    .metric-val { font-size: 18px; font-weight: bold; color: #f8fafc; }
    .badge-clear { color: #38bdf8; background: rgba(56, 189, 248, 0.15); padding: 4px 10px; border-radius: 8px; font-weight: bold; }
    .badge-colored { color: #fbbf24; background: rgba(251, 191, 36, 0.15); padding: 4px 10px; border-radius: 8px; font-weight: bold; }
    .badge-opaque { color: #c084fc; background: rgba(192, 132, 252, 0.15); padding: 4px 10px; border-radius: 8px; font-weight: bold; }
    .bar-bg { width: 100%; height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin-top: 4px; }
    .bar-fill { height: 100%; transition: width 0.3s ease; }
    .btn-snap { background: #10b981; color: white; border: none; padding: 12px 20px; border-radius: 12px; font-size: 15px; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; transition: 0.2s; }
    .btn-snap:hover { background: #059669; }
    .toast { position: fixed; bottom: 20px; right: 20px; background: #10b981; color: white; padding: 12px 20px; border-radius: 10px; display: none; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .legend { display: flex; gap: 12px; font-size: 12px; margin-top: 10px; flex-wrap: wrap; }
    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-box { width: 12px; height: 12px; border-radius: 3px; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title">&#127870; BotteProject AI Live Camera</div>
      <div class="status-badge" id="state-badge">Standby</div>
    </header>

    <div class="grid">
      <div class="video-card">
        <div class="video-container">
          <img src="/stream.mjpg" alt="AI Camera Stream" id="stream-img" onerror="setTimeout(() => { this.src='/stream.mjpg?t=' + Date.now(); }, 2000)">
        </div>
        <div style="padding: 14px 20px;">
          <div class="legend">
            <div class="legend-item"><div class="legend-box" style="background: #22c55e;"></div> Green: Bottle Shape</div>
            <div class="legend-item"><div class="legend-box" style="background: #facc15;"></div> Yellow: Neck ROI (ใต้ฝาไร้ฉลาก)</div>
            <div class="legend-item"><div class="legend-box" style="background: #e879f9;"></div> Purple: Base ROI (ก้นขวด)</div>
          </div>
        </div>
      </div>

      <div class="info-card">
        <div class="card-title">Live Classification (ผลการตรวจจับ)</div>
        <div class="metric-row">
          <span class="metric-label">Detected Bottle</span>
          <span class="metric-val" id="val-bottle">-</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Weight (น้ำหนัก)</span>
          <span class="metric-val" id="val-weight">0.0 g</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">System State</span>
          <span class="metric-val" id="val-state" style="font-size: 15px;">Standby</span>
        </div>

        <div class="card-title" style="margin-top: 10px;">Neck ROI Color Breakdown (ไร้ฉลาก)</div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 13px;">
            <span>Amber / Brown (ขวดสี)</span>
            <span id="txt-amber">0.0%</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" id="bar-amber" style="width: 0%; background: #d97706;"></div></div>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 13px;">
            <span>Green (ขวดสีเขียว)</span>
            <span id="txt-green">0.0%</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" id="bar-green" style="width: 0%; background: #16a34a;"></div></div>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 13px;">
            <span>Blue (ขวดสีฟ้า/ฝาฟ้า)</span>
            <span id="txt-blue">0.0%</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" id="bar-blue" style="width: 0%; background: #0284c7;"></div></div>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 13px;">
            <span>Opaque White (ขวดขาวขุ่น)</span>
            <span id="txt-opaque">0.0%</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" id="bar-opaque" style="width: 0%; background: #cbd5e1;"></div></div>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 13px;">
            <span>Vibrant Colors (สีสด)</span>
            <span id="txt-vibrant">0.0%</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" id="bar-vibrant" style="width: 0%; background: #ec4899;"></div></div>
        </div>

        <div style="display: flex; gap: 10px; margin-top: 10px;">
          <button class="btn-snap" style="flex: 1;" onclick="takeSnapshot()">&#128248; บันทึกภาพ Dataset</button>
          <button class="btn-snap" style="flex: 1; background: #0284c7;" onclick="rotateCamera()">&#128260; หมุนกล้อง 90&deg; (<span id="txt-rot">270&deg;</span>)</button>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 10px;">
          <button class="btn-snap" style="flex: 1; background: #059669;" onclick="tareScale()">&#9878;&#65039; เซ็ตศูนย์ตาชั่ง (Tare)</button>
          <button class="btn-snap" style="flex: 1; background: #e11d48;" onclick="reconnectCamera()">&#128250; รีเซ็ตกล้อง (Reconnect)</button>
        </div>
      </div>
    </div>
  </div>

  <div class="toast" id="toast">บันทึกรูปภาพสำเร็จ!</div>

  <script>
    async function updateStatus() {
      try {
        const res = await fetch('/api/status');
        if (res.ok) {
          const data = await res.json();
          let stText = data.state || 'Standby';
          if (data.state === 'TRACK_CONFIRM' && data.settle_rem > 0) {
            stText = `ติดตามตำแหน่งขวด... (${data.settle_rem.toFixed(1)}s)`;
          } else if (data.state === 'SETTLING' && data.settle_rem > 0) {
            stText = `รอขวดนิ่ง... (${data.settle_rem.toFixed(1)}s)`;
          } else if (data.state === 'WAIT_WEIGHT') {
            stText = 'Standby (รอวางขวด)';
          } else if (data.state === 'DETECT') {
            stText = 'AI Classifying (กำลังวิเคราะห์)';
          } else if (data.state === 'WAIT_CLEAR') {
            stText = 'Sorting (ปล่อยขวดลงถัง)';
          }
          document.getElementById('val-weight').innerText = (data.weight || 0.0).toFixed(1) + ' g';
          document.getElementById('val-state').innerText = stText;
          document.getElementById('state-badge').innerText = stText;

          if (data.rotation !== undefined) {
            document.getElementById('txt-rot').innerText = data.rotation + '°';
          }

          const bLabel = { 'clear': 'ขวดใส (Clear)', 'colored': 'ขวดสี (Colored)', 'opaque': 'ขวดขุ่น (Opaque HDPE)' };
          const bClass = { 'clear': 'badge-clear', 'colored': 'badge-colored', 'opaque': 'badge-opaque' };
          const bVal = data.decision;
          if (bVal && bLabel[bVal]) {
            document.getElementById('val-bottle').innerHTML = `<span class="${bClass[bVal] || ''}">${bLabel[bVal]}</span>`;
          } else {
            document.getElementById('val-bottle').innerHTML = `<span style="color:#64748b;">รอตรวจจับ...</span>`;
          }

          if (data.neck_metrics) {
            const m = data.neck_metrics;
            const a = ((m.amber || 0) * 100).toFixed(1);
            const g = ((m.green || 0) * 100).toFixed(1);
            const o = ((m.opaque || 0) * 100).toFixed(1);
            const v = ((m.vibrant || 0) * 100).toFixed(1);
            document.getElementById('txt-amber').innerText = a + '%';
            document.getElementById('bar-amber').style.width = Math.min(100, a * 2.5) + '%';
            document.getElementById('txt-green').innerText = g + '%';
            document.getElementById('bar-green').style.width = Math.min(100, g * 2.5) + '%';
            const bl = Math.max((m.body_blue || 0), (m.cap_blue || 0), (m.blue || 0)) * 100;
            document.getElementById('txt-blue').innerText = bl.toFixed(1) + '%';
            document.getElementById('bar-blue').style.width = Math.min(100, bl * 4.0) + '%';
            document.getElementById('txt-opaque').innerText = o + '%';
            document.getElementById('bar-opaque').style.width = Math.min(100, o * 1.5) + '%';
            document.getElementById('txt-vibrant').innerText = v + '%';
            document.getElementById('bar-vibrant').style.width = Math.min(100, v * 2.5) + '%';
          }
        }
      } catch (err) {}
    }
    setInterval(updateStatus, 350);

    async function takeSnapshot() {
      try {
        const res = await fetch('/api/snapshot');
        const data = await res.json();
        const toast = document.getElementById('toast');
        toast.innerText = data.success ? 'บันทึกรูป: ' + data.path : 'เกิดข้อผิดพลาดในการบันทึก';
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 3000);
      } catch (e) {
        alert('Snapshot error: ' + e);
      }
    }

    async function rotateCamera() {
      try {
        const res = await fetch('/api/rotate');
        if (res.ok) {
          const data = await res.json();
          document.getElementById('txt-rot').innerText = data.rotation + '°';
          const toast = document.getElementById('toast');
          toast.innerText = 'หมุนกล้องเป็น: ' + data.rotation + '° เรียบร้อย (บันทึกแล้ว)';
          toast.style.display = 'block';
          setTimeout(() => { toast.style.display = 'none'; }, 3000);
        }
      } catch (e) {
        alert('Rotate error: ' + e);
      }
    }

    async function tareScale() {
      try {
        const res = await fetch('/api/tare');
        if (res.ok) {
          const toast = document.getElementById('toast');
          toast.innerText = '✅ เซ็ตศูนย์ตาชั่งเรียบร้อย (0.0g)';
          toast.style.display = 'block';
          setTimeout(() => { toast.style.display = 'none'; }, 3000);
        }
      } catch (e) {
        alert('Tare error: ' + e);
      }
    }

    async function reconnectCamera() {
      try {
        const res = await fetch('/api/reconnect_camera');
        if (res.ok) {
          const data = await res.json();
          const toast = document.getElementById('toast');
          toast.innerText = data.success ? '✅ รีเซ็ตการเชื่อมต่อกล้องสำเร็จ' : '⚠️ เชื่อมต่อกล้องไม่สำเร็จ';
          toast.style.display = 'block';
          setTimeout(() => { toast.style.display = 'none'; }, 3000);
        }
      } catch (e) {
        alert('Reconnect camera error: ' + e);
      }
    }
  </script>
</body>
</html>"""

# Generate audio files if they don't exist
async def setup_audio():
    os.makedirs("./sound/type_bottle_sound", exist_ok=True)
    for c, th_text in thai_labels.items():
        filename = f"./sound/type_bottle_sound/{c}_th.mp3"
        if not os.path.exists(filename):
            try:
                communicate = edge_tts.Communicate(th_text, "th-TH-PremwadeeNeural")
                await communicate.save(filename)
            except Exception as e:
                print(f"TTS Error: {e}")

try:
    asyncio.run(setup_audio())
except:
    pass

class BottleDetector:
    def __init__(self, callback=None):
        self.callback = callback
        self.is_running = False
        self.thread = None
        self.cooldown = 2.0
        self.model_path = os.path.join("app", "bottle_model.pt")
        self.model = None
        self.locator_model_path = "yolov8n.pt"
        self.locator_model = None
        self.cap = None
        
        import atexit
        atexit.register(self.stop)

        self.current_weight = 0.0
        self.current_ir = 1  # 1 = ปกติ/ไม่มีขวดบัง (HIGH), 0 = มีขวดตัดผ่าน (LOW)
        self.min_weight = float(os.environ.get("MIN_BOTTLE_WEIGHT", "10.0"))  # นน. ขั้นต่ำ 10.0g ถือว่ามีขวดวางจริง (กันลมพัด/การสั่นไหว)
        self.max_weight = float(os.environ.get("MAX_BOTTLE_WEIGHT", "500.0"))  # นน. สูงสุด 500.0g หากเกินเตะออกทันที ไม่ต้องตรวจจับต่อ
        self.serial_thread = None
        self.serial_port = None
        self.ser = None
        self.on_esp_message = None
        self.is_paused = False

        # ข้อมูลสำหรับ UI แยกแสดงภาพสด (Camera Viewer & Debug HUD)
        self.last_frame = None
        self.last_bottle_box = None
        self.last_neck_box = None
        self.last_cap_box = None
        self.last_base_box = None
        self.last_vision_metrics = {}
        self.last_decision = None
        self.last_yolo_scores = {}
        self.last_skin_ratio = 0.0
        self.current_state = "WAIT_WEIGHT"
        self._settle_target = float(os.environ.get("SETTLE_DELAY", "2.5"))
        self._settle_elapsed = 0.0
        self._settle_rem = 0.0
        self._stream_server = None
        self._stream_thread = None
        self.stream_port = int(os.environ.get("STREAM_PORT", "5000"))

        # เธรดดึงภาพจากกล้องโดยเฉพาะ (Decoupled Camera Grabber) แยก 1 Core บน Pi 5 เพื่อไม่ให้ภาพค้าง/กระตุก
        self._cam_grabber_running = False
        self._cam_grabber_thread = None
        self._cam_frame_lock = threading.Lock()
        self._latest_raw_frame = None

        # โหลดการตั้งค่าการหมุนภาพกล้อง (ค่าเริ่มต้น 270 องศาตามที่กล้องติดตั้งในเครื่อง)
        self.config = load_camera_config()
        self.camera_rotate = int(self.config.get("rotate", 270))
        print(f"[AI Detector] Camera rotation initialized to: {self.camera_rotate}°")

    def set_rotation(self, angle):
        """กำหนดมุมหมุนภาพกล้อง (0, 90, 180, 270) และบันทึกลง camera_config.json"""
        self.camera_rotate = int(angle) % 360
        self.config["rotate"] = self.camera_rotate
        save_camera_config(self.config)
        print(f"[AI Detector] Camera rotation set to: {self.camera_rotate}°")
        return self.camera_rotate

    def tare_scale(self):
        """เซ็ตศูนย์ตาชั่ง ส่งคำสั่ง TARE ไปยัง ESP32 และรีเซ็ตตัวแปรน้ำหนัก"""
        print("[AI Detector] Manual Tare triggered: resetting scale to 0.0g")
        self.send_to_esp32("TARE\n")
        self.current_weight = 0.0
        self.last_bottle_box = None
        return True

    def reconnect_camera(self):
        """รีเซ็ตการเชื่อมต่อกล้อง ล้าง Frame Buffer และเปิดกล้องใหม่"""
        print("[AI Detector] Manual Reconnect Camera triggered")
        self._cam_grabber_running = False
        with self._cam_frame_lock:
            self._latest_raw_frame = None
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
        time.sleep(0.3)
        self.cap = self._open_camera()
        if self.cap is not None and self.cap.isOpened():
            self._start_cam_grabber()
            print("[AI Detector] Camera reconnected successfully")
            return True
        else:
            print("[AI Detector] Camera reconnect failed")
            return False

    def _read_serial_loop(self):
        env_port = os.environ.get("SCALE_PORT") or os.environ.get("SERIAL_PORT")
        self.serial_port = env_port
        if env_port:
            print(f"[Serial Scale] Using forced port from env: {self.serial_port}")

        last_scan_time = 0.0
        last_err_time = 0.0
        while self.is_running:
            if not self.serial_port:
                ports = list(serial.tools.list_ports.comports())
                found_port = None
                for p in ports:
                    dev = p.device
                    if "COM" in dev or "ttyUSB" in dev or "ttyACM" in dev:
                        found_port = dev
                        break
                if found_port:
                    self.serial_port = found_port
                    print(f"[Serial Scale] Auto-detected Scale port: {self.serial_port}")
                else:
                    now = time.time()
                    if now - last_scan_time > 15.0:
                        print(f"[Serial Scale] No ESP32/Scale connected. Standalone AI vision mode is active.")
                        last_scan_time = now
                    time.sleep(2)
                    continue

            try:
                self.ser = serial.Serial(self.serial_port, 115200, timeout=1)
                print(f"[Serial Scale] Successfully connected to Scale on {self.serial_port}")
                while self.is_running:
                    if self.ser.in_waiting > 0:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            # ดึงค่าน้ำหนักอย่างแม่นยำ (ป้องกันตัวเลข IR หรือข้อความดีบั๊กของ Servo/Bin ปะปน)
                            w_match = re.search(r"Weight\s*=\s*([-+]?\d*\.?\d+)", line, re.IGNORECASE)
                            if w_match:
                                try:
                                    val = float(w_match.group(1))
                                    self.current_weight = max(0.0, val)
                                except ValueError:
                                    pass
                            elif line.lower().startswith("weight"):
                                matches = re.findall(r"[-+]?\d*\.?\d+", line)
                                if matches:
                                    try:
                                        val = float(matches[0])
                                        self.current_weight = max(0.0, val)
                                    except ValueError:
                                        pass

                            # ดึงค่าสถานะเซนเซอร์ IR ประตู
                            if "IR detected = YES" in line or "GATE_IR:OK" in line:
                                self.current_ir = 0
                            elif "IR detected = NO" in line or "GATE_IR:TIMEOUT" in line:
                                self.current_ir = 1
                            else:
                                ir_match = re.search(r"IR\s*=\s*(\d+)", line, re.IGNORECASE)
                                if ir_match:
                                    try:
                                        self.current_ir = int(ir_match.group(1))
                                    except ValueError:
                                        pass

                            # สื่อสารข้อความสถานะ/IR/LOG จากบอร์ด ESP32 ไปยัง UI
                            is_pure_weight = line.lower().startswith("weight =") or line.lower().startswith("final weight")
                            if not is_pure_weight and callable(self.on_esp_message):
                                try:
                                    self.on_esp_message(line)
                                except Exception as cb_err:
                                    print(f"[Serial Scale] Error in on_esp_message callback: {cb_err}")
                    time.sleep(0.01)
            except Exception as e:
                now = time.time()
                if now - last_err_time > 15.0:
                    print(f"[Serial Scale] Notice: {e}")
                    last_err_time = now
                if self.ser:
                    try:
                        self.ser.close()
                    except:
                        pass
                    self.ser = None
                if not env_port:
                    self.serial_port = None
                time.sleep(2)

    def send_to_esp32(self, data: str):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(data.encode('utf-8'))
                print(f"Sent to ESP32: {data.strip()}")
            except Exception as e:
                print(f"Error sending to ESP32: {e}")

    def _configure_camera(self, cap):
        """
        ตั้งค่ากล้อง: ล็อก Auto Exposure และ White Balance เพื่อลดแสงสะท้อนและล็อกโทนสี
        - ปิด Auto Exposure: เพื่อไม่ให้แสงจ้าเกินไปจนเกิดแสงสะท้อน (Glare) บนขวดพลาสติกใส
        - ปิด Auto White Balance: เพื่อไม่ให้โทนสีแกว่งไปมาตามแสงไฟห้อง (ไม่ให้อมเหลือง/อมฟ้าเอง)
        """
        if cap is None or not cap.isOpened():
            return

        import platform
        is_windows = (platform.system() == "Windows")

        if is_windows:
            if "CAMERA_EXPOSURE" in os.environ:
                try:
                    exp_val = float(os.environ["CAMERA_EXPOSURE"])
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                    cap.set(cv2.CAP_PROP_EXPOSURE, exp_val)
                    print(f"[Camera Config] Windows DirectShow: Manual Exposure set to {exp_val}")
                except Exception as e:
                    print(f"[Camera Config] Exposure setting warning: {e}")
            else:
                # โหมดปกติ: ปล่อยให้กล้องปรับความสว่างอัตโนมัติ (ภาพสว่างชัดเจน ไม่มืดดำ)
                try:
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                except Exception:
                    pass
                print(f"[Camera Config] Windows DirectShow: Natural Auto-Exposure active (สว่างปกติ ไม่มืด)")

            if "CAMERA_WB_TEMP" in os.environ:
                try:
                    wb_temp = int(os.environ["CAMERA_WB_TEMP"])
                    if hasattr(cv2, 'CAP_PROP_AUTO_WB'):
                        cap.set(cv2.CAP_PROP_AUTO_WB, 0)
                    if hasattr(cv2, 'CAP_PROP_WB_TEMPERATURE'):
                        cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_temp)
                    print(f"[Camera Config] Windows DirectShow: WB Temperature locked at {wb_temp}K")
                except Exception as e:
                    print(f"[Camera Config] White Balance setting warning: {e}")
            else:
                try:
                    if hasattr(cv2, 'CAP_PROP_AUTO_WB'):
                        cap.set(cv2.CAP_PROP_AUTO_WB, 1)
                except Exception:
                    pass
        else:
            # บน Linux / Raspberry Pi (V4L2):
            if "CAMERA_EXPOSURE" in os.environ:
                try:
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                    exp_val = float(os.environ["CAMERA_EXPOSURE"])
                    cap.set(cv2.CAP_PROP_EXPOSURE, exp_val)
                    print(f"[Camera Config] V4L2 Manual Exposure set to {exp_val}")
                except Exception as e:
                    print(f"[Camera Config] V4L2 Exposure warning: {e}")
            else:
                # ปล่อยให้ V4L2 ควบคุมความสว่างอัตโนมัติ เพื่อให้ภาพสว่างชัดเจน ไม่มืดดำ
                print(f"[Camera Config] V4L2 Camera active in standard mode (Auto-Exposure)")

    def _open_camera(self):
        """ค้นหาและเปิดกล้องที่ใช้งานได้จริง (ทดสอบทั้ง Windows และ Linux/Raspberry Pi)"""
        import platform
        is_windows = (platform.system() == "Windows")

        # 1. หากผู้ใช้กำหนด CAMERA_INDEX มาทาง Environment Variable ให้ลองตัวนั้นก่อน
        env_cam = os.environ.get("CAMERA_INDEX")
        if env_cam is not None:
            try:
                forced_idx = int(env_cam)
                print(f"[Camera] Trying forced CAMERA_INDEX={forced_idx}")
                cap = cv2.VideoCapture(forced_idx, cv2.CAP_DSHOW if is_windows else cv2.CAP_V4L2)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        print(f"[Camera] Successfully opened Camera {forced_idx}")
                        self._configure_camera(cap)
                        return cap
                    cap.release()
            except Exception as e:
                print(f"[Camera] Error with forced index {env_cam}: {e}")

        if is_windows:
            # บน Windows: ลองหากล้องแยกด้วย pygrabber ก่อน
            try:
                from pygrabber.dshow_graph import FilterGraph
                graph = FilterGraph()
                devices = graph.get_input_devices()
                for idx, name in enumerate(devices):
                    name_lower = name.lower()
                    if any(internal in name_lower for internal in ["hd user facing", "integrated", "ir camera", "face"]):
                        continue
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            print(f"[Camera] Using External USB Camera: {name} (Index {idx})")
                            self._configure_camera(cap)
                            return cap
                        cap.release()
            except Exception as e:
                print("[Camera] Pygrabber error:", e)

            # หากไม่พบ หรือเปิดไม่ได้ ลองไล่ Index 0, 1, 2
            for idx in [0, 1, 2]:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        print(f"[Camera] Using Camera Index {idx} (DirectShow)")
                        self._configure_camera(cap)
                        return cap
                    cap.release()
            return None
        else:
            # บน Linux / Raspberry Pi:
            import glob
            video_devices = sorted(glob.glob("/dev/video*"))
            print(f"[Pi Camera] Scanning video devices: {video_devices}")

            indices_to_try = []
            for dev in video_devices:
                try:
                    num = int(dev.replace("/dev/video", ""))
                    indices_to_try.append(num)
                except ValueError:
                    pass

            if not indices_to_try:
                indices_to_try = [0, 1, 2, 3, 4]
            else:
                for i in [0, 1, 2]:
                    if i not in indices_to_try:
                        indices_to_try.append(i)

            print(f"[Pi Camera] Testing camera indices: {indices_to_try}")

            for idx in indices_to_try:
                # ลองด้วย V4L2 ก่อน (มาตรฐาน Linux / Pi)
                try:
                    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            print(f"[Pi Camera] Successfully opened Camera Index {idx} (/dev/video{idx}) with V4L2")
                            self._configure_camera(cap)
                            return cap
                        cap.release()
                except Exception:
                    pass

                # ลองด้วย default backend
                try:
                    cap = cv2.VideoCapture(idx)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            print(f"[Pi Camera] Successfully opened Camera Index {idx} (/dev/video{idx}) with default backend")
                            self._configure_camera(cap)
                            return cap
                        cap.release()
                except Exception:
                    pass

            print("[Pi Camera] Warning: No functional camera found across all indices.")
            return None

    def _start_cam_grabber(self):
        """เริ่มเธรดดึงเฟรมภาพจากกล้องโดยเฉพาะ (Dedicated Frame Grabber แยก 1 Core บน Pi 5 เพื่อไม่ให้ภาพค้าง)"""
        if self._cam_grabber_running:
            return
        self._cam_grabber_running = True

        def grabber_loop():
            # กำหนด CPU Affinity ให้เธรดกล้องรันบน Core 3 โดยเฉพาะ (บน Raspberry Pi 5 มี 4 Cores: 0, 1, 2, 3)
            set_thread_affinity([3])
            while self.is_running and getattr(self, '_cam_grabber_running', False):
                cap = self.cap
                if cap is not None and cap.isOpened():
                    try:
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            with self._cam_frame_lock:
                                self._latest_raw_frame = frame
                            # หน่วงเวลาสั้นมาก (5ms) เพื่อดูดเฟรมจาก Hardware Driver Buffer ตลอดเวลา ไม่ให้ค้างสะสม
                            time.sleep(0.005)
                            continue
                    except Exception:
                        pass
                time.sleep(0.02)

        th = threading.Thread(target=grabber_loop, daemon=True, name="CamGrabber-Core3")
        th.start()
        self._cam_grabber_thread = th
        print("[Pi5 Multi-Core] Dedicated Camera Grabber Thread active (Target: CPU Core 3).")

    def _read_latest_frame(self, timeout=0.8):
        """ดึงเฟรมภาพล่าสุดสดๆ จาก Camera Grabber โดยไม่ต้องรอคิว (Zero Latency)"""
        start = time.time()
        while time.time() - start < timeout:
            with self._cam_frame_lock:
                if self._latest_raw_frame is not None:
                    return True, self._latest_raw_frame.copy()
            time.sleep(0.01)
        return False, None

    def start(self):
        if self.is_running:
            return
        
        if self.model is None:
            try:
                import torch
                import platform
                if platform.system() == "Linux":
                    torch.set_num_threads(2)
                    print("[Pi5 Multi-Core] PyTorch configured with 2 threads (preserving Core 3 for Camera & Core 0 for GUI)")
                else:
                    torch.set_num_threads(4)
                print(f"[AI Model] Loading YOLO classifier from {self.model_path}...")
                self.model = YOLO(self.model_path)
                dummy = np.zeros((320, 320, 3), dtype=np.uint8)
                self.model.predict(dummy, imgsz=320, verbose=False)
                print(f"[AI Model] Classifier model ready.")
            except Exception as e:
                print(f"Failed to load YOLO model: {e}")
                return

        if getattr(self, 'locator_model', None) is None:
            try:
                print(f"[AI Model] Loading YOLOv8 bottle locator from {self.locator_model_path}...")
                self.locator_model = YOLO(self.locator_model_path)
                dummy = np.zeros((320, 320, 3), dtype=np.uint8)
                self.locator_model.predict(dummy, imgsz=320, verbose=False)
                print(f"[AI Model] Bottle locator model ready.")
            except Exception as e:
                print(f"[AI Model] Warning: Could not load locator model: {e}")

        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        self.serial_thread = threading.Thread(target=self._read_serial_loop, daemon=True)
        self.serial_thread.start()

        # เริ่มต้น Web Streamer อัตโนมัติ (เปิดผ่าน Browser เช่น http://<IP>:5000 ได้ทันที)
        enable_stream = (os.environ.get("ENABLE_STREAM", "1") == "1")
        if enable_stream:
            self._start_stream_server()
        
        print("AI Detector & Scale Started in background.")

    def stop(self):
        self.is_running = False
        self._cam_grabber_running = False
        with self._cam_frame_lock:
            self._latest_raw_frame = None
        if getattr(self, '_stream_server', None) is not None:
            try:
                self._stream_server.shutdown()
                self._stream_server.server_close()
            except:
                pass
            self._stream_server = None

        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
            
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
        print("AI Detector Stopped.")

    def _detect_bottle_box(self, img, offset_x=0, offset_y=0):
        """
        ตรวจจับตำแหน่งรูปทรงขวด (Bottle Body Shape) อย่างแม่นยำสูง
        ใช้ Hybrid Dual-Detector:
        1. YOLOv8 COCO Locator (ตรวจจับรูปทรงขวด bottle/cup/vase ด้วยความแม่นยำ 80-95%)
        2. Custom Model (ตรวจจับขวด clear/colored/opaque)
        คืนค่า: (best_box, best_conf, best_source, dbg_boxes, custom_scores)
        """
        best_box = None
        best_conf = 0.0
        best_source = None
        dbg_boxes = []
        custom_scores = {}

        # 1. ค้นหาด้วย Locator Model (ตรวจจับรูปทรงขวดแท้จริงจากสภาพแวดล้อม ป้องกันขวดทิพย์)
        if getattr(self, 'locator_model', None) is not None:
            try:
                res_loc = self.locator_model.predict(img, conf=0.30, imgsz=480, verbose=False)
                if res_loc and len(res_loc) > 0 and res_loc[0].boxes is not None:
                    for b in res_loc[0].boxes:
                        c_id = int(b.cls[0])
                        c_name = self.locator_model.names[c_id]
                        c_conf = float(b.conf[0])
                        if c_name in ('bottle', 'cup', 'vase'):
                            raw = b.xyxy[0].tolist() if hasattr(b.xyxy[0], 'tolist') else b.xyxy[0]
                            bw = abs(raw[2] - raw[0])
                            bh = abs(raw[3] - raw[1])
                            aspect = float(bh) / max(1.0, float(bw))
                            dbg_boxes.append(f"{c_name}:{c_conf:.2f}")
                            if bw >= 20 and bh >= 40 and aspect >= 1.2 and c_conf > best_conf:
                                best_conf = c_conf
                                best_box = [raw[0] + offset_x, raw[1] + offset_y, raw[2] + offset_x, raw[3] + offset_y]
                                best_source = c_name
            except Exception:
                pass

        # 2. ค้นหาด้วย Custom Model ร่วมด้วย
        if self.model is not None:
            try:
                res_cust = self.model.predict(img, conf=0.35, imgsz=480, verbose=False)
                if res_cust and len(res_cust) > 0 and res_cust[0].boxes is not None:
                    for b in res_cust[0].boxes:
                        c_id = int(b.cls[0])
                        c_name = self.model.names[c_id]
                        c_conf = float(b.conf[0])
                        if c_name in classes:
                            custom_scores[c_name] = max(custom_scores.get(c_name, 0.0), c_conf)
                            raw = b.xyxy[0].tolist() if hasattr(b.xyxy[0], 'tolist') else b.xyxy[0]
                            bw = abs(raw[2] - raw[0])
                            bh = abs(raw[3] - raw[1])
                            aspect = float(bh) / max(1.0, float(bw))
                            dbg_boxes.append(f"{c_name}:{c_conf:.2f}")
                            if bw >= 20 and bh >= 40 and aspect >= 1.2 and (c_conf > best_conf or best_box is None):
                                best_conf = c_conf
                                best_box = [raw[0] + offset_x, raw[1] + offset_y, raw[2] + offset_x, raw[3] + offset_y]
                                best_source = c_name
            except Exception:
                pass

        return best_box, best_conf, best_source, dbg_boxes, custom_scores

    def _classify_by_vision(self, frame, box=None):
        """
        วิเคราะห์ชนิดขวดด้วยอัลกอริทึม Background-Aware Differential Vision:
        1. เก็บตัวอย่างฉากหลังนอกตัวขวด (Background Sampling) เพื่อใช้อ้างอิงระดับความสว่างและค่าสีพื้นฐาน
        2. ตรวจสอบบริเวณคอขวดและบ่าขวด (Neck & Shoulder ROI) ไร้ฉลากปิดทับ
        3. คำนวณสีส่วนเกินเปรียบเทียบกับฉากหลัง (Differential Color Excess = Neck Color - Background Color)
        4. ตรวจจับขวดขุ่น (HDPE Diffuse Matte White) อย่างแม่นยำบนทุกฉากหลัง
        5. ตรวจจับการหักเหแสงที่ขอบทรงกระบอก (Fresnel Refraction Edges) และความโปร่งแสงของขวดใส PET
        คืนค่า: "colored", "opaque", หรือ "clear"
        """
        try:
            h, w = frame.shape[:2]
            
            if box is None:
                self.last_neck_box = None
                self.last_cap_box = None
                self.last_base_box = None
                return None

            try:
                if hasattr(box, 'tolist'):
                    b_list = box.tolist()
                else:
                    b_list = list(box)
                x1, y1, x2, y2 = [int(v) for v in b_list[:4]]
            except Exception:
                return None

            # Clamp coordinates to frame dimensions
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(x1, min(w, x2))
            y2 = max(y1, min(h, y2))

            bw = abs(x2 - x1)
            bh = abs(y2 - y1)

            if bw < 20 or bh < 45:
                self.last_neck_box = None
                self.last_cap_box = None
                self.last_base_box = None
                return None

            # -------------------------------------------------------------------------
            # 0. Background Sampling (สุ่มเก็บตัวอย่างฉากหลังนอกตัวขวด ซ้าย-ขวา)
            # -------------------------------------------------------------------------
            bg_samples = []
            pad_w = max(10, int(bw * 0.35))
            bg_l = frame[y1:y2, max(0, x1 - pad_w):max(0, x1 - 5)]
            bg_r = frame[y1:y2, min(w, x2 + 5):min(w, x2 + pad_w)]
            if bg_l.size > 0:
                bg_samples.append(bg_l.reshape(-1, 3))
            if bg_r.size > 0:
                bg_samples.append(bg_r.reshape(-1, 3))

            if bg_samples:
                bg_pixels = np.vstack(bg_samples)
                bg_gray_mean = float(np.mean(cv2.cvtColor(bg_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2GRAY)))
                bg_hsv = cv2.cvtColor(bg_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
                bg_H = bg_hsv[:, 0]
                bg_S = bg_hsv[:, 1]
                bg_b = bg_pixels[:, 0].astype(int)
                bg_g = bg_pixels[:, 1].astype(int)
                bg_r = bg_pixels[:, 2].astype(int)
                bg_tot = float(len(bg_pixels))
                bg_amber_ratio = float(np.sum((((bg_H >= 6) & (bg_H <= 24)) | (bg_H >= 172)) & (bg_S >= 40) & (bg_r - bg_b >= 20) & (bg_b < 95))) / bg_tot
                bg_green_ratio = float(np.sum((bg_H >= 35) & (bg_H <= 85) & (bg_S >= 40) & (bg_g - bg_r >= 15) & (bg_b < 95))) / bg_tot
                bg_blue_ratio = float(np.sum((bg_H >= 90) & (bg_H <= 135) & (bg_S >= 40) & (bg_b >= 120) & (bg_b - bg_r >= 30))) / bg_tot
            else:
                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                bg_gray_mean = float(np.mean(frame_gray))
                bg_amber_ratio = 0.0
                bg_green_ratio = 0.0
                bg_blue_ratio = 0.0

            # -------------------------------------------------------------------------
            # 1. กำหนดตำแหน่งคอขวดแท้จริง (Naked Neck ROI - ใต้ฝาและเหนือฉลาก)
            # -------------------------------------------------------------------------
            if bw >= 25 and bh >= 45:
                # 0. ฝาขวด (Cap ROI: 0% - 9% ของความสูงขวด กึ่งกลาง 60%)
                cy1 = max(0, min(h - 2, int(y1 + 0.00 * bh)))
                cy2 = max(cy1 + 1, min(h, int(y1 + 0.09 * bh)))
                cx1 = max(0, min(w - 2, int(x1 + 0.20 * bw)))
                cx2 = max(cx1 + 1, min(w, int(x2 - 0.20 * bw)))
                self.last_cap_box = [cx1, cy1, cx2, cy2]
                cap_crop = frame[cy1:cy2, cx1:cx2]

                # 1. คอขวดแท้จริง (Naked Neck ROI: 7% - 14% ใต้ฝา กึ่งกลาง 36%)
                ny1 = max(0, min(h - 2, int(y1 + 0.07 * bh)))
                ny2 = max(ny1 + 1, min(h, int(y1 + 0.14 * bh)))
                nx1 = max(0, min(w - 2, int(x1 + 0.32 * bw)))
                nx2 = max(nx1 + 1, min(w, int(x2 - 0.32 * bw)))
                self.last_neck_box = [nx1, ny1, nx2, ny2]

                # 2. บ่าขวด (Shoulder ROI: 14% - 28% ของความสูงขวด กึ่งกลาง 50%)
                sy1 = max(0, min(h - 2, int(y1 + 0.14 * bh)))
                sy2 = max(sy1 + 1, min(h, int(y1 + 0.28 * bh)))
                sx1 = max(0, min(w - 2, int(x1 + 0.25 * bw)))
                sx2 = max(sx1 + 1, min(w, int(x2 - 0.25 * bw)))
                shoulder_crop = frame[sy1:sy2, sx1:sx2]

                # 2.5 บริเวณคอและบ่ารวม (Upper Bottle Region: 7% - 30% กึ่งกลาง 50%)
                uy1 = max(0, min(h - 2, int(y1 + 0.07 * bh)))
                uy2 = max(uy1 + 1, min(h, int(y1 + 0.30 * bh)))
                ux1 = max(0, min(w - 2, int(x1 + 0.25 * bw)))
                ux2 = max(ux1 + 1, min(w, int(x2 - 0.25 * bw)))
                upper_crop = frame[uy1:uy2, ux1:ux2]

                # 3. ก้นขวดใต้ฉลาก (86%-98% ของความสูงขวด)
                base_y1 = max(0, min(h - 2, int(y1 + 0.86 * bh)))
                base_y2 = max(base_y1 + 1, min(h, int(y1 + 0.98 * bh)))
                base_x1 = max(0, min(w - 2, int(x1 + 0.25 * bw)))
                base_x2 = max(base_x1 + 1, min(w, int(x2 - 0.25 * bw)))
                self.last_base_box = [base_x1, base_y1, base_x2, base_y2]

                neck_crop = frame[ny1:ny2, nx1:nx2]
                base_crop = frame[base_y1:base_y2, base_x1:base_x2]
            else:
                self.last_cap_box = None
                ny1 = int(h * 0.10)
                ny2 = int(h * 0.20)
                nx1 = int(w * 0.38)
                nx2 = int(w * 0.62)
                self.last_neck_box = [nx1, ny1, nx2, ny2]
                self.last_base_box = None
                cap_crop = None
                neck_crop = frame[ny1:ny2, nx1:nx2]
                shoulder_crop = None
                upper_crop = frame[ny1:ny2, nx1:nx2]
                base_crop = None

            sample = neck_crop if (neck_crop is not None and neck_crop.size > 0) else frame

            hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
            H = hsv[:, :, 0]
            S = hsv[:, :, 1]
            V = hsv[:, :, 2]
            b = sample[:, :, 0].astype(np.int16)
            g = sample[:, :, 1].astype(np.int16)
            r = sample[:, :, 2].astype(np.int16)
            total_px = float(sample.shape[0] * sample.shape[1])
            if total_px <= 0:
                return None

            # คัดกรองแสงสะท้อนจ้า (Specular Glare) ออกจากการตรวจจับสี
            glare_mask = (V >= 225) & (b >= 170) & (g >= 170) & (r >= 170)
            valid_px = ~glare_mask

            # ตรวจจับขวดสีน้ำตาล/สีเข้ม (Amber / Brown เช่น M-150, เบียร์ช้าง/สิงห์)
            amber_mask = valid_px & (((H >= 6) & (H <= 24)) | (H >= 172)) & (S >= 45) & (V >= 25) & (V <= 210) & (r - b >= 25) & (r > 45) & (b < 85)
            amber_ratio = np.sum(amber_mask) / total_px

            # ตรวจจับขวดสีเขียวแท้ (Green เช่น สไปรท์ขวดเขียว, เบียร์ไฮเนเก้นเนื้อเขียว)
            green_mask = valid_px & (H >= 35) & (H <= 85) & (S >= 45) & (V >= 30) & (V <= 210) & (g - r >= 15) & (g - b >= 15) & (b < 95)
            green_ratio = np.sum(green_mask) / total_px

            # ตรวจจับขวดสีฟ้า/น้ำเงินแท้ (Vivid Blue เช่น B'lue, เป๊ปซี่ขวดฟ้า)
            blue_mask = valid_px & (H >= 90) & (H <= 135) & (S >= 45) & (b >= 120) & (b - r >= 35) & (r <= 140) & (b >= g + 5)
            blue_ratio = np.sum(blue_mask) / total_px

            # ตรวจสอบสีฟ้าที่ฝาขวด (Cap ROI) สำหรับขวด B'lue
            cap_blue_ratio = 0.0
            if cap_crop is not None and cap_crop.size > 0:
                try:
                    c_hsv = cv2.cvtColor(cap_crop, cv2.COLOR_BGR2HSV)
                    c_H, c_S = c_hsv[:, :, 0], c_hsv[:, :, 1]
                    c_b = cap_crop[:, :, 0].astype(int)
                    c_g = cap_crop[:, :, 1].astype(int)
                    c_r = cap_crop[:, :, 2].astype(int)
                    c_tot = float(cap_crop.shape[0] * cap_crop.shape[1])
                    c_mask = (c_H >= 90) & (c_H <= 135) & (c_S >= 45) & (c_b >= 120) & (c_b - c_r >= 35) & (c_r <= 140) & (c_b >= c_g + 5)
                    cap_blue_ratio = float(np.sum(c_mask)) / c_tot
                except Exception:
                    pass

            # ตรวจสอบสีฟ้า, เขียว, และชาที่บ่าขวด (Shoulder ROI - ไร้ฉลาก)
            sh_blue_ratio = 0.0
            sh_green_ratio = 0.0
            sh_amber_ratio = 0.0
            if shoulder_crop is not None and shoulder_crop.size > 0:
                try:
                    sh_hsv = cv2.cvtColor(shoulder_crop, cv2.COLOR_BGR2HSV)
                    sh_H, sh_S, sh_V = sh_hsv[:, :, 0], sh_hsv[:, :, 1], sh_hsv[:, :, 2]
                    sh_b = shoulder_crop[:, :, 0].astype(int)
                    sh_g = shoulder_crop[:, :, 1].astype(int)
                    sh_r = shoulder_crop[:, :, 2].astype(int)
                    sh_tot = float(shoulder_crop.shape[0] * shoulder_crop.shape[1])
                    sh_mask = (sh_H >= 90) & (sh_H <= 135) & (sh_S >= 45) & (sh_b >= 120) & (sh_b - sh_r >= 35) & (sh_r <= 140) & (sh_b >= sh_g + 5)
                    sh_blue_ratio = float(np.sum(sh_mask)) / sh_tot

                    sh_grn_mask = (sh_H >= 35) & (sh_H <= 85) & (sh_S >= 45) & (sh_V >= 30) & (sh_g - sh_r >= 15) & (sh_g - sh_b >= 15) & (sh_b < 95)
                    sh_green_ratio = float(np.sum(sh_grn_mask)) / sh_tot

                    sh_amb_mask = (((sh_H >= 6) & (sh_H <= 24)) | (sh_H >= 172)) & (sh_S >= 45) & (sh_V >= 25) & (sh_r - sh_b >= 25) & (sh_r > 45) & (sh_b < 85)
                    sh_amber_ratio = float(np.sum(sh_amb_mask)) / sh_tot
                except Exception:
                    pass

            # ตรวจสอบสีฟ้าที่ตัวขวด (Body ROI) สำหรับขวด B'lue
            body_blue_ratio = 0.0
            if box is not None and bw >= 25 and bh >= 45:
                try:
                    body_crop = frame[y1:y2, x1:x2]
                    if body_crop.size > 0:
                        bd_hsv = cv2.cvtColor(body_crop, cv2.COLOR_BGR2HSV)
                        bd_H, bd_S = bd_hsv[:, :, 0], bd_hsv[:, :, 1]
                        bd_b = body_crop[:, :, 0].astype(int)
                        bd_g = body_crop[:, :, 1].astype(int)
                        bd_r = body_crop[:, :, 2].astype(int)
                        bd_tot = float(body_crop.shape[0] * body_crop.shape[1])
                        bd_mask = (bd_H >= 90) & (bd_H <= 135) & (bd_S >= 45) & (bd_b >= 120) & (bd_b - bd_r >= 35) & (bd_r <= 140) & (bd_b >= bd_g + 5)
                        body_blue_ratio = float(np.sum(bd_mask)) / bd_tot
                except Exception:
                    pass

            # ตรวจจับขวดสีสดอื่นๆ
            vibrant_mask = valid_px & (S >= 65) & (V >= 45) & (V <= 215)
            vibrant_ratio = np.sum(vibrant_mask) / total_px

            # ตรวจจับขวดสีขุ่นบริเวณคอขวดแท้จริง (Opaque White เช่น HDPE นมขาวขุ่น)
            opaque_mask = (V >= 135) & (S <= 45) & (b >= 115) & (g >= 115) & (r >= 115) & (np.abs(b - r) <= 35)
            opaque_ratio = float(np.sum(opaque_mask)) / total_px

            # ตรวจจับสีขุ่นบริเวณบ่าขวด (Shoulder ROI Opaque White)
            sh_opaque_ratio = 0.0
            sh_mean = 0.0
            sh_dark = 1.0
            if shoulder_crop is not None and shoulder_crop.size > 0:
                try:
                    sh_gray_c = cv2.cvtColor(shoulder_crop, cv2.COLOR_BGR2GRAY)
                    sh_mean = float(np.mean(sh_gray_c))
                    sh_dark = float(np.mean(sh_gray_c <= 80))
                    sh_hsv = cv2.cvtColor(shoulder_crop, cv2.COLOR_BGR2HSV)
                    sh_V, sh_S = sh_hsv[:, :, 2], sh_hsv[:, :, 1]
                    sh_b = shoulder_crop[:, :, 0].astype(int)
                    sh_g = shoulder_crop[:, :, 1].astype(int)
                    sh_r = shoulder_crop[:, :, 2].astype(int)
                    sh_tot = float(shoulder_crop.shape[0] * shoulder_crop.shape[1])
                    sh_op_mask = (sh_V >= 135) & (sh_S <= 45) & (sh_b >= 115) & (sh_g >= 115) & (sh_r >= 115) & (np.abs(sh_b - sh_r) <= 35)
                    sh_opaque_ratio = float(np.sum(sh_op_mask)) / sh_tot
                except Exception:
                    pass

            # คำนวณสีส่วนเกินเปรียบเทียบกับฉากหลัง (Differential Color Excess)
            diff_amber = max(0.0, amber_ratio - bg_amber_ratio)
            diff_green = max(0.0, green_ratio - bg_green_ratio)
            diff_blue = max(0.0, blue_ratio - bg_blue_ratio)
            diff_cap_blue = max(0.0, cap_blue_ratio - bg_blue_ratio)
            diff_sh_blue = max(0.0, sh_blue_ratio - bg_blue_ratio)
            diff_sh_green = max(0.0, sh_green_ratio - bg_green_ratio)
            diff_sh_amber = max(0.0, sh_amber_ratio - bg_amber_ratio)
            diff_body_blue = max(0.0, body_blue_ratio - bg_blue_ratio)

            # -------------------------------------------------------------------------
            # 2. ตรวจสอบก้นขวด (Base ROI)
            # -------------------------------------------------------------------------
            base_is_colored = False
            base_is_opaque = False
            if base_crop is not None and base_crop.size > 0:
                try:
                    b_hsv = cv2.cvtColor(base_crop, cv2.COLOR_BGR2HSV)
                    b_H, b_S, b_V = b_hsv[:, :, 0], b_hsv[:, :, 1], b_hsv[:, :, 2]
                    b_b = base_crop[:, :, 0].astype(int)
                    b_g = base_crop[:, :, 1].astype(int)
                    b_r = base_crop[:, :, 2].astype(int)
                    b_tot = float(base_crop.shape[0] * base_crop.shape[1])

                    b_amb = np.sum((((b_H >= 6) & (b_H <= 24)) | (b_H >= 172)) & (b_S >= 40) & (b_V >= 25) & (b_r - b_b >= 20) & (b_b < 95)) / b_tot
                    b_grn = np.sum((b_H >= 35) & (b_H <= 85) & (b_S >= 45) & (b_V >= 30) & (b_g - b_r >= 15) & (b_g - b_b >= 15) & (b_b < 95)) / b_tot
                    b_blu = np.sum((b_H >= 95) & (b_H <= 135) & (b_S >= 45) & (b_b >= 135) & (b_b - b_r >= 35) & (b_b >= b_g + 8)) / b_tot

                    diff_b_amb = max(0.0, b_amb - bg_amber_ratio)
                    diff_b_grn = max(0.0, b_grn - bg_green_ratio)
                    diff_b_blu = max(0.0, b_blu - bg_blue_ratio)

                    if (diff_b_amb >= 0.15 or diff_b_grn >= 0.18 or diff_b_blu >= 0.14):
                        base_is_colored = True

                    b_gray = cv2.cvtColor(base_crop, cv2.COLOR_BGR2GRAY)
                    b_dark = float(np.mean(b_gray <= 80))
                    b_op = np.sum((b_V >= 135) & (b_S <= 45) & (b_b >= 115) & (b_g >= 115) & (b_r >= 115) & (np.abs(b_b - b_r) <= 35)) / b_tot
                    if b_op >= 0.45 and b_dark <= 0.04:
                        base_is_opaque = True
                except Exception:
                    pass

            # -------------------------------------------------------------------------
            # 3. การวิเคราะห์ระดับ Grayscale & Texture (ความโปร่งใส vs ขาวขุ่นทึบแสง)
            # -------------------------------------------------------------------------
            gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
            gray_mean = float(np.mean(gray))
            gray_std = float(np.std(gray))

            # Sobel Edge Gradient Magnitude วัดการหักเหแสง/ขอบสะท้อนบนเนื้อขวด
            sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            grad = np.sqrt(sobelx**2 + sobely**2)
            grad_mean = float(np.mean(grad))

            # อัตราส่วนพิกเซลมืด (Dark Transmission)
            dark_ratio = float(np.mean(gray <= 80))
            # อัตราส่วนจุดแสงสะท้อนจ้า (Specular Highlights) บนผิวพลาสติกใส
            specular_ratio = float(np.mean(gray >= 215))
            mean_s = float(np.mean(S))

            # ฉากหลังในตู้รับขวด (Dark Chamber): ค่าความสว่างเฉลี่ยของตู้ <= 120
            bg_is_dark = (bg_gray_mean <= 120)

            # ตรวจจับขอบทรงกระบอกหักเหแสง (Fresnel Refraction Edges)
            # ในขวดใส PET ที่อยู่บนฉากหลังสว่าง ขอบซ้าย-ขวาของกระบอกจะมืดกว่าทั้งกึ่งกลางและฉากหลัง
            # (บนฉากหลังมืด ไม่ใช้ขอบ Fresnel เพื่อป้องกันการเข้าใจผิดจากขอบฉากหลังมืดนอกคอขวด)
            has_fresnel_edges = False
            if bw >= 25 and bh >= 45 and (not bg_is_dark):
                try:
                    neck_full_w = frame[ny1:ny2, x1:x2]
                    if neck_full_w.size > 0:
                        neck_full_gray = cv2.cvtColor(neck_full_w, cv2.COLOR_BGR2GRAY)
                        edge_w = max(2, int(bw * 0.15))
                        if neck_full_gray.shape[1] > 2 * edge_w:
                            left_edge_val = float(np.mean(neck_full_gray[:, :edge_w]))
                            right_edge_val = float(np.mean(neck_full_gray[:, -edge_w:]))
                            center_val = float(np.mean(neck_full_gray[:, edge_w:-edge_w]))
                            min_edge = min(left_edge_val, right_edge_val)
                            has_fresnel_edges = (
                                (min_edge < center_val - 15) and 
                                (bg_gray_mean - min_edge >= 20)
                            )
                except Exception:
                    has_fresnel_edges = False

            # ตรวจสอบว่าเป็นฉากหลังว่างเปล่าที่ไม่มีขวดจริงหรือไม่ (Empty Chamber Rejection)
            # ป้องกันระบบจับเจอ "ขวดทิพย์" เมื่อไม่มีขวดวางอยู่ในช่องรับขวด
            if bg_is_dark:
                is_empty_background = (
                    (gray_std < 22.0) and 
                    (grad_mean < 35.0) and 
                    (specular_ratio < 0.04) and 
                    (diff_amber < 0.12) and (diff_green < 0.12) and (diff_blue < 0.05) and (opaque_ratio < 0.25)
                )
            else:
                is_empty_background = (
                    (not has_fresnel_edges) and 
                    (abs(gray_mean - bg_gray_mean) < 18.0) and 
                    (grad_mean < 25.0) and 
                    (gray_std < 18.0) and 
                    (diff_amber < 0.12) and (diff_green < 0.12) and (diff_blue < 0.05)
                )

            if is_empty_background:
                return None

            # การวิเคราะห์บริเวณคอและบ่ารวม (Upper Bottle Region: Neck + Shoulder)
            up_gray = cv2.cvtColor(upper_crop, cv2.COLOR_BGR2GRAY) if (upper_crop is not None and upper_crop.size > 0) else gray
            up_mean = float(np.mean(up_gray))
            up_dark = float(np.mean(up_gray <= 90))
            up_hsv = cv2.cvtColor(upper_crop, cv2.COLOR_BGR2HSV) if (upper_crop is not None and upper_crop.size > 0) else hsv
            up_V, up_S = up_hsv[:, :, 2], up_hsv[:, :, 1]
            up_diffuse_white = float(np.mean((up_V >= 115) & (up_S <= 45)))
            up_nonglare = up_gray[up_gray < 215]
            up_ng_mean = float(np.mean(up_nonglare)) if up_nonglare.size > 0 else up_mean
            up_p25 = float(np.percentile(up_nonglare, 25)) if up_nonglare.size > 0 else 0.0

            # คุณสมบัติขวดขุ่นแท้ (HDPE Diffuse Matte White เช่น ขวดนมเมจิ, บีทาเก้น):
            if bg_is_dark:
                # บนฉากหลังมืด (เช่น ฟิวเจอร์บอร์ดสีดำ):
                # ขวดขุ่น HDPE: เนื้อขาวทึบแสงทั่วคอและบ่า สว่างกว่าฉากหลังชัดเจน และแทบไม่มีพิกเซลมืดทะลุผ่าน (dark <= 8%)
                is_diffuse_opaque = (up_dark <= 0.08) and (up_diffuse_white >= 0.45) and (up_ng_mean >= 150.0 or up_mean >= 165.0)
                # ขวดใส PET: พลาสติกโปร่งแสง มองทะลุเห็นฟิวเจอร์บอร์ดสีดำ (dark >= 8% หรือ non-glare mean ต่ำ หรือมี specular highlight)
                is_transparent_clear = (not is_diffuse_opaque) and (up_dark >= 0.08 or up_ng_mean < 145.0 or up_p25 < 110.0 or specular_ratio >= 0.02)
            else:
                # บนฉากหลังสว่าง:
                is_diffuse_opaque = (up_mean >= 180.0) and (up_dark <= 0.04) and (up_diffuse_white >= 0.45)
                is_transparent_clear = (not is_diffuse_opaque) and ((up_dark >= 0.06) or (has_fresnel_edges) or (specular_ratio >= 0.03))

            self.last_vision_metrics = {
                'amber': amber_ratio,
                'green': green_ratio,
                'blue': blue_ratio,
                'cap_blue': cap_blue_ratio,
                'sh_blue': sh_blue_ratio,
                'body_blue': body_blue_ratio,
                'diff_amber': diff_amber,
                'diff_green': diff_green,
                'diff_blue': diff_blue,
                'bg_gray': bg_gray_mean,
                'bg_amber': bg_amber_ratio,
                'bg_green': bg_green_ratio,
                'bg_blue': bg_blue_ratio,
                'fresnel': has_fresnel_edges,
                'vibrant': vibrant_ratio,
                'opaque': opaque_ratio,
                'sh_opaque': sh_opaque_ratio,
                'gray_mean': gray_mean,
                'gray_std': gray_std,
                'grad_mean': grad_mean,
                'dark_ratio': dark_ratio,
                'sh_mean': sh_mean,
                'sh_dark': sh_dark,
                'is_transparent': is_transparent_clear,
                'is_diffuse_opaque': is_diffuse_opaque,
                'base_colored': base_is_colored,
                'base_opaque': base_is_opaque
            }

            # -------------------------------------------------------------------------
            # 4. กฎการวิเคราะห์คอและบ่าขวด (Neck & Shoulder Optical Guardrail)
            # -------------------------------------------------------------------------
            # ตรวจสอบว่าคอขวดและบ่าขวดเป็นเนื้อพลาสติกสีแท้ (ไม่ใช่แค่ฝาขวดหรือฉลาก)
            neck_is_colored = (
                ((diff_amber >= 0.25 and diff_sh_amber >= 0.10) or (diff_amber >= 0.40) or (diff_sh_amber >= 0.20) or (diff_amber >= 0.18 and base_is_colored)) or
                ((diff_blue >= 0.25 and diff_sh_blue >= 0.10) or (diff_sh_blue >= 0.18) or (diff_body_blue >= 0.25) or (diff_blue >= 0.18 and base_is_colored)) or
                ((diff_green >= 0.25 and diff_sh_green >= 0.10) or (diff_green >= 0.35) or (diff_sh_green >= 0.18) or (diff_green >= 0.18 and base_is_colored))
            )

            # ตรวจสอบว่าคอขวดและบ่าขวดเป็นพลาสติกใสโปร่งแสง ไร้สีเรซิน (คุ้มครองขวดชาเขียวฉลากใหญ่)
            neck_is_clear = (
                is_transparent_clear and 
                (not neck_is_colored) and 
                (diff_amber < 0.25 or diff_sh_amber < 0.10) and 
                (diff_green < 0.25 or diff_sh_green < 0.10) and 
                (diff_blue < 0.20 or diff_sh_blue < 0.10)
            )

            self.last_vision_metrics['neck_is_clear'] = neck_is_clear
            self.last_vision_metrics['neck_is_colored'] = neck_is_colored

            if neck_is_colored:
                return "colored"
            elif neck_is_clear:
                return "clear"
            elif is_diffuse_opaque:
                return "opaque"

            return None
        except Exception as ex:
            print(f"[Vision Error] {ex}")
            return None

    def get_annotated_frame(self):
        """
        วาด HUD, Bounding Box (ขวด), Neck ROI (คอขวดใต้ฝา), Base ROI (ก้นขวด) 
        และข้อมูลน้ำหนัก/ผลวิเคราะห์ลงบนภาพ สำหรับแสดงผลบน UI แยก (Camera Viewer & Web Stream)
        """
        if self.last_frame is None:
            return None
        
        display = self.last_frame.copy()
        h, w = display.shape[:2]

        # 1. วาดกรอบขวด (Bottle Shape) สีเขียว
        if self.last_bottle_box is not None:
            bx1, by1, bx2, by2 = [int(v) for v in self.last_bottle_box[:4]]
            cv2.rectangle(display, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
            cv2.putText(display, "Bottle Shape", (bx1, max(18, by1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        # 2. วาดกรอบฝาขวด (Cap ROI) สีฟ้า Cyan
        if getattr(self, 'last_cap_box', None) is not None:
            cx1, cy1, cx2, cy2 = self.last_cap_box
            cv2.rectangle(display, (cx1, cy1), (cx2, cy2), (255, 255, 0), 1)

        # 3. วาดกรอบคอขวด (Neck & Shoulder ROI - ไร้ฉลาก) สีทอง/เหลือง
        if self.last_neck_box is not None:
            nx1, ny1, nx2, ny2 = self.last_neck_box
            cv2.rectangle(display, (nx1, ny1), (nx2, ny2), (0, 215, 255), 2)
            cv2.putText(display, "Neck ROI (No Label)", (nx1, max(18, ny1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 255), 2)

        # 4. วาดกรอบก้นขวด (Base ROI) สีม่วง
        if self.last_base_box is not None:
            bx_b1, by_b1, bx_b2, by_b2 = self.last_base_box
            cv2.rectangle(display, (bx_b1, by_b1), (bx_b2, by_b2), (255, 0, 255), 1)

        # 5. กล่อง HUD ข้อมูลด้านบน
        overlay = display.copy()
        cv2.rectangle(overlay, (0, 0), (w, 65), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.70, display, 0.30, 0, display)

        if self.current_state in ("SETTLING", "CONFIRMING", "TRACK_CONFIRM"):
            rem = getattr(self, '_settle_rem', 1.0)
            state_th = f"Confirming (ติดตามตำแหน่งขวด {rem:.1f}s)"
        else:
            state_th = {
                "WAIT_WEIGHT": "Standby (รอวางขวด)",
                "TRACK_CONFIRM": f"Confirming (ยืนยันขวด {getattr(self, '_settle_rem', 1.0):.1f}s)",
                "DETECT": "AI Classifying (กำลังวิเคราะห์)",
                "WAIT_CLEAR": "Sorting (ปล่อยขวดลงถัง)",
                "WAIT_REMOVE": "Wait Remove (รอยกขวดออก)"
            }.get(self.current_state, self.current_state)

        cv2.putText(display, f"State: {state_th}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(display, f"Weight: {self.current_weight:.1f}g", (15, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        if self.last_decision:
            dec_color = (0, 255, 0) if self.last_decision == "clear" else ((0, 165, 255) if self.last_decision == "colored" else (255, 200, 200))
            cv2.putText(display, f"Result: {self.last_decision.upper()}", (w - 230, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.85, dec_color, 2)

        return display

    def get_telemetry(self):
        return {
            "state": self.current_state,
            "weight": round(self.current_weight, 1),
            "decision": self.last_decision,
            "yolo_scores": self.last_yolo_scores,
            "neck_metrics": self.last_vision_metrics,
            "bottle_box": self.last_bottle_box,
            "neck_box": self.last_neck_box,
            "cap_box": getattr(self, 'last_cap_box', None),
            "base_box": self.last_base_box,
            "settle_rem": round(getattr(self, '_settle_rem', 0.0), 1),
            "rotation": getattr(self, 'camera_rotate', 270)
        }

    def save_snapshot(self, folder="Train/dataset_captured"):
        if self.last_frame is None:
            return None
        os.makedirs(folder, exist_ok=True)
        filename = f"bottle_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        full_path = os.path.join(folder, filename)
        cv2.imwrite(full_path, self.last_frame)
        print(f"[Camera Snapshot] Saved training frame to: {full_path}")
        return full_path

    def _start_stream_server(self):
        """
        เริ่ม background HTTP server บน port 5000 (หรือ STREAM_PORT) เพื่อให้บริการ Live MJPEG Video Stream
        และ Web Dashboard สำหรับดูภาพกล้องผ่านบราวเซอร์ (เช่น บนมือถือหรือโน้ตบุ๊ก http://<pi-ip>:5000)
        """
        if getattr(self, '_stream_server', None) is not None:
            return

        detector_ref = self

        class MJPEGHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # ปิด log ใน console ไม่ให้รบกวน

            def do_GET(self):
                if self.path in ('/', '/index.html'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(get_viewer_html().encode('utf-8'))
                elif self.path == '/stream.mjpg':
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control', 'no-cache, private')
                    self.send_header('Pragma', 'no-cache')
                    self.end_headers()
                    while detector_ref.is_running:
                        frame = detector_ref.get_annotated_frame()
                        if frame is not None:
                            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
                            if ret:
                                data = jpeg.tobytes()
                                try:
                                    self.wfile.write(b'--frame\r\n')
                                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                                    self.wfile.write(f'Content-Length: {len(data)}\r\n\r\n'.encode('utf-8'))
                                    self.wfile.write(data)
                                    self.wfile.write(b'\r\n')
                                except (BrokenPipeError, ConnectionResetError):
                                    break
                        time.sleep(0.04)
                elif self.path == '/api/status':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    telemetry = detector_ref.get_telemetry()
                    self.wfile.write(json.dumps(telemetry).encode('utf-8'))
                elif self.path == '/api/snapshot':
                    saved_path = detector_ref.save_snapshot()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    res = {"success": bool(saved_path), "path": saved_path or ""}
                    self.wfile.write(json.dumps(res).encode('utf-8'))
                elif self.path.startswith('/api/rotate'):
                    cur = getattr(detector_ref, 'camera_rotate', 270)
                    new_rot = (cur + 90) % 360
                    if 'angle=' in self.path:
                        try:
                            new_rot = int(self.path.split('angle=')[1].split('&')[0]) % 360
                        except:
                            pass
                    detector_ref.set_rotation(new_rot)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    res = {"success": True, "rotation": new_rot}
                    self.wfile.write(json.dumps(res).encode('utf-8'))
                elif self.path == '/api/tare':
                    detector_ref.tare_scale()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"success": true, "weight": 0.0}')
                elif self.path == '/api/reconnect_camera':
                    ok = detector_ref.reconnect_camera()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": ok}).encode('utf-8'))
                else:
                    self.send_response(404)
                    self.end_headers()

        def run_server():
            port = detector_ref.stream_port
            try:
                class ReusableThreadingServer(ThreadingHTTPServer):
                    allow_reuse_address = True

                server = ReusableThreadingServer(('0.0.0.0', port), MJPEGHandler)
                detector_ref._stream_server = server
                print(f"[Camera Web Stream] Live feed active at: http://0.0.0.0:{port} (Open in browser to view)")
                server.serve_forever()
            except OSError as ex:
                print(f"[Camera Web Stream] Port {port} already in use or unavailable: {ex}")
            except Exception as ex:
                print(f"[Camera Web Stream] Stream server error: {ex}")

        th = threading.Thread(target=run_server, daemon=True)
        th.start()
        self._stream_thread = th

    def _run_loop(self):
        # กำหนด CPU Affinity ให้เธรด AI ประมวลผลรันบน Cores 1, 2 (บน Raspberry Pi 5)
        set_thread_affinity([1, 2])

        last_cam_retry = 0.0
        cap = self._open_camera()
        self.cap = cap
        self._start_cam_grabber()
        if self.cap is None or not self.cap.isOpened():
            print("[Camera] Warning: Camera not opened at startup. Retrying in background...")
            print("   (Serial Scale thread remains active so weight reading continues)")

        has_serial_scale = (self.ser is not None and self.ser.is_open)
        if has_serial_scale:
            print(f"[AI Detector] Ready! Weight-assisted mode active (Min Weight >= {self.min_weight:.1f}g)")
        else:
            print(f"[AI Detector] Ready! Standalone Vision-Only mode active (Show bottle in front of camera to test)")

        show_cam = (os.environ.get("SHOW_CAMERA", "0") == "1")
        if show_cam:
            print("[Camera Preview] Live camera preview window enabled (SHOW_CAMERA=1)")

        state = "WAIT_WEIGHT"
        weight_start_time = 0.0
        weight_samples = []
        last_trigger_time = 0.0
        detect_attempts = 0
        yolo_scores = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
        yolo_votes = {"clear": 0, "colored": 0, "opaque": 0}
        yolo_conf_sum = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
        vision_votes = {"colored": 0, "opaque": 0, "clear": 0}
        best_box = None
        best_yolo_conf = 0.0
        confirm_start_time = 0.0
        consecutive_no_box = 0
        detect_no_box_count = 0
        consecutive_cam_fails = 0

        while self.is_running:
            if getattr(self, 'is_paused', False):
                time.sleep(0.1)
                continue

            # ------------------------------------------------------------------
            # สถานะ WAIT_CLEAR: อยู่ระหว่างที่กลไกเซอร์โวหมุนหย่อนขวดลงถัง
            # เราปิดกล้องชั่วคราวเพื่อป้องกันสัญญาณรบกวน (EMI) และไฟกระชากจากมอเตอร์
            # ------------------------------------------------------------------
            if state == "WAIT_CLEAR":
                current_time = time.time()
                current_weight = self.current_weight
                has_serial_scale = (self.ser is not None and self.ser.is_open)
                time_passed = (current_time - last_trigger_time) >= (6.5 if has_serial_scale else 2.5)

                if has_serial_scale:
                    scale_is_empty = (self.current_weight < self.min_weight)
                    # ป้องกันปัญหาน้ำหนักค้างหลังกลไกทำงานเสร็จสิ้น
                    if time_passed and not scale_is_empty:
                        stick_duration = current_time - (last_trigger_time + 6.5)
                        if stick_duration >= 2.5:
                            print(f"[AI Detector] Scale weight sticking ({self.current_weight:.1f}g) -> Sending rescue TARE to ESP32...")
                            self.send_to_esp32("TARE\n")
                            self.current_weight = 0.0
                            scale_is_empty = True
                    ready_to_exit = time_passed and scale_is_empty
                else:
                    ready_to_exit = time_passed

                if ready_to_exit:
                    if has_serial_scale and self.current_weight >= self.min_weight:
                        print(f"[AI Detector] Item still on scale ({self.current_weight:.1f}g). Waiting for removal...")
                        state = "WAIT_REMOVE"
                    else:
                        print(f"[AI Detector] Bottle sorting complete. Ready for next bottle.")

                    # เปิดกล้องรอบใหม่ (หน่วงเวลา 0.35s รอให้กระแสไฟจากเซอร์โวนิ่งสมบูรณ์)
                    print("[Camera Lifecycle] Sorting complete. Reopening camera for next bottle...")
                    time.sleep(0.35)
                    self.cap = self._open_camera()
                    if self.cap is not None and self.cap.isOpened():
                        self._start_cam_grabber()

                    state = "WAIT_WEIGHT"
                    weight_start_time = 0.0
                    detect_attempts = 0
                    consecutive_cam_fails = 0
                    yolo_scores = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
                    yolo_votes = {"clear": 0, "colored": 0, "opaque": 0}
                    yolo_conf_sum = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
                    vision_votes = {"colored": 0, "opaque": 0, "clear": 0}
                    best_box = None
                    best_yolo_conf = 0.0
                    self.last_bottle_box = None
                    self.last_neck_box = None
                    self.last_base_box = None
                    self.last_decision = None

                time.sleep(0.08)
                continue

            # ------------------------------------------------------------------
            # ตรวจสอบความพร้อมของกล้อง (Watchdog & Auto-Reconnect)
            # ------------------------------------------------------------------
            if self.cap is None or not self.cap.isOpened():
                now = time.time()
                if now - last_cam_retry > 2.5:
                    last_cam_retry = now
                    print("[Camera Watchdog] Camera offline. Attempting auto-reconnect...")
                    if self.cap is not None:
                        try:
                            self.cap.release()
                        except:
                            pass
                    time.sleep(0.3)
                    self.cap = self._open_camera()
                    if self.cap is not None and self.cap.isOpened():
                        self._start_cam_grabber()
                if self.cap is None or not self.cap.isOpened():
                    current_weight = self.current_weight
                    has_serial = (self.ser is not None and self.ser.is_open)
                    if has_serial and current_weight >= self.min_weight:
                        if weight_start_time == 0.0:
                            weight_start_time = time.time()
                        elif time.time() - weight_start_time >= 2.0:
                            # ตาชั่งนิ่งและมีน้ำหนักเกินเกณฑ์ แต่กล้องยังเปิดไม่ได้ -> ส่ง fallback ไปให้ ESP32 ทำงานต่อได้
                            print(f"[Camera Offline Fallback] Weight detected ({current_weight:.1f}g) -> Triggering default Clear bottle")
                            weight_start_time = 0.0
                            if callable(self.callback):
                                self.callback("clear", current_weight, "clear")
                            time.sleep(2.0)
                    else:
                        weight_start_time = 0.0
                    time.sleep(0.1)
                    continue

            # ดึงเฟรมภาพล่าสุดสดๆ จาก Camera Grabber Thread (Core 3) โดยไม่ค้างใน Driver Buffer
            ret, frame = self._read_latest_frame(timeout=0.6)
            if not ret or frame is None:
                consecutive_cam_fails += 1
                if consecutive_cam_fails >= 6:
                    now = time.time()
                    if now - last_cam_retry > 2.5:
                        last_cam_retry = now
                        print(f"[Camera Watchdog] Frame grab failed ({consecutive_cam_fails} frames). Auto-reconnecting camera...")
                        if self.cap is not None:
                            try:
                                self.cap.release()
                            except:
                                pass
                        time.sleep(0.4)
                        self.cap = self._open_camera()
                        if self.cap is not None and self.cap.isOpened():
                            self._start_cam_grabber()
                        consecutive_cam_fails = 0
                time.sleep(0.04)
                continue
            else:
                consecutive_cam_fails = 0

            # หมุนภาพกล้องตามองศาที่กำหนด (0, 90, 180, 270) เพื่อแก้ปัญหากล้องติดตั้งเอียง 90 องศาในตัวเครื่อง
            if self.camera_rotate == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif self.camera_rotate in (270, -90):
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif self.camera_rotate == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)

            self.last_frame = frame
            self.current_state = state

            current_weight = self.current_weight
            current_time = time.time()

            # ตรวจสอบว่าต่อ Serial ตราชั่งอยู่หรือไม่
            has_serial_scale = (self.ser is not None and self.ser.is_open)

            if state == "WAIT_WEIGHT":
                bottle_detected_on_scale = False

                if has_serial_scale:
                    # โหมดหลัก (ต่อตราชั่งจริง): ตรวจสอบน้ำหนักเกิน (เตะออกทันที ไม่เริ่มการตรวจจับ AI)
                    if current_weight > self.max_weight:
                        print(f"[AI Detector] Overweight detected ({current_weight:.1f}g > {self.max_weight:.1f}g). Skipping AI detection.")
                        state = "WAIT_WEIGHT"
                        time.sleep(0.08)
                        continue
                    # ต้องมีน้ำหนักจริงบน Loadcell >= min_weight (10.0g)
                    if current_weight >= self.min_weight:
                        bottle_detected_on_scale = True
                else:
                    # โหมดทดสอบบนคอมพิวเตอร์ (ไม่ได้ต่อ ESP/ตราชั่ง): ให้ AI ส่องตรวจจับขวดผ่านกล้องโดยอัตโนมัติ
                    preview_box, preview_conf, *rest = self._detect_bottle_box(frame)
                    if preview_box is not None and preview_conf >= 0.40:
                        bottle_detected_on_scale = True

                    # อัปเดตค่าน้ำหนักจำลองเพื่อให้ UI บนหน้าจอตอบสนอง
                    if bottle_detected_on_scale:
                        if self.current_weight < 10.0:
                            self.current_weight = 18.5
                    else:
                        if self.current_weight > 0.0:
                            self.current_weight = 0.0
                        self.last_bottle_box = None
                        self.last_neck_box = None
                        self.last_base_box = None
                        self.last_decision = None
                        if show_cam:
                            cv2.putText(frame, "Standby: Waiting for bottle...", (20, 35),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
                            cv2.imshow("BotteProject Camera Test (Q to quit)", frame)
                            cv2.waitKey(1)
                        time.sleep(0.06)
                        continue

                if bottle_detected_on_scale:
                    confirm_delay = float(os.environ.get("CONFIRM_DELAY", "1.0"))
                    confirm_start_time = current_time
                    consecutive_no_box = 0
                    self._settle_target = confirm_delay
                    self._settle_elapsed = 0.0
                    self._settle_rem = confirm_delay
                    state = "TRACK_CONFIRM"
                    self.current_state = "TRACK_CONFIRM"
                    if has_serial_scale:
                        print(f"[Loadcell] Detected weight: {current_weight:.1f}g - Confirming bottle for {confirm_delay:.1f}s (tracking movement)...")
                    else:
                        print(f"[AI Vision-Only] Bottle detected in camera view - Confirming for {confirm_delay:.1f}s (tracking movement)...")
                    continue
                else:
                    self._settle_elapsed = 0.0
                    self._settle_rem = 0.0
                    self.current_state = "WAIT_WEIGHT"
                    time.sleep(0.04)

            elif state == "TRACK_CONFIRM":
                self.current_state = "TRACK_CONFIRM"
                confirm_delay = float(os.environ.get("CONFIRM_DELAY", "1.0"))
                self._settle_target = confirm_delay
                elapsed = current_time - confirm_start_time
                self._settle_elapsed = elapsed
                self._settle_rem = max(0.0, confirm_delay - elapsed)

                # 1. เงื่อนไขยกเลิกทันที (1): หากน้ำหนักตกลงต่ำกว่า min_weight หรือเกิน max_weight
                if has_serial_scale and (self.current_weight < self.min_weight or self.current_weight > self.max_weight):
                    print(f"[AI Detector] Weight out of range ({self.current_weight:.1f}g). Canceling sorting.")
                    state = "WAIT_WEIGHT"
                    self.last_bottle_box = None
                    self.last_neck_box = None
                    self.last_base_box = None
                    self.last_decision = None
                    self._settle_elapsed = 0.0
                    self._settle_rem = 0.0
                    time.sleep(0.05)
                    continue

                # 2. ตรวจจับตำแหน่งขวดแบบ Real-time ทุกเฟรม (ขวดขยับเลื่อนที่ กรอบเขียวและคอขวดเลื่อนตามทันที)
                h, w = frame.shape[:2]
                crop_y1, crop_y2 = int(h * 0.05), int(h * 0.95)
                crop_x1, crop_x2 = int(w * 0.15), int(w * 0.85)
                chamber_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

                current_frame_box, best_conf, src_name, dbg_boxes, _ = self._detect_bottle_box(chamber_crop, crop_x1, crop_y1)

                if current_frame_box is not None:
                    consecutive_no_box = 0
                    self.last_bottle_box = current_frame_box
                    # เลื่อนกรอบคอขวด (ROI) ตามขวดที่ขยับในเฟรมนี้ทันที
                    self._classify_by_vision(frame, current_frame_box)
                else:
                    consecutive_no_box += 1

                # 3. เงื่อนไขยกเลิกทันที (2): หากขวดหายไปจากกล้องต่อเนื่อง (เช่น ดึงขวดออก หรือไม่พบขวด)
                max_no_box = 10 if has_serial_scale else 6
                if consecutive_no_box >= max_no_box:
                    print(f"[AI Detector] Bottle disappeared from camera view ({consecutive_no_box} consecutive frames no box). Canceling sorting.")
                    state = "WAIT_WEIGHT"
                    self.last_bottle_box = None
                    self.last_neck_box = None
                    self.last_base_box = None
                    self.last_decision = None
                    self._settle_elapsed = 0.0
                    self._settle_rem = 0.0
                    time.sleep(0.05)
                    continue

                # 4. เมื่อครบ 1.0 วินาที และยืนยันว่ามีขวดอยู่จริง -> เริ่มขั้นตอนแยกชนิดขวด (DETECT)
                if elapsed >= confirm_delay:
                    if self.last_bottle_box is None and consecutive_no_box > 0:
                        if has_serial_scale and self.current_weight >= self.min_weight:
                            # สำรอง: หากมีน้ำหนักขวดบนตาชั่งแน่นอน แต่โมเดลตรวจภาพพลาด ให้ใช้บริเวณกลางห้องรับขวด
                            self.last_bottle_box = [crop_x1, crop_y1, crop_x2, crop_y2]
                            self._classify_by_vision(frame, self.last_bottle_box)
                            print(f"[AI Detector] Scale weight confirmed ({self.current_weight:.1f}g). Activating AI Classifier...")
                            state = "DETECT"
                            self.current_state = "DETECT"
                            detect_attempts = 0
                            detect_no_box_count = 0
                            yolo_scores = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
                            yolo_votes = {"clear": 0, "colored": 0, "opaque": 0}
                            yolo_conf_sum = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
                            vision_votes = {"colored": 0, "opaque": 0, "clear": 0}
                            best_box = self.last_bottle_box
                            best_yolo_conf = 0.0
                        else:
                            print(f"[AI Detector] {confirm_delay:.1f}s elapsed but no bottle confirmed by camera. Canceling sorting.")
                            state = "WAIT_WEIGHT"
                            self.last_bottle_box = None
                            self.last_neck_box = None
                            self.last_base_box = None
                            self.last_decision = None
                    else:
                        print(f"[AI Detector] Bottle confirmed after {elapsed:.2f}s tracking (conf={best_conf:.2f}). Activating AI Classifier...")
                        state = "DETECT"
                        self.current_state = "DETECT"
                        detect_attempts = 0
                        detect_no_box_count = 0
                        yolo_scores = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
                        yolo_votes = {"clear": 0, "colored": 0, "opaque": 0}
                        yolo_conf_sum = {"clear": 0.0, "colored": 0.0, "opaque": 0.0}
                        vision_votes = {"colored": 0, "opaque": 0, "clear": 0}
                        best_box = self.last_bottle_box
                        best_yolo_conf = 0.0

                time.sleep(0.03)

            elif state == "DETECT":
                if has_serial_scale and self.current_weight > self.max_weight:
                    print(f"[AI Detector] Overweight detected during classification ({self.current_weight:.1f}g > {self.max_weight:.1f}g). Aborting.")
                    state = "WAIT_WEIGHT"
                    self.last_bottle_box = None
                    self.last_neck_box = None
                    self.last_base_box = None
                    self.last_decision = None
                    detect_attempts = 0
                    time.sleep(0.05)
                    continue

                detect_attempts += 1
                h, w = frame.shape[:2]
                
                # ------------------------------------------------------------------
                # สแกนตรวจจับขวดในบริเวณห้องรับขวด
                # ------------------------------------------------------------------
                crop_y1, crop_y2 = int(h * 0.05), int(h * 0.95)
                crop_x1, crop_x2 = int(w * 0.15), int(w * 0.85)
                chamber_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

                current_frame_box, best_conf, src_name, dbg_boxes, custom_scores = self._detect_bottle_box(chamber_crop, crop_x1, crop_y1)

                if current_frame_box is not None:
                    self.last_bottle_box = current_frame_box
                    best_box = current_frame_box
                    detect_no_box_count = 0
                else:
                    current_frame_box = self.last_bottle_box or best_box

                # อัปเดตคะแนน custom model ที่ตรวจพบจากเฟรมเต็ม
                for c_k, c_v in custom_scores.items():
                    yolo_scores[c_k] = max(yolo_scores.get(c_k, 0.0), c_v)

                frame_winner_cls = None
                frame_winner_conf = 0.0
                frame_boxes_dbg = []
                skin_ratio = 0.0

                if current_frame_box is not None:
                    # 1) ตรวจสอบว่าโมเดลตรวจจับเป็นคลาสใดในเฟรมนี้
                    for c_k, c_v in custom_scores.items():
                        if c_v > frame_winner_conf:
                            frame_winner_conf = c_v
                            frame_winner_cls = c_k

                    loc_src = src_name
                    loc_conf = best_conf
                    if loc_src in classes:
                        yolo_scores[loc_src] = max(yolo_scores.get(loc_src, 0.0), loc_conf)
                        if loc_conf > best_yolo_conf:
                            best_yolo_conf = loc_conf
                        if loc_conf > frame_winner_conf:
                            frame_winner_conf = loc_conf
                            frame_winner_cls = loc_src

                    # 2) ตัดภาพเฉพาะตัวขวด (Crop Bottle Body) ส่งให้ Custom Model จำแนกประเภท
                    bx1, by1, bx2, by2 = [int(v) for v in current_frame_box]
                    bx1 = max(0, min(w - 1, bx1))
                    by1 = max(0, min(h - 1, by1))
                    bx2 = max(bx1 + 1, min(w, bx2))
                    by2 = max(by1 + 1, min(h, by2))
                    bottle_crop = frame[by1:by2, bx1:bx2]

                    if bottle_crop.shape[0] >= 30 and bottle_crop.shape[1] >= 20:
                        try:
                            crop_res = self.model.predict(bottle_crop, conf=0.15, imgsz=480, verbose=False)
                            if crop_res and len(crop_res) > 0 and crop_res[0].boxes is not None:
                                for b in crop_res[0].boxes:
                                    c_id = int(b.cls[0])
                                    c_name = self.model.names[c_id]
                                    c_conf = float(b.conf[0])
                                    if c_name in classes:
                                        yolo_scores[c_name] = max(yolo_scores.get(c_name, 0.0), c_conf)
                                        if c_conf > best_yolo_conf:
                                            best_yolo_conf = c_conf
                                        if c_conf > frame_winner_conf:
                                            frame_winner_conf = c_conf
                                            frame_winner_cls = c_name
                                        frame_boxes_dbg.append(f"crop_{c_name}:{c_conf:.2f}")
                        except Exception as e:
                            pass

                    # บันทึกผลโหวตและคะแนนสะสมของเฟรมนี้
                    min_conf = 0.15
                    if frame_winner_cls and frame_winner_conf >= min_conf:
                        yolo_votes[frame_winner_cls] = yolo_votes.get(frame_winner_cls, 0) + 1
                        yolo_conf_sum[frame_winner_cls] = yolo_conf_sum.get(frame_winner_cls, 0.0) + frame_winner_conf
                else:
                    detect_no_box_count += 1
                    # ถ้าขวดหายไประหว่าง detect (เช่น ดึงขวดออก) เกิน 6 เฟรม ให้ยกเลิกการแยกขวดทันที
                    if detect_no_box_count >= 6:
                        print(f"[AI Classifier] Bottle disappeared during classification. Canceling sorting.")
                        state = "WAIT_WEIGHT"
                        self.last_bottle_box = None
                        self.last_neck_box = None
                        self.last_base_box = None
                        self.last_decision = None
                        time.sleep(0.04)
                        continue

                self.last_yolo_scores = yolo_scores.copy()
                self.last_skin_ratio = skin_ratio

                # 3) รัน Computer Vision วิเคราะห์สีและเนื้อพลาสติกคอขวด (Neck & Shoulder ROI ไร้ฉลาก)
                vision_type = self._classify_by_vision(frame, current_frame_box or best_box)
                if vision_type in ("clear", "colored", "opaque"):
                    vision_votes[vision_type] = vision_votes.get(vision_type, 0) + 1

                print(f"[AI Classifier] Frame #{detect_attempts}: Win={frame_winner_cls}:{frame_winner_conf:.2f}, Vision={vision_type or 'neutral'}, YOLO_Votes={yolo_votes}, Vision_Votes={vision_votes}")

                # 4) เงื่อนไขการตัดสินใจ (Consensus Multi-Frame Voting):
                final_decision = None

                y_colored = yolo_scores.get("colored", 0.0)
                y_opaque = yolo_scores.get("opaque", 0.0)
                y_clear = yolo_scores.get("clear", 0.0)

                v_colored = vision_votes.get("colored", 0)
                v_opaque = vision_votes.get("opaque", 0)
                v_clear = vision_votes.get("clear", 0)

                yv_colored = yolo_votes.get("colored", 0)
                yv_opaque = yolo_votes.get("opaque", 0)
                yv_clear = yolo_votes.get("clear", 0)

                neck_metrics = self.last_vision_metrics or {}
                neck_is_clear = neck_metrics.get('neck_is_clear', False)
                neck_is_colored = neck_metrics.get('neck_is_colored', False)

                # ---------------------------------------------------------------------
                # 4) สถาปัตยกรรม YOLO-Dominant + Neck ROI Guardrail:
                # - YOLO เป็นผู้มีอำนาจตัดสินหลัก (Primary Decision Maker) สำหรับทุกคลาส
                # - แยก "ใส vs ขุ่น" (Clear vs Opaque) ด้วยโมเดล YOLO 100% ไร้การ Override จากแสงเงา
                # - Neck ROI ทำหน้าที่เฉพาะเจาะจง: คุ้มครองขวดชาเขียวฉลากผืนใหญ่ (Haru/Oishi sleeve)
                # ---------------------------------------------------------------------

                # ก) ทางลัดตัดสินเร็วในเฟรม 2 (Early Unanimous YOLO Exit):
                # หากโมเดล YOLO ตรวจพบเอกฉันท์ 2 เฟรมขึ้นไป ด้วยความมั่นใจสูง (conf >= 0.65)
                if detect_attempts >= 2 and frame_winner_cls and yolo_votes.get(frame_winner_cls, 0) >= 2 and frame_winner_conf >= 0.65:
                    if frame_winner_cls == "opaque":
                        final_decision = "opaque"
                        print(f"[AI Decision] YOLO high-confidence exit -> OPAQUE (conf={frame_winner_conf:.2f}, votes={yv_opaque})")
                    elif frame_winner_cls == "clear":
                        # ตรวจสอบ guardrail กรณีขวดนม HDPE สีขาวขุ่นทึบแสง (Diffuse Matte White)
                        if neck_metrics.get('is_diffuse_opaque', False) and not neck_metrics.get('is_transparent', True):
                            final_decision = "opaque"
                            print(f"[AI Decision] YOLO predicted clear ({frame_winner_conf:.2f}), but Optical Vision verified diffuse matte white HDPE -> OPAQUE (Meiji/Betagen milk protection)")
                        else:
                            final_decision = "clear"
                            print(f"[AI Decision] YOLO high-confidence exit -> CLEAR (conf={frame_winner_conf:.2f}, votes={yv_clear})")
                    elif frame_winner_cls == "colored":
                        # ตรวจสอบ Neck ROI Guardrail (กรณีฉลากชาเขียวผืนใหญ่คลุมขวดใส)
                        if neck_is_clear and not neck_is_colored:
                            final_decision = "clear"
                            print(f"[AI Decision] YOLO predicted colored ({frame_winner_conf:.2f}), but Neck ROI verified clear PET resin -> CLEAR (Haru/Oishi sleeve protection)")
                        else:
                            final_decision = "colored"
                            print(f"[AI Decision] YOLO high-confidence exit -> COLORED (conf={frame_winner_conf:.2f}, votes={yv_colored})")

                # ข) ตัดสินหลักเมื่อสะสมผลโหวตครบ 3 เฟรมขึ้นไป (YOLO Multi-Frame Consensus):
                if not final_decision and detect_attempts >= 3:
                    # จัดอันดับคลาสที่ได้คะแนนจาก YOLO สูงสุด
                    yolo_rank = [
                        ("clear", yv_clear, yolo_conf_sum.get("clear", 0.0)),
                        ("opaque", yv_opaque, yolo_conf_sum.get("opaque", 0.0)),
                        ("colored", yv_colored, yolo_conf_sum.get("colored", 0.0))
                    ]
                    # เรียงตามจำนวนโหวต YOLO ก่อน แล้วตามด้วยคะแนนความมั่นใจสะสม
                    yolo_rank.sort(key=lambda x: (x[1], x[2]), reverse=True)
                    top_cls, top_votes, top_conf = yolo_rank[0]

                    # เงื่อนไขชนะขาด: ได้คะแนนโหวตจาก YOLO อย่างน้อย 2 เฟรม และความมั่นใจสะสม >= 0.70
                    if top_votes >= 2 and top_conf >= 0.70:
                        if top_cls == "opaque":
                            final_decision = "opaque"
                            print(f"[AI Decision] YOLO consensus -> OPAQUE (votes={top_votes}, conf_sum={top_conf:.2f})")
                        elif top_cls == "clear":
                            # ตรวจสอบ guardrail กรณีขวดนม HDPE สีขาวขุ่นทึบแสง (Diffuse Matte White)
                            if neck_metrics.get('is_diffuse_opaque', False) and not neck_metrics.get('is_transparent', True):
                                final_decision = "opaque"
                                print(f"[AI Decision] YOLO consensus clear ({top_votes} votes), but Optical Vision verified diffuse matte white HDPE -> OPAQUE (Meiji/Betagen milk protection)")
                            else:
                                final_decision = "clear"
                                print(f"[AI Decision] YOLO consensus -> CLEAR (votes={top_votes}, conf_sum={top_conf:.2f})")
                        elif top_cls == "colored":
                            # ตรวจสอบ Neck ROI Guardrail สำหรับขวดฉลากใหญ่
                            if neck_is_clear and not neck_is_colored:
                                final_decision = "clear"
                                print(f"[AI Decision] YOLO consensus colored ({top_votes} votes), but Neck ROI verified clear PET resin -> CLEAR (Haru/Oishi sleeve protection)")
                            else:
                                final_decision = "colored"
                                print(f"[AI Decision] YOLO consensus -> COLORED (votes={top_votes}, conf_sum={top_conf:.2f})")

                # ค) Tiebreak และ Fallback สูงสุดที่ 5–6 เฟรม:
                if not final_decision and detect_attempts >= 5:
                    total_yolo_conf = sum(yolo_conf_sum.values())
                    # ป้องกันขวดทิพย์: หากไม่มีกรอบขวดจริง หรือคะแนนโมเดลต่ำมากโดยไม่มีขวด
                    if current_frame_box is None or (total_yolo_conf < 0.25 and best_yolo_conf < 0.30):
                        if detect_attempts >= 6:
                            print(f"[AI Decision] No confident bottle detected (total_yolo_conf={total_yolo_conf:.2f}). Rejecting phantom detection.")
                            state = "WAIT_WEIGHT"
                            self.last_bottle_box = None
                            self.last_neck_box = None
                            self.last_base_box = None
                            self.last_decision = None
                            detect_attempts = 0
                            time.sleep(0.04)
                            continue
                    else:
                        # ตัดสินตามคะแนนความมั่นใจสะสมสูงสุดของ YOLO (Pure Confidence Tiebreak)
                        conf_rank = [
                            ("clear", yolo_conf_sum.get("clear", 0.0)),
                            ("opaque", yolo_conf_sum.get("opaque", 0.0)),
                            ("colored", yolo_conf_sum.get("colored", 0.0))
                        ]
                        best_cand, best_cand_conf = max(conf_rank, key=lambda x: x[1])
                        if best_cand_conf >= 0.35:
                            if best_cand == "colored" and neck_is_clear and not neck_is_colored:
                                final_decision = "clear"
                                print(f"[AI Decision] Fallback winner colored ({best_cand_conf:.2f}), but Neck ROI verified clear PET resin -> CLEAR (Haru/Oishi sleeve protection)")
                            else:
                                final_decision = best_cand
                                print(f"[AI Decision] YOLO fallback winner -> {final_decision.upper()} (conf_sum={best_cand_conf:.2f})")
                        elif neck_metrics.get('is_diffuse_opaque', False) and v_opaque >= 2:
                            final_decision = "opaque"
                            print(f"[AI Decision] Fallback optical verification -> OPAQUE (diffuse white plastic detected)")
                        elif neck_is_clear and not neck_is_colored and v_clear >= 2:
                            final_decision = "clear"
                            print(f"[AI Decision] Fallback optical verification -> CLEAR (clear PET resin detected)")
                        else:
                            if detect_attempts >= 6:
                                print(f"[AI Decision] Max attempts reached with low score ({best_cand_conf:.2f}). Canceling sorting.")
                                state = "WAIT_WEIGHT"
                                self.last_bottle_box = None
                                self.last_neck_box = None
                                self.last_base_box = None
                                self.last_decision = None
                                detect_attempts = 0
                                time.sleep(0.04)
                                continue

                if final_decision:
                    self.last_decision = final_decision
                    try:
                        save_dir = os.path.join("Train", "dataset_captured")
                        os.makedirs(save_dir, exist_ok=True)
                        cv2.imwrite(os.path.join(save_dir, f"last_bottle_{final_decision}.jpg"), frame)
                    except Exception:
                        pass
                    db_bottle_type = "brown" if final_decision == "colored" else final_decision
                    if has_serial_scale:
                        final_weight = max(self.min_weight, self.current_weight)
                    else:
                        simulated_weights = {
                            "clear": 18.5,
                            "colored": 135.0,
                            "opaque": 35.0
                        }
                        final_weight = simulated_weights.get(final_decision, 18.5)
                        self.current_weight = final_weight

                    print(f"[AI DETECTED] Bottle: {db_bottle_type} (class={final_decision}, yolo={yolo_scores}, vision={vision_votes}), Weight: {final_weight:.1f}g")

                    if self.callback:
                        self.callback(db_bottle_type, final_weight, final_decision)

                    last_trigger_time = current_time
                    state = "WAIT_CLEAR"

                    # ปิดกล้องชั่วคราวระหว่างที่เซอร์โวกำลังหมุนหย่อนขวดลงถัง (ตัดปัญหาสัญญาณรบกวน EMI / ไฟกระชาก และเคลียร์ Frame Buffer)
                    if self.cap is not None:
                        try:
                            self.cap.release()
                        except:
                            pass
                        self.cap = None
                        with self._cam_frame_lock:
                            self._latest_raw_frame = None
                        print("[Camera Lifecycle] Camera released during sorting to isolate from motor electrical noise.")

                time.sleep(0.04)

            elif state == "WAIT_REMOVE":
                # รอยกวัตถุ/นิ้วออกจากตาชั่งก่อน จึงจะกลับไป Standby พร้อมรับขวดใหม่ได้ (ป้องกันการวนลูปซ้ำ)
                if not has_serial_scale or self.current_weight < self.min_weight:
                    print(f"[AI Detector] Scale cleared. Ready for next item.")
                    state = "WAIT_WEIGHT"
                    weight_start_time = 0.0
                    detect_attempts = 0
                time.sleep(0.08)

            if show_cam:
                overlay_text = f"State: {state} | W: {self.current_weight:.1f}g"
                cv2.putText(frame, overlay_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                box_to_draw = self.last_bottle_box or best_box
                if box_to_draw is not None:
                    bx1, by1, bx2, by2 = [int(v) for v in box_to_draw[:4]]
                    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                    cv2.putText(frame, "Bottle Shape", (bx1, max(15, by1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                if getattr(self, 'last_neck_box', None) is not None:
                    nx1, ny1, nx2, ny2 = self.last_neck_box
                    cv2.rectangle(frame, (nx1, ny1), (nx2, ny2), (0, 215, 255), 2)
                    cv2.putText(frame, "Neck ROI (No Label)", (nx1, max(15, ny1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 215, 255), 1)

                if getattr(self, 'last_base_box', None) is not None:
                    bx_b1, by_b1, bx_b2, by_b2 = self.last_base_box
                    cv2.rectangle(frame, (bx_b1, by_b1), (bx_b2, by_b2), (255, 0, 255), 1)

                cv2.imshow("BotteProject Camera Test (Q to quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        if show_cam:
            try:
                cv2.destroyAllWindows()
            except:
                pass

        if cap is not None:
            try:
                cap.release()
            except:
                pass
