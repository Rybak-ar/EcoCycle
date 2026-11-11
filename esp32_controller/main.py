import machine
import time
import sys
import uselect
from hx711 import HX711

# ==========================================
# 1. การตั้งค่า Servo Motor (สำหรับคัดแยกขวด)
# ==========================================
SERVO_PIN = 18  # เปลี่ยนเลขขาตามที่คุณต่อจริง
servo = machine.PWM(machine.Pin(SERVO_PIN), freq=50)

def set_servo_angle(angle):
    # คำนวณค่า Duty Cycle สำหรับองศา 0-180
    # (ค่า 25-125 เป็นค่าโดยประมาณสำหรับ Servo ทั่วไปใน MicroPython ที่ freq=50)
    min_duty = 25
    max_duty = 125
    duty = int(min_duty + (angle / 180.0) * (max_duty - min_duty))
    servo.duty(duty)

# เริ่มต้นให้ Servo อยู่ที่จุดกึ่งกลาง (90 องศา)
set_servo_angle(90)


# ==========================================
# 2. การตั้งค่า Load Cell (HX711)
# ==========================================
LOADCELL_DOUT_PIN = 4   # ตามโค้ดต้นฉบับของคุณ
LOADCELL_SCK_PIN = 5    # ตามโค้ดต้นฉบับของคุณ

# สร้างออบเจ็กต์ HX711
hx = HX711(d_out=LOADCELL_DOUT_PIN, pd_sck=LOADCELL_SCK_PIN)

# อ่านค่าเริ่มต้นเพื่อเป็นจุด 0 (Tare)
# หมายเหตุ: ตอนเริ่มเปิดเครื่องต้องไม่มีของวางบนตราชั่ง
print("Calibrating...")
offset = hx.read()

# ค่าจากโค้ดของคุณ
scale_val = 409          # ค่าเดิม
correction = 1.25    # ตัวคูณชดเชย


# ==========================================
# 3. การเตรียมตัวรับข้อความผ่าน USB Serial
# ==========================================
poll_obj = uselect.poll()
poll_obj.register(sys.stdin, uselect.POLLIN)


print("ESP32 MicroPython Ready")
last_print = time.ticks_ms()

while True:
    # ----------------------------------------------------
    # ส่วนที่ 1: รับข้อความ (ชนิดขวด) จาก Raspberry Pi (Python)
    # ----------------------------------------------------
    poll_results = poll_obj.poll(0)
    if poll_results:
        # อ่านข้อความที่ส่งมา 1 บรรทัด
        line = sys.stdin.readline().strip()
        
        if line == "clear":
            print("Received Type: clear")
            set_servo_angle(45)   # หมุนปัดขวดใส
            time.sleep(2)
            set_servo_angle(90)   # กลับจุดเดิม
            
        elif line == "opaque":
            print("Received Type: opaque")
            set_servo_angle(135)  # หมุนปัดขวดขุ่น
            time.sleep(2)
            set_servo_angle(90)   # กลับจุดเดิม
            
        elif line in ("brown", "colored"):
            print("Received Type: colored")
            set_servo_angle(180)  # หมุนปัดขวดสี
            time.sleep(2)
            set_servo_angle(90)   # กลับจุดเดิม

    # ----------------------------------------------------
    # ส่วนที่ 2: อ่านน้ำหนักและส่งให้ Raspberry Pi (ทุกๆ 300ms)
    # ----------------------------------------------------
    if time.ticks_diff(time.ticks_ms(), last_print) > 100:
        try:
            raw = hx.read()
            weight = abs(raw - offset) / scale_val
            
            # ชดเชยการชั่งแนวเอียง
            weight = weight * correction
            
            # ลบค่าที่แกว่งเล็กน้อยเวลาไม่มีของวาง
            if weight < 2:
                weight = 0
                
            # พิมพ์ส่งให้ Raspberry Pi ตามรูปแบบที่คุณใช้
            print("Raw =", raw, "Weight =", round(weight, 1), "g")
            
        except Exception as e:
            pass # กันกรณีอ่านค่า HX711 พลาด
            
        last_print = time.ticks_ms()
        
    time.sleep(0.01)
