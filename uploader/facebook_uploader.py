"""
Facebook Reels Uploader - Tự động upload video lên Facebook Reels qua Graph API
Sử dụng Facebook Graph API v19.0 với Page Access Token.
Hỗ trợ multi-account (nhiều file cấu hình Fanpage).
"""
import asyncio
import json
import os
import random
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from loguru import logger

from config.settings import FACEBOOK_CONFIG, COOKIES_DIR
from database.db_manager import DatabaseManager


class FacebookUploader:
    """Tự động upload video lên Facebook Reels qua Facebook Graph API."""

    def __init__(self, db: DatabaseManager = None, token_file: str = None, username: str = None):
        self.db = db or DatabaseManager()
        self.current_username = username
        self.config = FACEBOOK_CONFIG
        self.token_file = token_file or str(COOKIES_DIR / "facebook_1.json")
        self.api_version = self.config.get("graph_api_version", "v19.0")
        
        self.page_id = ""
        self.access_token = ""
        self.page_name = ""
        self._load_credentials()

    # ─── Credentials Management ──────────────────────────────────────────────

    def _load_credentials(self):
        """Load Page ID & Page Access Token từ file JSON."""
        token_path = Path(self.token_file)
        if not token_path.exists():
            logger.warning(f"Facebook token file not found: {token_path}")
            return

        try:
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.page_id = str(data.get("page_id", "")).strip()
                self.access_token = str(data.get("page_access_token", "")).strip()
                self.page_name = data.get("page_name", "")
                
            if self.page_id and self.access_token:
                logger.info(f"Loaded Facebook Page: {self.page_name or self.page_id} ✓")
        except Exception as e:
            logger.error(f"Failed to load Facebook token file {token_path}: {e}")

    @staticmethod
    def extract_from_cookie_or_token(input_str: str, page_id: str = "", api_version: str = "v19.0") -> Dict[str, Any]:
        """
        Hỗ trợ nhận vào Access Token HOẶC Cookie Facebook.
        Tự động lấy Token EAAG và danh sách Fanpage.
        """
        input_str = str(input_str).strip()
        page_id = str(page_id).strip()
        
        if not input_str:
            return {"valid": False, "page_name": "", "error": "Vui lòng dán Access Token hoặc Cookie Facebook!"}
            
        # Nếu là Cookie Facebook
        if "c_user=" in input_str or "datr=" in input_str or "xs=" in input_str or "sb=" in input_str:
            logger.info("🍪 Phát hiện định dạng Facebook Cookie! Đang tự động trích xuất Token EAAG...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Cookie": input_str,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
            }
            urls = [
                "https://business.facebook.com/content_management",
                "https://business.facebook.com/latest/home",
                "https://business.facebook.com/creatorstudio/home",
                "https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            ]
            import re
            extracted_token = None
            for u in urls:
                try:
                    r = requests.get(u, headers=headers, timeout=10)
                    matches = re.findall(r'"(EAAG[A-Za-z0-9]+)"', r.text) or re.findall(r'accessToken":"(EAA[A-Za-z0-9]+)"', r.text) or re.findall(r'"(EAA[A-Za-z0-9]{80,})"', r.text)
                    for m in matches:
                        if len(m) > 60:
                            extracted_token = m
                            logger.info(f"✅ Đã tìm thấy Token EAAG: {m[:15]}... từ {u}")
                            break
                    if extracted_token:
                        break
                except Exception as e:
                    logger.debug(f"Lỗi khi crawl {u}: {e}")
                    
            if extracted_token:
                res = FacebookUploader.verify_page_token(page_id, extracted_token, api_version)
                if res.get("valid"):
                    return res
                # Nếu vẫn chưa verify được thì fallback dùng token này
                return {
                    "valid": True,
                    "page_name": res.get("page_name") or f"Fanpage {page_id or 'Auto'}",
                    "page_id": res.get("page_id") or page_id or "me",
                    "page_access_token": extracted_token,
                    "error": ""
                }
            else:
                logger.warning("Không tự extract được EAAG từ Cookie, chuyển sang xác thực trực tiếp...")

        # Xác thực Token trực tiếp
        return FacebookUploader.verify_page_token(page_id, input_str, api_version)

    @staticmethod
    def verify_page_token(page_id: str, access_token: str, api_version: str = "v19.0") -> Dict[str, Any]:
        """
        Kiểm tra tính hợp lệ của Page Access Token hoặc User Token với Full Debug Logs.
        """
        page_id = str(page_id).strip() if page_id else ""
        access_token = str(access_token).strip() if access_token else ""
        
        logger.info(f"=== BẮT ĐẦU XÁC THỰC FACEBOOK TOKEN ===")
        logger.info(f"Input Page ID: '{page_id}'")
        logger.info(f"Input Token (Độ dài: {len(access_token)}, 15 ký tự đầu: '{access_token[:15]}...')")
        
        if not access_token:
            logger.error("❌ Access Token bị trống!")
            return {"valid": False, "page_name": "", "error": "Access Token không được để trống!"}
            
        if not access_token.startswith("EAA"):
            warn_msg = f"Cảnh báo: Access Token Facebook luôn bắt đầu bằng 'EAA...'. Bạn đang dán chuỗi bắt đầu bằng '{access_token[:10]}...'. Có thể bạn chưa copy đủ toàn bộ mã!"
            logger.warning(f"⚠️ {warn_msg}")

        # 1. Thử xác thực trực tiếp theo Page ID nếu có
        if page_id:
            try:
                url = f"https://graph.facebook.com/{api_version}/{page_id}"
                logger.info(f"🔍 [1/3] Đang gọi Graph API kiểm tra Page: {url}")
                resp = requests.get(url, params={"fields": "name,id,access_token", "access_token": access_token}, timeout=15)
                logger.info(f"   Status Code: {resp.status_code}")
                logger.debug(f"   Response: {resp.text}")
                data = resp.json()
                if resp.status_code == 200 and "id" in data:
                    page_name = data.get("name", f"Page {page_id}")
                    logger.info(f"✅ [1/3] Xác thực thành công Page ID: {page_id} ({page_name})")
                    return {
                        "valid": True,
                        "page_name": page_name,
                        "page_id": data.get("id", page_id),
                        "page_access_token": data.get("access_token") or access_token,
                        "error": ""
                    }
                else:
                    logger.warning(f"   [1/3] Trả về: {data.get('error', {}).get('message', resp.text)}")
            except Exception as e:
                logger.error(f"   [1/3] Lỗi mạng khi gọi Page ID: {e}")

        # 2. Thử truy vấn danh sách Fanpage của User qua /me/accounts
        try:
            me_accounts_url = f"https://graph.facebook.com/{api_version}/me/accounts"
            logger.info(f"🔍 [2/3] Đang gọi Graph API lấy danh sách Pages: {me_accounts_url}")
            resp = requests.get(me_accounts_url, params={"access_token": access_token}, timeout=15)
            logger.info(f"   Status Code: {resp.status_code}")
            logger.debug(f"   Response: {resp.text}")
            data = resp.json()
            if resp.status_code == 200 and "data" in data and len(data["data"]) > 0:
                logger.info(f"✅ [2/3] Tìm thấy {len(data['data'])} Fanpage từ tài khoản!")
                # Nếu người dùng có nhập page_id, tìm đúng Page đó
                if page_id:
                    for p in data["data"]:
                        if str(p.get("id")) == str(page_id):
                            logger.info(f"   -> Khớp đúng Page: {p.get('name')} (ID: {p.get('id')})")
                            return {
                                "valid": True,
                                "page_name": p.get("name", f"Page {page_id}"),
                                "page_id": p.get("id"),
                                "page_access_token": p.get("access_token", access_token),
                                "error": ""
                            }
                first_page = data["data"][0]
                logger.info(f"   -> Tự động chọn Page đầu tiên: {first_page.get('name')} (ID: {first_page.get('id')})")
                return {
                    "valid": True,
                    "page_name": first_page.get("name"),
                    "page_id": first_page.get("id"),
                    "page_access_token": first_page.get("access_token", access_token),
                    "error": ""
                }
            else:
                logger.warning(f"   [2/3] Không lấy được accounts: {data.get('error', {}).get('message', 'Không có data')}")
        except Exception as e:
            logger.error(f"   [2/3] Lỗi mạng khi gọi /me/accounts: {e}")

        # 3. Thử kiểm tra tài khoản cá nhân /me
        try:
            me_url = f"https://graph.facebook.com/{api_version}/me"
            logger.info(f"🔍 [3/3] Đang gọi Graph API kiểm tra User cá nhân: {me_url}")
            resp = requests.get(me_url, params={"fields": "name,id", "access_token": access_token}, timeout=15)
            logger.info(f"   Status Code: {resp.status_code}")
            logger.debug(f"   Response: {resp.text}")
            data = resp.json()
            if resp.status_code == 200 and "id" in data:
                logger.info(f"✅ [3/3] Xác thực tài khoản cá nhân thành công: {data.get('name')} ({data.get('id')})")
                return {
                    "valid": True,
                    "page_name": f"{data.get('name')} (Cá nhân)",
                    "page_id": data.get("id", page_id or data.get("id")),
                    "page_access_token": access_token,
                    "error": ""
                }
            else:
                err_detail = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                err_code = data.get("error", {}).get("code", "")
                err_subcode = data.get("error", {}).get("error_subcode", "")
                full_err = f"{err_detail} (Mã lỗi: {err_code}_{err_subcode})"
                if not access_token.startswith("EAA"):
                    full_err += "\n\n⚠️ Lưu ý: Mã Token của bạn không bắt đầu bằng 'EAA...'. Hãy bấm nút [Copy] trên extension thay vì bôi đen chuột để tránh bị thiếu chữ cái đầu!"
                logger.error(f"❌ Xác thực thất bại: {full_err}")
                return {"valid": False, "page_name": "", "error": full_err}
        except Exception as e:
            logger.error(f"❌ Lỗi ngoại lệ: {e}")
            return {"valid": False, "page_name": "", "error": str(e)}

    def _execute_reels_upload(self, video_path: Path, file_size: int, title: str, description: str, tags: list) -> bool:
        """Thực thi 3 phase upload Reels đồng bộ (chạy trên thread executor)."""
        # 1. Start Phase
        start_url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/video_reels"
        start_params = {
            "upload_phase": "start",
            "access_token": self.access_token
        }

        try:
            logger.info("  [Phase 1/3] Initializing Reels upload session...")
            start_resp = requests.post(start_url, data=start_params, timeout=20)
            start_data = start_resp.json()

            if start_resp.status_code != 200 or "video_id" not in start_data:
                err = start_data.get("error", {}).get("message", start_resp.text)
                logger.error(f"  ✗ Start phase failed: {err}")
                return False

            video_id = start_data["video_id"]
            upload_url = start_data.get("upload_url")
            logger.info(f"  ✓ Session created! Video ID: {video_id}")

            # 2. Transfer Phase
            logger.info("  [Phase 2/3] Transferring video binary data...")
            headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream"
            }

            with open(video_path, "rb") as f:
                video_data = f.read()

            upload_target_url = upload_url or f"https://rupload.facebook.com/video-upload/{self.api_version}/{video_id}"
            transfer_resp = requests.post(
                upload_target_url,
                headers=headers,
                data=video_data,
                timeout=120
            )

            if transfer_resp.status_code not in (200, 201):
                logger.error(f"  ✗ Transfer phase failed: {transfer_resp.text}")
                return False

            logger.info("  ✓ Video binary transferred successfully!")

            # 3. Finish Phase (Publish)
            logger.info("  [Phase 3/3] Publishing Reel to Facebook...")
            full_caption = description if description else title
            if tags:
                tag_str = " ".join([f"#{t.replace('#','')}" for t in tags])
                if tag_str not in full_caption:
                    full_caption = f"{full_caption}\n\n{tag_str}".strip()

            finish_params = {
                "upload_phase": "finish",
                "access_token": self.access_token,
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": full_caption
            }

            finish_resp = requests.post(start_url, data=finish_params, timeout=30)
            finish_data = finish_resp.json()

            if finish_resp.status_code == 200 and finish_data.get("success", False):
                logger.info(f"  ✅ Facebook Reel published successfully! Video ID: {video_id}")
                return True
            else:
                err = finish_data.get("error", {}).get("message", finish_resp.text)
                logger.error(f"  ✗ Finish phase failed: {err}")
                return False

        except Exception as e:
            logger.error(f"Facebook Reels upload exception: {e}")
            return False

    # ─── Batch Upload ────────────────────────────────────────────────────────

    def _generate_fb_metadata(self, video_info: dict) -> dict:
        """Tạo title, description, tags cho Facebook Reels từ video info."""
        from utils.translator import generate_youtube_metadata_with_gemini
        from config.settings import PROCESSOR_CONFIG

        original = video_info.get("title", "")
        gemini_keys = PROCESSOR_CONFIG.get("gemini_api_keys", [])
        if not gemini_keys and PROCESSOR_CONFIG.get("gemini_api_key"):
            gemini_keys = [PROCESSOR_CONFIG.get("gemini_api_key")]

        default_tags = self.config.get("default_tags", ["reels", "shorts", "viral", "trending"])

        if original and gemini_keys:
            meta = generate_youtube_metadata_with_gemini(original, gemini_keys)
            if meta:
                meta["tags"] = list(set(meta["tags"] + default_tags))
                desc_template = self.config.get(
                    "default_description_template",
                    "{title}\n\n{description}\n\n{hashtags}"
                )
                title = meta["title"][:100]
                desc = meta["description"]
                hashtags_str = " ".join([f"#{t.replace('#','')}" for t in meta["tags"]])
                description = desc_template.replace("{title}", title).replace("{description}", desc).replace("{hashtags}", hashtags_str)
                return {"title": title, "description": description, "tags": meta["tags"]}

        # Fallback template
        title = original[:100] if original else "Hot Trending Video"
        hashtags_str = " ".join([f"#{t.replace('#','')}" for t in default_tags])
        desc_template = self.config.get("default_description_template", "{title}\n\n{hashtags}")
        description = desc_template.replace("{title}", title).replace("{hashtags}", hashtags_str)
        return {"title": title, "description": description, "tags": default_tags}

    async def upload_pending_videos(
        self,
        limit: int = 4,
        video_ids: list = None,
        custom_captions: dict = None,
        cancel_check = None
    ) -> List[int]:
        """
        Upload danh sách video đã processed lên Facebook Reels.
        """
        if video_ids:
            videos = []
            for vid in video_ids:
                v = self.db.get_video_by_id(vid)
                if v:
                    videos.append(v)
            videos = videos[:limit]
        else:
            videos = self.db.get_processed_videos(limit=limit, username=self.current_username)

        if not videos:
            logger.info("Không có video nào cần upload lên Facebook Reels.")
            return []

        # Check daily limit
        max_daily = self.config.get("max_posts_per_day", 10)
        today_count = self.db.get_today_post_count(platform="facebook", username=self.current_username)
        remaining = max(0, max_daily - today_count)

        if remaining <= 0:
            logger.warning(f"Đã đạt giới hạn upload Facebook hôm nay ({today_count}/{max_daily} posts)")
            return []

        videos = videos[:remaining]
        logger.info(f"Bắt đầu upload {len(videos)} video lên Facebook Reels (đã post hôm nay: {today_count}/{max_daily})...")

        uploaded = []
        custom_captions = custom_captions or {}

        for i, video in enumerate(videos, 1):
            if cancel_check and cancel_check():
                logger.warning("Upload Facebook Reels bị hủy bởi người dùng!")
                break

            video_id = video.get("id") or video.get("video_id")
            proc_path = video.get("processed_path")

            if not proc_path or not Path(proc_path).exists():
                logger.warning(f"[{i}/{len(videos)}] File processed không tồn tại: {proc_path}")
                continue

            logger.info(f"[{i}/{len(videos)}] Processing upload: {video.get('title', 'N/A')[:40]}...")

            # Tạo metadata
            if video_id in custom_captions and custom_captions[video_id].strip():
                description = custom_captions[video_id].strip()
                title = video.get("title", "")[:100]
                tags = self.config.get("default_tags", ["reels", "shorts"])
            else:
                meta = self._generate_fb_metadata(video)
                title = meta["title"]
                description = meta["description"]
                tags = meta["tags"]

            # Upload
            success = await self.upload_video(
                video_path=proc_path,
                title=title,
                description=description,
                tags=tags
            )

            if success:
                # Ghi nhận vào DB
                self.db.add_posted_video(
                    crawled_video_id=video["id"],
                    caption=description,
                    hashtags=" ".join([f"#{t.replace('#','')}" for t in tags]),
                    tiktok_video_id=str(video_id),
                    platform="facebook",
                    username=self.current_username
                )
                uploaded.append(video["id"])
                logger.info(f"[{i}/{len(videos)}] ✅ Hoàn thành upload Facebook: {video.get('title', 'N/A')[:30]}")

                # Auto cleanup nếu bật
                if self.config.get("auto_cleanup_after_upload", True):
                    try:
                        p = Path(proc_path)
                        if p.exists():
                            p.unlink()
                            logger.info(f"  🗑️ Cleaned up local file: {p.name}")
                    except Exception as e:
                        logger.warning(f"  Could not delete {proc_path}: {e}")

                # Delay ngẫu nhiên giữa các lần post
                if i < len(videos):
                    delay = random.uniform(10, 25)
                    logger.info(f"Waiting {delay:.1f}s trước video tiếp theo...")
                    await asyncio.sleep(delay)
            else:
                logger.error(f"[{i}/{len(videos)}] ✗ Upload Facebook thất bại cho video ID: {video_id}")

        return uploaded

    async def close(self):
        """Cleanup resources."""
        pass
