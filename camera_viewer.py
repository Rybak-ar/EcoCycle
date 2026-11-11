#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
BotteProject - AI Camera & Vision HUD Viewer (camera_viewer.py)
==============================================================================
UI แสดงภาพสดจากกล้องพร้อมกรอบตรวจจับรูปทรงขวดและวิเคราะห์คอขวด (Neck & Shoulder ROI)
- ทำงานได้ทั้งแบบ Standalone (เปิดกล้องและรัน AI โดยตรง)
- หรือเชื่อมต่อกับ index.py (หาก index.py เปิดอยู่แล้ว จะดึง Stream ผ่าน Port 5000)
- หน้าต่าง Desktop GUI (OpenCV) + Web Dashboard ผ่าน Browser (http://localhost:5000)
==============================================================================
"""

import cv2
import numpy as np
import time
import os
import sys
import threading
import urllib.request
import json

from ai_detector import BottleDetector

def is_stream_active(url="http://127.0.0.1:5000/api/status"):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'BotteViewer'})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    print("=" * 65)
    print("   🍾 BOTTEPROJECT - AI CAMERA & VISION HUD VIEWER")
    print("=" * 65)

    os.makedirs("Train/dataset_captured", exist_ok=True)

    stream_url = "http://127.0.0.1:5000/stream.mjpg"
    status_url = "http://127.0.0.1:5000/api/status"
    snapshot_url = "http://127.0.0.1:5000/api/snapshot"

    client_mode = is_stream_active(status_url)
    detector = None

    if client_mode:
        print("[Mode] Detected existing BotteProject kiosk service (index.py) on port 5000.")
        print("[Mode] Connecting in Client/Monitor mode to avoid camera device conflict...")
    else:
        print("[Mode] Starting Standalone Camera & AI Detector engine...")
        detector = BottleDetector()
        detector.start()
        print("[Mode] Detector engine started.")

    print("\n" + "-" * 65)
    print(" 🌐 Web Browser Dashboard: http://localhost:5000")
    print("    (สามารถเปิดดูจากมือถือหรือโน้ตบุ๊กในวง Wi-Fi เดียวกันได้ทันที)")
    print(" ⌨️  Hotkeys in Camera Window:")
    print("    [T] -> ⚖️ เซ็ตศูนย์ตราชั่ง (Tare Scale to 0.0g)")
    print("    [C] -> 🎥 รีเซ็ตการเชื่อมต่อกล้อง (Reconnect Camera / Clear Buffer)")
    print("    [S] -> 📸 ถ่ายภาพบันทึก Dataset ลง Train/dataset_captured/")
    print("    [R] -> 🔄 หมุนภาพกล้องทีละ 90 องศา (0° / 90° / 180° / 270°)")
    print("    [Q] หรือ [ESC] -> ออกจากโปรแกรม")
    print("-" * 65 + "\n")

    window_name = "BotteProject - Camera & AI Vision HUD (Press Q to Exit)"
    headless = False

    last_snap_notice = ""
    snap_notice_time = 0.0

    # Stream reader for client mode
    cap_stream = None
    if client_mode:
        cap_stream = cv2.VideoCapture(stream_url)

    try:
        while True:
            frame = None
            telemetry = {}

            if detector is not None:
                frame = detector.get_annotated_frame()
                telemetry = detector.get_telemetry()
            elif cap_stream is not None:
                ret, frame = cap_stream.read()
                if not ret:
                    time.sleep(0.05)
                    continue
                try:
                    req = urllib.request.Request(status_url, headers={'User-Agent': 'BotteViewer'})
                    with urllib.request.urlopen(req, timeout=0.3) as resp:
                        telemetry = json.loads(resp.read().decode('utf-8'))
                except Exception:
                    pass

            if frame is None:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]

            # วาดแถบ Information Bar ด้านล่าง
            info_bar = frame.copy()
            cv2.rectangle(info_bar, (0, h - 45), (w, h), (15, 23, 42), -1)
            cv2.addWeighted(info_bar, 0.85, frame, 0.15, 0, frame)

            # Neck ROI metrics text
            metrics = telemetry.get('neck_metrics', {})
            amber_pct = (metrics.get('amber', 0.0) * 100)
            green_pct = (metrics.get('green', 0.0) * 100)
            opaque_pct = (metrics.get('opaque', 0.0) * 100)

            stats_str = f"Neck ROI: Amber:{amber_pct:.1f}% | Green:{green_pct:.1f}% | Opaque:{opaque_pct:.1f}%"
            cv2.putText(frame, stats_str, (15, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1)

            # Shortcut instructions & Rotation status
            curr_rot = telemetry.get('rotation', 270)
            guide_str = f"Rot: {curr_rot}° | [T] Tare | [C] Cam | [R] Rot | [S] Snap | [Q] Exit"
            cv2.putText(frame, guide_str, (w - 480, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (16, 185, 129), 1)

            # Flash snapshot / rotation confirmation
            if time.time() - snap_notice_time < 2.5:
                cv2.rectangle(frame, (10, 75), (w - 10, 115), (16, 185, 129), -1)
                cv2.putText(frame, last_snap_notice, (20, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

            if not headless:
                try:
                    cv2.imshow(window_name, frame)
                    key = cv2.waitKey(20) & 0xFF
                    if key in (ord('q'), ord('Q'), 27): # 'q' or ESC
                        print("\n[Camera Viewer] Exiting viewer...")
                        break
                    elif key in (ord('t'), ord('T')): # Tare scale
                        if detector is not None:
                            detector.tare_scale()
                        else:
                            try:
                                tare_url = "http://127.0.0.1:5000/api/tare"
                                req = urllib.request.Request(tare_url, headers={'User-Agent': 'BotteViewer'})
                                with urllib.request.urlopen(req, timeout=2.0) as resp:
                                    pass
                            except Exception as ex:
                                print(f"[Tare Error] {ex}")
                        last_snap_notice = "Scale Calibrated: Tared to 0.0g"
                        snap_notice_time = time.time()
                    elif key in (ord('c'), ord('C')): # Reconnect camera
                        if detector is not None:
                            detector.reconnect_camera()
                        else:
                            try:
                                cam_url = "http://127.0.0.1:5000/api/reconnect_camera"
                                req = urllib.request.Request(cam_url, headers={'User-Agent': 'BotteViewer'})
                                with urllib.request.urlopen(req, timeout=2.0) as resp:
                                    pass
                            except Exception as ex:
                                print(f"[Cam Reconnect Error] {ex}")
                        last_snap_notice = "Camera Reconnected: Buffer Cleared"
                        snap_notice_time = time.time()
                    elif key in (ord('r'), ord('R')): # Rotate 90 degrees
                        new_rot = 270
                        if detector is not None:
                            new_rot = detector.set_rotation((detector.camera_rotate + 90) % 360)
                        else:
                            try:
                                rotate_url = "http://127.0.0.1:5000/api/rotate"
                                req = urllib.request.Request(rotate_url, headers={'User-Agent': 'BotteViewer'})
                                with urllib.request.urlopen(req, timeout=2.0) as resp:
                                    res_data = json.loads(resp.read().decode('utf-8'))
                                    new_rot = res_data.get('rotation', 270)
                            except Exception as ex:
                                print(f"[Rotate Error] {ex}")
                        rot_names = {0: "0° (ปกติ)", 90: "90° (ตามเข็ม)", 180: "180° (กลับหัว)", 270: "270° (ทวนเข็ม)"}
                        last_snap_notice = f"Camera Rotated: {rot_names.get(new_rot, f'{new_rot}°')} [Saved to config]"
                        snap_notice_time = time.time()
                    elif key in (ord('s'), ord('S')): # Snapshot
                        saved_path = None
                        if detector is not None:
                            saved_path = detector.save_snapshot()
                        else:
                            try:
                                with urllib.request.urlopen(snapshot_url, timeout=2.0) as resp:
                                    res_data = json.loads(resp.read().decode('utf-8'))
                                    saved_path = res_data.get('path')
                            except Exception as ex:
                                print(f"[Snapshot Error] {ex}")

                        if saved_path:
                            last_snap_notice = f"Saved: {os.path.basename(saved_path)} -> Train/dataset_captured/"
                            snap_notice_time = time.time()
                except cv2.error as e:
                    print(f"\n[Camera Viewer] No display server detected (Headless mode): {e}")
                    print(f"[Camera Viewer] Live stream remains accessible at http://0.0.0.0:5000")
                    headless = True
            else:
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Camera Viewer] Interrupted by user.")
    finally:
        if not headless:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        if cap_stream is not None:
            cap_stream.release()
        if detector is not None:
            detector.stop()
        print("[Camera Viewer] Terminated cleanly.")

if __name__ == "__main__":
    main()
