"""
TikTok Uploader - Tự động upload video lên TikTok bằng Playwright
Sử dụng browser automation để upload video qua giao diện web TikTok.
"""
import asyncio
import json
import random
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import TIKTOK_CONFIG
from database.db_manager import DatabaseManager


class TikTokUploader:
    """Tự động upload video lên TikTok qua Playwright browser automation."""

    def __init__(self, db: DatabaseManager = None, cookies_file: str = None):
        self.db = db or DatabaseManager()
        self.config = TIKTOK_CONFIG
        self.cookies_file = cookies_file or self.config.get("cookies_file")
        self.browser = None
        self.context = None
        self.page = None

    async def _init_browser(self):
        """Khởi tạo Playwright browser với cookies."""
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

        try:
            # Ưu tiên dùng Chrome thật (hoặc Edge) để lách Cloudflare/Akamai 403
            self.browser = await self._playwright.chromium.launch(
                headless=browser_config.get("headless", False),
                slow_mo=browser_config.get("slow_mo", 500),
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
        except Exception:
            try:
                # Nếu không có Chrome, thử dùng Edge
                self.browser = await self._playwright.chromium.launch(
                    headless=browser_config.get("headless", False),
                    slow_mo=browser_config.get("slow_mo", 500),
                    channel="msedge",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
            except Exception:
                # Fallback dùng Chromium mặc định của Playwright
                logger.warning("Không tìm thấy Chrome/Edge, dùng Chromium mặc định (có thể bị TikTok chặn 403)")
                self.browser = await self._playwright.chromium.launch(
                    headless=browser_config.get("headless", False),
                    slow_mo=browser_config.get("slow_mo", 500),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )

        # Tạo context với viewport
        viewport = browser_config.get("viewport", {"width": 1280, "height": 720})
        self.context = await self.browser.new_context(
            viewport=viewport,
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )

        # Load cookies nếu có
        await self._load_cookies()

        self.page = await self.context.new_page()

        # Anti-detection: Override navigator.webdriver
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

        logger.info("Browser initialized successfully")

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

    async def _wait_for_upload_complete(self, timeout: int = 300):
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

    async def upload_pending_videos(self, limit: int = None, video_ids: list = None, custom_captions: dict = None) -> list:
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
            logger.info(f"\n[{i + 1}/{len(videos)}] Uploading video ID: {video['video_id']}")

            # Tạo caption
            custom_caption = custom_captions.get(video["video_id"]) if custom_captions else None
            
            if custom_caption is not None:
                caption = custom_caption
                hashtags = []
            else:
                caption = self._generate_caption(video)
                hashtags = self.config.get("default_hashtags", [])

            # Upload
            success = await self.upload_video(
                video_path=video["processed_path"],
                caption=caption,
                hashtags=hashtags,
            )

            if success:
                self.db.add_posted_video(
                    crawled_video_id=video["id"],
                    caption=caption,
                    hashtags=" ".join(hashtags),
                )
                uploaded_ids.append(video["video_id"])
                
                # Auto cleanup sau khi upload thành công
                if self.config.get("auto_cleanup_after_upload"):
                    import os
                    from pathlib import Path
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

            # Delay giữa các lần post
            if i < len(videos) - 1:
                wait_seconds = random.randint(15, 30)
                logger.info(f"  ⏳ Waiting {wait_seconds} seconds before next post...")
                await asyncio.sleep(wait_seconds)

        logger.info(f"\n📊 Upload summary: {len(uploaded_ids)}/{len(videos)} successful")
        return uploaded_ids

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
