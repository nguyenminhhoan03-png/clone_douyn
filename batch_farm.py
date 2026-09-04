import asyncio
import json
import argparse
import signal
import sys
from pathlib import Path
from loguru import logger
from uploader.tiktok_uploader import TikTokUploader

# Biến cờ ngắt toàn cục
cancel_requested = False

def handle_exit_signal(sig, frame):
    global cancel_requested
    if not cancel_requested:
        cancel_requested = True
        logger.warning("\n🛑 NHẬN ĐƯỢC TÍN HIỆU DỪNG (Ctrl+C). Đang đóng các trình duyệt an toàn...")
    else:
        logger.error("\n⚠️ Ép dừng khẩn cấp!")
        sys.exit(1)

signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)

async def main():
    global cancel_requested
    parser = argparse.ArgumentParser(description="Auto Farm/Nurture TikTok accounts on VPS (Headless)")
    parser.add_argument("--concurrency", type=int, default=2, help="Số lượng nick chạy song song cùng lúc (Mặc định: 2)")
    parser.add_argument("--flow", type=str, default=None, help="Tên hoặc ID kịch bản muốn chạy (Mặc định: Kịch bản đầu tiên)")
    args = parser.parse_args()

    # 1. Đọc danh sách Kịch bản (Flows)
    flows_path = Path("config/flows.json")
    if not flows_path.exists():
        logger.error("❌ Không tìm thấy file 'config/flows.json'! Vui lòng sync từ máy tính lên.")
        return
        
    try:
        with open(flows_path, "r", encoding="utf-8") as f:
            flows = json.load(f)
    except Exception as e:
        logger.error(f"❌ Lỗi đọc config/flows.json: {e}")
        return

    if not flows:
        logger.error("❌ Danh sách kịch bản trong config/flows.json đang trống!")
        return

    # Chọn kịch bản
    selected_flow = None
    if args.flow:
        selected_flow = next((f for f in flows if f.get("name") == args.flow or f.get("id") == args.flow), None)
        if not selected_flow:
            logger.warning(f"⚠️ Không tìm thấy kịch bản '{args.flow}', sẽ dùng kịch bản đầu tiên.")
            selected_flow = flows[0]
    else:
        selected_flow = flows[0]

    logger.info(f"🌱 KỊCH BẢN ĐÃ CHỌN: {selected_flow.get('name')} ({len(selected_flow.get('steps', []))} bước)")

    # 2. Tìm thư mục cookies của user
    cookies_base = Path("config/cookies")
    user_dirs = [d for d in cookies_base.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not user_dirs:
        logger.error("❌ Không tìm thấy thư mục cookies trong config/cookies!")
        return

    target_user_dir = None
    for d in user_dirs:
        if list(d.glob("tiktok_*.json")):
            target_user_dir = d
            break
            
    if not target_user_dir:
        if list(cookies_base.glob("tiktok_*.json")):
            target_user_dir = cookies_base
        else:
            target_user_dir = user_dirs[0]

    username = target_user_dir.name if target_user_dir != cookies_base else "default"
    cookie_files = sorted(list(target_user_dir.glob("tiktok_*.json")))
    if not cookie_files:
        logger.error(f"❌ Không có cookie tiktok_*.json nào trong {target_user_dir}!")
        return

    # 3. Đọc Proxy nếu có
    proxies = {}
    for p_file in [target_user_dir / "proxies.json", cookies_base / "proxies.json"]:
        if p_file.exists():
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    proxies.update(json.load(f))
            except Exception:
                pass

    # Chỉ nuôi các tài khoản có cấu hình Proxy trong proxies.json (tránh chạy IP thật của VPS hoặc nick rác)
    if proxies:
        cookie_files = [c for c in cookie_files if c.name in proxies or c.stem in proxies]

    logger.info(f"👥 Tìm thấy {len(cookie_files)} tài khoản TikTok hợp lệ trong '{target_user_dir.name}'.")
    logger.info(f"⚡ Chế độ chạy song song: {args.concurrency} tài khoản cùng lúc.\n")

    semaphore = asyncio.Semaphore(args.concurrency)
    active_uploaders = []

    async def _farm_account(cookie_path: Path, idx: int):
        async with semaphore:
            if cancel_requested:
                return
                
            acc_name = cookie_path.name
            short_name = cookie_path.stem.replace("tiktok_", "")
            proxy_str = proxies.get(acc_name) or proxies.get(cookie_path.stem)
            
            logger.info(f"\n{'='*50}\n🚀 [Nick {idx+1}/{len(cookie_files)}] Bắt đầu nuôi: {short_name}\nProxy: {proxy_str or 'Không dùng Proxy'}\n{'='*50}")
            
            uploader = TikTokUploader(
                cookies_file=str(cookie_path),
                proxy=proxy_str,
                username=username,
                window_idx=idx
            )
            active_uploaders.append(uploader)
            
            def log_callback(msg, lvl="INFO"):
                logger.info(f"[{short_name}] {msg}")
                
            try:
                await uploader.execute_farm_flow(
                    flow=selected_flow,
                    update_callback=log_callback,
                    cancel_check=lambda: cancel_requested
                )
            except Exception as e:
                if not cancel_requested:
                    logger.error(f"[{short_name}] ❌ Lỗi: {e}")
            finally:
                if uploader in active_uploaders:
                    active_uploaders.remove(uploader)
                await uploader.close()
                logger.info(f"[{short_name}] 🏁 Đã đóng trình duyệt.")

    try:
        tasks = [asyncio.create_task(_farm_account(cp, i)) for i, cp in enumerate(cookie_files)]
        while tasks:
            if cancel_requested:
                for t in tasks:
                    t.cancel()
                for u in active_uploaders:
                    try:
                        await u.close()
                    except: pass
                break
            # Chờ các task hoàn thành
            done, pending = await asyncio.wait(tasks, timeout=1)
            tasks = list(pending)
    except asyncio.CancelledError:
        pass
    finally:
        for u in active_uploaders:
            try: await u.close()
            except: pass

    if cancel_requested:
        logger.warning("\n⚠️ ĐÃ NGẮT TIẾN TRÌNH NUÔI NICK THEO YÊU CẦU.")
    else:
        logger.info("\n🎉 ĐÃ HOÀN THÀNH KỊCH BẢN NUÔI CHO TOÀN BỘ TÀI KHOẢN!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\n🛑 Đã dừng tiến trình.")
