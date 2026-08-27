"""
Main Entry Point - CLI tool crawl Douyin & auto-post TikTok
Usage:
    python main.py crawl --urls URL1 URL2 ...
    python main.py crawl --profile PROFILE_URL --count 10
    python main.py process
    python main.py post
    python main.py auto --urls URL1 URL2 ...
    python main.py status
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Thêm project root vào path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from config.settings import LOG_CONFIG, MUSIC_DIR


def setup_logging():
    """Cấu hình logging với loguru."""
    # Remove default handler
    logger.remove()

    # Console handler (có màu)
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
            "<level>{message}</level>"
        ),
        level="INFO",
        colorize=True,
    )

    # File handler
    logger.add(
        str(LOG_CONFIG["log_file"]),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation=LOG_CONFIG.get("rotation", "10 MB"),
        retention=LOG_CONFIG.get("retention", "7 days"),
        level=LOG_CONFIG.get("level", "DEBUG"),
        encoding="utf-8",
    )


def cmd_crawl(args):
    """Command: Crawl video từ Douyin."""
    from crawler.douyin_crawler import DouyinCrawler
    from database.db_manager import DatabaseManager

    db = DatabaseManager()
    crawler = DouyinCrawler(db=db)

    if args.profile:
        logger.info(f"Crawling profile: {args.profile}")
        results = asyncio.run(
            crawler.crawl_user_profile(args.profile, max_videos=args.count)
        )
    elif args.urls:
        logger.info(f"Crawling {len(args.urls)} video URLs")
        results = asyncio.run(
            crawler.crawl_multiple_videos(args.urls)
        )
    elif args.file:
        # Đọc URLs từ file
        urls = Path(args.file).read_text(encoding="utf-8").strip().splitlines()
        urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
        logger.info(f"Crawling {len(urls)} URLs from file: {args.file}")
        results = asyncio.run(
            crawler.crawl_multiple_videos(urls)
        )
    else:
        logger.error("Cần cung cấp --urls, --profile, hoặc --file")
        return

    logger.info(f"\n✅ Crawled {len(results)} videos successfully!")
    for r in results:
        logger.info(f"   {r['video_id']} - {r.get('title', 'N/A')[:50]}")


def cmd_process(args):
    """Command: Xử lý video đã download."""
    from processor.video_processor import VideoProcessor
    from database.db_manager import DatabaseManager

    db = DatabaseManager()
    processor = VideoProcessor(db=db)

    # Custom title nếu có
    titles = {}
    if args.title:
        # Nếu có title, apply cho tất cả video
        videos = db.get_downloaded_videos(limit=args.limit)
        for v in videos:
            titles[v["video_id"]] = args.title

    results = processor.process_downloaded_videos(titles=titles, limit=args.limit)

    logger.info(f"\n✅ Processed {len(results)} videos!")
    _check_music_folder()


def cmd_post(args):
    """Command: Upload video lên TikTok, YouTube hoặc Facebook Reels."""
    from database.db_manager import DatabaseManager
    from config.settings import COOKIES_DIR
    import json

    db = DatabaseManager()
    platform = getattr(args, "platform", "tiktok") or "tiktok"

    if platform == "facebook":
        from uploader.facebook_uploader import FacebookUploader
        fb_token = getattr(args, "fb_account", None) or getattr(args, "account", None)
        token_path = None
        if fb_token:
            p = Path(fb_token)
            token_path = p if p.is_absolute() and p.exists() else COOKIES_DIR / fb_token
        if not token_path or not token_path.exists():
            candidates = list(COOKIES_DIR.glob("facebook_*.json"))
            token_path = candidates[0] if candidates else None

        uploader = FacebookUploader(db=db, token_file=str(token_path) if token_path else None)
        logger.info(f"Uploading to Facebook Reels via token: {token_path.name if token_path else 'None'}")
        asyncio.run(uploader.upload_pending_videos(limit=args.limit))
        return

    if platform == "youtube":
        from uploader.youtube_uploader import YouTubeUploader
        yt_token = getattr(args, "yt_account", None) or getattr(args, "account", None)
        token_path = None
        if yt_token:
            p = Path(yt_token)
            token_path = p if p.is_absolute() and p.exists() else COOKIES_DIR / yt_token
        if not token_path or not token_path.exists():
            candidates = list(COOKIES_DIR.glob("youtube_*.json"))
            token_path = candidates[0] if candidates else None

        uploader = YouTubeUploader(db=db, token_file=str(token_path) if token_path else None)
        logger.info(f"Uploading to YouTube Shorts via token: {token_path.name if token_path else 'None'}")
        asyncio.run(uploader.upload_pending_videos(limit=args.limit))
        return

    from uploader.tiktok_uploader import TikTokUploader
    
    cookies_file = getattr(args, "account", None)
    proxy_str = None
    cookies_path = None

    if cookies_file:
        p = Path(cookies_file)
        if p.is_absolute() and p.exists():
            cookies_path = p
        else:
            candidates = [
                COOKIES_DIR / cookies_file,
                COOKIES_DIR / f"tiktok_{cookies_file}.json",
                COOKIES_DIR / f"{cookies_file}.json",
            ]
            for cand in candidates:
                if cand.exists():
                    cookies_path = cand
                    break
            if not cookies_path:
                # Search subdirectories
                for sub_p in COOKIES_DIR.rglob(f"*{cookies_file}*.json"):
                    if sub_p.is_file():
                        cookies_path = sub_p
                        break
    
    if not cookies_path:
        default_cookie = COOKIES_DIR / "tiktok_cookies.json"
        if default_cookie.exists():
            cookies_path = default_cookie
        else:
            candidates = list(COOKIES_DIR.glob("tiktok_*.json"))
            cookies_path = candidates[0] if candidates else default_cookie

    if cookies_path and cookies_path.exists() and not getattr(args, "no_proxy", False):
        # Tìm proxy trong thư mục của cookie hoặc thư mục gốc cookies
        for proxy_candidate in [cookies_path.parent / "proxies.json", COOKIES_DIR / "proxies.json"]:
            if proxy_candidate.exists():
                try:
                    with open(proxy_candidate, "r", encoding="utf-8") as f:
                        proxies = json.load(f)
                        proxy_str = proxies.get(cookies_path.name) or proxies.get(cookies_path.stem)
                        if proxy_str:
                            break
                except Exception:
                    pass

    if getattr(args, "no_proxy", False):
        proxy_str = None
        logger.info("🚫 Đang chạy chế độ KHÔNG DÙNG PROXY (--no-proxy)")

    logger.info(f"Target TikTok account cookie: {cookies_path.name if cookies_path else 'None'}")
    uploader = TikTokUploader(db=db, cookies_file=str(cookies_path) if cookies_path else None, proxy=proxy_str)

    async def _post():
        try:
            uploaded = await uploader.upload_pending_videos(limit=args.limit)
            logger.info(f"\n✅ Uploaded {len(uploaded) if isinstance(uploaded, list) else uploaded} videos!")
        finally:
            await uploader.close()

    asyncio.run(_post())


def cmd_auto(args):
    """Command: Chạy tự động (crawl → process → post)."""
    from scheduler.scheduler import AutoScheduler

    urls = args.urls or []

    # Đọc URLs từ file nếu có
    if args.file:
        file_urls = Path(args.file).read_text(encoding="utf-8").strip().splitlines()
        urls.extend([u.strip() for u in file_urls if u.strip() and not u.startswith("#")])

    if not urls:
        logger.warning(
            "Không có Douyin URLs! Sử dụng:\n"
            "  python main.py auto --urls URL1 URL2\n"
            "  python main.py auto --file urls.txt"
        )
        return

    _check_music_folder()

    account_file = getattr(args, "account", None)
    yt_account_file = getattr(args, "yt_account", None)
    fb_account_file = getattr(args, "fb_account", None)
    scheduler = AutoScheduler(
        douyin_urls=urls,
        tt_account_file=account_file,
        yt_account_file=yt_account_file,
        fb_account_file=fb_account_file
    )

    if args.once:
        logger.info("Running pipeline once...")
        asyncio.run(scheduler.run_once())
    else:
        logger.info("Starting auto scheduler (Ctrl+C to stop)...")
        asyncio.run(scheduler.start())


def cmd_status(args):
    """Command: Xem trạng thái hệ thống."""
    from database.db_manager import DatabaseManager

    db = DatabaseManager()
    stats = db.get_stats()

    print("\n" + "=" * 50)
    print("  📊 SYSTEM STATUS")
    print("=" * 50)
    print(f"  Total crawled:     {stats['total_crawled']}")
    print(f"  Total processed:   {stats['total_processed']}")
    print(f"  Total posted:      {stats['total_posted']}")
    print(f"  Pending process:   {stats['pending_process']}")
    print(f"  Pending post:      {stats['pending_post']}")
    print(f"  Today posted:      {stats['today_posted']}")
    print("=" * 50)

    # Hiện danh sách video gần đây
    if args.verbose:
        videos = db.get_all_videos(limit=10)
        if videos:
            print(f"\n  📋 Recent videos (last 10):")
            for v in videos:
                status_icon = {
                    "pending": "⏳",
                    "downloaded": "⬇️",
                    "processed": "✅",
                    "failed": "❌",
                }.get(v["status"], "❓")
                print(f"    {status_icon} [{v['status']}] {v['video_id']} - {v.get('title', 'N/A')[:40]}")
        print()

    # Kiểm tra music folder
    _check_music_folder()


def _check_music_folder():
    """Kiểm tra và nhắc nhở về thư mục nhạc."""
    music_files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.m4a"))
    if not music_files:
        logger.warning(
            f"\n⚠️  Chưa có nhạc Việt trong thư mục: {MUSIC_DIR}\n"
            f"   Hãy bỏ file nhạc trending (.mp3/.m4a) vào đây để ghép vào video!\n"
            f"   Gợi ý: Tải nhạc trending từ TikTok VN (Zing MP3, NhacCuaTui...)"
        )
    else:
        logger.info(f"🎵 Found {len(music_files)} music files in: {MUSIC_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="🎬 Tool Crawl Douyin & Auto-Post TikTok",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  # Crawl video từ URL cụ thể
  python main.py crawl --urls https://v.douyin.com/xxx https://v.douyin.com/yyy

  # Crawl 10 video từ profile user Douyin
  python main.py crawl --profile https://www.douyin.com/user/xxx --count 10

  # Crawl từ file danh sách URLs
  python main.py crawl --file urls.txt

  # Xử lý video đã download (mirror + text + nhạc)
  python main.py process
  python main.py process --title "Nhảy đẹp quá 😍"

  # Upload video đã xử lý lên TikTok
  python main.py post

  # Chạy tự động toàn bộ pipeline
  python main.py auto --urls URL1 URL2 --once       # Chạy 1 lần
  python main.py auto --file urls.txt                # Chạy theo lịch

  # Xem trạng thái
  python main.py status -v
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Chọn command")

    # === CRAWL ===
    crawl_parser = subparsers.add_parser("crawl", help="Crawl video từ Douyin")
    crawl_parser.add_argument("--urls", nargs="+", help="Danh sách Douyin video URLs")
    crawl_parser.add_argument("--profile", help="URL profile Douyin user")
    crawl_parser.add_argument("--file", help="File chứa danh sách URLs (mỗi dòng 1 URL)")
    crawl_parser.add_argument("--count", type=int, default=10, help="Số video crawl từ profile (default: 10)")

    # === PROCESS ===
    process_parser = subparsers.add_parser("process", help="Xử lý video (mirror, text, nhạc)")
    process_parser.add_argument("--title", help="Title tiếng Việt overlay lên tất cả video")
    process_parser.add_argument("--limit", type=int, default=10, help="Số video xử lý tối đa (default: 10)")

    # === POST ===
    post_parser = subparsers.add_parser("post", help="Upload video lên TikTok/YouTube/Facebook")
    post_parser.add_argument("--platform", choices=["tiktok", "youtube", "facebook"], default="tiktok", help="Nền tảng upload (default: tiktok)")
    post_parser.add_argument("--limit", type=int, default=4, help="Số video upload tối đa (default: 4)")
    post_parser.add_argument("--account", help="Tên file cookie TikTok/Token (VD: tiktok_1.json)")
    post_parser.add_argument("--yt-account", help="Tên file token YouTube (VD: youtube_1.json)")
    post_parser.add_argument("--fb-account", help="Tên file token Facebook (VD: facebook_1.json)")
    post_parser.add_argument("--no-proxy", action="store_true", help="Bỏ qua sử dụng Proxy dù có trong file proxies.json")

    # === AUTO ===
    auto_parser = subparsers.add_parser("auto", help="Tự động crawl → process → post")
    auto_parser.add_argument("--urls", nargs="+", help="Danh sách Douyin URLs")
    auto_parser.add_argument("--file", help="File chứa URLs")
    auto_parser.add_argument("--account", help="Tên file cookie TikTok (VD: tiktok_1.json hoặc tiktok_2.json)")
    auto_parser.add_argument("--yt-account", help="Tên file token YouTube (VD: youtube_1.json)")
    auto_parser.add_argument("--fb-account", help="Tên file token Facebook (VD: facebook_1.json)")
    auto_parser.add_argument("--once", action="store_true", help="Chỉ chạy 1 lần (không schedule)")
    auto_parser.add_argument("--no-proxy", action="store_true", help="Bỏ qua sử dụng Proxy dù có trong file proxies.json")

    # === STATUS ===
    status_parser = subparsers.add_parser("status", help="Xem trạng thái hệ thống")
    status_parser.add_argument("-v", "--verbose", action="store_true", help="Hiện chi tiết")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Setup logging
    setup_logging()

    # Banner
    print("""
    ╔══════════════════════════════════════════╗
    ║  🎬 Douyin Crawler & TikTok Uploader     ║
    ║  Auto crawl → process → post pipeline    ║
    ╚══════════════════════════════════════════╝
    """)

    # Dispatch commands
    commands = {
        "crawl": cmd_crawl,
        "process": cmd_process,
        "post": cmd_post,
        "auto": cmd_auto,
        "status": cmd_status,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
