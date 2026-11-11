# -*- coding: utf-8 -*-
import threading
import time
from core.config import get_api_base, get_machine_id

def run_async(func, *args, **kwargs):
    """Run heavy I/O function in a background worker thread"""
    t = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t

class ApiService:
    @staticmethod
    def _get_requests():
        """Lazy import requests only when an API call is made"""
        import requests
        return requests

    @classmethod
    def member_login(cls, phone: str, timeout: float = 3.5):
        """
        Login member by phone number.
        Returns (success: bool, data_or_msg: dict|str, token: str|None)
        """
        requests = cls._get_requests()
        api_base = get_api_base()
        try:
            url = f"{api_base}/member/login"
            res = requests.post(url, json={"phone": phone}, timeout=timeout)
            if res.status_code == 200:
                body = res.json()
                if body.get("status") == "success":
                    return True, body.get("data", {}), body.get("token")
                return False, body.get("message", "เบอร์โทรศัพท์ไม่ถูกต้อง"), None
            return False, f"HTTP Error {res.status_code}", None
        except Exception as ex:
            return False, f"ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้: {ex}", None

    @classmethod
    def member_login_async(cls, phone: str, on_result):
        """Asynchronous member login to prevent UI freezing"""
        def worker():
            success, data, token = cls.member_login(phone)
            on_result(success, data, token)
        run_async(worker)

    @classmethod
    def fetch_machine_config(cls, token: str = None, timeout: float = 2.5):
        """
        Fetch latest rates and configuration for this machine.
        Returns (success: bool, config_dict: dict)
        """
        requests = cls._get_requests()
        api_base = get_api_base()
        m_id = get_machine_id()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            url = f"{api_base}/operator/machines/{m_id}/config?t={time.time()}"
            res = requests.get(url, headers=headers, timeout=timeout)
            if res.status_code == 200:
                body = res.json()
                if body.get("status") == "success":
                    return True, body.get("data", {})
            return False, {}
        except Exception as ex:
            print(f"[API] fetch_machine_config error: {ex}")
            return False, {}

    @classmethod
    def operator_login(cls, phone: str, pin: str, timeout: float = 4.0):
        """
        Staff / Operator login.
        Returns (success: bool, token_or_msg: str)
        """
        requests = cls._get_requests()
        api_base = get_api_base()
        try:
            url = f"{api_base}/operator/login"
            res = requests.post(url, json={"phone": phone, "pin": pin}, timeout=timeout)
            if res.status_code == 200:
                body = res.json()
                if body.get("status") == "success":
                    return True, body.get("token")
                return False, body.get("message", "รหัสผ่านไม่ถูกต้อง")
            return False, f"เข้าสู่ระบบไม่สำเร็จ ({res.status_code})"
        except Exception as ex:
            return False, f"เชื่อมต่อล้มเหลว: {ex}"

    @classmethod
    def operator_login_async(cls, phone: str, pin: str, on_result):
        """Asynchronous operator login"""
        def worker():
            success, res = cls.operator_login(phone, pin)
            on_result(success, res)
        run_async(worker)

    @classmethod
    def fetch_dashboard_summary(cls, token: str, timeout: float = 4.0):
        """Fetch dashboard bottle & member totals"""
        requests = cls._get_requests()
        api_base = get_api_base()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            url = f"{api_base}/operator/dashboard/summary"
            res = requests.get(url, headers=headers, timeout=timeout)
            if res.status_code == 200:
                return True, res.json().get("data", {})
            return False, {}
        except Exception as ex:
            return False, {"error": str(ex)}

    @classmethod
    def fetch_transactions(cls, token: str, page: int = 1, limit: int = 10, timeout: float = 4.0):
        """Fetch paginated transaction logs"""
        requests = cls._get_requests()
        api_base = get_api_base()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            url = f"{api_base}/operator/transactions?page={page}&limit={limit}"
            res = requests.get(url, headers=headers, timeout=timeout)
            if res.status_code == 200:
                return True, res.json()
            return False, {}
        except Exception as ex:
            return False, {"error": str(ex)}

    @classmethod
    def update_machine_config(cls, token: str, payload: dict, timeout: float = 4.0):
        """Save machine reward rates and mode"""
        requests = cls._get_requests()
        api_base = get_api_base()
        m_id = get_machine_id()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            url = f"{api_base}/operator/machines/{m_id}/config"
            res = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if res.status_code == 200:
                return True, res.json()
            return False, res.text
        except Exception as ex:
            return False, str(ex)
