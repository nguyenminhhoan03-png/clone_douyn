import asyncio
import httpx
import re

async def main():
    url = "https://www.douyin.com/video/7372909012443991308" # A random ID from screenshot
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        print("Status:", resp.status_code)
        title_match = re.search(r'<title>(.*?)</title>', resp.text)
        if title_match:
            print("Title found:", title_match.group(1))
        else:
            print("No title tag")

asyncio.run(main())
