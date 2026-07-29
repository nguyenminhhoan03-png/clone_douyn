"""
Scheduler - Lập lịch tự động crawl, process và upload video
Sử dụng APScheduler để chạy các job theo lịch.
"""
import asyncio
import signal
import sys
import re
import random
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from config.settings import SCHEDULER_CONFIG
from crawler.douyin_crawler import DouyinCrawler
from database.db_manager import DatabaseManager
from processor.video_processor import VideoProcessor
from uploader.tiktok_uploader import TikTokUploader


class AutoScheduler:
    """Tự động lập lịch crawl → process → upload video."""

    def __init__(self, douyin_urls: list = None, tt_account_file: str = None, yt_account_file: str = None, source_mode: str = "full"):
        """
        Args:
            douyin_urls: Danh sách URL Douyin để crawl
            tt_account_file: Tên file cookies của tài khoản TikTok
            yt_account_file: Tên file token của tài khoản YouTube
            source_mode: 'full' (Crawl->Process->Upload) hoặc 'upload_only' (Chỉ Upload video đã Process)
        """
        self.db = DatabaseManager()
        self.crawler = DouyinCrawler(db=self.db)
        self.processor = VideoProcessor(db=self.db)
        
        self.uploader_tt = None
        self.uploader_yt = None
        self.source_mode = source_mode
        
        from config.settings import COOKIES_DIR
        import os
        from pathlib import Path
        
        if tt_account_file:
            cookies_path = Path(tt_account_file) if os.path.isabs(tt_account_file) else COOKIES_DIR / tt_account_file
            
            # Lấy proxy từ file
            proxy_str = None
            try:
                import json
                proxy_file = cookies_path.parent / "proxies.json"
                if proxy_file.exists():
                    with open(proxy_file, "r", encoding="utf-8") as f:
                        proxies = json.load(f)
                        proxy_str = proxies.get(cookies_path.name)
            except Exception:
                pass
                
            self.uploader_tt = TikTokUploader(db=self.db, cookies_file=str(cookies_path), proxy=proxy_str)
            
        if yt_account_file:
            from uploader.youtube_uploader import YouTubeUploader
            token_path = Path(yt_account_file) if os.path.isabs(yt_account_file) else COOKIES_DIR / yt_account_file
            self.uploader_yt = YouTubeUploader(db=self.db, token_file=str(token_path))
            
        self.douyin_urls = douyin_urls or []
        self.scheduler = AsyncIOScheduler(
            timezone=SCHEDULER_CONFIG.get("timezone", "Asia/Ho_Chi_Minh")
        )
        self._running = False

    def _load_urls(self):
        """Đọc URL từ file, tách link bằng regex."""
        if self.urls_file:
            try:
                with open(self.urls_file, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    for line in lines:
                        match = re.search(r'(https?://[^\s]+)', line)
                        if match:
                            url = match.group(1)
                            if url not in self.douyin_urls:
                                self.douyin_urls.append(url)
            except Exception as e:
                logger.error(f"Error reading URL file: {e}")

    async def crawl_job(self):
        """Job crawl video từ Douyin."""
        logger.info("=" * 50)
        logger.info("🔍 CRAWL JOB STARTED")
        logger.info("=" * 50)

        try:
            if self.douyin_urls:
                # Phân loại URL: profile vs video
                profile_urls = [u for u in self.douyin_urls if "/user/" in u]
                video_urls = [u for u in self.douyin_urls if "/video/" in u or "v.douyin.com" in u or "modal_id=" in u]

                # Crawl profiles
                for url in profile_urls:
                    count = SCHEDULER_CONFIG.get("crawl_count", 10)
                    await self.crawler.crawl_user_profile(url, max_videos=count)

                # Crawl videos
                crawled_count = 0
                for raw_url in video_urls:
                    # Trích xuất link http/https trong trường hợp copy nguyên cục text chia sẻ
                    match = re.search(r'(https?://[^\s]+)', raw_url)
                    clean_url = match.group(1) if match else raw_url
                    
                    # Douyin share url usually has trailing slash which is fine, but unicode/chinese text should be removed
                    success = await self.crawler.crawl_single_video(clean_url)
                    if success:
                        crawled_count += 1
                        # Tránh rate limit
                        await asyncio.sleep(random.uniform(2, 5))
            else:
                logger.warning("No Douyin URLs configured. Skipping crawl.")

        except Exception as e:
            logger.error(f"Crawl job error: {e}")

        stats = self.db.get_stats()
        logger.info(f"📊 After crawl - Downloaded: {stats['pending_process']} pending process")

    async def process_job(self):
        """Job xử lý video (mirror, text, nhạc)."""
        logger.info("=" * 50)
        logger.info("🎬 PROCESS JOB STARTED")
        logger.info("=" * 50)

        try:
            results = self.processor.process_downloaded_videos(limit=10)
            logger.info(f"Processed {len(results)} videos")
        except Exception as e:
            logger.error(f"Process job error: {e}")

    async def upload_job(self):
        """Job upload video lên TikTok và YouTube."""
        logger.info("=" * 50)
        logger.info("📤 UPLOAD JOB STARTED")
        logger.info("=" * 50)

        try:
            if self.uploader_tt:
                uploaded_tt = await self.uploader_tt.upload_pending_videos(limit=1)
                logger.info(f"Uploaded {len(uploaded_tt)} videos to TikTok")
                
            if self.uploader_yt:
                uploaded_yt = await self.uploader_yt.upload_pending_videos(limit=1)
                logger.info(f"Uploaded {len(uploaded_yt)} videos to YouTube")
                
        except Exception as e:
            logger.error(f"Upload job error: {e}")

    async def full_pipeline_job(self):
        """Job chạy toàn bộ pipeline: crawl → process → upload."""
        logger.info("=" * 60)
        logger.info(f"🚀 PIPELINE STARTED (Mode: {self.source_mode})")
        logger.info(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        if self.source_mode == "full":
            # Step 1: Crawl
            await self.crawl_job()

            # Step 2: Process
            await self.process_job()

        # Step 3: Upload (1 video mỗi lần)
        await self.upload_job()

        # Thống kê
        stats = self.db.get_stats()
        logger.info("\n📊 PIPELINE SUMMARY:")
        logger.info(f"   Total crawled:    {stats['total_crawled']}")
        logger.info(f"   Total processed:  {stats['total_processed']}")
        logger.info(f"   Total posted:     {stats['total_posted']}")
        logger.info(f"   Pending process:  {stats['pending_process']}")
        logger.info(f"   Pending post:     {stats['pending_post']}")
        logger.info(f"   Today posted:     {stats['today_posted']}")
        logger.info("=" * 60)

    def setup_schedules(self):
        """Thiết lập các lịch chạy tự động."""
        config = SCHEDULER_CONFIG

        # Schedule upload theo giờ cố định (VD: 09:00, 12:30, 18:00, 21:30)
        post_times = config.get("post_times", ["09:00", "12:30", "18:00", "21:30"])
        for time_str in post_times:
            hour, minute = time_str.split(":")
            self.scheduler.add_job(
                self.full_pipeline_job,
                CronTrigger(hour=int(hour), minute=int(minute)),
                id=f"pipeline_{time_str}",
                name=f"Full Pipeline at {time_str}",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info(f"  📅 Scheduled pipeline at {time_str}")

        # Schedule crawl định kỳ (mỗi 12 giờ)
        crawl_hours = config.get("crawl_interval_hours", 12)
        self.scheduler.add_job(
            self.crawl_job,
            IntervalTrigger(hours=crawl_hours),
            id="crawl_periodic",
            name=f"Periodic Crawl (every {crawl_hours}h)",
            replace_existing=True,
        )
        logger.info(f"  📅 Scheduled periodic crawl every {crawl_hours}h")

    async def start(self):
        """Khởi động scheduler."""
        logger.info("🚀 Auto Scheduler starting...")
        logger.info(f"   Timezone: {SCHEDULER_CONFIG.get('timezone', 'UTC')}")
        logger.info(f"   Douyin URLs: {len(self.douyin_urls)}")

        self.setup_schedules()
        self.scheduler.start()
        self._running = True

        # In danh sách jobs
        jobs = self.scheduler.get_jobs()
        logger.info(f"\n📋 Scheduled {len(jobs)} jobs:")
        for job in jobs:
            logger.info(f"   - {job.name}: next run at {job.next_run_time}")

        logger.info("\n✅ Scheduler is running. Press Ctrl+C to stop.\n")

        # Chạy pipeline đầu tiên ngay lập tức
        logger.info("Running initial pipeline now...")
        await self.full_pipeline_job()

        # Keep alive
        try:
            while self._running:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            await self.stop()

    async def stop(self):
        """Dừng scheduler."""
        logger.info("\n🛑 Stopping scheduler...")
        self._running = False
        self.scheduler.shutdown(wait=False)
        if self.uploader_tt:
            await self.uploader_tt.close()
        if self.uploader_yt:
            await self.uploader_yt.close()
        logger.info("Scheduler stopped.")

    async def run_once(self):
        """Chạy pipeline một lần (không schedule)."""
        await self.full_pipeline_job()
        if self.uploader_tt:
            await self.uploader_tt.close()
        if self.uploader_yt:
            await self.uploader_yt.close()
