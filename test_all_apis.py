"""
Test tất cả API để xem cái nào hoạt động với URL Douyin hiện tại.
Chạy: python test_all_apis.py
"""
import asyncio
import httpx
import json

# ← Thay URL này bằng URL Douyin video bạn muốn test
TEST_URL = "https://www.douyin.com/jingxuan?modal_id=7650434462522030705"

# Nếu có short URL thì dùng cái này thay thế
# TEST_URL = "https://v.douyin.com/w44Uv1d1z_g/"


async def test_all():
    print(f"\n{'='*60}")
    print(f"Testing URL: {TEST_URL}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    ) as client:

        # ── API 1: tikwm.com ─────────────────────────────────────────────
        print("🔵 [1] tikwm.com")
        try:
            r = await client.post("https://www.tikwm.com/api/", data={"url": TEST_URL})
            data = r.json()
            code = data.get("code")
            if code == 0 and data.get("data", {}).get("play"):
                print("   ✅ SUCCESS! play_url:", data["data"]["play"][:80])
            else:
                print(f"   ❌ FAIL  code={code}  msg={data.get('msg','')}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # ── API 2: tiklydown ─────────────────────────────────────────────
        print("\n🔵 [2] tiklydown.eu.org")
        try:
            r = await client.get(f"https://api.tiklydown.eu.org/api/download?url={TEST_URL}")
            print(f"   Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if data.get("video", {}).get("noWatermark"):
                    print("   ✅ SUCCESS! url:", data["video"]["noWatermark"][:80])
                else:
                    print("   ❌ FAIL  Response:", r.text[:200])
            else:
                print("   ❌ HTTP", r.status_code, r.text[:100])
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # ── API 3: douyin.wtf ─────────────────────────────────────────────
        print("\n🔵 [3] api.douyin.wtf")
        try:
            r = await client.get(f"https://api.douyin.wtf/api?url={TEST_URL}")
            print(f"   Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                vdata = data.get("video_data", {})
                if vdata.get("nwm_video_url"):
                    print("   ✅ SUCCESS! url:", vdata["nwm_video_url"][:80])
                else:
                    print("   ❌ FAIL  status:", data.get("status"), "| msg:", data.get("message", "")[:100])
            else:
                print("   ❌ HTTP", r.status_code)
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # ── API 4: dlpanda.com ────────────────────────────────────────────
        print("\n🔵 [4] dlpanda.com")
        try:
            import re
            r = await client.get(f"https://dlpanda.com/vi?url={TEST_URL}&token=G7eRpMaa")
            print(f"   Status: {r.status_code}")
            src = re.search(r'<source[^>]+src="([^"]+)"', r.text)
            if src:
                url = src.group(1)
                if url.startswith("//"): url = "https:" + url
                print("   ✅ SUCCESS! video_url:", url[:80])
            else:
                print("   ❌ FAIL  no <source> tag found")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # ── API 5: snapdouyin.app ─────────────────────────────────────────
        print("\n🔵 [5] snapdouyin.app")
        try:
            r = await client.post(
                "https://snapdouyin.app/wp-json/aio-dl/video-data/",
                data={"url": TEST_URL},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            print(f"   Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                medias = data.get("medias", [])
                if medias:
                    print("   ✅ SUCCESS! url:", medias[0].get("url", "")[:80])
                else:
                    print("   ❌ FAIL  no medias:", str(data)[:200])
            else:
                print("   ❌ HTTP", r.status_code)
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # ── API 6: DouYinZj ───────────────────────────────────────────────
        print("\n🔵 [6] douyinzj.com (via POST)")
        try:
            r = await client.post(
                "https://douyinzj.com/api/v3/video",
                json={"url": TEST_URL},
                headers={"Content-Type": "application/json"}
            )
            print(f"   Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if data.get("video_no_wm"):
                    print("   ✅ SUCCESS! url:", data["video_no_wm"][:80])
                else:
                    print("   ❌ FAIL:", str(data)[:200])
            else:
                print("   ❌ HTTP", r.status_code, r.text[:100])
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

    print(f"\n{'='*60}")
    print("Done! API nào có ✅ thì dùng được.")
    print("Lưu ý: URL dạng 'jingxuan?modal_id=...' có thể không được")
    print("hỗ trợ - hãy thử dùng URL dạng https://v.douyin.com/xxxxx")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(test_all())
