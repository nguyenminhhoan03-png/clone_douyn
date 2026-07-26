"""
YouTube Uploader - Tự động upload video lên YouTube qua Google API
Sử dụng YouTube Data API v3 với OAuth2 authentication.
Hỗ trợ multi-account (nhiều file token).
"""
import asyncio
import json
import random
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import YOUTUBE_CONFIG, COOKIES_DIR
from database.db_manager import DatabaseManager


# YouTube video categories (phổ biến)
YOUTUBE_CATEGORIES = {
    "Film & Animation": "1",
    "Autos & Vehicles": "2",
    "Music": "10",
    "Pets & Animals": "15",
    "Sports": "17",
    "Gaming": "20",
    "People & Blogs": "22",
    "Comedy": "23",
    "Entertainment": "24",
    "News & Politics": "25",
    "Howto & Style": "26",
    "Education": "27",
    "Science & Technology": "28",
}


class YouTubeUploader:
    """Tự động upload video lên YouTube qua Google Data API v3."""

    def __init__(self, db: DatabaseManager = None, token_file: str = None):
        self.db = db or DatabaseManager()
        self.config = YOUTUBE_CONFIG
        self.token_file = token_file or str(COOKIES_DIR / "youtube_1.json")
        self._youtube_service = None

    # ─── OAuth2 Authentication ───────────────────────────────────────────────

    def _get_credentials(self):
        """Load credentials từ token file, tự refresh nếu hết hạn."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
        except ImportError:
            logger.error(
                "Thiếu thư viện Google API! Chạy:\n"
                "  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
            )
            raise

        token_path = Path(self.token_file)
        if not token_path.exists():
            logger.error(f"Token file not found: {token_path}. Hãy đăng nhập tài khoản YouTube trước.")
            return None

        try:
            creds = Credentials.from_authorized_user_file(
                str(token_path),
                scopes=["https://www.googleapis.com/auth/youtube.upload"]
            )

            # Auto refresh nếu token hết hạn
            if creds and creds.expired and creds.refresh_token:
                logger.info("YouTube token expired, refreshing...")
                creds.refresh(Request())
                # Ghi lại token mới
                with open(str(token_path), "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                logger.info("YouTube token refreshed ✓")

            return creds
        except Exception as e:
            logger.error(f"Failed to load YouTube credentials: {e}")
            return None

    def _get_service(self):
        """Tạo YouTube API service."""
        if self._youtube_service:
            return self._youtube_service

        try:
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("Thiếu google-api-python-client! pip install google-api-python-client")
            raise

        creds = self._get_credentials()
        if not creds:
            return None

        self._youtube_service = build("youtube", "v3", credentials=creds)
        logger.info("YouTube API service initialized ✓")
        return self._youtube_service

    @staticmethod
    def authorize_new_account(client_secret_path: str, token_save_path: str) -> bool:
        """
        Mở browser để user đăng nhập Google, lưu token.
        
        Args:
            client_secret_path: Đường dẫn file client_secret.json từ Google Cloud Console
            token_save_path: Đường dẫn lưu file token (vd: youtube_1.json)
            
        Returns:
            True nếu thành công
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            logger.error("Thiếu google-auth-oauthlib! pip install google-auth-oauthlib")
            return False

        if not Path(client_secret_path).exists():
            logger.error(f"client_secret.json not found: {client_secret_path}")
            return False

        try:
            SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            
            # Mở browser để đăng nhập
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message="Đang mở trình duyệt để đăng nhập YouTube..."
            )

            # Lưu token
            token_path = Path(token_save_path)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(token_path), "w", encoding="utf-8") as f:
                f.write(creds.to_json())

            logger.info(f"YouTube account authorized & saved to: {token_path.name} ✓")
            return True
        except Exception as e:
            logger.error(f"YouTube authorization failed: {e}")
            return False

    # ─── Upload ──────────────────────────────────────────────────────────────

    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list = None,
        category: str = "22",
        privacy: str = "public",
    ) -> bool:
        """
        Upload một video lên YouTube.

        Args:
            video_path: Đường dẫn file video
            title: Tiêu đề video (tối đa 100 ký tự)
            description: Mô tả video
            tags: List tags
            category: ID category (22 = People & Blogs)
            privacy: public, unlisted, private

        Returns:
            True nếu upload thành công
        """
        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False

        service = self._get_service()
        if not service:
            logger.error("YouTube service not available. Hãy đăng nhập trước!")
            return False

        logger.info(f"Uploading to YouTube: {video_path.name}")
        logger.info(f"  Title: {title[:60]}...")

        try:
            from googleapiclient.http import MediaFileUpload

            # Cắt title nếu quá dài (YouTube giới hạn 100 ký tự)
            title = title[:100]
            
            # Build request body
            body = {
                "snippet": {
                    "title": title,
                    "description": description[:5000],  # YouTube limit 5000
                    "tags": (tags or [])[:500],
                    "categoryId": category,
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }

            # Resumable upload (Senior best practice cho file lớn)
            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=10 * 1024 * 1024,  # 10MB chunks
            )

            # Chạy upload trên thread pool vì Google API là sync
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._execute_upload(service, body, media)
            )

            if result:
                yt_video_id = result.get("id", "unknown")
                logger.info(f"  ✅ YouTube upload successful! Video ID: {yt_video_id}")
                logger.info(f"  🔗 https://www.youtube.com/watch?v={yt_video_id}")
                return True
            else:
                logger.error("  ✗ YouTube upload returned no result")
                return False

        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _execute_upload(self, service, body, media):
        """Thực thi resumable upload (sync, chạy trên thread pool)."""
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        retry_count = 0
        max_retries = 3

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"  📤 Upload progress: {progress}%")
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"  ✗ Upload failed after {max_retries} retries: {e}")
                    raise
                logger.warning(f"  ⚠️ Upload error, retrying ({retry_count}/{max_retries})...")
                time.sleep(5 * retry_count)

        return response

    # ─── Batch Upload ────────────────────────────────────────────────────────

    def _generate_yt_metadata(self, video_info: dict) -> dict:
        """Tạo title, description, tags cho YouTube từ video info."""
        from utils.translator import translate_description, generate_youtube_metadata_with_gemini
        import re
        from config.settings import PROCESSOR_CONFIG

        original = video_info.get("title", "")
        
        gemini_keys = PROCESSOR_CONFIG.get("gemini_api_keys", [])
        if not gemini_keys and PROCESSOR_CONFIG.get("gemini_api_key"):
            gemini_keys = [PROCESSOR_CONFIG.get("gemini_api_key")]
            
        if original and gemini_keys:
            meta = generate_youtube_metadata_with_gemini(original, gemini_keys)
            if meta:
                # Gắn thêm hashtags mặc định
                default_tags = self.config.get("default_tags", ["shorts", "viral", "trending"])
                meta["tags"] = list(set(meta["tags"] + default_tags))
                
                # Format description
                desc_template = self.config.get(
                    "default_description_template",
                    "{title}\n\n{description}\n\n{hashtags}"
                )
                
                # Cắt title nếu quá 100
                title = meta["title"][:100]
                desc = meta["description"]
                hashtags_str = " ".join([f"#{t.replace('#','')}" for t in meta["tags"]])
                
                description = desc_template.replace("{title}", title).replace("{description}", desc).replace("{hashtags}", hashtags_str)
                
                logger.info(f"  📝 [Gemini SEO] YT Title: {title[:60]}...")
                return {"title": title, "description": description, "tags": meta["tags"]}

        # Fallback to old behavior
        title_vi = video_info.get("title_vi", "")
        if not title_vi:
            title_vi = translate_description(original) if original else ""

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

        title = f"✨ {title_vi}"[:100]

        # Description
        desc_template = self.config.get(
            "default_description_template",
            "{title}\n\n#shorts #viral #trending"
        )
        description = desc_template.replace("{title}", title_vi)

        # Tags
        default_tags = self.config.get("default_tags", ["shorts", "viral", "trending"])
        tags = list(default_tags)

        logger.info(f"  📝 YT Title: {title[:60]}...")
        return {"title": title, "description": description, "tags": tags}

    async def upload_pending_videos(
        self,
        limit: int = None,
        video_ids: list = None,
        custom_captions: dict = None,
    ) -> list:
        """
        Upload tất cả video pending lên YouTube.
        Trả về list các video_id đã upload thành công.
        """
        if video_ids is not None:
            all_pending = self.db.get_pending_videos(limit=1000)
            videos = [v for v in all_pending if v["video_id"] in video_ids]
        else:
            max_posts = limit or self.config.get("max_posts_per_day", 5)
            today_count = self.db.get_today_post_count(platform="youtube")
            remaining = max_posts - today_count

            if remaining <= 0:
                logger.info(f"Đã đạt giới hạn YouTube {max_posts} video/ngày. Dừng upload.")
                return []

            videos = self.db.get_pending_videos(limit=remaining)

        if not videos:
            logger.info("Không có video nào pending để upload YouTube")
            return []

        logger.info(f"Found {len(videos)} videos to upload to YouTube")

        # Check service
        service = self._get_service()
        if not service:
            logger.error("Cannot upload: YouTube not authenticated")
            return []

        uploaded_ids = []
        privacy = self.config.get("default_privacy", "public")
        category = self.config.get("default_category", "22")

        for i, video in enumerate(videos):
            logger.info(f"\n[{i + 1}/{len(videos)}] Uploading to YouTube: {video['video_id']}")

            # Tạo metadata
            custom_caption = custom_captions.get(video["video_id"]) if custom_captions else None

            if custom_caption:
                title = custom_caption[:100]
                description = custom_caption
                tags = self.config.get("default_tags", [])
            else:
                meta = self._generate_yt_metadata(video)
                title = meta["title"]
                description = meta["description"]
                tags = meta["tags"]

            # Upload
            success = await self.upload_video(
                video_path=video["processed_path"],
                title=title,
                description=description,
                tags=tags,
                category=category,
                privacy=privacy,
            )

            if success:
                self.db.add_posted_video(
                    crawled_video_id=video["id"],
                    caption=title,
                    hashtags=" ".join(tags),
                    platform="youtube",
                )
                uploaded_ids.append(video["video_id"])

                # Auto cleanup
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
                        logger.info(f"  🧹 Đã xóa {cleaned_files} file cục bộ.")

            # Delay giữa các lần upload
            if i < len(videos) - 1:
                wait_seconds = random.randint(15, 30)
                logger.info(f"  ⏳ Waiting {wait_seconds}s before next YouTube upload...")
                await asyncio.sleep(wait_seconds)

        logger.info(f"\n📊 YouTube upload summary: {len(uploaded_ids)}/{len(videos)} successful")
        return uploaded_ids

    async def close(self):
        """Cleanup resources."""
        self._youtube_service = None
        logger.debug("YouTube uploader closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
