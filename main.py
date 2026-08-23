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
    """Command: Upload video lên TikTok."""
    from uploader.tiktok_uploader import TikTokUploader
    from database.db_manager import DatabaseManager
    from config.settings import COOKIES_DIR
    import json

    db = DatabaseManager()
    
    cookies_file = getattr(args, "account", None)
    proxy_str = None
    if cookies_file:
        cookies_path = Path(cookies_file) if Path(cookies_file).is_absolute() else COOKIES_DIR / cookies_file
    else:
        default_cookie = COOKIES_DIR / "tiktok_cookies.json"
        if default_cookie.exists():
            cookies_path = default_cookie
        else:
            candidates = list(COOKIES_DIR.glob("tiktok_*.json"))
            cookies_path = candidates[0] if candidates else default_cookie

    if cookies_path.exists():
        proxy_file = cookies_path.parent / "proxies.json"
        if proxy_file.exists():
            try:
                with open(proxy_file, "r", encoding="utf-8") as f:
                    proxies = json.load(f)
                    proxy_str = proxies.get(cookies_path.name)
            except Exception:
                pass

    logger.info(f"Target TikTok account cookie: {cookies_path.name}")
    uploader = TikTokUploader(db=db, cookies_file=str(cookies_path), proxy=proxy_str)

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
    scheduler = AutoScheduler(douyin_urls=urls, tt_account_file=account_file)

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
    post_parser = subparsers.add_parser("post", help="Upload video lên TikTok")
    post_parser.add_argument("--limit", type=int, default=4, help="Số video upload tối đa (default: 4)")
    post_parser.add_argument("--account", help="Tên file cookie TikTok (VD: tiktok_1.json hoặc tiktok_2.json)")

    # === AUTO ===
    auto_parser = subparsers.add_parser("auto", help="Tự động crawl → process → post")
    auto_parser.add_argument("--urls", nargs="+", help="Danh sách Douyin URLs")
    auto_parser.add_argument("--file", help="File chứa URLs")
    auto_parser.add_argument("--account", help="Tên file cookie TikTok (VD: tiktok_1.json hoặc tiktok_2.json)")
    auto_parser.add_argument("--once", action="store_true", help="Chỉ chạy 1 lần (không schedule)")

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
