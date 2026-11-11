# -*- coding: utf-8 -*-
import threading

class DetectorService:
    _instance = None
    _is_initializing = False
    _init_lock = threading.Lock()

    @classmethod
    def get_detector(cls, auto_create: bool = True):
        """
        Lazy load and return BottleDetector instance.
        Only imports ai_detector when this function is called.
        """
        if cls._instance is not None:
            return cls._instance

        if not auto_create:
            return None

        with cls._init_lock:
            if cls._instance is None:
                print("[DetectorService] Lazy importing BottleDetector (on-demand)...")
                try:
                    from ai_detector import BottleDetector
                    cls._instance = BottleDetector()
                    print("[DetectorService] BottleDetector initialized successfully.")
                except Exception as ex:
                    print(f"[DetectorService] Failed to initialize BottleDetector: {ex}")
                    return None
        return cls._instance

    @classmethod
    def init_in_background(cls, on_ready=None):
        """Pre-warm or initialize detector in a background thread without blocking UI"""
        def worker():
            d = cls.get_detector(auto_create=True)
            if on_ready:
                on_ready(d)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t

    @classmethod
    def stop_detector(cls):
        """Stop detector safely if running"""
        if cls._instance is not None:
            try:
                cls._instance.stop()
            except Exception as ex:
                print(f"[DetectorService] Error stopping detector: {ex}")

    @classmethod
    def tare_scale(cls):
        """Tare loadcell scale"""
        d = cls.get_detector(auto_create=False)
        if d:
            try:
                d.tare_scale()
                return True
            except Exception as ex:
                print(f"[DetectorService] Tare error: {ex}")
        return False

    @classmethod
    def reconnect_camera(cls):
        """Reconnect camera"""
        d = cls.get_detector(auto_create=False)
        if d:
            try:
                return d.reconnect_camera()
            except Exception as ex:
                print(f"[DetectorService] Camera reconnect error: {ex}")
        return False
