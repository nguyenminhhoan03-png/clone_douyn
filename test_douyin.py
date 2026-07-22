import asyncio
import httpx
import re
import json

async def test_douyin():
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
        
        print("Status:", resp.status_code)
        print("HTML len:", len(html))
        
        # Check RENDER_DATA
        render_data = re.search(r'<script\s+id="RENDER_DATA"[^>]*>(.*?)</script>', html, re.DOTALL)
        if render_data:
            print("Found RENDER_DATA, len:", len(render_data.group(1)))
        
        # Check SSR_HYDRATED_DATA
        ssr_data = re.search(r'window\["_SSR_HYDRATED_DATA"\]=(.*?);</script>', html, re.DOTALL)
        if ssr_data:
            print("Found SSR_HYDRATED_DATA, len:", len(ssr_data.group(1)))
            
        # Check ROUTER_DATA
        router_data = re.search(r'window\._ROUTER_DATA\s*=\s*(.*?);</script>', html, re.DOTALL)
        if router_data:
            print("Found _ROUTER_DATA, len:", len(router_data.group(1)))
            
asyncio.run(test_douyin())
