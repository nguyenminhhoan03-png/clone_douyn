"""
Module quản lý nhật ký các phiên Upload (Upload Session Logger).
Tự động lưu lại toàn bộ quá trình upload kèm thời gian, danh sách video,
tài khoản sử dụng và kết quả thành công/thất bại vào thư mục logs/upload_sessions/.
"""
import os
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import BASE_DIR

UPLOAD_LOGS_DIR = BASE_DIR / "logs" / "upload_sessions"
INDEX_FILE = UPLOAD_LOGS_DIR / "sessions_index.json"

_lock = threading.Lock()


class UploadLogManager:
    """Quản lý các phiên upload và file logs tương ứng."""

    @staticmethod
    def ensure_dir() -> Path:
        """Đảm bảo thư mục lưu log tồn tại."""
        UPLOAD_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return UPLOAD_LOGS_DIR

    @classmethod
    def start_session(
        cls,
        platforms: List[str],
        total_videos: int,
        headless: bool = False,
        upload_threads: int = 3,
        username: str = "default",
        accounts: Optional[List[str]] = None,
    ) -> str:
        """
        Bắt đầu một phiên upload mới.
        Trả về session_id dạng: upload_YYYYMMDD_HHMMSS
        """
        cls.ensure_dir()
        now = datetime.now()
        session_id = now.strftime("upload_%Y%m%d_%H%M%S")
        log_file = UPLOAD_LOGS_DIR / f"{session_id}.log"

        # Tạo file log kèm header rõ ràng
        header = (
            f"================================================================================\n"
            f"  NHẬT KÝ PHIÊN UPLOAD VIDEO (SESSION LOG)\n"
            f"  Mã phiên: {session_id}\n"
            f"  Thời gian bắt đầu: {now.strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"  Người dùng: {username}\n"
            f"  Nền tảng: {', '.join(platforms) if platforms else 'Chưa chọn'}\n"
            f"  Tổng số video: {total_videos}\n"
            f"  Số luồng đồng thời: {upload_threads}\n"
            f"  Chế độ trình duyệt TikTok: {'Ẩn ngầm (Headless)' if headless else 'Hiện trình duyệt'}\n"
            f"  Tài khoản sử dụng: {', '.join(accounts) if accounts else 'Theo phân bổ'}\n"
            f"================================================================================\n\n"
        )

        with _lock:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(header)

            # Cập nhật vào sessions_index.json
            index = cls._read_index()
            session_meta = {
                "session_id": session_id,
                "start_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": None,
                "duration_seconds": None,
                "username": username,
                "platforms": platforms,
                "total_videos": total_videos,
                "success_count": 0,
                "fail_count": 0,
                "status": "RUNNING",  # RUNNING | SUCCESS | WARNING | ERROR | CANCELLED
                "headless": headless,
                "upload_threads": upload_threads,
                "log_file": str(log_file.name),
            }
            index.insert(0, session_meta)
            cls._write_index(index)

        return session_id

    @classmethod
    def append_log(cls, session_id: str, message: str, level: str = "INFO"):
        """Ghi một dòng log vào file của phiên chỉ định."""
        if not session_id:
            return
        log_file = UPLOAD_LOGS_DIR / f"{session_id}.log"
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level:7s}] {message}\n"

        try:
            with _lock:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            pass

    @classmethod
    def finish_session(
        cls,
        session_id: str,
        success_count: int,
        fail_count: int,
        status: str = "SUCCESS",
        cancelled: bool = False,
    ):
        """Kết thúc một phiên upload và lưu tổng kết."""
        if not session_id:
            return
        cls.ensure_dir()
        log_file = UPLOAD_LOGS_DIR / f"{session_id}.log"
        now = datetime.now()

        if cancelled:
            final_status = "CANCELLED"
        elif fail_count > 0 and success_count > 0:
            final_status = "WARNING"
        elif fail_count > 0 and success_count == 0:
            final_status = "ERROR"
        else:
            final_status = "SUCCESS"

        with _lock:
            # Ghi footer vào log file
            footer = (
                f"\n================================================================================\n"
                f"  KẾT THÚC PHIÊN UPLOAD: {final_status}\n"
                f"  Thời gian kết thúc: {now.strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"  Thành công: {success_count} video\n"
                f"  Thất bại / Bỏ qua: {fail_count} video\n"
                f"================================================================================\n"
            )
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(footer)
            except Exception:
                pass

            # Cập nhật sessions_index.json
            index = cls._read_index()
            for s in index:
                if s.get("session_id") == session_id:
                    s["end_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    s["success_count"] = success_count
                    s["fail_count"] = fail_count
                    s["status"] = final_status
                    try:
                        st = datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S")
                        s["duration_seconds"] = int((now - st).total_seconds())
                    except Exception:
                        s["duration_seconds"] = None
                    break
            cls._write_index(index)

    @classmethod
    def get_sessions(cls) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả các phiên upload đã lưu, xếp mới nhất lên đầu."""
        cls.ensure_dir()
        with _lock:
            index = cls._read_index()
            # Kiểm tra xem file log có còn tồn tại không
            valid_sessions = []
            for s in index:
                f_name = s.get("log_file")
                if f_name and (UPLOAD_LOGS_DIR / f_name).exists():
                    valid_sessions.append(s)
            
            # Quét thêm những file .log chưa có trong index (nếu có)
            existing_ids = {s.get("session_id") for s in valid_sessions}
            for log_path in sorted(UPLOAD_LOGS_DIR.glob("upload_*.log"), reverse=True):
                sid = log_path.stem
                if sid not in existing_ids:
                    try:
                        mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
                        entry = {
                            "session_id": sid,
                            "start_time": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                            "end_time": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                            "duration_seconds": None,
                            "username": "unknown",
                            "platforms": ["Upload"],
                            "total_videos": 0,
                            "success_count": 0,
                            "fail_count": 0,
                            "status": "UNKNOWN",
                            "headless": False,
                            "upload_threads": 1,
                            "log_file": log_path.name,
                        }
                        valid_sessions.append(entry)
                    except Exception:
                        pass

            # Sắp xếp mới nhất lên đầu
            valid_sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
            return valid_sessions

    @classmethod
    def get_session_log(cls, session_id: str) -> str:
        """Đọc toàn bộ nội dung file log của 1 session."""
        log_file = UPLOAD_LOGS_DIR / f"{session_id}.log"
        if not log_file.exists():
            return f"Không tìm thấy file log: {log_file.name}"
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"Lỗi đọc file log: {e}"

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        """Xóa log và metadata của 1 session."""
        cls.ensure_dir()
        log_file = UPLOAD_LOGS_DIR / f"{session_id}.log"
        with _lock:
            if log_file.exists():
                try:
                    log_file.unlink()
                except Exception:
                    pass
            index = cls._read_index()
            new_index = [s for s in index if s.get("session_id") != session_id]
            cls._write_index(new_index)
        return True

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Lấy đường dẫn thư mục logs."""
        return cls.ensure_dir()

    @classmethod
    def _read_index(cls) -> List[Dict[str, Any]]:
        """Đọc file index."""
        if not INDEX_FILE.exists():
            return []
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @classmethod
    def _write_index(cls, data: List[Dict[str, Any]]):
        """Ghi dữ liệu vào file index (giữ tối đa 200 phiên gần nhất)."""
        cls.ensure_dir()
        try:
            trimmed = data[:200]
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(trimmed, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
