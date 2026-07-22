import asyncio
import httpx
import re

async def debug_parse():
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
        
        with open("debug_html.txt", "w", encoding="utf-8") as f:
            f.write(html)
            
        play_urls = re.findall(r'"(https?://[^"]*?video/tos/[^"]*?)"', html)
        if not play_urls:
             play_urls = re.findall(r'"(https?://[^"]*?(?:v26|v3|v5)[^"]*?)"', html)
             
        with open("debug_urls.txt", "w", encoding="utf-8") as f:
            for u in play_urls:
                f.write(u + "\n\n")

if __name__ == "__main__":
    asyncio.run(debug_parse())
