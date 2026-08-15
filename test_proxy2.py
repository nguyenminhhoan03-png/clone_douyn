import asyncio
from uploader.tiktok_uploader import TikTokUploader

async def test():
    try:
        u = TikTokUploader(proxy='103.166.184.10:37361:Hoanphe1@:Hoanphe1@')
        await u._init_browser()
    except Exception as e:
        print(f"ERROR_REPR: {repr(e)}")
        print(f"ERROR_STR: {str(e)}")

asyncio.run(test())
