import httpx
import asyncio
from bs4 import BeautifulSoup

async def test_dlpanda():
    url = "https://v.douyin.com/w44Uv1d1z_g/"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(f"https://dlpanda.com/vi?url={url}&token=G7eRpMaa", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for video links
        video_links = [a['href'] for a in soup.find_all('a', href=True) if 'download' in a.get('class', []) or 'btn' in a.get('class', []) or 'video' in a['href']]
        video_srcs = [src['src'] for src in soup.find_all('source')]
        
        print("Links found:", video_links[:5])
        print("Video Srcs:", video_srcs)
        
        # Title
        title_tag = soup.find('p', class_='title')
        if title_tag:
            print("Title:", title_tag.text)

asyncio.run(test_dlpanda())
