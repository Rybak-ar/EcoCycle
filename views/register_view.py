# -*- coding: utf-8 -*-
import flet as ft
from core.ui_utils import b_all, get_back_btn

def render_register_view(page: ft.Page, router):
    page.controls.clear()
    
    # องค์ประกอบตกแต่งพื้นหลัง
    bg_decor_1 = ft.Container(
        width=500, height=500, border_radius=250,
        bgcolor="#D1FAE5", top=-150, right=-100
    )
    bg_decor_2 = ft.Container(
        width=350, height=350, border_radius=175,
        bgcolor="#DEF7EC", bottom=-100, left=-80
    )
    
    # Top App Bar
    top_bar = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.Icons.AUTORENEW, size=28, color="#38A169"),
                ft.Text("EcoCycle Pro", size=24, color="#064E3B", weight="bold")
            ], spacing=10),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.Icons.PERSON_ADD, size=18, color="#38A169"),
                    ft.Text("ลงทะเบียนสมาชิกใหม่", size=14, color="#064E3B", weight="bold"),
                ], spacing=6),
                bgcolor="white",
                padding=ft.Padding(left=14, right=16, top=6, bottom=6),
                border_radius=20,
                border=b_all(1, "#CBD5E0")
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        left=40, right=40, top=25
    )

    # ฝั่งซ้าย: คำแนะนำและขั้นตอนการสมัคร
    badge = ft.Container(
        content=ft.Text("✨ สมาชิกใหม่รับสิทธิประโยชน์ทันที", size=13, color="#276749", weight="bold"),
        bgcolor="#C6F6D5",
        padding=ft.Padding(left=12, right=12, top=4, bottom=4),
        border_radius=12
    )
    main_title = ft.Text("สมัครสมาชิกง่ายๆ\nเพียงสแกน QR Code", size=32, color="#064E3B", weight="bold")
    sub_title = ft.Text("เปิดกล้องมือถือหรือแอป Line เพื่อลงทะเบียนใน 1 นาที\nสะสมแต้มทุกการหยอดขวด แลกรับเงินสดหรือของรางวัล", size=14, color="#4A5568")

    def build_step(title, desc, icon):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, size=22, color="#38A169"),
                    bgcolor="#E6FBF2",
                    width=42, height=42,
                    border_radius=21,
                    alignment=ft.Alignment(0, 0)
                ),
                ft.Column([
                    ft.Text(title, size=14, color="#064E3B", weight="bold"),
                    ft.Text(desc, size=12, color="#718096"),
                ], spacing=2, expand=True)
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor="white",
            border_radius=14,
            padding=ft.Padding(left=14, right=14, top=8, bottom=8),
            border=b_all(1, "#E2E8F0")
        )

    steps_column = ft.Column([
        build_step("1. สแกน QR Code บนหน้าจอ", "เปิดแอป Line หรือกล้องถ่ายรูปสแกนภาพด้านขวา", ft.icons.Icons.QR_CODE_SCANNER),
        build_step("2. กรอกเบอร์โทรศัพท์และชื่อ", "ลงทะเบียนผ่านมือถือ ไม่ต้องดาวน์โหลดแอปพลิเคชัน", ft.icons.Icons.PHONE_ANDROID),
        build_step("3. นำเบอร์มากรอกที่ตู้เพื่อเริ่มใช้งาน", "ใส่ขวด สะสมแต้ม และแลกรับของรางวัลได้ทันที", ft.icons.Icons.STARS)
    ], spacing=8)

    left_panel = ft.Container(
        content=ft.Column([
            badge,
            main_title,
            sub_title,
            ft.Container(height=4),
            steps_column
        ], spacing=6),
        width=480
    )

    # ฝั่งขวา: Card แสดง QR Code
    qr_code_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.Icons.QR_CODE_2, size=20, color="#38A169"),
                    bgcolor="#E6FBF2", width=34, height=34, border_radius=17, alignment=ft.Alignment(0, 0)
                ),
                ft.Column([
                    ft.Text("Scan to Register", size=18, color="#064E3B", weight="bold"),
                    ft.Text("สแกนด้วยสมาร์ตโฟนของคุณ", size=12, color="#718096")
                ], spacing=0)
            ], spacing=8),
            ft.Container(height=2),
            ft.Container(
                content=ft.Image(src="qr-code.png", width=220, height=220, fit="contain"),
                bgcolor="white",
                padding=12,
                border_radius=20,
                border=b_all(2, "#38A169"),
                alignment=ft.Alignment(0, 0)
            ),
            ft.Container(height=2),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.Icons.CHECK_CIRCLE, size=15, color="#38A169"),
                    ft.Text("เปิดรับลงทะเบียนตลอด 24 ชั่วโมง", size=12, color="#064E3B", weight="bold")
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                bgcolor="#E6FBF2",
                padding=ft.Padding(left=12, right=12, top=6, bottom=6),
                border_radius=12
            ),
            ft.Text("รองรับทั้ง iOS และ Android ทุกเครือข่าย", size=11, color="#A0AEC0", text_align="center")
        ], horizontal_alignment="center", spacing=6),
        bgcolor="white",
        border_radius=24,
        padding=ft.Padding(left=26, right=26, top=18, bottom=18),
        border=b_all(1, "#CBD5E0"),
        width=340
    )

    # เนื้อหากลางหน้าจอ
    main_content = ft.Container(
        content=ft.Row([
            left_panel,
            qr_code_card
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        left=60, right=60, top=80, bottom=90
    )

    # ปุ่มย้อนกลับ
    back_btn = get_back_btn(lambda e: router.go_home())

    register_stack = ft.Stack([
        bg_decor_1,
        bg_decor_2,
        top_bar,
        main_content,
        back_btn
    ], expand=True)

    page.add(register_stack)
    page.update()
