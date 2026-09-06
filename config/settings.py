"""
Settings module - Cấu hình chung cho toàn bộ hệ thống
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# ============================================================
# BASE PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
PROCESSED_DIR = BASE_DIR / "processed"
MUSIC_DIR = BASE_DIR / "music"  # Thư mục chứa nhạc Việt trending
LOGS_DIR = BASE_DIR / "logs"
DATABASE_PATH = BASE_DIR / "database" / "videos.db"
COOKIES_DIR = BASE_DIR / "config" / "cookies"

# Tạo thư mục nếu chưa tồn tại
for dir_path in [DOWNLOADS_DIR, PROCESSED_DIR, MUSIC_DIR, LOGS_DIR, COOKIES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


def get_user_processed_dir(username: str = "default") -> Path:
    """Trả về thư mục processed riêng cho mỗi user (processed/<username>/)."""
    username = username or "default"
    user_dir = PROCESSED_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def get_user_downloads_dir(username: str = "default") -> Path:
    """Trả về thư mục downloads riêng cho mỗi user (downloads/<username>/)."""
    username = username or "default"
    user_dir = DOWNLOADS_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

# ============================================================
# DOUYIN CRAWLER CONFIG
# ============================================================
DOUYIN_CONFIG = {
    # Headers giả lập trình duyệt
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    # Cookies file path
    "cookies_file": COOKIES_DIR / "douyin_cookies.txt",
    # API endpoints
    "base_url": "https://www.douyin.com",
    "api_url": "https://www.douyin.com/aweme/v1/web",
    # Crawl settings
    "max_videos_per_session": 20,
    "request_delay": (2, 5),  # Random delay giữa các request (min, max) giây
    # Proxy (để trống nếu không dùng)
    "proxy": os.getenv("DOUYIN_PROXY", None),  # Ví dụ: "http://user:pass@ip:port"
}

# ============================================================
# TIKTOK UPLOADER CONFIG
# ============================================================
TIKTOK_CONFIG = {
    # Cookies file path
    "cookies_file": COOKIES_DIR / os.getenv("TIKTOK_COOKIE_FILE", "tiktok_cookies.json"),
    # Upload settings
    "max_posts_per_day": int(os.getenv("MAX_POSTS_PER_DAY", "4")),
    "post_interval_hours": (3, 4),  # Random delay giữa các lần post (min, max) giờ
    "auto_cleanup_after_upload": True,  # Tự động xóa file local mp4 sau khi upload xong
    # Default hashtags cho thị trường VN
    "default_hashtags": [
        "#fyp", "#foryou", "#xuhuong", "#tiktokvietnam",
        "#trending", "#viral", "#dance", "#nhảy",
        "#gainhay", "#hotgirl", "#tiktokgainhat",
    ],
    # Caption templates
    "caption_templates": [
        "😍 {title} #fyp #xuhuong",
        "🔥 {title} #viral #tiktokvietnam",
        "💃 {title} #dance #trending",
        "✨ {title} #foryou #gainhay",
        "🎵 {title} #nhảy #hotgirl",
    ],
    # Browser settings cho Playwright
    "browser": {
        "headless": os.getenv("HEADLESS", "True" if os.name != "nt" else "False").lower() in ("true", "1"),  # True khi chạy Docker/Linux
        "slow_mo": int(os.getenv("BROWSER_SLOW_MO", "500")),  # Delay giữa các actions (ms)
        "viewport": {"width": 1280, "height": 720},
    },
}

# ============================================================
# YOUTUBE UPLOADER CONFIG
# ============================================================
YOUTUBE_CONFIG = {
    # Default Client Secret
    "client_secret_file": COOKIES_DIR / "client_secret.json",
    # Upload settings
    "max_posts_per_day": 5,
    "default_privacy": "public",  # public, unlisted, private
    "default_category": "22",      # 22 = People & Blogs
    "default_tags": ["shorts", "viral", "trending", "xuhuong"],
    "default_description_template": "{title}\n\n#shorts #viral #trending #xuhuong",
    "auto_cleanup_after_upload": True,
}

# ============================================================
# VIDEO PROCESSOR CONFIG
# ============================================================

# ============================================================
# FACEBOOK REELS UPLOADER CONFIG
# ============================================================
FACEBOOK_CONFIG = {
    "graph_api_version": "v19.0",
    "max_posts_per_day": 10,
    "default_tags": ["reels", "shorts", "viral", "trending", "xuhuong"],
    "default_description_template": "{title}\n\n#reels #shorts #viral #trending #xuhuong",
    "auto_cleanup_after_upload": True,
}

PROCESSOR_CONFIG = {
    # Text overlay settings
    "text_overlay": {
        "font_size": 45,
        "font_color": "white",
        "bg_color": (0, 0, 0, 160),  # RGBA - nền đen trong suốt
        "position": "top",  # top, center, bottom
        "margin": 30,
    },
    # Hiệu ứng cơ bản
    "mirror": True,  # Mirror (Lật video): BẬT
    "replace_audio": False,  # Ghép nhạc nền: TẮT
    "original_audio_volume": 0.5,  # Âm lượng gốc: 50%
    "mute_original_audio": False,  # Tắt âm thanh gốc: TẮT
    "speed_range": (0.97, 1.03),  # Thay đổi tốc độ nhẹ
    "brightness_adjust": 1.05,  # Tăng sáng nhẹ

    # Subtitles & Blur
    "auto_subtitle": True,  # Auto-Vietsub: BẬT
    "subtitle_overlay": "overlay_blur",  # Vị trí sub: Đè lên vùng mờ
    "blur_enabled": True,   # Làm mờ phụ đề gốc: BẬT
    "blur_pct": 0.15,       # Vùng làm mờ: 15%
    "blur_position": "auto", # Vị trí làm mờ: Tự động (AI Auto-Detect)

    # Voiceover AI
    "ai_dubbing": True,  # Thuyết minh AI: BẬT
    "dubbing_mode": "original",  # Chế độ: Thuyết minh nguyên bản
    "tts_voice": "Multi",  # Giọng đọc: Đa giọng (Đoản kịch)
    "tts_rate": "+15%",  # Tốc độ đọc: 15%
    
    # Whisper Model (Local PC Windows: medium, Docker VPS Linux: base)
    "whisper_model": os.getenv("WHISPER_MODEL", "base" if os.name != "nt" else "medium"),
    # AI Translation Provider: "ollama" (Local offline), "gemini", hoặc "groq"
    "ai_provider": os.getenv("AI_PROVIDER", "ollama"),
    "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
    "ollama_model": os.getenv("OLLAMA_MODEL", "qwen2.5"),
    # Gemini/Groq AI Translation (Hỗ trợ xoay tua nhiều key, cách nhau dấu phẩy)
    "gemini_api_keys": [k.strip() for k in os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()],
    
    # Nền tảng đích: TikTok
    "platform": "tiktok",
    
    # YouTube Bypass (Anti-Content ID)
    "youtube_bypass": {
        "crop_zoom": 1.15,         # Zoom & crop 15% viền
        "add_noise": True,         # Thêm nhiễu hạt nhẹ
        "logo_path": None,         # Đường dẫn file logo PNG
        "logo_position": "top_right", # top_left, top_right, bottom_left, bottom_right, floating
        "logo_scale": 0.15,        # Tỉ lệ logo so với chiều rộng video (15%)
    },
    # Output settings
    "output_fps": 30,
    "output_codec": "libx264",
    "output_audio_codec": "aac",
    "output_bitrate": "5000k",
}

# ============================================================
# SCHEDULER CONFIG
# ============================================================
SCHEDULER_CONFIG = {
    # Crawl schedule
    "crawl_interval_hours": 12,  # Crawl mỗi 12 giờ
    "crawl_count": 10,  # Số video crawl mỗi lần
    # Post schedule
    "post_times": ["09:00", "12:30", "18:00", "21:30"],  # Giờ post (VN timezone)
    "timezone": "Asia/Ho_Chi_Minh",
}

# ============================================================
# LOGGING CONFIG
# ============================================================
LOG_CONFIG = {
    "log_file": LOGS_DIR / "app_{time}.log",
    "rotation": "10 MB",
    "retention": "7 days",
    "level": "INFO",
}

# ============================================================
# GOOGLE DRIVE BACKUP CONFIG
# ============================================================
GOOGLE_DRIVE_CONFIG = {
    # Default Client Secret for Drive
    "client_secret_file": COOKIES_DIR / "client_secret.json",
    # Tự động backup lên Google Drive sau khi có file (crawled/processed)
    "auto_backup": os.getenv("DRIVE_AUTO_BACKUP", "False").lower() == "true",
    # Xóa file local sau khi backup thành công
    "delete_local_after_backup": os.getenv("DRIVE_DELETE_LOCAL", "False").lower() == "true",
}
