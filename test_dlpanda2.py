import httpx
import asyncio
import re

async def test_dlpanda2():
    url = "https://v.douyin.com/w44Uv1d1z_g/"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(f"https://dlpanda.com/vi?url={url}&token=G7eRpMaa", headers=headers, timeout=10)
        
        # Regex to find video source
        src_match = re.search(r'<source[^>]+src="([^"]+)"', r.text)
        if src_match:
            video_url = src_match.group(1)
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            print("Video URL:", video_url)
        else:
            print("No video source found. Let's look for hrefs.")
            href_matches = re.findall(r'href="([^"]+)"', r.text)
            links = [l for l in href_matches if 'dlpanda.com' in l or 'douyin' in l or '.mp4' in l]
            print("Links:", links[:5])
            
        # Title
        title_match = re.search(r'<p[^>]*class="title"[^>]*>(.*?)</p>', r.text, re.IGNORECASE | re.DOTALL)
        if title_match:
            print("Title:", title_match.group(1).strip())

asyncio.run(test_dlpanda2())
