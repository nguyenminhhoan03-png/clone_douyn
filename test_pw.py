import asyncio
from playwright.async_api import async_playwright

async def start_pw(idx):
    try:
        pw = await async_playwright().start()
        print(f"[{idx}] Started PW: {pw}")
        await asyncio.sleep(1)
        await pw.stop()
    except Exception as e:
        print(f"[{idx}] ERROR: '{e}' type: {type(e)}")

async def main():
    await asyncio.gather(
        start_pw(1),
        start_pw(2),
        start_pw(3)
    )

asyncio.run(main())
