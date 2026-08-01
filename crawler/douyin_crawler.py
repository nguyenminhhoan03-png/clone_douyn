"""
Douyin Crawler - Crawl video từ Douyin (TikTok Trung Quốc) không watermark
Sử dụng yt-dlp - công cụ download chuyên dụng hỗ trợ Douyin natively.
"""
import asyncio
import random
import re
import time
import threading
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from config.settings import DOUYIN_CONFIG, get_user_downloads_dir
from database.db_manager import DatabaseManager


class DouyinCrawler:
    """Crawl và download video từ Douyin không watermark qua Public APIs."""

    def __init__(self, db: DatabaseManager = None):
        self.db = db or DatabaseManager()
        self.headers = DOUYIN_CONFIG["headers"].copy()
        self.proxy = DOUYIN_CONFIG.get("proxy")
        self.delay_range = DOUYIN_CONFIG["request_delay"]
        self.current_username = None

    def _random_delay(self):
        """Random delay giữa các request."""
        delay = random.uniform(*self.delay_range)
        logger.debug(f"Waiting {delay:.1f}s...")
        time.sleep(delay)

    async def _async_random_delay(self):
        """Async version of random delay."""
        delay = random.uniform(*self.delay_range)
        logger.debug(f"Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Trích xuất video ID từ Douyin URL."""
        # /video/1234567890
        match = re.search(r"/video/(\d+)", url)
        if match: return match.group(1)

        # modal_id=1234567890  (jingxuan page)
        match = re.search(r"modal_id=(\d+)", url)
        if match: return match.group(1)

        return None

    def _normalize_url(self, url: str) -> str:
        """
        Chuẩn hóa URL về dạng /video/<id> để API xử lý tốt hơn.
        VD: douyin.com/jingxuan?modal_id=123 → douyin.com/video/123
        """
        match = re.search(r"modal_id=(\d+)", url)
        if match:
            video_id = match.group(1)
            normalized = f"https://www.douyin.com/video/{video_id}"
            logger.info(f"URL normalized: {url[:60]}... → {normalized}")
            return normalized
        return url

    async def resolve_short_url(self, short_url: str) -> Optional[str]:
        """Resolve Douyin short URL thành full URL."""
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=self.headers,
            proxy=self.proxy,
            timeout=15.0
        ) as client:
            try:
                resp = await client.get(short_url)
                final_url = str(resp.url)
                logger.debug(f"Resolved: {short_url} → {final_url}")
                return final_url
            except Exception as e:
                logger.error(f"Failed to resolve URL {short_url}: {e}")
                return None

    # ───────────────────────────────────────────────────────────────
    #  yt-dlp: phương pháp chính để download Douyin video
    # ───────────────────────────────────────────────────────────────

    def _build_ydl_opts(self, skip_download=True, outtmpl=None, progress_hook=None) -> dict:
        """
        Build yt-dlp options chung — tự động lấy cookies từ Chrome/Edge.
        """
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": skip_download,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.douyin.com/",
            },
        }

        if not skip_download and outtmpl:
            opts["outtmpl"] = outtmpl
            opts["merge_output_format"] = "mp4"
            opts["noprogress"] = True
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
            opts["extractor_args"] = {"douyin": {"waterfall": ["0"]}}
            if progress_hook:
                opts["progress_hooks"] = [progress_hook]

        # 1. File cookies thủ công (nếu có và hợp lệ)
        cookies_file = DOUYIN_CONFIG.get("cookies_file")
        cookies_path = Path(str(cookies_file)) if cookies_file else None
        if cookies_path and cookies_path.exists():
            # Kiểm tra sơ bộ format Netscape (dòng đầu hoặc có tab)
            try:
                first_line = cookies_path.read_text(encoding="utf-8", errors="ignore").split("\n")[0]
                if "Netscape" in first_line or "\t" in first_line:
                    opts["cookiefile"] = str(cookies_path)
                    logger.debug(f"Using cookies file: {cookies_path}")
                else:
                    logger.debug("Cookies file not Netscape format → trying browser cookies")
                    raise ValueError("not netscape")
            except Exception:
                # Thử browser cookies
                for browser in ["chrome", "edge", "firefox"]:
                    try:
                        opts["cookiesfrombrowser"] = (browser,)
                        logger.debug(f"Using cookies from browser: {browser}")
                        break
                    except Exception:
                        continue
        else:
            # 2. Tự động lấy cookies từ browser (Chrome → Edge → Firefox)
            for browser in ["chrome", "edge", "firefox"]:
                try:
                    opts["cookiesfrombrowser"] = (browser,)
                    logger.debug(f"Using cookies from browser: {browser}")
                    break
                except Exception:
                    continue

        if self.proxy:
            opts["proxy"] = self.proxy

        return opts

    def _ytdlp_extract_info(self, url: str) -> Optional[dict]:
        """
        Dùng yt-dlp để lấy thông tin video Douyin mà không download.
        Tự lấy cookies từ Chrome/Edge/Firefox trên máy bạn.
        """
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp chưa được cài! Chạy: pip install yt-dlp")
            return None

        # Thử lần lượt: có cookies browser, rồi không có
        for attempt, use_browser_cookies in enumerate([True, False], 1):
            opts = self._build_ydl_opts(skip_download=True)
            if not use_browser_cookies:
                # Lần 2: bỏ cookiesfrombrowser, thử không cookies
                opts.pop("cookiesfrombrowser", None)
                opts.pop("cookiefile", None)
                logger.debug("Attempt 2: trying without browser cookies...")

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        logger.debug(f"yt-dlp attempt {attempt} success")
                        return info
            except Exception as e:
                logger.debug(f"yt-dlp attempt {attempt} error: {e}")

        return None

    def _ytdlp_download(self, url: str, save_path: Path, progress_cb=None) -> bool:
        """
        Dùng yt-dlp để download video Douyin không watermark.
        Tự lấy cookies từ Chrome/Edge browser trên máy bạn.
        """
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp chưa được cài! Chạy: pip install yt-dlp")
            return False

        save_path.parent.mkdir(parents=True, exist_ok=True)

        def _progress_hook(d):
            if d["status"] == "downloading":
                pct   = d.get("_percent_str", "?").strip()
                speed = d.get("_speed_str",   "?").strip()
                logger.debug(f"  {pct} @ {speed}")
                if progress_cb: progress_cb(pct, speed)
            elif d["status"] == "finished":
                logger.info("  Merging/converting...")

        outtmpl = str(save_path.with_suffix("")) + ".%(ext)s"
        opts = self._build_ydl_opts(skip_download=False, outtmpl=outtmpl, progress_hook=_progress_hook)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
                for ext in [".mp4", ".webm", ".mkv"]:
                    candidate = save_path.with_suffix(ext)
                    if candidate.exists() and candidate.stat().st_size > 10_000:
                        if candidate != save_path:
                            candidate.rename(save_path)
                        return True
                if save_path.exists() and save_path.stat().st_size > 10_000:
                    return True
                logger.error("yt-dlp finished but output file not found or too small")
                return False
        except Exception as e:
            logger.error(f"yt-dlp download failed: {e}")
            return False

    async def _fetch_douyin_title(self, video_url: str) -> str:
        """Fetch title directly from Douyin page if API doesn't provide it."""
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(video_url)
                if resp.status_code == 200:
                    match = re.search(r'<title>(.*?)</title>', resp.text)
                    if match:
                        t = match.group(1).replace(" - 抖音", "").replace("抖音", "").strip()
                        return t
        except Exception as e:
            logger.debug(f"Failed to fetch title from Douyin directly: {e}")
        return ""

    async def get_video_info(self, video_url: str) -> Optional[dict]:
        """
        Lấy thông tin video từ Douyin URL dùng yt-dlp.
        Trả về dict chứa: video_id, title, author, music, no_watermark_url, ...
        """
        original_url = video_url

        # Resolve short URL để lấy video_id
        if "v.douyin.com" in video_url:
            resolved = await self.resolve_short_url(video_url)
            if not resolved: return None
            video_url = resolved

        # Normalize jingxuan?modal_id= → /video/<id>
        video_url = self._normalize_url(video_url)

        # Clean query params
        if "?" in video_url and "/video/" in video_url:
            video_url = video_url.split("?")[0]

        video_id = self._extract_video_id(video_url)
        if not video_id:
            logger.error(f"Cannot extract video ID from: {video_url}")
            return None

        logger.info(f"Video ID: {video_id} | URL: {video_url}")

        unique_vid = f"{self.current_username}_{video_id}" if self.current_username else video_id
        if self.db.is_duplicate(unique_vid, username=self.current_username):
            logger.info(f"Video already crawled: {video_id}")
            return None

        # Lấy sẵn title nếu có thể
        real_title = await self._fetch_douyin_title(video_url)
        default_title = real_title if real_title else f"Video {video_id}"

        # URL ngắn gọn nhất để truyền vào API
        api_url = original_url if "v.douyin.com" in original_url else video_url

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            },
            timeout=25.0,
            follow_redirects=True,
            verify=False,
        ) as client:

            # ── API 1: musicaldown.com ────────────────────────────────────────
            # Hỗ trợ TikTok + Douyin, không cần key
            try:
                logger.info(f"[1/4] musicaldown.com...")
                # Bước 1: Lấy token từ trang chủ
                resp0 = await client.get("https://musicaldown.com/en")
                token = ""
                if resp0.status_code == 200:
                    m = re.search(r'name="([^"]+)"\s+value="([^"]+)"', resp0.text)
                    if m:
                        token_name, token_val = m.group(1), m.group(2)
                    else:
                        token_name, token_val = "", ""
                # Bước 2: Post URL
                if token_name:
                    resp = await client.post(
                        "https://musicaldown.com/download",
                        data={"id": api_url, token_name: token_val},
                        headers={
                            "Origin": "https://musicaldown.com",
                            "Referer": "https://musicaldown.com/en",
                        },
                    )
                    if resp.status_code == 200:
                        # Tìm link mp4
                        m2 = re.search(r'href="(https://[^"]+\.mp4[^"]*)"', resp.text)
                        if m2:
                            dl_url = m2.group(1)
                            logger.info("✅ musicaldown success!")
                            return {
                                "video_id": video_id,
                                "source_url": video_url,
                                "title": default_title,
                                "author": "unknown",
                                "music_title": "",
                                "tags": "",
                                "no_watermark_url": dl_url,
                                "duration": 0,
                                "_ytdlp_url": api_url,
                            }
                        else:
                            logger.debug(f"musicaldown: no mp4 link found")
                    else:
                        logger.debug(f"musicaldown step2 HTTP {resp.status_code}")
                else:
                    logger.debug("musicaldown: no token found")
            except Exception as e:
                logger.debug(f"musicaldown error: {e}")

            # ── API 2: savetik.co ─────────────────────────────────────────────
            try:
                logger.info(f"[2/4] savetik.co...")
                resp = await client.post(
                    "https://www.savetik.co/api/ajaxSearch",
                    data={"q": api_url, "lang": "en"},
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://www.savetik.co",
                        "Referer": "https://www.savetik.co/",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "ok":
                        html = data.get("data", "")
                        # Tìm link mp4 không watermark
                        m = re.search(r'href="(https://[^"]+\.mp4[^"]*)"[^>]*>[^<]*(?:No watermark|HD|Watermark free)', html, re.IGNORECASE)
                        if not m:
                            m = re.search(r'href="(https://[^"]+\.mp4[^"]*)"', html)
                        if m:
                            dl_url = m.group(1)
                            m_title = re.search(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
                            title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip() if m_title else default_title
                            logger.info("✅ savetik.co success!")
                            return {
                                "video_id": video_id,
                                "source_url": video_url,
                                "title": title[:200],
                                "author": "unknown",
                                "music_title": "",
                                "tags": "",
                                "no_watermark_url": dl_url,
                                "duration": 0,
                                "_ytdlp_url": api_url,
                            }
                    logger.debug(f"savetik fail: {str(data)[:100]}")
            except Exception as e:
                logger.debug(f"savetik error: {e}")

            # ── API 3: snapdouyin.app ─────────────────────────────────────────
            try:
                logger.info(f"[3/4] snapdouyin.app...")
                resp = await client.post(
                    "https://snapdouyin.app/wp-json/aio-dl/video-data/",
                    data={"url": video_url},  # dùng clean URL
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": "https://snapdouyin.app/",
                        "Origin": "https://snapdouyin.app",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    medias = data.get("medias", [])
                    best = next(
                        (m for m in medias if m.get("quality") in ("hd", "sd") and m.get("url")),
                        next((m for m in medias if m.get("url")), None),
                    )
                    if best and best.get("url"):
                        logger.info("✅ snapdouyin.app success!")
                        return {
                            "video_id": video_id,
                            "source_url": video_url,
                            "title": data.get("title", default_title)[:200],
                            "author": "unknown",
                            "music_title": "",
                            "tags": "",
                            "no_watermark_url": best["url"],
                            "duration": 0,
                            "_ytdlp_url": api_url,
                        }
                    logger.debug(f"snapdouyin fail: medias={len(medias)} | {str(data)[:100]}")
            except Exception as e:
                logger.debug(f"snapdouyin error: {e}")

            # ── API 4: dlpanda.com ────────────────────────────────────────────
            try:
                logger.info(f"[4/4] dlpanda.com...")
                resp = await client.post(
                    "https://dlpanda.com/api",
                    json={"url": api_url},
                    headers={
                        "Content-Type": "application/json",
                        "Referer": "https://dlpanda.com/",
                        "Origin": "https://dlpanda.com",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    videos = data.get("data", {}).get("video", []) or data.get("video", [])
                    if isinstance(videos, list) and videos:
                        dl_url = videos[0].get("url") if isinstance(videos[0], dict) else videos[0]
                    elif isinstance(videos, str):
                        dl_url = videos
                    else:
                        dl_url = data.get("url") or data.get("data", {}).get("url")
                    if dl_url:
                        logger.info("✅ dlpanda success!")
                        return {
                            "video_id": video_id,
                            "source_url": video_url,
                            "title": data.get("title", default_title)[:200],
                            "author": "unknown",
                            "music_title": "",
                            "tags": "",
                            "no_watermark_url": dl_url,
                            "duration": 0,
                            "_ytdlp_url": api_url,
                        }
                    logger.debug(f"dlpanda fail: {str(data)[:150]}")
            except Exception as e:
                logger.debug(f"dlpanda error: {e}")

        # ── Fallback: yt-dlp với browser cookies ──────────────────────────────
        logger.info(f"[fallback] yt-dlp with browser cookies...")
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, self._ytdlp_extract_info, api_url)
        if info:
            logger.info(f"✅ yt-dlp OK: '{str(info.get('title',''))[:50]}'")
            return {
                "video_id": str(info.get("id", video_id)),
                "source_url": video_url,
                "title": (info.get("description") or info.get("title") or f"Video {video_id}")[:200],
                "author": info.get("uploader") or info.get("creator") or "unknown",
                "music_title": info.get("track") or "",
                "tags": "",
                "no_watermark_url": info.get("url") or "",
                "duration": int(info.get("duration") or 0),
                "_ytdlp_url": api_url,
            }

        logger.error(
            f"❌ Tất cả API thất bại cho video: {video_id}\n"
            f"   URL: {video_url}\n"
            f"   → Cần cookies Douyin hợp lệ hoặc proxy"
        )
        return None

    async def download_video(self, video_info: dict, save_dir: str = None) -> Optional[str]:
        """Download video: ưu tiên direct URL từ web API, fallback yt-dlp."""
        video_id        = video_info.get("video_id", "unknown")
        direct_url      = video_info.get("no_watermark_url", "")
        ytdlp_url       = video_info.get("_ytdlp_url") or video_info.get("source_url")

        save_dir = Path(save_dir) if save_dir else get_user_downloads_dir(self.current_username)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{video_id}.mp4"

        if save_path.exists() and save_path.stat().st_size > 10_000:
            logger.info(f"Video already downloaded: {save_path}")
            return str(save_path)

        # ── Cách 1: Direct download từ URL trả về bởi web API ─────────────────
        if direct_url and direct_url.startswith("http"):
            logger.info(f"Downloading {video_id} via direct URL...")
            try:
                async with httpx.AsyncClient(
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                        "Referer": "https://www.douyin.com/",
                    },
                    timeout=120.0,
                    follow_redirects=True,
                    verify=False,
                ) as client:
                    async with client.stream("GET", direct_url) as resp:
                        if resp.status_code == 200:
                            total = int(resp.headers.get("content-length", 0))
                            downloaded = 0
                            with open(save_path, "wb") as f:
                                async for chunk in resp.aiter_bytes(chunk_size=65536):
                                    f.write(chunk)
                                    downloaded += len(chunk)
                            if save_path.stat().st_size > 10_000:
                                size_mb = save_path.stat().st_size / 1024 / 1024
                                logger.info(f"✅ Downloaded: {save_path.name} ({size_mb:.1f} MB)")
                                return str(save_path)
                            else:
                                logger.warning("File too small, trying yt-dlp...")
                                save_path.unlink(missing_ok=True)
                        else:
                            logger.warning(f"Direct URL failed: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Direct download error: {e} → falling back to yt-dlp")
                save_path.unlink(missing_ok=True)

        # ── Cách 2: yt-dlp fallback ────────────────────────────────────────────
        if ytdlp_url:
            logger.info(f"Downloading {video_id} via yt-dlp...")
            loop = asyncio.get_event_loop()
            ok = await loop.run_in_executor(None, self._ytdlp_download, ytdlp_url, save_path)
            if ok and save_path.exists():
                size_mb = save_path.stat().st_size / 1024 / 1024
                logger.info(f"✅ Downloaded: {save_path.name} ({size_mb:.1f} MB)")
                return str(save_path)

        logger.error(f"❌ Download thất bại: {video_id}")
        if save_path.exists():
            save_path.unlink(missing_ok=True)
        return None

    async def crawl_single_video(self, video_url: str) -> Optional[dict]:
        """Crawl một video từ URL Douyin."""
        logger.info(f"Crawling video: {video_url}")
        
        video_info = await self.get_video_info(video_url)
        if not video_info:
            logger.warning(f"Could not get info for: {video_url}")
            return None

        download_path = await self.download_video(video_info)
        if not download_path:
            logger.warning(f"Could not download: {video_url}")
            return None

        import time
        base_vid = video_info["video_id"]
        timestamp = int(time.time() * 1000)
        # Gắn thêm timestamp để cho phép crawl cùng 1 video nhiều lần (đáp ứng nghiệp vụ phân luồng nhiều bản sao)
        unique_vid = f"{self.current_username}_{base_vid}_{timestamp}" if self.current_username else f"{base_vid}_{timestamp}"
        
        row_id = self.db.add_crawled_video(
            video_id=unique_vid,
            source_url=video_info["source_url"],
            title=video_info["title"],
            author=video_info["author"],
            music_title=video_info["music_title"],
            tags=video_info["tags"],
            download_path=download_path,
            duration=video_info["duration"],
            username=self.current_username,
        )

        if row_id > 0:
            self.db.update_video_status(unique_vid, "downloaded")
            video_info["video_id"] = unique_vid
            video_info["download_path"] = download_path
            video_info["db_id"] = row_id
            return video_info

        return None

    async def crawl_multiple_videos(self, video_urls: list) -> list:
        """Crawl nhiều video từ danh sách URLs."""
        results = []
        total = len(video_urls)
        for i, url in enumerate(video_urls, 1):
            logger.info(f"[{i}/{total}] Processing: {url}")
            result = await self.crawl_single_video(url)
            if result:
                results.append(result)
            await self._async_random_delay()

        logger.info(f"Crawled {len(results)}/{total} videos successfully")
        return results

    async def crawl_user_profile(self, user_url: str, max_videos: int = None) -> list:
        """Crawl video từ profile Douyin user thông qua Web API."""
        logger.warning("Crawl user profile without cookies might fail if Douyin blocks the request.")
        max_videos = max_videos or DOUYIN_CONFIG["max_videos_per_session"]

        if "v.douyin.com" in user_url:
            user_url = await self.resolve_short_url(user_url)
            if not user_url: return []

        match = re.search(r"/user/([A-Za-z0-9_-]+)", user_url)
        if not match: return []

        sec_uid = match.group(1)
        logger.info(f"Crawling user profile: {sec_uid} (max {max_videos} videos)")

        results = []
        max_cursor = 0
        has_more = True

        import http.cookiejar
        cookies_file = DOUYIN_CONFIG.get("cookies_file")
        client_cookies = httpx.Cookies()
        if cookies_file and Path(cookies_file).exists():
            try:
                cj = http.cookiejar.MozillaCookieJar(cookies_file)
                cj.load(ignore_discard=True, ignore_expires=True)
                for cookie in cj:
                    client_cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
            except Exception as e:
                logger.debug(f"Failed to load Netscape cookies for profile crawl: {e}")

        async with httpx.AsyncClient(
            headers=self.headers,
            cookies=client_cookies,
            proxy=self.proxy,
            timeout=15.0,
            follow_redirects=True
        ) as client:
            while has_more and len(results) < max_videos:
                try:
                    api_url = "https://www.douyin.com/aweme/v1/web/aweme/post/"
                    params = {
                        "sec_user_id": sec_uid,
                        "count": "18",
                        "max_cursor": str(max_cursor),
                        "aid": "6383",
                        "cookie_enabled": "true",
                        "platform": "PC",
                        "downlink": "10",
                    }
                    resp = await client.get(api_url, params=params)
                    if resp.status_code != 200: break
                    
                    try:
                        data = resp.json()
                    except Exception:
                        logger.error("Douyin chặn truy cập (yêu cầu xác minh/captcha hoặc cần Cookies hợp lệ). Không thể lấy danh sách video Profile.")
                        break
                        
                    aweme_list = data.get("aweme_list", [])
                    has_more = data.get("has_more", 0) == 1
                    max_cursor = data.get("max_cursor", 0)

                    if not aweme_list: break

                    for aweme in aweme_list:
                        if len(results) >= max_videos: break
                        
                        video_url = f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}"
                        video_id = str(aweme.get("aweme_id", ""))
                        unique_vid = f"{self.current_username}_{video_id}" if self.current_username else video_id
                        if self.db.is_duplicate(unique_vid, username=self.current_username): continue
                        
                        video_data = await self.get_video_info(video_url)
                        if not video_data: continue

                        download_path = await self.download_video(video_data)
                        if download_path:
                            self.db.add_crawled_video(
                                video_id=unique_vid,
                                source_url=video_data["source_url"],
                                title=video_data["title"],
                                author=video_data["author"],
                                music_title=video_data["music_title"],
                                tags=video_data["tags"],
                                download_path=download_path,
                                duration=video_data["duration"],
                                username=self.current_username,
                            )
                            self.db.update_video_status(unique_vid, "downloaded")
                            video_data["video_id"] = unique_vid
                            video_data["download_path"] = download_path
                            results.append(video_data)
                        await self._async_random_delay()
                except Exception as e:
                    logger.error(f"Error crawling profile: {e}")
                    break

        logger.info(f"Finished crawling user profile: {len(results)} videos")
        return results

def crawl_videos_sync(urls: list, username: str = None) -> list:
    crawler = DouyinCrawler()
    crawler.current_username = username
    return asyncio.run(crawler.crawl_multiple_videos(urls))

def crawl_profile_sync(user_url: str, max_videos: int = 10, username: str = None) -> list:
    crawler = DouyinCrawler()
    crawler.current_username = username
    return asyncio.run(crawler.crawl_user_profile(user_url, max_videos))
