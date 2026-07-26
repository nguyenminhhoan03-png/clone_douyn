import requests
import json
import os
from pathlib import Path

# Cấu hình API Server
API_BASE_URL = "http://localhost:8000"
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

    def generate_ai(self, prompt):
        if not self.token:
            raise Exception("Chưa đăng nhập! Không thể dùng AI.")
            
        resp = requests.post(f"{API_BASE_URL}/ai/generate", json={
            "prompt": prompt
        }, headers={
            "Authorization": f"Bearer {self.token}"
        }, timeout=15)
        
        if resp.status_code == 200:
            return resp.json().get("text", "")
        else:
            raise Exception(f"Lỗi AI Server: {resp.text}")

    # ── ADMIN APIs ───────────────────────────────────────────────────────────
    def admin_get_users(self):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/users", headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_create_user(self, username, password, role="user", plan_name="Free"):
        if not self.token: return False, "Not logged in"
        try:
            resp = requests.post(f"{API_BASE_URL}/admin/users", json={
                "username": username,
                "password": password,
                "role": role,
                "plan_name": plan_name
            }, headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
            return False, resp.json().get("detail", "Error")
        except Exception as e:
            return False, str(e)

    def admin_update_user(self, user_id, password=None, role=None, plan_name=None):
        if not self.token: return False, "Not logged in"
        data = {}
        if password: data["password"] = password
        if role: data["role"] = role
        if plan_name: data["plan_name"] = plan_name
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

# Global instance
auth_client = AuthClient()
