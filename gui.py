"""
GUI Entry Point - Giao diện desktop cho Douyin Crawler & TikTok Auto-Uploader
Yêu cầu: pip install customtkinter
Chạy:    python gui.py
"""
import sys
import os
import re
import asyncio
import inspect
import threading
import shutil
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox

# ─── Project root vào sys.path ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ─── Theme ───────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Palette ─────────────────────────────────────────────────────────────────
BG_DARK      = "#0f1117"
BG_CARD      = "#1a1d27"
BG_SIDEBAR   = "#13151f"
ACCENT       = "#4f8ef7"
ACCENT_HOVER = "#6ba3ff"
SUCCESS      = "#2ecc71"
WARNING      = "#f39c12"
DANGER       = "#e74c3c"
TEXT_MAIN    = "#e8eaf6"
TEXT_DIM     = "#6c7293"
BORDER       = "#2a2d3e"


# ═══════════════════════════════════════════════════════════════════════════════
#  LogWidget — hiện log real-time
# ═══════════════════════════════════════════════════════════════════════════════
class LogWidget(ctk.CTkTextbox):
    """Textbox với màu log."""

    COLORS = {
        "INFO":    "#4f8ef7",
        "SUCCESS": "#2ecc71",
        "WARNING": "#f39c12",
        "ERROR":   "#e74c3c",
        "DEBUG":   "#6c7293",
    }

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            font=("Consolas", 12),
            text_color=TEXT_MAIN,
            fg_color=BG_DARK,
            border_color=BORDER,
            wrap="word",
            state="disabled",
            **kwargs,
        )
        # Cấu hình tags màu
        for tag, color in self.COLORS.items():
            self._textbox.tag_configure(tag, foreground=color)

    def append(self, message: str, level: str = "INFO"):
        ts  = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level:7s}] {message}\n"
        self.configure(state="normal")
        self._textbox.insert("end", line, level)
        self.configure(state="disabled")
        self._textbox.see("end")

    def clear(self):
        self.configure(state="normal")
        self.delete("0.0", "end")
        self.configure(state="disabled")


# ═══════════════════════════════════════════════════════════════════════════════
#  StatusBadge
# ═══════════════════════════════════════════════════════════════════════════════
class StatusBadge(ctk.CTkLabel):
    def __init__(self, master, text="Idle", color=TEXT_DIM, **kwargs):
        super().__init__(
            master,
            text=f"  ●  {text}  ",
            font=("Segoe UI", 11, "bold"),
            text_color=color,
            fg_color=BG_CARD,
            corner_radius=10,
            **kwargs,
        )

    def set(self, text, color):
        self.configure(text=f"  ●  {text}  ", text_color=color)


# ═══════════════════════════════════════════════════════════════════════════════
#  StatsCard
# ═══════════════════════════════════════════════════════════════════════════════
class StatsCard(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "0", color=ACCENT, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._lbl_value = ctk.CTkLabel(
            self, text=value,
            font=("Segoe UI", 28, "bold"),
            text_color=color,
        )
        self._lbl_value.grid(row=0, column=0, padx=16, pady=(16, 2))

        ctk.CTkLabel(
            self, text=label,
            font=("Segoe UI", 11),
            text_color=TEXT_DIM,
        ).grid(row=1, column=0, padx=16, pady=(2, 14))

    def set_value(self, v):
        self._lbl_value.configure(text=str(v))


# ═══════════════════════════════════════════════════════════════════════════════
#  SidebarButton
# ═══════════════════════════════════════════════════════════════════════════════
class SidebarButton(ctk.CTkButton):
    def __init__(self, master, icon: str, text: str, command=None, **kwargs):
        super().__init__(
            master,
            text=f"  {icon}  {text}",
            command=command,
            font=("Segoe UI", 14, "bold"),
            fg_color="transparent",
            text_color=TEXT_DIM,
            hover_color="#1E293B",
            anchor="w",
            height=48,
            corner_radius=12,
            **kwargs,
        )

    def set_active(self, active: bool):
        if active:
            self.configure(fg_color="#1E293B", text_color="#3B82F6")
        else:
            self.configure(fg_color="transparent", text_color=TEXT_DIM)


# ═══════════════════════════════════════════════════════════════════════════════
#  Mixin: chạy task trên thread nền, route log về queue
# ═══════════════════════════════════════════════════════════════════════════════
class TaskMixin:
    """Mixin cho các Tab cần chạy lệnh Python nền."""

    def __init__(self, *args, **kwargs):
        # We don't always call super().__init__ in mixins, but let's just initialize the flag
        self.cancel_flag = False

    def _run_in_thread(self, func, *args, **kwargs):
        """Chạy coroutine hoặc hàm sync trên thread riêng."""
        self.cancel_flag = False
        def _worker():
            try:
                if inspect.iscoroutinefunction(func):
                    asyncio.run(func(*args, **kwargs))
                else:
                    func(*args, **kwargs)
            except Exception as e:
                self._log(f"Lỗi: {e}", "ERROR")
            finally:
                self._on_task_done()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _cancel_task(self):
        """Yêu cầu dừng task."""
        self.cancel_flag = True
        self._log("Đang yêu cầu dừng tiến trình...", "WARNING")

    def _log(self, msg: str, level: str = "INFO"):
        """Ghi log (gọi được từ thread bất kỳ)."""
        # Mỗi tab phải bind self._log_widget
        self.after(0, lambda: self._log_widget.append(msg, level))

    def _on_task_done(self):
        """Gọi sau khi task xong."""
        self.cancel_flag = False


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Dashboard
# ═══════════════════════════════════════════════════════════════════════════════
class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=4, sticky="ew", padx=4, pady=(0, 20))
        ctk.CTkLabel(
            hdr, text="🎬  Dashboard",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(side="left")

        btn_refresh = ctk.CTkButton(
            hdr, text="⟳  Refresh", width=110, height=34,
            font=("Segoe UI", 12), command=self.refresh_stats,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        )
        btn_refresh.pack(side="right")

        # Stats cards - Account
        self._card_plan = StatsCard(self, "Gói Cước", value="Free", color="#3498db")
        self._card_limit = StatsCard(self, "Giới Hạn / Ngày", value="0", color="#e67e22")
        self._card_used = StatsCard(self, "Đã Dùng", value="0", color="#e74c3c")
        self._card_rem = StatsCard(self, "Còn Lại", value="0", color="#2ecc71")
        
        for col, card in enumerate([self._card_plan, self._card_limit, self._card_used, self._card_rem]):
            card.grid(row=1, column=col, padx=6, pady=4, sticky="ew")

        # Stats cards - Local
        self._card_crawled   = StatsCard(self, "Đã Crawl",   color=ACCENT)
        self._card_processed = StatsCard(self, "Đã Xử lý",   color="#9b59b6")
        self._card_posted    = StatsCard(self, "Đã Upload",   color=SUCCESS)
        self._card_pending   = StatsCard(self, "Chờ Upload",  color=WARNING)

        for col, card in enumerate([
            self._card_crawled, self._card_processed,
            self._card_posted, self._card_pending
        ]):
            card.grid(row=2, column=col, padx=6, pady=4, sticky="ew")

        # Recent activity log
        log_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        log_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=4, pady=(20, 0))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            log_frame, text="📋  Activity Log",
            font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self._log_widget = LogWidget(log_frame)
        self._log_widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._log_widget.append("Chào mừng! Hệ thống sẽ tự động cập nhật thống kê...", "INFO")
        
        # Tự động tải số liệu lần đầu
        self.after(500, self.refresh_stats)
        # Tự động refresh mỗi 15 giây
        self.after(15000, self._auto_refresh)

    def _auto_refresh(self):
        """Loop auto refresh stats."""
        try:
            self.refresh_stats(silent=True)
        except Exception:
            pass
        finally:
            self.after(15000, self._auto_refresh)

    def refresh_stats(self, silent=False):
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            
            from auth_client import auth_client
            current_user = auth_client.user_info.get("username") if auth_client.user_info else None
            
            s  = db.get_stats(username=current_user)
            self._card_crawled.set_value(s.get("total_crawled", 0))
            self._card_processed.set_value(s.get("total_processed", 0))
            self._card_posted.set_value(s.get("total_posted", 0))
            self._card_pending.set_value(s.get("pending_post", 0))
            
            # Fetch Account Info
            from auth_client import auth_client
            success, _ = auth_client.get_me()
            if success and auth_client.user_info:
                self._card_plan.set_value(auth_client.user_info.get("plan_name", "Free"))
                limit = auth_client.user_info.get("max_daily_videos", 0)
                limit_str = "∞" if limit > 1000 else str(limit)
                self._card_limit.set_value(limit_str)
                self._card_used.set_value(auth_client.user_info.get("used_today", 0))
                
                rem = auth_client.user_info.get("remaining", 0)
                rem_str = "∞" if limit > 1000 else str(rem)
                self._card_rem.set_value(rem_str)
                
            if not silent:
                self._log_widget.append("Stats đã được cập nhật.", "SUCCESS")
        except Exception as e:
            if not silent:
                self._log_widget.append(f"Không thể tải stats: {e}", "WARNING")


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Crawl
# ═══════════════════════════════════════════════════════════════════════════════
class CrawlTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build()

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="🔍  Crawl Video từ Douyin",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Input card
        self._input_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._input_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self._input_card.grid_columnconfigure(1, weight=1)
        self._input_card.grid_columnconfigure(0, minsize=120) # Cố định chiều rộng cột nhãn

        # Mode chọn
        ctk.CTkLabel(self._input_card, text="Chế độ:", font=("Segoe UI", 12, "bold"),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 10))

        self._mode_var = ctk.StringVar(value="urls")
        mode_frame = ctk.CTkFrame(self._input_card, fg_color="transparent")
        mode_frame.grid(row=0, column=1, sticky="w", padx=0, pady=(16, 10))
        for val, lbl in [("urls", "URL cụ thể"), ("profile", "Profile user"), ("file", "File URLs")]:
            ctk.CTkRadioButton(
                mode_frame, text=lbl, variable=self._mode_var, value=val,
                command=self._on_mode_change,
                font=("Segoe UI", 12), text_color=TEXT_MAIN,
            ).pack(side="left", padx=(0, 20))

        ctk.CTkFrame(self._input_card, height=1, fg_color=BORDER).grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=5) # Divider

        # --- ROW 2: URLs ---
        self._frame_urls = ctk.CTkFrame(self._input_card, fg_color="transparent")
        self._frame_urls.grid_columnconfigure(1, weight=1)
        self._frame_urls.grid_columnconfigure(0, minsize=120)
        
        ctk.CTkLabel(self._frame_urls, text="Douyin URLs:", font=("Segoe UI", 12, "bold"),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="nw", padx=16, pady=4)

        url_inner = ctk.CTkFrame(self._frame_urls, fg_color="transparent")
        url_inner.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=4)
        url_inner.grid_columnconfigure(0, weight=1)

        self._txt_urls = ctk.CTkTextbox(url_inner, height=120, font=("Consolas", 12), fg_color=BG_DARK, border_color=BORDER)
        self._txt_urls.grid(row=0, column=0, sticky="ew")
        self._txt_urls.insert("0.0", "# Paste URL hoặc cả đoạn text từ app Douyin đều được\n# VD: 5.33 07/15 ... https://v.douyin.com/K_UlIwJrDJY/\n# Tool sẽ tự trích xuất URL ra\n")
        ctk.CTkLabel(url_inner, text="💡 Mỗi dòng 1 URL — Hỗ trợ: v.douyin.com | www.douyin.com/video/", font=("Segoe UI", 10, "italic"), text_color=TEXT_DIM, anchor="w").grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # --- ROW 3: Profile ---
        self._frame_profile = ctk.CTkFrame(self._input_card, fg_color="transparent")
        self._frame_profile.grid_columnconfigure(1, weight=1)
        self._frame_profile.grid_columnconfigure(0, minsize=120)

        ctk.CTkLabel(self._frame_profile, text="Profile URL:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=4)
        self._entry_profile = ctk.CTkEntry(self._frame_profile, placeholder_text="https://www.douyin.com/user/...", font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._entry_profile.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=4)

        ctk.CTkLabel(self._frame_profile, text="Số lượng:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self._spin_count = ctk.CTkEntry(self._frame_profile, width=80, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._spin_count.insert(0, "10")
        self._spin_count.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=4)
        
        # --- ROW 4: File ---
        self._frame_file = ctk.CTkFrame(self._input_card, fg_color="transparent")
        self._frame_file.grid_columnconfigure(1, weight=1)
        self._frame_file.grid_columnconfigure(0, minsize=120)

        ctk.CTkLabel(self._frame_file, text="File URLs:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=4)
        
        file_inner = ctk.CTkFrame(self._frame_file, fg_color="transparent")
        file_inner.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=4)
        file_inner.grid_columnconfigure(0, weight=1)
        self._entry_file = ctk.CTkEntry(file_inner, placeholder_text="C:\\path\\to\\urls.txt", font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._entry_file.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(file_inner, text="📁 Chọn", width=90, height=30, font=("Segoe UI", 11, "bold"), fg_color=BORDER, hover_color=BG_CARD, command=self._browse_file).grid(row=0, column=1, padx=(8, 0))

        # --- Buttons ---
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self._btn_crawl = ctk.CTkButton(btn_row, text="▶  Bắt đầu Crawl", height=42, width=150, font=("Segoe UI", 14, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._start_crawl)
        self._btn_crawl.pack(side="left", padx=(0, 15))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(side="left")

        # Log
        self._log_widget = LogWidget(self)
        self._log_widget.grid(row=3, column=0, sticky="nsew")

        self._on_mode_change()

    def _on_mode_change(self):
        mode = self._mode_var.get()
        # Hide all
        self._frame_urls.grid_remove()
        self._frame_profile.grid_remove()
        self._frame_file.grid_remove()
        
        # Show specific
        if mode == "urls":
            self._frame_urls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 16))
        elif mode == "profile":
            self._frame_profile.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 16))
        elif mode == "file":
            self._frame_file.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 16))

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Chọn file URLs",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=str(Path(__file__).parent),
        )
        if path:
            self._entry_file.delete(0, "end")
            self._entry_file.insert(0, path)

    # ── Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_douyin_urls(raw_text: str) -> list[str]:
        """
        Trích xuất tất cả Douyin URL từ đoạn text bất kỳ.
        Hỗ trợ:
          - https://v.douyin.com/xxxxx/
          - https://www.douyin.com/video/123456
          - https://www.douyin.com/jingxuan?modal_id=123456
          - Paste cả đoạn text chia sẻ từ app Douyin
        """
        pattern = r'https?://(?:v\.douyin\.com/[A-Za-z0-9_\-/]+|(?:www\.)?douyin\.com/(?:video/\d+|[^\s]+?modal_id=\d+|user/[A-Za-z0-9_\-]+))'
        found = re.findall(pattern, raw_text)
        # Loại bỏ trùng lặp, giữ thứ tự
        seen, result = set(), []
        for u in found:
            u = u.rstrip('/')
            if u not in seen:
                seen.add(u)
                result.append(u)
        return result

    def _start_crawl(self):
        self._btn_crawl.configure(state="disabled")
        self._status_badge.set("Đang crawl...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu crawl...", "INFO")

        mode  = self._mode_var.get()
        count = int(self._spin_count.get() or 10)

        if mode == "urls":
            raw_text = self._txt_urls.get("0.0", "end")
            # Tự động trích xuất URL từ text paste (kể cả text từ app Douyin)
            urls = self._extract_douyin_urls(raw_text)
            if not urls:
                self._log("❌ Không tìm thấy URL Douyin nào! Hãy paste URL vào ô trên.", "ERROR")
                self._on_task_done()
                return
            self._log(f"🔗 Tìm thấy {len(urls)} URL:", "INFO")
            for u in urls:
                self._log(f"   → {u}", "INFO")
            self._run_in_thread(self._do_crawl_urls, urls)
        elif mode == "profile":
            profile = self._entry_profile.get().strip()
            self._run_in_thread(self._do_crawl_profile, profile, count)
        else:
            file_path = self._entry_file.get().strip() or "urls.txt"
            self._run_in_thread(self._do_crawl_file, file_path)

    def _do_crawl_urls(self, urls):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        crawler.current_username = auth_client.user_info.get("username") if auth_client.user_info else None
        self._log(f"Crawling {len(urls)} URLs...", "INFO")
        results = asyncio.run(crawler.crawl_multiple_videos(urls))
        self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")

    def _do_crawl_profile(self, profile, count):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        crawler.current_username = auth_client.user_info.get("username") if auth_client.user_info else None
        self._log(f"Crawling profile ({count} videos)...", "INFO")
        results = asyncio.run(crawler.crawl_user_profile(profile, max_videos=count))
        self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")

    def _do_crawl_file(self, file_path):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        urls = Path(file_path).read_text(encoding="utf-8").strip().splitlines()
        urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        crawler.current_username = auth_client.user_info.get("username") if auth_client.user_info else None
        self._log(f"Crawling {len(urls)} URLs from {file_path}...", "INFO")
        results = asyncio.run(crawler.crawl_multiple_videos(urls))
        self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")

    def _on_task_done(self):
        self.after(0, lambda: self._btn_crawl.configure(state="normal"))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS))


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Process
# ═══════════════════════════════════════════════════════════════════════════════
class ProcessTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._checkboxes = {} # Lưu trạng thái {video_id: BooleanVar}
        self._selected_music_path = None
        self._build()
        self.after(200, self._load_videos) # Load video khi tab mở

    def _build(self):
        ctk.CTkLabel(
            self, text="🎞️  Xử lý Video",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # Khởi tạo 2 cột (Trái: Danh sách, Phải: Sidebar công cụ)
        self.grid_columnconfigure(0, weight=5) # 5 phần cho danh sách
        self.grid_columnconfigure(1, weight=4) # 4 phần cho sidebar (rộng hơn một chút để chứa đủ text)
        self.grid_rowconfigure(1, weight=1)

        # --- LEFT PANE ---
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 15))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        list_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(list_header, text="Danh sách Video đã tải:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        
        ctk.CTkButton(list_header, text="🔄 Refresh", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._load_videos).pack(side="right")
        ctk.CTkButton(list_header, text="🗑 Xóa", width=60, height=24, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_selected).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="☑ Chọn", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._toggle_selection).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="📥 Import Video", width=100, height=24, fg_color=SUCCESS, hover_color="#27ae60", command=self._import_local_video).pack(side="right", padx=(0, 10))
        
        self._video_list_frame = ctk.CTkScrollableFrame(left_frame, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._video_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

        self._log_widget = LogWidget(left_frame, height=120)
        self._log_widget.grid(row=2, column=0, sticky="nsew")

        # --- RIGHT PANE (SIDEBAR) ---
        right_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        right_frame.grid(row=1, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        # Options card
        opts = ctk.CTkFrame(right_frame, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        opts.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(opts, text="Title overlay", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        self._entry_title = ctk.CTkEntry(
            opts, placeholder_text="Để trống = Dịch tự động",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_title.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(14, 4))

        # Limit
        ctk.CTkLabel(opts, text="Số lượng", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self._entry_limit = ctk.CTkEntry(
            opts, width=80, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_limit.insert(0, "10")
        self._entry_limit.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(4, 14))

        # Cấu hình xếp dọc theo Sidebar
        config_frame = ctk.CTkFrame(opts, fg_color="transparent")
        config_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

        # --- Hình ảnh & Âm thanh ---
        ctk.CTkLabel(config_frame, text="Hiệu ứng cơ bản", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))

        self._sw_mirror = ctk.CTkSwitch(row1, text="Mirror (Lật video)", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_mirror.select()
        self._sw_mirror.pack(anchor="w", pady=(0, 10))

        self._sw_music = ctk.CTkSwitch(row1, text="Ghép nhạc nền", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_music.select()
        self._sw_music.pack(anchor="w", pady=(0, 10))

        music_tools = ctk.CTkFrame(row1, fg_color="transparent")
        music_tools.pack(fill="x")
        self._btn_open_music = ctk.CTkButton(music_tools, text="🎵 Chọn...", width=70, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._select_music_file)
        self._btn_open_music.pack(side="left", padx=(0, 10))
        self._lbl_music_file = ctk.CTkLabel(music_tools, text="(Mặc định)", font=("Segoe UI", 11), text_color=TEXT_DIM)
        self._lbl_music_file.pack(side="left")
        
        vol_frame = ctk.CTkFrame(row1, fg_color="transparent")
        vol_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(vol_frame, text="Âm lượng gốc:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_bg_vol = ctk.CTkEntry(vol_frame, width=45, placeholder_text="15%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_bg_vol.insert(0, "15%")
        self._entry_bg_vol.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Xử lý Chữ & Vietsub ---
        ctk.CTkLabel(config_frame, text="Subtitles & Blur", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))

        # --- Chế độ Tùy chỉnh Cao cấp ---
        sub_frame = ctk.CTkFrame(row2, fg_color="transparent")
        sub_frame.pack(fill="x", pady=(0, 10))
        self._sw_subtitle = ctk.CTkSwitch(sub_frame, text="Auto-Vietsub", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_subtitle.select()
        self._sw_subtitle.pack(side="left")
        
        self._opt_sub_pos = ctk.CTkOptionMenu(
            sub_frame, values=["Đè lên vùng mờ", "Cao (Tránh TikTok UI)", "Giữa màn hình"], 
            width=130, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_sub_pos.set("Đè lên vùng mờ")
        self._opt_sub_pos.pack(side="left", padx=(10, 0))

        self._sw_blur = ctk.CTkSwitch(row2, text="Làm mờ phụ đề gốc", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_blur.select()
        self._sw_blur.pack(anchor="w", pady=(0, 10))

        blur_tools = ctk.CTkFrame(row2, fg_color="transparent")
        blur_tools.pack(fill="x")
        ctk.CTkLabel(blur_tools, text="Vùng làm mờ:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_blur_height = ctk.CTkEntry(blur_tools, width=45, placeholder_text="15%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_blur_height.insert(0, "15%")
        self._entry_blur_height.pack(side="left", padx=(0, 10))
        
        self._opt_blur_pos = ctk.CTkOptionMenu(blur_tools, values=["Dưới cùng", "Trên cùng"], width=100, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD)
        self._opt_blur_pos.set("Dưới cùng")
        self._opt_blur_pos.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Thuyết minh AI ---
        ctk.CTkLabel(config_frame, text="Voiceover AI", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        row3 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 12))

        self._sw_dubbing = ctk.CTkSwitch(row3, text="Thuyết minh AI", font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_dubbing.select()
        self._sw_dubbing.pack(anchor="w", pady=(0, 10))
        
        ai_mode_frame = ctk.CTkFrame(row3, fg_color="transparent")
        ai_mode_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(ai_mode_frame, text="Chế độ:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._opt_ai_mode = ctk.CTkOptionMenu(
            ai_mode_frame, 
            values=["Thuyết minh nguyên bản", "Tóm tắt Review Phim"], 
            width=180, font=("Segoe UI", 11, "bold"), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_ai_mode.set("Thuyết minh nguyên bản")
        self._opt_ai_mode.pack(side="left")

        voice_tools = ctk.CTkFrame(row3, fg_color="transparent")
        voice_tools.pack(fill="x")
        self._opt_voice = ctk.CTkOptionMenu(
            voice_tools, 
            values=["Giọng Nam", "Giọng Nữ", "Đa giọng (Đoản kịch)"], 
            width=140, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_voice.set("Giọng Nữ")
        self._opt_voice.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(voice_tools, text="Tốc độ:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_tts_rate = ctk.CTkEntry(voice_tools, width=45, placeholder_text="0%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_tts_rate.insert(0, "0%")
        self._entry_tts_rate.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Nền tảng xuất ---
        ctk.CTkLabel(config_frame, text="🎯 Nền tảng đích", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        row4 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row4.pack(fill="x")

        self._opt_platform = ctk.CTkOptionMenu(
            row4, values=["TikTok", "YouTube (Bypass ID)"],
            width=180, font=("Segoe UI", 11, "bold"), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD,
            command=self._on_platform_change
        )
        self._opt_platform.set("TikTok")
        self._opt_platform.pack(anchor="w", pady=(0, 15))

        self._yt_frame = ctk.CTkFrame(row4, fg_color="transparent")
        
        self._btn_open_logo = ctk.CTkButton(
            self._yt_frame, text="🖼️ Chọn Logo...", width=120, height=24,
            fg_color=BORDER, hover_color=BG_CARD, command=self._select_logo_file
        )
        self._btn_open_logo.pack(anchor="w", pady=(0, 10))

        self._lbl_logo_file = ctk.CTkLabel(self._yt_frame, text="(Chưa chọn)", font=("Segoe UI", 11), text_color=TEXT_DIM)
        self._lbl_logo_file.pack(anchor="w", pady=(0, 10))

        self._opt_logo_pos = ctk.CTkOptionMenu(
            self._yt_frame, values=["Góc trên phải", "Góc trên trái", "Góc dưới trái", "Góc dưới phải", "Di chuyển"],
            width=130, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_logo_pos.set("Góc trên phải")
        self._opt_logo_pos.pack(anchor="w", pady=(0, 10))

        self._sw_yt_crop = ctk.CTkSwitch(self._yt_frame, text="Crop Zoom 15%", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_yt_crop.select()
        self._sw_yt_crop.pack(anchor="w", pady=(0, 10))

        self._sw_yt_noise = ctk.CTkSwitch(self._yt_frame, text="Nhiễu hạt (Noise)", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_yt_noise.select()
        self._sw_yt_noise.pack(anchor="w")
        
        # Buttons
        btn_row = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._btn_process = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Xử lý", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#9b59b6", hover_color="#8e44ad",
            command=self._start_process,
        )
        self._btn_process.pack(fill="x", pady=(0, 10))

        self._btn_bypass = ctk.CTkButton(
            btn_row, text="⏩ Chuyển thẳng Upload", height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._bypass_process,
        )
        self._btn_bypass.pack(fill="x", pady=(0, 10))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(anchor="center")

    def _load_videos(self):
        """Hiển thị danh sách video đã tải vào scrollable frame."""
        # Xóa các checkbox cũ
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()

        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username") if auth_client.user_info else None
        
        # Lấy 100 video tải gần nhất để hiển thị
        videos = db.get_downloaded_videos(limit=100, username=current_user)
        
        if not videos:
            ctk.CTkLabel(self._video_list_frame, text="Không có video nào đang chờ xử lý.", text_color=TEXT_DIM).pack(pady=20)
            return

        for video in videos:
            vid = video["video_id"]
            title = video.get("title") or "No title"
            
            # Khung chứa 1 video (Card)
            card = ctk.CTkFrame(self._video_list_frame, fg_color=BG_CARD, corner_radius=8,
                                 border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=4, padx=10)
            
            var = ctk.BooleanVar(value=True) # Mặc định chọn tất cả
            self._checkboxes[vid] = var
            
            # Checkbox bên trái
            cb = ctk.CTkCheckBox(
                card, text="", variable=var, width=24
            )
            cb.pack(side="left", padx=(10, 0), pady=10)
            
            # Action buttons (pack bên phải trước để không bị đẩy mất bởi text dài)
            action_frame = ctk.CTkFrame(card, fg_color="transparent")
            action_frame.pack(side="right", padx=10, pady=8)
            
            path = video.get("download_path")
            if path:
                import os
                if os.path.exists(path):
                    ctk.CTkButton(
                        action_frame, text="▶ Xem", width=60, font=("Segoe UI", 11),
                        fg_color=BORDER, hover_color=BG_CARD,
                        command=lambda p=path: os.startfile(p) if os.name == 'nt' else None
                    ).pack(side="left")

            # Thông tin video (pack sau action_frame, expand=True)
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)
            
            ctk.CTkLabel(info_frame, text=f"ID: {vid}", font=("Consolas", 11, "bold"), text_color=ACCENT).pack(anchor="w")
            ctk.CTkLabel(info_frame, text=title[:80] + ("..." if len(title) > 80 else ""), 
                         font=("Segoe UI", 13), text_color=TEXT_MAIN).pack(anchor="w", pady=(2, 0))
            
            # Kiểm tra dung lượng
            size_mb = 0
            if path:
                import os
                if os.path.exists(path):
                    size_mb = os.path.getsize(path) / (1024 * 1024)
            ctk.CTkLabel(info_frame, text=f"📦 {size_mb:.1f} MB (Chưa xử lý)", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))
            
    def _delete_selected(self):
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_ids:
            self._log("Vui lòng chọn video để xóa!", "WARNING")
            return
            
        if not messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa {len(selected_ids)} video này không? Thao tác này sẽ xóa vĩnh viễn cả file gốc."):
            return
            
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        deleted = 0
        for vid in selected_ids:
            if db.delete_video_data(vid):
                deleted += 1
                
        self._log(f"Đã xóa vĩnh viễn {deleted} video (gồm cả file gốc).", "SUCCESS")
        self._load_videos()

    def _import_local_video(self):
        file_paths = filedialog.askopenfilenames(
            title="Chọn Video (.mp4)",
            filetypes=[("Video files", "*.mp4"), ("All files", "*.*")]
        )
        if not file_paths:
            return
            
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        import shutil
        import uuid
        import subprocess
        
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username") if auth_client.user_info else None
        
        # Thư mục lưu trữ video cục bộ
        local_dir = Path("downloads/local")
        local_dir.mkdir(parents=True, exist_ok=True)
        
        imported_count = 0
        for path_str in file_paths:
            path = Path(path_str)
            if not path.exists():
                continue
                
            # Copy file vào workspace
            vid_id = f"local_{uuid.uuid4().hex[:8]}"
            dest_path = local_dir / f"{vid_id}.mp4"
            try:
                shutil.copy2(path, dest_path)
                
                # Lấy duration (dùng ffprobe qua subprocess đơn giản)
                duration = 0.0
                try:
                    res = subprocess.run([
                        "ffprobe", "-v", "error", "-show_entries", "format=duration", 
                        "-of", "default=noprint_wrappers=1:nokey=1", str(dest_path)
                    ], capture_output=True, text=True)
                    duration = float(res.stdout.strip())
                except:
                    pass
                
                db.add_crawled_video(
                    video_id=vid_id,
                    source_url="local",
                    title=f"[Local] {path.name}",
                    author="Bản thân",
                    music_title="Nhạc gốc",
                    tags="#local",
                    download_path=str(dest_path),
                    duration=duration,
                    username=current_user
                )
                db.update_video_status(vid_id, "downloaded")
                imported_count += 1
            except Exception as e:
                self._log(f"Lỗi import {path.name}: {e}", "WARNING")
                
        if imported_count > 0:
            self._log(f"✅ Đã import thành công {imported_count} video cục bộ!", "SUCCESS")
            self._load_videos()

    def _toggle_selection(self):
        if not self._checkboxes:
            return
        all_checked = all(var.get() for var in self._checkboxes.values())
        new_state = not all_checked
        for var in self._checkboxes.values():
            var.set(new_state)

    def _select_music_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file nhạc mp3/m4a",
            filetypes=[("Audio files", "*.mp3 *.m4a"), ("All files", "*.*")]
        )
        if file_path:
            self._selected_music_path = file_path
            name = Path(file_path).name
            self._lbl_music_file.configure(text=name[:15] + "...")
            self._sw_music.select()
        else:
            self._selected_music_path = None
            self._lbl_music_file.configure(text="")

    def _select_logo_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file Logo PNG/JPG",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        )
        if file_path:
            self._selected_logo_path = file_path
            name = Path(file_path).name
            self._lbl_logo_file.configure(text=name[:15] + "...")
        else:
            self._selected_logo_path = None
            self._lbl_logo_file.configure(text="(Chưa chọn logo)")

    def _on_platform_change(self, choice=None):
        if "YouTube" in self._opt_platform.get():
            self._yt_frame.pack(side="left")
        else:
            self._yt_frame.pack_forget()

    def _bypass_process(self):
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_ids:
            self._log("Vui lòng chọn video để chuyển sang Upload!", "WARNING")
            return
            
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        
        videos = db.get_downloaded_videos(limit=1000)
        count = 0
        for video in videos:
            vid = video["video_id"]
            if vid in selected_ids and video.get("download_path"):
                db.update_video_status(vid, "processed", video.get("download_path"))
                count += 1
                
        self._log(f"Đã chuyển {count} video thẳng sang tab Upload thành công!", "SUCCESS")
        self._load_videos()

    def _start_process(self):
        if getattr(self, "is_running", False):
            self._cancel_task()
            self._btn_process.configure(state="disabled", text="Đang dừng...")
            return

        self.is_running = True
        self._btn_process.configure(text="⏹ Dừng lại", fg_color=DANGER, hover_color="#c0392b")
        self._status_badge.set("Đang xử lý...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu xử lý video...", "INFO")

        title = self._entry_title.get().strip() or None
        limit = int(self._entry_limit.get() or 10)
        self._run_in_thread(self._do_process, title, limit)

    def _do_process(self, title, limit):
        from processor.video_processor import VideoProcessor
        from database.db_manager import DatabaseManager
        from config.settings import PROCESSOR_CONFIG
        
        # Lấy danh sách ID đã tick
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_ids:
            self._log("Không có video nào được chọn!", WARNING)
            self._on_task_done()
            return

        # Cập nhật config từ UI
        PROCESSOR_CONFIG["mirror"] = int(self._sw_mirror.get()) == 1
        PROCESSOR_CONFIG["replace_audio"] = int(self._sw_music.get()) == 1
        PROCESSOR_CONFIG["add_text"] = False
        PROCESSOR_CONFIG["specific_music_path"] = getattr(self, "_selected_music_path", None)
        PROCESSOR_CONFIG["auto_subtitle"] = int(self._sw_subtitle.get()) == 1
        
        # Lấy tuỳ chọn Vị trí Vietsub
        try:
            PROCESSOR_CONFIG["sub_pos"] = getattr(self, "_opt_sub_pos", ctk.CTkOptionMenu(self, values=[""])).get()
        except:
            PROCESSOR_CONFIG["sub_pos"] = "Đè lên vùng mờ"
            
        PROCESSOR_CONFIG["ai_dubbing"] = int(self._sw_dubbing.get()) == 1
        
        try:
            PROCESSOR_CONFIG["ai_mode"] = getattr(self, "_opt_ai_mode", ctk.CTkOptionMenu(self, values=[""])).get()
        except:
            PROCESSOR_CONFIG["ai_mode"] = "Thuyết minh nguyên bản"
        
        # Parse Platform & YouTube Options
        platform_choice = "youtube" if "YouTube" in self._opt_platform.get() else "tiktok"
        PROCESSOR_CONFIG["platform"] = platform_choice
        
        # Map Logo Position
        pos_map = {
            "Góc trên phải": "top_right",
            "Góc trên trái": "top_left",
            "Góc dưới trái": "bottom_left",
            "Góc dưới phải": "bottom_right",
            "Di chuyển (Floating)": "floating",
        }
        logo_pos_key = pos_map.get(self._opt_logo_pos.get(), "top_right")
        
        PROCESSOR_CONFIG["youtube_bypass"] = {
            "crop_zoom": 1.15 if int(self._sw_yt_crop.get()) == 1 else 1.0,
            "add_noise": int(self._sw_yt_noise.get()) == 1,
            "logo_path": getattr(self, "_selected_logo_path", None),
            "logo_position": logo_pos_key,
            "logo_scale": 0.15,
        }
        
        # Parse Bg Volume Options
        bg_vol_str = getattr(self, "_entry_bg_vol", ctk.CTkEntry(self)).get().strip().replace("%", "")
        try:
            vol_float = float(bg_vol_str) / 100.0
            if vol_float < 0: vol_float = 0.0
            if vol_float > 1: vol_float = 1.0
            PROCESSOR_CONFIG["original_audio_volume"] = vol_float
        except Exception:
            PROCESSOR_CONFIG["original_audio_volume"] = 0.15 # fallback
            
        # Parse Blur Options
        try:
            PROCESSOR_CONFIG["blur_enabled"] = int(getattr(self, "_sw_blur", ctk.CTkSwitch(self)).get()) == 1
        except Exception:
            PROCESSOR_CONFIG["blur_enabled"] = False
            
        blur_height_str = getattr(self, "_entry_blur_height", ctk.CTkEntry(self)).get().strip().replace("%", "")
        try:
            blur_height_float = float(blur_height_str) / 100.0
            if blur_height_float <= 0: PROCESSOR_CONFIG["blur_enabled"] = False
            if blur_height_float > 1: blur_height_float = 1.0
            PROCESSOR_CONFIG["blur_height"] = blur_height_float
        except Exception:
            PROCESSOR_CONFIG["blur_height"] = 0.15
        
        blur_pos_map = {
            "Dưới cùng": "bottom",
            "Trên cùng": "top",
        }
        PROCESSOR_CONFIG["blur_position"] = blur_pos_map.get(getattr(self, "_opt_blur_pos", ctk.CTkOptionMenu(self, values=[""])).get(), "bottom")
        
        # Parse TTS Options
        voice_sel = self._opt_voice.get()
        if "Đa giọng" in voice_sel:
            PROCESSOR_CONFIG["tts_voice"] = "Multi"
        else:
            PROCESSOR_CONFIG["tts_voice"] = "vi-VN-NamMinhNeural" if "Nam" in voice_sel else "vi-VN-HoaiMyNeural"
        
        rate_val = self._entry_tts_rate.get().strip()
        if not rate_val.startswith("+") and not rate_val.startswith("-"):
            rate_val = "+" + rate_val
        if not rate_val.endswith("%"):
            rate_val = rate_val + "%"
        PROCESSOR_CONFIG["tts_rate"] = rate_val

        db        = DatabaseManager()
        processor = VideoProcessor(db=db)
        titles    = {}
        if title:
            for vid in selected_ids:
                titles[vid] = title
                
        results = processor.process_downloaded_videos(titles=titles, limit=limit, video_ids=selected_ids, cancel_check=lambda: self.cancel_flag)
        if self.cancel_flag:
            self._log("Đã ngắt quá trình xử lý (Stop).", "WARNING")
        else:
            self._log(f"✅ Đã xử lý {len(results)} videos!", "SUCCESS")
        # Load lại danh sách sau khi xử lý xong
        self.after(0, self._load_videos)
        self._on_task_done()

    def _on_task_done(self):
        super()._on_task_done()
        self.is_running = False
        self.after(0, lambda: self._btn_process.configure(state="normal", text="▶  Bắt đầu Xử lý", fg_color="#9b59b6", hover_color="#8e44ad"))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS))


# ═══════════════════════════════════════════════════════════════════════════════
#  InputJSONWindow
# ═══════════════════════════════════════════════════════════════════════════════
class InputJSONWindow(ctk.CTkToplevel):
    def __init__(self, master, on_close_callback=None, initial_name=None, initial_content=None):
        super().__init__(master)
        self.title("Sửa/Thêm Tài khoản (JSON)")
        self.geometry("500x400")
        self.on_close_callback = on_close_callback
        
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Tên tài khoản (vd: tiktok_acc1):", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        
        self.name_entry = ctk.CTkEntry(self, font=("Segoe UI", 12))
        self.name_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=0)
        self.name_entry.insert(0, initial_name if initial_name else "tiktok_")
        
        ctk.CTkLabel(self, text="Dán nội dung JSON (từ Cookie Editor):", font=("Segoe UI", 12)).grid(row=2, column=0, sticky="w", padx=16, pady=(10, 4))
        
        self.json_text = ctk.CTkTextbox(self, font=("Consolas", 11), wrap="word")
        self.json_text.grid(row=3, column=0, sticky="nsew", padx=16, pady=0)
        if initial_content:
            self.json_text.insert("1.0", initial_content)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=16)
        
        ctk.CTkButton(btn_frame, text="Lưu", fg_color=SUCCESS, hover_color="#27ae60", command=self._save_json).pack(side="left")
        ctk.CTkButton(btn_frame, text="Hủy", fg_color=BORDER, hover_color=BG_CARD, command=self._on_close).pack(side="right")

    def _save_json(self):
        import json
        name = self.name_entry.get().strip()
        content = self.json_text.get("1.0", "end").strip()
        
        if not name or not content:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên tài khoản và nội dung JSON")
            return
            
        if not name.endswith(".json"):
            name += ".json"
            
        if not name.startswith("tiktok_"):
            name = f"tiktok_{name}"
            
        try:
            # Validate JSON format
            json.loads(content)
            
            user_dir = UploadTab._get_user_cookies_dir()
            with open(user_dir / name, "w", encoding="utf-8") as f:
                f.write(content)
                
            messagebox.showinfo("Thành công", f"Đã lưu tài khoản: {name}")
            if self.on_close_callback:
                self.on_close_callback()
            self.destroy()
        except json.JSONDecodeError:
            messagebox.showerror("Lỗi JSON", "Nội dung bạn dán không phải là JSON hợp lệ. Vui lòng kiểm tra lại.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")
            
    def _on_close(self):
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  AccountManagerWindow
# ═══════════════════════════════════════════════════════════════════════════════
class AccountManagerWindow(ctk.CTkToplevel):
    def __init__(self, master, on_close_callback=None):
        super().__init__(master)
        self.title("Quản lý Tài khoản (Cookies)")
        self.geometry("450x350")
        self.on_close_callback = on_close_callback
        
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Danh sách tài khoản (JSON):", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        
        ctk.CTkButton(btn_frame, text="Tải lên tài khoản mới", fg_color=SUCCESS, hover_color="#27ae60", command=self._upload_account).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Nhập JSON thủ công", fg_color=ACCENT, hover_color="#2980b9", command=self._input_json).pack(side="left")
        ctk.CTkButton(btn_frame, text="Đóng", fg_color=BORDER, hover_color=BG_CARD, command=self._on_close).pack(side="right")
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_accounts()

    def _load_accounts(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()
            
        user_dir = UploadTab._get_user_cookies_dir()
        accounts = [f.name for f in user_dir.glob("tiktok_*.json")]
            
        for acc in accounts:
            item = ctk.CTkFrame(self._list_frame, fg_color=BG_CARD, corner_radius=6)
            item.pack(fill="x", pady=4, padx=4)
            display_acc = acc if len(acc) < 35 else acc[:20] + "..." + acc[-10:]
            ctk.CTkLabel(item, text=display_acc, font=("Consolas", 12)).pack(side="left", padx=10, pady=8)
            ctk.CTkButton(item, text="Xóa", width=50, fg_color=DANGER, hover_color="#c0392b", command=lambda a=acc: self._delete_account(a)).pack(side="right", padx=10, pady=8)
            ctk.CTkButton(item, text="Sửa", width=50, fg_color=WARNING, hover_color="#d35400", command=lambda a=acc: self._edit_account(a)).pack(side="right", padx=5, pady=8)

    def _upload_account(self):
        path = filedialog.askopenfilename(
            title="Chọn file cookie JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                dest_name = os.path.basename(path)
                if not dest_name.startswith("tiktok_"):
                    dest_name = f"tiktok_{dest_name}"
                user_dir = UploadTab._get_user_cookies_dir()
                shutil.copy2(path, user_dir / dest_name)
                messagebox.showinfo("Thành công", f"Đã tải lên tài khoản: {dest_name}")
                self._load_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể tải lên file: {e}")

    def _input_json(self):
        InputJSONWindow(self, on_close_callback=self._load_accounts)

    def _edit_account(self, filename):
        try:
            user_dir = UploadTab._get_user_cookies_dir()
            with open(user_dir / filename, "r", encoding="utf-8") as f:
                content = f.read()
            InputJSONWindow(self, on_close_callback=self._load_accounts, initial_name=filename, initial_content=content)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def _delete_account(self, filename):
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa {filename}?"):
            try:
                user_dir = UploadTab._get_user_cookies_dir()
                (user_dir / filename).unlink(missing_ok=True)
                self._load_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa file: {e}")

    def _on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  YouTubeAccountManagerWindow
# ═══════════════════════════════════════════════════════════════════════════════
class YouTubeAccountManagerWindow(ctk.CTkToplevel):
    def __init__(self, master, on_close_callback=None):
        super().__init__(master)
        self.title("Quản lý Tài khoản (YouTube)")
        self.geometry("550x550")
        self.on_close_callback = on_close_callback
        
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Danh sách tài khoản YouTube (Token):", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        
        # Secret Key input frame (File)
        secret_frame = ctk.CTkFrame(self, fg_color="transparent")
        secret_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        
        ctk.CTkLabel(secret_frame, text="Client Secret (File):", font=("Segoe UI", 12)).pack(side="left")
        self._secret_entry = ctk.CTkEntry(secret_frame, font=("Segoe UI", 11), width=250)
        user_dir = UploadTab._get_user_cookies_dir()
        self._secret_entry.insert(0, str(user_dir / "client_secret.json"))
        self._secret_entry.pack(side="left", padx=10)
        ctk.CTkButton(secret_frame, text="📁", width=36, height=28, fg_color=BORDER, hover_color=BG_CARD, command=self._pick_secret).pack(side="left")
        ctk.CTkButton(secret_frame, text="Đăng nhập", fg_color=SUCCESS, hover_color="#27ae60", command=self._add_account).pack(side="left", padx=(10, 0))
        
        # Secret Key input frame (Paste JSON)
        paste_frame = ctk.CTkFrame(self, fg_color="transparent")
        paste_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        
        ctk.CTkLabel(paste_frame, text="Hoặc dán mã JSON của Client Secret (KHÔNG PHẢI COOKIES!):", font=("Segoe UI", 12, "bold"), text_color="#e74c3c").pack(anchor="w")
        self._json_textbox = ctk.CTkTextbox(paste_frame, height=80, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._json_textbox.pack(fill="x", pady=4)
        ctk.CTkButton(paste_frame, text="Lưu JSON & Đăng nhập", fg_color=SUCCESS, hover_color="#27ae60", command=self._add_account_from_json).pack(anchor="w")
        
        # Bottom Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(16, 16))
        
        ctk.CTkButton(btn_frame, text="Đóng", fg_color=BORDER, hover_color=BG_CARD, command=self._on_close).pack(side="right")
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_accounts()

    def _pick_secret(self):
        import os
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn file client_secret.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self._secret_entry.delete(0, "end")
            self._secret_entry.insert(0, path)

    def _load_accounts(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()
            
        user_dir = UploadTab._get_user_cookies_dir()
        accounts = [f.name for f in user_dir.glob("youtube_*.json")]
            
        for acc in accounts:
            item = ctk.CTkFrame(self._list_frame, fg_color=BG_CARD, corner_radius=6)
            item.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(item, text=acc, font=("Consolas", 12)).pack(side="left", padx=10, pady=8)
            ctk.CTkButton(item, text="Xóa", width=50, fg_color=DANGER, hover_color="#c0392b", command=lambda a=acc: self._delete_account(a)).pack(side="right", padx=10, pady=8)

    def _add_account_from_json(self):
        json_text = self._json_textbox.get("1.0", "end").strip()
        if not json_text:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", "Vui lòng dán nội dung file client_secret.json vào ô trống.")
            return
            
        import json
        try:
            json.loads(json_text)
        except json.JSONDecodeError:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", "Nội dung JSON không hợp lệ.")
            return
            
        user_dir = UploadTab._get_user_cookies_dir()
        secret_path = str(user_dir / "client_secret.json")
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(json_text)
            
        self._secret_entry.delete(0, "end")
        self._secret_entry.insert(0, secret_path)
        
        # Clear textbox sau khi dùng
        self._json_textbox.delete("1.0", "end")
        self._add_account()

    def _add_account(self):
        secret_path = self._secret_entry.get().strip()
        import os
        if not os.path.exists(secret_path):
            from tkinter import messagebox
            messagebox.showerror("Lỗi", "Không tìm thấy file client_secret.json! Vui lòng tải từ Google Cloud Console hoặc dán code JSON vào ô bên dưới.")
            return
            
        user_dir = UploadTab._get_user_cookies_dir()
        # Find next available youtube_X.json
        idx = 1
        while (user_dir / f"youtube_{idx}.json").exists():
            idx += 1
        
        new_token_name = f"youtube_{idx}.json"
        token_path = str(user_dir / new_token_name)
        
        import threading
        
        def _auth_thread():
            from uploader.youtube_uploader import YouTubeUploader
            if YouTubeUploader.authorize_new_account(secret_path, token_path):
                self.after(0, lambda: _on_auth_success(new_token_name))
                
        def _on_auth_success(name):
            from tkinter import messagebox
            messagebox.showinfo("Thành công", f"Đã đăng nhập và lưu {name}")
            self._load_accounts()
            
        t = threading.Thread(target=_auth_thread, daemon=True)
        t.start()

    def _delete_account(self, filename):
        from tkinter import messagebox
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa {filename}?"):
            try:
                user_dir = UploadTab._get_user_cookies_dir()
                (user_dir / filename).unlink(missing_ok=True)
                self._load_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa file: {e}")

    def _on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Upload
# ═══════════════════════════════════════════════════════════════════════════════
class UploadTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._checkboxes = {}
        self._video_accounts = {}
        self._video_accounts_yt = {}
        self._build()
        self.after(200, self._load_videos)

    @staticmethod
    def _get_user_cookies_dir():
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    @staticmethod
    def _get_tiktok_accounts():
        user_dir = UploadTab._get_user_cookies_dir()
        accounts = [f.name for f in user_dir.glob("tiktok_*.json")]
        return ["Không up"] + accounts if accounts else ["Không up"]

    @staticmethod
    def _get_youtube_accounts():
        user_dir = UploadTab._get_user_cookies_dir()
        accounts = [f.name for f in user_dir.glob("youtube_*.json")]
        return ["Không up"] + accounts if accounts else ["Không up"]

    def _build(self):
        ctk.CTkLabel(
            self, text="📤  Upload Video",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # Khởi tạo 2 cột (Trái: Danh sách, Phải: Sidebar công cụ)
        self.grid_columnconfigure(0, weight=5)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(1, weight=1)

        # --- LEFT PANE ---
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 15))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        # Danh sách chọn video
        list_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(list_header, text="Danh sách Video đã xử lý:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        
        ctk.CTkButton(list_header, text="🔄 Refresh", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._load_videos).pack(side="right")
        ctk.CTkButton(list_header, text="🗑 Xóa", width=60, height=24, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_selected).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="⏪ Về Process", width=90, height=24, fg_color="#f39c12", hover_color="#e67e22", command=self._revert_to_process).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="☑ Chọn", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._toggle_selection).pack(side="right", padx=(0, 10))
        
        self._video_list_frame = ctk.CTkScrollableFrame(left_frame, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._video_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

        self._log_widget = LogWidget(left_frame, height=120)
        self._log_widget.grid(row=2, column=0, sticky="nsew")

        # --- RIGHT PANE (SIDEBAR) ---
        right_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        right_frame.grid(row=1, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        # Options card
        opts = ctk.CTkFrame(right_frame, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        opts.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(0, weight=1)

        # Cấu hình xếp dọc theo Sidebar
        config_frame = ctk.CTkFrame(opts, fg_color="transparent")
        config_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 14))
        
        # --- Cấu hình chung ---
        ctk.CTkLabel(config_frame, text="Cấu hình chung", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(row1, text="Số video:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_limit = ctk.CTkEntry(row1, width=45, font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_limit.insert(0, "4")
        self._entry_limit.pack(side="left", padx=(0, 15))
        
        self._sw_cleanup_upload = ctk.CTkSwitch(row1, text="Dọn dẹp file sau đăng", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_cleanup_upload.select()
        self._sw_cleanup_upload.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Nền tảng Đăng ---
        ctk.CTkLabel(config_frame, text="Nền tảng Upload", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))
        
        self._sw_platform_tt = ctk.CTkSwitch(row2, text="TikTok", font=("Segoe UI", 11))
        self._sw_platform_tt.select()
        self._sw_platform_tt.pack(side="left", padx=(0, 20))
        
        self._sw_platform_yt = ctk.CTkSwitch(row2, text="YouTube", font=("Segoe UI", 11))
        self._sw_platform_yt.select()
        self._sw_platform_yt.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Tài khoản TikTok ---
        ctk.CTkLabel(config_frame, text="Tài khoản TikTok mặc định", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row3 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 12))
        
        accounts = self._get_tiktok_accounts()
        self._opt_account = ctk.CTkOptionMenu(
            row3, values=accounts, font=("Segoe UI", 11),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account.pack(fill="x", pady=(0, 5))
        
        tt_btns = ctk.CTkFrame(row3, fg_color="transparent")
        tt_btns.pack(fill="x")
        self._btn_apply_acc = ctk.CTkButton(
            tt_btns, text="Áp dụng All", width=90, height=24, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._apply_account_to_all
        )
        self._btn_apply_acc.pack(side="left", padx=(0, 10))
        
        self._btn_manage_acc = ctk.CTkButton(
            tt_btns, text="⚙ Quản lý", width=70, height=24, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._open_account_manager
        )
        self._btn_manage_acc.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Tài khoản YouTube ---
        ctk.CTkLabel(config_frame, text="Tài khoản YouTube mặc định", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row4 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row4.pack(fill="x", pady=(0, 12))
        
        yt_accounts = self._get_youtube_accounts()
        self._opt_account_yt = ctk.CTkOptionMenu(
            row4, values=yt_accounts, font=("Segoe UI", 11),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_yt.pack(fill="x", pady=(0, 5))
        
        yt_btns = ctk.CTkFrame(row4, fg_color="transparent")
        yt_btns.pack(fill="x")
        self._btn_apply_acc_yt = ctk.CTkButton(
            yt_btns, text="Áp dụng All", width=90, height=24, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._apply_account_to_all_yt
        )
        self._btn_apply_acc_yt.pack(side="left", padx=(0, 10))
        
        self._btn_manage_acc_yt = ctk.CTkButton(
            yt_btns, text="⚙ Quản lý", width=70, height=24, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._open_youtube_account_manager
        )
        self._btn_manage_acc_yt.pack(side="left")

        # Buttons
        btn_row = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._btn_upload = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Upload", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._start_upload,
        )
        self._btn_upload.pack(fill="x", pady=(0, 10))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(anchor="center")

    def _load_videos(self):
        """Hiển thị danh sách video đã processed vào scrollable frame."""
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        self._video_accounts.clear()
        self._video_accounts_yt.clear()
        self._custom_captions = {}

        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username") if auth_client.user_info else None
        videos = db.get_pending_videos(limit=100, username=current_user)
        
        if not videos:
            ctk.CTkLabel(self._video_list_frame, text="Không có video nào đang chờ upload.", text_color=TEXT_DIM).pack(pady=20)
            self._update_selected_count()
            return

        from uploader.tiktok_uploader import TikTokUploader
        uploader_dummy = TikTokUploader(db=db)

        for video in videos:
            vid = video["video_id"]
            
            # Khung chứa 1 video (Card)
            card = ctk.CTkFrame(self._video_list_frame, fg_color=BG_CARD, corner_radius=8,
                                 border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=6, padx=10)
            
            var = ctk.BooleanVar(value=True)
            self._checkboxes[vid] = var
            
            # --- ROW 1: Header (Checkbox, ID, Size, Xem, Tài khoản) ---
            row1 = ctk.CTkFrame(card, fg_color="transparent")
            row1.pack(fill="x", padx=10, pady=(10, 5))
            
            cb = ctk.CTkCheckBox(row1, text="", variable=var, width=24, command=self._update_selected_count)
            cb.pack(side="left")
            
            ctk.CTkLabel(row1, text=f"ID: {vid}", font=("Consolas", 11, "bold"), text_color=ACCENT).pack(side="left", padx=5)
            
            path = video.get("processed_path")
            size_mb = 0
            import os
            if path and os.path.exists(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
            ctk.CTkLabel(row1, text=f"📦 {size_mb:.1f} MB", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(5, 10))
            
            if path and os.path.exists(path):
                ctk.CTkButton(
                    row1, text="▶ Xem", width=50, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda p=path: os.startfile(p) if os.name == 'nt' else None
                ).pack(side="left", padx=(0, 15))
                
            # Đẩy phần chọn tài khoản sang phải
            right_header = ctk.CTkFrame(row1, fg_color="transparent")
            right_header.pack(side="right")
            
            ctk.CTkLabel(right_header, text="TT:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(5, 2))
            accounts = self._get_tiktok_accounts()
            opt_acc = ctk.CTkOptionMenu(right_header, values=accounts, font=("Segoe UI", 11), width=100, fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD)
            opt_acc.pack(side="left")
            global_acc = getattr(self, "_opt_account", None)
            if global_acc and global_acc.get() in accounts:
                opt_acc.set(global_acc.get())
            self._video_accounts[vid] = opt_acc

            ctk.CTkLabel(right_header, text="YT:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(10, 2))
            yt_accounts = self._get_youtube_accounts()
            opt_acc_yt = ctk.CTkOptionMenu(right_header, values=yt_accounts, font=("Segoe UI", 11), width=100, fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD)
            opt_acc_yt.pack(side="left")
            global_acc_yt = getattr(self, "_opt_account_yt", None)
            if global_acc_yt and global_acc_yt.get() in yt_accounts:
                opt_acc_yt.set(global_acc_yt.get())
            self._video_accounts_yt[vid] = opt_acc_yt

            # --- ROW 2: Editable Caption Title ---
            display_title = video.get("title_vi") or video.get("title") or "No title"
            row2 = ctk.CTkFrame(card, fg_color="transparent")
            row2.pack(fill="x", padx=10, pady=(0, 2))
            ctk.CTkLabel(row2, text=display_title[:80] + ("..." if len(display_title) > 80 else ""), font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN).pack(side="left")

            # --- ROW 3: Textbox ---
            row3 = ctk.CTkFrame(card, fg_color="transparent")
            row3.pack(fill="x", padx=10, pady=(2, 5))
            
            # Ưu tiên lấy custom_caption trong DB
            title = video.get("custom_caption")
            if not title:
                title = uploader_dummy._generate_caption(video)
                
            textbox = ctk.CTkTextbox(row3, font=("Segoe UI", 13), text_color=TEXT_MAIN, fg_color=BG_DARK, border_color=BORDER, height=60, wrap="word")
            textbox.insert("1.0", title)
            textbox.pack(fill="x", expand=True)
            self._custom_captions[vid] = textbox

            # --- ROW 4: Save Button ---
            row4 = ctk.CTkFrame(card, fg_color="transparent")
            row4.pack(fill="x", padx=10, pady=(0, 10))
            
            def make_save_cmd(video_id, tb_widget):
                def cmd():
                    from database.db_manager import DatabaseManager
                    db_tmp = DatabaseManager()
                    new_cap = tb_widget.get("1.0", "end-1c")
                    db_tmp.update_custom_caption(video_id, new_cap)
                    messagebox.showinfo("Thành công", f"Đã lưu Caption cho video {video_id}")
                return cmd
                
            btn_save = ctk.CTkButton(row4, text="💾 Lưu Caption", width=120, height=26, font=("Segoe UI", 12, "bold"), fg_color="#2980b9", hover_color="#3498db", command=make_save_cmd(vid, textbox))
            btn_save.pack(side="left")

        self._update_selected_count()

    def _revert_to_process(self):
        """Đưa các video đã chọn trở lại tab Process (đổi status về downloaded)"""
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 video để hoàn tác!")
            return
            
        if messagebox.askyesno("Xác nhận", f"Đưa {len(selected_ids)} video trở lại tab Process để xử lý lại?"):
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            for vid in selected_ids:
                db.update_video_status(video_id=vid, status="downloaded")
            self._log(f"Đã đưa {len(selected_ids)} video trở lại hàng chờ Xử lý.", "SUCCESS")
            self._load_videos()

    def _update_selected_count(self, *args):
        count = sum(1 for var in self._checkboxes.values() if var.get())
        if hasattr(self, '_entry_limit'):
            self._entry_limit.delete(0, "end")
            self._entry_limit.insert(0, str(count))

    def _delete_selected(self):
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_ids:
            self._log("Vui lòng chọn video để xóa!", "WARNING")
            return
            
        if not messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa {len(selected_ids)} video đã xử lý này không? Thao tác này sẽ xóa vĩnh viễn cả file gốc."):
            return
            
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        deleted = 0
        for vid in selected_ids:
            if db.delete_video_data(vid):
                deleted += 1
                
        self._log(f"Đã xóa vĩnh viễn {deleted} video khỏi DB và ổ cứng.", "SUCCESS")
        self._load_videos()

    def _toggle_selection(self):
        if not self._checkboxes:
            return
        all_checked = all(var.get() for var in self._checkboxes.values())
        new_state = not all_checked
        for var in self._checkboxes.values():
            var.set(new_state)
        self._update_selected_count()

    def _start_upload(self):
        if getattr(self, "is_running", False):
            self._cancel_task()
            self._btn_upload.configure(state="disabled", text="Đang dừng...")
            return

        self.is_running = True
        self._btn_upload.configure(text="⏹ Dừng lại", fg_color=DANGER, hover_color="#c0392b")
        self._status_badge.set("Đang upload...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu upload video lên TikTok...", "INFO")
        
        # Lấy tất cả giá trị GUI ở thread chính trước khi chạy ngầm
        selected_vids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_vids:
            self._log("Không có video nào được chọn!", "WARNING")
            self._on_task_done()
            return
            
        custom_captions_dict = {vid: tb.get("1.0", "end-1c") for vid, tb in self._custom_captions.items()}
        video_accounts_tt_dict = {vid: opt.get() for vid, opt in self._video_accounts.items()}
        video_accounts_yt_dict = {vid: opt.get() for vid, opt in self._video_accounts_yt.items()}
        cleanup_upload = self._sw_cleanup_upload.get() == 1
        
        do_tt = self._sw_platform_tt.get() == 1
        do_yt = self._sw_platform_yt.get() == 1
        
        if not do_tt and not do_yt:
            self._log("Vui lòng chọn ít nhất 1 nền tảng để upload!", "WARNING")
            self._on_task_done()
            return
        
        # Override limit bằng đúng số lượng video được chọn để đảm bảo up đủ
        limit = len(selected_vids)
        
        self._run_in_thread(self._do_upload, limit, selected_vids, custom_captions_dict, video_accounts_tt_dict, video_accounts_yt_dict, cleanup_upload, do_tt, do_yt)

    def _on_task_done(self):
        super()._on_task_done()
        self.is_running = False
        self.after(0, lambda: self._btn_upload.configure(text="▶  Bắt đầu Upload", state="normal", fg_color="#e74c3c", hover_color="#c0392b"))

    async def _async_upload_groups(self, limit, account_groups_tt, account_groups_yt, custom_captions_dict, do_tt, do_yt):
        from database.db_manager import DatabaseManager
        from config.settings import COOKIES_DIR
        db = DatabaseManager()
        
        if do_tt:
            from uploader.tiktok_uploader import TikTokUploader
            total_uploaded = 0
            for account_file, vids in account_groups_tt.items():
                if self.cancel_flag:
                    self._log("Đã ngắt quá trình upload (Stop).", "WARNING")
                    break
                if total_uploaded >= limit:
                    break
                    
                vids_to_upload = vids[:limit - total_uploaded]
                
                self._log(f"Bắt đầu upload {len(vids_to_upload)} video lên TikTok bằng {account_file}...", "INFO")
                user_dir = self._get_user_cookies_dir()
                cookies_path = str(user_dir / account_file)
                
                # Lấy proxy từ file
                proxy_str = None
                try:
                    import json
                    proxy_file = user_dir / "proxies.json"
                    if proxy_file.exists():
                        with open(proxy_file, "r", encoding="utf-8") as f:
                            proxies = json.load(f)
                            proxy_str = proxies.get(account_file)
                except Exception:
                    pass
                    
                uploader = TikTokUploader(db=db, cookies_file=cookies_path, proxy=proxy_str)
                
                captions_to_pass = {
                    vid: custom_captions_dict[vid] 
                    for vid in vids_to_upload if vid in custom_captions_dict
                }
                
                try:
                    results = await uploader.upload_pending_videos(
                        limit=len(vids_to_upload), 
                        video_ids=vids_to_upload,
                        custom_captions=captions_to_pass
                    )
                    total_uploaded += len(results)
                    self._log(f"✅ Upload xong {len(results)} videos lên TikTok ({account_file})!", "SUCCESS")
                except Exception as e:
                    self._log(f"Lỗi upload TikTok {account_file}: {e}", "ERROR")
                finally:
                    await uploader.close()

        if do_yt:
            from uploader.youtube_uploader import YouTubeUploader
            total_uploaded = 0
            for account_file, vids in account_groups_yt.items():
                if total_uploaded >= limit:
                    break
                    
                vids_to_upload = vids[:limit - total_uploaded]
                
                self._log(f"Bắt đầu upload {len(vids_to_upload)} video lên YouTube bằng {account_file}...", "INFO")
                user_dir = self._get_user_cookies_dir()
                token_path = str(user_dir / account_file)
                yt_uploader = YouTubeUploader(db=db, token_file=token_path)
                
                captions_to_pass = {
                    vid: custom_captions_dict[vid] 
                    for vid in vids_to_upload if vid in custom_captions_dict
                }
                
                try:
                    results = await yt_uploader.upload_pending_videos(
                        limit=len(vids_to_upload), 
                        video_ids=vids_to_upload,
                        custom_captions=captions_to_pass
                    )
                    total_uploaded += len(results)
                    self._log(f"✅ Upload xong {len(results)} videos lên YouTube ({account_file})!", "SUCCESS")
                except Exception as e:
                    self._log(f"Lỗi upload YouTube {account_file}: {e}", "ERROR")
                finally:
                    await yt_uploader.close()
                
        self.after(0, self._load_videos)
        self._on_task_done()


    def _apply_account_to_all(self):
        selected = self._opt_account.get()
        for vid, opt in self._video_accounts.items():
            if self._checkboxes[vid].get():
                opt.set(selected)

    def _open_account_manager(self):
        AccountManagerWindow(self, on_close_callback=self._refresh_accounts)

    def _refresh_accounts(self):
        accounts = self._get_tiktok_accounts()
        self._opt_account.configure(values=accounts)
        
        current_global = self._opt_account.get()
        if not accounts:
            self._opt_account.set("")
        elif current_global not in accounts:
            self._opt_account.set(accounts[0])
            
        for opt in self._video_accounts.values():
            opt.configure(values=accounts)
            curr = opt.get()
            if not accounts:
                opt.set("")
            elif curr not in accounts:
                opt.set(accounts[0])

    def _apply_account_to_all_yt(self):
        selected = self._opt_account_yt.get()
        for vid, opt in self._video_accounts_yt.items():
            if self._checkboxes[vid].get():
                opt.set(selected)

    def _open_youtube_account_manager(self):
        YouTubeAccountManagerWindow(self, on_close_callback=self._refresh_youtube_accounts)

    def _refresh_youtube_accounts(self):
        accounts = self._get_youtube_accounts()
        self._opt_account_yt.configure(values=accounts)
        
        current_global = self._opt_account_yt.get()
        if not accounts:
            self._opt_account_yt.set("")
        elif current_global not in accounts:
            self._opt_account_yt.set(accounts[0])
            
        for opt in self._video_accounts_yt.values():
            opt.configure(values=accounts)
            curr = opt.get()
            if not accounts:
                opt.set("")
            elif curr not in accounts:
                opt.set(accounts[0])

    def _do_upload(self, limit, selected_vids, custom_captions_dict, video_accounts_tt_dict, video_accounts_yt_dict, cleanup_upload, do_tt, do_yt):
        from config.settings import TIKTOK_CONFIG, YOUTUBE_CONFIG
        TIKTOK_CONFIG["auto_cleanup_after_upload"] = cleanup_upload
        YOUTUBE_CONFIG["auto_cleanup_after_upload"] = cleanup_upload

        account_groups_tt = {}
        account_groups_yt = {}
        
        for vid in selected_vids:
            if do_tt:
                acc_tt = video_accounts_tt_dict.get(vid)
                if acc_tt and acc_tt != "Không up":
                    if acc_tt not in account_groups_tt:
                        account_groups_tt[acc_tt] = []
                    account_groups_tt[acc_tt].append(vid)
            
            if do_yt:
                acc_yt = video_accounts_yt_dict.get(vid)
                if acc_yt and acc_yt != "Không up":
                    if acc_yt not in account_groups_yt:
                        account_groups_yt[acc_yt] = []
                    account_groups_yt[acc_yt].append(vid)

        import asyncio
        asyncio.run(self._async_upload_groups(limit, account_groups_tt, account_groups_yt, custom_captions_dict, do_tt, do_yt))

    def _on_task_done(self):
        self.after(0, lambda: self._btn_upload.configure(state="normal"))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS))


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Auto (Pipeline)
# ═══════════════════════════════════════════════════════════════════════════════
class AutoTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._running = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="🤖  Auto Pipeline",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Config card
        cfg = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        cfg.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        cfg.grid_columnconfigure(1, weight=1)

        # Source / Nguồn Video
        ctk.CTkLabel(cfg, text="Nguồn Video", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        
        self._source_var = ctk.StringVar(value="urls")
        
        src_frame = ctk.CTkFrame(cfg, fg_color="transparent")
        src_frame.grid(row=0, column=1, sticky="w", pady=(14, 4))
        
        ctk.CTkRadioButton(src_frame, text="Từ File URLs (Crawl mới)", variable=self._source_var, value="urls", command=self._toggle_source,
                            font=("Segoe UI", 12), text_color=TEXT_MAIN).pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(src_frame, text="Chỉ Upload (Video đã xử lý)", variable=self._source_var, value="db", command=self._toggle_source,
                            font=("Segoe UI", 12), text_color="#f39c12").pack(side="left")

        # URLs
        self.file_label = ctk.CTkLabel(cfg, text="File URLs", font=("Segoe UI", 12), text_color=TEXT_DIM)
        self.file_label.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 4))
        
        self.file_row = ctk.CTkFrame(cfg, fg_color="transparent")
        self.file_row.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(4, 4))
        self.file_row.grid_columnconfigure(0, weight=1)
        self._entry_file = ctk.CTkEntry(
            self.file_row, placeholder_text="urls.txt",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_file.insert(0, "urls.txt")
        self._entry_file.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            self.file_row, text="📁", width=40, height=30,
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._browse,
        ).grid(row=0, column=1, padx=(8, 0))

        # Mode
        ctk.CTkLabel(cfg, text="Chế độ", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=2, column=0, sticky="w", padx=16, pady=4)
        self._mode_var = ctk.StringVar(value="once")
        mode_frame = ctk.CTkFrame(cfg, fg_color="transparent")
        mode_frame.grid(row=2, column=1, sticky="w", pady=4)
        ctk.CTkRadioButton(mode_frame, text="Chạy 1 lần", variable=self._mode_var, value="once",
                            font=("Segoe UI", 12), text_color=TEXT_MAIN).pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="Chạy 24/7 theo lịch", variable=self._mode_var, value="schedule",
                            font=("Segoe UI", 12), text_color=TEXT_MAIN).pack(side="left", padx=10)

        # Schedule times
        ctk.CTkLabel(cfg, text="Giờ post", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=3, column=0, sticky="w", padx=16, pady=(4, 4))
        self._entry_times = ctk.CTkEntry(
            cfg, placeholder_text="09:00, 12:30, 18:00, 21:30",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_times.insert(0, "09:00, 12:30, 18:00, 21:30")
        self._entry_times.grid(row=3, column=1, sticky="ew", padx=(0, 16), pady=(4, 4))
        
        # Max posts & Cleanup
        ctk.CTkLabel(cfg, text="Upload tối đa", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=4, column=0, sticky="w", padx=16, pady=(4, 14))
        opt_frame = ctk.CTkFrame(cfg, fg_color="transparent")
        opt_frame.grid(row=4, column=1, sticky="w", pady=(4, 14))
        self._entry_auto_limit = ctk.CTkEntry(
            opt_frame, width=50, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_auto_limit.insert(0, "4")
        self._entry_auto_limit.pack(side="left")
        ctk.CTkLabel(opt_frame, text="vid/ngày", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(side="left", padx=(8, 15))
        
        # Thêm cấu hình Delay
        ctk.CTkLabel(opt_frame, text="Giãn cách:", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(side="left", padx=(5, 5))
        self._entry_delay = ctk.CTkEntry(
            opt_frame, width=50, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_delay.insert(0, "120") # Mặc định 120 phút
        self._entry_delay.pack(side="left")
        ctk.CTkLabel(opt_frame, text="phút", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(side="left", padx=(5, 15))

        self._sw_cleanup_auto = ctk.CTkSwitch(opt_frame, text="🧹 Tự động dọn dẹp",
                                                font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_cleanup_auto.select()
        self._sw_cleanup_auto.pack(side="left")

        # Account selection & Platform Switches
        acc_frame = ctk.CTkFrame(cfg, fg_color="transparent")
        acc_frame.grid(row=5, column=0, columnspan=3, sticky="w", padx=16, pady=(4, 14))

        self._sw_auto_tt = ctk.CTkSwitch(acc_frame, text="TikTok:", font=("Segoe UI", 12, "bold"), width=60)
        self._sw_auto_tt.select()
        self._sw_auto_tt.pack(side="left", padx=(0, 5))
        
        accounts = UploadTab._get_tiktok_accounts()
        self._opt_account = ctk.CTkOptionMenu(
            acc_frame, values=accounts, font=("Segoe UI", 12), width=120,
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account.pack(side="left")
        
        self._btn_manage_acc = ctk.CTkButton(
            acc_frame, text="⚙ Quản lý", width=70, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._open_account_manager
        )
        self._btn_manage_acc.pack(side="left", padx=(10, 20))

        self._sw_auto_yt = ctk.CTkSwitch(acc_frame, text="YouTube:", font=("Segoe UI", 12, "bold"), width=60)
        self._sw_auto_yt.select()
        self._sw_auto_yt.pack(side="left", padx=(0, 5))
        
        yt_accounts = UploadTab._get_youtube_accounts()
        self._opt_account_yt = ctk.CTkOptionMenu(
            acc_frame, values=yt_accounts, font=("Segoe UI", 12), width=120,
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_yt.pack(side="left")
        
        self._btn_manage_acc_yt = ctk.CTkButton(
            acc_frame, text="⚙ Quản lý YT", width=70, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._open_youtube_account_manager
        )
        self._btn_manage_acc_yt.pack(side="left", padx=(10, 0))

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self._btn_start = ctk.CTkButton(
            btn_row, text="▶  Start Auto", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._start,
        )
        self._btn_start.pack(side="left", padx=(0, 8))

        self._btn_stop = ctk.CTkButton(
            btn_row, text="⏹  Stop", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color=DANGER, hover_color="#c0392b",
            state="disabled",
            command=self._stop,
        )
        self._btn_stop.pack(side="left", padx=(0, 10))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(side="left")

        # Log
        self._log_widget = LogWidget(self)
        self._log_widget.grid(row=3, column=0, sticky="nsew")

    def _open_account_manager(self):
        AccountManagerWindow(self, on_close_callback=self._refresh_accounts)

    def _refresh_accounts(self):
        accounts = UploadTab._get_tiktok_accounts()
        self._opt_account.configure(values=accounts)
        if accounts:
            current = self._opt_account.get()
            if current not in accounts:
                self._opt_account.set(accounts[0])
        else:
            self._opt_account.set("")

    def _open_youtube_account_manager(self):
        YouTubeAccountManagerWindow(self, on_close_callback=self._refresh_youtube_accounts)

    def _refresh_youtube_accounts(self):
        accounts = UploadTab._get_youtube_accounts()
        self._opt_account_yt.configure(values=accounts)
        if accounts:
            current = self._opt_account_yt.get()
            if current not in accounts:
                self._opt_account_yt.set(accounts[0])
        else:
            self._opt_account_yt.set("")

    def _toggle_source(self):
        if self._source_var.get() == "db":
            self.file_label.grid_remove()
            self.file_row.grid_remove()
        else:
            self.file_label.grid()
            self.file_row.grid()

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Chọn file URLs",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=str(Path(__file__).parent),
        )
        if path:
            self._entry_file.delete(0, "end")
            self._entry_file.insert(0, path)

    def _start(self):
        self._running = True
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._status_badge.set("Đang chạy...", SUCCESS)
        self._log_widget.clear()
        self._log("Auto pipeline bắt đầu...", "INFO")

        source_mode = self._source_var.get()
        file_path = self._entry_file.get().strip() or "urls.txt"
        once      = self._mode_var.get() == "once"
        
        do_tt = getattr(self, "_sw_auto_tt", None)
        do_tt = do_tt.get() == 1 if do_tt else True
        
        do_yt = getattr(self, "_sw_auto_yt", None)
        do_yt = do_yt.get() == 1 if do_yt else True
        
        if not do_tt and not do_yt:
            self._log("LỖI: Vui lòng bật ít nhất 1 nền tảng (TikTok hoặc YouTube)!", "WARNING")
            self._on_task_done()
            return

        account_file = self._opt_account.get() if do_tt else None
        account_file_yt = getattr(self, "_opt_account_yt", None)
        account_file_yt = account_file_yt.get() if account_file_yt and do_yt else None
        
        self._run_in_thread(self._do_auto, file_path, once, account_file, account_file_yt, source_mode)

    def _do_auto(self, file_path, once, account_file, account_file_yt, source_mode):
        from scheduler.scheduler import AutoScheduler
        from config.settings import SCHEDULER_CONFIG, TIKTOK_CONFIG, YOUTUBE_CONFIG
        
        # Cập nhật config từ UI
        try:
            SCHEDULER_CONFIG["post_times"] = [t.strip() for t in self._entry_times.get().split(",")]
            max_limit = int(self._entry_auto_limit.get() or 4)
            TIKTOK_CONFIG["max_posts_per_day"] = max_limit
            YOUTUBE_CONFIG["max_posts_per_day"] = max_limit
            
            # Lưu delay (phút -> chuyển thành cấu hình)
            delay_mins = int(self._entry_delay.get() or 120)
            TIKTOK_CONFIG["post_delay_minutes"] = delay_mins
            YOUTUBE_CONFIG["post_delay_minutes"] = delay_mins
            
            cleanup = self._sw_cleanup_auto.get() == 1
            TIKTOK_CONFIG["auto_cleanup_after_upload"] = cleanup
            YOUTUBE_CONFIG["auto_cleanup_after_upload"] = cleanup
        except Exception as e:
            self._log(f"Lỗi parse cấu hình: {e}", "WARNING")
            
        urls = []
        if source_mode == "urls":
            try:
                urls = Path(file_path).read_text(encoding="utf-8").strip().splitlines()
                urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
            except Exception as e:
                self._log(f"Không thể đọc file URLs: {e}", "WARNING")
        
        user_dir = UploadTab._get_user_cookies_dir()
        tt_account_path = str(user_dir / account_file) if account_file else None
        yt_account_path = str(user_dir / account_file_yt) if account_file_yt else None
        
        mode_val = "full" if source_mode == "urls" else "upload_only"
        scheduler = AutoScheduler(douyin_urls=urls, tt_account_file=tt_account_path, yt_account_file=yt_account_path, source_mode=mode_val)
        if once:
            import asyncio
            asyncio.run(scheduler.run_once())
        else:
            import asyncio
            asyncio.run(scheduler.start())

    def _stop(self):
        self._running = False
        self._log("Đã gửi tín hiệu dừng...", "WARNING")
        self._on_task_done()

    def _on_task_done(self):
        self.after(0, lambda: self._btn_start.configure(state="normal"))
        self.after(0, lambda: self._btn_stop.configure(state="disabled"))
        self.after(0, lambda: self._status_badge.set("Dừng", DANGER if not self._running else SUCCESS))


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Nuôi Nick (Farm)
# ═══════════════════════════════════════════════════════════════════════════════
class FarmTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._checkboxes = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()
        self.after(200, self._load_accounts)

    def _build(self):
        # Tiêu đề
        ctk.CTkLabel(
            self, text="🌱  Nuôi Nick (Farm)",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Cấu hình
        cfg = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        cfg.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        cfg.grid_columnconfigure(0, weight=1)
        
        row1 = ctk.CTkFrame(cfg, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=20, pady=16)
        row1.grid_columnconfigure(4, weight=1) # Đẩy nút Start sang phải

        ctk.CTkLabel(row1, text="⏱ Thời gian (phút):", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=0, padx=(0, 10))
        self._entry_duration = ctk.CTkEntry(row1, width=70, font=("Segoe UI", 12, "bold"), justify="center", fg_color=BG_DARK, border_color=BORDER)
        self._entry_duration.insert(0, "15")
        self._entry_duration.grid(row=0, column=1, padx=(0, 25))

        ctk.CTkLabel(row1, text="❤️ Tỷ lệ thả tim:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=2, padx=(0, 10))
        self._entry_like_ratio = ctk.CTkEntry(row1, width=70, font=("Segoe UI", 12, "bold"), justify="center", fg_color=BG_DARK, border_color=BORDER)
        self._entry_like_ratio.insert(0, "0.2")
        self._entry_like_ratio.grid(row=0, column=3)

        self._btn_start = ctk.CTkButton(
            row1, text="▶  Bắt đầu Nuôi", height=36, font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60", command=self._start_farm
        )
        self._btn_start.grid(row=0, column=4, sticky="e")

        # Layout cột: Trái (Danh sách Acc), Phải (Log)
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=2, column=0, sticky="nsew")
        split.grid_columnconfigure(0, weight=1)
        split.grid_columnconfigure(1, weight=2)
        split.grid_rowconfigure(0, weight=1)

        # Danh sách Account
        acc_frame = ctk.CTkFrame(split, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        acc_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        acc_frame.grid_rowconfigure(1, weight=1)
        
        hdr = ctk.CTkFrame(acc_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(hdr, text="Danh sách Tài khoản (TikTok)", font=("Segoe UI", 13, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="🔄 Refresh", width=60, height=24, command=self._load_accounts).pack(side="right")
        ctk.CTkButton(hdr, text="➕ Thêm nick mới", width=100, height=24, fg_color="#2ecc71", hover_color="#27ae60", command=self._add_new_account).pack(side="right", padx=(0, 10))
        
        self._list_frame = ctk.CTkScrollableFrame(acc_frame, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Log
        log_frame = ctk.CTkFrame(split, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        log_frame.grid(row=0, column=1, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        self._log_widget = LogWidget(log_frame)
        self._log_widget.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _load_accounts(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        if not hasattr(self, '_proxy_entries'):
            self._proxy_entries = {}
        self._proxy_entries.clear()
        
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        
        accounts = [f.name for f in user_dir.glob("tiktok_*.json")]
        if not accounts:
            ctk.CTkLabel(self._list_frame, text="Chưa có tài khoản nào.", text_color=TEXT_DIM).pack(pady=20)
            return
        
        # Load saved proxies
        saved_proxies = self._load_proxies(user_dir)
            
        for acc in accounts:
            row = ctk.CTkFrame(self._list_frame, fg_color=BG_DARK, corner_radius=8, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=4, ipady=2)
            row.grid_columnconfigure(1, weight=1) # Cột proxy tự giãn
            
            var = ctk.BooleanVar(value=False)
            self._checkboxes[acc] = var
            
            # Rút gọn tên hiển thị (bỏ tiktok_ và .json)
            display_acc = acc.replace("tiktok_", "").replace(".json", "")
            if len(display_acc) > 15:
                display_acc = display_acc[:12] + "..."
                
            cb = ctk.CTkCheckBox(row, text=display_acc, variable=var, font=("Segoe UI", 12, "bold"), width=120)
            cb.grid(row=0, column=0, padx=(12, 10), pady=10, sticky="w")
            
            # Proxy Input
            proxy_frame = ctk.CTkFrame(row, fg_color="transparent")
            proxy_frame.grid(row=0, column=1, sticky="ew", padx=10)
            proxy_frame.grid_columnconfigure(1, weight=1)
            
            ctk.CTkLabel(proxy_frame, text="🌐 Proxy:", font=("Segoe UI", 11), text_color=TEXT_DIM).grid(row=0, column=0, padx=(0, 8))
            proxy_entry = ctk.CTkEntry(
                proxy_frame, height=28, font=("Consolas", 11),
                placeholder_text="ip:port:user:pass", fg_color=BG_CARD, border_color=BORDER
            )
            proxy_entry.grid(row=0, column=1, sticky="ew")
            
            # Điền proxy đã lưu (nếu có)
            if acc in saved_proxies and saved_proxies[acc]:
                proxy_entry.insert(0, saved_proxies[acc])
            self._proxy_entries[acc] = proxy_entry
            
            # Nút Đăng nhập thủ công
            btn_login = ctk.CTkButton(
                row, text="🔑 Login", width=70, height=28, font=("Segoe UI", 11, "bold"),
                fg_color=BORDER, hover_color=BG_CARD, text_color=TEXT_MAIN,
                command=lambda a=acc: self._manual_login(a)
            )
            btn_login.grid(row=0, column=2, padx=(0, 12))

    def _add_new_account(self):
        dialog = ctk.CTkInputDialog(text="Nhập tên tài khoản (Viết liền không dấu, VD: nick_1):", title="Thêm tài khoản")
        acc_name = dialog.get_input()
        if not acc_name:
            return
            
        acc_name = acc_name.strip()
        if not acc_name:
            return
            
        if not acc_name.startswith("tiktok_"):
            acc_name = "tiktok_" + acc_name
            
        if not acc_name.endswith(".json"):
            acc_name += ".json"
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        user_dir.mkdir(parents=True, exist_ok=True)
        
        cookie_file = user_dir / acc_name
        if not cookie_file.exists():
            import json
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump([], f)
                
        self._load_accounts()
        self._log(f"Đã tạo {acc_name}. Hãy điền Proxy và bấm '🔑 Đăng nhập' để lưu phiên!", "SUCCESS")

    def _manual_login(self, acc_name):
        proxy_str = self._proxy_entries[acc_name].get().strip()
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)
        
        cookie_path = str(user_dir / acc_name)
        self._log(f"Mở trình duyệt cho {acc_name} để đăng nhập...", "INFO")
        
        def _login_worker():
            import asyncio
            from config.settings import TIKTOK_CONFIG
            from uploader.tiktok_uploader import TikTokUploader
            old_headless = TIKTOK_CONFIG["browser"].get("headless", True)
            TIKTOK_CONFIG["browser"]["headless"] = False
            try:
                async def _run():
                    uploader = TikTokUploader(cookies_file=cookie_path, proxy=proxy_str if proxy_str else None)
                    await uploader._init_browser()
                    self._log(f"Đã mở trình duyệt. Hãy đăng nhập TikTok. Đăng nhập xong, tắt trình duyệt để tự động lưu.", "WARNING")
                    tiktok_page = await uploader.context.new_page()
                    await tiktok_page.goto("https://www.tiktok.com/")
                    # Chờ người dùng đóng tab cuối cùng
                    while len(uploader.context.pages) > 0:
                        try:
                            # Test xem page còn mở không
                            await uploader.context.pages[0].title()
                            await asyncio.sleep(1)
                        except:
                            break
                    await uploader.close()
                asyncio.run(_run())
                self._log(f"Đã đóng trình duyệt và lưu thông tin cho {acc_name}.", "SUCCESS")
            except Exception as e:
                self._log(f"Lỗi khi mở đăng nhập: {e}", "ERROR")
            finally:
                TIKTOK_CONFIG["browser"]["headless"] = old_headless
                
        import threading
        threading.Thread(target=_login_worker, daemon=True).start()

    def _load_proxies(self, user_dir) -> dict:
        """Load proxy config từ file proxies.json."""
        proxy_file = user_dir / "proxies.json"
        if proxy_file.exists():
            try:
                import json
                with open(proxy_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_proxies(self, user_dir):
        """Lưu proxy config vào file proxies.json."""
        import json
        proxies = {}
        for acc, entry in self._proxy_entries.items():
            val = entry.get().strip()
            if val:
                proxies[acc] = val
        proxy_file = user_dir / "proxies.json"
        with open(proxy_file, "w", encoding="utf-8") as f:
            json.dump(proxies, f, indent=2, ensure_ascii=False)

    def _start_farm(self):
        if getattr(self, "is_running", False):
            self._cancel_task()
            self._btn_start.configure(state="disabled", text="Đang dừng...")
            return

        selected = [acc for acc, var in self._checkboxes.items() if var.get()]
        if not selected:
            self._log("Vui lòng chọn ít nhất 1 tài khoản để nuôi!", "WARNING")
            return
            
        try:
            duration = int(self._entry_duration.get())
            ratio = float(self._entry_like_ratio.get())
        except ValueError:
            self._log("Vui lòng nhập đúng định dạng số cho Thời gian và Tỷ lệ Like!", "ERROR")
            return
        
        # Thu thập proxy cho mỗi account
        proxies = {}
        for acc in selected:
            if acc in self._proxy_entries:
                val = self._proxy_entries[acc].get().strip()
                if val:
                    proxies[acc] = val
        
        # Lưu proxy config
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)
            
        self.is_running = True
        self._btn_start.configure(text="⏹ Dừng lại", fg_color=DANGER, hover_color="#c0392b")
        self._log_widget.clear()
        self._log(f"Bắt đầu nuôi {len(selected)} tài khoản...", "INFO")
        
        self._run_in_thread(self._do_farm, selected, duration, ratio, proxies)

    async def _do_farm(self, accounts, duration, ratio, proxies=None):
        import random
        import asyncio
        from uploader.tiktok_uploader import TikTokUploader
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        
        proxies = proxies or {}
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        
        # Giới hạn số luồng (browser) mở cùng lúc để tránh tràn RAM/CPU (Tối đa 3)
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _farm_single_account(acc, idx):
            async with semaphore:
                if self.cancel_flag:
                    return
                    
                cookie_path = str(user_dir / acc)
                proxy_str = proxies.get(acc)
                
                # Lấy tên ngắn gọn để làm tiền tố Log (VD: tiktok_1)
                short_name = acc.split('_')[1] if len(acc.split('_')) > 1 else acc[:8]
                prefix = f"[Nick_{short_name}]"
                
                acc_duration = int(duration * random.uniform(0.7, 1.3))
                acc_ratio = round(ratio * random.uniform(0.7, 1.3), 2)
                acc_ratio = min(acc_ratio, 1.0)
                
                self._log(f"-------------------------------------", "INFO")
                self._log(f"{prefix} 🌱 Bắt đầu (⏱ {acc_duration}m | ❤️ {acc_ratio})", "INFO")
                if proxy_str:
                    display_proxy = proxy_str.split("@")[-1] if "@" in proxy_str else proxy_str
                    self._log(f"{prefix} 🌐 Proxy: {display_proxy}", "INFO")
                else:
                    self._log(f"{prefix} ⚠️ Dùng mạng thật (Không Proxy)", "WARNING")
                
                uploader = TikTokUploader(cookies_file=cookie_path, proxy=proxy_str, window_idx=idx)
                try:
                    def update_cb(msg, lvl="INFO"):
                        # Tránh in log quá rác, thêm tiền tố để phân biệt đa luồng
                        if "Đang xem video" not in msg: 
                            self._log(f"{prefix} {msg}", lvl)
                    
                    await uploader.nurture_account(
                        duration_minutes=acc_duration,
                        like_ratio=acc_ratio,
                        update_callback=update_cb,
                        cancel_check=lambda: self.cancel_flag
                    )
                except Exception as e:
                    self._log(f"{prefix} Lỗi: {e}", "ERROR")
                finally:
                    await uploader.close()
                    self._log(f"{prefix} Đã đóng trình duyệt.", "INFO")

        # Gom tất cả các account thành các tasks và chạy đồng thời (có kiểm soát bởi semaphore)
        tasks = [_farm_single_account(acc, idx) for idx, acc in enumerate(accounts)]
        await asyncio.gather(*tasks)
        
        if self.cancel_flag:
            self._log("⚠️ Đã ngắt quá trình nuôi nick (Stop).", "WARNING")
            
        self._log(f"=====================================", "INFO")
        self._log("🎉 Đã hoàn thành quá trình nuôi nick (Multi-thread) cho tất cả tài khoản!", "SUCCESS")

    def _on_task_done(self):
        super()._on_task_done()
        self.is_running = False
        self.after(0, lambda: self._btn_start.configure(state="normal", text="▶ Bắt đầu nuôi", fg_color=SUCCESS, hover_color="#27ae60"))


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Settings
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.refresh_ui()

    def refresh_ui(self):
        for widget in self.winfo_children():
            widget.destroy()
            
        from auth_client import auth_client
        role = auth_client.user_info.get("role", "user") if auth_client.user_info else "user"
        
        if role == "admin":
            self._build_admin()
        else:
            self._build_user()

    def _build_user(self):
        ctk.CTkLabel(
            self, text="💎  Gói Cước & Nâng Cấp",
            font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        plans = ctk.CTkFrame(self, fg_color="transparent")
        plans.grid(row=1, column=0, sticky="ew")
        plans.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Free Plan
        p1 = ctk.CTkFrame(plans, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        p1.grid(row=0, column=0, padx=10, sticky="nsew")
        ctk.CTkLabel(p1, text="Free", font=("Segoe UI", 20, "bold"), text_color=TEXT_DIM).pack(pady=(20, 10))
        ctk.CTkLabel(p1, text="5 Videos / Ngày", font=("Segoe UI", 14)).pack(pady=5)
        ctk.CTkLabel(p1, text="❌ Thuyết Minh AI", font=("Segoe UI", 14), text_color=DANGER).pack(pady=5)
        ctk.CTkButton(p1, text="Đang Dùng", state="disabled", fg_color=BG_DARK, text_color=TEXT_DIM).pack(pady=20)
        
        # Pro Plan
        p2 = ctk.CTkFrame(plans, fg_color=BG_CARD, corner_radius=12, border_width=2, border_color=ACCENT)
        p2.grid(row=0, column=1, padx=10, sticky="nsew")
        ctk.CTkLabel(p2, text="Pro", font=("Segoe UI", 24, "bold"), text_color=ACCENT).pack(pady=(20, 10))
        ctk.CTkLabel(p2, text="50 Videos / Ngày", font=("Segoe UI", 16, "bold")).pack(pady=5)
        ctk.CTkLabel(p2, text="✅ Thuyết Minh AI", font=("Segoe UI", 16), text_color=SUCCESS).pack(pady=5)
        ctk.CTkButton(p2, text="Nâng cấp ngay", fg_color=ACCENT, hover_color=ACCENT_HOVER, command=lambda: self._show_upgrade_dialog("Pro")).pack(pady=20)
        
        # VIP Plan
        p3 = ctk.CTkFrame(plans, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#f1c40f")
        p3.grid(row=0, column=2, padx=10, sticky="nsew")
        ctk.CTkLabel(p3, text="VIP", font=("Segoe UI", 20, "bold"), text_color="#f1c40f").pack(pady=(20, 10))
        ctk.CTkLabel(p3, text="∞ Không Giới Hạn", font=("Segoe UI", 14)).pack(pady=5)
        ctk.CTkLabel(p3, text="✅ Thuyết Minh AI", font=("Segoe UI", 14), text_color=SUCCESS).pack(pady=5)
        ctk.CTkButton(p3, text="Liên hệ", fg_color="#f1c40f", text_color="#000", hover_color="#f39c12", command=lambda: self._show_upgrade_dialog("VIP")).pack(pady=20)
        
        # ── Gemini API Key (Người dùng tự điền) ──
        ctk.CTkLabel(
            self, text="🔑  Tự Túc API Key (Giảm chi phí, không giới hạn)",
            font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN,
        ).grid(row=2, column=0, sticky="w", pady=(30, 10))
        
        ai_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        ai_frame.grid(row=3, column=0, sticky="ew")
        ai_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(ai_frame, text="Gemini API Key:", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, padx=16, pady=16)
        
        self._entry_user_gemini = ctk.CTkEntry(ai_frame, font=("Consolas", 12), fg_color=BG_DARK, border_color=BORDER, show="*")
        self._entry_user_gemini.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=16)
        
        # Load existing key
        import os
        from dotenv import load_dotenv
        load_dotenv()
        existing_key = os.getenv("GEMINI_API_KEY", "")
        if existing_key:
            self._entry_user_gemini.insert(0, existing_key)
            
        btn_save_key = ctk.CTkButton(
            ai_frame, text="💾 Lưu Key", width=100, font=("Segoe UI", 12, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._save_user_gemini_key
        )
        btn_save_key.grid(row=0, column=2, padx=(0, 16), pady=16)
        
        ctk.CTkLabel(
            ai_frame, text="*Nếu bạn tự nhập API Key, bạn có thể dùng tính năng AI mà KHÔNG cần nâng cấp gói Pro/VIP.", 
            font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 16))

    def _save_user_gemini_key(self):
        gemini_key = self._entry_user_gemini.get().strip()
        from pathlib import Path
        env_path = Path(__file__).parent / ".env"
        env_content = f"GEMINI_API_KEY={gemini_key}\n"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        messagebox.showinfo(
            "Đã lưu",
            "Đã lưu Gemini API Key. Bạn có thể sử dụng các tính năng AI không giới hạn!"
        )

    def _show_upgrade_dialog(self, plan_name):
        win = ctk.CTkToplevel(self)
        win.title(f"Nâng cấp gói {plan_name}")
        win.geometry("400x500")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        
        ctk.CTkLabel(win, text=f"Nâng cấp lên gói {plan_name}", font=("Segoe UI", 20, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(win, text="Vui lòng chuyển khoản với nội dung:", font=("Segoe UI", 14)).pack()
        
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "Unknown") if auth_client.user_info else "Unknown"
        syntax = f"NANG CAP {username} {plan_name.upper()}"
        
        # Copy to clipboard button
        def _copy_syntax():
            self.clipboard_clear()
            self.clipboard_append(syntax)
            self.update()
            
        code_btn = ctk.CTkButton(win, text=syntax + " 📋", font=("Consolas", 16, "bold"), 
                                 fg_color=BG_DARK, text_color=SUCCESS, hover_color=BORDER,
                                 command=_copy_syntax)
        code_btn.pack(pady=10)
        
        import os
        from PIL import Image
        qr_path = os.path.join(os.path.dirname(__file__), "qr.png")
        if os.path.exists(qr_path):
            try:
                img = Image.open(qr_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 200))
                ctk.CTkLabel(win, image=ctk_img, text="").pack(pady=10)
            except Exception as e:
                print(f"Không thể load QR code: {e}")
        else:
            ctk.CTkLabel(win, text="(Bạn có thể copy file qr.png vào thư mục\nchứa tool để hiển thị mã QR ở đây)", font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM).pack(pady=20)
                
        ctk.CTkLabel(win, text="Sau khi chuyển khoản, vui lòng liên hệ Admin\nqua Zalo/Telegram để kích hoạt.", font=("Segoe UI", 12)).pack(pady=10)
        
        ctk.CTkButton(win, text="Đóng", command=win.destroy, fg_color=BORDER, hover_color=BG_CARD).pack(pady=(10, 20))

    def _build_admin(self):
        ctk.CTkLabel(
            self, text="⚙️  Quản trị Hệ thống (Admin Dashboard)",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        
        self.tab_sys = self.tabview.add("Hệ thống")
        self.tab_sys.grid_columnconfigure(0, weight=1)
        self.tab_users = self.tabview.add("Người dùng")
        self.tab_users.grid_columnconfigure(0, weight=1)
        self.tab_plans = self.tabview.add("Gói Cước")
        self.tab_plans.grid_columnconfigure(0, weight=1)
        
        self._build_admin_system(self.tab_sys)
        self._build_admin_users(self.tab_users)
        self._build_admin_plans(self.tab_plans)

    def _build_admin_system(self, parent):
        # ── Cookies section ──────────────────────────────────────────────────
        self._section(parent, "🍪  Cookies", row=0)
        cook = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        cook.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        cook.grid_columnconfigure(1, weight=1)

        for i, (label, placeholder, attr) in enumerate([
            ("Douyin cookies",  "config/cookies/douyin_cookies.txt",  "_entry_douyin"),
            ("TikTok cookies",  "config/cookies/tiktok_cookies.json", "_entry_tiktok"),
        ]):
            ctk.CTkLabel(cook, text=label, font=("Segoe UI", 12),
                         text_color=TEXT_DIM).grid(row=i, column=0, sticky="w", padx=16,
                                                   pady=(14 if i == 0 else 4, 4))
            row_f = ctk.CTkFrame(cook, fg_color="transparent")
            row_f.grid(row=i, column=1, sticky="ew", padx=(0, 16),
                       pady=(14 if i == 0 else 4, 4 if i == 0 else 14))
            row_f.grid_columnconfigure(0, weight=1)
            entry = ctk.CTkEntry(row_f, placeholder_text=placeholder,
                                  font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
            entry.grid(row=0, column=0, sticky="ew")
            ctk.CTkButton(row_f, text="📁", width=36, height=28,
                           fg_color=BORDER, hover_color=BG_CARD,
                           command=lambda e=entry: self._pick_file(e),
                           ).grid(row=0, column=1, padx=(8, 0))
            setattr(self, attr, entry)

        # Pre-fill defaults
        self._entry_douyin.insert(0, "config/cookies/douyin_cookies.txt")
        self._entry_tiktok.insert(0, "config/cookies/tiktok_cookies.json")

        # ── Gemini AI section ──────────────────────────────────────────────────
        self._section(parent, "🧠  AI Translation (Gemini)", row=2)
        ai = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                           border_width=1, border_color=BORDER)
        ai.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        ai.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ai, text="Gemini API Key", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 14))
        self._entry_gemini = ctk.CTkEntry(ai, font=("Consolas", 11),
                                             fg_color=BG_DARK, border_color=BORDER, show="*")
        
        # Load from .env if available
        import os
        from dotenv import load_dotenv
        load_dotenv()
        existing_key = os.getenv("GEMINI_API_KEY", "")
        if existing_key:
            self._entry_gemini.insert(0, existing_key)
            
        self._entry_gemini.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(14, 14))
        self._entry_gemini.configure(state="disabled") # KHÓA (Sử dụng Proxy Server)

        # ── TikTok section ───────────────────────────────────────────────────
        self._section(parent, "🎵  TikTok Upload", row=4)
        tt = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                           border_width=1, border_color=BORDER)
        tt.grid(row=5, column=0, sticky="ew", pady=(0, 16))
        tt.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tt, text="Max posts/ngày", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        self._entry_maxposts = ctk.CTkEntry(tt, width=80, font=("Segoe UI", 12),
                                             fg_color=BG_DARK, border_color=BORDER)
        self._entry_maxposts.insert(0, "4")
        self._entry_maxposts.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(14, 4))

        ctk.CTkLabel(tt, text="Hashtags mặc định", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=(4, 14))
        self._entry_hashtags = ctk.CTkEntry(
            tt, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_hashtags.insert(0, "#fyp #xuhuong #tiktokvietnam #trending #viral")
        self._entry_hashtags.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(4, 14))

        # Save button
        ctk.CTkButton(
            parent, text="💾  Lưu cài đặt", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save,
        ).grid(row=6, column=0, sticky="w", pady=(4, 0))

    def _section(self, parent, title, row):
        ctk.CTkLabel(
            parent, text=title,
            font=("Segoe UI", 13, "bold"), text_color=TEXT_DIM,
        ).grid(row=row, column=0, sticky="w", pady=(8, 4))

    def _pick_file(self, entry: ctk.CTkEntry):
        path = filedialog.askopenfilename(
            filetypes=[("All files", "*.*")],
            initialdir=str(Path(__file__).parent),
        )
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _save(self):
        gemini_key = self._entry_gemini.get().strip()
        env_path = Path(__file__).parent / ".env"
        
        # Ghi API key ra file .env
        env_content = f"GEMINI_API_KEY={gemini_key}\n"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
            
        messagebox.showinfo(
            "Đã lưu",
            "Cài đặt đã được ghi nhận.\n"
            "(Lưu ý: API Key sẽ có hiệu lực ngay trong lần dịch tiếp theo.)"
        )

    # ── ADMIN: User Management ────────────────────────────────────────────────
    def _build_admin_users(self, parent):
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(top_bar, text="Danh sách Tài khoản", font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkButton(top_bar, text="🔄 Làm mới", width=80, height=28, fg_color=BORDER, hover_color=BG_CARD, command=self._load_users).pack(side="right", padx=5)
        ctk.CTkButton(top_bar, text="➕ Thêm User", width=100, height=28, fg_color=SUCCESS, hover_color="#27ae60", command=self._add_user_dialog).pack(side="right", padx=5)
        
        self.user_list_frame = ctk.CTkScrollableFrame(parent, fg_color=BG_DARK, border_color=BORDER, border_width=1, height=350)
        self.user_list_frame.grid(row=1, column=0, sticky="nsew")
        parent.grid_rowconfigure(1, weight=1)
        
        # Gọi load user
        self.after(200, self._load_users)

    def _load_users(self):
        for w in self.user_list_frame.winfo_children():
            w.destroy()
            
        from auth_client import auth_client
        success, users = auth_client.admin_get_users()
        if not success:
            ctk.CTkLabel(self.user_list_frame, text=f"Lỗi: {users}", text_color=DANGER).pack(pady=20)
            return
            
        if not users:
            ctk.CTkLabel(self.user_list_frame, text="Không có dữ liệu", text_color=TEXT_DIM).pack(pady=20)
            return
            
        for u in users:
            card = ctk.CTkFrame(self.user_list_frame, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=4, padx=10)
            
            info_str = f"👤 {u['username']}  |  🎖️ Role: {u['role']}  |  💎 Plan: {u['plan_name']}"
            ctk.CTkLabel(card, text=info_str, font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=15, pady=10)
            
            ctk.CTkButton(card, text="🗑 Xóa", width=60, height=26, fg_color=DANGER, hover_color="#c0392b",
                          command=lambda user_id=u['id']: self._delete_user(user_id)).pack(side="right", padx=(5, 15), pady=10)
            ctk.CTkButton(card, text="✏️ Sửa", width=60, height=26, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          command=lambda user=u: self._edit_user_dialog(user)).pack(side="right", padx=5, pady=10)

    def _add_user_dialog(self):
        self._user_form_dialog()
        
    def _edit_user_dialog(self, user):
        self._user_form_dialog(user)
        
    def _user_form_dialog(self, user=None):
        win = ctk.CTkToplevel(self)
        title = "Sửa Tài khoản" if user else "Thêm Tài khoản"
        win.title(title)
        win.geometry("400x350")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        
        ctk.CTkLabel(win, text=title, font=("Segoe UI", 20, "bold")).pack(pady=(20, 10))
        
        entry_user = ctk.CTkEntry(win, placeholder_text="Username", width=250)
        entry_user.pack(pady=5)
        if user:
            entry_user.insert(0, user["username"])
            entry_user.configure(state="disabled")
            
        entry_pass = ctk.CTkEntry(win, placeholder_text="Password" + (" (Bỏ trống nếu không đổi)" if user else ""), width=250, show="*")
        entry_pass.pack(pady=5)
        
        opt_role = ctk.CTkOptionMenu(win, values=["user", "admin"], width=250)
        if user: opt_role.set(user["role"])
        else: opt_role.set("user")
        opt_role.pack(pady=5)
        
        opt_plan = ctk.CTkOptionMenu(win, values=["Free", "Pro", "VIP"], width=250)
        if user: opt_plan.set(user["plan_name"])
        else: opt_plan.set("Free")
        opt_plan.pack(pady=5)
        
        def _save():
            from auth_client import auth_client
            u_name = entry_user.get()
            u_pass = entry_pass.get()
            u_role = opt_role.get()
            u_plan = opt_plan.get()
            
            if not user:
                if not u_name or not u_pass:
                    messagebox.showerror("Lỗi", "Username và Password là bắt buộc")
                    return
                success, msg = auth_client.admin_create_user(u_name, u_pass, u_role, u_plan)
            else:
                success, msg = auth_client.admin_update_user(user["id"], password=u_pass if u_pass else None, role=u_role, plan_name=u_plan)
                
            if success:
                win.destroy()
                self._load_users()
            else:
                messagebox.showerror("Lỗi", msg)
                
        ctk.CTkButton(win, text="Lưu", width=250, command=_save, fg_color=SUCCESS, hover_color="#27ae60").pack(pady=20)

    def _delete_user(self, user_id):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa tài khoản này?"):
            from auth_client import auth_client
            success, msg = auth_client.admin_delete_user(user_id)
            if success:
                self._load_users()
            else:
                messagebox.showerror("Lỗi", msg)

    def _build_admin_plans(self, parent):
        ctk.CTkLabel(parent, text="Quản lý Gói cước (Plans)", font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(pady=10)
        
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.plans_list_frame = ctk.CTkScrollableFrame(frame, fg_color=BG_CARD)
        self.plans_list_frame.pack(fill="both", expand=True)
        
        btn_refresh = ctk.CTkButton(parent, text="Làm mới danh sách", command=self._refresh_plans_list)
        btn_refresh.pack(pady=10)
        
        self._refresh_plans_list()

    def _refresh_plans_list(self):
        for widget in self.plans_list_frame.winfo_children():
            widget.destroy()
            
        import requests
        from auth_client import auth_client, API_BASE_URL
        
        try:
            resp = requests.get(f"{API_BASE_URL}/admin/plans", headers={
                "Authorization": f"Bearer {auth_client.token}"
            }, timeout=5)
            if resp.status_code == 200:
                plans = resp.json()
                for i, p in enumerate(plans):
                    item = ctk.CTkFrame(self.plans_list_frame, fg_color=BG_DARK, corner_radius=8)
                    item.pack(fill="x", pady=5, padx=5)
                    
                    info = f"Gói: {p['name']} | Max Limit: {p['max_daily_videos']} | AI Script: {'Có' if p['can_use_ai_script'] else 'Không'}"
                    ctk.CTkLabel(item, text=info, font=("Segoe UI", 12)).pack(side="left", padx=10, pady=10)
                    
                    btn_edit = ctk.CTkButton(item, text="Sửa", width=60, command=lambda p=p: self._show_edit_plan_dialog(p))
                    btn_edit.pack(side="right", padx=10)
            else:
                ctk.CTkLabel(self.plans_list_frame, text="Lỗi khi tải danh sách Gói Cước").pack(pady=10)
        except Exception as e:
            ctk.CTkLabel(self.plans_list_frame, text=f"Lỗi kết nối: {e}").pack(pady=10)

    def _show_edit_plan_dialog(self, plan):
        win = ctk.CTkToplevel(self)
        win.title(f"Sửa Gói Cước: {plan['name']}")
        win.geometry("400x300")
        win.grab_set()
        
        ctk.CTkLabel(win, text=f"Chỉnh sửa giới hạn cho gói {plan['name']}", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        ctk.CTkLabel(win, text="Giới Hạn Video / Ngày:").pack(pady=(10, 0))
        entry_limit = ctk.CTkEntry(win, width=200)
        entry_limit.insert(0, str(plan['max_daily_videos']))
        entry_limit.pack(pady=5)
        
        switch_ai = ctk.CTkSwitch(win, text="Cho phép dùng AI Script")
        if plan['can_use_ai_script']:
            switch_ai.select()
        switch_ai.pack(pady=10)
        
        def save():
            try:
                limit = int(entry_limit.get())
            except:
                messagebox.showerror("Lỗi", "Giới hạn phải là số nguyên")
                return
                
            data = {
                "max_daily_videos": limit,
                "can_use_ai_script": switch_ai.get() == 1
            }
            
            import requests
            from auth_client import auth_client, API_BASE_URL
            
            try:
                resp = requests.put(f"{API_BASE_URL}/admin/plans/{plan['id']}", json=data, headers={
                    "Authorization": f"Bearer {auth_client.token}"
                }, timeout=5)
                
                if resp.status_code == 200:
                    messagebox.showinfo("Thành công", "Đã cập nhật Gói cước thành công!")
                    win.destroy()
                    self._refresh_plans_list()
                else:
                    messagebox.showerror("Lỗi", f"Không thể lưu: {resp.text}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi kết nối: {e}")
                
        ctk.CTkButton(win, text="Lưu thay đổi", command=save, fg_color=SUCCESS, hover_color="#27ae60").pack(pady=20)

# ═══════════════════════════════════════════════════════════════════════════════
#  Login Window
# ═══════════════════════════════════════════════════════════════════════════════
from auth_client import auth_client

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        
        self.title("Đăng nhập Hệ thống")
        self.geometry("400x320")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        ctk.CTkLabel(
            self, text="DouyinBot SaaS",
            font=("Segoe UI", 28, "bold"), text_color=TEXT_MAIN
        ).pack(pady=(30, 20))
        
        self.entry_user = ctk.CTkEntry(self, placeholder_text="Tên đăng nhập", width=250)
        self.entry_user.pack(pady=10)
        
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Mật khẩu", show="*", width=250)
        self.entry_pass.pack(pady=10)
        
        self.btn_login = ctk.CTkButton(
            self, text="Đăng nhập", width=250, height=40,
            command=self._do_login, font=("Segoe UI", 14, "bold")
        )
        self.btn_login.pack(pady=20)
        
    def _do_login(self):
        user = self.entry_user.get()
        pwd = self.entry_pass.get()
        self.btn_login.configure(state="disabled", text="Đang xử lý...")
        
        def run():
            success, msg = auth_client.login(user, pwd)
            self.after(0, self._handle_result, success, msg)
            
        import threading
        threading.Thread(target=run, daemon=True).start()
        
    def _handle_result(self, success, msg):
        if success:
            self.grab_release()
            self.destroy()
            self.on_success()
        else:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", msg)
            self.btn_login.configure(state="normal", text="Đăng nhập")

    def _on_close(self):
        self.master.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  Main App Window
# ═══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    TABS = [
        ("📊", "Dashboard", DashboardTab),
        ("🔍", "Crawl",     CrawlTab),
        ("🎞️", "Process",   ProcessTab),
        ("📤", "Upload",    UploadTab),
        ("🤖", "Auto",      AutoTab),
        ("🌱", "Farm",      FarmTab),
        ("⚙️", "Settings",  SettingsTab),
    ]

    def __init__(self):
        super().__init__()

        self.title("🎬 Douyin → TikTok Auto-Uploader")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DARK)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        
        # Check login
        success, _ = auth_client.get_me()
        if success:
            self._nav_buttons[0].set_active(True)
            self._show_tab(0)
            self._update_user_ui()
        else:
            self.withdraw() # Ẩn main window
            LoginWindow(self, self._on_login_success)

    def _update_user_ui(self):
        # Cập nhật UI theo gói cước
        if auth_client.user_info:
            plan = auth_client.user_info.get("plan_name", "Unknown")
            user = auth_client.user_info.get("username", "Unknown")
            rem = auth_client.user_info.get("remaining", 0)
            if hasattr(self, "lbl_user_info"):
                self.lbl_user_info.configure(text=f"👤 User: {user}\n💎 Plan: {plan}\n📦 Còn lại: {rem} vid")
            
            # Cập nhật quyền hạn ở tab Process
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 2:
                process_tab = self._tab_frames[2]
                can_use_ai = auth_client.user_info.get("can_use_ai", False)
                if hasattr(process_tab, "_sw_dubbing"):
                    if not can_use_ai:
                        process_tab._sw_dubbing.deselect()
                        process_tab._sw_dubbing.configure(state="disabled", text="🎙️ Thuyết minh AI (Cần gói Pro+)")
                    else:
                        process_tab._sw_dubbing.configure(state="normal", text="🎙️ Thuyết minh AI (Đọc Vietsub tự động)")
                        
            # Update Dashboard
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 0:
                dashboard_tab = self._tab_frames[0]
                if hasattr(dashboard_tab, "refresh_stats"):
                    dashboard_tab.refresh_stats(silent=True)
                    
            # Update Settings UI based on role
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 5:
                settings_tab = self._tab_frames[5]
                if hasattr(settings_tab, "refresh_ui"):
                    settings_tab.refresh_ui()
                    
            # Update UploadTab accounts
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 3:
                upload_tab = self._tab_frames[3]
                if hasattr(upload_tab, "_refresh_accounts"):
                    upload_tab._refresh_accounts()
                if hasattr(upload_tab, "_refresh_youtube_accounts"):
                    upload_tab._refresh_youtube_accounts()
                    
            # Update AutoTab accounts
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 4:
                auto_tab = self._tab_frames[4]
                if hasattr(auto_tab, "_refresh_accounts"):
                    auto_tab._refresh_accounts()

    def _on_login_success(self):
        auth_client.get_me()
        self.deiconify() # Hiện lại main window
        self._nav_buttons[0].set_active(True)
        self._show_tab(0)
        self._update_user_ui()

    def _do_logout(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn đăng xuất?"):
            auth_client.logout()
            self.withdraw()
            LoginWindow(self, self._on_login_success)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(97, weight=1)  # pushes bottom items down

        # Logo
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=16, pady=(30, 24))
        ctk.CTkLabel(
            logo, text="✨",
            font=("Segoe UI", 32), text_color=ACCENT
        ).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(
            logo, text="DouyinBot",
            font=("Segoe UI", 20, "bold"), text_color=TEXT_MAIN,
        ).pack(side="left")

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color="#1E293B").grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 20)
        )

        # Nav buttons
        self._nav_buttons: list[SidebarButton] = []
        for i, (icon, label, _) in enumerate(self.TABS):
            btn = SidebarButton(sidebar, icon=icon, text=label,
                                command=lambda idx=i: self._nav(idx))
            btn.grid(row=i + 2, column=0, sticky="ew", padx=12, pady=3)
            self._nav_buttons.append(btn)

        # Premium User Profile Card
        self.user_card = ctk.CTkFrame(sidebar, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#334155")
        self.user_card.grid(row=98, column=0, pady=(20, 10), padx=12, sticky="ew")
        
        self.lbl_user_info = ctk.CTkLabel(
            self.user_card, text="👤  Chưa đăng nhập",
            font=("Segoe UI", 12), text_color=TEXT_MAIN, justify="left"
        )
        self.lbl_user_info.pack(padx=12, pady=12, anchor="w")

        # Logout button
        btn_logout = ctk.CTkButton(
            sidebar, text="🚪 Đăng xuất", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#EF4444", hover_color="#B91C1C", corner_radius=8,
            command=self._do_logout
        )
        btn_logout.grid(row=99, column=0, pady=(0, 20), padx=12, sticky="ew")

        # Bottom: version
        ctk.CTkLabel(
            sidebar, text="v1.0.0 (Premium)",
            font=("Segoe UI", 10), text_color=TEXT_DIM,
        ).grid(row=100, column=0, pady=12)

    # ── Content area ─────────────────────────────────────────────────────────
    def _build_content(self):
        self._content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # Build all tab frames (hidden by default)
        self._tab_frames: list[ctk.CTkFrame] = []
        for _, _, TabClass in self.TABS:
            frame = TabClass(self._content, app=self)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_remove()
            self._tab_frames.append(frame)

    def _nav(self, idx: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == idx)
        self._show_tab(idx)

    def _show_tab(self, idx: int):
        for frame in self._tab_frames:
            frame.grid_remove()
        self._tab_frames[idx].grid()


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
