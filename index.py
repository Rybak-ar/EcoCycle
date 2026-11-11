# -*- coding: utf-8 -*-
"""
EcoCycle Pro - Automated Reverse Vending Machine (Kiosk System)
Normalized Architecture:
- View-Driven Modular Routing
- Lazy Library Imports on Demand
- Non-blocking Background Workers
"""
import os
import sys
import time
import threading
import flet as ft

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

from core.config import load_machine_config, get_machine_type
from views import (
    render_home_view,
    render_action_view,
    render_register_view,
    render_staff_login_view,
    render_dashboard_view,
)


class KioskRouter:
    """Central View-Driven Navigation Controller for Kiosk with Anti-Duplicate Navigation Guard"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._nav_lock = threading.Lock()
        self._is_navigating = False
        self._current_view = None

    def _dispatch(self, nav_action, *args, **kwargs):
        """
        Dispatches navigation safely to the main event loop so that Flet/Flutter 
        immediately processes the UI update without waiting for OS window events.
        """
        try:
            loop = getattr(self.page, 'loop', None)
            if loop and loop.is_running():
                import asyncio
                try:
                    cur_loop = asyncio.get_running_loop()
                except RuntimeError:
                    cur_loop = None
                if cur_loop != loop:
                    loop.call_soon_threadsafe(lambda: nav_action(*args, **kwargs))
                    return
        except Exception as ex:
            print(f"[Router Dispatch Warning]: {ex}")
        nav_action(*args, **kwargs)

    def go_home(self, e=None):
        def _exec():
            with self._nav_lock:
                if self._is_navigating:
                    return
                self._is_navigating = True
            try:
                render_home_view(self.page, self)
                self._current_view = "home"
            finally:
                self._is_navigating = False
        self._dispatch(_exec)

    def go_action(self, e=None):
        def _exec():
            with self._nav_lock:
                if self._is_navigating or self._current_view == "action":
                    return
                self._is_navigating = True
            try:
                render_action_view(self.page, self, e)
                self._current_view = "action"
            finally:
                self._is_navigating = False
        self._dispatch(_exec)

    def go_register(self, e=None):
        def _exec():
            with self._nav_lock:
                if self._is_navigating or self._current_view == "register":
                    return
                self._is_navigating = True
            try:
                render_register_view(self.page, self)
                self._current_view = "register"
            finally:
                self._is_navigating = False
        self._dispatch(_exec)

    def go_staff_login(self, e=None):
        def _exec():
            with self._nav_lock:
                if self._is_navigating or self._current_view == "staff_login":
                    return
                self._is_navigating = True
            try:
                render_staff_login_view(self.page, self)
                self._current_view = "staff_login"
            finally:
                self._is_navigating = False
        self._dispatch(_exec)

    def go_dashboard(self, e=None):
        def _exec():
            with self._nav_lock:
                if self._is_navigating or self._current_view == "dashboard":
                    return
                self._is_navigating = True
            try:
                render_dashboard_view(self.page, self, e)
                self._current_view = "dashboard"
            finally:
                self._is_navigating = False
        self._dispatch(_exec)


def main(page: ft.Page):
    # กำหนดค่าหน้าต่างโปรแกรมหลักให้เปิดเร็วที่สุด
    page.title = "Transform Waste into Renewable Trust"
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#E6FBF2"  # Light Mint theme

    # โหลดฟอนต์ภาษาไทย (Kanit)
    page.fonts = {
        "Kanit": "fonts/Kanit-Regular.ttf"
    }
    page.theme = ft.Theme(font_family="Kanit")
    page.theme_mode = ft.ThemeMode.LIGHT

    # โหมดเต็มจอ Kiosk (True Full Screen Mode)
    page.window.full_screen = True
    page.window.resizable = True
    page.window.focused = True
    try:
        page.window.update()
    except Exception as ex:
        print("[Window] Update error:", ex)

    # คีย์ลัด F11 หรือ Escape สำหรับสลับโหมดเต็มจอ
    def on_keyboard(e: ft.KeyboardEvent):
        if e.key in ("F11", "Escape"):
            page.window.full_screen = not page.window.full_screen
            try:
                page.window.update()
            except Exception:
                pass
    page.on_keyboard_event = on_keyboard

    # กำหนดค่าตัวแปรประจำเครื่อง (Lazy State)
    cfg = load_machine_config()
    page.machine_type = cfg.get("machine_type", "point")
    page.detector = None  # Detector โหลดแบบ Lazy ตอนเข้าสู่หน้ารับขวดจริงเท่านั้น

    # สร้าง Router และแสดงหน้าแรกทันที (Instant Startup < 0.2s)
    router = KioskRouter(page)
    page.router = router
    router.go_home()

    # รับประกันการเปิดเต็มจอ 100% หลัง Windows OS Mount หน้าต่างเสร็จสมบูรณ์
    def force_fullscreen_worker():
        for wait_time in [0.1, 0.4, 0.8, 1.5]:
            time.sleep(wait_time)
            try:
                if not page.window.full_screen:
                    page.window.full_screen = True
                    page.window.update()
            except Exception:
                pass
    threading.Thread(target=force_fullscreen_worker, daemon=True).start()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main, assets_dir="assets")
    else:
        try:
            ft.app(target=main, assets_dir="assets")
        except AttributeError:
            ft.app(main, assets_dir="assets")
