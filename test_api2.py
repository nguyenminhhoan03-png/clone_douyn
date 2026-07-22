import httpx
import asyncio

async def test_apis():
    url = "https://v.douyin.com/w44Uv1d1z_g/"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Test tiklydown
        print("Testing tiklydown...")
        try:
            r1 = await client.get(f"https://api.tiklydown.eu.org/api/download?url={url}", timeout=10)
            print("Tiklydown:", r1.status_code)
            if r1.status_code == 200:
                print(r1.text[:200])
        except Exception as e: print("Tiklydown error:", e)

        # Test dlpanda
        print("\nTesting dlpanda...")
        try:
            r3 = await client.get(f"https://dlpanda.com/vi?url={url}&token=G7eRpMaa", timeout=10)
            print("Dlpanda:", r3.status_code)
        except Exception as e: print("Dlpanda error:", e)

        # Test unduhtiktok with redirects
        print("\nTesting unduhtiktok...")
        try:
            r4 = await client.post("https://unduhtiktok.com/api/ajaxSearch", data={"q": url, "vt": "douyin"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            print("unduhtiktok:", r4.status_code)
            if r4.status_code == 200:
                print(r4.text[:200])
        except Exception as e: print("unduhtiktok error:", e)

asyncio.run(test_apis())
