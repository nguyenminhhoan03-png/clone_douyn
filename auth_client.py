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
                    
                if self.token:
                    import base64
                    parts = self.token.split(".")
                    if len(parts) == 3:
                        payload = parts[1]
                        payload += "=" * ((4 - len(payload) % 4) % 4)
                        decoded = json.loads(base64.b64decode(payload))
                        self.user_info = {
                            "username": decoded.get("sub", "default"),
                            "role": decoded.get("role", "user")
                        }
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
                self.get_me()
                return True, "Success"
            else:
                return False, resp.json().get("detail", "Login failed")
        except requests.exceptions.ConnectionError:
            return False, "Không thể kết nối đến Máy chủ (Server đang tắt?)"
        except Exception as e:
            return False, str(e)

    def get_hwid(self) -> str:
        """Lấy HWID duy nhất của máy tính (dựa trên MachineGuid trên Windows hoặc UUID)."""
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
        except Exception:
            pass
        return hashlib.md5(mac.encode()).hexdigest()

    def register(self, username, password):
        try:
            hwid = self.get_hwid()
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

    def is_admin(self) -> bool:
        """Kiểm tra xem user hiện tại có phải là Admin / Super Admin hay không."""
        if not self.user_info:
            return False
        role = str(self.user_info.get("role", "user")).lower()
        return role in ("admin", "super_admin", "superadmin")

    def is_paid_user(self) -> bool:
        """
        Kiểm tra xem user có phải là tài khoản đã mua gói bản quyền hay không.
        - Admin: Mặc định là full, không giới hạn.
        - Role 'vip' hoặc 'pro': Gói trả phí.
        - Plan '1M', '3M', '6M', '1Y', 'LT', 'VIP', 'Pro': Gói trả phí.
        - Gói 'Free': Luôn là gói dùng thử/miễn phí, không phải paid user dù có bao nhiêu ngày.
        """
        if not self.user_info:
            return False
            
        if self.is_admin():
            return True
            
        if self.user_info.get("is_expired", True):
            return False

        plan_name = str(self.user_info.get("plan_name") or "Free").strip().lower()
        role = str(self.user_info.get("role", "user")).strip().lower()

        # Gói Free tuyệt đối không phải là paid_user
        if plan_name == "free":
            if role in ("vip", "pro"):
                return True
            return False
            
        if role in ("vip", "pro") or plan_name in ("vip", "pro", "lt", "trọn đời", "1m", "3m", "6m", "1y"):
            return True
            
        username = self.user_info.get("username", "default")
        clean_user = username.replace("@", "_").replace(".", "_")
        
        # Kiểm tra cache subscription cục bộ
        from config.settings import COOKIES_DIR
        user_dir = COOKIES_DIR / clean_user
        sub_file = user_dir / "subscription.json"
        if sub_file.exists():
            try:
                with open(sub_file, "r", encoding="utf-8") as f:
                    sub_data = json.load(f)
                    if sub_data.get("is_paid") and str(sub_data.get("plan_name", "")).lower() != "free":
                        return True
            except Exception:
                pass
                
        return False

    def mark_user_paid(self, username: str = None, plan_name: str = "VIP"):
        """Đánh dấu vĩnh viễn user này đã nâng cấp gói."""
        uname = username or (self.user_info.get("username", "default") if self.user_info else "default")
        clean_user = uname.replace("@", "_").replace(".", "_")
        from config.settings import COOKIES_DIR
        user_dir = COOKIES_DIR / clean_user
        user_dir.mkdir(parents=True, exist_ok=True)
        sub_file = user_dir / "subscription.json"
        try:
            with open(sub_file, "w", encoding="utf-8") as f:
                json.dump({"username": uname, "is_paid": True, "plan_name": plan_name}, f)
        except Exception:
            pass

    def get_trial_info(self) -> dict:
        """
        Lấy thông tin lượt render của tài khoản:
        - is_unlimited: True nếu là Admin hoặc Gói VIP/Trọn Đời (max_daily_videos >= 9999)
        - max_allowed: số video tối đa mỗi ngày theo cấu hình gói
        - used_count: tổng số video đã render trong ngày hôm nay
        - remaining: số video còn lại có thể render hôm nay
        """
        if self.is_admin():
            return {
                "is_unlimited": True,
                "max_allowed": None,
                "used_count": 0,
                "remaining": 999999,
                "plan_type": "Admin (Toàn quyền)"
            }
            
        from database.db_manager import DatabaseManager
        from datetime import datetime
        db = DatabaseManager()
        username = self.user_info.get("username", "default") if self.user_info else "default"
        clean_user = username.replace("@", "_").replace(".", "_")
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Đếm số video đã xử lý hôm nay theo tài khoản trong database
        user_processed_today = db.get_today_processed_count(username=username)
        
        # 2. Đếm theo mã máy (HWID) hôm nay để chống tạo nhiều tài khoản trên 1 máy
        from config.settings import BASE_DIR
        hw_file = BASE_DIR / "config" / ".hw_trial.json"
        hw_used = 0
        hwid = self.get_hwid()
        if hw_file.exists():
            try:
                with open(hw_file, "r", encoding="utf-8") as f:
                    hw_data = json.load(f)
                    hw_entry = hw_data.get(hwid)
                    if isinstance(hw_entry, dict):
                        if hw_entry.get("date") == today_str:
                            hw_used = hw_entry.get("count", 0)
                    elif isinstance(hw_entry, int):
                        hw_used = hw_data.get(f"{hwid}_{today_str}", 0)
            except Exception:
                pass
                
        used_count = max(user_processed_today, hw_used)
        
        # 3. Lấy hạn mức cấu hình theo gói
        plan_name = str(self.user_info.get("plan_name") or "Free").strip() if self.user_info else "Free"
        role = str(self.user_info.get("role", "user")).strip().lower() if self.user_info else "user"
        
        max_daily = None
        if self.user_info and self.user_info.get("max_daily_videos") is not None:
            try:
                max_daily = int(self.user_info["max_daily_videos"])
            except Exception:
                pass

        if max_daily is None:
            # Fallback đọc từ cấu hình packages đã lưu trong hệ thống
            try:
                _, configs = self.admin_get_config()
                if configs and "packages" in configs:
                    import json
                    pkgs = json.loads(configs["packages"]) if isinstance(configs["packages"], str) else configs["packages"]
                    curr_plan = plan_name.upper()
                    for p in pkgs:
                        p_code = str(p.get("code", "")).upper()
                        p_name_upper = str(p.get("name", "")).upper()
                        if p_code == curr_plan or p_name_upper == curr_plan:
                            max_daily = int(p.get("max_daily_videos", 5))
                            break
            except Exception:
                pass

        if max_daily is None:
            max_daily = 5 if plan_name.lower() == "free" else 9999

        if max_daily >= 9999 or role in ("vip", "super_admin"):
            return {
                "is_unlimited": True,
                "max_allowed": None,
                "used_count": used_count,
                "remaining": 999999,
                "plan_type": f"Gói {plan_name} (Không giới hạn)"
            }

        remaining = max(0, max_daily - used_count)
        return {
            "is_unlimited": False,
            "max_allowed": max_daily,
            "used_count": used_count,
            "remaining": remaining,
            "plan_type": f"Gói {plan_name} ({max_daily} video/ngày)"
        }

    def record_trial_render(self, count: int = 1):
        """Ghi nhận số lượng video đã render hôm nay vào hồ sơ máy tính (HWID)."""
        if self.is_admin() or self.is_paid_user():
            return
            
        from config.settings import BASE_DIR
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        hw_file = BASE_DIR / "config" / ".hw_trial.json"
        hw_file.parent.mkdir(parents=True, exist_ok=True)
        hwid = self.get_hwid()
        hw_data = {}
        if hw_file.exists():
            try:
                with open(hw_file, "r", encoding="utf-8") as f:
                    hw_data = json.load(f)
            except Exception:
                pass
                
        hw_entry = hw_data.get(hwid)
        if isinstance(hw_entry, dict) and hw_entry.get("date") == today_str:
            current = hw_entry.get("count", 0)
        else:
            current = 0
            
        hw_data[hwid] = {
            "date": today_str,
            "count": current + count
        }
        hw_data[f"{hwid}_{today_str}"] = current + count
        try:
            with open(hw_file, "w", encoding="utf-8") as f:
                json.dump(hw_data, f)
        except Exception:
            pass

    def get_me(self):
        if not self.token:
            return False, "Not logged in"
            
        try:
            resp = requests.get(f"{API_BASE_URL}/me", headers={
                "Authorization": f"Bearer {self.token}"
            }, timeout=5)
            
            if resp.status_code == 200:
                self.user_info = resp.json()
                # Tự động đồng bộ trạng thái gói đã mua nếu hợp lệ
                if not self.is_admin():
                    self.is_paid_user()
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

    def test_ollama_connection(self, url="http://localhost:11434"):
        """Kiểm tra kết nối tới Ollama và lấy danh sách model đã tải."""
        import requests as http_requests
        try:
            clean_url = (url or "http://localhost:11434").rstrip("/")
            resp = http_requests.get(f"{clean_url}/api/tags", timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return True, models
            return False, f"HTTP {resp.status_code}: {resp.text[:60]}"
        except Exception as e:
            return False, f"Không thể kết nối đến Ollama: {str(e)}"

    def generate_ai(self, prompt, api_key=None, model=None, provider=None, ollama_url=None, temperature=None):
        import os
        import re
        import requests as http_requests

        def _clean_think(txt: str) -> str:
            if not txt:
                return ""
            # Lọc bỏ toàn bộ đoạn suy nghĩ nội tâm <think>...</think>
            cleaned = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL)
            return cleaned.strip()

        # 1. Xử lý qua Ollama Local nếu được chỉ định
        if provider == "ollama" or (not api_key and os.getenv("AI_PROVIDER") == "ollama"):
            target_url = (ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
            target_model = model or os.getenv("OLLAMA_MODEL", "qwen2.5")

            eff_temp = float(temperature) if temperature is not None else 0.35
            cpu_threads = os.cpu_count() or 8
            ollama_options = {
                "temperature": eff_temp,
                "num_thread": cpu_threads,
                "num_ctx": 4096,
                "num_predict": 2048,
                "stop": ["<think>", "</think>"]
            }

            system_instruction = (
                "You are an elite, native Vietnamese film subtitle and short-video translator. "
                "Translate Chinese dialogue into natural, expressive, lively, and culturally authentic Vietnamese. "
                "Do NOT think, do NOT reason, do NOT output internal thoughts or <think> tags. "
                "Directly output the required ID|text format."
            )

            ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "120"))

            # 1. Gọi trực tiếp native endpoint /api/generate của Ollama (hỗ trợ đầy đủ options tăng tốc)
            try:
                resp = http_requests.post(
                    f"{target_url}/api/generate",
                    json={
                        "model": target_model,
                        "system": system_instruction,
                        "prompt": prompt,
                        "stream": False,
                        "options": ollama_options
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=ollama_timeout
                )
                if resp.status_code == 200:
                    return _clean_think(resp.json().get("response", ""))
            except http_requests.exceptions.Timeout:
                raise Exception(f"Ollama xử lý quá thời gian ({ollama_timeout}s) trên CPU")
            except Exception as e:
                pass

            # 2. Fallback sang OpenAI-compatible endpoint /v1/chat/completions (nếu /api/generate lỗi endpoint)
            try:
                resp = http_requests.post(
                    f"{target_url}/v1/chat/completions",
                    json={
                        "model": target_model,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": eff_temp,
                        "max_tokens": 1024,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=ollama_timeout
                )
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        raw_content = choices[0].get("message", {}).get("content", "")
                        return _clean_think(raw_content)
                else:
                    raise Exception(f"Ollama trả về lỗi {resp.status_code}: {resp.text}")
            except Exception as e:
                raise Exception(f"Lỗi kết nối Ollama ({target_model} tại {target_url}): {str(e)}")

        if api_key:
            # Make direct API calls from the client to avoid backend proxy errors
            if api_key.startswith("gsk_"):
                groq_model = model or "qwen/qwen3.8-27b"
                
                # Groq has a strict 12,000 TPM limit on free tier. 
                # Groq calculates: Requested Tokens = Input Tokens + max_tokens.
                # Since the new prompt is huge (~3500 tokens) and subtitles are ~1000 tokens,
                # setting max_tokens to 8000+ will result in Requested > 12000, causing an instant rejection.
                # Setting max_tokens to 4000 is more than enough for short video subtitles and keeps total < 10000.
                max_tokens = 4000
                
                resp = http_requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": max_tokens
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
            elif api_key.startswith("sk-"):
                # OpenAI / vilao.ai / OpenAI-compatible Proxy
                base_url = (os.getenv("OPENAI_BASE_URL") or os.getenv("CUSTOM_AI_URL") or "https://api.vilao.ai/v1").rstrip("/")
                chosen_model = model or os.getenv("CUSTOM_AI_MODEL") or os.getenv("OPENAI_MODEL") or "gemini-3.6-flash-high"
                
                resp = http_requests.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": chosen_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 4000
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=45
                )
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        raw_content = choices[0].get("message", {}).get("content", "")
                        return _clean_think(raw_content)
                    return ""
                else:
                    raise Exception(f"Lỗi vilao.ai / OpenAI Proxy ({chosen_model}): {resp.text}")
            else:
                # Gemini API (Thử qua SDK trước, nếu lỗi hoặc chưa cài SDK thì gọi thẳng REST API)
                error_msgs = []
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
                        try:
                            model = genai.GenerativeModel(model_name)
                            response = model.generate_content(prompt)
                            if response and response.text:
                                return response.text
                        except Exception as m_err:
                            error_msgs.append(f"{model_name}: {m_err}")
                except Exception as sdk_err:
                    error_msgs.append(f"SDK error: {sdk_err}")

                # REST API fallback trực tiếp không cần thư viện
                for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
                    try:
                        rest_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                        rest_resp = requests.post(
                            rest_url,
                            json={"contents": [{"parts": [{"text": prompt}]}]},
                            headers={"Content-Type": "application/json"},
                            timeout=30
                        )
                        if rest_resp.status_code == 200:
                            data = rest_resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts and "text" in parts[0]:
                                    return parts[0]["text"]
                        else:
                            error_msgs.append(f"REST {model_name} HTTP {rest_resp.status_code}: {rest_resp.text[:100]}")
                    except Exception as rest_err:
                        error_msgs.append(f"REST {model_name} err: {rest_err}")

                raise Exception(f"Lỗi Gemini API: {'; '.join(error_msgs[-2:])}")

        # Fallback: Gọi qua Backend nếu không có API Key riêng
        if not self.token:
            raise Exception("Chưa đăng nhập! Không thể dùng AI.")
            
        payload = {"prompt": prompt}
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

    def admin_reset_hwid(self, user_id):
        """Mở khóa thiết bị máy tính (Reset HWID) cho người dùng."""
        if not self.token: return False, "Not logged in"
        # 1. Thử gọi Cloud API
        try:
            resp = requests.post(f"{API_BASE_URL}/admin/users/{user_id}/reset_hwid", 
                                headers={"Authorization": f"Bearer {self.token}"}, timeout=8)
            if resp.status_code == 200:
                return True, resp.json().get("message", "Reset HWID thành công!")
        except Exception:
            pass
        # 2. Fallback local DB
        try:
            from pathlib import Path
            import sys
            backend_dir = Path(__file__).parent / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            import models
            models.init_db()
            db = models.SessionLocal()
            u = db.query(models.User).filter(models.User.id == user_id).first()
            if u:
                u.hwid = None
                db.commit()
                db.close()
                return True, f"Đã mở khóa thiết bị (Reset HWID) thành công cho '{u.username}'."
            db.close()
            return False, "Không tìm thấy User."
        except Exception as e:
            return False, str(e)

    def admin_get_config(self):
        if not self.token: return False, "Not logged in"
        # 1. Cloud API
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/config", 
                              headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if resp.status_code == 200: return True, resp.json()
        except Exception:
            pass
        # 2. Local fallback
        try:
            from pathlib import Path
            import sys
            backend_dir = Path(__file__).parent / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            import models
            models.init_db()
            db = models.SessionLocal()
            configs = db.query(models.SystemConfig).all()
            res = {c.key: c.value for c in configs}
            db.close()
            return True, res
        except Exception as e:
            return False, str(e)

    def admin_save_config(self, data):
        if not self.token: return False, "Not logged in"
        # 1. Cloud API
        try:
            resp = requests.put(f"{API_BASE_URL}/admin/config", json=data,
                              headers={"Authorization": f"Bearer {self.token}"}, timeout=8)
            if resp.status_code == 200: return True, resp.json().get("message", "Đã lưu thành công!")
        except Exception:
            pass
        # 2. Local fallback
        try:
            from pathlib import Path
            import sys
            backend_dir = Path(__file__).parent / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            import models
            models.init_db()
            db = models.SessionLocal()
            for k, v in data.items():
                val_str = str(v) if not isinstance(v, str) else v
                cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == k).first()
                if cfg: cfg.value = val_str
                else: db.add(models.SystemConfig(key=k, value=val_str))
            
            # Đồng bộ bảng plans
            if "packages" in data:
                try:
                    import json
                    pkgs = json.loads(data["packages"]) if isinstance(data["packages"], str) else data["packages"]
                    for p in pkgs:
                        p_code = str(p.get("code", "")).strip()
                        p_name = str(p.get("name", "")).strip()
                        p_max = int(p.get("max_daily_videos", 5))
                        p_ai = bool(p.get("can_use_ai", True))
                        p_price = float(p.get("price", 0))

                        plan_name_target = "Free" if p_code.upper() == "FREE" else p_name
                        plan = db.query(models.Plan).filter(models.Plan.name == plan_name_target).first()
                        if not plan and p_code.upper() != "FREE":
                            plan = db.query(models.Plan).filter(models.Plan.name == p_code).first()
                        if plan:
                            plan.max_daily_videos = p_max
                            plan.can_use_ai_script = p_ai
                            plan.price = p_price
                        else:
                            db.add(models.Plan(name=plan_name_target, max_daily_videos=p_max, can_use_ai_script=p_ai, price=p_price))
                except Exception:
                    pass
            db.commit()
            db.close()
            return True, "Đã lưu cấu hình vào hệ thống thành công!"
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

    def send_feedback(self, rating: int = 5, category: str = "Đánh giá", content: str = ""):
        """Gửi đánh giá & góp ý của người dùng lên server (hỗ trợ fallback local database)."""
        if not self.token:
            return False, "Bạn chưa đăng nhập! Vui lòng đăng nhập để gửi góp ý."
        # 1. Thử gửi lên Cloud API
        try:
            resp = requests.post(f"{API_BASE_URL}/api/feedback", json={
                "rating": rating,
                "category": category,
                "content": content
            }, headers={"Authorization": f"Bearer {self.token}"}, timeout=8)
            if resp.status_code == 200:
                return True, resp.json().get("message", "Gửi góp ý thành công!")
        except Exception:
            pass

        # 2. Fallback: Lưu trực tiếp vào SQLite database cục bộ (nếu Cloud API VPS chưa cập nhật endpoint)
        try:
            import sys
            from datetime import datetime
            backend_dir = Path(__file__).parent / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            import models
            models.init_db()
            db = models.SessionLocal()
            u_name = self.user_info.get("username", "anonymous") if self.user_info else "anonymous"
            new_fb = models.Feedback(
                username=u_name,
                rating=max(1, min(5, rating)),
                category=category or "Đánh giá",
                content=content.strip(),
                created_at=datetime.utcnow()
            )
            db.add(new_fb)
            db.commit()
            db.close()
            return True, "Cảm ơn bạn đã gửi đánh giá & góp ý! Ý kiến của bạn đã được ghi nhận."
        except Exception as e:
            return False, f"Lỗi lưu đánh giá: {e}"

    def admin_get_feedbacks(self):
        """Lấy danh sách đánh giá & thống kê cho Admin (hỗ trợ fallback local database)."""
        if not self.token:
            return False, "Not logged in"
        # 1. Thử lấy từ Cloud API
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/feedbacks", headers={"Authorization": f"Bearer {self.token}"}, timeout=8)
            if resp.status_code == 200:
                return True, resp.json()
        except Exception:
            pass

        # 2. Fallback: Đọc từ SQLite database cục bộ
        try:
            import sys
            from datetime import datetime
            backend_dir = Path(__file__).parent / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            import models
            models.init_db()
            db = models.SessionLocal()
            feedbacks = db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()
            total = len(feedbacks)
            avg_rating = round(sum(f.rating for f in feedbacks) / total, 1) if total > 0 else 5.0
            results = []
            for f in feedbacks:
                results.append({
                    "id": f.id,
                    "username": f.username,
                    "rating": f.rating,
                    "category": f.category,
                    "content": f.content,
                    "created_at": f.created_at.strftime("%d/%m/%Y %H:%M") if f.created_at else ""
                })
            db.close()
            return True, {
                "total": total,
                "avg_rating": avg_rating,
                "feedbacks": results
            }
        except Exception as e:
            return False, str(e)

# Global instance
auth_client = AuthClient()
