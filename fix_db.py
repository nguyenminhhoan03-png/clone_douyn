import sqlite3
import os
from pathlib import Path

db_path = Path(__file__).parent / "database" / "videos.db"
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM crawled_videos WHERE video_id='7654053716367414867'")
    conn.commit()
    conn.close()
    print("✅ Đã xóa video lỗi khỏi database.")
else:
    print("Không tìm thấy database.")

video_file = Path(__file__).parent / "downloads" / "7654053716367414867.mp4"
if video_file.exists():
    video_file.unlink()
    print("✅ Đã xóa file video lỗi.")
