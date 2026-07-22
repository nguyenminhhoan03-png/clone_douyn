"""Test yt-dlp với Douyin URL"""
import yt_dlp

url = "https://v.douyin.com/K_UlIwJrDJY/"

print(f"Testing yt-dlp with: {url}")
print("-" * 60)

ydl_opts = {
    "quiet": False,
    "no_warnings": False,
    "skip_download": True,   # Chỉ lấy info, chưa download
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print("\n✅ SUCCESS!")
        print(f"  Title   : {info.get('title', 'N/A')}")
        print(f"  Author  : {info.get('uploader', 'N/A')}")
        print(f"  Duration: {info.get('duration', 0)}s")
        url_list = info.get('url') or (info.get('formats') or [{}])[-1].get('url', 'N/A')
        print(f"  URL     : {str(url_list)[:80]}...")
except Exception as e:
    print(f"\n❌ FAILED: {e}")
