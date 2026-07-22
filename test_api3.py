import httpx
import asyncio

async def test_douyin_wtf():
    url = "https://v.douyin.com/w44Uv1d1z_g/"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(f"https://api.douyin.wtf/api?url={url}", headers=headers, timeout=10)
        print("Status:", r.status_code)
        print("JSON:", r.text[:1000])

asyncio.run(test_douyin_wtf())
