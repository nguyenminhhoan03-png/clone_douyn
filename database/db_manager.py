"""
Database Manager - Quản lý SQLite database cho video đã crawl và đã post
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from loguru import logger

from config.settings import DATABASE_PATH


class DatabaseManager:
    """Quản lý database SQLite lưu trữ thông tin video crawl/post."""
    
    _initialized = False

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not DatabaseManager._initialized:
            self._init_db()
            DatabaseManager._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo connection mới cho mỗi operation."""
        # Tăng timeout lên 20s để tránh lỗi 'database is locked' khi thread GUI và Background cùng truy cập
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Khởi tạo database và tạo bảng nếu chưa tồn tại."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Bảng lưu video đã crawl từ Douyin
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawled_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    title TEXT,
                    author TEXT,
                    music_title TEXT,
                    tags TEXT,
                    download_path TEXT,
                    processed_path TEXT,
                    duration REAL,
                    status TEXT DEFAULT 'pending',
                    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    error_message TEXT,
                    username TEXT,
                    title_vi TEXT,
                    custom_caption TEXT,
                    UNIQUE(video_id, username)
                )
            """)

            # Bảng lưu video đã post lên TikTok
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posted_videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crawled_video_id INTEGER NOT NULL,
                    caption TEXT,
                    hashtags TEXT,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'posted',
                    tiktok_video_id TEXT,
                    error_message TEXT,
                    platform TEXT DEFAULT 'tiktok',
                    FOREIGN KEY (crawled_video_id) REFERENCES crawled_videos(id)
                )
            """)

            # Bảng lưu thống kê
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    videos_crawled INTEGER DEFAULT 0,
                    videos_processed INTEGER DEFAULT 0,
                    videos_posted INTEGER DEFAULT 0
                )
            """)

            conn.commit()

            # Migration: thêm cột title_vi nếu chưa có
            try:
                cursor.execute("SELECT title_vi FROM crawled_videos LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE crawled_videos ADD COLUMN title_vi TEXT")
                conn.commit()
                logger.info("Migration: Added title_vi column")
                
            # Migration: thêm cột username cho crawled_videos
            try:
                cursor.execute("SELECT username FROM crawled_videos LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE crawled_videos ADD COLUMN username TEXT")
                conn.commit()
                logger.info("Migration: Added username column to crawled_videos")

            # Migration: thêm cột username cho posted_videos
            try:
                cursor.execute("SELECT username FROM posted_videos LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE posted_videos ADD COLUMN username TEXT")
                conn.commit()
                logger.info("Migration: Added username column to posted_videos")

            # Migration: thêm cột custom_caption
            try:
                cursor.execute("SELECT custom_caption FROM crawled_videos LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE crawled_videos ADD COLUMN custom_caption TEXT")
                conn.commit()
                logger.info("Migration: Added custom_caption column")

            # Migration: thêm cột drive_download_id và drive_processed_id
            try:
                cursor.execute("SELECT drive_download_id FROM crawled_videos LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE crawled_videos ADD COLUMN drive_download_id TEXT")
                cursor.execute("ALTER TABLE crawled_videos ADD COLUMN drive_processed_id TEXT")
                conn.commit()
                logger.info("Migration: Added drive_download_id and drive_processed_id columns")

            logger.info(f"Database initialized at: {self.db_path}")
        finally:
            conn.close()

    # ============================================================
    # CRAWLED VIDEOS OPERATIONS
    # ============================================================

    def add_crawled_video(self, video_id: str, source_url: str, title: str = None,
                          author: str = None, music_title: str = None,
                          tags: str = None, download_path: str = None,
                          duration: float = None, username: str = None,
                          drive_download_id: str = None) -> int:
        """Thêm video đã crawl vào database. Trả về row id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO crawled_videos 
                (video_id, source_url, title, author, music_title, tags, download_path, duration, username, drive_download_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (video_id, source_url, title, author, music_title, tags, download_path, duration, username, drive_download_id))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Added crawled video: {video_id} - {title}")
                self._update_daily_stats("videos_crawled")
                return cursor.lastrowid
            else:
                logger.debug(f"Video already exists: {video_id}")
                return -1
        finally:
            conn.close()

    def is_duplicate(self, video_id: str, username: str = None) -> bool:
        """Kiểm tra video đã tồn tại trong database chưa."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if username:
                cursor.execute("SELECT 1 FROM crawled_videos WHERE video_id = ? AND username = ?", (video_id, username))
            else:
                cursor.execute("SELECT 1 FROM crawled_videos WHERE video_id = ?", (video_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def update_video_status(self, video_id: str, status: str,
                            processed_path: str = None, error_message: str = None, drive_processed_id: str = None):
        """Cập nhật trạng thái video (downloaded, processed, failed)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if status == "processed":
                cursor.execute("""
                    UPDATE crawled_videos 
                    SET status = ?, processed_path = ?, processed_at = ?, drive_processed_id = ?
                    WHERE video_id = ?
                """, (status, processed_path, datetime.now().isoformat(), drive_processed_id, video_id))
            elif status == "failed":
                cursor.execute("""
                    UPDATE crawled_videos SET status = ?, error_message = ? WHERE video_id = ?
                """, (status, error_message, video_id))
            else:
                cursor.execute("""
                    UPDATE crawled_videos SET status = ? WHERE video_id = ?
                """, (status, video_id))
            conn.commit()
            logger.info(f"Updated video {video_id} status to: {status}")
            
            if status == "processed" and processed_path:
                self._update_daily_stats("videos_processed")
        finally:
            conn.close()

    def update_translated_title(self, video_id: str, title_vi: str):
        """Lưu title đã dịch sang tiếng Việt."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE crawled_videos SET title_vi = ? WHERE video_id = ?",
                (title_vi, video_id)
            )
            conn.commit()
            logger.debug(f"Saved Vietnamese title for {video_id}: {title_vi[:50]}")
        finally:
            conn.close()

    def update_custom_caption(self, video_id: str, custom_caption: str):
        """Lưu caption đã được người dùng chỉnh sửa thủ công."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE crawled_videos SET custom_caption = ? WHERE video_id = ?",
                (custom_caption, video_id)
            )
            conn.commit()
            logger.info(f"Đã lưu custom caption cho video {video_id}")
        finally:
            conn.close()

    def get_authors(self, status: str = None, username: str = None) -> list:
        """Lấy danh sách các tác giả duy nhất."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT DISTINCT author FROM crawled_videos WHERE author IS NOT NULL AND author != ''"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if username:
                query += " AND username = ?"
                params.append(username)
            query += " ORDER BY author ASC"
            cursor.execute(query, tuple(params))
            return [row["author"] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_pending_videos(self, limit: int = 5, username: str = None, author: str = None, platform: str = None) -> list:
        """Lấy danh sách video đã processed, chưa post theo từng platform."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if platform:
                query = """
                    SELECT * FROM crawled_videos 
                    WHERE status = 'processed' 
                    AND id NOT IN (SELECT crawled_video_id FROM posted_videos WHERE status = 'posted' AND platform = ?)
                """
                params = [platform]
            else:
                query = """
                    SELECT * FROM crawled_videos 
                    WHERE status = 'processed' 
                    AND id NOT IN (SELECT crawled_video_id FROM posted_videos WHERE status = 'posted')
                """
                params = []
            if username:
                clean_user = username.replace("@", "_").replace(".", "_")
                query += " AND (username = ? OR REPLACE(REPLACE(username, '@', '_'), '.', '_') = ?)"
                params.extend([username, clean_user])
            if author:
                query += " AND author = ?"
                params.append(author)
            query += " ORDER BY processed_at DESC, crawled_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_downloaded_videos(self, limit: int = 10, username: str = None, author: str = None) -> list:
        """Lấy danh sách video đã download, chưa processed."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM crawled_videos WHERE status = 'downloaded'"
            params = []
            if username:
                query += " AND username = ?"
                params.append(username)
            if author:
                query += " AND author = ?"
                params.append(author)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_videos(self, status: str = None, limit: int = 50, username: str = None, author: str = None) -> list:
        """Lấy tất cả video với optional status filter."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM crawled_videos WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if username:
                query += " AND username = ?"
                params.append(username)
            if author:
                query += " AND author = ?"
                params.append(author)
                
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_video_by_id(self, video_id: str):
        """Lấy thông tin 1 video theo video_id hoặc id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM crawled_videos WHERE video_id = ? OR id = ?", (str(video_id), str(video_id)))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_processed_videos(self, limit: int = 5, username: str = None, author: str = None, platform: str = None) -> list:
        """Lấy danh sách video đã processed."""
        return self.get_pending_videos(limit=limit, username=username, author=author, platform=platform)

    # ============================================================
    # POSTED VIDEOS OPERATIONS
    # ============================================================

    def add_posted_video(self, crawled_video_id: int, caption: str,
                         hashtags: str, tiktok_video_id: str = None, platform: str = "tiktok", username: str = None) -> int:
        """Ghi nhận video đã post lên TikTok/YouTube."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posted_videos (crawled_video_id, caption, hashtags, tiktok_video_id, platform, username)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (crawled_video_id, caption, hashtags, tiktok_video_id, platform, username))
            conn.commit()
            self._update_daily_stats("videos_posted")
            logger.info(f"Recorded posted video: crawled_id={crawled_video_id}")
            return cursor.lastrowid
        finally:
            conn.close()

    def get_today_post_count(self, platform: str = "tiktok", username: str = None) -> int:
        """Đếm số video đã post hôm nay."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            query = "SELECT COUNT(*) FROM posted_videos WHERE DATE(posted_at) = ? AND status = 'posted' AND platform = ?"
            params = [today, platform]
            if username:
                clean_user = username.replace("@", "_").replace(".", "_")
                query += " AND (username = ? OR REPLACE(REPLACE(username, '@', '_'), '.', '_') = ?)"
                params.extend([username, clean_user])
                
            cursor.execute(query, tuple(params))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_today_processed_count(self, username: str = None) -> int:
        """Đếm số video đã processed hôm nay."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            query = "SELECT COUNT(*) FROM crawled_videos WHERE DATE(processed_at) = ?"
            params = [today]
            if username:
                query += " AND username = ?"
                params.append(username)

                
            cursor.execute(query, tuple(params))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    # ============================================================
    # STATISTICS
    # ============================================================

    def _update_daily_stats(self, field: str):
        """Cập nhật thống kê hàng ngày."""
        conn = self._get_connection()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO daily_stats (date, {field}) VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET {field} = {field} + 1
            """.format(field=field), (today,))
            conn.commit()
        finally:
            conn.close()

    def get_stats(self, username: str = None) -> dict:
        """Lấy thống kê tổng quan."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            user_filter = " AND username = ?" if username else ""
            params = (username,) if username else ()

            cursor.execute(f"SELECT COUNT(*) FROM crawled_videos WHERE 1=1{user_filter}", params)
            total_crawled = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM crawled_videos WHERE status = 'processed'{user_filter}", params)
            total_processed = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM posted_videos WHERE status = 'posted'{user_filter}", params)
            total_posted = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM crawled_videos WHERE status = 'downloaded'{user_filter}", params)
            pending_process = cursor.fetchone()[0]

            pending_post = len(self.get_pending_videos(limit=100, username=username))

            today_posted = self.get_today_post_count(username=username)

            return {
                "total_crawled": total_crawled,
                "total_processed": total_processed,
                "total_posted": total_posted,
                "pending_process": pending_process,
                "pending_post": pending_post,
                "today_posted": today_posted,
            }
        finally:
            conn.close()

    # ============================================================
    # DELETION
    # ============================================================

    def delete_video_data(self, video_id: str) -> bool:
        """Xóa video khỏi Database, ổ cứng và cả Google Drive."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Lấy đường dẫn file và Google Drive ID trước khi xóa
            cursor.execute("SELECT * FROM crawled_videos WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            if row:
                import os
                # 1. Xóa file cục bộ trên ổ cứng
                paths_to_delete = [row["download_path"], row["processed_path"]]
                for p in paths_to_delete:
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                
                # 2. Xóa file trên Google Drive nếu có
                username = row["username"] if "username" in row.keys() and row["username"] else "admin"
                drive_download_id = row["drive_download_id"] if "drive_download_id" in row.keys() else None
                drive_processed_id = row["drive_processed_id"] if "drive_processed_id" in row.keys() else None
                
                if drive_download_id or drive_processed_id:
                    try:
                        from uploader.google_drive_uploader import GoogleDriveUploader
                        uploader = GoogleDriveUploader(username)
                        uploader.authenticate()
                        if drive_download_id:
                            uploader.delete_file(drive_download_id)
                        if drive_processed_id:
                            uploader.delete_file(drive_processed_id)
                    except Exception as e:
                        logger.warning(f"Lỗi khi xóa file trên Google Drive ({video_id}): {e}")

                # 3. Xóa khỏi DB (Cascade/Manual)
                cursor.execute("SELECT id FROM crawled_videos WHERE video_id = ?", (video_id,))
                crawled_id_row = cursor.fetchone()
                if crawled_id_row:
                    crawled_id = crawled_id_row["id"]
                    cursor.execute("DELETE FROM posted_videos WHERE crawled_video_id = ?", (crawled_id,))
                
                cursor.execute("DELETE FROM crawled_videos WHERE video_id = ?", (video_id,))
                conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting video {video_id}: {e}")
            return False
        finally:
            conn.close()
