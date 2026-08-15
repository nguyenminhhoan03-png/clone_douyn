import sqlite3
import shutil
from loguru import logger

db_path = "e:/Project_ItWebDev/Python/tiktok-upload-video/database/videos.db"

def migrate():
    # backup
    shutil.copy2(db_path, db_path + ".bak")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if UNIQUE on video_id exists by trying to insert a duplicate with different username
    # Or just recreate it
    cursor.execute("PRAGMA foreign_keys=off;")
    
    # 1. Rename table
    cursor.execute("ALTER TABLE crawled_videos RENAME TO crawled_videos_old;")
    
    # 2. Create new table without the UNIQUE constraint on video_id alone, but with UNIQUE(video_id, username)
    cursor.execute("""
        CREATE TABLE crawled_videos (
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
    
    # 3. Copy data
    cursor.execute("""
        INSERT INTO crawled_videos 
        (id, video_id, source_url, title, author, music_title, tags, download_path, processed_path, 
         duration, status, crawled_at, processed_at, error_message, username, title_vi, custom_caption)
        SELECT 
         id, video_id, source_url, title, author, music_title, tags, download_path, processed_path, 
         duration, status, crawled_at, processed_at, error_message, username, title_vi, custom_caption
        FROM crawled_videos_old;
    """)
    
    # 4. Drop old table
    cursor.execute("DROP TABLE crawled_videos_old;")
    
    conn.commit()
    conn.close()
    print("Migration successful")

if __name__ == "__main__":
    migrate()
