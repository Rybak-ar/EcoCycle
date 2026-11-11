# -*- coding: utf-8 -*-
import json
import threading
import flet as ft
from core.config import get_api_base
from core.ui_utils import b_all, get_back_btn, show_alert as ui_show_alert, dispatch_ui

def render_staff_login_view(page: ft.Page, router):
    page.controls.clear()
    
    if getattr(page, 'detector', None):
        try:
            page.detector.stop()
        except Exception:
            pass
    
    # องค์ประกอบตกแต่งพื้นหลัง
    bg_decor_1 = ft.Container(
        width=500, height=500, border_radius=250,
        bgcolor="#D1FAE5", top=-140, right=-80
    )
    bg_decor_2 = ft.Container(
        width=380, height=380, border_radius=190,
        bgcolor="#DEF7EC", bottom=-100, left=-80
    )
    
    saved_phone = None
    try:
        with open("staff_cache.json", "r") as f:
            saved_phone = json.load(f).get("staff_phone")
    except Exception:
        pass
    
    input_mode = ["pin" if saved_phone else "phone"]
    staff_phone_val = [saved_phone if saved_phone else ""]
    staff_pin_val = [""]
    is_submitting = [False]

    # Top App Bar
    top_bar = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.Icons.AUTORENEW, size=28, color="#059669"),
                ft.Text("EcoCycle Pro", size=24, color="#064E3B", weight="bold")
            ], spacing=10),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.Icons.ADMIN_PANEL_SETTINGS, size=18, color="#B45309"),
                    ft.Text("ระบบจัดการตู้สำหรับเจ้าหน้าที่", size=13, color="#92400E", weight="bold"),
                ], spacing=6),
                bgcolor="#FEF3C7",
                padding=ft.Padding(left=14, right=16, top=6, bottom=6),
                border_radius=20,
                border=b_all(1, "#FCD34D")
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        left=40, right=40, top=20
    )

    display_text = ft.Text(value="", size=22, color="#9CA3AF", weight="bold", text_align="center", max_lines=1)
    mode_chip_text = ft.Text("โหมด: รหัสผ่าน PIN" if saved_phone else "โหมด: เบอร์โทร / รหัสเจ้าหน้าที่", size=12, color="#059669", weight="bold")

    if saved_phone:
        login_label = ft.Text("กรอกรหัส PIN", size=32, color="#064E3B", weight="bold")
        sub_label = ft.Text(f"เจ้าหน้าที่: {saved_phone}\nกรุณากรอกรหัสผ่าน PIN", size=14, color="#4B5563")
    else:
        login_label = ft.Text("เข้าสู่ระบบเจ้าหน้าที่", size=32, color="#064E3B", weight="bold")
        sub_label = ft.Text("กรุณากรอกเบอร์โทรศัพท์หรือรหัสเจ้าหน้าที่เพื่อยืนยันตัวตน", size=14, color="#4B5563")

    def format_display_phone(val):
        if len(val) == 10:
            return f"{val[:3]} - {val[3:6]} - {val[6:]}"
        elif len(val) == 9:
            return f"{val[:2]} - {val[2:5]} - {val[5:]}"
        return val

    def update_display():
        if input_mode[0] == "phone":
            val = staff_phone_val[0]
            if not val:
                display_text.value = "กรอกเบอร์โทร / รหัสเจ้าหน้าที่"
                display_text.color = "#9CA3AF"
                display_text.size = 18
            else:
                display_text.value = format_display_phone(val)
                display_text.color = "#064E3B"
                display_text.size = 24 if len(val) <= 6 else 22
        else:
            val = staff_pin_val[0]
            if not val:
                display_text.value = "กรอกรหัส PIN"
                display_text.color = "#9CA3AF"
                display_text.size = 20
            else:
                if len(val) <= 6:
                    display_text.value = "  ".join(["●"] * len(val))
                    display_text.color = "#064E3B"
                    display_text.size = 24
                else:
                    display_text.value = " ".join(["●"] * len(val))
                    display_text.color = "#064E3B"
                    display_text.size = 20

    update_display()

    def security_feature(icon_name, title, desc):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon_name, size=20, color="#059669"),
                    bgcolor="#E6FBF2", width=38, height=38, border_radius=19,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Column([
                    ft.Text(title, size=13, color="#064E3B", weight="bold"),
                    ft.Text(desc, size=11, color="#6B7280"),
                ], spacing=1, expand=True)
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="white",
            border_radius=14,
            padding=ft.Padding(left=12, right=14, top=8, bottom=8),
            border=b_all(1, "#E5E7EB")
        )

    def switch_account(e):
        input_mode[0] = "phone"
        staff_phone_val[0] = ""
        staff_pin_val[0] = ""
        login_label.value = "เข้าสู่ระบบเจ้าหน้าที่"
        sub_label.value = "กรุณากรอกเบอร์โทรศัพท์หรือรหัสเจ้าหน้าที่เพื่อยืนยันตัวตน"
        mode_chip_text.value = "โหมด: เบอร์โทร / รหัสเจ้าหน้าที่"
        switch_btn.visible = False
        update_display()
        page.update()

    switch_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.ARROW_BACK, size=16, color="#059669"),
            ft.Text("เปลี่ยนเบอร์ / กรอกใหม่", size=12, color="#059669", weight="bold")
        ], spacing=4),
        on_click=switch_account,
        padding=ft.Padding(left=10, right=10, top=4, bottom=4),
        border_radius=10,
        bgcolor="#E6FBF2",
        visible=bool(saved_phone)
    )

    left_panel = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.Icons.LOCK, size=14, color="#B45309"),
                    ft.Text("SECURITY CONSOLE", size=11, color="#92400E", weight="bold")
                ], spacing=4),
                bgcolor="#FEF3C7",
                padding=ft.Padding(left=10, right=10, top=3, bottom=3),
                border_radius=10
            ),
            login_label,
            sub_label,
            switch_btn,
            ft.Container(height=4),
            security_feature(ft.icons.Icons.SECURITY, "ระบบความปลอดภัย 2 ชั้น", "ยืนยันหมายเลขโทรศัพท์และรหัสผ่าน PIN"),
            security_feature(ft.icons.Icons.SETTINGS, "ตั้งค่าเครื่องและราคา", "ปรับอัตราคะแนน ข้อมูลตู้ และเซ็นเซอร์"),
            security_feature(ft.icons.Icons.INSIGHTS, "รายงานและสถิติตู้", "ดูจำนวนขวดสะสมและประวัติทำรายการ"),
        ], spacing=8),
        width=420
    )

    def show_alert(msg, alert_type="error", title=None):
        ui_show_alert(page, msg, alert_type=alert_type, title=title)

    def num_click(e):
        if is_submitting[0]:
            return
        val = e.control.data
        if input_mode[0] == "phone" and len(staff_phone_val[0]) < 10:
            staff_phone_val[0] += val
            update_display()
        elif input_mode[0] == "pin" and len(staff_pin_val[0]) < 10:
            staff_pin_val[0] += val
            update_display()
        page.update()
            
    def backspace_click(e):
        if is_submitting[0]:
            return
        if input_mode[0] == "phone" and len(staff_phone_val[0]) > 0:
            staff_phone_val[0] = staff_phone_val[0][:-1]
            update_display()
        elif input_mode[0] == "pin" and len(staff_pin_val[0]) > 0:
            staff_pin_val[0] = staff_pin_val[0][:-1]
            update_display()
        page.update()
            
    def submit_click(e):
        if is_submitting[0]:
            return
        if input_mode[0] == "phone":
            if staff_phone_val[0].strip():
                input_mode[0] = "pin"
                login_label.value = "กรอกรหัส PIN"
                sub_label.value = f"เจ้าหน้าที่: {staff_phone_val[0]}\nกรุณากรอกรหัสผ่าน PIN"
                mode_chip_text.value = "โหมด: รหัสผ่าน PIN"
                switch_btn.visible = True
                update_display()
                page.update()
            else:
                show_alert("กรุณากรอกเบอร์โทรศัพท์หรือรหัสเจ้าหน้าที่", alert_type="warning", title="Warning")
        elif input_mode[0] == "pin":
            if not staff_pin_val[0].strip():
                show_alert("กรุณากรอกรหัส PIN หรือรหัสผ่าน", alert_type="warning", title="Warning")
                return

            entered_val = staff_phone_val[0].strip()
            pin_val = staff_pin_val[0].strip()
            is_submitting[0] = True
            submit_btn.on_click = None
            submit_btn.opacity = 0.6
            submit_btn.content = ft.ProgressRing(width=22, height=22, stroke_width=2.5, color="white")
            display_text.value = "กำลังตรวจสอบ..."
            display_text.color = "#059669"
            page.update()

            def do_staff_login_worker():
                import requests  # Lazy import requests on-demand
                email_map = {
                    "0800000000": "operator@example.com",
                    "0811111111": "admin@example.com",
                    "0822222222": "shop@example.com"
                }
                email_to_send = email_map.get(entered_val, entered_val)
                payload = {
                    "identifier": entered_val,
                    "email": email_to_send,
                    "phonenumber": entered_val,
                    "password": pin_val
                }
                try:
                    api_base = get_api_base()
                    response = requests.post(f"{api_base}/login", json=payload, timeout=5)
                    if response.status_code == 200:
                        res_data = response.json()
                        if res_data.get('status') == 'success':
                            page.staff_token = res_data.get('token')
                            try:
                                with open("staff_cache.json", "w") as f:
                                    json.dump({"staff_phone": entered_val}, f)
                            except Exception as ex:
                                print(f"Error saving staff cache: {ex}")
                            router.go_dashboard()
                        else:
                            def _on_st_fail():
                                is_submitting[0] = False
                                submit_btn.on_click = submit_click
                                submit_btn.opacity = 1.0
                                submit_btn.content = ft.Text("✓", size=24, color="white", weight="bold")
                                error_msg = res_data.get('message') or "รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
                                show_alert(error_msg, alert_type="error", title="Error")
                                staff_pin_val[0] = ""
                                display_text.value = "รหัสผ่านไม่ถูกต้อง"
                                display_text.color = "#DC2626"
                                display_text.size = 20
                                page.update()
                            dispatch_ui(page, _on_st_fail)
                    else:
                        def _on_st_err_resp():
                            is_submitting[0] = False
                            submit_btn.on_click = submit_click
                            submit_btn.opacity = 1.0
                            submit_btn.content = ft.Text("✓", size=24, color="white", weight="bold")
                            try:
                                res_data = response.json()
                                error_msg = res_data.get('message') or "รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
                            except Exception:
                                if response.status_code in (401, 400, 403):
                                    error_msg = "รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง"
                                else:
                                    error_msg = "เกิดข้อผิดพลาดจากเซิร์ฟเวอร์"
                            show_alert(error_msg, alert_type="error", title="Error")
                            staff_pin_val[0] = ""
                            display_text.value = "รหัสผ่านไม่ถูกต้อง"
                            display_text.color = "#DC2626"
                            display_text.size = 20
                            page.update()
                        dispatch_ui(page, _on_st_err_resp)
                except Exception as ex:
                    print(f"[Staff Login] API Error: {ex}")
                    def _on_st_exc():
                        is_submitting[0] = False
                        submit_btn.on_click = submit_click
                        submit_btn.opacity = 1.0
                        submit_btn.content = ft.Text("✓", size=24, color="white", weight="bold")
                        show_alert("ไม่สามารถเชื่อมต่อฐานข้อมูลได้", alert_type="error", title="Error")
                        staff_pin_val[0] = ""
                        update_display()
                        page.update()
                    dispatch_ui(page, _on_st_exc)

            threading.Thread(target=do_staff_login_worker, daemon=True).start()
        
    def create_btn(text, on_click, bg_color="#F9FAFB", text_color="#1F2937"):
        return ft.Container(
            content=ft.Text(text, size=24, color=text_color, weight="bold"),
            bgcolor=bg_color, width=82, height=62, border_radius=16,
            border=b_all(1, "#E5E7EB") if bg_color == "#F9FAFB" else None,
            alignment=ft.Alignment(0, 0), on_click=on_click, data=text
        )

    submit_btn = ft.Container(
        content=ft.Text("✓", size=24, color="white", weight="bold"),
        bgcolor="#059669", width=82, height=62, border_radius=16,
        alignment=ft.Alignment(0, 0), on_click=submit_click, data="✓"
    )

    keypad_card = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.Icons.KEYBOARD, size=16, color="#059669"),
                    mode_chip_text
                ], spacing=6, alignment="center"),
                bgcolor="#E6FBF2",
                padding=ft.Padding(left=12, right=12, top=4, bottom=4),
                border_radius=12
            ),
            ft.Container(
                content=display_text,
                width=280, height=60,
                bgcolor="#F9FAFB",
                border=b_all(2, "#059669"),
                border_radius=16,
                alignment=ft.Alignment(0, 0)
            ),
            ft.Container(height=4),
            ft.Row([create_btn("1", num_click), create_btn("2", num_click), create_btn("3", num_click)], alignment="center", spacing=8),
            ft.Row([create_btn("4", num_click), create_btn("5", num_click), create_btn("6", num_click)], alignment="center", spacing=8),
            ft.Row([create_btn("7", num_click), create_btn("8", num_click), create_btn("9", num_click)], alignment="center", spacing=8),
            ft.Row([
                create_btn("⌫", backspace_click, bg_color="#FEE2E2", text_color="#DC2626"), 
                create_btn("0", num_click), 
                submit_btn, 
            ], alignment="center", spacing=8),
        ], spacing=8, alignment="center", horizontal_alignment="center"),
        bgcolor="white",
        padding=ft.Padding(left=24, right=24, top=20, bottom=20),
        border_radius=24,
        border=b_all(1, "#E5E7EB"),
        width=340,
        height=470
    )

    main_content = ft.Container(
        content=ft.Row([
            left_panel,
            keypad_card
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        left=80, right=80, top=75, bottom=60
    )

    back_btn = get_back_btn(lambda e: router.go_home())

    staff_login_stack = ft.Stack([
        bg_decor_1,
        bg_decor_2,
        top_bar,
        main_content,
        back_btn
    ], expand=True)
    page.add(staff_login_stack)
    page.update()
