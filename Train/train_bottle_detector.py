# ==============================================================================
# Bottle Detector Training Script (YOLOv8)
# สำหรับเทรน AI ตรวจจับรูปทรงขวด (Bottle Shape Localization)
# ==============================================================================

import os
import shutil
from ultralytics import YOLO

def train():
    # 1. โหลด Base Model (แนะนำ yolov8n.pt หรือ yolov8s.pt เพื่อความเร็วบน Raspberry Pi 5)
    print("[1/4] Loading base YOLOv8 model...")
    model = YOLO("yolov8n.pt")

    # 2. เส้นทางไฟล์ dataset (สามารถดาวน์โหลดจาก Roboflow หรือเตรียมเองในรูปแบบ YOLO)
    # data.yaml ควรมีคลาส:
    # names: ['bottle']  (ถ้าต้องการเน้นจับรูปทรงขวดเดี่ยว แล้วใช้ Neck ROI แยกชนิด)
    # หรือ names: ['clear', 'colored', 'opaque']
    data_yaml_path = "bottle_detection-7/data.yaml"
    
    if not os.path.exists(data_yaml_path):
        print(f"Warning: {data_yaml_path} not found.")
        print("กรุณาดาวน์โหลด dataset จาก Roboflow หรือระบุ path ของ data.yaml ที่ถูกต้อง")
        return

    # 3. เริ่มเทรนโมเดล
    # สำคัญ: imgsz ต้องเป็น 640 เพื่อให้เก็บรายละเอียดเส้นขอบพลาสติกใสได้ชัดเจน
    print("[2/4] Starting training with imgsz=640...")
    results = model.train(
        data=data_yaml_path,
        epochs=100,
        imgsz=640,
        batch=16,
        device="0" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu",
        workers=2,
        name="bottle_detector_neck_roi",
        save=True
    )

    # 4. ประเมินผลความแม่นยำ (Validation)
    print("[3/4] Validating model...")
    metrics = model.val()
    print("Validation metrics:", metrics)

    # 5. คัดลอกโมเดล weights/best.pt ไปยัง app/bottle_model.pt
    best_pt = os.path.join("runs", "detect", "bottle_detector_neck_roi", "weights", "best.pt")
    if os.path.exists(best_pt):
        target_path = os.path.join("app", "bottle_model.pt")
        shutil.copy(best_pt, target_path)
        print(f"[4/4] Successfully updated production model at: {target_path}")

if __name__ == "__main__":
    train()
