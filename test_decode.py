import asyncio
import httpx
import re

async def test_download_url():
    url = "https://www.douyin.com/video/7654053716367414867"
    cookies_content = open("config/cookies/douyin_cookies.txt").read()
    cookies = {}
    for line in cookies_content.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            cookies[k.strip()] = v.strip()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/"
    }

    async with httpx.AsyncClient(headers=headers, cookies=cookies) as client:
        resp = await client.get(url)
        html = resp.text
        
        play_urls = re.findall(r'"(https?://[^"]*?video/tos/[^"]*?)"', html)
        if not play_urls:
             play_urls = re.findall(r'"(https?://[^"]*?(?:v26|v3|v5)[^"]*?)"', html)
             
        if play_urls:
            raw_url = max(play_urls, key=len)
            print("Raw URL:", raw_url)
            
            clean_url = raw_url.replace("\\u002F", "/").replace("\\/", "/").replace("\\u0026", "&")
            print("Clean URL:", clean_url)
            
            # Test download
            print("Testing download...")
            dl_resp = await client.get(clean_url)
            print("Download status:", dl_resp.status_code)
        else:
            print("No video URLs found in HTML")

asyncio.run(test_download_url())
