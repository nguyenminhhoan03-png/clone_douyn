import httpx
import asyncio

async def test_api():
    url = "https://v.douyin.com/w44Uv1d1z_g/"
    # Try tikwm first (maybe their API for Douyin is different?)
    # Try unduhtiktok API
    api_url = "https://unduhtiktok.com/api/ajaxSearch"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://unduhtiktok.com/vi/douyin/",
        "Origin": "https://unduhtiktok.com"
    }
    data = {"q": url, "vt": "douyin"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(api_url, headers=headers, data=data)
        print("unduhtiktok:", resp.status_code)
        print(resp.text[:1000])

asyncio.run(test_api())
