import asyncio
import random
import time
from loguru import logger
from core.ldplayer_manager import LDPlayerManager

class LDPlayerSeeder:
    """Engine xem Livestream TikTok tự động chạy trên giả lập LDPlayer + ADB"""
    
    def __init__(self, ld_index: int = 0, proxy: str = None):
        self.ld_index = ld_index
        self.proxy = proxy
        self.manager = LDPlayerManager()
        self.d = None # Thiết bị uiautomator2
        
        # Stats
        self.hearts_sent = 0
        self.comments_sent = 0
        self.is_watching = False

    async def _init_emulator(self):
        """Khởi động giả lập và kết nối uiautomator2"""
        try:
            import uiautomator2 as u2
        except ImportError:
            raise ImportError("Chưa cài uiautomator2! Hãy chạy: pip install uiautomator2")
            
        # 1. Bật giả lập
        self.manager.launch(self.ld_index)
        if not self.manager.wait_for_device(self.ld_index, timeout=60):
            raise Exception(f"Không thể khởi động LDPlayer số {self.ld_index}")
            
        # 2. Cài Proxy (nếu có)
        # Tạm thời bỏ qua bước cài Proxy bằng App. Ở mức độ đơn giản, 
        # ta dùng lệnh ADB settings (không ổn định 100% nhưng là cách nhanh nhất)
        if self.proxy:
            proxy_str = self.proxy.strip().replace("http://", "")
            # Chỉ hỗ trợ IP:Port qua lệnh settings. User/Pass phải dùng app Postern/SuperProxy.
            if len(proxy_str.split(":")) == 2:
                self.manager.adb_command(self.ld_index, f"settings put global http_proxy {proxy_str}")
                logger.info(f"[LDPlayer-{self.ld_index}] Đã set Global Proxy: {proxy_str}")
            else:
                logger.warning(f"[LDPlayer-{self.ld_index}] Proxy có User/Pass cần cài đặt qua App SuperProxy/Postern trên giả lập.")
        else:
            self.manager.adb_command(self.ld_index, "settings put global http_proxy :0")

        # 3. Kết nối uiautomator2 (Có Retry để chờ ADB boot xong)
        serial_ip = self.manager.get_adb_serial(self.ld_index) # VD: 127.0.0.1:5555
        serial_emu = f"emulator-{5554 + int(self.ld_index) * 2}" # VD: emulator-5554
        
        logger.info(f"Đang kết nối uiautomator2 tới {serial_ip} hoặc {serial_emu}...")
        
        # Gọi lệnh của LDPlayer để đảm bảo ADB Server nội bộ của giả lập đang chạy
        self.manager.run_cmd("adb", "--index", str(self.ld_index), "--command", "start-server")
        
        connected = False
        connected_serial = ""
        for i in range(5):
            for s in [serial_ip, serial_emu]:
                try:
                    self.d = u2.connect(s)
                    # Test connection
                    self.d.info
                    connected = True
                    connected_serial = s
                    break
                except Exception as e:
                    pass
            
            if connected:
                break
                
            logger.warning(f"Lần thử {i+1}/5: Chưa sẵn sàng. Đang đợi thêm 5s...")
            time.sleep(5)
                
        if not connected:
            raise Exception(f"Thiết bị (IP: {serial_ip} hoặc Tên: {serial_emu}) không online. Hãy đảm bảo đã bật 'ADB Debugging' (Kết nối nội bộ) trong Cài đặt LDPlayer.")
        else:
            logger.info(f"Đã kết nối thành công qua: {connected_serial}")
        
        # Đảm bảo thiết bị đã sẵn sàng
        self.d.wait_timeout = 30.0
        logger.info(f"🎭 [LDPlayer-{self.ld_index}] Sẵn sàng tự động hóa!")

    async def join_livestream(self, live_url: str, config: dict = None, update_callback=None, cancel_check=None):
        """Mở TikTok và vào phòng Live"""
        try:
            await self._init_emulator()
            self.is_watching = True
            
            if update_callback: update_callback(f"🔗 Đang vào phòng Live: {live_url}", "INFO")
            
            # Xử lý URL để lấy username hoặc room_id
            # Khởi động app TikTok trước để đảm bảo app sẵn sàng
            try:
                # Thử tìm package name của TikTok (Thường là com.ss.android.ugc.trill ở VN)
                pkgs = self.d.shell("pm list packages").output
                tiktok_pkg = "com.ss.android.ugc.trill" if "com.ss.android.ugc.trill" in pkgs else "com.zhiliaoapp.musically"
                self.d.app_start(tiktok_pkg)
                await asyncio.sleep(5)
            except Exception as e:
                logger.debug(f"Không thể khởi động trực tiếp bằng package name: {e}")
                
            # Dùng u2 shell với dạng list để tránh lỗi dính dấu ngoặc kép (quotes) của Windows/ldconsole
            self.d.shell(['am', 'start', '-a', 'android.intent.action.VIEW', '-d', live_url])
            
            # Đợi app mở và load video (khoảng 10s)
            await asyncio.sleep(10)
            
            if update_callback: update_callback("✅ Đã mở phòng Live trên Giả lập!", "SUCCESS")
            
            # Bắt đầu vòng lặp seeding
            await self._watching_loop(config or {}, update_callback, cancel_check)
            
            return True
        except Exception as e:
            logger.error(f"[LDPlayer-{self.ld_index}] Lỗi Seeding: {e}")
            if update_callback: update_callback(f"❌ Lỗi: {e}", "ERROR")
            return False
        finally:
            self.is_watching = False
            
    async def _watching_loop(self, cfg, update_callback, cancel_check):
        dur_val = cfg.get("duration_minutes", 15)
        dur = random.uniform(dur_val[0], dur_val[1]) if isinstance(dur_val, (tuple, list)) else float(dur_val)
        end_time = time.time() + (dur * 60)
        
        # Đợi ngẫu nhiên 1-3 phút trước khi bắt đầu tương tác (giống người thật xem live trước)
        initial_wait = random.uniform(60, 180)
        if update_callback: update_callback(f"👀 Đang xem im lặng {int(initial_wait)}s trước khi tương tác...", "INFO")
        
        # Lên lịch đơn giản, cộng thêm thời gian chờ ban đầu
        next_heart = time.time() + initial_wait + random.uniform(10, 30)
        next_comment = time.time() + initial_wait + random.uniform(60, 120)
        
        while time.time() < end_time:
            if cancel_check and cancel_check():
                break
                
            now = time.time()
            
            if now >= next_heart:
                await self._send_heart()
                self.hearts_sent += 1
                if update_callback: update_callback(f"❤️ Đã thả tim (lần {self.hearts_sent})", "SUCCESS")
                # Thả tim liên tục vài lần, hoặc ngắt quãng lâu hơn
                next_heart = now + random.uniform(15, 60)
                
            if now >= next_comment:
                comments = cfg.get("comments", ["Hay quá", "Xinh quá", "Tuyệt vời", "❤️❤️"])
                cmt = random.choice(comments)
                await self._send_comment(cmt)
                self.comments_sent += 1
                if update_callback: update_callback(f"💬 Đã bình luận: {cmt}", "SUCCESS")
                next_comment = now + random.uniform(120, 300)
                
            # Swipe up/down nhẹ để màn hình không bị tối (hoặc mô phỏng lướt chat)
            # Vuốt mượt hơn với tọa độ và thời gian ngẫu nhiên
            if random.random() < 0.15:
                w, h = self.d.window_size()
                start_x = w // 2 + random.randint(-50, 50)
                start_y = int(h * 0.6) + random.randint(-50, 50)
                end_x = start_x + random.randint(-20, 20)
                end_y = int(h * 0.4) + random.randint(-50, 50)
                duration = random.uniform(0.2, 0.6)
                self.d.swipe(start_x, start_y, end_x, end_y, duration) # Vuốt chat lên tự nhiên
                
            await asyncio.sleep(5)
            
    async def _send_heart(self):
        """Thả tim bằng cách nhấp đúp (Double tap) rải rác xung quanh tâm màn hình"""
        if not self.d: return
        w, h = self.d.window_size()
        
        # Randomize tọa độ click (tạo offset ngẫu nhiên từ tâm)
        center_x, center_y = w // 2, h // 2
        offset_x = random.randint(-150, 150)
        offset_y = random.randint(-200, 200)
        target_x = center_x + offset_x
        target_y = center_y + offset_y
        
        # Double click với thời gian ngẫu nhiên giữa 2 lần tap
        self.d.double_click(target_x, target_y, duration=random.uniform(0.05, 0.15))
        
        # Có thể tap thêm vài cái giống bị "cuốn" khi thả tim
        if random.random() < 0.5:
            extra_taps = random.randint(1, 4)
            for _ in range(extra_taps):
                await asyncio.sleep(random.uniform(0.1, 0.3))
                tap_x = target_x + random.randint(-30, 30)
                tap_y = target_y + random.randint(-30, 30)
                self.d.click(tap_x, tap_y)
            
    async def _send_comment(self, message):
        """Bình luận: Gõ từng ký tự giống người thật"""
        if not self.d: return
        
        try:
            input_box = self.d(resourceIdMatches=".*comment_edit_text.*") # Đoán ID
            w, h = self.d.window_size()
            if not input_box.exists:
                # Bấm theo toạ độ tương đối (Góc dưới cùng bên trái) với độ lệch ngẫu nhiên
                self.d.click(w * 0.2 + random.randint(-10, 10), h * 0.95 + random.randint(-10, 10))
            else:
                input_box.click()
                
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # Xóa text cũ nếu có (bằng cách clear thay vì bôi đen)
            self.d.clear_text()
            await asyncio.sleep(0.5)
            
            # Gõ từng ký tự với delay ngẫu nhiên
            for char in message:
                self.d.send_keys(char, clear=False)
                await asyncio.sleep(random.uniform(0.05, 0.2)) # Delay 50-200ms mỗi ký tự
                
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Bấm nút Gửi trên bàn phím ảo
            self.d.press("enter")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # Bấm ra ngoài màn hình để tắt bàn phím (tránh bấm nhầm vào livestream, bấm vào khu vực an toàn)
            self.d.click(w * 0.1, h * 0.4)
            
        except Exception as e:
            logger.debug(f"Lỗi comment LDPlayer: {e}")

    async def close(self):
        """Đóng giả lập khi xong việc (Tùy chọn)"""
        # Nếu muốn giữ giả lập mở để làm việc khác thì không gọi quit.
        # Ở đây ta tạm thời không quit để người dùng quan sát.
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
