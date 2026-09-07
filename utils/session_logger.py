"""
Module quản lý nhật ký các phiên làm việc (Unified Session Logger).
Hỗ trợ tất cả các phân hệ: Crawl, Process, Upload, Farm, Auto Pipeline.
Lưu vết phiên độc lập, ghi file log theo thời gian thực và quản lý chỉ mục metadata.
"""
import os
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import BASE_DIR

LOGS_BASE_DIR = BASE_DIR / "logs"
SESSIONS_ROOT_DIR = LOGS_BASE_DIR / "sessions"
LEGACY_UPLOAD_DIR = LOGS_BASE_DIR / "upload_sessions"
INDEX_FILE = SESSIONS_ROOT_DIR / "sessions_index.json"

_lock = threading.Lock()

# Danh mục phân hệ chuẩn
MODULE_CONFIG = {
    "crawl": {
        "title": "Crawl Video",
        "icon": "🌐",
        "color": "#3B82F6",  # Blue
        "folder": "crawl",
    },
    "process": {
        "title": "Xử lý Video",
        "icon": "⚙️",
        "color": "#F59E0B",  # Orange
        "folder": "process",
    },
    "upload": {
        "title": "Upload Video",
        "icon": "📤",
        "color": "#8B5CF6",  # Purple
        "folder": "upload",
    },
    "farm": {
        "title": "Nuôi Nick (Farm)",
        "icon": "🌱",
        "color": "#10B981",  # Green
        "folder": "farm",
    },
    "auto": {
        "title": "Auto Pipeline",
        "icon": "🤖",
        "color": "#06B6D4",  # Cyan
        "folder": "auto",
    },
    "general": {
        "title": "Hệ thống",
        "icon": "📋",
        "color": "#64748B",  # Slate
        "folder": "general",
    },
}


class SessionLogManager:
    """Quản lý các phiên hoạt động và file logs cho toàn bộ ứng dụng."""

    @classmethod
    def ensure_dirs(cls):
        """Đảm bảo thư mục lưu log của các module tồn tại."""
        SESSIONS_ROOT_DIR.mkdir(parents=True, exist_ok=True)
        for mod, cfg in MODULE_CONFIG.items():
            (SESSIONS_ROOT_DIR / cfg["folder"]).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_logs_dir(cls, module: Optional[str] = None) -> Path:
        """Lấy đường dẫn thư mục log tương ứng."""
        cls.ensure_dirs()
        if module and module in MODULE_CONFIG:
            return SESSIONS_ROOT_DIR / MODULE_CONFIG[module]["folder"]
        return SESSIONS_ROOT_DIR

    @classmethod
    def _read_index(cls) -> List[Dict[str, Any]]:
        """Đọc danh sách chỉ mục phiên. Tự động đồng bộ các phiên cũ nếu có."""
        cls.ensure_dirs()
        sessions = []
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            except Exception:
                sessions = []

        # Tự động nạp các phiên cũ từ upload_sessions nếu chưa có trong index
        cls._import_legacy_upload_sessions(sessions)
        return sessions

    @classmethod
    def _write_index(cls, sessions: List[Dict[str, Any]]):
        """Ghi đè danh sách chỉ mục phiên."""
        cls.ensure_dirs()
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SessionLogManager] Lỗi ghi sessions_index.json: {e}")

    @classmethod
    def _import_legacy_upload_sessions(cls, current_sessions: List[Dict[str, Any]]):
        """Đồng bộ các phiên upload cũ trong logs/upload_sessions/ vào index chung."""
        legacy_index = LEGACY_UPLOAD_DIR / "sessions_index.json"
        if not legacy_index.exists():
            return

        existing_ids = {s.get("session_id") for s in current_sessions}
        modified = False

        try:
            with open(legacy_index, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            for item in legacy_data:
                sid = item.get("session_id")
                if sid and sid not in existing_ids:
                    # Chuyển đổi định dạng sang schema chuẩn của SessionLogManager
                    legacy_meta = {
                        "session_id": sid,
                        "module": "upload",
                        "title": f"Upload Video ({', '.join(item.get('platforms', ['TikTok']))})",
                        "start_time": item.get("start_time"),
                        "end_time": item.get("end_time"),
                        "duration_seconds": item.get("duration_seconds"),
                        "username": item.get("username", "default"),
                        "status": item.get("status", "SUCCESS"),
                        "summary": f"Thành công {item.get('success_count', 0)}/{item.get('total_videos', 0)} video",
                        "details": {
                            "platforms": item.get("platforms", []),
                            "total_videos": item.get("total_videos", 0),
                            "success_count": item.get("success_count", 0),
                            "fail_count": item.get("fail_count", 0),
                            "headless": item.get("headless", False),
                            "upload_threads": item.get("upload_threads", 3),
                        },
                        "log_file": str(LEGACY_UPLOAD_DIR / item.get("log_file", f"{sid}.log")),
                        "is_legacy": True,
                    }
                    current_sessions.append(legacy_meta)
                    existing_ids.add(sid)
                    modified = True
            if modified:
                # Sắp xếp theo start_time giảm dần
                current_sessions.sort(key=lambda x: str(x.get("start_time", "")), reverse=True)
                cls._write_index(current_sessions)
        except Exception:
            pass

    @classmethod
    def start_session(
        cls,
        module: str,
        title: str,
        username: str = "default",
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Bắt đầu một phiên ghi log mới cho bất kỳ phân hệ nào.
        Trả về session_id dạng: {module}_{YYYYMMDD}_{HHMMSS}
        """
        cls.ensure_dirs()
        mod = module if module in MODULE_CONFIG else "general"
        mod_info = MODULE_CONFIG[mod]

        now = datetime.now()
        session_id = now.strftime(f"{mod}_%Y%m%d_%H%M%S")
        mod_dir = SESSIONS_ROOT_DIR / mod_info["folder"]
        log_file = mod_dir / f"{session_id}.log"

        details_dict = details or {}
        details_str = "\n".join(f"  • {k}: {v}" for k, v in details_dict.items()) if details_dict else "  • Không có chi tiết bổ sung"

        header = (
            f"================================================================================\n"
            f"  {mod_info['icon']}  NHẬT KÝ PHIÊN: {mod_info['title'].upper()}\n"
            f"  Mã phiên: {session_id}\n"
            f"  Tiêu đề tác vụ: {title}\n"
            f"  Thời gian bắt đầu: {now.strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"  Người thực hiện: {username}\n"
            f"  Thông số cấu hình:\n{details_str}\n"
            f"================================================================================\n\n"
        )

        with _lock:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(header)

            index = cls._read_index()
            session_meta = {
                "session_id": session_id,
                "module": mod,
                "title": title,
                "start_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": None,
                "duration_seconds": None,
                "username": username,
                "status": "RUNNING",  # RUNNING | SUCCESS | WARNING | ERROR | CANCELLED
                "summary": "Đang thực hiện...",
                "details": details_dict,
                "log_file": str(log_file),
                "is_legacy": False,
            }
            index.insert(0, session_meta)
            cls._write_index(index)

        return session_id

    @classmethod
    def append_log(cls, module: str, session_id: str, message: str, level: str = "INFO"):
        """Ghi một dòng log vào file của phiên chỉ định."""
        if not session_id:
            return
        mod = module if module in MODULE_CONFIG else "general"
        mod_dir = SESSIONS_ROOT_DIR / MODULE_CONFIG[mod]["folder"]
        log_file = mod_dir / f"{session_id}.log"

        # Nếu không tìm thấy trong thư mục module, thử tìm trong legacy upload_sessions
        if not log_file.exists() and (LEGACY_UPLOAD_DIR / f"{session_id}.log").exists():
            log_file = LEGACY_UPLOAD_DIR / f"{session_id}.log"

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
        module: str,
        session_id: str,
        status: str = "SUCCESS",
        summary: str = "",
        details: Optional[Dict[str, Any]] = None,
        cancelled: bool = False,
    ):
        """Kết thúc một phiên và ghi tổng kết vào file log + index."""
        if not session_id:
            return
        cls.ensure_dirs()
        mod = module if module in MODULE_CONFIG else "general"
        mod_dir = SESSIONS_ROOT_DIR / MODULE_CONFIG[mod]["folder"]
        log_file = mod_dir / f"{session_id}.log"

        if not log_file.exists() and (LEGACY_UPLOAD_DIR / f"{session_id}.log").exists():
            log_file = LEGACY_UPLOAD_DIR / f"{session_id}.log"

        now = datetime.now()
        final_status = "CANCELLED" if cancelled else status

        with _lock:
            # Ghi footer vào log file
            footer = (
                f"\n================================================================================\n"
                f"  KẾT THÚC PHIÊN: {final_status}\n"
                f"  Thời gian kết thúc: {now.strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"  Tổng kết: {summary or 'Hoàn tất tác vụ.'}\n"
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
                    s["status"] = final_status
                    s["summary"] = summary or f"Trạng thái: {final_status}"
                    if details:
                        s["details"].update(details)

                    # Tính thời lượng
                    try:
                        start_dt = datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S")
                        s["duration_seconds"] = int((now - start_dt).total_seconds())
                    except Exception:
                        s["duration_seconds"] = None
                    break

            cls._write_index(index)

    @classmethod
    def get_sessions(
        cls,
        module: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lọc và lấy danh sách các phiên."""
        with _lock:
            sessions = cls._read_index()

        filtered = []
        search_lower = search.strip().lower() if search else None

        for s in sessions:
            if module and module != "all" and s.get("module") != module:
                continue
            if status and status != "all" and s.get("status") != status:
                continue
            if search_lower:
                text_to_search = (
                    f"{s.get('session_id', '')} {s.get('title', '')} "
                    f"{s.get('username', '')} {s.get('summary', '')} {s.get('start_time', '')}"
                ).lower()
                if search_lower not in text_to_search:
                    continue
            filtered.append(s)

        return filtered

    @classmethod
    def get_session_log(cls, session_id: str) -> str:
        """Đọc toàn bộ nội dung file log của một phiên."""
        index = cls._read_index()
        target_path = None
        for s in index:
            if s.get("session_id") == session_id:
                raw_path = s.get("log_file")
                if raw_path:
                    target_path = Path(raw_path)
                break

        if not target_path or not target_path.exists():
            # Thử tìm kiếm trong tất cả thư mục sessions
            for mod_cfg in MODULE_CONFIG.values():
                candidate = SESSIONS_ROOT_DIR / mod_cfg["folder"] / f"{session_id}.log"
                if candidate.exists():
                    target_path = candidate
                    break
            # Thử tìm kiếm trong legacy
            if not target_path or not target_path.exists():
                legacy_candidate = LEGACY_UPLOAD_DIR / f"{session_id}.log"
                if legacy_candidate.exists():
                    target_path = legacy_candidate

        if target_path and target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"[Lỗi đọc file log: {e}]"

        return f"[Không tìm thấy file log cho phiên {session_id}]"

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        """Xóa một phiên khỏi index và xóa file log tương ứng."""
        with _lock:
            index = cls._read_index()
            target_meta = None
            for s in index:
                if s.get("session_id") == session_id:
                    target_meta = s
                    break

            if not target_meta:
                return False

            index.remove(target_meta)
            cls._write_index(index)

            # Xóa file log
            raw_path = target_meta.get("log_file")
            if raw_path and Path(raw_path).exists():
                try:
                    Path(raw_path).unlink()
                except Exception:
                    pass

            return True
