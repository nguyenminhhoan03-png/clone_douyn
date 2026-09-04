import asyncio
from pathlib import Path
from loguru import logger
from database.db_manager import DatabaseManager
from uploader.facebook_uploader import FacebookUploader

async def main():
    db = DatabaseManager()
    
    # 1. Lấy danh sách video pending
    pending = db.get_pending_videos(limit=1000)
    if not pending:
        logger.warning("❌ Không còn video pending nào trong database để upload Facebook Reels!")
        return
        
    # 2. Tìm thư mục cookies/tokens
    cookies_base = Path("config/cookies")
    user_dirs = [d for d in cookies_base.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    target_user_dir = None
    for d in user_dirs:
        if "admin" in d.name:
            target_user_dir = d
            break
    if not target_user_dir:
        target_user_dir = user_dirs[0] if user_dirs else cookies_base
        
    username = target_user_dir.name
    fb_tokens = sorted(list(target_user_dir.glob("facebook_*.json")))
    if not fb_tokens:
        fb_tokens = sorted(list(cookies_base.glob("facebook_*.json")))
        
    if not fb_tokens:
        logger.warning(f"❌ Không tìm thấy file facebook_*.json nào trong {target_user_dir}!")
        return

    logger.info(f"📋 Tìm thấy {len(fb_tokens)} Fanpage Facebook trong '{username}'.")
    logger.info(f"📦 Tổng số video pending: {len(pending)}")
    
    VIDEOS_PER_PAGE = 2
    
    for i, token_path in enumerate(fb_tokens):
        start_idx = i * VIDEOS_PER_PAGE
        end_idx = start_idx + VIDEOS_PER_PAGE
        vids_for_page = pending[start_idx:end_idx]
        
        if not vids_for_page:
            logger.info("🏁 Đã phân bổ hết video pending cho các Page trước.")
            break
            
        uploader = FacebookUploader(db=db, token_file=str(token_path), username=username)
        page_title = uploader.page_name or uploader.page_id or token_path.stem
        
        logger.info(f"\n{'='*50}\n🚀 [{i+1}/{len(fb_tokens)}] ĐANG ĐĂNG REELS CHO PAGE: {page_title} ({len(vids_for_page)} video)\n{'='*50}")
        
        try:
            video_ids = [v["video_id"] for v in vids_for_page]
            await uploader.upload_pending_videos(limit=len(video_ids), video_ids=video_ids)
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng cho Page {page_title}: {e}")
            
    logger.info("\n🎉 Hoàn thành toàn bộ tiến trình đăng Facebook Reels!")

if __name__ == "__main__":
    asyncio.run(main())
