"""
TikTok Uploader - Tự động upload video lên TikTok bằng Playwright
Sử dụng browser automation để upload video qua giao diện web TikTok.
"""
import asyncio
import json
import random
import time
from pathlib import Path
from typing import Optional, Callable

from loguru import logger

from config.settings import TIKTOK_CONFIG
from database.db_manager import DatabaseManager


# ═══════════════════════════════════════════════════════════════════════════════
#  Anti-Detection Fingerprint Pools
#  Mỗi lần mở browser sẽ random 1 bộ để mỗi nick trông như 1 thiết bị khác nhau
# ═══════════════════════════════════════════════════════════════════════════════
_VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
    {"width": 1920, "height": 1080},
    {"width": 1600, "height": 900},
    {"width": 1280, "height": 720},
    {"width": 1360, "height": 768},
]

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

_LOCALES = ["vi-VN", "en-US", "vi", "en-GB", "en"]
_TIMEZONES = ["Asia/Ho_Chi_Minh", "Asia/Bangkok", "Asia/Singapore", "Asia/Jakarta"]

# Anti-detection JS injection — Không dùng Object.defineProperty để tránh bị vướng lỗi "Masking detected" của Pixelscan
_ANTI_DETECT_SCRIPT = """
    // Xóa dấu vết cơ bản mà không can thiệp sâu vào DOM
    if (navigator.webdriver !== undefined) {
        delete Object.getPrototypeOf(navigator).webdriver;
    }
    if (!window.chrome) {
        window.chrome = { runtime: {} };
    }
"""


class TikTokUploader:
    """Tự động upload video lên TikTok qua Playwright browser automation."""

    def __init__(self, db: DatabaseManager = None, cookies_file: str = None, proxy: str = None, window_idx: int = 0, username: str = None):
        self.db = db or DatabaseManager()
        self.current_username = username
        self.config = TIKTOK_CONFIG
        self.cookies_file = cookies_file or self.config.get("cookies_file")
        self.proxy = proxy  # Format: "http://user:pass@ip:port" hoặc "socks5://ip:port"
        self.window_idx = window_idx # Dùng để sắp xếp vị trí cửa sổ
        self.browser = None
        self.context = None
        self.page = None

    async def _init_browser(self):
        """Khởi tạo Playwright browser với cookies, proxy, và random fingerprint."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "Playwright chưa cài! Chạy:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )
            raise

        self._playwright = await async_playwright().start()

        browser_config = self.config.get("browser", {})

        # ── Fix Timezone khớp với Proxy VN ──────────────────────────────
        # Proxy dân cư sếp mua là IP Việt Nam, nếu random ra múi giờ Singapore/Jakarta 
        # sẽ bị web phát hiện "Timezone Mismatch". Bắt buộc phải là GMT+7.
        fp_timezone = "Asia/Ho_Chi_Minh" 
        
        # ── Random fingerprint cho mỗi nick ──────────────────────────────
        fp_viewport = random.choice(_VIEWPORTS)
        fp_user_agent = random.choice(_USER_AGENTS)
        fp_locale = random.choice(_LOCALES)

        # Tính toán kích thước và vị trí cửa sổ (Mô phỏng đt xếp hàng)
        win_w = 420
        win_h = 800
        # Xếp các cửa sổ liên tiếp nhau từ trái qua phải, nếu hết màn (VD 1920) thì xuống dòng
        max_cols = 1920 // win_w
        if max_cols == 0: max_cols = 1
        
        row = self.window_idx // max_cols
        col = self.window_idx % max_cols
        
        pos_x = col * win_w
        pos_y = row * 50 # Xuống dòng thì thụt xuống 1 xíu để thấy viền trên

        # ── Build launch kwargs (có thể có proxy) ────────────────────────
        launch_kwargs = {
            "headless": browser_config.get("headless", False),
            "slow_mo": browser_config.get("slow_mo", 500),
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--webrtc-ip-handling-policy=disable_non_proxied_udp",
                f"--window-size={win_w},{win_h}",
                f"--window-position={pos_x},{pos_y}",
                "--force-device-scale-factor=1", # Khử triệt để lỗi lẻ số thập phân do Scale của Windows
            ],
        }
        if self.proxy:
            proxy_str = self.proxy.strip()
            if proxy_str.startswith("http://") or proxy_str.startswith("socks5://"):
                launch_kwargs["proxy"] = {"server": proxy_str}
            else:
                parts = proxy_str.split(":")
                if len(parts) == 4:
                    ip, port, user, pwd = parts
                    launch_kwargs["proxy"] = {
                        "server": f"http://{ip}:{port}",
                        "username": user,
                        "password": pwd
                    }
                elif len(parts) == 2:
                    ip, port = parts
                    launch_kwargs["proxy"] = {"server": f"http://{ip}:{port}"}
                else:
                    launch_kwargs["proxy"] = {"server": proxy_str}
                    
            display_proxy = proxy_str
            if ":" in proxy_str and len(proxy_str.split(":")) == 4:
                parts = proxy_str.split(":")
                display_proxy = f"{parts[0]}:{parts[1]} (có user/pass)"
                
            logger.info(f"🌐 Sử dụng proxy: {display_proxy}")

        # ── Profile Directory (Khởi tạo máy mới thực sự) ──────────────────
        # Thay vì dùng trình duyệt ẩn danh (Incognito) sẽ bị mất LocalStorage/Cache
        # Ta tạo riêng 1 thư mục vật lý (Profile) cho từng nick như người dùng thật.
        import os
        from pathlib import Path
        cookie_path = Path(self.cookies_file) if self.cookies_file else Path("default.json")
        profile_dir = cookie_path.parent / ".profiles" / cookie_path.stem
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            try:
                self.context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel="chrome", 
                    no_viewport=True,
                    user_agent=fp_user_agent,
                    locale=fp_locale,
                    timezone_id=fp_timezone,
                    **launch_kwargs
                )
            except Exception:
                try:
                    self.context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        channel="msedge", 
                        no_viewport=True,
                        user_agent=fp_user_agent,
                        locale=fp_locale,
                        timezone_id=fp_timezone,
                        **launch_kwargs
                    )
                except Exception:
                    logger.warning("Không tìm thấy Chrome/Edge, dùng Chromium mặc định")
                    self.context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        no_viewport=True,
                        user_agent=fp_user_agent,
                        locale=fp_locale,
                        timezone_id=fp_timezone,
                        **launch_kwargs
                    )
        except Exception as e:
            err_str = str(e).lower()
            if "in use" in err_str or "locked" in err_str:
                raise Exception("Trình duyệt cũ chưa được đóng hẳn (Thư mục Profile đang bị khóa). Vui lòng tắt thủ công các cửa sổ Chrome đang mở hoặc chạy Task Manager để End Task 'chrome.exe' rồi thử lại!")
            raise e

        logger.info(
            f"🎭 Fingerprint: {fp_viewport['width']}x{fp_viewport['height']} | "
            f"{fp_locale} | {fp_timezone} | UA: ...{fp_user_agent[-30:]}"
        )

        # Không cần gọi new_context vì launch_persistent_context đã trả về context

        # Load cookies nếu có
        await self._load_cookies()

        # Lấy tab (page) mặc định đã được mở sẵn khi launch
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Kiểm tra mạng/proxy sống hay chết trước khi tiếp tục
        await self._check_network_and_proxy()

        logger.info("Browser initialized successfully (anti-detect enabled)")

    async def _check_network_and_proxy(self):
        """Kiểm tra IP hiện tại qua context để đảm bảo Proxy sống trước khi làm việc."""
        try:
            logger.info("🔍 Đang kiểm tra kết nối mạng và Proxy (Check IP)...")
            response = await self.page.goto("https://api.ipify.org", timeout=15000)
            if response and response.ok:
                ip = await response.text()
                logger.info(f"✅ KẾT NỐI THÀNH CÔNG. IP hiện tại: {ip.strip()}")
            else:
                raise Exception(f"HTTP Status: {response.status if response else 'No response'}")
        except Exception as e:
            err_msg = str(e).split('\n')[0]
            logger.error(f"❌ Lỗi Proxy/Mạng: {err_msg}")
            raise Exception(f"Lỗi Proxy/Mạng: {err_msg}")

    async def _load_cookies(self):
        """Load cookies TikTok từ file JSON."""
        cookies_file = self.cookies_file

        if not cookies_file or not Path(cookies_file).exists():
            logger.warning(
                f"TikTok cookies file not found: {cookies_file}\n"
                f"Hướng dẫn lấy cookies:\n"
                f"  1. Mở Chrome, đăng nhập TikTok\n"
                f"  2. F12 → Console, paste đoạn code sau:\n"
                f'     copy(JSON.stringify(document.cookie.split("; ").map(c => {{\n'
                f'       const [name, ...v] = c.split("=");\n'
                f'       return {{name, value: v.join("="), domain: ".tiktok.com", path: "/"}};\n'
                f"     }})))\n"
                f"  3. Paste vào file: {cookies_file}"
            )
            return

        try:
            with open(cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            # Đảm bảo format đúng cho Playwright
            formatted_cookies = []
            for cookie in cookies:
                formatted = {
                    "name": cookie.get("name", ""),
                    "value": cookie.get("value", ""),
                    "domain": cookie.get("domain", ".tiktok.com"),
                    "path": cookie.get("path", "/"),
                }
                if formatted["name"] and formatted["value"]:
                    formatted_cookies.append(formatted)

            await self.context.add_cookies(formatted_cookies)
            logger.info(f"Loaded {len(formatted_cookies)} TikTok cookies")
        except Exception as e:
            logger.error(f"Failed to load TikTok cookies: {e}")

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Random delay để mô phỏng hành vi người thật."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def check_login(self) -> bool:
        """Kiểm tra đã đăng nhập TikTok chưa."""
        try:
            # Lách luật 403 Forbidden của TikTok: vào trang chủ trước khi vào trang upload
            try:
                await self.page.goto("https://www.tiktok.com/", wait_until="load", timeout=20000)
            except Exception:
                pass
            await self._random_delay(2, 4)

            try:
                await self.page.goto("https://www.tiktok.com/tiktokstudio/upload",
                                      wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                if "interrupted" in str(e).lower():
                    await self._random_delay(2, 4)
                    await self.page.goto("https://www.tiktok.com/tiktokstudio/upload",
                                          wait_until="domcontentloaded", timeout=30000)
                else:
                    raise e
                    
            await self._random_delay(2, 4)

            # Kiểm tra xem có bị redirect về trang login không
            current_url = self.page.url
            if "login" in current_url.lower():
                logger.warning("Not logged in! Please update cookies.")
                return False

            logger.info("TikTok login verified ✓")
            return True
        except Exception as e:
            logger.error(f"Login check failed: {e}")
            return False

    async def upload_video(self, video_path: str, caption: str,
                           hashtags: list = None) -> bool:
        """
        Upload một video lên TikTok.

        Args:
            video_path: Đường dẫn file video
            caption: Mô tả video
            hashtags: List hashtags (không có dấu #)

        Returns:
            True nếu upload thành công
        """
        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False

        if not self.page:
            await self._init_browser()

        logger.info(f"Uploading: {video_path.name}")
        logger.info(f"Caption: {caption[:50]}...")

        try:
            # 1. Navigate đến trang upload
            # Nếu chưa ở trang upload thì vào qua trang chủ để tránh 403
            if "upload" not in self.page.url:
                try:
                    await self.page.goto("https://www.tiktok.com/", wait_until="load", timeout=20000)
                except Exception:
                    pass
                await self._random_delay(2, 4)
                
            try:
                await self.page.goto(
                    "https://www.tiktok.com/tiktokstudio/upload",
                    wait_until="domcontentloaded",
                    timeout=30000
                )
            except Exception as e:
                if "interrupted" in str(e).lower():
                    await self._random_delay(2, 4)
                    await self.page.goto(
                        "https://www.tiktok.com/tiktokstudio/upload",
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                else:
                    raise e
                    
            await self._random_delay(3, 5)

            # Kiểm tra login
            if "login" in self.page.url.lower():
                logger.error("Not logged in! Upload cancelled.")
                return False

            # 2. Tìm input file và upload
            # TikTok upload page có iframe, cần tìm đúng element
            file_input = await self._find_file_input()
            if not file_input:
                logger.error("Cannot find file input element")
                return False

            await file_input.set_input_files(str(video_path))
            logger.info("  ✓ File selected")

            # Đợi form render sau khi chọn file
            await self._random_delay(3, 5)

            # 3. Nhập caption và hashtags (có thể nhập ngay trong lúc video đang upload)
            logger.info("  📝 Filling caption...")
            await self._fill_caption(caption, hashtags)

            # Đợi video xử lý xong (nút Post sáng lên)
            await self._wait_for_upload_complete()

            # 4. Đợi một chút rồi click Post
            await self._random_delay(2, 4)
            await self._click_post_button()

            # 5. Đợi và verify
            await self._random_delay(5, 10)
            success = await self._verify_upload()

            if success:
                logger.info(f"  ✅ Upload successful: {video_path.name}")
            else:
                logger.warning(f"  ⚠️ Upload may have succeeded but verification unclear")

            return success

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    async def _find_file_input(self):
        """Tìm input element để upload file."""
        # Thử nhiều selector vì TikTok hay thay đổi UI
        selectors = [
            'input[type="file"]',
            'input[accept="video/*"]',
            'input[accept*="video"]',
            '#upload-btn input[type="file"]',
        ]

        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(
                    selector, timeout=10000, state="attached"
                )
                if element:
                    return element
            except Exception:
                continue

        # Fallback: tìm trong iframe
        try:
            frames = self.page.frames
            for frame in frames:
                for selector in selectors:
                    try:
                        element = await frame.wait_for_selector(
                            selector, timeout=5000, state="attached"
                        )
                        if element:
                            return element
                    except Exception:
                        continue
        except Exception:
            pass

        return None

    async def _wait_for_upload_complete(self, timeout: int = 30):
        """Đợi video upload xong bằng cách check xem nút Post đã bấm được chưa."""
        logger.info("  ⏳ Waiting for video upload/encoding to finish before posting...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Kiểm tra có nút Post/Đăng chưa
                post_btn = await self.page.query_selector(
                    'button:has-text("Post"), button:has-text("Đăng"), '
                    'button:has-text("Upload"), [data-e2e="post_video_button"]'
                )
                if post_btn:
                    # Trong TikTok Studio mới, nút Post sẽ bị disabled (is_enabled=False) hoặc class báo disabled
                    # Thường playwright is_enabled() check thuộc tính disabled
                    is_disabled = await post_btn.get_attribute("disabled")
                    aria_disabled = await post_btn.get_attribute("aria-disabled")
                    
                    if is_disabled is None and aria_disabled != "true":
                        logger.info("  ✓ Upload/encoding complete (Post button enabled)")
                        return True

            except Exception:
                pass

            await asyncio.sleep(3)

        logger.warning("  ⚠️ Upload timeout, nút Post chưa sẵn sàng!")
        return False

    async def _fill_caption(self, caption: str, hashtags: list = None):
        """Nhập caption và hashtags vào form."""
        try:
            # Tìm caption input (contenteditable div hoặc textarea)
            caption_selectors = [
                '[contenteditable="true"]',
                '[data-text="true"]',
                '.public-DraftEditor-content',
                'div[class*="caption"] [contenteditable]',
                'div[class*="editor"] [contenteditable]',
            ]

            caption_element = None
            for selector in caption_selectors:
                try:
                    caption_element = await self.page.wait_for_selector(
                        selector, timeout=5000
                    )
                    if caption_element:
                        break
                except Exception:
                    continue

            if caption_element:
                # Bấm ra ngoài một cái để mất các toast thông báo che màn hình (như "Xem trước video")
                try:
                    await self.page.mouse.click(10, 10)
                    await asyncio.sleep(0.5)
                    
                    got_it_btn = await self.page.query_selector('button:has-text("Đã hiểu"), button:has-text("Got it")')
                    if got_it_btn:
                        await got_it_btn.click(force=True)
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

                # Clear existing text
                await caption_element.click(force=True)
                await self._random_delay(0.5, 1)

                # Select all và xóa
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
                await self._random_delay(0.3, 0.5)

                # Build full caption text
                full_caption = caption
                if hashtags:
                    default_tags = self.config.get("default_hashtags", [])
                    all_tags = list(set(hashtags + default_tags))
                    # Giới hạn số hashtags
                    tags_text = " ".join(all_tags[:15])
                    full_caption = f"{caption} {tags_text}"

                # Giới hạn 2200 ký tự (TikTok limit)
                full_caption = full_caption[:2200]

                # Type caption (type chậm để giống người thật)
                await caption_element.type(full_caption, delay=random.randint(30, 80))
                logger.info(f"  ✓ Caption filled ({len(full_caption)} chars)")
            else:
                logger.warning("  ⚠️ Could not find caption input")

        except Exception as e:
            logger.error(f"Error filling caption: {e}")

    async def _handle_post_anyway_modal(self, post_btn):
        """Xử lý popup 'Tiếp tục đăng?' (Post anyway) hoặc cảnh báo 'Nội dung bị hạn chế'."""
        try:
            # Đợi nhẹ 1.5s xem có popup xuất hiện không, giúp tối ưu hiệu năng không phải đợi lâu
            await asyncio.sleep(1.5)
            
            # Case 1: Popup "Tiếp tục đăng?" (Chưa check xong bản quyền)
            post_anyway_btn = await self.page.query_selector(
                'button:has-text("Đăng ngay"), button:has-text("Post anyway"), button:has-text("Continue posting")'
            )
            if post_anyway_btn:
                await post_anyway_btn.click(force=True)
                logger.info("  ✓ Clicked 'Đăng ngay' (Bypassed copyright check delay)")
                await asyncio.sleep(1)
                return
                
            # Case 2: Popup "Nội dung có thể sẽ bị hạn chế" (Cảnh báo vi phạm)
            restricted_modal = await self.page.query_selector(
                'text="Nội dung có thể sẽ bị hạn chế", text="Content may be restricted"'
            )
            if restricted_modal:
                logger.info("  ⚠️ Detected restriction warning. Clicking X and posting anyway...")
                
                # Cố gắng tìm và click nút X (Close)
                close_selectors = [
                    '[aria-label="Đóng"]', 
                    '[aria-label="Close"]',
                    'div[class*="close-icon"]',
                    'svg[class*="close"]'
                ]
                
                closed = False
                for selector in close_selectors:
                    try:
                        close_btn = await self.page.query_selector(selector)
                        if close_btn:
                            await close_btn.click(force=True)
                            closed = True
                            logger.info(f"  ✓ Clicked X (Close) via {selector}")
                            break
                    except Exception:
                        pass
                
                if not closed:
                    # Fallback: Bấm phím ESC (cách Senior nhất để đóng hầu hết modal trên web)
                    await self.page.keyboard.press("Escape")
                    logger.info("  ✓ Pressed ESC to close modal")
                
                await asyncio.sleep(1)
                
                # Bấm Đăng lại lần nữa sau khi đóng modal
                await post_btn.click(force=True)
                logger.info("  ✓ Clicked Post button AGAIN after dismissing warning")
                await asyncio.sleep(1)
                
        except Exception:
            pass

    async def _click_post_button(self):
        """Click nút Post/Đăng."""
        # Dismiss blocking modals like "Xem trước video của bạn trên điện thoại" -> "Đã hiểu"
        try:
            got_it_btn = await self.page.query_selector('button:has-text("Đã hiểu"), button:has-text("Got it")')
            if got_it_btn:
                await got_it_btn.click(force=True)
                await asyncio.sleep(1)
                logger.info("  ✓ Dismissed blocking modal/toast")
            else:
                # Try clicking somewhere safe to close any other dismissable popups
                await self.page.mouse.click(0, 0)
                await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Error dismissing modal: {e}")

        post_selectors = [
            '[data-e2e="post_video_button"]',
            'button:has-text("Post")',
            'button:has-text("Đăng")',
            'button[class*="post-button"]',
            'div[class*="btn-post"]'
        ]

        for selector in post_selectors:
            try:
                btn = await self.page.wait_for_selector(selector, timeout=5000)
                if btn:
                    is_disabled = await btn.get_attribute("disabled")
                    aria_disabled = await btn.get_attribute("aria-disabled")
                    if is_disabled is None and aria_disabled != "true":
                        await btn.click(force=True)
                        logger.info(f"  ✓ Post button clicked via {selector}")
                        await self._handle_post_anyway_modal(btn)
                        return True
            except Exception:
                continue

        # Fallback: tìm nút cuối cùng trong form
        try:
            buttons = await self.page.query_selector_all("button")
            for btn in reversed(buttons):
                text = await btn.inner_text()
                if any(keyword in text.lower() for keyword in ["post", "đăng"]):
                    is_disabled = await btn.get_attribute("disabled")
                    aria_disabled = await btn.get_attribute("aria-disabled")
                    if is_disabled is None and aria_disabled != "true":
                        await btn.click(force=True)
                        logger.info(f"  ✓ Clicked fallback button: {text}")
                        await self._handle_post_anyway_modal(btn)
                        return True
        except Exception:
            pass

        logger.error("  ✗ Could not find an enabled Post button")
        return False

    async def _verify_upload(self) -> bool:
        """Verify upload thành công."""
        try:
            logger.info("  ⏳ Verifying upload success...")
            
            # Các dấu hiệu cho thấy đã đăng thành công
            success_selectors = [
                ':has-text("Manage your posts")',
                ':has-text("Quản lý bài đăng")',
                ':has-text("Upload another video")',
                ':has-text("Tải video khác lên")',
                ':has-text("uploaded")',
                ':has-text("thành công")',
                ':has-text("đã tải lên")'
            ]
            
            # Chờ tối đa 30 giây cho popup/toast xuất hiện hoặc URL thay đổi
            for _ in range(15):
                # 1. Check URL
                url = self.page.url.lower()
                # Nếu URL thay đổi và không còn ở trang upload nữa thì tức là upload xong
                if "upload" not in url:
                    logger.info(f"  ✓ URL changed to {url} (Upload assumed success)")
                    return True
                    
                # 2. Check UI elements
                for selector in success_selectors:
                    try:
                        if await self.page.query_selector(selector):
                            logger.info(f"  ✓ Found success element: {selector}")
                            return True
                    except Exception:
                        pass
                        
                await asyncio.sleep(2)
                
            logger.warning("  ⚠️ Could not verify upload success via URL or UI (Timeout)")
            return False
        except Exception as e:
            logger.error(f"  ⚠️ Error verifying upload: {e}")
            return False

    def _generate_caption(self, video_info: dict) -> str:
        """Tạo caption tiếng Việt cho video.
        Ưu tiên dùng title đã dịch sẵn (từ processor).
        Nếu chưa có, dịch on-the-fly từ title gốc.
        """
        from utils.translator import translate_description, translate_hashtags
        import re

        # 1. Lấy title tiếng Việt (ưu tiên đã dịch sẵn trong DB)
        title_vi = video_info.get("title_vi", "")
        if not title_vi:
            original = video_info.get("title", "")
            title_vi = translate_description(original) if original else ""

        # Clean title
        title_vi = re.sub(r"#\S+", "", title_vi).strip()
        title_vi = re.sub(r"@\S+", "", title_vi).strip()
        if not title_vi or len(title_vi) < 3:
            title_vi = random.choice([
                "Nhảy đẹp quá 😍",
                "Hot dance 🔥",
                "Xinh quá trời 💃",
                "Trend mới đây 🌟",
                "Dance cực đỉnh ✨",
            ])

        # 2. Dịch hashtags gốc sang tiếng Việt
        original_tags = video_info.get("tags", "")
        vi_hashtags = translate_hashtags(original_tags) if original_tags else []

        # 3. Build caption
        caption = f"✨ {title_vi}"

        # Thêm hashtags đã dịch (tối đa 5)
        if vi_hashtags:
            caption += " " + " ".join(vi_hashtags[:5])

        # Thêm default hashtags
        default_hashtags = self.config.get("default_hashtags", [])
        caption += " " + " ".join(default_hashtags[:8])

        logger.info(f"  📝 Caption: {caption[:80]}...")
        return caption[:2200]

    async def upload_pending_videos(
        self, 
        limit: int = None, 
        video_ids: list = None, 
        custom_captions: dict = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> list:
        """
        Upload tất cả video pending lên TikTok.
        Trả về list các video_id đã upload thành công.
        """
        if video_ids is not None:
            # Manual mode: Bỏ qua giới hạn ngày, chỉ upload các video được chọn
            all_pending = self.db.get_pending_videos(limit=1000)
            videos = [v for v in all_pending if v["video_id"] in video_ids]
            today_count = self.db.get_today_post_count()
            max_posts = "Unlimited (Manual)"
        else:
            # Auto mode: Tuân thủ giới hạn ngày
            max_posts = limit or self.config.get("max_posts_per_day", 4)
            today_count = self.db.get_today_post_count()
            remaining = max_posts - today_count
            
            if remaining <= 0:
                logger.info(f"Đã đạt giới hạn {max_posts} video/ngày. Dừng upload.")
                return []
                
            videos = self.db.get_pending_videos(limit=remaining)

            
        if not videos:
            logger.info("Không có video nào pending để upload")
            return []

        logger.info(f"Found {len(videos)} videos to upload (today: {today_count}/{max_posts})")

        # Init browser
        if not self.page:
            await self._init_browser()

        # Check login
        if not await self.check_login():
            logger.error("Cannot upload: Not logged in")
            return []

        uploaded_ids = []
        interval = self.config.get("post_interval_hours", (3, 4))

        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                logger.warning("Upload bị hủy bởi người dùng!")
                break
                
            logger.info(f"\n[{i + 1}/{len(videos)}] Uploading video ID: {video['video_id']}")

            # Tạo caption
            custom_caption = custom_captions.get(video["video_id"]) if custom_captions else None
            
            if custom_caption is not None:
                caption = custom_caption
                hashtags = []
            else:
                caption = self._generate_caption(video)
                hashtags = self.config.get("default_hashtags", [])

            # Chuẩn bị file local từ Drive nếu cần
            video_path = video.get("processed_path")
            drive_processed_id = video.get("drive_processed_id")
            temp_downloaded_path = None
            
            if not video_path or not Path(video_path).exists():
                if drive_processed_id:
                    logger.info("Đang tải video từ Google Drive để upload...")
                    from uploader.google_drive_uploader import GoogleDriveUploader
                    uploader = GoogleDriveUploader(self.current_username or "default")
                    import uuid
                    from config.settings import DOWNLOADS_DIR
                    temp_downloaded_path = str(DOWNLOADS_DIR / f"upload_temp_{uuid.uuid4().hex[:8]}.mp4")
                    if uploader.download_file(drive_processed_id, temp_downloaded_path):
                        video_path = temp_downloaded_path
                    else:
                        logger.error("Không thể tải video từ Google Drive")
                        continue
                else:
                    logger.error("Không tìm thấy file video (cả local và Drive)")
                    continue

            # Upload
            success = await self.upload_video(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
            )

            if success:
                self.db.add_posted_video(
                    crawled_video_id=video["id"],
                    caption=caption,
                    hashtags=" ".join(hashtags),
                    username=self.current_username
                )
                uploaded_ids.append(video["video_id"])
                
                # Auto cleanup sau khi upload thành công
                if self.config.get("auto_cleanup_after_upload"):
                    import os
                    cleaned_files = 0
                    paths_to_remove = [video.get("download_path"), video.get("processed_path")]
                    for p in paths_to_remove:
                        if p and Path(p).exists():
                            try:
                                os.remove(p)
                                cleaned_files += 1
                            except Exception as e:
                                logger.warning(f"  ⚠️ Lỗi khi xóa file {p}: {e}")
                    
                    if cleaned_files > 0:
                        logger.info(f"  🧹 Đã xóa {cleaned_files} file cục bộ để tiết kiệm dung lượng.")
                        
                # Xóa file trên Google Drive nếu có
                if drive_processed_id:
                    try:
                        from uploader.google_drive_uploader import GoogleDriveUploader
                        uploader = GoogleDriveUploader(self.current_username or "default")
                        uploader.delete_file(drive_processed_id)
                        # Có thể xóa luôn bản chưa process (drive_download_id) nếu user muốn sạch sẽ
                        drive_download_id = video.get("drive_download_id")
                        if drive_download_id:
                            uploader.delete_file(drive_download_id)
                    except Exception as e:
                        logger.warning(f"Lỗi khi xóa file trên Drive: {e}")
                
                # Dọn dẹp file temp upload (nếu có tải từ drive)
                if temp_downloaded_path and Path(temp_downloaded_path).exists():
                    try: Path(temp_downloaded_path).unlink()
                    except: pass

            # Delay giữa các lần post
            if i < len(videos) - 1:
                if cancel_check and cancel_check():
                    break
                    
                # Đọc cấu hình delay (tính bằng phút) hoặc mặc định random 15-30 giây nếu không cấu hình (hoặc bằng 0)
                delay_mins = self.config.get("post_delay_minutes", 0)
                if delay_mins > 0:
                    wait_seconds = int(delay_mins * 60)
                    # Thêm chút random +- 5 phút (nếu delay lớn) để giống người thật
                    if wait_seconds > 300:
                        wait_seconds += random.randint(-300, 300)
                else:
                    wait_seconds = random.randint(15, 30)
                    
                logger.info(f"  ⏳ Waiting {wait_seconds} seconds before next post...")
                # Ngủ chia nhỏ để có thể dừng ngang được
                for _ in range(wait_seconds):
                    if cancel_check and cancel_check():
                        break
                    await asyncio.sleep(1)

        logger.info(f"\n📊 Upload summary: {len(uploaded_ids)}/{len(videos)} successful")
        return uploaded_ids

    async def nurture_account(
        self,
        duration_minutes: int = 15,
        like_ratio: float = 0.2,
        update_callback: Optional[Callable[[str, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Nuôi nick bằng cách lướt trang For You và thả tim ngẫu nhiên.
        
        Args:
            duration_minutes: Thời gian treo (phút).
            like_ratio: Tỷ lệ thả tim (0.0 -> 1.0).
            update_callback: Hàm callback để cập nhật log ra giao diện.
        """
        try:
            if not self.page:
                await self._init_browser()

            logger.info(f"Bắt đầu nuôi nick {self.cookies_file} trong {duration_minutes} phút...")
            if update_callback:
                update_callback(f"Bắt đầu nuôi nick trong {duration_minutes} phút...", "INFO")

            # Đi tới trang For You thẳng luôn, bỏ qua check_login (vào trang upload) để tránh rườm rà
            try:
                await self.page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                pass
            await self._random_delay(3, 6)

            start_time = time.time()
            end_time = start_time + (duration_minutes * 60)
            video_count = 0
            liked_count = 0

            while time.time() < end_time:
                if cancel_check and cancel_check():
                    break

                video_count += 1
                
                # Giả lập xem video — thời gian random tự nhiên
                # Đôi khi xem nhanh (3-8s), đôi khi xem kỹ (15-45s), đôi khi "nghỉ" đọc comment (30-90s)
                behavior_roll = random.random()
                if behavior_roll < 0.15:
                    # 15% xác suất: "nghỉ xả hơi" — giống đang đọc comment hoặc AFK
                    watch_time = random.uniform(30.0, 90.0)
                    pause_msg = f"💤 Tạm nghỉ {int(watch_time)}s (giả lập đọc comment)..."
                    logger.info(pause_msg)
                    if update_callback:
                        update_callback(pause_msg, "INFO")
                elif behavior_roll < 0.40:
                    # 25% xác suất: xem nhanh rồi lướt
                    watch_time = random.uniform(3.0, 8.0)
                else:
                    # 60% xác suất: xem bình thường
                    watch_time = random.uniform(8.0, 30.0)

                msg = f"Đang xem video thứ {video_count} (chờ {int(watch_time)}s)..."
                logger.info(msg)
                if update_callback:
                    update_callback(msg, "INFO")
                
                await asyncio.sleep(watch_time)

                # Thử tắt các popup cảnh báo (như popup rủi ro tài khoản)
                try:
                    # Dùng name="OK", exact=True để tránh bấm nhầm chữ "TikTok" (vì chứa chữ ok)
                    ok_btn = self.page.get_by_role("button", name="OK", exact=True)
                    if await ok_btn.count() > 0 and await ok_btn.first.is_visible():
                        await ok_btn.first.click()
                        logger.info("Đã tự động đóng popup cảnh báo của TikTok.")
                except Exception:
                    pass

                # Đảm bảo bot không đi lạc, nếu mất dấu /foryou hoặc /explore thì quay về
                try:
                    current_url = self.page.url
                    if "tiktok.com/@" in current_url or ("/foryou" not in current_url and "/explore" not in current_url):
                        logger.info("Bị đi lạc khỏi trang chủ, đang quay lại For You...")
                        await self.page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded")
                        await self._random_delay(2, 4)
                except Exception:
                    pass

                # Thả tim ngẫu nhiên — nhưng không like liên tục, đôi khi skip vài video
                if random.random() < like_ratio and watch_time > 5.0:
                    try:
                        # TikTok có nhiều nút tim trong DOM, ta tìm nút nào đang nằm CHÍNH XÁC trên màn hình (viewport)
                        like_btns = self.page.locator('[data-e2e="like-icon"]')
                        viewport = self.page.viewport_size
                        vh = viewport['height'] if viewport else 800
                        for i in range(await like_btns.count()):
                            if await like_btns.nth(i).is_visible():
                                box = await like_btns.nth(i).bounding_box()
                                # Nút tim phải nằm trong vùng nhìn thấy của màn hình (từ 0 đến vh)
                                if box and 0 <= box['y'] <= vh:
                                    # Mô phỏng thao tác di chuột và click thật để vượt bot detection
                                    target_x = box['x'] + box['width'] / 2
                                    target_y = box['y'] + box['height'] / 2
                                    
                                    await self.page.mouse.move(target_x, target_y, steps=10)
                                    await asyncio.sleep(random.uniform(0.1, 0.3))
                                    await self.page.mouse.click(target_x, target_y, delay=random.randint(50, 150))
                                    
                                    liked_count += 1
                                    like_msg = f"❤️ Đã thả tim video thứ {video_count}"
                                    logger.info(like_msg)
                                    if update_callback:
                                        update_callback(like_msg, "SUCCESS")
                                    await self._random_delay(1, 3)
                                    break
                    except Exception as e:
                        logger.debug(f"Không thể thả tim: {e}")

                # Follow ngẫu nhiên (Khoảng 5% xác suất nếu xem lâu)
                if random.random() < 0.05 and watch_time > 8.0:
                    try:
                        # Tìm nút follow (nút + đỏ dưới avatar hoặc nút chữ Follow/Theo dõi)
                        follow_locators = ['[data-e2e="feed-follow"]', 'button:has-text("Follow")', 'button:has-text("Theo dõi")']
                        followed = False
                        viewport = self.page.viewport_size
                        vh = viewport['height'] if viewport else 800
                        
                        for loc in follow_locators:
                            if followed: break
                            btns = self.page.locator(loc)
                            for i in range(await btns.count()):
                                if await btns.nth(i).is_visible():
                                    box = await btns.nth(i).bounding_box()
                                    if box and 0 <= box['y'] <= vh:
                                        await btns.nth(i).click(force=True)
                                        flw_msg = f"👤 Đã bấm Follow chủ kênh video thứ {video_count}"
                                        logger.info(flw_msg)
                                        if update_callback:
                                            update_callback(flw_msg, "SUCCESS")
                                        await self._random_delay(1, 3)
                                        followed = True
                                        break
                    except Exception as e:
                        logger.debug(f"Không thể Follow: {e}")

                # Lướt sang video tiếp theo — đôi khi scroll nhanh 2-3 video liên tiếp
                try:
                    await self.page.keyboard.press("ArrowDown")
                    # 20% xác suất: scroll nhanh thêm 1-2 video (giống lướt qua video không thích)
                    if random.random() < 0.20:
                        extra_scrolls = random.randint(1, 2)
                        for _ in range(extra_scrolls):
                            await self._random_delay(0.5, 1.5)
                            await self.page.keyboard.press("ArrowDown")
                            video_count += 1
                    await self._random_delay(1, 2)
                except Exception as e:
                    logger.debug(f"Lỗi cuộn trang: {e}")
                    await self.page.evaluate("window.scrollBy(0, window.innerHeight);")
                    await self._random_delay(1, 2)
                    
            summary = f"🎉 Hoàn thành nuôi nick! Đã xem ~{video_count} video, thả tim {liked_count} lần."
            logger.info(summary)
            if update_callback:
                update_callback(summary, "SUCCESS")
                
            return True

        except Exception as e:
            err = f"Lỗi trong quá trình nuôi nick: {e}"
            logger.error(err)
            if update_callback:
                update_callback(err, "ERROR")
            return False

    async def execute_farm_flow(
        self,
        flow: dict,
        update_callback: Optional[Callable[[str, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """Thực thi một Kịch bản nuôi (Farm Flow) với nhiều bước."""
        try:
            if not self.page:
                await self._init_browser()
                
            steps = flow.get("steps", [])
            if not steps:
                if update_callback: update_callback("Kịch bản trống!", "ERROR")
                return False
                
            if update_callback: update_callback(f"🚀 Bắt đầu chạy Kịch bản: {flow.get('name')}", "INFO")
                
            for idx, step in enumerate(steps):
                if cancel_check and cancel_check():
                    break
                    
                step_type = step.get("type")
                if update_callback: update_callback(f"--- Bước {idx+1}: {step_type} ---", "INFO")
                
                if step_type == "scroll_foryou":
                    await self.nurture_account(
                        duration_minutes=step.get("duration", 10),
                        like_ratio=step.get("like_ratio", 0.2),
                        update_callback=update_callback,
                        cancel_check=cancel_check
                    )
                elif step_type == "search_and_interact":
                    await self._action_search_and_interact(step, update_callback, cancel_check)
                elif step_type == "rest":
                    duration = step.get("duration", 5)
                    if update_callback: update_callback(f"💤 Bắt đầu ngâm máy {duration} phút...", "INFO")
                    
                    end_time = time.time() + (duration * 60)
                    while time.time() < end_time:
                        if cancel_check and cancel_check(): break
                        await asyncio.sleep(2)
                        
            if update_callback: update_callback(f"🎉 Hoàn thành Kịch bản: {flow.get('name')}", "SUCCESS")
            return True
        except Exception as e:
            import traceback
            logger.error(f"Lỗi khi chạy Flow: {repr(e)}\n{traceback.format_exc()}")
            if update_callback: update_callback(f"Lỗi Kịch bản: {repr(e)}", "ERROR")
            return False

    async def _action_search_and_interact(self, step, update_callback, cancel_check):
        import urllib.parse
        keyword = step.get("keyword", "")
        watch_count = int(step.get("watch_count", 3))
        like_ratio = float(step.get("like_ratio", 0.5))
        follow_ratio = float(step.get("follow_ratio", 0.1))
        
        if not keyword:
            if update_callback: update_callback("Từ khóa trống, bỏ qua tìm kiếm.", "WARNING")
            return
            
        if update_callback: update_callback(f"🔍 Tìm kiếm từ khóa: '{keyword}'", "INFO")
        
        try:
            url = f"https://www.tiktok.com/search/video?q={urllib.parse.quote(keyword)}"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
            
        await self._random_delay(3, 5)
        
        try:
            # Scroll nhẹ để load nếu mạng chậm
            await self.page.evaluate("window.scrollBy(0, 300);")
            await asyncio.sleep(2)
            
            # Thử nhiều cách xác định Video đầu tiên vì TikTok hay đổi DOM
            first_video = None
            locators_to_try = [
                "[data-e2e='search-card-video-link']",
                "[data-e2e='search_video-item'] a",
                "a:has(video)",
                "div[class*='DivItemContainer'] a",
                "[data-e2e='search-card-user-link']"
            ]
            
            for loc in locators_to_try:
                elements = self.page.locator(loc)
                if await elements.count() > 0:
                    first_video = elements.first
                    break
                    
            if first_video:
                await first_video.click()
                await self._random_delay(2, 4)
            else:
                if update_callback: update_callback(f"Không tìm thấy video nào cho từ khóa '{keyword}'", "WARNING")
                return
                
            # Đã mở Video Modal, bắt đầu xem và lướt
            for i in range(watch_count):
                if cancel_check and cancel_check(): break
                
                watch_time = random.uniform(8.0, 35.0)
                if update_callback: update_callback(f"Đang xem video tìm kiếm thứ {i+1} (chờ {int(watch_time)}s)...", "INFO")
                await asyncio.sleep(watch_time)
                
                # Thả tim
                if random.random() < like_ratio:
                    try:
                        like_btn = self.page.locator("[data-e2e='browse-like-icon']").first
                        if await like_btn.count() > 0:
                            await like_btn.click()
                            if update_callback: update_callback("❤️ Đã thả tim video tìm kiếm!", "SUCCESS")
                            await self._random_delay(1, 2)
                    except Exception:
                        pass
                        
                # Follow
                if random.random() < follow_ratio:
                    try:
                        follow_btn = self.page.locator("[data-e2e='browse-follow']").first
                        if await follow_btn.count() > 0 and await follow_btn.is_visible():
                            await follow_btn.click()
                            if update_callback: update_callback("✅ Đã bấm Follow người đăng!", "SUCCESS")
                            await self._random_delay(1, 2)
                    except Exception:
                        pass
                
                # Next video (nhấn nút xuống trên bàn phím)
                if i < watch_count - 1:
                    await self.page.keyboard.press("ArrowDown")
                    await self._random_delay(2, 4)
                    
            # Đóng modal
            try:
                close_btn = self.page.locator("[data-e2e='browse-close']").first
                if await close_btn.count() > 0:
                    await close_btn.click()
            except Exception:
                pass
                
        except Exception as e:
            if update_callback: update_callback(f"Lỗi tương tác tìm kiếm: {e}", "ERROR")

    async def close(self):
        """Đóng browser."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, '_playwright'):
                await self._playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")

    async def __aenter__(self):
        await self._init_browser()
        return self

    async def __aexit__(self, *args):
        await self.close()
