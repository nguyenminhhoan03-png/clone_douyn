import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Cho phép đọc thẳng URL từ .env (để dùng được domain như http://douyn-api.muabanwebsite.io.vn)
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    # Nếu không có file .env đi kèm file EXE, mặc định sẽ gọi lên subdomain này:
    API_BASE_URL = "http://douyn-api.muabanwebsite.io.vn"
SESSION_FILE = Path(__file__).parent / "config" / "session.json"

class AuthClient:
    def __init__(self):
        self.token = None
        self.user_info = None
        self.load_session()

    def load_session(self):
        if SESSION_FILE.exists():
            try:
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                    self.token = data.get("access_token")
            except:
                pass

    def save_session(self):
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w") as f:
            json.dump({"access_token": self.token}, f)

    def clear_session(self):
        self.token = None
        self.user_info = None
        if SESSION_FILE.exists():
            SESSION_FILE.unlink(missing_ok=True)
            
    def logout(self):
        self.clear_session()
        return True

    def login(self, username, password):
        try:
            resp = requests.post(f"{API_BASE_URL}/login", data={
                "username": username,
                "password": password
            }, timeout=5)
            
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                self.save_session()
                return True, "Success"
            else:
                return False, resp.json().get("detail", "Login failed")
        except requests.exceptions.ConnectionError:
            return False, "Không thể kết nối đến Máy chủ (Server đang tắt?)"
        except Exception as e:
            return False, str(e)

    def register(self, username, password):
        try:
            import uuid
            import hashlib
            
            import platform
            
            mac = str(uuid.getnode())
            try:
                if platform.system() == "Windows":
                    import winreg
                    registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                    key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                    mac, _ = winreg.QueryValueEx(key, "MachineGuid")
            except:
                pass
            hwid = hashlib.md5(mac.encode()).hexdigest()
            
            resp = requests.post(f"{API_BASE_URL}/register", json={
                "username": username,
                "password": password,
                "role": "user",
                "hwid": hwid
            }, timeout=5)
            
            if resp.status_code == 200:
                return True, "Đăng ký thành công! Bạn có thể đăng nhập."
            else:
                return False, resp.json().get("detail", "Đăng ký thất bại")
        except requests.exceptions.ConnectionError:
            return False, "Không thể kết nối đến Máy chủ (Server đang tắt?)"
        except Exception as e:
            return False, str(e)

    def get_me(self):
        if not self.token:
            return False, "Not logged in"
            
        try:
            resp = requests.get(f"{API_BASE_URL}/me", headers={
                "Authorization": f"Bearer {self.token}"
            }, timeout=5)
            
            if resp.status_code == 200:
                self.user_info = resp.json()
                return True, self.user_info
            else:
                self.clear_session()
                return False, "Session expired"
        except Exception as e:
            return False, str(e)

    def sync_douyin_cookie(self):
        if not self.token:
            return False, "Not logged in"
            
        try:
            resp = requests.get(f"{API_BASE_URL}/api/system/douyin-cookie", headers={
                "Authorization": f"Bearer {self.token}"
            }, timeout=10)
            
            if resp.status_code == 200:
                cookie_str = resp.json().get("cookie", "")
                if cookie_str:
                    from config.settings import COOKIES_DIR
                    cookie_path = COOKIES_DIR / "douyin_cookies.txt"
                    # Lưu file cookie đè lên bản cũ
                    with open(cookie_path, "w", encoding="utf-8") as f:
                        f.write(cookie_str)
                    return True, "Synced"
            return False, "Failed to sync"
        except Exception as e:
            return False, str(e)

    def track_usage(self, action_type):
        if not self.token:
            return False, "Not logged in"
            
        try:
            resp = requests.post(f"{API_BASE_URL}/track", json={
                "action_type": action_type
            }, headers={
                "Authorization": f"Bearer {self.token}"
            }, timeout=5)
            
            if resp.status_code == 200:
                return True, resp.json()
            elif resp.status_code == 403:
                return False, "HẾT LƯỢT TRONG NGÀY (Quota Exceeded)!"
            else:
                return False, resp.json().get("detail", "Track failed")
        except Exception as e:
            return False, str(e)

    def generate_ai(self, prompt, api_key=None):
        if not self.token:
            raise Exception("Chưa đăng nhập! Không thể dùng AI.")
            
        payload = {"prompt": prompt}
        if api_key:
            payload["api_key"] = api_key
            
        resp = requests.post(f"{API_BASE_URL}/ai/generate", json=payload, headers={
            "Authorization": f"Bearer {self.token}"
        }, timeout=15)
        
        if resp.status_code == 200:
            return resp.json().get("text", "")
        else:
            raise Exception(f"Lỗi AI Server: {resp.text}")

    # ── TELEMETRY ────────────────────────────────────────────────────────────
    def send_telemetry(self, action_type: str, details: str = None):
        """Gửi log hoạt động ngầm lên server (Non-blocking)"""
        if not self.token: return

        def _do_send():
            try:
                requests.post(f"{API_BASE_URL}/api/telemetry", json={
                    "action_type": action_type,
                    "details": details
                }, headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            except:
                pass # Bỏ qua mọi lỗi để không ảnh hưởng app chính
                
        import threading
        threading.Thread(target=_do_send, daemon=True).start()

    # ── ADMIN APIs ───────────────────────────────────────────────────────────
    def admin_get_users(self):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/users", headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_create_user(self, username, password, role="user", days_to_add=30):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.post(f"{API_BASE_URL}/admin/users", json={
                "username": username,
                "password": password,
                "role": role,
                "days_to_add": days_to_add
            }, headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_update_user(self, user_id, password=None, role=None, days_to_add=None):
        if not self.token: return False, "Not logged in"
        data = {}
        if password: data["password"] = password
        if role: data["role"] = role
        if days_to_add: data["days_to_add"] = days_to_add
        try:
            resp = requests.put(f"{API_BASE_URL}/admin/users/{user_id}", json=data, 
                              headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_delete_user(self, user_id):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.delete(f"{API_BASE_URL}/admin/users/{user_id}", 
                                 headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_get_config(self):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/config", 
                              headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_save_config(self, data):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.put(f"{API_BASE_URL}/admin/config", json=data,
                              headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_get_stats(self):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/stats", headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_get_logs(self, limit=100):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.get(f"{API_BASE_URL}/api/admin/logs?limit={limit}", headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)
            
    def get_payment_info(self):
        try:
            resp = requests.get(f"{API_BASE_URL}/payment/info", timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, "Error fetching payment info"
        except Exception as e:
            return False, str(e)

# Global instance
auth_client = AuthClient()
