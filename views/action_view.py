# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import threading
import flet as ft
from core.config import load_machine_config, save_machine_config, get_api_base, get_machine_id
from core.ui_utils import b_all, safe_set_icon, get_back_btn, show_alert
from services.detector_service import DetectorService

def render_action_view(page: ft.Page, router, e=None):
    API_BASE = get_api_base()
    MACHINE_ID = get_machine_id()
    import requests  # Lazy imported on action view

    page.controls.clear()
    
    # ตั้งค่าสถานะการโหลดข้อมูล loop
    page.is_polling = True
    page.session_bottles = []
    page.machine_rates = {}
    page.machine_allow = True
    
    # Helper สำหรับเปลี่ยนไอคอน Flet อย่างปลอดภัย (ป้องกัน .name พังใน Flet บางเวอร์ชัน)
    def safe_set_icon(ctrl, icon_val):
        if hasattr(ctrl, 'icon'):
            ctrl.icon = icon_val
        if hasattr(ctrl, 'name'):
            try:
                ctrl.name = icon_val
            except Exception:
                pass

    # ตรวจสอบและซิงค์โหมดการทำงาน (point หรือ money)
    cfg_disk = load_machine_config()
    current_type_str = cfg_disk.get("machine_type", "point")
    if hasattr(page, 'member_data'):
        s_type = page.member_data.get('machine_type') or page.member_data.get('type')
        if s_type:
            current_type_str = s_type
    current_type_str = getattr(page, 'machine_type', current_type_str)
    current_m_type = [current_type_str]
    page.machine_type = current_m_type[0]

    # โหลดเรทราคาเริ่มต้นจาก config ในเครื่องทันที (Zero-delay ไม่บล็อก UI)
    # Background worker (poll_machine_status) จะซิงค์เรทล่าสุดจากเซิร์ฟเวอร์ต่อให้ทันที
    r_pt = cfg_disk.get("rates", {}) if isinstance(cfg_disk.get("rates"), dict) else {}
    r_mn = cfg_disk.get("base_prices", {}) if isinstance(cfg_disk.get("base_prices"), dict) else {}
    all_r = {}
    all_r.update(r_pt)
    for k, v in r_mn.items():
        all_r[f"money_{k}"] = v
    if current_m_type[0] == "money":
        for k in ["clear", "opaque", "brown"]:
            val = r_mn.get(k, all_r.get(f"money_{k}"))
            if val is not None:
                all_r[k] = float(val) * 0.8
        if "brown" in all_r:
            all_r["colored"] = all_r["brown"]
    else:
        for k in ["clear", "opaque", "brown"]:
            val = r_pt.get(k)
            if val is not None:
                all_r[k] = float(val)
        if "brown" in all_r:
            all_r["colored"] = all_r["brown"]
    page.machine_rates = all_r

    # ตรวจสอบข้อมูลสมาชิกใน page
    if hasattr(page, 'member_data'):
        fname = page.member_data.get('fname', '')
        lname = page.member_data.get('lname', '')
        display_user = f"{fname} {lname}".strip() or "สมาชิก"
        if current_m_type[0] == "point":
            point_val = page.member_data.get('point', 0)
            try:
                display_point = f"{float(point_val):,.1f} แต้ม" if float(point_val) % 1 != 0 else f"{int(float(point_val))} แต้ม"
            except Exception:
                display_point = f"{point_val} แต้ม"
        else:
            bal_val = page.member_data.get('total_money', page.member_data.get('money', page.member_data.get('balance', 0.0)))
            try:
                display_point = f"{float(bal_val):,.2f} บาท"
            except Exception:
                display_point = f"{bal_val} บาท"
    else:
        display_user = "สมาชิกทั่วไป"
        display_point = "0 แต้ม" if current_m_type[0] == "point" else "0.00 บาท"
        
    user_reward_icon = ft.Icon(
        ft.icons.Icons.STARS if current_m_type[0] == "point" else ft.icons.Icons.PAYMENTS,
        size=14,
        color="#D97706" if current_m_type[0] == "point" else "#059669"
    )
    point_text_control = ft.Text(display_point, size=16, color="#48BB78", weight="bold")
        
    # Top App Bar (โลโก้ซ้าย + โปรไฟล์ขวา + สถานะเซนเซอร์และปุ่มรีเซ็ตด่วน)
    has_det = getattr(page, 'detector', None) is not None
    ai_icon = ft.Icon(
        ft.icons.Icons.CHECK_CIRCLE if has_det else ft.icons.Icons.AUTORENEW,
        size=14,
        color="#059669" if has_det else "#2563EB"
    )
    ai_status_text = ft.Text(
        "AI Sensor พร้อมทำงาน" if has_det else "กำลังเชื่อมต่อ AI...",
        size=12,
        color="#065F46" if has_det else "#1E40AF",
        weight="bold"
    )
    ai_status_badge = ft.Container(
        content=ft.Row([
            ai_icon,
            ai_status_text
        ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#D1FAE5" if has_det else "#DBEAFE",
        padding=ft.Padding(left=10, right=12, top=4, bottom=4),
        border_radius=12
    )

    def on_quick_tare(e):
        if getattr(page, 'detector', None):
            page.detector.tare_scale()
        detected_weight_value.value = "0.0 กรัม"
        detected_weight_value.color = "#6B7280"
        detected_type_value.value = "-"
        set_machine_status("idle", custom_msg="เซ็ตศูนย์ตาชั่งสำเร็จ (0.0g)", note="นำสิ่งของออกจากช่องรับ แล้วใส่ขวดใหม่อีกครั้ง")
        show_alert(page, "เซ็ตศูนย์ตราชั่งเรียบร้อยแล้ว (0.0g)", alert_type="success")

    def on_quick_cam_reset(e):
        if getattr(page, 'detector', None):
            set_machine_status("idle", custom_msg="กำลังเชื่อมต่อกล้องใหม่...", note="กรุณารอสักครู่ ระบบกำลังรีสตาร์ทกล้อง AI")
            def do_reconnect():
                ok = page.detector.reconnect_camera()
                msg = "✅ รีเซ็ตการเชื่อมต่อกล้องสำเร็จ พร้อมใช้งาน" if ok else "⚠️ ไม่สามารถเปิดกล้องได้ โปรดตรวจสายเชื่อมต่อกล้อง"
                show_alert(page, msg, alert_type="success" if ok else "error")
                set_machine_status("idle", custom_msg="รอรับขวด...", note="กล้องพร้อมทำงานแล้ว กรุณาใส่ขวดทีละขวด" if ok else "กล้องขัดข้อง โปรดตรวจสายกล้องหรือแจ้งเจ้าหน้าที่")
                try:
                    page.update()
                except Exception:
                    pass
            threading.Thread(target=do_reconnect, daemon=True).start()
        else:
            show_alert(page, "ไม่พบโมดูลกล้อง AI", alert_type="error")

    top_bar = ft.Container(
        content=ft.Row([
            # Logo & Status
            ft.Row([
                ft.Icon(ft.icons.Icons.AUTORENEW, size=28, color="#059669"),
                ft.Text("EcoCycle Pro", size=22, color="#064E3B", weight="bold"),
                ai_status_badge
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            # Profile Chip
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.Icons.PERSON, size=22, color="white"),
                        bgcolor="#059669", width=36, height=36, border_radius=18,
                        alignment=ft.Alignment(0, 0)
                    ),
                    ft.Column([
                        ft.Text(display_user, size=15, color="#064E3B", weight="bold"),
                        ft.Row([
                            user_reward_icon,
                            point_text_control,
                        ], spacing=3)
                    ], spacing=1)
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor="white",
                padding=ft.Padding(left=12, right=18, top=6, bottom=6),
                border_radius=25,
                border=ft.Border(
                    top=ft.BorderSide(1, "#E5E7EB"),
                    bottom=ft.BorderSide(1, "#E5E7EB"),
                    left=ft.BorderSide(1, "#E5E7EB"),
                    right=ft.BorderSide(1, "#E5E7EB")
                )
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        left=40, right=40, top=25
    )

    # ข้อความหัวข้อหลัก (ตรงกลางจอ)
    title_sub = ft.Text(
        "เครื่องกำลังตรวจจับประเภท ชั่งน้ำหนัก และคำนวณแต้มสะสมอัตโนมัติ..." if current_m_type[0] == "point" else "เครื่องกำลังตรวจจับประเภท ชั่งน้ำหนัก และคำนวณเงินสะสมอัตโนมัติ...",
        size=13,
        color="#4B5563"
    )
    title = ft.Column(
        [
            ft.Text("กรุณาใส่ขวดพลาสติกทีละขวด", size=26, color="#064E3B", weight="bold"),
            title_sub,
        ],
        spacing=3, horizontal_alignment="center"
    )

    # บล็อก 1 (ซ้ายสุด): กล่องแสดงสถานะการทำงาน / ตรวจจับขวดแบบ Real-time
    status_badge_icon = ft.Icon(ft.icons.Icons.HOURGLASS_EMPTY, size=15, color="#0284C7")
    status_badge_text = ft.Text("รอรับขวด...", size=12, color="#0284C7", weight="bold")
    status_badge_row = ft.Row([status_badge_icon, status_badge_text], spacing=5, alignment="center")
    status_badge_pill = ft.Container(
        content=status_badge_row,
        bgcolor="#E0F2FE",
        padding=ft.Padding(left=12, right=12, top=4, bottom=4),
        border_radius=10
    )

    detected_type_label = ft.Text("ประเภทขวด:", size=11, color="#4B5563")
    detected_type_value = ft.Text("-", size=12, color="#1F2937", weight="bold")
    detected_weight_label = ft.Text("น้ำหนักที่ชั่ง:", size=11, color="#4B5563")
    detected_weight_value = ft.Text("0.0 กรัม", size=12, color="#059669", weight="bold")

    bottle_info_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Row([ft.Icon(ft.icons.Icons.CATEGORY, size=14, color="#0284C7"), detected_type_label], spacing=4),
                detected_type_value
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([
                ft.Row([ft.Icon(ft.icons.Icons.SCALE, size=14, color="#059669"), detected_weight_label], spacing=4),
                detected_weight_value
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=4),
        bgcolor="#F8FAFC",
        padding=ft.Padding(left=10, right=10, top=6, bottom=6),
        border_radius=10,
        border=ft.Border(
            top=ft.BorderSide(1, "#E2E8F0"),
            bottom=ft.BorderSide(1, "#E2E8F0"),
            left=ft.BorderSide(1, "#E2E8F0"),
            right=ft.BorderSide(1, "#E2E8F0")
        ),
        width=255
    )

    status_note_text = ft.Text(
        "กรุณาใส่ขวดทีละขวดลงในช่องรับ",
        size=11,
        color="#6B7280",
        text_align=ft.TextAlign.CENTER
    )

    machine_status_box = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.Icons.PRECISION_MANUFACTURING, size=18, color="#0284C7"),
                    bgcolor="#E0F2FE", width=30, height=30, border_radius=15,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Text("สถานะการทำงาน", size=15, color="#064E3B", weight="bold")
            ], alignment="center", spacing=6),
            status_badge_pill,
            bottle_info_card,
            status_note_text,
        ], horizontal_alignment="center", spacing=5, alignment="center"),
        bgcolor="white",
        border_radius=20,
        border=ft.Border(
            top=ft.BorderSide(1, "#E5E7EB"),
            bottom=ft.BorderSide(1, "#E5E7EB"),
            left=ft.BorderSide(1, "#E5E7EB"),
            right=ft.BorderSide(1, "#E5E7EB")
        ),
        width=290, height=240,
        padding=ft.Padding(left=14, right=14, top=10, bottom=10),
    )

    def set_machine_status(state_mode, custom_msg=None, b_type=None, b_weight=None, note=None):
        if state_mode == "idle":
            status_badge_pill.bgcolor = "#E0F2FE"
            status_badge_row.controls[0] = ft.Icon(ft.icons.Icons.HOURGLASS_EMPTY, size=16, color="#0284C7")
            status_badge_text.value = custom_msg or "รอรับขวด..."
            status_badge_text.color = "#0284C7"
            detected_type_value.value = "-"
            detected_weight_value.value = "0.0 กรัม"
            detected_weight_value.color = "#6B7280"
            status_note_text.value = note or "กรุณาใส่ขวดทีละขวดลงในช่องรับ"
            status_note_text.color = "#6B7280"
        elif state_mode == "storing":
            status_badge_pill.bgcolor = "#FFEDD5"
            status_badge_row.controls[0] = ft.Icon(ft.icons.Icons.SYNC, size=16, color="#D97706")
            status_badge_text.value = custom_msg or "กำลังจัดเก็บขวด..."
            status_badge_text.color = "#D97706"
            if b_type:
                detected_type_value.value = b_type
            if b_weight is not None:
                detected_weight_value.value = f"{float(b_weight):.1f} กรัม"
                detected_weight_value.color = "#059669"
            status_note_text.value = note or "⚠️ ห้ามหยิบขวดออก! เครื่องกำลังลำเลียงขวด..."
            status_note_text.color = "#DC2626"
        elif state_mode == "stored":
            status_badge_pill.bgcolor = "#D1FAE5"
            status_badge_row.controls[0] = ft.Icon(ft.icons.Icons.CHECK_CIRCLE, size=16, color="#059669")
            status_badge_text.value = custom_msg or "จัดเก็บขวดเสร็จสิ้น"
            status_badge_text.color = "#059669"
            if b_type:
                detected_type_value.value = b_type
            if b_weight is not None:
                detected_weight_value.value = f"{float(b_weight):.1f} กรัม"
            default_note = "จัดเก็บลงถังเรียบร้อย บันทึกแต้มสำเร็จ!" if (current_m_type[0] == "point") else "จัดเก็บลงถังเรียบร้อย บันทึกยอดเงินสำเร็จ!"
            status_note_text.value = note or default_note
            status_note_text.color = "#059669"
        elif state_mode in ("cheat", "error", "warning"):
            is_warn = (state_mode == "warning")
            status_badge_pill.bgcolor = "#FEF3C7" if is_warn else "#FEE2E2"
            status_badge_row.controls[0] = ft.Icon(ft.icons.Icons.WARNING_ROUNDED, size=16, color="#D97706" if is_warn else "#DC2626")
            status_badge_text.value = custom_msg or ("ตรวจไม่พบขวด" if is_warn else "ตรวจพบข้อผิดพลาด")
            status_badge_text.color = "#D97706" if is_warn else "#DC2626"
            status_note_text.value = note or "มีขวดถูกนำออก หรือน้ำหนักเกินเกณฑ์"
            status_note_text.color = "#B45309" if is_warn else "#DC2626"
        
        try:
            machine_status_box.update()
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    # บล็อก 2 (กลาง): กล่องแสดงจำนวนขวดสะสม
    bottle_count_text = ft.Text("0", size=48, color="#059669", weight="bold")
    bottle_count_sub = ft.Text("/ 10 ขวด", size=16, color="#9CA3AF", weight="bold")
    
    # จุดแสดงสถานะ 10 ช่อง (Visual Progress Dots)
    progress_dots = [
        ft.Container(width=12, height=12, border_radius=6, bgcolor="#E5E7EB")
        for _ in range(10)
    ]
    dots_row = ft.Row(progress_dots, alignment="center", spacing=5)

    session_reward_icon = ft.Icon(
        ft.icons.Icons.STARS if current_m_type[0] == "point" else ft.icons.Icons.PAYMENTS,
        size=15,
        color="#D97706" if current_m_type[0] == "point" else "#059669"
    )
    session_reward_label = ft.Text(
        "รอบนี้ได้รับ:" if current_m_type[0] == "point" else "รอบนี้ได้รับเงิน:",
        size=11,
        color="#78350F" if current_m_type[0] == "point" else "#065F46",
        weight="bold"
    )
    session_points_text = ft.Text(
        "+0.0 แต้ม" if current_m_type[0] == "point" else "+0.00 บาท",
        size=13,
        color="#D97706" if current_m_type[0] == "point" else "#059669",
        weight="bold"
    )
    session_points_pill = ft.Container(
        content=ft.Row([
            session_reward_icon,
            session_reward_label,
            session_points_text
        ], spacing=4, alignment="center"),
        bgcolor="#FEF3C7" if current_m_type[0] == "point" else "#D1FAE5",
        padding=ft.Padding(left=10, right=12, top=3, bottom=3),
        border_radius=10
    )

    bottle_count_box = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.Icons.LOCAL_DRINK, size=18, color="#059669"),
                    bgcolor="#E6FBF2", width=30, height=30, border_radius=15,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Text("จำนวนขวดที่รับแล้ว", size=15, color="#064E3B", weight="bold")
            ], alignment="center", spacing=6),
            ft.Row([bottle_count_text, bottle_count_sub], alignment="center", vertical_alignment="end"),
            dots_row,
            ft.Container(height=1),
            session_points_pill
        ], horizontal_alignment="center", spacing=5, alignment="center"),
        bgcolor="white",
        border_radius=20,
        border=ft.Border(
            top=ft.BorderSide(1, "#E5E7EB"),
            bottom=ft.BorderSide(1, "#E5E7EB"),
            left=ft.BorderSide(1, "#E5E7EB"),
            right=ft.BorderSide(1, "#E5E7EB")
        ),
        width=290, height=240,
        padding=ft.Padding(left=16, right=16, top=14, bottom=14),
    )

    def on_ui_update(topic):
        page.update()

    page.pubsub.subscribe(on_ui_update)

    # บล็อก 3 (ขวาสุด): คอนเทนเนอร์สำหรับปุ่มแลกรางวัล
    reward_btn_container = ft.Container()

    # จัดวางกล่อง 3 กล่องกึ่งกลางจออย่างสมดุล (กว้าง 290x3 + เว้น 16x2 = 902px พอดีจอ 1024px ไม่ล้นขอบ)
    cards_row = ft.Row(
        [machine_status_box, bottle_count_box, reward_btn_container],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=16
    )

    # แถบคำแนะนำประเภทขวดที่รับด้านล่าง
    def guide_chip(icon_name, name, desc_widget, color, bg):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon_name, size=15, color=color),
                    bgcolor=bg, width=26, height=26, border_radius=13,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Column([
                    ft.Text(name, size=11, color="#1F2937", weight="bold"),
                    desc_widget,
                ], spacing=1)
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="white",
            padding=ft.Padding(left=10, right=12, top=4, bottom=4),
            border_radius=10,
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            )
        )

    is_point_init = (current_m_type[0] == "point")
    r_c_init = page.machine_rates.get('clear', 1.2 if is_point_init else 0.008)
    r_b_init = page.machine_rates.get('brown', page.machine_rates.get('colored', 1.4 if is_point_init else 0.0112))
    r_o_init = page.machine_rates.get('opaque', 0.2 if is_point_init else 0.0008)

    clear_guide_desc = ft.Text(
        f"เรท {float(r_c_init):.1f} แต้ม/ก." if is_point_init else f"เรท {float(r_c_init):.4f} บ./ก.",
        size=10, color="#6B7280"
    )
    colored_guide_desc = ft.Text(
        f"เรท {float(r_b_init):.1f} แต้ม/ก." if is_point_init else f"เรท {float(r_b_init):.4f} บ./ก.",
        size=10, color="#6B7280"
    )
    opaque_guide_desc = ft.Text(
        f"เรท {float(r_o_init):.1f} แต้ม/ก." if is_point_init else f"เรท {float(r_o_init):.4f} บ./ก.",
        size=10, color="#6B7280"
    )
    materials_guide = ft.Row([
        guide_chip(ft.icons.Icons.WATER_DROP, "ขวดใส (Clear PET)", clear_guide_desc, "#0284C7", "#E0F2FE"),
        guide_chip(ft.icons.Icons.PALETTE, "ขวดสี (Colored PET)", colored_guide_desc, "#D97706", "#FEF3C7"),
        guide_chip(ft.icons.Icons.INVERT_COLORS, "ขวดขุ่น (Opaque HDPE)", opaque_guide_desc, "#4F46E5", "#EDE9FE"),
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=12)
    
    # แถบปุ่มช่วยเหลือและแคลิเบรตสำหรับผู้ใช้งานโดยตรง (User Self-Service Calibration Bar)
    user_tare_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.SCALE, size=18, color="white"),
            ft.Text("เซ็ตศูนย์ตาชั่ง (Tare 0g)", size=13, color="white", weight="bold"),
        ], spacing=6, alignment="center"),
        bgcolor="#059669",
        padding=ft.Padding(left=18, right=20, top=8, bottom=8),
        border_radius=12,
        border=ft.Border(
            top=ft.BorderSide(1.5, "#34D399"),
            bottom=ft.BorderSide(1.5, "#34D399"),
            left=ft.BorderSide(1.5, "#34D399"),
            right=ft.BorderSide(1.5, "#34D399")
        ),
        on_click=on_quick_tare,
        tooltip="กดเมื่อน้ำหนักค้างหรือไม่ตรง เพื่อเซ็ตศูนย์เป็น 0.0 กรัม ทันที"
    )

    user_cam_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.CAMERASWITCH, size=18, color="white"),
            ft.Text("รีเซ็ตกล้อง AI", size=13, color="white", weight="bold"),
        ], spacing=6, alignment="center"),
        bgcolor="#2563EB",
        padding=ft.Padding(left=18, right=20, top=8, bottom=8),
        border_radius=12,
        border=ft.Border(
            top=ft.BorderSide(1.5, "#60A5FA"),
            bottom=ft.BorderSide(1.5, "#60A5FA"),
            left=ft.BorderSide(1.5, "#60A5FA"),
            right=ft.BorderSide(1.5, "#60A5FA")
        ),
        on_click=on_quick_cam_reset,
        tooltip="กดเมื่อภาพกล้องค้าง เพื่อเชื่อมต่อกล้องใหม่ทันที"
    )

    user_troubleshoot_bar = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.Icons.HELP_OUTLINE, size=16, color="#4B5563"),
                ft.Text("พบปัญหาน้ำหนักค้างหรือกล้องไม่ขยับ?", size=12, color="#374151", weight="bold"),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            user_tare_btn,
            user_cam_btn
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#F3F4F6",
        padding=ft.Padding(left=18, right=18, top=6, bottom=6),
        border_radius=16,
        border=ft.Border(
            top=ft.BorderSide(1, "#E5E7EB"),
            bottom=ft.BorderSide(1, "#E5E7EB"),
            left=ft.BorderSide(1, "#E5E7EB"),
            right=ft.BorderSide(1, "#E5E7EB")
        )
    )
    
    # กล่องเนื้อหาหลัก กึ่งกลางจอแบบ Responsive พอดีจอ 1024x600
    center_content = ft.Container(
        content=ft.Column([
            title,
            cards_row,
            user_troubleshoot_bar,
            materials_guide
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment="center", spacing=10),
        left=20, right=20, top=65, bottom=25,
        alignment=ft.Alignment(0, 0)
    )
    
    # ฟังก์ชันสร้างปุ่มเมนูขนาดใหญ่แบบ Card (ปรับขนาด 290x240 ให้สมส่วน)
    def modern_button(btn_title, desc, icon_name, on_click, is_active=True, pill_text="กดเพื่อรับแต้ม"):
        border_color = "#059669" if is_active else "#E53E3E"
        btn_bg = "#059669" if is_active else "#E53E3E"
        is_point = (current_m_type[0] == "point")
        icon_color = "#D97706" if (is_point and is_active) else ("#059669" if is_active else "#E53E3E")
        icon_bg = "#FEF3C7" if (is_point and is_active) else ("#D1FAE5" if is_active else "#FEE2E2")
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(icon_name, size=26, color=icon_color),
                    bgcolor=icon_bg,
                    width=48, height=48, border_radius=24,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Container(height=1),
                ft.Text(btn_title, size=18, color="#064E3B" if is_active else "#E53E3E", weight="bold"),
                ft.Text(desc, size=11, color="#6B7280"),
                ft.Container(height=3),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.CHECK_CIRCLE, size=15, color="white"),
                        ft.Text(pill_text, size=13, color="white", weight="bold")
                    ], alignment="center", spacing=5),
                    bgcolor=btn_bg,
                    padding=ft.Padding(left=16, right=16, top=6, bottom=6),
                    border_radius=10
                )
            ], horizontal_alignment="center", alignment="center", spacing=4),
            bgcolor="white",
            border=ft.Border(
                top=ft.BorderSide(2, border_color),
                bottom=ft.BorderSide(2, border_color),
                left=ft.BorderSide(2, border_color),
                right=ft.BorderSide(2, border_color)
            ),
            border_radius=20,
            width=290, height=240,
            padding=ft.Padding(left=16, right=16, top=14, bottom=14),
            on_click=on_click if is_active else None
        )

    storage_done_event = threading.Event()

    is_storing_lock = threading.Lock()
    is_storing_bottle = False
    current_cycle_counted = False
    current_cycle_bottle = None

    def trigger_bottle_counted():
        nonlocal current_cycle_counted, current_cycle_bottle
        if current_cycle_counted or not current_cycle_bottle:
            return False

        current_cycle_counted = True
        b_info = current_cycle_bottle
        b_data = b_info["data"]

        page.session_bottles.append(b_data)
        bottle_count_text.value = str(len(page.session_bottles))
        current_earned = sum(float(b.get("earned", 0.0)) for b in page.session_bottles)
        is_point = (current_m_type[0] == "point")

        if is_point:
            session_points_text.value = f"+{current_earned:.1f} แต้ม"
        else:
            session_points_text.value = f"+{current_earned:.2f} บาท"

        for i, dot in enumerate(progress_dots):
            dot.bgcolor = "#059669" if i < len(page.session_bottles) else "#E5E7EB"

        reward_suffix = "บันทึกแต้มสำเร็จ!" if is_point else "บันทึกยอดเงินสำเร็จ!"
        set_machine_status(
            "stored",
            custom_msg="จัดเก็บลงถังสำเร็จ",
            b_type=b_info["display_type"],
            b_weight=b_info["weight"],
            note=f"✓ เซนเซอร์ IR ยืนยันขวดลงถังเรียบร้อย {reward_suffix}"
        )

        try:
            bottle_count_text.update()
            session_points_text.update()
            dots_row.update()
            bottle_count_box.update()
            page.update()
        except Exception:
            pass

        unit_str = "pts" if is_point else "บาท"
        val_fmt = f"{b_data['earned']:.1f}" if is_point else f"{b_data['earned']:.2f}"
        print(f"[BIN IR DROP VERIFIED] Bottle #{len(page.session_bottles)} confirmed in bin! ({b_data['type']}, {b_data['weight']}g) -> +{val_fmt} {unit_str}")
        return True

    def handle_bottle_detected(bottle_type, weight, original_class):
        nonlocal is_storing_bottle, current_cycle_counted, current_cycle_bottle
        if len(page.session_bottles) >= 10:
            return

        with is_storing_lock:
            if is_storing_bottle:
                print("[UI IGNORE] Already storing previous bottle, ignoring trigger.")
                return

            now = time.time()
            if now - getattr(page, '_last_bottle_detected_time', 0.0) < 2.5:
                print("[UI DEBOUNCE] Ignored duplicate bottle event within 2.5s")
                return
            page._last_bottle_detected_time = now
            is_storing_bottle = True
            current_cycle_counted = False
            storage_done_event.clear()
            if getattr(page, 'detector', None):
                page.detector.is_paused = True

        print(f"Bottle detected: {bottle_type}, weight: {weight}")

        type_th_map = {
            "clear": "ขวดใส (Clear PET)",
            "colored": "ขวดสี (Colored PET)",
            "brown": "ขวดสี (Colored PET)",
            "opaque": "ขวดขุ่น (Opaque HDPE)"
        }
        display_type = type_th_map.get(bottle_type, bottle_type)

        db_bottle_type = "brown" if bottle_type == "colored" else bottle_type
        is_point = (current_m_type[0] == "point")
        if is_point:
            rate_val = float(page.machine_rates.get(db_bottle_type, 1.2 if db_bottle_type == 'clear' else (0.2 if db_bottle_type == 'opaque' else 1.4)))
        else:
            rate_val = float(page.machine_rates.get(db_bottle_type, page.machine_rates.get(f"money_{db_bottle_type}", 0.008 if db_bottle_type == 'clear' else (0.0008 if db_bottle_type == 'opaque' else 0.0112))))
        earned_reward = float(weight) * float(rate_val)

        bottle_data = {
            "type": db_bottle_type,
            "weight": weight,
            "earned": earned_reward
        }

        with is_storing_lock:
            current_cycle_bottle = {
                "data": bottle_data,
                "display_type": display_type,
                "weight": weight,
                "bottle_type": bottle_type,
                "earned": earned_reward
            }

        # ขั้นที่ 1: บล็อก 1 อัปเดตทันที "กำลังจัดเก็บขวด..." พร้อมเตือนห้ามหยิบออก (บล็อก 2 ยังไม่นับ รอเซนเซอร์ IR ยืนยัน!)
        set_machine_status(
            "storing",
            custom_msg="กำลังจัดเก็บขวด...",
            b_type=display_type,
            b_weight=weight,
            note="⚠️ ห้ามหยิบขวดออก! เครื่องกำลังลำเลียงขวดลงถัง..."
        )

        # ส่งข้อมูลชนิดขวดไปยัง ESP32 (ส่งครั้งเดียว ไม่ส่งวนลูปซ้ำ เพื่อไม่ให้ค้างในบัฟเฟอร์ ESP32)
        def send_type_to_esp(b_type):
            has_esp = getattr(page, 'detector', None) and getattr(page.detector, 'ser', None) and page.detector.ser.is_open
            if not has_esp:
                return
            if getattr(page, 'detector', None):
                page.detector.send_to_esp32(f"TYPE:{b_type}\n")

        threading.Thread(target=send_type_to_esp, args=(bottle_type,), daemon=True).start()

        # เล่นเสียงแจ้งเตือนภาษาไทย
        audio_path = os.path.abspath(f"sound/type_bottle_sound/{original_class}_th.mp3")
        if os.path.exists(audio_path):
            import platform
            if platform.system() == "Windows":
                import ctypes
                try:
                    ctypes.windll.winmm.mciSendStringW('close bot_audio', None, 0, None)
                    ctypes.windll.winmm.mciSendStringW(f'open "{audio_path}" type mpegvideo alias bot_audio', None, 0, None)
                    ctypes.windll.winmm.mciSendStringW('play bot_audio', None, 0, None)
                except Exception as e:
                    print("Audio play error:", e)
            else:
                import subprocess
                for player in [["mpg123", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], ["paplay"]]:
                    try:
                        subprocess.Popen(player + [audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
                    except Exception as e:
                        print("Audio play error:", e)

        # ขั้นที่ 2-4: ลำเลียงขวดใน Background Thread
        def process_storage_completion():
            nonlocal is_storing_bottle, current_cycle_counted, current_cycle_bottle
            try:
                has_esp = getattr(page, 'detector', None) and getattr(page.detector, 'ser', None) and page.detector.ser.is_open

                if not has_esp:
                    # โหมดจำลอง PC Standalone (ไม่มี ESP32 ต่ออยู่):
                    # สเต็ป 1: จำลอง Gate IR ตรวจพบขวดหลัง 0.8s
                    time.sleep(0.8)
                    set_machine_status(
                        "storing",
                        custom_msg="ขวดผ่านประตูแล้ว",
                        b_type=display_type,
                        b_weight=weight,
                        note="✓ ตรวจพบขวดผ่านประตู กำลังลำเลียงไปหย่อนลงถัง..."
                    )
                    # สเต็ป 2: จำลอง Bin Dropcheck IR ตรวจพบขวดลงถังจริงหลังอีก 0.8s (รวม 1.6s)
                    time.sleep(0.8)
                    with is_storing_lock:
                        if not current_cycle_counted:
                            trigger_bottle_counted()
                    time.sleep(0.4)
                    storage_done_event.set()
                else:
                    # มี ESP32 ต่ออยู่จริง: รอสัญญาณจัดเก็บเสร็จสิ้นจาก ESP32 (รอสูงสุด 16 วินาที)
                    storage_done_event.wait(timeout=16.0)

                # ตรวจสอบว่าเซนเซอร์ Bin Drop IR ยืนยันขวดลงถังจริงหรือไม่
                with is_storing_lock:
                    counted = current_cycle_counted

                is_point = (current_m_type[0] == "point")

                if not counted:
                    # หากเซนเซอร์ในถังไม่พบขวดตกผ่านช่อง (Dropcheck ล้มเหลว หรือ timeout)
                    print("[STORAGE WARNING] Bin Drop IR did not detect bottle drop! Bottle NOT counted.")
                    unit_name = "แต้ม" if is_point else "ยอดเงิน"
                    set_machine_status(
                        "warning",
                        custom_msg="ไม่พบขวดลงถัง",
                        b_type=display_type,
                        b_weight=weight,
                        note=f"⚠️ ตรวจไม่พบขวดตกผ่าน IR ถัง ระบบไม่นับ{unit_name}รอบนี้"
                    )
                    time.sleep(2.5)
                else:
                    # ตรวจสอบว่าครบ 10 ขวดหรือยัง ถ้าครบให้หยุดกล้องทันที
                    if len(page.session_bottles) >= 10:
                        print("Max 10 bottles reached for this session. Stopping AI.")
                        if getattr(page, 'detector', None):
                            page.detector.stop()
                        end_msg = "คุณใส่ขวดครบ 10 ขวดแล้ว กรุณากดรับแต้ม" if is_point else "คุณใส่ขวดครบ 10 ขวดแล้ว กรุณากดรับเงินสด"
                        show_alert(page, end_msg, alert_type="warning")
                        time.sleep(1.5)
                        idle_note = "กรุณากดปุ่มสะสมแต้มเพื่อจบรอบ" if is_point else "กรุณากดปุ่มรับเงินสดเพื่อจบรอบ"
                        set_machine_status("idle", custom_msg="ครบ 10 ขวดแล้ว", note=idle_note)
                        return

                    # แสดงผลสำเร็จ 1.5 วินาที แล้วรีเซ็ตบล็อก 1 เป็น "รอรับขวด..."
                    time.sleep(1.5)

                set_machine_status("idle")

            finally:
                with is_storing_lock:
                    is_storing_bottle = False
                    current_cycle_counted = False
                    current_cycle_bottle = None
                if getattr(page, 'detector', None):
                    page.detector.is_paused = False

        threading.Thread(target=process_storage_completion, daemon=True).start()

    def on_esp_status(msg):
        nonlocal is_storing_bottle, current_cycle_counted, current_cycle_bottle
        if not msg.lower().startswith("weight ="):
            print(f"[UI ESP Message] {msg}")

        # -------------------------------------------------------------
        # IR 1: GATE IR (IR detector ที่ประตู)
        # หน้าที่: ตรวจสอบว่าขวดถูกผลักผ่านประตูเครื่องเข้ามาแล้ว
        # ข้อความจาก ESP1: "IR detected = YES" หรือ "STATUS:GATE_IR:OK" หรือ "GATE_IR:OK"
        # **ข้อสำคัญ: ยังไม่นับขวด (+1) และยังไม่เพิ่มแต้ม/เงินตรงนี้! แค่อัปเดตสถานะ**
        # -------------------------------------------------------------
        is_gate_ir_ok = ("IR detected = YES" in msg) or ("GATE_IR:OK" in msg) or ("STATUS:GATE_IR:OK" in msg)
        is_gate_ir_fail = ("IR detected = NO" in msg) or ("GATE_IR:TIMEOUT" in msg) or ("STATUS:GATE_IR:TIMEOUT" in msg)

        if is_gate_ir_ok and is_storing_bottle and not current_cycle_counted:
            b_info = current_cycle_bottle
            set_machine_status(
                "storing",
                custom_msg="ขวดผ่านประตูแล้ว",
                b_type=b_info["display_type"] if b_info else None,
                b_weight=b_info["weight"] if b_info else None,
                note="✓ ตรวจพบขวดผ่านประตู กำลังลำเลียงไปหย่อนลงถัง..."
            )
        elif is_gate_ir_fail and is_storing_bottle and not current_cycle_counted:
            b_info = current_cycle_bottle
            set_machine_status(
                "warning",
                custom_msg="ขวดไม่ผ่านประตู",
                b_type=b_info["display_type"] if b_info else None,
                b_weight=b_info["weight"] if b_info else None,
                note="⚠️ เซนเซอร์ไม่พบขวดผ่านประตู ขวดอาจติดค้างหรือถูกนำออก"
            )

        # -------------------------------------------------------------
        # IR 2: BIN DROPCHECK IR (IR ที่ dropcheck ตรวจจับขวดลงถังจริง)
        # หน้าที่: ตรวจสอบว่าขวดตกลงไปในถังเก็บจริงแล้ว
        # ข้อความจาก ESP2/ESP3: "DROP_CHECK:สำเร็จ" หรือ "DROP:OK" หรือ "DROP=OK"
        # หรือ "SORT_DONE:" ที่ไม่ใช่ DROP=NONE / DROP=TIMEOUT
        # **ข้อสำคัญ: ตรงนี้นับขวด (+1) และเพิ่มแต้ม/เงิน สะสมทันที!**
        # -------------------------------------------------------------
        is_bin_drop_ok = ("DROP_CHECK:สำเร็จ" in msg) or ("DROP:OK" in msg) or ("DROP=OK" in msg) or (
            "SORT_DONE:" in msg and "DROP=NONE" not in msg and "DROP=ERROR" not in msg and "DROP=TIMEOUT" not in msg
        )
        is_bin_drop_fail = ("WARNING:DROP_NOT_DETECTED" in msg) or ("DROP_CHECK:ไม่สำเร็จ" in msg) or (
            "DROP=NONE" in msg
        )

        if is_bin_drop_ok and is_storing_bottle:
            with is_storing_lock:
                if not current_cycle_counted:
                    trigger_bottle_counted()

        elif is_bin_drop_fail and is_storing_bottle and not current_cycle_counted:
            b_info = current_cycle_bottle
            set_machine_status(
                "warning",
                custom_msg="ไม่พบขวดลงถัง",
                b_type=b_info["display_type"] if b_info else None,
                b_weight=b_info["weight"] if b_info else None,
                note="⚠️ ตรวจไม่พบขวดตกผ่าน IR ถัง ระบบไม่นับรายการนี้"
            )

        # -------------------------------------------------------------
        # สัญญาณสิ้นสุดรอบกลไก (STATUS:DONE หรือ SORT_DONE หรือ READY)
        # -------------------------------------------------------------
        if "STATUS:DONE" in msg or "SORT_DONE" in msg:
            # กรณีฉุกเฉิน fallback: หากมี DROP=OK แต่ด้วยเหตุใดๆ ยังไม่ถูกนับ
            if "DROP=OK" in msg and is_storing_bottle:
                with is_storing_lock:
                    if not current_cycle_counted:
                        trigger_bottle_counted()
            storage_done_event.set()

        elif "READY FOR NEXT BOTTLE" in msg or "LAMP:GREEN_READY" in msg:
            storage_done_event.set()

        elif "STATUS:FAULT_CLEARED" in msg:
            set_machine_status("idle", custom_msg="รอรับขวด...", note="กรุณาใส่ขวดทีละขวดลงในช่องรับ")
        elif "CHEAT_WEIGHT" in msg:
            set_machine_status("cheat", custom_msg="ตรวจพบน้ำหนักผิดปกติ!", note="⚠️ น้ำหนักเกินหรือมีการหยิบขวดออก ระบบยกเลิกรายการนี้")
        elif "STATUS:FAULT:" in msg:
            set_machine_status("error", custom_msg="กลไกขัดข้อง", note="กรุณาแจ้งเจ้าหน้าที่เพื่อตรวจสอบระบบ")

    # ส่งคำสั่งปลดล็อกข้อผิดพลาดและเซ็ตศูนย์ตาชั่ง (TARE) เฉพาะเมื่อไม่มีของวางค้างอยู่
    def init_esp_link():
        time.sleep(1.2)
        has_esp = getattr(page, 'detector', None) and getattr(page.detector, 'ser', None) and page.detector.ser.is_open
        if has_esp:
            print("[UI Init] Sending RESET_FAULT to ESP32...")
            page.detector.send_to_esp32("RESET_FAULT\n")
            time.sleep(0.3)
            cur_w = getattr(page.detector, 'current_weight', 0.0)
            if cur_w < 5.0:
                page.detector.send_to_esp32("TARE\n")
            else:
                print(f"[UI Init] Object already on scale ({cur_w:.1f}g), skipping startup TARE.")
        else:
            print("[UI Init] Standalone PC Mode: Running AI Detector without ESP32/Scale.")

    # เธรดอัปเดตตัวเลขน้ำหนักแบบ Real-time บนหน้าจอทันทีที่วางของลงบนตราชั่ง
    def live_weight_monitor():
        last_w = -1.0
        while getattr(page, 'is_polling', False):
            if getattr(page, 'detector', None) and not is_storing_bottle:
                cur_w = getattr(page.detector, 'current_weight', 0.0)
                if abs(cur_w - last_w) >= 0.2:
                    last_w = cur_w
                    detected_weight_value.value = f"{cur_w:.1f} กรัม"
                    detected_weight_value.color = "#059669" if cur_w >= 10.0 else "#6B7280"
                    if cur_w >= 10.0:
                        status_badge_text.value = "กำลังตรวจจับขวด..."
                        status_badge_pill.bgcolor = "#FEF3C7"
                        status_badge_text.color = "#D97706"
                        status_badge_row.controls[0] = ft.Icon(ft.icons.Icons.SEARCH, size=15, color="#D97706")
                    else:
                        status_badge_text.value = "รอรับขวด..."
                        status_badge_pill.bgcolor = "#E0F2FE"
                        status_badge_text.color = "#0284C7"
                        status_badge_row.controls[0] = ft.Icon(ft.icons.Icons.HOURGLASS_EMPTY, size=15, color="#0284C7")
                    try:
                        machine_status_box.update()
                    except:
                        pass
            time.sleep(0.15)

    def start_hardware_thread():
        if getattr(page, 'detector', None) is None:
            page.detector = DetectorService.get_detector()
        if getattr(page, 'detector', None) and getattr(page, 'is_polling', False):
            page.detector.on_esp_message = on_esp_status
            page.detector.callback = handle_bottle_detected
            page.detector.start()
            threading.Thread(target=init_esp_link, daemon=True).start()
            threading.Thread(target=live_weight_monitor, daemon=True).start()
            try:
                ai_icon.name = ft.icons.Icons.CHECK_CIRCLE
                ai_icon.color = "#059669"
                ai_status_text.value = "AI Sensor พร้อมทำงาน"
                ai_status_text.color = "#065F46"
                ai_status_badge.bgcolor = "#D1FAE5"
                ai_status_badge.update()
            except Exception:
                pass

    def handle_redeem(e):
        if is_storing_bottle:
            show_alert(page, "เครื่องกำลังจัดเก็บขวด กรุณารอสักครู่...", alert_type="warning")
            return

        if not page.session_bottles:
            show_alert(page, "คุณยังไม่ได้ใส่ขวดเลยครับ!", alert_type="error")
            return
            
        if hasattr(page, 'user_token'):
            headers = {"Authorization": f"Bearer {page.user_token}"}
            
            success = False
            res_data = {}
            total_earned = 0.0
            last_total_point = float(page.member_data.get('point', 0.0))
            last_total_money = float(page.member_data.get('total_money', page.member_data.get('money', page.member_data.get('balance', 0.0))))
            
            # เตรียมข้อมูลขวด (แปลง colored เป็น brown ให้ตรงกับฐานข้อมูลเซิร์ฟเวอร์)
            clean_bottles = []
            for b in page.session_bottles:
                bt = b.get("type", "clear")
                if bt == "colored":
                    bt = "brown"
                clean_bottles.append({"type": bt, "weight": float(b.get("weight", 1.0))})

            # ลอง batch_deposit ก่อน (ถ้าเซิร์ฟเวอร์รองรับ)
            try:
                payload = {"bottles": clean_bottles}
                res = requests.post(f"{API_BASE}/user/machines/{MACHINE_ID}/batch_deposit", json=payload, headers=headers, timeout=10)
                if res.status_code == 200:
                    res_data = res.json()
                    success = True
                elif res.status_code == 404:
                    # เซิร์ฟเวอร์หลักไม่มี batch_deposit -> ใช้วิธีวนลูปส่งทีละใบด้วย /deposit
                    print("batch_deposit not found (404), falling back to individual /deposit calls...")
                    all_bottles_ok = True
                    for b in clean_bottles:
                        single_payload = {"type": b["type"], "weight": b["weight"]}
                        s_res = requests.post(f"{API_BASE}/user/machines/{MACHINE_ID}/deposit", json=single_payload, headers=headers, timeout=5)
                        if s_res.status_code == 200:
                            s_data = s_res.json()
                            total_earned += float(s_data.get('data', {}).get('earned', 0.0))
                            last_total_point = float(s_data.get('data', {}).get('total_point', last_total_point))
                            last_total_money = float(s_data.get('data', {}).get('total_money', s_data.get('data', {}).get('money', s_data.get('data', {}).get('balance', last_total_money))))
                        else:
                            all_bottles_ok = False
                            print("Deposit error on bottle:", s_res.status_code, s_res.text)
                            break
                    
                    if all_bottles_ok:
                        success = True
                        res_data = {
                            "status": "success",
                            "message": f"รับขวดสำเร็จ! ({len(page.session_bottles)} ใบ)",
                            "data": {
                                "earned": total_earned,
                                "total_point": last_total_point,
                                "total_money": last_total_money
                            }
                        }
                    else:
                        res_data = {"message": "เกิดข้อผิดพลาดในการบันทึกบางขวด"}
                else:
                    print("Error from batch_deposit:", res.status_code, res.text)
            except Exception as ex:
                print("API Error on batch_deposit:", ex)
                # กรณีเชื่อมต่อ batch ไม่ได้ ให้ลองส่งเดี่ยว
                try:
                    all_bottles_ok = True
                    for b in clean_bottles:
                        single_payload = {"type": b["type"], "weight": b["weight"]}
                        s_res = requests.post(f"{API_BASE}/user/machines/{MACHINE_ID}/deposit", json=single_payload, headers=headers, timeout=5)
                        if s_res.status_code == 200:
                            s_data = s_res.json()
                            total_earned += float(s_data.get('data', {}).get('earned', 0.0))
                            last_total_point = float(s_data.get('data', {}).get('total_point', last_total_point))
                            last_total_money = float(s_data.get('data', {}).get('total_money', s_data.get('data', {}).get('money', s_data.get('data', {}).get('balance', last_total_money))))
                        else:
                            all_bottles_ok = False
                            break
                    if all_bottles_ok:
                        success = True
                        res_data = {
                            "status": "success",
                            "message": f"รับขวดสำเร็จ! ({len(page.session_bottles)} ใบ)",
                            "data": {
                                "earned": total_earned,
                                "total_point": last_total_point,
                                "total_money": last_total_money
                            }
                        }
                except Exception as inner_ex:
                    print("Fallback deposit exception:", inner_ex)

            if success:
                is_point = (current_m_type[0] == "point")
                default_msg = "รับแต้มสำเร็จ!" if is_point else "รับเงินสดสำเร็จ!"
                show_alert(page, res_data.get('message', default_msg), alert_type="success")
                page.session_bottles = []
                bottle_count_text.value = "0"
                session_points_text.value = "+0.0 แต้ม" if is_point else "+0.00 บาท"
                for dot in progress_dots:
                    dot.bgcolor = "#E5E7EB"
                
                # รีเซ็ตสถานะบล็อก 1 เป็นรอรับขวด
                set_machine_status("idle")

                # อัปเดตแต้ม/ยอดเงินล่าสุดใน UI ทันที
                if 'data' in res_data:
                    d = res_data['data']
                    if is_point:
                        if 'total_point' in d:
                            new_point = d['total_point']
                            page.member_data['point'] = new_point
                            try:
                                point_text_control.value = f"{float(new_point):,.1f} แต้ม" if float(new_point) % 1 != 0 else f"{int(float(new_point))} แต้ม"
                            except Exception:
                                point_text_control.value = f"{new_point} แต้ม"
                    else:
                        new_bal = d.get('total_money', d.get('money', d.get('balance', d.get('total_point', None))))
                        if new_bal is not None:
                            page.member_data['money'] = new_bal
                            page.member_data['total_money'] = new_bal
                            page.member_data['balance'] = new_bal
                            try:
                                point_text_control.value = f"{float(new_bal):,.2f} บาท"
                            except Exception:
                                point_text_control.value = f"{new_bal} บาท"
                    
                # แลกแต้มเสร็จแล้ว เริ่ม AI ใหม่อีกครั้งเพื่อรับรอบต่อไป
                if getattr(page, 'detector', None):
                    page.detector.start()
            else:
                error_msg = res_data.get('message', "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้")
                show_alert(page, error_msg, alert_type="error")
        page.update()

    # สร้างปุ่มรับแต้ม/รับเงินสดเริ่มต้น
    btn_init_title = "สะสมแต้ม" if current_m_type[0] == "point" else "รับเงินสด"
    btn_init_desc = "รับแต้มพิเศษเข้าบัญชี" if current_m_type[0] == "point" else "รับเงินสดเข้าบัญชี/สแกนรับเงิน"
    btn_init_icon = ft.icons.Icons.STARS if current_m_type[0] == "point" else ft.icons.Icons.PAYMENTS
    btn_init_pill = "กดเพื่อรับแต้ม" if current_m_type[0] == "point" else "กดเพื่อรับเงิน"
    reward_btn = modern_button(btn_init_title, btn_init_desc, btn_init_icon, handle_redeem, is_active=True, pill_text=btn_init_pill)
    reward_btn_container.content = reward_btn

    def update_ui_for_mode(m_type):
        current_m_type[0] = m_type
        page.machine_type = m_type
        is_point = (m_type == "point")

        # 1. หัวข้อรอง
        title_sub.value = (
            "เครื่องกำลังตรวจจับประเภท ชั่งน้ำหนัก และคำนวณแต้มสะสมอัตโนมัติ..."
            if is_point else
            "เครื่องกำลังตรวจจับประเภท ชั่งน้ำหนัก และคำนวณเงินสะสมอัตโนมัติ..."
        )

        # 2. ข้อมูลโปรไฟล์มุมบนขวา
        if hasattr(page, 'member_data'):
            if is_point:
                p = page.member_data.get('point', 0)
                try:
                    disp = f"{float(p):,.1f} แต้ม" if float(p) % 1 != 0 else f"{int(float(p))} แต้ม"
                except Exception:
                    disp = f"{p} แต้ม"
                safe_set_icon(user_reward_icon, ft.icons.Icons.STARS)
                user_reward_icon.color = "#D97706"
                point_text_control.value = disp
            else:
                bal = page.member_data.get('total_money', page.member_data.get('money', page.member_data.get('balance', 0.0)))
                try:
                    disp = f"{float(bal):,.2f} บาท"
                except Exception:
                    disp = f"{bal} บาท"
                safe_set_icon(user_reward_icon, ft.icons.Icons.PAYMENTS)
                user_reward_icon.color = "#059669"
                point_text_control.value = disp

        # 3. กล่องยอดสะสมรอบนี้
        current_earned = sum(float(b.get("earned", 0.0)) for b in page.session_bottles)
        if is_point:
            session_points_pill.bgcolor = "#FEF3C7"
            safe_set_icon(session_reward_icon, ft.icons.Icons.STARS)
            session_reward_icon.color = "#D97706"
            session_reward_label.value = "รอบนี้ได้รับ:"
            session_reward_label.color = "#78350F"
            session_points_text.value = f"+{current_earned:.1f} แต้ม"
            session_points_text.color = "#D97706"
        else:
            session_points_pill.bgcolor = "#D1FAE5"
            safe_set_icon(session_reward_icon, ft.icons.Icons.PAYMENTS)
            session_reward_icon.color = "#059669"
            session_reward_label.value = "รอบนี้ได้รับเงิน:"
            session_reward_label.color = "#065F46"
            session_points_text.value = f"+{current_earned:.2f} บาท"
            session_points_text.color = "#059669"

        # 4. ปุ่มกดแลกแต้ม/รับเงิน
        btn_icon_container = reward_btn.content.controls[0]
        btn_icon_ctrl = btn_icon_container.content
        btn_title_ctrl = reward_btn.content.controls[2]
        btn_desc_ctrl = reward_btn.content.controls[3]
        btn_pill_box = reward_btn.content.controls[5]
        btn_pill_text = btn_pill_box.content.controls[1]

        allow = getattr(page, 'machine_allow', True)
        if allow:
            if is_point:
                safe_set_icon(btn_icon_ctrl, ft.icons.Icons.STARS)
                btn_icon_ctrl.color = "#D97706"
                btn_icon_container.bgcolor = "#FEF3C7"
                btn_title_ctrl.value = "สะสมแต้ม"
                btn_desc_ctrl.value = "รับแต้มพิเศษเข้าบัญชี"
                btn_pill_text.value = "กดเพื่อรับแต้ม"
                btn_title_ctrl.color = "#064E3B"
            else:
                safe_set_icon(btn_icon_ctrl, ft.icons.Icons.PAYMENTS)
                btn_icon_ctrl.color = "#059669"
                btn_icon_container.bgcolor = "#D1FAE5"
                btn_title_ctrl.value = "รับเงินสด"
                btn_desc_ctrl.value = "รับเงินสดเข้าบัญชี/สแกนรับเงิน"
                btn_pill_text.value = "กดเพื่อรับเงิน"
                btn_title_ctrl.color = "#064E3B"
            reward_btn.on_click = handle_redeem
        else:
            btn_title_ctrl.value = "ปิดบริการ"
            btn_desc_ctrl.value = "ตู้ปิดรับขวดชั่วคราว"
            reward_btn.on_click = None
            btn_title_ctrl.color = "#E53E3E"

        # 5. คำอธิบายประเภทขวดด้านล่าง
        r_c = page.machine_rates.get('clear', 1.2 if is_point else 0.008)
        r_b = page.machine_rates.get('brown', page.machine_rates.get('colored', 1.4 if is_point else 0.0112))
        r_o = page.machine_rates.get('opaque', 0.2 if is_point else 0.0008)
        clear_guide_desc.value = f"เรท {float(r_c):.1f} แต้ม/ก." if is_point else f"เรท {float(r_c):.4f} บ./ก."
        colored_guide_desc.value = f"เรท {float(r_b):.1f} แต้ม/ก." if is_point else f"เรท {float(r_b):.4f} บ./ก."
        opaque_guide_desc.value = f"เรท {float(r_o):.1f} แต้ม/ก." if is_point else f"เรท {float(r_o):.4f} บ./ก."

        try:
            page.update()
        except Exception:
            pass
        
    def poll_machine_status():
        m_id = MACHINE_ID
        last_m_type = None
        last_allow = None
        auth_headers = {"Authorization": f"Bearer {page.user_token}"} if hasattr(page, 'user_token') else {}
        while getattr(page, 'is_polling', False):
            try:
                # ดึง config ของตู้จากเซิร์ฟเวอร์
                res = requests.get(f"{API_BASE}/operator/machines/{m_id}/config?t={time.time()}", headers=auth_headers, timeout=3)
                if res.status_code in (401, 404):
                    res = requests.get(f"{API_BASE}/user/machines/{m_id}/status?t={time.time()}", headers=auth_headers, timeout=3)

                if res.status_code == 200:
                    res_data = res.json()
                    if res_data.get('status') == 'success':
                        m_data = res_data['data']
                        count = m_data.get('count', 0)
                        m_type = m_data.get('type', getattr(page, 'machine_type', 'point'))
                        allow = m_data.get('allow', True)
                        
                        # ดึงเรททั้งสองแบบจากฐานข้อมูล
                        r_pt = m_data.get('rates', {}) if isinstance(m_data.get('rates'), dict) else {}
                        r_bp = m_data.get('base_prices', {}) if isinstance(m_data.get('base_prices'), dict) else {}
                        
                        all_rates = {}
                        all_rates.update(r_pt)
                        for k, v in r_bp.items():
                            all_rates[f"money_{k}"] = v

                        if m_type == "money":
                            # โหมดเงินสด: คำนวณตามสูตรเซิร์ฟเวอร์ base_prices * 0.8
                            for k in ["clear", "opaque", "brown"]:
                                val = r_bp.get(k, all_rates.get(f"money_{k}"))
                                if val is not None:
                                    all_rates[k] = float(val) * 0.8
                            if "brown" in all_rates:
                                all_rates["colored"] = all_rates["brown"]
                            if "colored" in all_rates:
                                all_rates["brown"] = all_rates["colored"]
                        else:
                            # โหมดแต้ม: ใช้ point rates
                            for k in ["clear", "opaque", "brown"]:
                                val = r_pt.get(k)
                                if val is not None:
                                    all_rates[k] = float(val)
                            if "brown" in all_rates:
                                all_rates["colored"] = all_rates["brown"]
                            if "colored" in all_rates:
                                all_rates["brown"] = all_rates["colored"]

                        page.machine_rates = all_rates
                        page.machine_allow = allow
                        # อัปเดตตัวเลขแบบ Real-time ถ้ามีข้อมูลอื่นๆ
                        page.pubsub.send_all("update")
                        # อัปเดต UI เมื่อมีการเปลี่ยนแปลงโหมดหรือสิทธิ์
                        if m_type != last_m_type or allow != last_allow:
                            last_m_type = m_type
                            last_allow = allow
                            update_ui_for_mode(m_type)
            except Exception as ex:
                if "destroyed session" in str(ex).lower():
                    break  # โปรแกรมถูกปิดไปแล้ว ให้ออกจาก Loop เลย
                print(f"Polling Error: {ex}")
            time.sleep(0.5)

    def on_back(e):
        if is_storing_bottle:
            show_alert(page, "เครื่องกำลังจัดเก็บขวด กรุณารอสักครู่...", alert_type="warning")
            return

        if hasattr(page, 'session_bottles') and page.session_bottles and len(page.session_bottles) > 0:
            n_bottles = len(page.session_bottles)
            btn_title = "สะสมแต้ม" if current_m_type[0] == "point" else "รับเงินสด"

            def on_confirm_redeem(ev):
                if getattr(dlg, 'open', False):
                    dlg.open = False
                    page.update()
                handle_redeem(ev)

            def on_cancel_dlg(ev):
                dlg.open = False
                page.update()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.icons.Icons.WARNING_AMBER_ROUNDED, color="#DC2626", size=28),
                    ft.Text("มีขวดที่ยังไม่ได้กดรับแต้ม!", weight="bold", size=18, color="#DC2626")
                ], spacing=8),
                content=ft.Text(
                    f"คุณมีขวดที่ใส่ไว้แล้ว {n_bottles} ใบ\n"
                    f"กรุณากดปุ่ม '{btn_title}' เพื่อรับแต้มเข้าบัญชีก่อนย้อนกลับ\n"
                    f"(หากย้อนกลับตอนนี้ ข้อมูลขวดจะสูญหาย)",
                    size=15,
                    color="#374151"
                ),
                actions=[
                    ft.ElevatedButton(
                        f"กด{btn_title}ทันที",
                        bgcolor="#059669",
                        color="white",
                        on_click=on_confirm_redeem
                    ),
                    ft.TextButton("อยู่หน้านี้ต่อ", on_click=on_cancel_dlg)
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            page.dialog = dlg
            dlg.open = True

            show_alert(page, f"มีขวดค้างอยู่ {n_bottles} ใบ! กรุณากด{btn_title}ก่อนย้อนกลับ เพื่อไม่ให้แต้มสูญหาย", alert_type="error")
            return

        page.is_polling = False
        if getattr(page, 'detector', None):
            page.detector.stop()
            page.detector.on_esp_message = None
        router.go_home()

    back_btn = get_back_btn(on_back)

    action_stack = ft.Stack([top_bar, center_content, back_btn], expand=True)
    page.add(action_stack)
    page.update()
    
    threading.Thread(target=start_hardware_thread, daemon=True).start()
    threading.Thread(target=poll_machine_status, daemon=True).start()

