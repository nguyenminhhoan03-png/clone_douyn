"""
Livestream Seeder — Tự động vào xem Livestream TikTok để Buff mắt xem.
Sử dụng Playwright browser automation, kế thừa hạ tầng Anti-Detect từ TikTokUploader.
"""
import asyncio
import json
import random
import time
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, List

from loguru import logger

_camoufox_init_lock = None

# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════
class LiveStatus(Enum):
    LIVE_ACTIVE = "active"
    LIVE_ENDED = "ended"
    LIVE_RESTRICTED = "restricted"
    LIVE_ERROR = "error"
    LIVE_NOT_FOUND = "not_found"
    LIVE_BLOCKED_403 = "blocked_403"


DEFAULT_COMMENTS = [
    "🔥🔥🔥", "Hay quá", "Xinh quá", "Ủng hộ nè", "❤️❤️",
    "Cố lên", "Đỉnh quá", "Người đẹp", "💯💯", "Tuyệt vời",
    "Quá đỉnh luôn", "Xin chào", "👏👏👏", "Dễ thương quá",
    "Live hay quá", "Ở lại xem tiếp", "🎉🎉", "Chào mọi người",
    "Like mạnh", "Quá xịn", "Thích quá đi", "Share cho bạn bè nào",
]

DEFAULT_LIVESTREAM_CONFIG = {
    "heart_interval": (10, 30),
    "comment_interval": (60, 180),
    "comments": DEFAULT_COMMENTS,
    "comment_enabled": True,
    "share_enabled": False,
    "share_interval": (300, 600),
    "auto_reconnect": True,
    "max_reconnect_attempts": 3,
    "duration_minutes": 30,
    "max_concurrent": 5,
}

# Fallback selector chains — TikTok thường xuyên đổi DOM
_SELECTORS = {
    "heart_button": [
        '[data-e2e="room-chat-like-btn"]',
        '[data-e2e="like-icon"]',
        '[data-e2e="live-like-icon"]',
        'button[class*="heart"]',
        'div[class*="like-btn"]',
        'div[class*="DivLikeButton"]',
        '[class*="bottom-like"]',
        'div[data-e2e="live-video"]', # Fallback: Double click video sends heart
        'video' # Fallback: Double click video
    ],
    "comment_input": [
        '[data-e2e="room-chat-input-field"]',
        '[data-e2e="comment-input"]',
        '[data-e2e="chat-input"]',
        'div[contenteditable="true"]',
        'div[contenteditable="plaintext-only"]',
        '[class*="public-DraftEditor-content"]',
        'input[placeholder*="Say something"]',
        'input[placeholder*="Nhập bình luận"]',
        'input[placeholder*="bình luận"]',
        'input[placeholder*="Type"]',
        'div[class*="chat-input"] input',
        'div[class*="DivInputContainer"] input',
        'input[class*="Input"]',
    ],
    "comment_send": [
        '[data-e2e="comment-send"]',
        'button[class*="send"]',
        'div[class*="DivSendButton"]',
    ],
    "live_badge": [
        # Nhắm thẳng vào Avatar (Vì nếu họ đang Live, bấm Avatar sẽ vào thẳng phòng Live)
        '[data-e2e="user-avatar"]',
        '[data-e2e="user-avatar"] [class*="live-ring"]',
        '[data-e2e="user-avatar"] [class*="live-badge"]',
        'a[href*="/live"] [data-e2e="user-avatar"]',
        'a[href*="/live"]',
        '[data-e2e="live-badge"]',
        'span:text-is("LIVE")',
        'span:text-is("Live")',
    ],
    "live_ended": [
        'text="LIVE has ended"',
        'text="Phiên LIVE đã kết thúc"',
        'text="has ended"',
        'text="đã kết thúc"',
        'text="Replay"',
        'text="phát lại"',
        'div[class*="EndedContainer"]',
        'div[class*="LiveEnded"]',
    ],
    "viewer_count": [
        '[data-e2e="viewer-count"]',
        'span[class*="viewer"]',
        'div[class*="ViewerCount"]',
    ],
    "share_button": [
        '[data-e2e="share-icon"]',
        'button[class*="share"]',
        'div[class*="DivShareButton"]',
    ],
    "close_popup": [
        'button:has-text("OK")',
        'button:has-text("Đã hiểu")',
        'button:has-text("Got it")',
        'button:has-text("Đóng")',
        'button:has-text("Close")',
        '[aria-label="Close"]',
        '[aria-label="Đóng"]',
        'button:has-text("Not now")',
        'button:has-text("Để sau")',
        'button:has-text("Dismiss")',
        'button:has-text("Skip")',
        'button:has-text("Bỏ qua")',
    ],
    "login_popup": [
        'button:has-text("Đăng nhập")',
        'button:has-text("Log in")',
        '[data-e2e="login-banner-close"]',
        'div[class*="LoginBanner"] [class*="close"]',
        'div[class*="login"] [class*="close"]',
    ],
    "follow_button": [
        '[data-e2e="live-follow-button"]',
        'button:has-text("Follow")',
        'button:has-text("Theo dõi")',
        'div[class*="FollowButton"]',
    ],
}


class LivestreamSeeder:
    """Engine xem Livestream TikTok tự động — dùng Playwright."""

    def __init__(self, cookies_file: str = None, proxy: str = None, window_idx: int = 0):
        self.cookies_file = cookies_file
        self.proxy = proxy
        self.window_idx = window_idx
        self.context = None
        self.page = None
        self._playwright = None

        # Stats
        self.hearts_sent = 0
        self.comments_sent = 0
        self.shares_done = 0
        self.is_watching = False

    # ──────────────────────────────────────────────────────────────────────────
    #  Browser Init — Kế thừa 100% logic từ TikTokUploader._init_browser()
    # ──────────────────────────────────────────────────────────────────────────
    async def _init_browser(self):
        """Khởi tạo trình duyệt qua CDP để vượt mặt hệ thống chống Bot của TikTok Live."""
        global _camoufox_init_lock
        if _camoufox_init_lock is None:
            _camoufox_init_lock = asyncio.Lock()

        from uploader.tiktok_uploader import (
            _VIEWPORTS, _USER_AGENTS, _LOCALES, get_anti_detect_script
        )
        from config.settings import TIKTOK_CONFIG
        import os
        import subprocess
        import socket
        import tempfile
        from pathlib import Path
        import hashlib

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("Playwright chưa cài! Chạy: pip install playwright")

        self._playwright = await async_playwright().start()
        browser_config = TIKTOK_CONFIG.get("browser", {})
        engine = TIKTOK_CONFIG.get("antidetect", {}).get("engine", "built-in")
        
        if engine == "adspower":
            await self._connect_adspower()
            return
        elif engine == "hubstudio":
            await self._connect_adspower(is_hubstudio=True)
            return
        elif engine == "dolphin":
            await self._connect_dolphin()
            return
        elif engine == "cloakbrowser":
            await self._connect_cloakbrowser()
            return
            
        if not self.cookies_file or not Path(self.cookies_file).exists():
            logger.error(f"❌ [DEBUG] Không tìm thấy file cookies: {self.cookies_file}")
            return

        profile_name = Path(self.cookies_file).stem if self.cookies_file else "default"
        import hashlib
        seed = int(hashlib.md5(profile_name.encode('utf-8')).hexdigest(), 16)
        rng = random.Random(seed)
        fp_timezone = "Asia/Ho_Chi_Minh"
        fp_locale = rng.choice(_LOCALES)
        
        cookie_path = Path(self.cookies_file) if self.cookies_file else Path("default.json")
        profile_dir = cookie_path.parent / ".profiles" / cookie_path.stem
        profile_dir.mkdir(parents=True, exist_ok=True)

        win_w = 1200
        win_h = 800
        max_cols = 1920 // 450
        
        if max_cols == 0: max_cols = 1
        row = self.window_idx // max_cols
        col = self.window_idx % max_cols
        pos_x = col * 450 + 20
        pos_y = row * 50 + 20

        try:
            from camoufox.async_api import AsyncCamoufox
            import warnings
            warnings.filterwarnings("ignore", message=".*geoip.*")
            warnings.filterwarnings("ignore", message=".*locale region.*")
            warnings.filterwarnings("ignore", category=ResourceWarning)
        except ImportError:
            raise Exception("Chưa cài Camoufox! Hãy mở Terminal và chạy: pip install camoufox[geoip]")

        import os
        from pathlib import Path
        custom_env = os.environ.copy()
        
        # BẮT BUỘC: Tạo thư mục profile riêng để lưu cứng Fingerprint. 
        user_dir = Path("user_data")
        user_dir.mkdir(exist_ok=True)
        profile_dir = user_dir / f"profile_{profile_name}"
        
        # Xoá tận gốc thư mục profile cũ để tẩy sạch bộ nhớ đệm (prefs.js) chứa lỗi chặn mạng
        if profile_dir.exists():
            try:
                import shutil
                shutil.rmtree(profile_dir, ignore_errors=True)
                logger.info("🗑️ Đã xóa sạch profile cũ để tẩy trắng cài đặt lỗi mạng.")
            except Exception:
                pass
                
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Bắt buộc tắt Sandbox để Camoufox không bị crash trên máy này (Đã đồng bộ với lúc Login nên không sợ lệch vân tay)
        os.environ["MOZ_DISABLE_CONTENT_SANDBOX"] = "1"
        os.environ["MOZ_DISABLE_GPU_SANDBOX"] = "1"
        camoufox_args = {
            "headless": False,  # BẮT BUỘC False với Camoufox trên máy này để tránh crash I/O Pipe
            "geoip": False,
            "persistent_context": True,
            "user_data_dir": str(profile_dir),
            "args": []
        }

        if self.proxy:
            proxy_str = self.proxy.strip()
            if proxy_str.startswith("http://") or proxy_str.startswith("socks5://"):
                camoufox_args["proxy"] = {"server": proxy_str}
            else:
                parts = proxy_str.split(":")
                if len(parts) == 4:
                    ip, port, user, pwd = parts
                    camoufox_args["proxy"] = {
                        "server": f"http://{ip}:{port}",
                        "username": user,
                        "password": pwd
                    }
                elif len(parts) == 2:
                    camoufox_args["proxy"] = {"server": f"http://{parts[0]}:{parts[1]}"}
            logger.info(f"🌐 [Seeder] Sử dụng proxy cho Camoufox: {proxy_str[:30]}...")
        else:
            # Ép Firefox KHÔNG dùng System Proxy của Windows (tránh lỗi Proxy server is refusing connections)
            # Dùng 'per-context' để bỏ qua proxy hệ thống
            camoufox_args["proxy"] = {"server": "per-context"}

        try:
            logger.info(f"🦊 [DEBUG] Chuẩn bị khởi động Camoufox cho profile: {profile_name}...")
            
            # Chỉ khóa duy nhất thao tác spawn tiến trình trình duyệt để tránh đụng độ file hệ thống
            logger.info(f"⏳ [DEBUG] Đang chờ cấp quyền khởi động (Lock)...")
            async with _camoufox_init_lock:
                logger.info(f"🔓 [DEBUG] Đã nhận quyền khởi động! Bắt đầu mở Camoufox...")
                self.camoufox = AsyncCamoufox(**camoufox_args)
                logger.info(f"⏳ [DEBUG] Đang đợi Camoufox.start()...")
                result = await self.camoufox.start()
            
            # Giải phóng lock ngay sau khi tiến trình đã chạy, cho phép các tiến trình khác bung lên song song
            if hasattr(result, "new_context"):
                self.browser = result
                logger.info(f"⏳ [DEBUG] Đang đợi self.browser.new_context()...")
                self.context = await self.browser.new_context()
            else:
                self.browser = None
                self.context = result
            logger.info(f"✅ [DEBUG] Đã tạo xong browser context!")
            
            logger.info("🛡️ [DEBUG] Camoufox đã kích hoạt! Bắt đầu nạp Cookies...")
            await self._load_cookies()
            logger.info("⏳ [DEBUG] Lấy danh sách pages hiện tại...")
            pages = self.context.pages
            logger.info(f"⏳ [DEBUG] Có {len(pages)} pages. Đang mở page chính...")
            if not pages:
                logger.info("⏳ [DEBUG] Đang đợi self.context.new_page()...")
                try:
                    self.page = await asyncio.wait_for(self.context.new_page(), timeout=60.0)
                    logger.info("✅ [DEBUG] Đã tạo xong page mới!")
                except asyncio.TimeoutError:
                    logger.error("❌ [DEBUG] Lỗi: Timeout khi gọi self.context.new_page() (Quá 60s)!")
                    raise Exception("Timeout khi tạo cửa sổ mới. Có thể Firefox bị kẹt tiến trình GPU!")
                except Exception as e:
                    logger.error(f"❌ [DEBUG] Lỗi Exception khi gọi self.context.new_page(): {e}")
                    raise e
            else:
                self.page = pages[0]
                logger.info("✅ [DEBUG] Sử dụng page có sẵn!")
                for p in pages[1:]:
                    try: await p.close()
                    except: pass
                
        except Exception as e:
            err_str = str(e).lower()
            if "in use" in err_str or "locked" in err_str:
                raise Exception("Profile trình duyệt đang mở. Vui lòng tắt cửa sổ cũ rồi thử lại!")
            raise e

        logger.info("⏳ [DEBUG] Chuyển qua bước _check_network()...")
        await self._check_network()
        logger.info("🎭 [Seeder] Browser initialized via CDP (Bypass Shadowban)")

    async def _connect_cloakbrowser(self):
        """Khởi động CloakBrowser - Trình duyệt tàng hình C++ bypass cực mạnh"""
        from pathlib import Path
        
        cookie_path = Path(self.cookies_file) if self.cookies_file else Path("default.json")
        profile_dir = cookie_path.parent / ".profiles" / cookie_path.stem
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        proxy_dict = None
        if self.proxy:
            proxy_str = self.proxy.strip()
            # Xử lý format proxy ip:port:user:pass
            parts = proxy_str.split(":")
            if len(parts) == 4:
                ip, port, user, pwd = parts
                import urllib.parse
                user = urllib.parse.unquote(user)
                pwd = urllib.parse.unquote(pwd)
                proxy_dict = {"server": f"http://{ip}:{port}", "username": user, "password": pwd}
            elif len(parts) == 2:
                proxy_dict = {"server": f"http://{parts[0]}:{parts[1]}"}
            else:
                proxy_dict = {"server": proxy_str}
                
        logger.info(f"🌐 [Seeder] Đang khởi động CloakBrowser (C++) với Profile: {cookie_path.stem}")
        
        try:
            from cloakbrowser import launch_persistent_context_async
        except ImportError:
            raise Exception("Chưa cài CloakBrowser! Vui lòng chạy lệnh: pip install \"cloakbrowser[geoip]\"")
            
        import shutil
        # Xóa các thư mục Cache để làm sạch trình duyệt (tránh bị kẹt cache bài post cũ)
        for cache_folder in ["Cache", "Code Cache", "GPUCache"]:
            cache_path = profile_dir / "Default" / cache_folder
            if cache_path.exists():
                try:
                    shutil.rmtree(cache_path)
                    logger.info(f"🧹 Đã dọn dẹp Cache: {cache_folder}")
                except Exception:
                    pass

        launch_args = {
            "user_data_dir": str(profile_dir),
            "headless": False,
            "humanize": True,
            "viewport": None,
            "args": [
                "--test-type",
                "--disable-infobars"
            ]
        }
        
        if proxy_dict:
            # Rất quan trọng: Ép WebRTC IP thành Proxy IP để chống rò rỉ IP thật
            # CloakBrowser auto-geoip đôi khi lấy nhầm IP thật cho WebRTC
            proxy_ip = ip if 'ip' in locals() else (parts[0] if 'parts' in locals() and len(parts) >= 2 else None)
            if proxy_ip:
                launch_args["args"].append(f"--fingerprint-webrtc-ip={proxy_ip}")
                
            launch_args["proxy"] = proxy_dict
            launch_args["geoip"] = True  # Tự động khớp múi giờ và locale theo Proxy
            
        self.context = await launch_persistent_context_async(**launch_args)
        
        # Bỏ qua stealth.js vì CloakBrowser đã tự động xử lý ẩn danh ở tầng C++
        # Việc inject thêm JS bằng Playwright (CDP) có thể bị WAF Akamai phát hiện ngược

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # [QUAN TRỌNG] Bỏ qua việc nạp cookie bằng JSON (add_cookies) đối với Persistent Context.
        # Vì người dùng đã login bằng "Cloak", toàn bộ Cookie và LocalStorage ĐÃ NẰM SẴN trong profile_dir.
        # Việc cố tình add_cookies() đè lên có thể làm hỏng Session hoặc bị WAF đánh dấu là Cookie Injection.
        logger.info(f"🎭 Đang dùng Profile được lưu sẵn tại: {profile_dir.name}")
        
        await self.page.bring_to_front()
        await self._check_network()
        logger.info("🎭 [Seeder] CloakBrowser khởi tạo thành công!")

    async def _connect_adspower(self, is_hubstudio=False):
        """Kết nối tới AdsPower hoặc HubStudio thông qua Local API."""
        import aiohttp
        from pathlib import Path
        from config.settings import TIKTOK_CONFIG
        
        adspower_url = TIKTOK_CONFIG.get("antidetect", {}).get("api_url", "http://127.0.0.1:50325")
        
        # Lấy profile ID từ tên file cookie (bỏ chữ tiktok_)
        profile_id = Path(self.cookies_file).stem if self.cookies_file else ""
        profile_id = profile_id.replace("tiktok_", "")
        if not profile_id or profile_id == "default":
            raise Exception("Chưa xác định được Profile ID của AdsPower.")
            
        logger.info(f"🚀 Yêu cầu AdsPower mở Profile: {profile_id}")
        
        ws_url = None
        async with aiohttp.ClientSession() as session:
            try:
                # Check status
                status_url = f"{adspower_url}/api/v1/browser/active?user_id={profile_id}"
                async with session.get(status_url, timeout=3) as resp:
                    data = await resp.json()
                    if data["code"] == 0 and data["data"]["status"] == "Active":
                        ws_url = data["data"]["ws"]["puppeteer"]
                        logger.info(f"🔄 AdsPower Profile đang chạy sẵn, lấy WebSocket: {ws_url}")
                    else:
                        start_url = f"{adspower_url}/api/v1/browser/start?user_id={profile_id}&open_tabs=1"
                        async with session.get(start_url, timeout=5) as resp2:
                            data2 = await resp2.json()
                            if data2.get("code") != 0:
                                raise Exception(f"AdsPower API Error: {data2.get('msg')}")
                            ws_url = data2["data"]["ws"]["puppeteer"]
                            logger.info(f"✅ Đã bật AdsPower Profile mới. WebSocket: {ws_url}")
            except Exception as e:
                logger.warning(f"⚠️ API AdsPower không khả dụng: {e}. Đang chuyển sang Quét tiến trình...")
                
        if is_hubstudio:
            logger.info("ℹ️ Chế độ HubStudio: Đang quét tiến trình để tìm cổng kết nối...")
            ws_url = None
        
        # Bypass cho bản Free / HubStudio - Quét cổng thủ công
        if not ws_url:
            import subprocess
            import re
            import os
            try:
                # Quét tất cả tiến trình có remote-debugging-port
                output = ""
                try:
                    output = subprocess.check_output('wmic process where "commandline like \'%remote-debugging-port%\'" get commandline', shell=True).decode('utf-8', errors='ignore')
                except Exception:
                    pass
                
                lines = [l for l in output.splitlines() if '--remote-debugging-port=' in l]
                if not lines:
                    try:
                        output = subprocess.check_output('wmic process get commandline', shell=True).decode('utf-8', errors='ignore')
                        lines = [l for l in output.splitlines() if '--remote-debugging-port=' in l]
                    except Exception:
                        pass
                
                # Tìm dòng khớp với profile_id trước, nếu không tìm thấy mới lấy dòng bất kỳ
                target_line = None
                if profile_id:
                    for line in lines:
                        if profile_id in line:
                            target_line = line
                            break
                if not target_line and lines:
                    target_line = lines[0]
                    
                if target_line:
                    port_match = re.search(r'--remote-debugging-port=(\d+)', target_line)
                    port = port_match.group(1) if port_match else None
                    
                    if port == '0':
                        dir_match = re.search(r'--user-data-dir="([^"]+)"', target_line) or re.search(r'--user-data-dir=([^\s]+)', target_line)
                        if dir_match:
                            user_data_dir = dir_match.group(1)
                            dev_file = os.path.join(user_data_dir, "DevToolsActivePort")
                            if os.path.exists(dev_file):
                                with open(dev_file, 'r', encoding='utf-8') as f:
                                    port = f.readline().strip()
                    
                    if port and port != '0':
                        ws_url = f"http://127.0.0.1:{port}"
                        logger.info(f"🔓 Bắt thành công cổng nội bộ HubStudio/AdsPower: {port}")
            except Exception as e:
                logger.error(f"Lỗi quét cổng HubStudio: {e}")
                
        if not ws_url:
            raise Exception("Chưa lấy được cổng kết nối! Vui lòng BẤM NÚT MỞ (打开) THỦ CÔNG trình duyệt trong HubStudio/AdsPower trước khi bấm Bắt đầu trên Tool.")

                
        # Connect Playwright via CDP
        self.browser = await self._playwright.chromium.connect_over_cdp(ws_url)
        self.context = self.browser.contexts[0]
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        await self.page.bring_to_front()
        logger.info(f"✅ Đã kết nối thành công Playwright tới AdsPower Profile: {profile_id}")

    async def _connect_dolphin(self):
        """Kết nối tới Dolphin Anty thông qua Local API."""
        import aiohttp
        from pathlib import Path
        from config.settings import TIKTOK_CONFIG
        
        dolphin_url = TIKTOK_CONFIG.get("antidetect", {}).get("api_url", "http://127.0.0.1:3001")
        
        profile_id = Path(self.cookies_file).stem if self.cookies_file else ""
        profile_id = profile_id.replace("tiktok_", "")
        if not profile_id or profile_id == "default":
            raise Exception("Chưa xác định được Profile ID. Vui lòng đặt tên file tài khoản trùng với Profile ID của Dolphin (VD: 18534891.json)")
            
        logger.info(f"🚀 Yêu cầu Dolphin Anty mở Profile ID: {profile_id}")
        
        url = f"{dolphin_url}/v1.0/browser_profiles/{profile_id}/start?automation=1"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if not data.get("success"):
                        raise Exception(f"Dolphin API Error: {data}")
                    
                    ws_url = f"ws://127.0.0.1:{data['automation']['port']}{data['automation']['wsEndpoint']}" if not data['automation']['wsEndpoint'].startswith('ws') else data['automation']['wsEndpoint']
                    logger.info(f"✅ Đã lấy được WebSocket Dolphin: {ws_url}")
            except Exception as e:
                raise Exception(f"Không thể kết nối Dolphin API ({url}). Hãy chắc chắn phần mềm Dolphin Anty đang mở.\nChi tiết: {e}")
                
        self.browser = await self._playwright.chromium.connect_over_cdp(ws_url)
        self.context = self.browser.contexts[0]
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        await self.page.bring_to_front()
        logger.info(f"✅ Đã kết nối thành công Playwright tới Dolphin Profile: {profile_id}")

    async def _load_cookies(self):
        """Load cookies TikTok từ file JSON."""
        if not self.cookies_file or not Path(self.cookies_file).exists():
            return
            
        try:
            # Check if profile already has a valid session (from previous runs)
            current_cookies = await self.context.cookies()
            if any(c.get("name") == "sessionid" for c in current_cookies):
                logger.info("[Seeder] Profile already logged in. Skipping JSON cookie load to preserve active session.")
                return

            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            formatted = []
            for c in cookies:
                item = {
                    "name": c.get("name", ""),
                    "value": c.get("value", ""),
                    "domain": c.get("domain", ".tiktok.com"),
                    "path": c.get("path", "/"),
                }
                if item["name"] and item["value"]:
                    formatted.append(item)
            await self.context.add_cookies(formatted)
            logger.info(f"[Seeder] Loaded {len(formatted)} cookies")
        except Exception as e:
            logger.error(f"[Seeder] Failed to load cookies: {e}")

    async def _check_network(self):
        """Kiểm tra IP/Proxy sống."""
        try:
            response = await self.page.goto("https://api.ipify.org", timeout=15000)
            if response and response.ok:
                ip = await response.text()
                if self.proxy:
                    logger.info(f"✅ [Seeder] KẾT NỐI PROXY THÀNH CÔNG. IP: {ip.strip()}")
                else:
                    logger.info(f"✅ [Seeder] Đang dùng IP MÁY THẬT. IP: {ip.strip()}")
            else:
                if self.proxy:
                    logger.warning(f"⚠️ [Seeder] Proxy có thể bị lỗi (HTTP {response.status if response else 'No response'}). Vẫn tiếp tục chạy...")
                else:
                    logger.warning(f"⚠️ [Seeder] Không check được IP máy (HTTP {response.status if response else 'No response'}). Vẫn tiếp tục chạy...")
        except Exception as e:
            err_msg = str(e).split('\n')[0]
            if self.proxy:
                logger.warning(f"⚠️ [Seeder] Lỗi Proxy: {err_msg}. Vẫn tiếp tục chạy...")
            else:
                logger.warning(f"⚠️ [Seeder] Không lấy được IP máy: {err_msg}. Vẫn tiếp tục chạy...")

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def _cleanup_extra_pages(self):
        """Đóng tất cả các tab thừa, chỉ giữ lại tab chính (self.page)."""
        try:
            if self.context and self.page:
                pages = self.context.pages
                if len(pages) > 1:
                    for p in pages:
                        if p != self.page:
                            try:
                                await p.close()
                            except Exception:
                                pass
        except Exception:
            pass

    async def join_livestream(
        self,
        live_url: str,
        config: dict = None,
        update_callback: Optional[Callable[[str, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """
        Vào phòng Live TikTok và thực hiện seeding.

        Args:
            live_url: URL phòng live (VD: https://www.tiktok.com/@user/live)
            config: Cấu hình seeding (intervals, comments, duration...)
            update_callback: Callback(message, level) để cập nhật log
            cancel_check: Callback() -> bool để kiểm tra dừng
        """
        cfg = {**DEFAULT_LIVESTREAM_CONFIG, **(config or {})}
        self.hearts_sent = 0
        self.comments_sent = 0
        self.shares_done = 0

        def _log(msg, lvl="INFO"):
            logger.log(lvl, msg)
            if update_callback:
                update_callback(msg, lvl)

        try:
            if not self.page:
                await self._init_browser()
            
            # Dọn dẹp mọi tab rác từ vòng lặp trước
            await self._cleanup_extra_pages()

            # Chuẩn hoá URL
            live_url = self._normalize_live_url(live_url)
            _log(f"🔗 Đang vào phòng Live: {live_url}")

            self.is_guest_mode = False

            # LỚP 1: PRE-WARMUP (LÀM ẤM COOKIE & PROXY TRƯỚC KHI VÀO LIVE)
            _log("🌟 [Senior++] Đang làm ấm Proxy & Cookie tại trang chủ...", "INFO")
            try:
                await self.page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=20000)
                await self._random_delay(2, 3)
                # Cuộn chuột lướt ForYou giả làm người thật để lấy Trust Score từ TikTok
                for _ in range(3):
                    await self.page.mouse.wheel(0, random.randint(300, 700))
                    await self._random_delay(1, 2)
                _log("✅ Làm ấm hoàn tất, chuyển hướng vào phòng Live!", "INFO")
            except Exception as e:
                logger.error(f"[DEBUG] Lỗi Lớp 1 (goto tiktok.com): {e}")
            await self._random_delay(1, 2)

            # LỚP 2: KIỂM TRA ĐĂNG NHẬP & KÍCH HOẠT GUEST-MODE
            try:
                from config.settings import TIKTOK_CONFIG
                engine = TIKTOK_CONFIG.get("antidetect", {}).get("engine", "built-in").lower()
            except:
                engine = "built-in"
                
            if engine not in ["adspower", "dolphin", "gologin"]:
                # Kiểm tra cookie trong bộ nhớ trước
                context_cookies = await self.context.cookies()
                has_session = any(c.get("name") == "sessionid" for c in context_cookies)
                
                # Check thực tế trên web
                is_logged_out = False
                try:
                    is_logged_out = await self.page.evaluate("""
                        () => {
                            const btns = document.querySelectorAll('button, a, div');
                            for (const btn of btns) {
                                const t = (btn.textContent || '').trim().toLowerCase();
                                if (t === 'log in' || t === 'đăng nhập') return true;
                            }
                            return false;
                        }
                    """)
                except:
                    pass

                if not has_session or is_logged_out:
                    _log("⚠️ [Senior++] Cookie hết hạn! Bật chế độ Khách (Guest Mode) để cứu View (Không tương tác).", "WARNING")
                    self.is_guest_mode = True
                else:
                    self.is_guest_mode = False

            # Navigate tới phòng Live
            reconnect_attempts = 0
            max_reconnect = cfg.get("max_reconnect_attempts", 3)
            success_run = False

            while reconnect_attempts <= max_reconnect:
                if cancel_check and cancel_check():
                    break

                try:
                    # Tách lấy username từ live_url (vd: https://www.tiktok.com/@d.kha0845/live -> https://www.tiktok.com/@d.kha0845)
                    profile_url = live_url.split("/live")[0]
                    _log(f"👉 Chuyển hướng gián tiếp qua Profile: {profile_url}", "INFO")
                    await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.error(f"[DEBUG] Lỗi Lớp 3 (goto profile_url): {e}")
                
                # Đợi trang profile load hẳn
                await self._random_delay(4, 6)

                # Ưu tiên click tự nhiên vào Avatar thay vì dùng goto() để giữ luồng Referer chuẩn của trình duyệt
                try:
                    clicked_live = False
                    for selector in _SELECTORS["live_badge"]:
                        badge = self.page.locator(selector).first
                        if await badge.count() > 0 and await badge.is_visible():
                            _log(f"👉 Tìm thấy avatar LIVE (selector: {selector}), đang click vào phòng...", "INFO")
                            
                            # Tính toán tọa độ và mô phỏng click chuột thật của con người
                            box = await badge.bounding_box()
                            if box:
                                x = box["x"] + box["width"] / 2
                                y = box["y"] + box["height"] / 2
                                
                                # Move chuột mượt mà đến phần tử
                                await self.page.mouse.move(x, y, steps=10)
                                await asyncio.sleep(0.1)
                                
                                # Click xuống và nhả ra giống người
                                await self.page.mouse.down()
                                await asyncio.sleep(0.05)
                                await self.page.mouse.up()
                                
                                clicked_live = True
                                break
                            else:
                                # Fallback nếu không lấy được tọa độ
                                await badge.evaluate("node => node.click()")
                                clicked_live = True
                                break
                    if not clicked_live:
                        _log("⚠️ Không thấy huy hiệu LIVE trên Avatar, chuyển hướng dự phòng...", "WARNING")
                        await self.page.evaluate(f"window.location.href = '{live_url}'")
                except Exception as e:
                    logger.error(f"[DEBUG] Lỗi Lớp 3 (Click Avatar): {e}")
                
                await self._random_delay(5, 8)

                # Tự động xử lý nút Retry hoặc chờ giải Captcha (nếu có)
                await self._handle_captcha_and_retry(_log)

                # Dismiss popups nhiều lần (TikTok hay hiện popup login, age-gate liên tục)
                await self._dismiss_popups()
                await self._random_delay(1, 2)
                await self._dismiss_popups()
                
                # Nếu bị redirect ra trang profile (không có /live), thử click vào avatar LIVE để vào phòng
                if "/live" not in self.page.url.lower() and "@" in self.page.url.lower():
                    # Tránh vòng lặp vô tận click tạo tab mới nếu trang hiện tại bị 403 block
                    try:
                        is_blocked = await self.page.evaluate("""
                            () => {
                                const body = document.body ? document.body.innerText : '';
                                return body.includes('Access to www.tiktok.com was denied') || body.includes('HTTP ERROR 403');
                            }
                        """)
                        if is_blocked:
                            _log("🚨 Proxy bị chặn (HTTP 403). Dừng kết nối.", "ERROR")
                            break
                    except Exception:
                        pass

                    try:
                        for selector in _SELECTORS["live_badge"]:
                            badge = self.page.locator(selector).first
                            if await badge.count() > 0 and await badge.is_visible():
                                _log("👉 Phát hiện đang ở trang Profile. Click vào avatar để vào phòng Live...", "INFO")
                                
                                pages_before = self.context.pages
                                await badge.click(no_wait_after=True)
                                
                                # Đợi tối đa 10s cho tab mới xuất hiện
                                new_page = None
                                for _ in range(10):
                                    await asyncio.sleep(1)
                                    pages_after = self.context.pages
                                    if len(pages_after) > len(pages_before):
                                        new_page = pages_after[-1]
                                        break
                                
                                if new_page:
                                    old_page = self.page
                                    self.page = new_page
                                    try:
                                        await old_page.close()
                                    except Exception:
                                        pass
                                
                                await self._cleanup_extra_pages()
                                await self._random_delay(3, 5)
                                break
                    except Exception:
                        pass

                # Detect trạng thái Live
                status = await self._detect_live_status()
                _log(f"🔍 Trạng thái phát hiện: {status.value}", "DEBUG") if status != LiveStatus.LIVE_ACTIVE else None

                if status == LiveStatus.LIVE_ACTIVE:
                    self.is_watching = True
                    _log("✅ Đã vào phòng Live thành công! Bắt đầu xem...", "SUCCESS")

                    # Bắt đầu watching loop
                    success_run = await self._watching_loop(cfg, _log, cancel_check)

                    # Kiểm tra sau khi loop kết thúc
                    if cancel_check and cancel_check():
                        break

                    # Nếu live vẫn active mà loop kết thúc → do hết duration
                    post_status = await self._detect_live_status()
                    if post_status == LiveStatus.LIVE_ENDED:
                        _log("📴 Phiên Live đã kết thúc.", "WARNING")
                        break
                    else:
                        # Hết duration
                        break

                elif status == LiveStatus.LIVE_ENDED:
                    _log("📴 Phiên Live đã kết thúc hoặc chưa bắt đầu.", "WARNING")
                    break

                elif status == LiveStatus.LIVE_NOT_FOUND:
                    reconnect_attempts += 1
                    if reconnect_attempts > max_reconnect:
                        _log("❌ Bị TikTok đẩy ra trang chủ hoặc lỗi 'Something went wrong' liên tục. Có thể do Proxy bẩn hoặc Cookie lỗi!", "ERROR")
                        break
                    _log(f"⚠️ Không thấy Live (lần {reconnect_attempts}/{max_reconnect}), thử lại sau 5 giây...", "WARNING")
                    await self._random_delay(4, 6)

                elif status == LiveStatus.LIVE_BLOCKED_403:
                    _log("🚨 IP/Proxy bị TikTok chặn (HTTP 403 Access Denied)!", "ERROR")
                    break

                elif status == LiveStatus.LIVE_RESTRICTED:
                    _log("🔒 Phòng Live yêu cầu đăng nhập/xác minh tuổi. Đang thử bypass...", "WARNING")
                    # Thử bypass bằng cách dismiss popup và bấm Escape nhiều lần
                    for _ in range(3):
                        await self._dismiss_popups()
                        await self._random_delay(1, 2)
                    
                    # Re-check: nếu vẫn có video đang chạy ở phía dưới popup → vẫn vào được
                    try:
                        has_video = await self.page.evaluate("""
                            () => {
                                const videos = document.querySelectorAll('video');
                                return videos.length > 0;
                            }
                        """)
                        if has_video:
                            self.is_watching = True
                            _log("✅ Bypass thành công! Đã vào phòng Live (có thể bị giới hạn tính năng).", "SUCCESS")
                            success_run = await self._watching_loop(cfg, _log, cancel_check)
                            break
                    except Exception:
                        pass
                    
                    _log("🚫 Không thể bypass. Bỏ qua phòng Live này.", "ERROR")
                    break

                else:
                    # LIVE_ERROR — thử reconnect
                    if cfg.get("auto_reconnect") and reconnect_attempts < max_reconnect:
                        reconnect_attempts += 1
                        wait = random.randint(5, 15)
                        _log(f"⚠️ Lỗi kết nối, thử lại lần {reconnect_attempts}/{max_reconnect} sau {wait}s...", "WARNING")
                        await asyncio.sleep(wait)
                        continue
                    else:
                        _log("❌ Không thể kết nối tới phòng Live sau nhiều lần thử.", "ERROR")
                        break

            # Tổng kết
            self.is_watching = False
            summary = (
                f"📊 Tổng kết: Thả tim {self.hearts_sent} lần | "
                f"Bình luận {self.comments_sent} lần | "
                f"Share {self.shares_done} lần"
            )
            if success_run:
                _log(summary, "SUCCESS")
            return success_run

        except Exception as e:
            self.is_watching = False
            _log(f"❌ Lỗi Seeding: {e}", "ERROR")
            return False

    def _normalize_live_url(self, url: str) -> str:
        """Chuẩn hoá URL phòng Live TikTok."""
        url = url.strip()
        
        # Xoá các query parameter tracking (từ dấu ? trở đi) để tránh bị TikTok redirect
        if "?" in url:
            url = url.split("?")[0]
            
        # Nếu chỉ nhập username (VD: @username hoặc username)
        if not url.startswith("http"):
            username = url.lstrip("@")
            return f"https://www.tiktok.com/@{username}/live"
            
        # Đảm bảo có /live ở cuối nếu là URL profile
        if "/live" not in url and "@" in url:
            url = url.rstrip("/") + "/live"
            
        return url

    # ──────────────────────────────────────────────────────────────────────────
    #  Watching Loop — Vòng lặp chính khi đang xem Live
    # ──────────────────────────────────────────────────────────────────────────
    async def _watching_loop(
        self,
        cfg: dict,
        _log: Callable,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Vòng lặp chính mô phỏng người xem Live thật theo số lượng hành động."""
        
        # 1. Tính toán thời gian xem cho Live này
        if isinstance(cfg.get("duration_minutes"), tuple):
            dur = random.uniform(*cfg["duration_minutes"])
        else:
            dur = cfg.get("duration_minutes", 30)
        
        start_time = time.time()
        end_time = start_time + (dur * 60)
        total_sec = dur * 60

        # Hàm tiện ích tạo mảng thời gian
        def create_schedule(count, total_sec):
            if count <= 0: return []
            interval = total_sec / count
            times = [start_time + (i * interval) + random.uniform(-interval*0.2, interval*0.2) for i in range(1, count + 1)]
            times.sort()
            return times

        # 2. Lên lịch thả tim
        heart_times = []
        if cfg.get("heart_enabled", True) and not getattr(self, "is_guest_mode", False):
            h_count = cfg.get("heart_count", (10, 30))
            count = random.randint(*h_count) if isinstance(h_count, tuple) else int(h_count)
            heart_times = create_schedule(count, total_sec)

        # 3. Lên lịch bình luận
        cmt_times = []
        comments_bank = cfg.get("comments", DEFAULT_COMMENTS)
        if cfg.get("comment_enabled", True) and comments_bank and not getattr(self, "is_guest_mode", False):
            c_count = cfg.get("comment_count", (1, 3))
            count = random.randint(*c_count) if isinstance(c_count, tuple) else int(c_count)
            cmt_times = create_schedule(count, total_sec)

        # 4. Lên lịch chia sẻ
        share_times = []
        if cfg.get("share_enabled", False) and not getattr(self, "is_guest_mode", False):
            s_count = cfg.get("share_count", (1, 1))
            count = random.randint(*s_count) if isinstance(s_count, tuple) else int(s_count)
            share_times = create_schedule(count, total_sec)

        # 5. Theo dõi (Follow)
        follow_enabled = cfg.get("follow_enabled", False)
        follow_time = start_time + random.uniform(20, total_sec * 0.7) if follow_enabled else float('inf')

        next_popup_check = start_time + 5  # Kiểm tra popup sớm (TikTok hay hiện popup đăng nhập)
        next_status_check = start_time + 60
        next_human_action = start_time + random.uniform(15, 45)
        
        interval_min, interval_max = cfg.get("interval_between_actions", (10, 20))
        next_allowed_action = 0

        _log(f"⚙️ Config: Xem {dur:.1f}p | Tim: {len(heart_times)} | Cmt: {len(cmt_times)} | Share: {len(share_times)} | Follow: {follow_enabled}", "INFO")

        while time.time() < end_time:
            if cancel_check and cancel_check():
                _log("⏹ Đã dừng theo yêu cầu.", "WARNING")
                return False

            now = time.time()
            remaining = int(end_time - now)

            # --- CÁC HÀNH ĐỘNG TƯƠNG TÁC (CHỈ THỰC HIỆN 1 HÀNH ĐỘNG MỖI LƯỢT ĐỂ TRÁNH SPAM) ---
            if heart_times and now >= heart_times[0] and now >= next_allowed_action:
                heart_times.pop(0)
                if await self._send_heart():
                    self.hearts_sent += 1
                    if self.hearts_sent <= 3 or self.hearts_sent % 5 == 0:
                        _log(f"❤️ Đã thả tim (lần {self.hearts_sent})", "SUCCESS")
                    next_allowed_action = time.time() + random.uniform(interval_min, interval_max)

            elif cmt_times and now >= cmt_times[0] and now >= next_allowed_action:
                cmt_times.pop(0)
                cmt = random.choice(comments_bank)
                if random.random() < 0.3: cmt += " " + random.choice(["😍", "🥰", "💪", "👍", "🙏", "😊", "💕"])
                if await self._send_comment(cmt):
                    self.comments_sent += 1
                    _log(f"💬 Đã bình luận: \"{cmt}\"", "SUCCESS")
                    next_allowed_action = time.time() + random.uniform(interval_min, interval_max)

            elif share_times and now >= share_times[0] and now >= next_allowed_action:
                share_times.pop(0)
                if await self._share_live():
                    self.shares_done += 1
                    _log(f"📤 Đã share phiên Live", "SUCCESS")
                    next_allowed_action = time.time() + random.uniform(interval_min, interval_max)
                    
            elif now >= follow_time and now >= next_allowed_action:
                follow_time = float('inf') # Chỉ follow 1 lần
                if await self._follow_streamer():
                    _log(f"👤 Đã Theo dõi (Follow) chủ phòng Live", "SUCCESS")
                    next_allowed_action = time.time() + random.uniform(interval_min, interval_max)

            # --- HÀNH ĐỘNG NỀN (KHÔNG BỊ GIỚI HẠN BỞI interval_between_actions) ---
            # Dismiss popups
            if now >= next_popup_check:
                await self._dismiss_popups()
                next_popup_check = now + 30

            # Check live status
            if now >= next_status_check:
                status = await self._detect_live_status()
                if status == LiveStatus.LIVE_ENDED:
                    _log("📴 Phiên Live đã kết thúc!", "WARNING")
                    return True
                elif status == LiveStatus.LIVE_RESTRICTED:
                    _log("🚫 Bị hạn chế xem!", "ERROR")
                    return False
                elif status == LiveStatus.LIVE_NOT_FOUND:
                    _log("❌ Không tìm thấy tín hiệu phiên Live (Bị redirect hoặc mất kết nối).", "ERROR")
                    return False
                next_status_check = now + 60

            # Hành vi ngẫu nhiên
            if now >= next_human_action:
                await self._human_micro_action()
                await self._cleanup_extra_pages()
                next_human_action = now + random.uniform(15, 60)

            await asyncio.sleep(random.uniform(2.0, 4.0))

        _log(f"⏱ Đã xem đủ {dur:.1f} phút. Rời phòng Live.", "INFO")
        return True

    # ──────────────────────────────────────────────────────────────────────────
    #  Actions
    # ──────────────────────────────────────────────────────────────────────────
    async def _move_mouse_human_like(self, target_element):
        """Di chuột tới một mục tiêu bằng các đường vòng cung (Bezier curves) giống tay người thật."""
        try:
            box = await target_element.bounding_box()
            if not box: return
            
            target_x = box['x'] + box['width'] / 2 + random.uniform(-box['width']*0.2, box['width']*0.2)
            target_y = box['y'] + box['height'] / 2 + random.uniform(-box['height']*0.2, box['height']*0.2)
            
            viewport = self.page.viewport_size
            start_x = random.randint(0, viewport['width'] if viewport else 800)
            start_y = random.randint(0, viewport['height'] if viewport else 600)
            
            await self.page.mouse.move(start_x, start_y)
            
            steps = random.randint(15, 30)
            for i in range(1, steps + 1):
                t = i / steps
                # Simple lerp with noise
                noise_x = random.uniform(-5, 5) * math.sin(t * math.pi)
                noise_y = random.uniform(-5, 5) * math.cos(t * math.pi)
                cur_x = start_x + (target_x - start_x) * t + noise_x
                cur_y = start_y + (target_y - start_y) * t + noise_y
                await self.page.mouse.move(cur_x, cur_y)
                await asyncio.sleep(0.01)
                
            await self.page.mouse.move(target_x, target_y)
            await asyncio.sleep(random.uniform(0.1, 0.4))
        except: pass

    async def _send_heart(self) -> bool:
        """Thả tim trong phòng Live có log chi tiết và xác minh."""
        try:
            logger.debug("[Seeder] Bắt đầu tìm nút thả tim...")
            for selector in _SELECTORS["heart_button"]:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        logger.debug(f"[Seeder] Đã tìm thấy nút thả tim qua selector: {selector}")
                        
                        # Biometrics: Di chuột tới nút trước
                        import math
                        await self._move_mouse_human_like(btn)
                        
                        box = await btn.bounding_box()
                        if box:
                            await btn.click(delay=random.randint(30, 80), timeout=5000, force=True)
                            logger.debug("[Seeder] Đã click nút thả tim (First Click)")
                            
                            # Double/Triple click ngẫu nhiên (thả tim liên tục)
                            if random.random() < 0.4:
                                num_clicks = random.randint(1, 3)
                                await asyncio.sleep(random.uniform(0.1, 0.3))
                                await btn.click(click_count=num_clicks, delay=random.randint(20, 60), timeout=5000, force=True)
                                logger.debug(f"[Seeder] Đã double/triple click (x{num_clicks})")
                            
                            # Verify: Kiểm tra xem class hoặc aria-pressed có thay đổi không
                            try:
                                aria_pressed = await btn.get_attribute("aria-pressed")
                                class_attr = await btn.get_attribute("class")
                                logger.debug(f"[Seeder] Verify tim -> aria-pressed: {aria_pressed}, class: {class_attr}")
                            except:
                                pass
                            
                            return True
                except Exception as e:
                    logger.debug(f"[Seeder] Lỗi khi xử lý selector tim '{selector}': {e}")
                    continue
            logger.debug("[Seeder] Không tìm thấy nút thả tim qua bất kỳ selector nào.")
        except Exception as e:
            logger.debug(f"[Seeder] Heart error: {e}")
        return False

    async def _send_comment(self, message: str) -> bool:
        """Gửi bình luận trong phòng Live có log chi tiết."""
        try:
            logger.debug("[Seeder] Bắt đầu tìm ô nhập comment...")
            input_el = None
            found_selector = None
            for selector in _SELECTORS["comment_input"]:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible():
                        input_el = el
                        found_selector = selector
                        break
                except Exception:
                    continue

            if not input_el:
                logger.debug("❌ [Seeder] Bỏ qua cmt: Không tìm thấy ô nhập comment bằng bất kỳ selector nào.")
                return False
                
            logger.debug(f"✅ [Seeder] Đã tìm thấy ô nhập comment qua selector: {found_selector}")

            import math
            await self._move_mouse_human_like(input_el)

            await input_el.click()
            await asyncio.sleep(random.uniform(0.5, 1.2))

            logger.debug(f"[Seeder] Đang type comment: '{message}'...")
            
            # Bắt buộc dùng type() vì CloakBrowser's humanize=True hook vào hàm này để thêm typing rhythms.
            # Nếu dùng press_sequentially() sẽ bị bypass tính năng humanize và lộ bot.
            await input_el.type(message, delay=random.randint(40, 120))
                
            await asyncio.sleep(random.uniform(0.5, 1.0))
            logger.debug("[Seeder] Đã type xong, chuẩn bị submit...")

            sent = False
            for selector in _SELECTORS["comment_send"]:
                try:
                    send_btn = self.page.locator(selector).first
                    if await send_btn.count() > 0 and await send_btn.is_visible():
                        await send_btn.click()
                        sent = True
                        logger.debug(f"[Seeder] Đã submit bằng cách Click nút Send ({selector})")
                        break
                except Exception:
                    continue

            if not sent:
                await self.page.keyboard.press("Enter")
                logger.debug("[Seeder] Đã submit bằng cách bấm phím Enter")

            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            logger.debug("[Seeder] Verify comment: Quá trình submit hoàn tất.")
            return True

        except Exception as e:
            logger.debug(f"[Seeder] Comment error: {e}")
            return False

    async def _share_live(self) -> bool:
        """Share phiên Live (Copy Link)."""
        try:
            for selector in _SELECTORS["share_button"]:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(random.uniform(1.0, 2.0))

                        # Tìm nút "Copy Link" trong menu share
                        copy_btn = self.page.locator(':has-text("Copy link"), :has-text("Sao chép liên kết")').first
                        if await copy_btn.count() > 0:
                            await copy_btn.click()
                            await asyncio.sleep(0.5)

                        # Đóng menu share (Escape)
                        await self.page.keyboard.press("Escape")
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[Seeder] Share error: {e}")
        return False

    async def _follow_streamer(self) -> bool:
        """Theo dõi chủ phòng Live."""
        try:
            for selector in _SELECTORS["follow_button"]:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[Seeder] Follow error: {e}")
        return False

    async def _handle_captcha_and_retry(self, _log: Callable):
        """Tự động bấm Retry nếu lỗi mạng hoặc chờ người dùng giải Captcha."""
        try:
            # 1. Kiểm tra màn hình lỗi "Something went wrong" / "Something is wrong on our end" -> Tự động bấm Retry/Refresh
            for attempt in range(5): # Thử tối đa 5 lần
                retry_btn = self.page.locator(
                    'button:has-text("Retry"), button:has-text("Thử lại"), '
                    'button:has-text("Refresh"), button:has-text("Làm mới"), '
                    'button:has-text("Try again"), button:has-text("Thử lại ngay")'
                ).first
                if await retry_btn.count() > 0 and await retry_btn.is_visible():
                    _log(f"⚠️ Phát hiện lỗi trang (Something went wrong / Retry). Tự động bấm... (lần {attempt+1})", "WARNING")
                    await retry_btn.click()
                    await self._random_delay(4, 7)
                else:
                    break
            
            # 2. Kiểm tra Captcha -> Dừng lại chờ người dùng giải
            captcha_selectors = [
                '#captcha-verify-image',
                'div[class*="captcha"]',
                'div[id*="captcha"]',
                'iframe[src*="captcha"]'
            ]
            has_captcha = False
            for selector in captcha_selectors:
                el = self.page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    has_captcha = True
                    break
            
            if has_captcha:
                _log("🛑 PHÁT HIỆN CAPTCHA! Vui lòng tự giải Captcha trên trình duyệt. Hệ thống sẽ tự động chờ tối đa 3 phút...", "WARNING")
                wait_time = 0
                while wait_time < 180: # Chờ tối đa 3 phút (180s)
                    await asyncio.sleep(5)
                    wait_time += 5
                    
                    # Kiểm tra xem Captcha đã biến mất chưa
                    still_has_captcha = False
                    for selector in captcha_selectors:
                        el = self.page.locator(selector).first
                        if await el.count() > 0 and await el.is_visible():
                            still_has_captcha = True
                            break
                    
                    if not still_has_captcha:
                        _log("✅ Captcha đã được giải quyết! Đang tiếp tục chạy...", "SUCCESS")
                        await self._random_delay(2, 4)
                        break
                        
        except Exception as e:
            logger.debug(f"[Seeder] Handle captcha/retry error: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    #  Detection
    # ──────────────────────────────────────────────────────────────────────────
    async def _detect_live_status(self) -> LiveStatus:
        """Phát hiện trạng thái phiên Live hiện tại."""
        try:
            current_url = self.page.url.lower()

            # --- Check Cloudflare Block (HTTP 403 / Access Denied) ---
            try:
                is_blocked = await self.page.evaluate("""
                    () => {
                        const body = document.body ? document.body.innerText : '';
                        return body.includes('Access to www.tiktok.com was denied') || body.includes('HTTP ERROR 403');
                    }
                """)
                if is_blocked:
                    logger.error("[Seeder] 🚨 IP/Proxy bị TikTok chặn (HTTP 403 Access Denied)!")
                    return LiveStatus.LIVE_BLOCKED_403
            except Exception:
                pass

            # Nếu bị redirect về trang login (chỉ khi URL chính là /login)
            if "/login" in current_url and "/live" not in current_url:
                return LiveStatus.LIVE_RESTRICTED

            # Nếu bị redirect ra trang cá nhân hoặc trang chủ (không có /live)
            if "/live" not in current_url and "tiktok.com" in current_url:
                logger.error(f"❌ [Seeder] Bị redirect khỏi trang Live! URL hiện tại: {current_url}")
                try:
                    title = await self.page.title()
                    logger.error(f"⚠️ [Seeder] Tiêu đề trang: {title}")
                    
                    import os
                    import time
                    os.makedirs("debug", exist_ok=True)
                    timestamp = int(time.time())
                    screenshot_path = f"debug/redirect_error_{timestamp}.png"
                    await self.page.screenshot(path=screenshot_path)
                    logger.error(f"📸 [Seeder] Đã chụp màn hình lỗi lưu tại: {screenshot_path}")
                    
                    html_content = await self.page.content()
                    logger.debug(f"📄 [Seeder] HTML Preview: {html_content[:500]}...")
                except Exception as e:
                    logger.debug(f"[Seeder] Lỗi khi dump debug: {e}")
                    
                # Vẫn kiểm tra xem có video không, nếu không có thì trả về LIVE_NOT_FOUND
                try:
                    video_playing = await self.page.evaluate("""
                        () => {
                            const videos = document.querySelectorAll('video');
                            for (const v of videos) {
                                if (!v.paused && v.readyState >= 2) return true;
                            }
                            return false;
                        }
                    """)
                    if not video_playing:
                        return LiveStatus.LIVE_NOT_FOUND
                except Exception:
                    return LiveStatus.LIVE_NOT_FOUND

            # Check phiên Live bị hạn chế (age-gate, login required) — ưu tiên trước ended
            try:
                restricted = await self.page.evaluate("""
                    () => {
                        const body = document.body ? document.body.innerText : '';
                        const restrictedPhrases = [
                            'Phiên LIVE không có sẵn',
                            'chỉ dành cho người xem đủ 18',
                            'only available to viewers over 18',
                            'LIVE is not available',
                            'age verification',
                            'xác minh tuổi',
                            'Hãy đăng nhập để tiếp tục xem'
                        ];
                        for (const phrase of restrictedPhrases) {
                            if (body.includes(phrase)) return true;
                        }
                        return false;
                    }
                """)
                if restricted:
                    logger.debug("[Seeder] Detected age-gate/restricted content")
                    return LiveStatus.LIVE_RESTRICTED
            except Exception:
                pass

            # Check live đã kết thúc — dùng JavaScript để tìm chính xác hơn
            try:
                ended = await self.page.evaluate("""
                    () => {
                        const body = document.body ? document.body.innerText : '';
                        const endedPhrases = [
                            'LIVE has ended', 'Phiên LIVE đã kết thúc',
                            'This LIVE has ended', 'The LIVE is over',
                            'Phiên live đã kết thúc'
                        ];
                        for (const phrase of endedPhrases) {
                            if (body.includes(phrase)) return true;
                        }
                        return false;
                    }
                """)
                if ended:
                    return LiveStatus.LIVE_ENDED
            except Exception:
                pass

            # Check live đang hoạt động
            # 1. Kiểm tra có video element đang play (cách chính xác nhất)
            try:
                video_playing = await self.page.evaluate("""
                    () => {
                        const videos = document.querySelectorAll('video');
                        for (const v of videos) {
                            if (!v.paused && v.readyState >= 2) return true;
                        }
                        return false;
                    }
                """)
                if video_playing:
                    return LiveStatus.LIVE_ACTIVE
            except Exception:
                pass

            # 2. Kiểm tra badge LIVE
            for selector in _SELECTORS["live_badge"]:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible():
                        return LiveStatus.LIVE_ACTIVE
                except Exception:
                    continue

            # 3. Kiểm tra viewer count element
            for selector in _SELECTORS["viewer_count"]:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible():
                        return LiveStatus.LIVE_ACTIVE
                except Exception:
                    continue

            # 4. Kiểm tra có video element nào (kể cả chưa play)
            try:
                has_video = await self.page.evaluate("""
                    () => document.querySelectorAll('video').length > 0
                """)
                if has_video:
                    return LiveStatus.LIVE_ACTIVE
            except Exception:
                pass

            # Không xác định được
            logger.debug("[Seeder] ❌ Không detect được Live (Không thấy video/badge/viewer). Trả về LIVE_NOT_FOUND.")
            
            try:
                import os
                import time
                os.makedirs("debug", exist_ok=True)
                timestamp = int(time.time())
                screenshot_path = f"debug/not_found_{timestamp}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"📸 [Seeder] Đã chụp màn hình trang không có Live tại: {screenshot_path}")
            except Exception as e:
                pass
                
            return LiveStatus.LIVE_NOT_FOUND

        except Exception as e:
            logger.debug(f"[Seeder] Status detect error: {e}")
            return LiveStatus.LIVE_NOT_FOUND

    async def _dismiss_popups(self):
        """Tắt các popup cảnh báo (login, age gate, v.v.)."""
        try:
            for selector in _SELECTORS["close_popup"]:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(0.5)
                        logger.debug(f"[Seeder] Dismissed popup via: {selector}")
                except Exception:
                    continue

            # Dismiss login banner/popup (TikTok hay hiện "Đăng nhập để tiếp tục xem")
            try:
                # Tìm nút X đóng trên popup login banner
                close_btns = self.page.locator('[class*="close"], [class*="Close"], [aria-label="Close"], [aria-label="Đóng"]')
                count = await close_btns.count()
                for i in range(count):
                    try:
                        btn = close_btns.nth(i)
                        if await btn.is_visible():
                            box = await btn.bounding_box()
                            if box and box['width'] < 60 and box['height'] < 60:  # Chỉ click nút nhỏ (X)
                                await btn.click()
                                await asyncio.sleep(0.3)
                                logger.debug(f"[Seeder] Dismissed login popup close button")
                                break
                    except Exception:
                        continue
            except Exception:
                pass

            # Dismiss overlay đen (nếu có)
            try:
                overlay = self.page.locator('div[class*="Overlay"]').first
                if await overlay.count() > 0 and await overlay.is_visible():
                    await overlay.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # Dismiss bằng phím Escape
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            except Exception:
                pass

        except Exception:
            pass

    async def _human_micro_action(self):
        """Hành vi vi mô ngẫu nhiên để giống người thật."""
        action = random.choice(["mouse_move", "scroll_chat", "idle", "idle"])
        try:
            if action == "mouse_move":
                # Di chuột ngẫu nhiên trên màn hình
                viewport = self.page.viewport_size
                if viewport:
                    x = random.randint(50, viewport['width'] - 50)
                    y = random.randint(50, viewport['height'] - 50)
                    await self.page.mouse.move(x, y, steps=random.randint(10, 30))

            elif action == "scroll_chat":
                # Scroll vùng chat/comment
                await self.page.evaluate("""
                    () => {
                        const chatContainer = document.querySelector('[class*="ChatContainer"], [class*="chat-list"], [class*="CommentList"]');
                        if (chatContainer) {
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        }
                    }
                """)

            else:
                # idle — không làm gì, giống người ngồi xem
                await asyncio.sleep(random.uniform(1, 3))

        except Exception:
            pass

    async def get_viewer_count(self) -> Optional[str]:
        """Lấy số người xem hiện tại (nếu có thể)."""
        try:
            for selector in _SELECTORS["viewer_count"]:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0 and await el.is_visible():
                        return await el.inner_text()
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────────────────────
    #  Cleanup
    # ──────────────────────────────────────────────────────────────────────────
    async def close(self):
        """Đóng browser."""
        self.is_watching = False
        try:
            if self.page:
                try: await self.page.close()
                except Exception: pass
            if self.context:
                try: await self.context.close()
                except Exception: pass
            if self.browser:
                try: await self.browser.close()
                except Exception: pass
            
            # Đóng tiến trình Camoufox (Firefox) hoàn toàn
            if hasattr(self, 'camoufox') and self.camoufox:
                try: await self.camoufox.stop()
                except Exception: pass
                self.camoufox = None
                
            if hasattr(self, '_playwright') and self._playwright:
                try: await self._playwright.stop()
                except Exception: pass
                
            # Đảm bảo tiến trình subprocess của CDP bị tiêu diệt
            if hasattr(self, '_browser_process') and self._browser_process:
                self._browser_process.terminate()
                
            self.page = None
            self.context = None
            self.browser = None
                
            logger.info("[Seeder] Browser closed")
        except Exception as e:
            logger.debug(f"[Seeder] Error closing: {e}")

    async def __aenter__(self):
        await self._init_browser()
        return self

    async def __aexit__(self, *args):
        await self.close()
        return self

    async def __aexit__(self, *args):
        await self.close()
        await self.close()
