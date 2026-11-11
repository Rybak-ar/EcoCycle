import cv2
from ultralytics import YOLO
import edge_tts
import asyncio
import pygame
import os
import time

# Initialize audio mixer
pygame.mixer.init()
classes = ["colored", "clear", "opaque"]
thai_labels = {
    "colored": "ตรวจพบขวดสี",
    "clear": "ตรวจพบขวดใส",
    "opaque": "ตรวจพบขวดสีขุ่น"
}

# Generate audio files if they don't exist
async def setup_audio():
    # Ensure the directory exists
    os.makedirs("./sound/tpye_botton_sound", exist_ok=True)
    for c, th_text in thai_labels.items():
        filename = f"./sound/tpye_botton_sound/{c}_th.mp3"
        if not os.path.exists(filename):
            communicate = edge_tts.Communicate(th_text, "th-TH-PremwadeeNeural")
            await communicate.save(filename)

# Run the audio setup before opening the camera
asyncio.run(setup_audio())

model = YOLO(r"D:\bottleproject\app\bottle_model.pt")

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("Error")
    exit()

last_play_time = 0
cooldown = 2.0  # 2 seconds cooldown between sounds

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # เพิ่มค่าความมั่นใจ (Confidence Threshold) เพื่อกรองความผิดพลาด
    results = model.track(frame, persist=True, conf=0.6)

    # Extract labels from detections
    detected_classes = []
    if results[0].boxes is not None and len(results[0].boxes) > 0:
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            detected_classes.append(cls_name)

    # Play sound if an object is detected and cooldown has passed
    if detected_classes:
        target_class = detected_classes[0] # Grab the first detected object
        current_time = time.time()
        
        if current_time - last_play_time > cooldown:
            if target_class in classes:
                try:
                    pygame.mixer.music.load(f"./sound/tpye_botton_sound/{target_class}_th.mp3")
                    pygame.mixer.music.play()
                    last_play_time = current_time
                except Exception as e:
                    print(f"Could not play audio: {e}")

    annotated_frame = results[0].plot()

    cv2.imshow("YOLO & OpenCV Live Feed", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

