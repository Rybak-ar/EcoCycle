# -*- coding: utf-8 -*-
import threading
import flet as ft
from core.config import get_api_base, get_machine_id, save_machine_config
from core.ui_utils import b_all, show_alert, dispatch_ui

def render_home_view(page: ft.Page, router):
    page.controls.clear()
    
    # Stop detector if returning from another screen
    if getattr(page, 'detector', None):
        try:
            page.detector.stop()
        except Exception:
            pass

    print("[App] EcoCycle Pro GUI: Displaying Home Screen (Fast View).")
    
    # องค์ประกอบตกแต่งพื้นหลัง
    bg_decor_1 = ft.Container(
        width=550, height=550, border_radius=275,
        bgcolor="#D1FAE5", top=-150, right=-100
    )
    bg_decor_2 = ft.Container(
        width=400, height=400, border_radius=200,
        bgcolor="#DEF7EC", bottom=-120, left=-100
    )

    # การ์ดจุดเด่นสิทธิประโยชน์
    def feature_chip(icon_name, title, subtitle):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon_name, size=22, color="#059669"),
                    bgcolor="#E6FBF2", width=42, height=42, border_radius=21,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Column([
                    ft.Text(title, size=15, color="#064E3B", weight="bold"),
                    ft.Text(subtitle, size=12, color="#6B7280"),
                ], spacing=2, expand=True)
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="white",
            padding=ft.Padding(left=14, right=16, top=10, bottom=10),
            border_radius=16,
            border=b_all(1, "#E5E7EB"),
            width=380
        )

    # ส่วนหัวและเนื้อหาฝั่งซ้าย (Hero Section)
    brand_tag = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.AUTORENEW, size=24, color="#059669"),
            ft.Text("EcoCycle Pro", size=22, color="#064E3B", weight="bold"),
            ft.Container(
                content=ft.Text("Smart Kiosk", size=12, color="#059669", weight="bold"),
                bgcolor="#D1FAE5", padding=ft.Padding(left=10, right=10, top=3, bottom=3),
                border_radius=10
            )
        ], spacing=10),
    )

    hero_col = ft.Column([
        brand_tag,
        ft.Container(height=5),
        ft.Text("เปลี่ยนขยะพลาสติก\nให้เป็นรางวัลได้ทันที", size=38, color="#064E3B", weight="bold"),
        ft.Text("ระบบรับคืนขวดอัตโนมัติ หยอดขวดปุ๊บ ได้แต้มปั๊บ\nสะสมแลกรับของรางวัลและส่วนลดมากมายเพื่อโลกสีเขียว", size=15, color="#4B5563"),
        ft.Container(height=10),
        feature_chip(ft.icons.Icons.FLASH_ON, "สะดวก รวดเร็ว ไม่ต้องโหลดแอป", "เพียงกดเบอร์โทรศัพท์ ก็เริ่มสะสมแต้มได้ทันที"),
        feature_chip(ft.icons.Icons.CARD_GIFTCARD, "ของรางวัลและสิทธิพิเศษมากมาย", "สะสมแต้มแลกสินค้า คูปองส่วนลด หรือเงินสด"),
        feature_chip(ft.icons.Icons.ECO, "ร่วมลดขยะเพื่อโลกที่ยั่งยืน", "ขวดพลาสติกจะถูกนำไปรีไซเคิลอย่างถูกวิธี 100%"),
    ], spacing=10)

    # ปุ่มมุมซ้ายล่างสำหรับเจ้าหน้าที่
    staff_only = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.ADMIN_PANEL_SETTINGS, size=18, color="#9CA3AF"),
            ft.Text("เข้าสู่ระบบเจ้าหน้าที่ (Staff Only)", size=13, color="#9CA3AF", weight="bold"),
        ], spacing=6),
        on_click=lambda e: router.go_staff_login(),
        padding=ft.Padding(left=14, right=16, top=8, bottom=8),
        border_radius=12,
    )

    bottom_row = ft.Row([
        staff_only
    ], spacing=10)

    left_col = ft.Column([
        hero_col,
        ft.Container(expand=True),
        bottom_row
    ], expand=True)

    # ตัวแปรเก็บหมายเลขสมาชิกที่กรอก
    raw_phone = [""]
    phone_display_text = ft.Text(value="กรอกเบอร์มือถือ 10 หลัก", size=22, color="#9CA3AF", weight="bold", text_align="center", max_lines=1)
    is_submitting = [False]

    def update_display():
        v = raw_phone[0]
        if not v:
            phone_display_text.value = "กรอกเบอร์มือถือ 10 หลัก"
            phone_display_text.color = "#9CA3AF"
            phone_display_text.size = 20
        else:
            formatted = ""
            for i, ch in enumerate(v):
                if i in [3, 6]:
                    formatted += " - "
                formatted += ch
            phone_display_text.value = formatted
            phone_display_text.color = "#064E3B"
            phone_display_text.size = 24
        page.update()

    def num_click(e):
        if is_submitting[0]:
            return
        if len(raw_phone[0]) < 10:
            raw_phone[0] += e.control.data
            update_display()

    def backspace_click(e):
        if is_submitting[0]:
            return
        if len(raw_phone[0]) > 0:
            raw_phone[0] = raw_phone[0][:-1]
            update_display()

    submit_btn = ft.Container(
        content=ft.Text("✓", size=24, color="white", weight="bold"),
        bgcolor="#059669",
        width=76, height=62,
        border_radius=16,
        alignment=ft.Alignment(0, 0),
        data="✓"
    )

    def submit_click(e=None):
        if is_submitting[0]:
            return
        if not raw_phone[0]:
            return

        phone_num = raw_phone[0].strip()
        is_submitting[0] = True

        # ป้องกันการกดซ้ำทันที: ตัด Event Handler + ลด Opacity + แสดง ProgressRing
        submit_btn.on_click = None
        submit_btn.opacity = 0.6
        submit_btn.content = ft.ProgressRing(width=22, height=22, stroke_width=2.5, color="white")
        phone_display_text.value = "กำลังตรวจสอบ..."
        phone_display_text.color = "#059669"
        page.update()

        # Background Worker for Login - NEVER freezes the UI thread!
        def do_login_worker():
            try:
                import requests  # Lazy import requests on-demand
                api_base = get_api_base()
                m_id = get_machine_id()
                payload = {"phonenumber": phone_num}
                response = requests.post(f"{api_base}/user/machines/{m_id}/login", json=payload, timeout=5)
                if response.status_code == 200:
                    res_data = response.json()
                    page.user_token = res_data.get('token')
                    page.member_data = res_data.get('data')
                    server_m_type = res_data.get('data', {}).get('machine_type') or res_data.get('data', {}).get('type')
                    if server_m_type:
                        page.machine_type = server_m_type
                        save_machine_config({"machine_type": server_m_type})
                    # เมื่อสำเร็จ: ให้ค้างสถานะ is_submitting ไว้ เพื่อไม่ให้กดซ้ำระหว่างหน้าจอกำลังเปลี่ยน
                    router.go_action()
                else:
                    def _on_fail():
                        is_submitting[0] = False
                        submit_btn.on_click = submit_click
                        submit_btn.opacity = 1.0
                        submit_btn.content = ft.Text("✓", size=24, color="white", weight="bold")
                        show_alert(page, "ไม่พบหมายเลขนี้ในระบบ โปรดสแกนสมัครสมาชิก", alert_type="error")
                        raw_phone[0] = ""
                        phone_display_text.value = "ไม่พบหมายเลขนี้ในระบบ"
                        phone_display_text.color = "#DC2626"
                        page.update()
                    dispatch_ui(page, _on_fail)
            except Exception as ex:
                print(f"[Home Login] API Error: {ex}")
                def _on_err():
                    is_submitting[0] = False
                    submit_btn.on_click = submit_click
                    submit_btn.opacity = 1.0
                    submit_btn.content = ft.Text("✓", size=24, color="white", weight="bold")
                    show_alert(page, "ไม่สามารถเชื่อมต่อฐานข้อมูลได้", alert_type="error")
                    raw_phone[0] = ""
                    phone_display_text.value = "กรอกเบอร์มือถือ 10 หลัก"
                    phone_display_text.color = "#9CA3AF"
                    page.update()
                dispatch_ui(page, _on_err)

        threading.Thread(target=do_login_worker, daemon=True).start()

    submit_btn.on_click = submit_click

    # ฟังก์ชันสร้างปุ่มตัวเลขบนแป้นพิมพ์
    def create_btn(text, on_click, bg_color="#F9FAFB", text_color="#1F2937"):
        return ft.Container(
            content=ft.Text(text, size=24, color=text_color, weight="bold"),
            bgcolor=bg_color,
            width=76, height=62,
            border_radius=16,
            border=b_all(1, "#E5E7EB") if bg_color == "#F9FAFB" else None,
            alignment=ft.Alignment(0, 0),
            on_click=on_click,
            data=text
        )

    # การ์ดคีย์แพดฝั่งขวา
    phone_input_box = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.PHONE_ANDROID, size=22, color="#059669"),
            phone_display_text
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
        width=280, height=62,
        bgcolor="#F9FAFB",
        border=b_all(2, "#D1FAE5"),
        border_radius=16,
        alignment=ft.Alignment(0, 0)
    )

    register_banner = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.PERSON_ADD, size=18, color="#059669"),
            ft.Text("ยังไม่เป็นสมาชิก? สแกนสมัครเลย", size=14, color="#059669", weight="bold"),
            ft.Icon(ft.icons.Icons.ARROW_FORWARD, size=16, color="#059669")
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
        bgcolor="#ECFDF5",
        border=b_all(1.5, "#A7F3D0"),
        border_radius=14,
        padding=ft.Padding(left=14, right=14, top=8, bottom=8),
        on_click=lambda e: router.go_register()
    )

    keypad_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.Icons.TOUCH_APP, size=22, color="#059669"),
                ft.Text("เข้าสู่ระบบสะสมแต้ม", size=20, color="#064E3B", weight="bold"),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            ft.Text("กรุณากรอกเบอร์โทรศัพท์ของท่าน", size=13, color="#6B7280"),
            ft.Container(height=4),
            phone_input_box,
            ft.Container(height=4),
            ft.Row([create_btn("1", num_click), create_btn("2", num_click), create_btn("3", num_click)], alignment="center", spacing=12),
            ft.Row([create_btn("4", num_click), create_btn("5", num_click), create_btn("6", num_click)], alignment="center", spacing=12),
            ft.Row([create_btn("7", num_click), create_btn("8", num_click), create_btn("9", num_click)], alignment="center", spacing=12),
            ft.Row([
                create_btn("⌫", backspace_click, bg_color="#FEE2E2", text_color="#DC2626"),
                create_btn("0", num_click),
                submit_btn,
            ], alignment="center", spacing=12),
            ft.Container(height=6),
            register_banner
        ], spacing=8, alignment="center", horizontal_alignment="center"),
        bgcolor="white",
        padding=ft.Padding(left=28, right=28, top=24, bottom=24),
        border_radius=24,
        border=b_all(1, "#E5E7EB"),
        width=360,
    )

    home_row = ft.Container(
        content=ft.Row([
            left_col,
            keypad_card
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        expand=True,
        padding=ft.Padding(left=50, right=50, top=40, bottom=30)
    )

    home_stack = ft.Stack([bg_decor_1, bg_decor_2, home_row], expand=True)
    page.add(home_stack)
    page.update()
    try:
        page.window.full_screen = True
        page.window.update()
    except Exception:
        pass
