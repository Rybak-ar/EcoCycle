# -*- coding: utf-8 -*-
import flet as ft
import threading
import time

def b_all(width, color):
    """Safe explicit 4-side border for this project's Flet version"""
    return ft.Border(
        top=ft.BorderSide(width, color),
        bottom=ft.BorderSide(width, color),
        left=ft.BorderSide(width, color),
        right=ft.BorderSide(width, color)
    )

def safe_set_icon(ctrl, icon_val):
    """Helper for setting Flet icons safely without crashing on .name"""
    if hasattr(ctrl, 'icon'):
        ctrl.icon = icon_val
    if hasattr(ctrl, 'name'):
        try:
            ctrl.name = icon_val
        except Exception:
            pass

def get_back_btn(on_click_action):
    """Modern Back button for Kiosk"""
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.Icons.ARROW_BACK_IOS_NEW, size=18, color="#064E3B"),
            ft.Text("กลับ", size=18, color="#064E3B", weight="bold")
        ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor="white",
        padding=ft.Padding(left=16, right=20, top=8, bottom=8),
        border_radius=16,
        border=b_all(1, "#E5E7EB"),
        bottom=35, left=40,
        on_click=on_click_action
    )

def dispatch_ui(page: ft.Page, fn):
    """Safely dispatches UI update to Flet main event loop from background threads"""
    if page is None:
        return
    try:
        loop = getattr(page, 'loop', None)
        if loop and loop.is_running():
            import asyncio
            try:
                cur_loop = asyncio.get_running_loop()
            except RuntimeError:
                cur_loop = None
            if cur_loop != loop:
                loop.call_soon_threadsafe(fn)
                return
    except Exception as ex:
        print(f"[Dispatch UI Error]: {ex}")
    try:
        fn()
    except Exception as ex:
        print(f"[Dispatch UI Exec Error]: {ex}")

def show_alert(page: ft.Page, msg: str, alert_type=None, title=None, duration=3.2, bgcolor=None):
    """
    Modern bottom-right Toast Notification matching user's custom design.
    - Success (Green): #A5DC86, checkmark icon, #84B06B bottom accent
    - Error (Red): #F27474, cancel icon, #C25D5D bottom accent
    - Warning (Amber): #FBBF24, warning icon, #D97706 bottom accent
    - Info (Blue): #38BDF8, info icon, #0284C7 bottom accent
    Positioned in bottom-right corner (right=25, bottom=25), compact width 350px.
    """
    if page is None:
        return

    try:
        raw_msg = str(msg or "")
        clean_msg = raw_msg
        for prefix in ["✅", "⚠️", "❌", "ℹ️", "🌐", "🔔", "!"]:
            if clean_msg.startswith(prefix):
                clean_msg = clean_msg[len(prefix):].strip()

        # Deduce type if not explicitly passed
        if alert_type is None:
            if bgcolor:
                bg_l = str(bgcolor).lower()
                if any(k in bg_l for k in ["dc2626", "e53e3e", "ef4444", "red", "fca5a5"]):
                    alert_type = "error"
                elif any(k in bg_l for k in ["059669", "38a169", "10b981", "green", "a5dc86"]):
                    alert_type = "success"
                elif any(k in bg_l for k in ["d97706", "d69e2e", "fbbf24", "f59e0b", "amber", "orange"]):
                    alert_type = "warning"
                elif any(k in bg_l for k in ["0284c7", "2563eb", "38bdf8", "blue"]):
                    alert_type = "info"
            if alert_type is None:
                m_lower = raw_msg.lower()
                if any(w in m_lower for w in ["⚠️", "ผิดพลาด", "ไม่สามารถ", "error", "fail", "สูญหาย", "ขัดข้อง", "ไม่ถูกต้อง", "ไม่พบ"]):
                    alert_type = "error"
                elif any(w in m_lower for w in ["กำลังจัดเก็บ", "รอสักครู่", "เตือน"]):
                    alert_type = "warning"
                elif any(w in m_lower for w in ["✅", "สำเร็จ", "เรียบร้อย", "success"]):
                    alert_type = "success"
                else:
                    alert_type = "info"

        type_configs = {
            "success": {
                "main_bg": "#A5DC86",
                "accent_bg": "#84B06B",
                "icon": ft.icons.Icons.CHECK_CIRCLE,
                "default_title": "Success"
            },
            "error": {
                "main_bg": "#F27474",
                "accent_bg": "#C25D5D",
                "icon": ft.icons.Icons.CANCEL,
                "default_title": "Error"
            },
            "warning": {
                "main_bg": "#FBBF24",
                "accent_bg": "#D97706",
                "icon": ft.icons.Icons.WARNING_ROUNDED,
                "default_title": "Warning"
            },
            "info": {
                "main_bg": "#38BDF8",
                "accent_bg": "#0284C7",
                "icon": ft.icons.Icons.INFO_ROUNDED,
                "default_title": "Info"
            }
        }
        cfg = type_configs.get(alert_type, type_configs["info"])
        display_title = title or cfg["default_title"]

        # Content column
        text_column = ft.Column([
            ft.Text(display_title, color="white", size=16, weight="bold"),
            *( [ft.Text(clean_msg, color="white", size=13, weight="w500", max_lines=2)] if clean_msg and clean_msg != display_title else [] )
        ], spacing=2, expand=True, alignment=ft.MainAxisAlignment.CENTER)

        toast_box = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(cfg["icon"], color="white", size=32),
                        text_column,
                        ft.IconButton(
                            ft.icons.Icons.CLOSE,
                            icon_color="white",
                            icon_size=15,
                            tooltip="ปิด",
                            on_click=lambda e: dismiss_toast()
                        )
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding(left=14, right=10, top=10, bottom=8)
                ),
                # Bottom progress/accent strip matching user screenshots
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            width=150,
                            height=4,
                            bgcolor=cfg["accent_bg"],
                            border_radius=ft.BorderRadius(bottom_left=12, top_left=0, top_right=0, bottom_right=0)
                        )
                    ]),
                    height=4,
                    bgcolor="transparent"
                )
            ], spacing=0),
            bgcolor=cfg["main_bg"],
            border_radius=12,
            width=350,
            right=25,
            bottom=25,
            opacity=1.0,
            animate_opacity=250,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=14,
                color="#33000000",
                offset=ft.Offset(0, 4)
            )
        )

        def dismiss_toast():
            def _do_dismiss():
                try:
                    if toast_box in page.overlay:
                        toast_box.opacity = 0
                        page.update()
                        time.sleep(0.2)
                        if toast_box in page.overlay:
                            page.overlay.remove(toast_box)
                            if getattr(page, "_active_toast", None) == toast_box:
                                page._active_toast = None
                            page.update()
                except Exception:
                    pass

            loop = getattr(page, 'loop', None)
            if loop and loop.is_running():
                import asyncio
                try:
                    cur_loop = asyncio.get_running_loop()
                except RuntimeError:
                    cur_loop = None
                if cur_loop != loop:
                    loop.call_soon_threadsafe(_do_dismiss)
                    return
            _do_dismiss()

        toast_box.on_click = lambda e: dismiss_toast()

        def _do_show():
            try:
                prev_toast = getattr(page, "_active_toast", None)
                if prev_toast:
                    try:
                        if prev_toast in page.overlay:
                            page.overlay.remove(prev_toast)
                    except Exception:
                        pass

                page._active_toast = toast_box
                page.overlay.append(toast_box)
                page.update()
            except Exception as e:
                print(f"[Alert Show Error]: {e}")

        loop = getattr(page, 'loop', None)
        if loop and loop.is_running():
            import asyncio
            try:
                cur_loop = asyncio.get_running_loop()
            except RuntimeError:
                cur_loop = None
            if cur_loop != loop:
                loop.call_soon_threadsafe(_do_show)
            else:
                _do_show()
        else:
            _do_show()

        # Auto-dismiss thread
        def auto_dismiss():
            time.sleep(duration)
            try:
                if getattr(page, "_active_toast", None) == toast_box:
                    dismiss_toast()
            except Exception:
                pass

        threading.Thread(target=auto_dismiss, daemon=True).start()

    except Exception as ex:
        print(f"[Alert] {msg} (Error: {ex})")
