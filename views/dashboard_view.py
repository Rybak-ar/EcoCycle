# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import threading
import flet as ft
from core.config import load_machine_config, save_machine_config, get_api_base, get_machine_id
from core.ui_utils import b_all, safe_set_icon, get_back_btn, show_alert

def render_dashboard_view(page: ft.Page, router, e=None):
    API_BASE = get_api_base()
    MACHINE_ID = get_machine_id()
    import requests  # Lazy imported on dashboard view

    page.controls.clear()

    def get_or_init_detector():
        if getattr(page, 'detector', None) is None:
            try:
                from services.detector_service import DetectorService
                page.detector = DetectorService.get_detector()
            except Exception as ex:
                print(f"[Dashboard] Warning: Could not initialize detector: {ex}")
        return getattr(page, 'detector', None)
    
    # ดึงโหมดปัจจุบันและเรทจากฐานข้อมูล
    cfg = load_machine_config()
    m_type = cfg.get("machine_type", getattr(page, "machine_type", "point"))
    db_rates = {"clear": 1.8, "opaque": 0.2, "brown": 1.4}
    money_rates = {"clear": 1.8, "opaque": 0.2, "brown": 1.4}
    serial_number_val = [cfg.get("serial_number", "1111111")]
    cfg_rates = cfg.get("rates", {})
    if isinstance(cfg_rates, dict) and cfg_rates:
        for k in ["clear", "opaque", "brown"]:
            if k in cfg_rates:
                db_rates[k] = float(cfg_rates[k])
            if f"money_{k}" in cfg_rates:
                money_rates[k] = float(cfg_rates[f"money_{k}"])
            elif m_type == "money" and k in cfg_rates:
                money_rates[k] = float(cfg_rates[k])

    # กำหนดเรทเริ่มต้นตามค่าจากเครื่องทันที (Instant Init)
    point_rates = {
        "clear": float(db_rates.get("clear", 1.8)),
        "opaque": float(db_rates.get("opaque", 0.2)),
        "brown": float(db_rates.get("brown", db_rates.get("colored", 1.4))),
    }

    current_type = [m_type]
    row_controls = {}
    
    # Handlers
    
    def save_settings(e):
        headers = {}
        if hasattr(page, 'staff_token'):
            headers['Authorization'] = f"Bearer {page.staff_token}"
            
        # 1. ซิงค์ค่าจาก TextField ทุกช่องที่เปิดแก้ไขอยู่ทันที (แม้ไม่ได้กดปุ่ม Save ประจำแถว)
        is_point = (current_type[0] == "point")
        current_dict = point_rates if is_point else money_rates
        for k, ctrl in row_controls.items():
            tf_ctrl = ctrl.get('tf')
            if tf_ctrl and tf_ctrl.value is not None:
                try:
                    v_str = str(tf_ctrl.value).strip()
                    if v_str != "":
                        v = float(v_str)
                        current_dict[k] = v
                        if ctrl.get('txt'):
                            ctrl['txt'].value = str(v)
                except ValueError:
                    pass
            if ctrl.get('tf'):
                ctrl['tf'].visible = False
            if ctrl.get('val_container'):
                ctrl['val_container'].visible = True
            if ctrl.get('edit_btn'):
                ctrl['edit_btn'].visible = True
            if ctrl.get('save_row_btn'):
                ctrl['save_row_btn'].visible = False

        # 2. เตรียม rates และ base_prices ให้ครบทุกประเภทวัสดุเสมอ
        # รองรับทั้ง brown และ colored และมีค่า fallback ครบถ้วน เพื่อป้องกัน Backend Error: กรุณาส่ง rates ให้ครบทุกประเภท
        brown_pt = float(point_rates.get("brown", point_rates.get("colored", db_rates.get("brown", 1.4))))
        clean_point_rates = {
            "clear": float(point_rates.get("clear", db_rates.get("clear", 1.8))),
            "brown": brown_pt,
            "colored": brown_pt,
            "opaque": float(point_rates.get("opaque", db_rates.get("opaque", 0.2)))
        }

        brown_mn = float(money_rates.get("brown", money_rates.get("colored", 1.4)))
        clean_money_rates = {
            "clear": float(money_rates.get("clear", 1.8)),
            "brown": brown_mn,
            "colored": brown_mn,
            "opaque": float(money_rates.get("opaque", 0.2))
        }

        # เลือกว่าเรทหลักของโหมดปัจจุบันคืออะไร (โหมดเงินสดใช้ clean_money_rates, โหมดแต้มใช้ clean_point_rates)
        if current_type[0] == "money":
            target_rates = clean_money_rates.copy()
        else:
            target_rates = clean_point_rates.copy()

        # ซิงค์ทั้งรูปแบบ key ปกติ และ key ที่ขึ้นต้นด้วย money_ เพื่อให้สอดคล้องกับ SQL tb_pointrate
        target_rates["money_clear"] = clean_money_rates["clear"]
        target_rates["money_brown"] = clean_money_rates["brown"]
        target_rates["money_colored"] = clean_money_rates["colored"]
        target_rates["money_opaque"] = clean_money_rates["opaque"]

        # ส่งทั้ง rates และ base_prices เสมอเพื่อให้ Backend ทุก endpoint/validation ผ่าน 100%
        payload = {
            "type": current_type[0],
            "rates": target_rates,
            "base_prices": clean_money_rates
        }
            
        try:
            # 1. พยายามบันทึกผ่าน PUT /operator/machines/{MACHINE_ID}/config
            response = None
            try:
                response = requests.put(f"{API_BASE}/operator/machines/{MACHINE_ID}/config", json=payload, headers=headers, timeout=5)
            except Exception as req_ex:
                print("PUT config error:", req_ex)

            # 2. ถ้าเซิร์ฟเวอร์ตอบกลับ 405 (Method Not Allowed) หรือตอบเป็น HTML (เช่น Apache shared host บล็อก PUT)
            if response is None or response.status_code == 405 or (response.status_code != 200 and "<html" in response.text.lower()):
                post_headers = headers.copy()
                post_headers['X-HTTP-Method-Override'] = 'PUT'
                payload_with_method = payload.copy()
                payload_with_method['_method'] = 'PUT'
                try:
                    response = requests.post(
                        f"{API_BASE}/operator/machines/{MACHINE_ID}/config?_method=PUT",
                        json=payload_with_method,
                        headers=post_headers,
                        timeout=5
                    )
                except Exception as req_ex2:
                    print("POST config error:", req_ex2)

            # 3. ถ้ายังไม่ได้ ลอง endpoint /machine/{MACHINE_ID}/config
            if response is None or response.status_code in (404, 405) or (response.status_code != 200 and "<html" in response.text.lower()):
                try:
                    response = requests.post(
                        f"{API_BASE}/machine/{MACHINE_ID}/config",
                        json=payload,
                        headers=headers,
                        timeout=5
                    )
                except Exception as req_ex3:
                    print("POST machine/config error:", req_ex3)

            # 4. ประเมินผลตอบกลับอย่างปลอดภัย (ป้องกัน JSONDecodeError เมื่อได้ HTML)
            if response is not None and response.status_code == 200:
                try:
                    res_json = response.json()
                    msg = res_json.get('message', 'บันทึกการตั้งค่าเรียบร้อยแล้ว')
                except Exception:
                    msg = "บันทึกการตั้งค่าเรียบร้อยแล้ว"
                # อัปเดตเรทและโหมดในหน่วยความจำของหน้าจอหลักทันที
                page.machine_type = current_type[0]
                save_machine_config({"machine_type": current_type[0]})
                all_r = {}
                all_r.update(clean_point_rates)
                for k, v in clean_money_rates.items():
                    all_r[f"money_{k}"] = v
                if current_type[0] == "money":
                    for k in ["clear", "opaque", "brown", "colored"]:
                        all_r[k] = clean_money_rates.get(k, 0.0)
                else:
                    for k in ["clear", "opaque", "brown", "colored"]:
                        all_r[k] = clean_point_rates.get(k, 0.0)
                page.machine_rates = all_r
                show_alert(page, msg, alert_type="success")
            elif response is not None:
                try:
                    res_json = response.json()
                    msg = res_json.get('message', f'เกิดข้อผิดพลาดในการบันทึก (HTTP {response.status_code})')
                except Exception:
                    msg = f"HTTP {response.status_code} ({response.reason or 'Server Error'})"
                show_alert(page, f"Error: {msg}", alert_type="error")
            else:
                show_alert(page, "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้", alert_type="error")
        except Exception as ex:
            show_alert(page, f"เกิดข้อผิดพลาด: {ex}", alert_type="error")

    def execute_toggle(e, dlg):
        dlg.open = False
        current_type[0] = "money" if current_type[0] == "point" else "point"
        render_dashboard()
        
    def close_dlg(e, dlg):
        dlg.open = False
        page.update()

    def toggle_type(e):
        target = "Money Mode (เงินสด)" if current_type[0] == "point" else "Point Mode (สะสมแต้ม)"
        dlg = ft.AlertDialog(
            title=ft.Text("ยืนยันการเปลี่ยนโหมด", size=24, weight="bold"),
            content=ft.Text(f"คุณต้องการเปลี่ยนตู้เป็น {target} ใช่หรือไม่?\n(โปรดตรวจสอบเรทราคาและกดบันทึกอีกครั้ง)", size=20),
            actions=[
                ft.TextButton("ยกเลิก", on_click=lambda e: close_dlg(e, dlg)),
                ft.TextButton("ยืนยัน", on_click=lambda e: execute_toggle(e, dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=20)
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # Card สำหรับ Material Conversion Rates
    def material_row(key, title, subtitle, icon_name=ft.icons.Icons.CATEGORY, icon_color="#059669", icon_bg="#E6FBF2"):
        is_point = (current_type[0] == "point")
        rates_dict = point_rates if is_point else money_rates
        unit = "pts / gram" if is_point else "baht / gram"
        val = str(rates_dict.get(key, 0.0))
        
        tf = ft.TextField(value=val, width=100, text_size=16, bgcolor="white", border_color="#E5E7EB", visible=False)
        txt = ft.Text(val, size=18, color="#064E3B", weight="bold")
        
        val_container = ft.Container(
            content=txt,
            bgcolor="white", border=ft.Border(top=ft.BorderSide(1, "#E5E7EB"), bottom=ft.BorderSide(1, "#E5E7EB"), left=ft.BorderSide(1, "#E5E7EB"), right=ft.BorderSide(1, "#E5E7EB")), border_radius=10,
            padding=ft.Padding(left=10, right=10, top=5, bottom=5), width=80, alignment=ft.Alignment(0,0)
        )

        edit_btn = ft.Container(content=ft.Row([ft.Icon(ft.icons.Icons.EDIT, size=14, color="#059669"), ft.Text("Edit", size=14, color="#059669", weight="bold")], spacing=5), padding=2)
        save_row_btn = ft.Container(content=ft.Row([ft.Icon(ft.icons.Icons.SAVE, size=14, color="#059669"), ft.Text("Save", size=14, color="#059669", weight="bold")], spacing=5), padding=2, visible=False)

        def edit_click(e):
            tf.visible = True
            val_container.visible = False
            edit_btn.visible = False
            save_row_btn.visible = True
            page.update()
            
        def save_row_click(e=None):
            try:
                new_val = float(tf.value)
                rates_dict[key] = new_val
                txt.value = str(new_val)
            except ValueError:
                tf.value = txt.value
                
            tf.visible = False
            val_container.visible = True
            edit_btn.visible = True
            save_row_btn.visible = False
            page.update()

        tf.on_submit = save_row_click
        edit_btn.on_click = edit_click
        save_row_btn.on_click = save_row_click

        row_controls[key] = {
            'tf': tf,
            'txt': txt,
            'val_container': val_container,
            'edit_btn': edit_btn,
            'save_row_btn': save_row_btn,
            'rates_dict': rates_dict
        }

        return ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icon_name, size=20, color=icon_color),
                        bgcolor=icon_bg, width=38, height=38, border_radius=19, alignment=ft.Alignment(0,0)
                    ),
                    ft.Column([
                        ft.Text(title, size=16, color="#064E3B", weight="bold"),
                        ft.Text(subtitle, size=12, color="#6B7280")
                    ], spacing=0)
                ], spacing=10, width=220),
                
                ft.Row([
                    val_container,
                    tf,
                    ft.Text(unit, size=14, color="#4B5563", weight="bold", width=95),
                    edit_btn,
                    save_row_btn
                ], spacing=6)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor="#F9FAFB",
            border=ft.Border(top=ft.BorderSide(1, "#E5E7EB"), bottom=ft.BorderSide(1, "#E5E7EB"), left=ft.BorderSide(1, "#E5E7EB"), right=ft.BorderSide(1, "#E5E7EB")),
            border_radius=14,
            padding=ft.Padding(left=16, right=16, top=10, bottom=10),
            margin=ft.Margin(left=0, right=0, top=0, bottom=8)
        )

    def render_dashboard():
        page.controls.clear()
        row_controls.clear()
        
        # Reactive Dashboard State for this machine
        total_bottles_val = [0]
        total_members_val = [0]
        total_points_val = [0.0]
        machine_name_val = [f"ตู้ #{MACHINE_ID}"]
        machine_location_val = [""]
        machine_status_text_val = ["พร้อมใช้งาน"]
        all_logs = []
        logs_error_msg = [None]
        is_loading_data = [True]

        # List to track all active skeleton controls for shimmer pulsing
        skeleton_controls = []

        def make_skeleton_bar(width=None, height=14, border_radius=6, bgcolor="#E2E8F0", opacity=0.75):
            ctrl = ft.Container(
                width=width,
                height=height,
                bgcolor=bgcolor,
                border_radius=border_radius,
                opacity=opacity,
                animate_opacity=400,
            )
            skeleton_controls.append(ctrl)
            return ctrl

        def build_skeleton_table_rows(count=7):
            rows = []
            badge_colors = ["#E0F2FE", "#FEF3C7", "#EDE9FE", "#E0F2FE", "#FEF3C7", "#EDE9FE", "#E0F2FE"]
            date_widths = [135, 125, 140, 130, 120, 138, 128]
            name_widths = [115, 95, 130, 105, 85, 120, 100]

            for i in range(count):
                row_bg = "#FFFFFF" if i % 2 == 0 else "#F9FAFB"
                rows.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(content=make_skeleton_bar(width=date_widths[i % len(date_widths)], height=13, border_radius=6, bgcolor="#E2E8F0"), expand=2),
                            ft.Container(content=make_skeleton_bar(width=48, height=20, border_radius=6, bgcolor="#D1FAE5"), expand=1),
                            ft.Container(content=make_skeleton_bar(width=name_widths[i % len(name_widths)], height=13, border_radius=6, bgcolor="#E2E8F0"), expand=2),
                            ft.Container(content=make_skeleton_bar(width=95, height=13, border_radius=6, bgcolor="#E2E8F0"), expand=2),
                            ft.Container(content=make_skeleton_bar(width=112, height=22, border_radius=8, bgcolor=badge_colors[i % len(badge_colors)]), expand=2),
                            ft.Container(content=make_skeleton_bar(width=42, height=13, border_radius=6, bgcolor="#E2E8F0"), expand=1),
                            ft.Container(content=make_skeleton_bar(width=54, height=20, border_radius=6, bgcolor="#FEF3C7"), expand=1),
                        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding(left=16, right=16, top=9, bottom=9),
                        bgcolor=row_bg,
                        border=ft.Border(
                            top=ft.BorderSide(0, "transparent"),
                            bottom=ft.BorderSide(1, "#F3F4F6"),
                            left=ft.BorderSide(0, "transparent"),
                            right=ft.BorderSide(0, "transparent")
                        )
                    )
                )
            return rows

        # Dynamic Controls for Stat Cards & Banner (Updated Asynchronously)
        bottles_stat_box = ft.Container(content=make_skeleton_bar(width=90, height=22, border_radius=6, bgcolor="#BAE6FD"))
        members_stat_box = ft.Container(content=make_skeleton_bar(width=80, height=22, border_radius=6, bgcolor="#BBF7D0"))
        points_stat_box = ft.Container(content=make_skeleton_bar(width=100, height=22, border_radius=6, bgcolor="#FDE68A"))
        mode_stat_val_txt = ft.Text("Point Mode" if current_type[0] == "point" else "Money Mode", size=18, color="#111827", weight="bold")
        mode_stat_sub_txt = ft.Text(f"SN: {serial_number_val[0] or '-'}", size=11, color="#9CA3AF")

        banner_machine_name_txt = ft.Text(f"ตู้ปัจจุบัน: ตู้ #{MACHINE_ID}", size=15, color="#064E3B", weight="bold")
        banner_status_txt = ft.Text("● พร้อมใช้งาน", size=12, color="#15803D", weight="bold")
        banner_location_txt = ft.Text(f"ตำแหน่ง: จุดติดตั้งเครื่อง Kiosk | Serial: {serial_number_val[0]}", size=12, color="#6B7280")

        # --- Stat Cards & Machine Banner ---
        def create_stat_card(title, val_control, sub_control, icon, icon_color, icon_bg, card_bg, border_color):
            sub_widget = sub_control if isinstance(sub_control, ft.Control) else ft.Text(str(sub_control), size=11, color="#9CA3AF")
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=24, color=icon_color),
                        bgcolor=icon_bg, width=46, height=46, border_radius=12, alignment=ft.Alignment(0, 0)
                    ),
                    ft.Column([
                        ft.Text(title, size=11, color="#6B7280", weight="bold"),
                        val_control,
                        sub_widget,
                    ], spacing=1, expand=True)
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=card_bg,
                border=ft.Border(
                    top=ft.BorderSide(1, border_color),
                    bottom=ft.BorderSide(1, border_color),
                    left=ft.BorderSide(1, border_color),
                    right=ft.BorderSide(1, border_color)
                ),
                border_radius=14,
                padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                expand=1
            )

        stat_cards_row = ft.Row([
            create_stat_card("จำนวนขวดสะสมในตู้", bottles_stat_box, "ขวดที่รับเข้าตู้นี้ทั้งหมด", ft.icons.Icons.RECYCLING, "#0284C7", "#E0F2FE", "#F0F9FF", "#BAE6FD"),
            create_stat_card("สมาชิกที่ใช้บริการตู้นี้", members_stat_box, "สมาชิกที่บันทึกกับตู้นี้", ft.icons.Icons.PEOPLE_ALT, "#059669", "#D1FAE5", "#F0FDF4", "#BBF7D0"),
            create_stat_card("แต้มที่แจกทั้งหมด", points_stat_box, "แต้มสะสมจากตู้นี้", ft.icons.Icons.STARS, "#D97706", "#FEF3C7", "#FFFBEB", "#FDE68A"),
            create_stat_card(f"ตู้ ID: #{MACHINE_ID}", mode_stat_val_txt, mode_stat_sub_txt, ft.icons.Icons.DASHBOARD_CUSTOMIZE, "#7C3AED", "#EDE9FE", "#FAF5FF", "#E9D5FF"),
        ], spacing=10)

        machine_banner = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.Icons.PRECISION_MANUFACTURING, size=20, color="#059669"),
                        bgcolor="#E6FBF2", width=36, height=36, border_radius=18, alignment=ft.Alignment(0, 0)
                    ),
                    ft.Column([
                        ft.Row([
                            banner_machine_name_txt,
                            ft.Container(
                                content=ft.Text(f"รหัสตู้: #{MACHINE_ID}", size=12, color="#059669", weight="bold"),
                                bgcolor="#D1FAE5", padding=ft.Padding(left=8, right=8, top=2, bottom=2), border_radius=6
                            ),
                            ft.Container(
                                content=banner_status_txt,
                                bgcolor="#DCFCE7", padding=ft.Padding(left=8, right=8, top=2, bottom=2), border_radius=6
                            )
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        banner_location_txt,
                    ], spacing=2)
                ], spacing=10),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.REFRESH, size=14, color="#4B5563"),
                        ft.Text("รีเฟรชข้อมูล", size=12, color="#4B5563", weight="bold")
                    ], spacing=4),
                    bgcolor="#F3F4F6", padding=ft.Padding(left=12, right=14, top=6, bottom=6), border_radius=8,
                    on_click=lambda e: trigger_refresh()
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="#F9FAFB",
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
            border_radius=14,
            padding=ft.Padding(left=14, right=14, top=8, bottom=8)
        )

        # Pagination
        ITEMS_PER_PAGE = 10
        current_page = [0]
        total_pages_holder = [1]
        
        bottle_type_labels = {"clear": "ขวดใส", "colored": "ขวดสี", "brown": "ขวดสี", "opaque": "ขวดขุ่น"}

        def build_table_rows(page_num):
            if is_loading_data[0]:
                return build_skeleton_table_rows(7)

            start = page_num * ITEMS_PER_PAGE
            end = start + ITEMS_PER_PAGE
            page_logs = all_logs[start:end]
            
            rows = []
            for i, log in enumerate(page_logs):
                btype = log.get("bottle_type", "")
                btype_display = bottle_type_labels.get(btype, btype or "-")
                
                if btype == "clear":
                    btype_badge = ft.Container(
                        content=ft.Text("ขวดใส (Clear PET)", size=12, color="#0284C7", weight="bold"),
                        bgcolor="#E0F2FE", padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                        border_radius=8
                    )
                elif btype in ("brown", "colored"):
                    btype_badge = ft.Container(
                        content=ft.Text("ขวดสี (Colored PET)", size=12, color="#D97706", weight="bold"),
                        bgcolor="#FEF3C7", padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                        border_radius=8
                    )
                elif btype == "opaque":
                    btype_badge = ft.Container(
                        content=ft.Text("ขวดขุ่น (Opaque HDPE)", size=12, color="#4F46E5", weight="bold"),
                        bgcolor="#EDE9FE", padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                        border_radius=8
                    )
                else:
                    btype_badge = ft.Container(
                        content=ft.Text(btype_display, size=12, color="#4B5563", weight="bold"),
                        bgcolor="#F3F4F6", padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                        border_radius=8
                    )

                weight_display = f"{log.get('weight', 0)} g" if log.get("weight") else "-"
                row_bg = "#FFFFFF" if i % 2 == 0 else "#F9FAFB"
                point_val = log.get("point", "0")
                point_widget = ft.Row([
                    ft.Icon(ft.icons.Icons.STARS, size=15, color="#059669"),
                    ft.Text(f"+{point_val}", size=13, color="#059669", weight="bold")
                ], spacing=4)

                log_m_id = str(log.get("machine_id") or log.get("m_id") or MACHINE_ID)
                machine_badge = ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.CHECK_CIRCLE, size=11, color="#059669"),
                        ft.Text(f"#{log_m_id}", size=12, color="#065F46", weight="bold")
                    ], spacing=3),
                    bgcolor="#D1FAE5",
                    padding=ft.Padding(left=6, right=8, top=2, bottom=2),
                    border_radius=6
                )

                rows.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(content=ft.Text(str(log.get("createat", "") or "-"), size=12, color="#6B7280"), expand=2),
                            ft.Container(content=machine_badge, expand=1),
                            ft.Container(content=ft.Text(f"{log.get('fname', '')} {log.get('lname', '')}".strip() or "-", size=13, color="#1F2937", weight="bold"), expand=2),
                            ft.Container(content=ft.Text(str(log.get("phonenumber", "") or "-"), size=13, color="#4B5563"), expand=2),
                            ft.Container(content=btype_badge, expand=2),
                            ft.Container(content=ft.Text(weight_display, size=13, color="#6B7280"), expand=1),
                            ft.Container(content=point_widget, expand=1),
                        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.Padding(left=16, right=16, top=8, bottom=8),
                        bgcolor=row_bg,
                        border=ft.Border(
                            top=ft.BorderSide(0, "transparent"),
                            bottom=ft.BorderSide(1, "#F3F4F6"),
                            left=ft.BorderSide(0, "transparent"),
                            right=ft.BorderSide(0, "transparent")
                        )
                    )
                )
            if not rows:
                if logs_error_msg[0]:
                    rows.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.icons.Icons.CLOUD_OFF, size=38, color="#DC2626"),
                                ft.Text("ไม่สามารถโหลดประวัติจากเซิร์ฟเวอร์ได้", size=15, color="#DC2626", weight="bold"),
                                ft.Text(logs_error_msg[0], size=13, color="#6B7280", text_align=ft.TextAlign.CENTER),
                                ft.Text("จำเป็นต้องเพิ่ม Route และฟังก์ชัน getMachineLogs บนเซิร์ฟเวอร์หลัก", size=12, color="#9CA3AF", text_align=ft.TextAlign.CENTER)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                            alignment=ft.Alignment(0, 0),
                            padding=26
                        )
                    )
                else:
                    rows.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.icons.Icons.RECEIPT_LONG, size=38, color="#D1D5DB"),
                                ft.Text(f"ไม่พบประวัติการทำรายการของตู้ ID: #{MACHINE_ID}", size=14, color="#6B7280", weight="bold"),
                                ft.Text("ยังไม่มีข้อมูลการหยอดขวดที่ตรงกับรหัสตู้นี้ในระบบ", size=12, color="#9CA3AF")
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                            alignment=ft.Alignment(0, 0),
                            padding=26
                        )
                    )
            return rows

        table_header = ft.Container(
            content=ft.Row([
                ft.Container(content=ft.Text("วัน-เวลา (Date)", size=13, color="#4B5563", weight="bold"), expand=2),
                ft.Container(content=ft.Text("รหัสตู้ (Machine)", size=13, color="#4B5563", weight="bold"), expand=1),
                ft.Container(content=ft.Text("ชื่อสมาชิก (Member)", size=13, color="#4B5563", weight="bold"), expand=2),
                ft.Container(content=ft.Text("เบอร์โทรศัพท์ (Phone)", size=13, color="#4B5563", weight="bold"), expand=2),
                ft.Container(content=ft.Text("ประเภทขวด (Type)", size=13, color="#4B5563", weight="bold"), expand=2),
                ft.Container(content=ft.Text("น้ำหนัก (Weight)", size=13, color="#4B5563", weight="bold"), expand=1),
                ft.Container(content=ft.Text("แต้มที่ได้รับ (Pts)", size=13, color="#4B5563", weight="bold"), expand=1),
            ], alignment=ft.MainAxisAlignment.START),
            bgcolor="#F9FAFB",
            padding=ft.Padding(left=16, right=16, top=10, bottom=10),
            border=ft.Border(
                top=ft.BorderSide(0, "transparent"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(0, "transparent"),
                right=ft.BorderSide(0, "transparent")
            )
        )

        table_body = ft.Column(
            controls=build_skeleton_table_rows(7),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH
        )

        logs_table_container = ft.Container(
            content=ft.Column([
                table_header,
                table_body
            ], spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
            border_radius=12,
            expand=True
        )

        page_info_text = ft.Text("Page 1/1 (กำลังโหลด...)", size=13, color="#4B5563", weight="bold")

        def go_prev(e):
            if current_page[0] > 0:
                current_page[0] -= 1
                table_body.controls = build_table_rows(current_page[0])
                page_info_text.value = f"Page {current_page[0]+1}/{total_pages_holder[0]} ({len(all_logs)} records)"
                page.update()

        def go_next(e):
            if current_page[0] < total_pages_holder[0] - 1:
                current_page[0] += 1
                table_body.controls = build_table_rows(current_page[0])
                page_info_text.value = f"Page {current_page[0]+1}/{total_pages_holder[0]} ({len(all_logs)} records)"
                page.update()

        pagination_row = ft.Row([
            ft.Container(
                content=ft.Text("◀ ก่อนหน้า", size=12, color="white", weight="bold"),
                bgcolor="#059669",
                padding=ft.Padding(left=12, right=12, top=6, bottom=6),
                border_radius=8,
                on_click=go_prev
            ),
            page_info_text,
            ft.Container(
                content=ft.Text("ถัดไป ▶", size=12, color="white", weight="bold"),
                bgcolor="#059669",
                padding=ft.Padding(left=12, right=12, top=6, bottom=6),
                border_radius=8,
                on_click=go_next
            ),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        table_records_count_txt = ft.Container(
            content=ft.Row([
                ft.ProgressRing(width=12, height=12, stroke_width=2, color="#059669"),
                ft.Text("กำลังโหลดประวัติ...", size=12, color="#059669", weight="bold")
            ], spacing=6),
            bgcolor="#E6FBF2",
            padding=ft.Padding(left=8, right=8, top=2, bottom=2),
            border_radius=6
        )

        table_header_row = ft.Row([
            ft.Row([
                ft.Icon(ft.icons.Icons.HISTORY, size=18, color="#064E3B"),
                ft.Text("ประวัติรายการของตู้", size=16, color="#064E3B", weight="bold"),
                table_records_count_txt,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            pagination_row
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        def fetch_dashboard_data_worker():
            auth_headers = {}
            if hasattr(page, "staff_token"):
                auth_headers["Authorization"] = f"Bearer {page.staff_token}"

            # 1. Fetch Config/Rates in background
            try:
                r_cfg = requests.get(f"{API_BASE}/operator/machines/{MACHINE_ID}/config?t={time.time()}", headers=auth_headers, timeout=4)
                if r_cfg.status_code == 200:
                    d_cfg = r_cfg.json().get('data', {})
                    if d_cfg.get('type'):
                        current_type[0] = d_cfg['type']
                    rates_obj = d_cfg.get('rates', {})
                    base_prices_obj = d_cfg.get('base_prices', {})
                    if isinstance(rates_obj, dict) and rates_obj:
                        for k, v in rates_obj.items():
                            db_rates[k] = float(v)
                        for k in ["clear", "opaque", "brown"]:
                            if f"money_{k}" in rates_obj:
                                money_rates[k] = float(rates_obj[f"money_{k}"])
                            elif current_type[0] == "money" and k in rates_obj:
                                money_rates[k] = float(rates_obj[k])
                    if isinstance(base_prices_obj, dict) and base_prices_obj:
                        for k, v in base_prices_obj.items():
                            money_rates[k] = float(v)
                    for k in ["clear", "opaque", "brown"]:
                        if k in db_rates:
                            point_rates[k] = float(db_rates[k])
            except Exception as ex:
                print(f"[Dashboard Async] Config fetch error: {ex}")

            # 2. Fetch Status in background
            try:
                res1 = requests.get(f"{API_BASE}/user/machines/{MACHINE_ID}/status?t={time.time()}", headers=auth_headers, timeout=4)
                if res1.status_code == 200:
                    st_data = res1.json().get("data", {})
                    m_obj = st_data.get("machine", {})
                    total_bottles_val[0] = int(m_obj.get("count", 0) or 0)
                    if m_obj.get("name"):
                        machine_name_val[0] = m_obj.get("name")
                    if m_obj.get("location"):
                        machine_location_val[0] = m_obj.get("location")
                    if m_obj.get("status"):
                        machine_status_text_val[0] = m_obj.get("status")
            except Exception as ex:
                print(f"[Dashboard Async] Status fetch error: {ex}")

            # 3. Fetch Users in background
            try:
                res2 = requests.get(f"{API_BASE}/operator/machines/{MACHINE_ID}/users?t={time.time()}", headers=auth_headers, timeout=4)
                if res2.status_code == 200:
                    u_data = res2.json().get("data", {})
                    total_members_val[0] = int(u_data.get("total_users", len(u_data.get("members", []))) or 0)
            except Exception as ex:
                print(f"[Dashboard Async] Users fetch error: {ex}")

            # 4. Fetch Logs in background
            logs_data = []
            try:
                res3 = requests.get(f"{API_BASE}/operator/machines/{MACHINE_ID}/logs?t={time.time()}", headers=auth_headers, timeout=4)
                if res3.status_code == 404:
                    res3 = requests.get(f"{API_BASE}/machine/{MACHINE_ID}/logs?t={time.time()}", headers=auth_headers, timeout=4)
                if res3.status_code == 200:
                    logs_data = res3.json().get("data", [])
                    logs_error_msg[0] = None
                elif res3.status_code == 404:
                    logs_error_msg[0] = f"เซิร์ฟเวอร์หลักยังไม่มี API ดึงประวัติ (/machine/{MACHINE_ID}/logs - 404 Not Found)"
                else:
                    logs_error_msg[0] = f"ไม่สามารถดึงข้อมูลได้ (HTTP {res3.status_code})"
            except Exception as ex:
                logs_error_msg[0] = f"เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์: {ex}"

            all_logs.clear()
            for log in (logs_data or []):
                m_id = str(log.get("machine_id") or log.get("m_id") or "").strip()
                if not m_id or m_id == str(MACHINE_ID).strip():
                    all_logs.append(log)

            calc_bottles = len([l for l in all_logs if float(l.get("point", 0) or 0) > 0 or l.get("bottle_type")])
            if not total_bottles_val[0] and calc_bottles:
                total_bottles_val[0] = calc_bottles
            calc_members = len(set(l.get("phonenumber") or l.get("member_id") for l in all_logs if (l.get("phonenumber") or l.get("member_id"))))
            if not total_members_val[0] and calc_members:
                total_members_val[0] = calc_members
            total_points = sum(float(l.get("point", 0) or 0) for l in all_logs if float(l.get("point", 0) or 0) > 0)
            total_points_val[0] = total_points

            is_loading_data[0] = False
            skeleton_controls.clear()
            total_pages = max(1, (len(all_logs) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            total_pages_holder[0] = total_pages

            # Update Stat Cards from Skeleton to actual Text
            bottles_stat_box.content = ft.Text(f"{total_bottles_val[0]:,} ใบ", size=18, color="#111827", weight="bold")
            members_stat_box.content = ft.Text(f"{total_members_val[0]:,} คน", size=18, color="#111827", weight="bold")
            points_stat_box.content = ft.Text(f"+{total_points_val[0]:,.1f} Pts", size=18, color="#111827", weight="bold")
            mode_stat_val_txt.value = "Point Mode" if current_type[0] == "point" else "Money Mode"
            mode_stat_sub_txt.value = f"SN: {serial_number_val[0] or '-'}"

            banner_machine_name_txt.value = f"ตู้ปัจจุบัน: {machine_name_val[0]}"
            banner_status_txt.value = f"● {machine_status_text_val[0]}"
            banner_location_txt.value = f"ตำแหน่ง: {machine_location_val[0] if machine_location_val[0] else 'จุดติดตั้งเครื่อง Kiosk'} | Serial: {serial_number_val[0]}"

            table_records_count_txt.content = ft.Text(f"ตู้ ID: #{MACHINE_ID} ({len(all_logs)} รายการ)", size=12, color="#059669", weight="bold")
            page_info_text.value = f"Page {current_page[0]+1}/{total_pages} ({len(all_logs)} records)"

            # Sync material rates into text controls
            is_pt = (current_type[0] == "point")
            curr_dict = point_rates if is_pt else money_rates
            for k, ctrl in row_controls.items():
                if ctrl.get('txt') and k in curr_dict:
                    ctrl['txt'].value = str(curr_dict[k])
                if ctrl.get('tf') and k in curr_dict and not ctrl['tf'].visible:
                    ctrl['tf'].value = str(curr_dict[k])

            table_body.controls = build_table_rows(0)
            try:
                page.update()
            except Exception:
                pass

        def shimmer_pulse_worker():
            pulse_state = [False]
            while is_loading_data[0]:
                time.sleep(0.55)
                if not is_loading_data[0]:
                    break
                pulse_state[0] = not pulse_state[0]
                target_op = 0.40 if pulse_state[0] else 0.85
                for c in list(skeleton_controls):
                    c.opacity = target_op
                try:
                    page.update()
                except Exception:
                    break

        def trigger_refresh():
            is_loading_data[0] = True
            skeleton_controls.clear()
            table_body.controls = build_skeleton_table_rows(7)
            table_records_count_txt.content = ft.Row([
                ft.ProgressRing(width=12, height=12, stroke_width=2, color="#059669"),
                ft.Text("กำลังรีเฟรชประวัติ...", size=12, color="#059669", weight="bold")
            ], spacing=6)
            bottles_stat_box.content = make_skeleton_bar(width=90, height=22, border_radius=6, bgcolor="#BAE6FD")
            members_stat_box.content = make_skeleton_bar(width=80, height=22, border_radius=6, bgcolor="#BBF7D0")
            points_stat_box.content = make_skeleton_bar(width=100, height=22, border_radius=6, bgcolor="#FDE68A")
            try:
                page.update()
            except Exception:
                pass
            threading.Thread(target=fetch_dashboard_data_worker, daemon=True).start()
            threading.Thread(target=shimmer_pulse_worker, daemon=True).start()

        dashboard_card = ft.Container(
            content=ft.Column([
                machine_banner,
                stat_cards_row,
                table_header_row,
                logs_table_container,
            ], expand=True, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor="white",
            border_radius=20,
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
            padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            expand=True
        )

        type_label = "Point Mode (สะสมแต้ม)" if current_type[0] == "point" else "Money Mode (เงินสด)"
        type_btn = ft.Container(
            content=ft.Text(type_label, size=16, color="white", weight="bold"),
            bgcolor="#38A169" if current_type[0] == "point" else "#2196F3",
            padding=ft.Padding(left=15, right=15, top=8, bottom=8),
            border_radius=10,
            on_click=toggle_type
        )
        
        save_btn = ft.Container(
            content=ft.Text("บันทึก (Save)", size=16, color="white", weight="bold"),
            bgcolor="#E53E3E",
            padding=ft.Padding(left=15, right=15, top=8, bottom=8),
            border_radius=10,
            on_click=save_settings
        )

        rates_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.icons.Icons.BAR_CHART, size=24, color="#064E3B"),
                        ft.Text("Reward Configuration (ตั้งค่าเรทราคา)", size=20, color="#064E3B", weight="bold"),
                    ], spacing=10),
                    ft.Row([type_btn, save_btn], spacing=10)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text("กำหนดแต้มสะสมหรือราคาเงินสดต่อน้ำหนัก (กรัม) สำหรับแต่ละประเภทวัสดุ", size=14, color="#4B5563"),
                ft.Container(height=5),
                material_row("clear", "ขวดใส (Clear PET)", "High recyclability grade", ft.icons.Icons.WATER_DROP, "#0284C7", "#E0F2FE"),
                material_row("brown", "ขวดสี (Colored PET)", "ขวดเครื่องดื่มมีสีทุกชนิด", ft.icons.Icons.PALETTE, "#D97706", "#FEF3C7"),
                material_row("opaque", "ขวดขุ่น (Opaque HDPE)", "Milk & detergent bottles", ft.icons.Icons.INVERT_COLORS, "#4F46E5", "#EDE9FE"),
            ]),
            bgcolor="white",
            border_radius=20,
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
            padding=ft.Padding(left=16, right=16, top=16, bottom=16),
        )

        # --- Serial Number Card ---
        current_serial = [serial_number_val[0]]
        has_serial = bool(current_serial[0])

        serial_display_text = ft.Text(
            current_serial[0] if has_serial else "ยังไม่ได้กำหนด Serial Number",
            size=16,
            color="#064E3B" if has_serial else "#9CA3AF",
            weight="bold"
        )

        serial_display_box = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.NUMBERS, size=18, color="#059669" if has_serial else "#9CA3AF"),
                serial_display_text
            ], spacing=8),
            bgcolor="#F9FAFB",
            padding=ft.Padding(left=15, right=15, top=10, bottom=10),
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
            border_radius=12
        )

        serial_input = ft.TextField(
            value=current_serial[0],
            hint_text="กรอก Serial Number ใหม่",
            width=280,
            text_size=16,
            bgcolor="white",
            border_color="#E5E7EB",
            border_radius=12
        )

        def open_edit_serial(e):
            serial_input.value = current_serial[0]
            serial_info_row.visible = False
            serial_edit_row.visible = True
            cancel_serial_btn.visible = bool(current_serial[0])
            page.update()

        def cancel_edit_serial(e):
            serial_info_row.visible = True
            serial_edit_row.visible = False
            page.update()

        change_serial_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.EDIT, size=16, color="white"),
                ft.Text("เปลี่ยน Serial Number", size=14, color="white", weight="bold")
            ], spacing=6),
            bgcolor="#38A169",
            padding=ft.Padding(left=15, right=15, top=10, bottom=10),
            border_radius=10,
            on_click=open_edit_serial
        )

        serial_info_row = ft.Row([
            serial_display_box,
            change_serial_btn
        ], spacing=12, alignment=ft.MainAxisAlignment.START, visible=has_serial)

        def close_confirm_dlg(dlg):
            dlg.open = False
            page.update()

        def execute_save_serial(new_val, dlg):
            dlg.open = False
            page.update()

            try:
                save_machine_config({"serial_number": new_val})
                current_serial[0] = new_val
                serial_number_val[0] = new_val
                serial_display_text.value = new_val
                serial_display_text.color = "#064E3B"
                serial_input.value = new_val
                serial_info_row.visible = True
                serial_edit_row.visible = False
                show_alert(page, "บันทึก Serial Number สำเร็จ", alert_type="success")
            except Exception as ex:
                show_alert(page, f"เกิดข้อผิดพลาด: {ex}", alert_type="error")

        def on_save_serial_click(e):
            new_val = serial_input.value.strip() if serial_input.value else ""
            if not new_val:
                show_alert(page, "กรุณากรอก Serial Number ก่อนบันทึก", alert_type="error")
                return

            dlg = ft.AlertDialog(
                title=ft.Text("ยืนยันการบันทึก", size=22, weight="bold"),
                content=ft.Text(f"คุณต้องการบันทึก Serial Number เป็น\n'{new_val}' ใช่หรือไม่?\nยืนยันหรือไม่?", size=18),
                actions=[
                    ft.TextButton("ยกเลิก", on_click=lambda ev: close_confirm_dlg(dlg)),
                    ft.TextButton("ยืนยัน", on_click=lambda ev: execute_save_serial(new_val, dlg))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                shape=ft.RoundedRectangleBorder(radius=20)
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        save_serial_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.SAVE, size=16, color="white"),
                ft.Text("บันทึก", size=14, color="white", weight="bold")
            ], spacing=6),
            bgcolor="#E53E3E",
            padding=ft.Padding(left=16, right=16, top=10, bottom=10),
            border_radius=10,
            on_click=on_save_serial_click
        )

        cancel_serial_btn = ft.Container(
            content=ft.Text("ยกเลิก", size=14, color="#4A5568", weight="bold"),
            bgcolor="#EDF2F7",
            padding=ft.Padding(left=14, right=14, top=10, bottom=10),
            border_radius=10,
            on_click=cancel_edit_serial,
            visible=has_serial
        )

        serial_edit_row = ft.Row([
            serial_input,
            save_serial_btn,
            cancel_serial_btn
        ], spacing=10, alignment=ft.MainAxisAlignment.START, visible=not has_serial)

        serial_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.Icons.TAG, size=24, color="#064E3B"),
                    ft.Text("Machine Serial Number", size=20, color="#064E3B", weight="bold"),
                ], spacing=10),
                ft.Text("หมายเลขประจำเครื่องสำหรับเชื่อมต่อระบบและระบุตัวตน", size=14, color="#4A5568"),
                ft.Container(height=5),
                serial_info_row,
                serial_edit_row,
            ]),
            bgcolor="white",
            border_radius=20,
            padding=ft.Padding(left=15, right=15, top=15, bottom=15),
        )

        # --- Hardware Calibration & Diagnostic Card ---
        def toggle_fs_click(e):
            page.window.full_screen = not getattr(page.window, 'full_screen', False)
            try:
                page.window.update()
                st = "เต็มจอ (Fullscreen)" if page.window.full_screen else "หน้าต่างปกติ (Windowed)"
                show_alert(page, f"เปลี่ยนโหมดหน้าจอเป็น: {st}", alert_type="info")
            except Exception as ex:
                show_alert(page, f"ไม่สามารถสลับโหมดได้: {ex}", alert_type="error")

        def open_cam_viewer(e):
            import webbrowser
            try:
                detector = getattr(page, 'detector', None)
                if detector is None:
                    from services.detector_service import DetectorService
                    detector = DetectorService.get_detector()
                    page.detector = detector

                if detector:
                    detector.start_preview_mode()
                    port = getattr(detector, 'stream_port', 5000)
                    show_alert(page, f"กำลังเปิด Camera Viewer ที่ http://localhost:{port}...", alert_type="info")

                    def _delayed_open():
                        time.sleep(0.8)
                        webbrowser.open(f"http://localhost:{port}")
                    threading.Thread(target=_delayed_open, daemon=True).start()
                else:
                    webbrowser.open("http://localhost:5000")
            except Exception as ex:
                print(f"[Dashboard Camera Viewer] Error: {ex}")
                try:
                    webbrowser.open("http://localhost:5000")
                except:
                    pass

        def rotate_cam_click(e):
            det = get_or_init_detector()
            if det:
                cur_rot = getattr(det, 'camera_rotate', 270)
                new_rot = det.set_rotation((cur_rot + 90) % 360)
                txt_cam_rot.value = f"หมุนกล้อง 90° (มุม: {new_rot}°)"
                txt_cam_rot.update()
                show_alert(page, f"หมุนกล้องเป็น {new_rot}° เรียบร้อยแล้ว (บันทึกแล้ว)", alert_type="success")
            else:
                show_alert(page, "ไม่พบโมดูลกล้อง", alert_type="error")

        def tare_scale_click(e):
            det = get_or_init_detector()
            if det:
                det.tare_scale()
                show_alert(page, "เซ็ตศูนย์ตราชั่งเรียบร้อยแล้ว (0.0g)", alert_type="success")
            else:
                show_alert(page, "ไม่พบโมดูลตราชั่ง", alert_type="error")

        def reconnect_cam_click(e):
            det = get_or_init_detector()
            if det:
                ok = det.reconnect_camera()
                msg = "รีเซ็ตการเชื่อมต่อกล้องสำเร็จ (ล้าง Frame Buffer เรียบร้อย)" if ok else "กล้องไม่พร้อมใช้งาน โปรดตรวจสาย USB"
                show_alert(page, msg, alert_type="success" if ok else "error")
            else:
                show_alert(page, "ไม่พบโมดูลกล้อง", alert_type="error")

        init_rot = getattr(page.detector, 'camera_rotate', 270) if getattr(page, 'detector', None) else 270
        txt_cam_rot = ft.Text(f"หมุนกล้อง 90° (มุม: {init_rot}°)", size=14, color="white", weight="bold")

        hardware_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.Icons.BUILD_CIRCLE, size=24, color="#064E3B"),
                    ft.Text("Hardware Calibration & Diagnostic (แคลิเบรตกล้องและที่ชั่ง)", size=20, color="#064E3B", weight="bold"),
                ], spacing=10),
                ft.Text("เครื่องมือแก้ไขกรณีตราชั่งค้าง (น้ำหนักไม่คืน 0) หรือภาพกล้องค้าง/กระตุก พร้อมปรับมุมภาพสด", size=14, color="#4A5568"),
                ft.Container(height=5),
                ft.Row([
                    # ปุ่ม Tare ตราชั่ง
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.Icons.SCALE, size=18, color="white"),
                            ft.Text("เซ็ตศูนย์ตราชั่ง (Tare 0g)", size=14, color="white", weight="bold")
                        ], spacing=6),
                        bgcolor="#059669",
                        padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                        border_radius=10,
                        on_click=tare_scale_click,
                        tooltip="รีเซ็ตค่าน้ำหนักบน Loadcell เป็น 0.0g เมื่อมีเศษน้ำหนักค้าง"
                    ),
                    # ปุ่มรีเซ็ตกล้อง
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.Icons.VIDEOCAM, size=18, color="white"),
                            ft.Text("รีเซ็ตกล้อง (Reconnect)", size=14, color="white", weight="bold")
                        ], spacing=6),
                        bgcolor="#E11D48",
                        padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                        border_radius=10,
                        on_click=reconnect_cam_click,
                        tooltip="รีเซ็ตและเชื่อมต่อกล้องใหม่ เคลียร์ Buffer ภาพค้าง"
                    ),
                    # ปุ่มหมุนกล้อง
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.Icons.ROTATE_RIGHT, size=18, color="white"),
                            txt_cam_rot
                        ], spacing=6),
                        bgcolor="#D97706",
                        padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                        border_radius=10,
                        on_click=rotate_cam_click
                    ),
                    # ปุ่มเปิด Stream
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.Icons.OPEN_IN_BROWSER, size=18, color="white"),
                            ft.Text("เปิด Camera Viewer (Web Stream)", size=14, color="white", weight="bold")
                        ], spacing=6),
                        bgcolor="#0284C7",
                        padding=ft.Padding(left=16, right=16, top=10, bottom=10),
                        border_radius=10,
                        on_click=open_cam_viewer
                    ),
                ], spacing=10, wrap=True)
            ]),
            bgcolor="white",
            border_radius=20,
            padding=ft.Padding(left=15, right=15, top=15, bottom=15),
        )

        config_view = ft.Column([
            serial_card,
            rates_card,
            hardware_card
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        tab_content = ft.Container(content=dashboard_card, expand=True)

        def change_tab(e):
            if e.control.data == "Dashboard":
                tab_content.content = dashboard_card
                btn_dash.bgcolor = "#059669"
                btn_dash.content.controls[0].color = "white"
                btn_dash.content.controls[1].color = "white"
                btn_dash.border = ft.Border(top=ft.BorderSide(1, "#059669"), bottom=ft.BorderSide(1, "#059669"), left=ft.BorderSide(1, "#059669"), right=ft.BorderSide(1, "#059669"))
                btn_conf.bgcolor = "white"
                btn_conf.content.controls[0].color = "#4B5563"
                btn_conf.content.controls[1].color = "#4B5563"
                btn_conf.border = ft.Border(top=ft.BorderSide(1, "#E5E7EB"), bottom=ft.BorderSide(1, "#E5E7EB"), left=ft.BorderSide(1, "#E5E7EB"), right=ft.BorderSide(1, "#E5E7EB"))
            else:
                tab_content.content = config_view
                btn_dash.bgcolor = "white"
                btn_dash.content.controls[0].color = "#4B5563"
                btn_dash.content.controls[1].color = "#4B5563"
                btn_dash.border = ft.Border(top=ft.BorderSide(1, "#E5E7EB"), bottom=ft.BorderSide(1, "#E5E7EB"), left=ft.BorderSide(1, "#E5E7EB"), right=ft.BorderSide(1, "#E5E7EB"))
                btn_conf.bgcolor = "#059669"
                btn_conf.content.controls[0].color = "white"
                btn_conf.content.controls[1].color = "white"
                btn_conf.border = ft.Border(top=ft.BorderSide(1, "#059669"), bottom=ft.BorderSide(1, "#059669"), left=ft.BorderSide(1, "#059669"), right=ft.BorderSide(1, "#059669"))
            page.update()

        btn_dash = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.DASHBOARD, size=16, color="white"),
                ft.Text("Dashboard", size=14, color="white", weight="bold")
            ], spacing=6),
            bgcolor="#059669", padding=ft.Padding(left=18, right=18, top=8, bottom=8),
            border_radius=12,
            border=ft.Border(top=ft.BorderSide(1, "#059669"), bottom=ft.BorderSide(1, "#059669"), left=ft.BorderSide(1, "#059669"), right=ft.BorderSide(1, "#059669")),
            data="Dashboard", on_click=change_tab
        )
        btn_conf = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.TUNE, size=16, color="#4B5563"),
                ft.Text("Configuration", size=14, color="#4B5563", weight="bold")
            ], spacing=6),
            bgcolor="white", padding=ft.Padding(left=18, right=18, top=8, bottom=8),
            border_radius=12,
            border=ft.Border(top=ft.BorderSide(1, "#E5E7EB"), bottom=ft.BorderSide(1, "#E5E7EB"), left=ft.BorderSide(1, "#E5E7EB"), right=ft.BorderSide(1, "#E5E7EB")),
            data="Configuration", on_click=change_tab
        )
        
        tabs = ft.Column([
            ft.Row([btn_dash, btn_conf], spacing=10, alignment="center"),
            tab_content
        ], expand=True, spacing=10)
        
        def cleanup_dashboard():
            if getattr(page, 'detector', None) and getattr(page.detector, 'is_preview_mode', False):
                try:
                    page.detector.stop()
                except:
                    pass

        def do_logout(e):
            cleanup_dashboard()
            try:
                import os
                if os.path.exists("staff_cache.json"):
                    os.remove("staff_cache.json")
            except:
                pass
            router.go_staff_login()

        def on_dash_back(e):
            cleanup_dashboard()
            router.go_staff_login()

        dash_back_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.ARROW_BACK_IOS_NEW, size=14, color="#064E3B"),
                ft.Text("กลับ", size=13, color="#064E3B", weight="bold")
            ], spacing=4),
            bgcolor="white",
            padding=ft.Padding(left=12, right=14, top=6, bottom=6),
            border_radius=12,
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
            on_click=on_dash_back
        )

        title_row = ft.Row([
            dash_back_btn,
            ft.Icon(ft.icons.Icons.SETTINGS, size=20, color="#059669"),
            ft.Text("Machine Configuration", size=18, color="#064E3B", weight="bold")
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        admin_badge = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.ADMIN_PANEL_SETTINGS, size=16, color="#059669"),
                ft.Text("Admin Central", size=13, color="#064E3B", weight="bold"),
            ], spacing=6),
            bgcolor="white",
            padding=ft.Padding(left=10, right=12, top=6, bottom=6),
            border_radius=12,
            border=ft.Border(
                top=ft.BorderSide(1, "#E5E7EB"),
                bottom=ft.BorderSide(1, "#E5E7EB"),
                left=ft.BorderSide(1, "#E5E7EB"),
                right=ft.BorderSide(1, "#E5E7EB")
            ),
        )

        logout_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.LOGOUT, size=15, color="#DC2626"),
                ft.Text("ออกจากระบบ", size=13, color="#DC2626", weight="bold")
            ], spacing=6),
            bgcolor="#FEF2F2",
            padding=ft.Padding(left=12, right=14, top=6, bottom=6),
            border_radius=12,
            border=ft.Border(
                top=ft.BorderSide(1, "#FCA5A5"),
                bottom=ft.BorderSide(1, "#FCA5A5"),
                left=ft.BorderSide(1, "#FCA5A5"),
                right=ft.BorderSide(1, "#FCA5A5")
            ),
            on_click=do_logout
        )

        top_actions = ft.Row([admin_badge, logout_btn], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        top_bar = ft.Container(
            content=ft.Row([
                title_row,
                top_actions
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            left=20, right=20, top=12
        )

        main_container = ft.Container(
            content=tabs,
            top=58, left=20, right=20, bottom=15
        )

        dashboard_stack = ft.Stack([top_bar, main_container], expand=True)
        page.add(dashboard_stack)
        page.update()
        threading.Thread(target=fetch_dashboard_data_worker, daemon=True).start()
        threading.Thread(target=shimmer_pulse_worker, daemon=True).start()

    render_dashboard()

