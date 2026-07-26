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
                    video_id TEXT UNIQUE NOT NULL,
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
                    error_message TEXT
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
                
            # Migration: thêm cột platform vào posted_videos
            try:
                cursor.execute("SELECT platform FROM posted_videos LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE posted_videos ADD COLUMN platform TEXT DEFAULT 'tiktok'")
                conn.commit()
                logger.info("Migration: Added platform column to posted_videos")

            logger.info(f"Database initialized at: {self.db_path}")
        finally:
            conn.close()

    # ============================================================
    # CRAWLED VIDEOS OPERATIONS
    # ============================================================

    def add_crawled_video(self, video_id: str, source_url: str, title: str = None,
                          author: str = None, music_title: str = None,
                          tags: str = None, download_path: str = None,
                          duration: float = None) -> int:
        """Thêm video đã crawl vào database. Trả về row id."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO crawled_videos 
                (video_id, source_url, title, author, music_title, tags, download_path, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (video_id, source_url, title, author, music_title, tags, download_path, duration))
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

    def is_duplicate(self, video_id: str) -> bool:
        """Kiểm tra video đã tồn tại trong database chưa."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM crawled_videos WHERE video_id = ?", (video_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def update_video_status(self, video_id: str, status: str,
                            processed_path: str = None, error_message: str = None):
        """Cập nhật trạng thái video (downloaded, processed, failed)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if status == "processed" and processed_path:
                cursor.execute("""
                    UPDATE crawled_videos 
                    SET status = ?, processed_path = ?, processed_at = ?
                    WHERE video_id = ?
                """, (status, processed_path, datetime.now().isoformat(), video_id))
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

    def get_pending_videos(self, limit: int = 5) -> list:
        """Lấy danh sách video đã processed, chưa post."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM crawled_videos 
                WHERE status = 'processed' 
                AND id NOT IN (SELECT crawled_video_id FROM posted_videos WHERE status = 'posted')
                ORDER BY crawled_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_downloaded_videos(self, limit: int = 10) -> list:
        """Lấy danh sách video đã download, chưa processed."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM crawled_videos 
                WHERE status = 'downloaded'
                ORDER BY crawled_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_videos(self, status: str = None, limit: int = 50) -> list:
        """Lấy tất cả video với optional status filter."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM crawled_videos WHERE status = ? 
                    ORDER BY crawled_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM crawled_videos ORDER BY crawled_at DESC LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ============================================================
    # POSTED VIDEOS OPERATIONS
    # ============================================================

    def add_posted_video(self, crawled_video_id: int, caption: str,
                         hashtags: str, tiktok_video_id: str = None, platform: str = "tiktok") -> int:
        """Ghi nhận video đã post lên TikTok/YouTube."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posted_videos (crawled_video_id, caption, hashtags, tiktok_video_id, platform)
                VALUES (?, ?, ?, ?, ?)
            """, (crawled_video_id, caption, hashtags, tiktok_video_id, platform))
            conn.commit()
            self._update_daily_stats("videos_posted")
            logger.info(f"Recorded posted video: crawled_id={crawled_video_id}")
            return cursor.lastrowid
        finally:
            conn.close()

    def get_today_post_count(self, platform: str = "tiktok") -> int:
        """Đếm số video đã post hôm nay."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT COUNT(*) FROM posted_videos 
                WHERE DATE(posted_at) = ? AND status = 'posted' AND platform = ?
            """, (today, platform))
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

    def get_stats(self) -> dict:
        """Lấy thống kê tổng quan."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM crawled_videos")
            total_crawled = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM crawled_videos WHERE status = 'processed'")
            total_processed = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM posted_videos WHERE status = 'posted'")
            total_posted = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM crawled_videos WHERE status = 'downloaded'")
            pending_process = cursor.fetchone()[0]

            pending_post = len(self.get_pending_videos(limit=100))

            today_posted = self.get_today_post_count()

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
        """Xóa video khỏi Database và ổ cứng."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Lấy đường dẫn file trước khi xóa
            cursor.execute("SELECT download_path, processed_path FROM crawled_videos WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            if row:
                import os
                paths_to_delete = [row["download_path"], row["processed_path"]]
                for p in paths_to_delete:
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                
                # Xóa khỏi DB (Cascade/Manual)
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
