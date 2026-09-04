import asyncio
from pathlib import Path
from loguru import logger
from database.db_manager import DatabaseManager
from uploader.youtube_uploader import YouTubeUploader

async def main():
    db = DatabaseManager()
    
    # 1. Lấy danh sách video pending
    pending = db.get_pending_videos(limit=1000)
    if not pending:
        logger.warning("❌ Không còn video pending nào trong database để upload YouTube Shorts!")
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
    yt_tokens = sorted(list(target_user_dir.glob("youtube_*.json")))
    if not yt_tokens:
        yt_tokens = sorted(list(cookies_base.glob("youtube_*.json")))
        
    if not yt_tokens:
        logger.warning(f"❌ Không tìm thấy file youtube_*.json nào trong {target_user_dir}!")
        return

    logger.info(f"📋 Tìm thấy {len(yt_tokens)} kênh YouTube Shorts trong '{username}'.")
    logger.info(f"📦 Tổng số video pending: {len(pending)}")
    
    VIDEOS_PER_CHANNEL = 2
    
    for i, token_path in enumerate(yt_tokens):
        start_idx = i * VIDEOS_PER_CHANNEL
        end_idx = start_idx + VIDEOS_PER_CHANNEL
        vids_for_ch = pending[start_idx:end_idx]
        
        if not vids_for_ch:
            logger.info("🏁 Đã phân bổ hết video pending cho các kênh trước.")
            break
            
        uploader = YouTubeUploader(db=db, token_file=str(token_path), username=username)
        channel_name = token_path.stem
        
        logger.info(f"\n{'='*50}\n🚀 [{i+1}/{len(yt_tokens)}] ĐANG ĐĂNG SHORTS CHO KÊNH: {channel_name} ({len(vids_for_ch)} video)\n{'='*50}")
        
        try:
            video_ids = [v["video_id"] for v in vids_for_ch]
            await uploader.upload_pending_videos(limit=len(video_ids), video_ids=video_ids)
        except Exception as e:
            logger.error(f"❌ Lỗi khi đăng cho kênh {channel_name}: {e}")
            
    logger.info("\n🎉 Hoàn thành toàn bộ tiến trình đăng YouTube Shorts!")

if __name__ == "__main__":
    asyncio.run(main())
