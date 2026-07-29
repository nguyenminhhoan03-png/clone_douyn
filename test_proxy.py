import asyncio
import sys
from loguru import logger

# Ép hiển thị trình duyệt
from config.settings import TIKTOK_CONFIG
TIKTOK_CONFIG["browser"]["headless"] = False

from uploader.tiktok_uploader import TikTokUploader

async def main():
    print("="*60)
    print("CÔNG CỤ THÊM TÀI KHOẢN MỚI & TEST PROXY (SẠCH 100%)")
    print("="*60)
    
    acc_name = input("1. Nhập tên tài khoản (Viết liền không dấu, VD: nick_1): ").strip()
    if not acc_name:
        acc_name = "test_acc"
        
    proxy = input("2. Nhập proxy (Ví dụ: 103.166.184.186:27910:user:pass) - Bấm Enter để bỏ qua: ").strip()
    
    # Tạo file cookie ảo để GUI nhận diện
    import os
    import json
    os.makedirs("config/cookies", exist_ok=True)
    cookie_file = f"config/cookies/{acc_name}.json"
    if not os.path.exists(cookie_file):
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump([], f)
    
    # Tạo uploader với profile vật lý
    uploader = TikTokUploader(cookies_file=cookie_file, proxy=proxy if proxy else None)
    
    print("\n[1] Đang khởi tạo trình duyệt ẩn danh với bộ chống phát hiện...")
    await uploader._init_browser()
    
    print("\n[2] Đang mở trang kiểm tra độ sạch (Pixelscan)...")
    await uploader.page.goto("https://pixelscan.net/", timeout=60000)
    
    print("\n[3] Đang mở thẻ mới cho TikTok...")
    tiktok_page = await uploader.context.new_page()
    await tiktok_page.goto("https://www.tiktok.com/", timeout=60000)
    
    print("\n" + "="*60)
    print("✅ TRÌNH DUYỆT ĐÃ ĐƯỢC MỞ!")
    print("- Thẻ 1: Xem IP và độ tin cậy của Proxy.")
    print("- Thẻ 2: Trang chủ TikTok để bạn tự do đăng nhập và lướt test.")
    print("="*60)
    print("⚠️ Bấm Ctrl + C ở cửa sổ này để đóng trình duyệt khi test xong.")
    print("="*60)
    
    try:
        # Treo trình duyệt để người dùng test
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nĐang đóng trình duyệt...")
        await uploader.close()
        print("Xong!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
