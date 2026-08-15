import os
import subprocess
import time
import logging

logger = logging.getLogger(__name__)

class LDPlayerManager:
    """Quản lý các instance của LDPlayer thông qua ldconsole.exe"""
    
    def __init__(self, ldconsole_path=None):
        self.ldconsole = ldconsole_path or self._find_ldplayer()
        if not self.ldconsole or not os.path.exists(self.ldconsole):
            logger.warning("Không tìm thấy ldconsole.exe. Vui lòng cài đặt LDPlayer 9 hoặc tự truyền đường dẫn.")

    def _find_ldplayer(self):
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\\XuanZhi\\LDPlayer9")
            install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
            path = os.path.join(install_dir, "ldconsole.exe")
            if os.path.exists(path):
                return path
        except Exception:
            pass
            
        common_paths = [
            r"C:\\LDPlayer\\LDPlayer9\\ldconsole.exe",
            r"D:\\LDPlayer\\LDPlayer9\\ldconsole.exe",
            r"E:\\LDPlayer\\LDPlayer9\\ldconsole.exe",
            r"C:\\XuanZhi\\LDPlayer9\\ldconsole.exe",
            r"D:\\XuanZhi\\LDPlayer9\\ldconsole.exe"
        ]
        for p in common_paths:
            if os.path.exists(p): return p
        return r"C:\\LDPlayer\\LDPlayer9\\ldconsole.exe"

    def run_cmd(self, *args):
        """Chạy lệnh ldconsole"""
        cmd = [self.ldconsole] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Lỗi LDPlayer CMD: {' '.join(cmd)}\n{e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Lỗi hệ thống khi gọi LDPlayer: {e}")
            return None

    def randomize_device(self, index_or_name):
        """Tự động Fake thông số phần cứng (IMEI, MAC, Android ID) bằng lệnh của LDPlayer"""
        logger.info(f"Đang Fake thông số thiết bị cho LDPlayer {index_or_name}...")
        # Lệnh modify của LDPlayer hỗ trợ auto tạo chuỗi ngẫu nhiên
        return self.run_cmd(
            "modify", "--index", str(index_or_name),
            "--imei", "auto",
            "--imsi", "auto",
            "--simserial", "auto",
            "--androidid", "auto",
            "--mac", "auto",
            "--adb", "1"
        )

    def launch(self, index_or_name):
        """Mở một giả lập theo index hoặc name"""
        self.randomize_device(index_or_name)
        logger.info(f"Đang khởi động LDPlayer: {index_or_name}")
        return self.run_cmd("launch", "--index", str(index_or_name))

    def quit(self, index_or_name):
        """Tắt giả lập"""
        return self.run_cmd("quit", "--index", str(index_or_name))

    def quitall(self):
        """Tắt toàn bộ giả lập"""
        return self.run_cmd("quitall")

    def list2(self):
        """Lấy danh sách các giả lập và trạng thái. 
        Trả về list các dict chứa thông tin."""
        output = self.run_cmd("list2")
        if not output: return []
        
        instances = []
        for line in output.strip().split('\n'):
            parts = line.split(',')
            if len(parts) >= 7:
                instances.append({
                    "index": int(parts[0]),
                    "title": parts[1],
                    "top_window": parts[2],
                    "bind_window": parts[3],
                    "android_started": parts[4] == '1',
                    "pid": parts[5],
                    "pid_of_vbox": parts[6]
                })
        return instances

    def adb_command(self, index, command):
        """Gửi lệnh ADB trực tiếp tới giả lập thông qua ldconsole"""
        return self.run_cmd("adb", "--index", str(index), "--command", command)

    def wait_for_device(self, index, timeout=60):
        """Đợi giả lập khởi động xong hoàn toàn"""
        logger.info(f"Đang đợi LDPlayer {index} khởi động...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            instances = self.list2()
            for inst in instances:
                if inst["index"] == int(index) and inst["android_started"]:
                    logger.info(f"LDPlayer {index} đã sẵn sàng!")
                    return True
            time.sleep(2)
        logger.error(f"Timeout khi đợi LDPlayer {index} khởi động.")
        return False

    def get_adb_serial(self, index):
        """Lấy địa chỉ IP:Port của ADB cho giả lập này để uiautomator2 kết nối"""
        # LDPlayer mặc định mở cổng ADB 5555 cho index 0, 5557 cho index 1...
        port = 5555 + (int(index) * 2)
        return f"127.0.0.1:{port}"
