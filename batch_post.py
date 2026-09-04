import argparse
import asyncio
import json
import os
from pathlib import Path
from loguru import logger
from database.db_manager import DatabaseManager

async def post_tiktok(db, target_user_dir, cookies_base, pending, vids_per_acc=2):
    from uploader.tiktok_uploader import TikTokUploader
    username = target_user_dir.name
    all_cookies = sorted(list(target_user_dir.glob("tiktok_*.json")))
    cookies = [c for c in all_cookies if c.stat().st_size > 10]
    
    if not cookies:
        logger.warning(f"❌ Không tìm thấy file cookie tiktok_*.json hợp lệ trong {target_user_dir}!")
        return

    proxies = {}
    for p_file in [target_user_dir / "proxies.json", cookies_base / "proxies.json"]:
        if p_file.exists():
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    proxies.update(json.load(f))
            except Exception:
                pass

    # Chỉ chạy các nick TikTok có trong cấu hình proxies.json (tránh chạy nick rác/đã xóa)
    if proxies:
        valid_set = set(proxies.keys())
        cookies = [c for c in cookies if c.name in valid_set or c.stem in valid_set]

    logger.info(f"\n{'='*55}\n🎵 [TIKTOK] Bắt đầu đăng bài cho {len(cookies)} tài khoản...\n{'='*55}")
    for i, cookie_path in enumerate(cookies):
        start_idx = i * vids_per_acc
        end_idx = start_idx + vids_per_acc
        vids_for_acc = pending[start_idx:end_idx]
        
        if not vids_for_acc:
            logger.info("🏁 Đã phân bổ hết video pending cho các nick TikTok trước.")
            break
            
        acc_name = cookie_path.stem
        proxy_str = proxies.get(cookie_path.name) or proxies.get(cookie_path.stem)
        logger.info(f"\n🚀 [TikTok {i+1}/{len(cookies)}] Đăng bài cho: {acc_name} ({len(vids_for_acc)} video) | Proxy: {proxy_str or 'None'}")
        
        uploader = TikTokUploader(
            db=db,
            cookies_file=str(cookie_path),
            proxy=proxy_str,
            username=username,
            window_idx=i
        )
        try:
            video_ids = [v["video_id"] for v in vids_for_acc]
            await uploader.upload_pending_videos(video_ids=video_ids)
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng TikTok {acc_name}: {e}")
        finally:
            await uploader.close()

async def post_facebook(db, target_user_dir, cookies_base, pending, vids_per_page=2):
    from uploader.facebook_uploader import FacebookUploader
    username = target_user_dir.name
    fb_tokens = sorted(list(target_user_dir.glob("facebook_*.json")))
    if not fb_tokens:
        fb_tokens = sorted(list(cookies_base.glob("facebook_*.json")))
        
    if not fb_tokens:
        logger.warning(f"❌ Không tìm thấy file facebook_*.json nào!")
        return

    logger.info(f"\n{'='*55}\n📘 [FACEBOOK REELS] Bắt đầu đăng bài cho {len(fb_tokens)} Fanpage...\n{'='*55}")
    for i, token_path in enumerate(fb_tokens):
        try:
            uploader = FacebookUploader(db=db, token_file=str(token_path), username=username)
            page_title = uploader.page_name or uploader.page_id or token_path.stem
            logger.info(f"\n🚀 [Facebook {i+1}/{len(fb_tokens)}] Đang đăng Reels cho Page: {page_title} (Tối đa {vids_per_page} video)")
            await uploader.upload_pending_videos(limit=vids_per_page)
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng Reels cho token {token_path.name}: {e}")

async def post_youtube(db, target_user_dir, cookies_base, pending, vids_per_ch=2):
    try:
        from uploader.youtube_uploader import YouTubeUploader
    except Exception as e:
        logger.error(f"❌ Không thể nạp module YouTubeUploader: {e}")
        return

    username = target_user_dir.name
    yt_tokens = sorted(list(target_user_dir.glob("youtube_*.json")))
    if not yt_tokens:
        yt_tokens = sorted(list(cookies_base.glob("youtube_*.json")))
        
    if not yt_tokens:
        logger.warning(f"❌ Không tìm thấy file youtube_*.json nào!")
        return

    logger.info(f"\n{'='*55}\n▶️ [YOUTUBE SHORTS] Bắt đầu đăng bài cho {len(yt_tokens)} kênh Shorts...\n{'='*55}")
    for i, token_path in enumerate(yt_tokens):
        try:
            uploader = YouTubeUploader(db=db, token_file=str(token_path), username=username)
            ch_name = token_path.stem
            logger.info(f"\n🚀 [YouTube {i+1}/{len(yt_tokens)}] Đang đăng Shorts cho kênh: {ch_name} (Tối đa {vids_per_ch} video)")
            await uploader.upload_pending_videos(limit=vids_per_ch)
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng Shorts cho token {token_path.name}: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Multi-platform Batch Post: TikTok, Facebook Reels, YouTube Shorts")
    parser.add_argument("--platform", type=str, default="tiktok", choices=["tiktok", "facebook", "fb", "youtube", "yt", "all"], help="Nền tảng đăng bài")
    parser.add_argument("--vids-per-acc", type=int, default=2, help="Số video mỗi nick/page/kênh (mặc định: 2)")
    args = parser.parse_args()

    db = DatabaseManager()
    pending = db.get_pending_videos(limit=1000)
    if not pending:
        logger.warning("❌ Không còn video pending nào trong database để upload!")
        return

    cookies_base = Path("config/cookies")
    user_dirs = [d for d in cookies_base.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    target_user_dir = None
    for d in user_dirs:
        if "admin" in d.name:
            target_user_dir = d
            break
    if not target_user_dir:
        target_user_dir = user_dirs[0] if user_dirs else cookies_base

    logger.info(f"📦 Tổng số video pending: {len(pending)}")
    logger.info(f"🎯 Nền tảng chỉ định: {args.platform.upper()} (Mỗi tài khoản: {args.vids_per_acc} video)")

    p = args.platform.lower()
    if p in ["tiktok", "all"]:
        try:
            tt_pending = db.get_pending_videos(limit=1000, platform="tiktok")
            if tt_pending:
                logger.info(f"📦 Số video pending cho TikTok: {len(tt_pending)}")
                await post_tiktok(db, target_user_dir, cookies_base, tt_pending, args.vids_per_acc)
            else:
                logger.info("ℹ️ Không có video pending nào cho TikTok.")
        except Exception as e:
            logger.error(f"❌ Lỗi tiến trình TikTok (tự động bỏ qua chạy tiếp): {e}")

    if p in ["facebook", "fb", "all"]:
        try:
            fb_pending = db.get_pending_videos(limit=1000, platform="facebook")
            if fb_pending:
                logger.info(f"📦 Số video pending cho Facebook Reels: {len(fb_pending)}")
                await post_facebook(db, target_user_dir, cookies_base, fb_pending, args.vids_per_acc)
            else:
                logger.info("ℹ️ Không có video pending nào cho Facebook Reels.")
        except Exception as e:
            logger.error(f"❌ Lỗi tiến trình Facebook Reels (tự động bỏ qua chạy tiếp): {e}")

    if p in ["youtube", "yt", "all"]:
        try:
            yt_pending = db.get_pending_videos(limit=1000, platform="youtube")
            if yt_pending:
                logger.info(f"📦 Số video pending cho YouTube Shorts: {len(yt_pending)}")
                await post_youtube(db, target_user_dir, cookies_base, yt_pending, args.vids_per_acc)
            else:
                logger.info("ℹ️ Không có video pending nào cho YouTube Shorts.")
        except Exception as e:
            logger.error(f"❌ Lỗi tiến trình YouTube Shorts (tự động bỏ qua): {e}")

    logger.info("\n🎉 Hoàn thành toàn bộ tiến trình đăng bài!")

if __name__ == "__main__":
    asyncio.run(main())
