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
            font=("Segoe UI", 13),
            fg_color="transparent",
            text_color=TEXT_DIM,
            hover_color=BG_CARD,
            anchor="w",
            height=44,
            corner_radius=10,
            **kwargs,
        )

    def set_active(self, active: bool):
        if active:
            self.configure(fg_color=BG_CARD, text_color=ACCENT)
        else:
            self.configure(fg_color="transparent", text_color=TEXT_DIM)


# ═══════════════════════════════════════════════════════════════════════════════
#  Mixin: chạy task trên thread nền, route log về queue
# ═══════════════════════════════════════════════════════════════════════════════
class TaskMixin:
    """Mixin cho các Tab cần chạy lệnh Python nền."""

    def _run_in_thread(self, func, *args, **kwargs):
        """Chạy coroutine hoặc hàm sync trên thread riêng."""
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

    def _log(self, msg: str, level: str = "INFO"):
        """Ghi log (gọi được từ thread bất kỳ)."""
        # Mỗi tab phải bind self._log_widget
        self.after(0, lambda: self._log_widget.append(msg, level))

    def _on_task_done(self):
        """Gọi sau khi task xong."""
        pass


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

        # Stats cards
        self._card_crawled   = StatsCard(self, "Đã Crawl",   color=ACCENT)
        self._card_processed = StatsCard(self, "Đã Xử lý",   color="#9b59b6")
        self._card_posted    = StatsCard(self, "Đã Upload",   color=SUCCESS)
        self._card_pending   = StatsCard(self, "Chờ Upload",  color=WARNING)

        for col, card in enumerate([
            self._card_crawled, self._card_processed,
            self._card_posted, self._card_pending
        ]):
            card.grid(row=1, column=col, padx=6, pady=4, sticky="ew")

        # Recent activity log
        log_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        log_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=4, pady=(20, 0))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

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
            s  = db.get_stats()
            self._card_crawled.set_value(s.get("total_crawled", 0))
            self._card_processed.set_value(s.get("total_processed", 0))
            self._card_posted.set_value(s.get("total_posted", 0))
            self._card_pending.set_value(s.get("pending_post", 0))
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
        input_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                                   border_width=1, border_color=BORDER)
        input_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        input_card.grid_columnconfigure(1, weight=1)

        # Mode chọn
        ctk.CTkLabel(input_card, text="Chế độ", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))

        self._mode_var = ctk.StringVar(value="urls")
        mode_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        mode_frame.grid(row=0, column=1, sticky="w", padx=0, pady=(14, 4))
        for val, lbl in [("urls", "URL cụ thể"), ("profile", "Profile user"), ("file", "File URLs")]:
            ctk.CTkRadioButton(
                mode_frame, text=lbl, variable=self._mode_var, value=val,
                command=self._on_mode_change,
                font=("Segoe UI", 12), text_color=TEXT_MAIN,
            ).pack(side="left", padx=10)

        # URL input
        ctk.CTkLabel(input_card, text="Douyin URLs", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=1, column=0, sticky="nw", padx=16, pady=4)

        url_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        url_frame.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=4)
        url_frame.grid_columnconfigure(0, weight=1)

        self._txt_urls = ctk.CTkTextbox(
            url_frame, height=110, font=("Consolas", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._txt_urls.grid(row=0, column=0, sticky="ew")
        self._txt_urls.insert(
            "0.0",
            "# Paste URL hoặc cả đoạn text từ app Douyin đều được\n"
            "# VD: 5.33 07/15 ... https://v.douyin.com/K_UlIwJrDJY/ 复制此链接...\n"
            "# Tool sẽ tự trích xuất URL ra\n"
        )

        # Hint label
        ctk.CTkLabel(
            url_frame,
            text="💡 Mỗi dòng 1 URL — Hỗ trợ: v.douyin.com  |  www.douyin.com/video/  |  modal_id=...",
            font=("Segoe UI", 10), text_color=TEXT_DIM, anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

        # Profile row
        ctk.CTkLabel(input_card, text="Profile URL", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=2, column=0, sticky="w", padx=16, pady=4)
        self._entry_profile = ctk.CTkEntry(
            input_card, placeholder_text="https://www.douyin.com/user/...",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_profile.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=4)

        # Count row
        ctk.CTkLabel(input_card, text="Số video", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=3, column=0, sticky="w", padx=16, pady=4)
        self._spin_count = ctk.CTkEntry(
            input_card, width=80, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._spin_count.insert(0, "10")
        self._spin_count.grid(row=3, column=1, sticky="w", padx=(0, 16), pady=(4, 14))

        # File row
        file_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        file_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        file_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(file_frame, text="File URLs", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._entry_file = ctk.CTkEntry(
            file_frame, placeholder_text="urls.txt",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_file.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(
            file_frame, text="📁 Chọn", width=90, height=30,
            font=("Segoe UI", 11), fg_color=BORDER, hover_color=BG_CARD,
            command=self._browse_file,
        ).grid(row=0, column=2, padx=(8, 0))

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self._btn_crawl = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Crawl", height=42, font=("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._start_crawl,
        )
        self._btn_crawl.pack(side="left", padx=(0, 10))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(side="left")

        # Log
        self._log_widget = LogWidget(self)
        self._log_widget.grid(row=3, column=0, sticky="nsew")

        self._on_mode_change()

    def _on_mode_change(self):
        mode = self._mode_var.get()
        self._txt_urls.configure(state="normal" if mode == "urls" else "disabled")
        self._entry_profile.configure(state="normal" if mode == "profile" else "disabled")
        self._entry_file.configure(state="normal" if mode == "file" else "disabled")

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
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        self._log(f"Crawling {len(urls)} URLs...", "INFO")
        results = asyncio.run(crawler.crawl_multiple_videos(urls))
        self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")

    def _do_crawl_profile(self, profile, count):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        self._log(f"Crawling profile ({count} videos)...", "INFO")
        results = asyncio.run(crawler.crawl_user_profile(profile, max_videos=count))
        self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")

    def _do_crawl_file(self, file_path):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        urls = Path(file_path).read_text(encoding="utf-8").strip().splitlines()
        urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
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
        self.grid_rowconfigure(3, weight=1) # Row 3 cho danh sách video
        self.grid_rowconfigure(5, weight=1) # Row 5 cho log widget
        self._checkboxes = {} # Lưu trạng thái {video_id: BooleanVar}
        self._selected_music_path = None
        self._build()
        self.after(200, self._load_videos) # Load video khi tab mở

    def _build(self):
        ctk.CTkLabel(
            self, text="🎞️  Xử lý Video",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Options card
        opts = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        opts.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(opts, text="Title overlay", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        self._entry_title = ctk.CTkEntry(
            opts, placeholder_text="Nhảy đẹp quá 😍🔥  (để trống = Dịch tự động tiêu đề gốc)",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_title.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(14, 4))

        # Limit
        ctk.CTkLabel(opts, text="Giới hạn video", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self._entry_limit = ctk.CTkEntry(
            opts, width=80, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_limit.insert(0, "10")
        self._entry_limit.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(4, 14))

        # Switches & Cấu hình (Chia làm 3 dòng để không bị tràn)
        config_frame = ctk.CTkFrame(opts, fg_color="transparent")
        config_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

        # --- Dòng 1: Hình ảnh & Âm thanh ---
        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))

        self._sw_mirror = ctk.CTkSwitch(row1, text="Mirror (Lật video chống reup)", font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_mirror.select()
        self._sw_mirror.pack(side="left", padx=(0, 20))

        self._sw_music = ctk.CTkSwitch(row1, text="Ghép nhạc (Tránh bản quyền âm thanh)", font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_music.select()
        self._sw_music.pack(side="left", padx=(0, 10))

        self._btn_open_music = ctk.CTkButton(row1, text="🎵 Chọn file nhạc...", width=110, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._select_music_file)
        self._btn_open_music.pack(side="left", padx=(0, 10))
        
        self._lbl_music_file = ctk.CTkLabel(row1, text="(Đang dùng nhạc Tóp Tóp mặc định)", font=("Segoe UI", 11), text_color=TEXT_DIM)
        self._lbl_music_file.pack(side="left")

        # --- Dòng 2: Xử lý Chữ & Vietsub ---
        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))

        self._sw_subtitle = ctk.CTkSwitch(row2, text="Auto-Vietsub (Tự động dịch & gắn sub Việt)", font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_subtitle.select()
        self._sw_subtitle.pack(side="left", padx=(0, 20))

        # --- Dòng 3: Thuyết minh AI ---
        row3 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row3.pack(fill="x")

        self._sw_dubbing = ctk.CTkSwitch(row3, text="🎙️ Thuyết minh AI (Đọc Vietsub tự động)", font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_dubbing.select()
        self._sw_dubbing.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row3, text="Giọng đọc:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(5, 5))
        self._opt_voice = ctk.CTkOptionMenu(row3, values=["Giọng Nam (NamMinh)", "Giọng Nữ (HoaiMy)"], width=140, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD)
        self._opt_voice.set("Giọng Nam (NamMinh)")
        self._opt_voice.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row3, text="Tốc độ đọc:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_tts_rate = ctk.CTkEntry(row3, width=65, placeholder_text="0%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_tts_rate.insert(0, "0%")
        self._entry_tts_rate.pack(side="left")
        
        # Danh sách chọn video
        list_header = ctk.CTkFrame(self, fg_color="transparent")
        list_header.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(list_header, text="Danh sách Video đã tải (chọn để xử lý):", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkButton(list_header, text="🔄 Refresh", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._load_videos).pack(side="right")
        ctk.CTkButton(list_header, text="🗑 Xóa đã chọn", width=100, height=24, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_selected).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="☑ Chọn / Bỏ chọn", width=110, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._toggle_selection).pack(side="right", padx=(0, 10))
        
        self._video_list_frame = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._video_list_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 12))

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="ew", pady=(0, 12))

        self._btn_process = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Xử lý", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#9b59b6", hover_color="#8e44ad",
            command=self._start_process,
        )
        self._btn_process.pack(side="left", padx=(0, 10))

        self._btn_bypass = ctk.CTkButton(
            btn_row, text="⏩ Chuyển thẳng Upload", height=42,
            font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._bypass_process,
        )
        self._btn_bypass.pack(side="left", padx=(0, 10))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(side="left")

        # Log
        self._log_widget = LogWidget(self)
        self._log_widget.grid(row=5, column=0, sticky="nsew")

    def _load_videos(self):
        """Hiển thị danh sách video đã tải vào scrollable frame."""
        # Xóa các checkbox cũ
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()

        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        # Lấy 100 video tải gần nhất để hiển thị
        videos = db.get_downloaded_videos(limit=100)
        
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
        self._btn_process.configure(state="disabled")
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
        PROCESSOR_CONFIG["mirror"] = self._sw_mirror.get() == 1
        PROCESSOR_CONFIG["replace_audio"] = self._sw_music.get() == 1
        PROCESSOR_CONFIG["add_text"] = False
        PROCESSOR_CONFIG["specific_music_path"] = getattr(self, "_selected_music_path", None)
        PROCESSOR_CONFIG["auto_subtitle"] = self._sw_subtitle.get() == 1
        PROCESSOR_CONFIG["ai_dubbing"] = self._sw_dubbing.get() == 1
        
        # Parse TTS Options
        voice_sel = self._opt_voice.get()
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
            videos = db.get_downloaded_videos(limit=limit)
            for v in videos:
                titles[v["video_id"]] = title
                
        results = processor.process_downloaded_videos(titles=titles, limit=limit, video_ids=selected_ids)
        self._log(f"✅ Đã xử lý {len(results)} videos!", "SUCCESS")
        # Load lại danh sách sau khi xử lý xong
        self.after(0, self._load_videos)
        self._on_task_done()

    def _on_task_done(self):
        self.after(0, lambda: self._btn_process.configure(state="normal"))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS))


# ═══════════════════════════════════════════════════════════════════════════════
#  InputJSONWindow
# ═══════════════════════════════════════════════════════════════════════════════
class InputJSONWindow(ctk.CTkToplevel):
    def __init__(self, master, on_close_callback=None):
        super().__init__(master)
        self.title("Nhập Cookies JSON")
        self.geometry("500x400")
        self.on_close_callback = on_close_callback
        
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Tên tài khoản (vd: tiktok_acc1):", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        
        self.name_entry = ctk.CTkEntry(self, font=("Segoe UI", 12))
        self.name_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=0)
        self.name_entry.insert(0, "tiktok_")
        
        ctk.CTkLabel(self, text="Dán nội dung JSON (từ Cookie Editor):", font=("Segoe UI", 12)).grid(row=2, column=0, sticky="w", padx=16, pady=(10, 4))
        
        self.json_text = ctk.CTkTextbox(self, font=("Consolas", 11), wrap="word")
        self.json_text.grid(row=3, column=0, sticky="nsew", padx=16, pady=0)

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
            
            from config.settings import COOKIES_DIR
            with open(COOKIES_DIR / name, "w", encoding="utf-8") as f:
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
            
        from config.settings import COOKIES_DIR
        accounts = [f.name for f in COOKIES_DIR.glob("tiktok_*.json")]
        if not accounts and (COOKIES_DIR / "tiktok_cookies.json").exists():
            accounts = ["tiktok_cookies.json"]
            
        for acc in accounts:
            item = ctk.CTkFrame(self._list_frame, fg_color=BG_CARD, corner_radius=6)
            item.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(item, text=acc, font=("Consolas", 12)).pack(side="left", padx=10, pady=8)
            ctk.CTkButton(item, text="Xóa", width=50, fg_color=DANGER, hover_color="#c0392b", command=lambda a=acc: self._delete_account(a)).pack(side="right", padx=10, pady=8)

    def _upload_account(self):
        path = filedialog.askopenfilename(
            title="Chọn file cookie JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            from config.settings import COOKIES_DIR
            try:
                dest_name = os.path.basename(path)
                if not dest_name.startswith("tiktok_"):
                    dest_name = f"tiktok_{dest_name}"
                shutil.copy2(path, COOKIES_DIR / dest_name)
                messagebox.showinfo("Thành công", f"Đã tải lên tài khoản: {dest_name}")
                self._load_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể tải lên file: {e}")

    def _input_json(self):
        InputJSONWindow(self, on_close_callback=self._load_accounts)

    def _delete_account(self, filename):
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa {filename}?"):
            from config.settings import COOKIES_DIR
            try:
                (COOKIES_DIR / filename).unlink(missing_ok=True)
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
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) # Row 3 cho danh sách video
        self.grid_rowconfigure(5, weight=1) # Row 5 cho log widget
        self._checkboxes = {}
        self._video_accounts = {}
        self._build()
        self.after(200, self._load_videos)

    @staticmethod
    def _get_tiktok_accounts():
        from config.settings import COOKIES_DIR
        accounts = [f.name for f in COOKIES_DIR.glob("tiktok_*.json")]
        return accounts if accounts else ["tiktok_cookies.json"]

    def _build(self):
        ctk.CTkLabel(
            self, text="📤  Upload lên TikTok",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Options card
        opts = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        opts.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(opts, text="Số video upload", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 14))
        self._entry_limit = ctk.CTkEntry(
            opts, width=80, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_limit.insert(0, "4")
        self._entry_limit.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(14, 14))
        
        self._sw_cleanup_upload = ctk.CTkSwitch(opts, text="🧹 Tự động dọn dẹp file sau khi upload",
                                                font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_cleanup_upload.select()
        self._sw_cleanup_upload.grid(row=0, column=2, sticky="w", padx=(20, 16), pady=(14, 14))

        acc_row = ctk.CTkFrame(opts, fg_color="transparent")
        acc_row.grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 14))
        
        ctk.CTkLabel(acc_row, text="Tài khoản mặc định:", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(side="left", padx=(0, 10))
        accounts = self._get_tiktok_accounts()
        self._opt_account = ctk.CTkOptionMenu(
            acc_row, values=accounts, font=("Segoe UI", 12), width=130,
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account.pack(side="left")
        
        self._btn_apply_acc = ctk.CTkButton(
            acc_row, text="Áp dụng cho video đã chọn", width=120, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._apply_account_to_all
        )
        self._btn_apply_acc.pack(side="left", padx=(10, 0))
        
        self._btn_manage_acc = ctk.CTkButton(
            acc_row, text="⚙ Quản lý", width=70, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._open_account_manager
        )
        self._btn_manage_acc.pack(side="left", padx=(10, 0))

        # Danh sách chọn video
        list_header = ctk.CTkFrame(self, fg_color="transparent")
        list_header.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(list_header, text="Danh sách Video đã xử lý (chọn để upload):", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkButton(list_header, text="🔄 Refresh", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._load_videos).pack(side="right")
        ctk.CTkButton(list_header, text="🗑 Xóa đã chọn", width=100, height=24, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_selected).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="⏪ Về Process", width=100, height=24, fg_color="#f39c12", hover_color="#e67e22", command=self._revert_to_process).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="☑ Chọn / Bỏ chọn", width=110, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._toggle_selection).pack(side="right", padx=(0, 10))
        
        self._video_list_frame = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._video_list_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 12))

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="ew", pady=(0, 12))

        self._btn_upload = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Upload", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._start_upload,
        )
        self._btn_upload.pack(side="left", padx=(0, 10))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(side="left")

        # Log
        self._log_widget = LogWidget(self)
        self._log_widget.grid(row=5, column=0, sticky="nsew")

    def _load_videos(self):
        """Hiển thị danh sách video đã processed vào scrollable frame."""
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        self._video_accounts.clear()
        self._custom_captions = {}

        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        videos = db.get_pending_videos(limit=100)
        
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
            card.pack(fill="x", pady=4, padx=10)
            
            var = ctk.BooleanVar(value=True)
            self._checkboxes[vid] = var
            
            # Checkbox bên trái
            cb = ctk.CTkCheckBox(
                card, text="", variable=var, width=24,
                command=self._update_selected_count
            )
            cb.pack(side="left", padx=(10, 0), pady=10)
            
            # Action & Account Selector for this video (pack bên phải trước)
            acc_frame = ctk.CTkFrame(card, fg_color="transparent")
            acc_frame.pack(side="right", padx=10, pady=8)
            
            path = video.get("processed_path")
            if path:
                import os
                if os.path.exists(path):
                    ctk.CTkButton(
                        acc_frame, text="▶ Xem", width=50, font=("Segoe UI", 11),
                        fg_color=BORDER, hover_color=BG_CARD,
                        command=lambda p=path: os.startfile(p) if os.name == 'nt' else None
                    ).pack(side="left", padx=(0, 15))
                
            ctk.CTkLabel(acc_frame, text="Tài khoản:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=5)
            
            accounts = self._get_tiktok_accounts()
            opt_acc = ctk.CTkOptionMenu(
                acc_frame, values=accounts, font=("Segoe UI", 11),
                width=130, fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
            )
            opt_acc.pack(side="left")
            
            global_acc = self._opt_account.get()
            if global_acc in accounts:
                opt_acc.set(global_acc)
                
            self._video_accounts[vid] = opt_acc

            # Thông tin video (pack sau, expand=True)
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)
            
            ctk.CTkLabel(info_frame, text=f"ID: {vid}", font=("Consolas", 11, "bold"), text_color=ACCENT).pack(anchor="w")
            
            # Editable caption
            title = uploader_dummy._generate_caption(video)
            caption_var = ctk.StringVar(value=title)
            self._custom_captions[vid] = caption_var
            
            entry = ctk.CTkEntry(
                info_frame, textvariable=caption_var, 
                font=("Segoe UI", 13), text_color=TEXT_MAIN,
                fg_color=BG_DARK, border_color=BORDER, height=28
            )
            entry.pack(fill="x", pady=(2, 0), padx=(0, 10))
            
            # Kiểm tra dung lượng
            size_mb = 0
            if path:
                import os
                if os.path.exists(path):
                    size_mb = os.path.getsize(path) / (1024 * 1024)
            ctk.CTkLabel(info_frame, text=f"📦 {size_mb:.1f} MB", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))

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
        self._btn_upload.configure(state="disabled")
        self._status_badge.set("Đang upload...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu upload video lên TikTok...", "INFO")
        
        # Lấy tất cả giá trị GUI ở thread chính trước khi chạy ngầm
        selected_vids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_vids:
            self._log("Không có video nào được chọn!", "WARNING")
            self._on_task_done()
            return
            
        custom_captions_dict = {vid: var.get() for vid, var in self._custom_captions.items()}
        video_accounts_dict = {vid: opt.get() for vid, opt in self._video_accounts.items()}
        cleanup_upload = self._sw_cleanup_upload.get() == 1
        
        # Override limit bằng đúng số lượng video được chọn để đảm bảo up đủ
        limit = len(selected_vids)
        
        self._run_in_thread(self._do_upload, limit, selected_vids, custom_captions_dict, video_accounts_dict, cleanup_upload)

    async def _async_upload_groups(self, limit, account_groups, custom_captions_dict):
        from uploader.tiktok_uploader import TikTokUploader
        from database.db_manager import DatabaseManager
        from config.settings import COOKIES_DIR
        
        db = DatabaseManager()
        
        total_uploaded = 0
        for account_file, vids in account_groups.items():
            if total_uploaded >= limit:
                break
                
            vids_to_upload = vids[:limit - total_uploaded]
            
            self._log(f"Bắt đầu upload {len(vids_to_upload)} video cho tài khoản {account_file}...", "INFO")
            cookies_path = str(COOKIES_DIR / account_file)
            uploader = TikTokUploader(db=db, cookies_file=cookies_path)
            
            # Lọc ra các caption cho các video đang chuẩn bị upload
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
                self._log(f"✅ Upload xong {len(results)} videos cho {account_file}!", "SUCCESS")
            except Exception as e:
                self._log(f"Lỗi upload {account_file}: {e}", "ERROR")
            finally:
                await uploader.close()
                
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

    def _do_upload(self, limit, selected_vids, custom_captions_dict, video_accounts_dict, cleanup_upload):
        from config.settings import TIKTOK_CONFIG
        TIKTOK_CONFIG["auto_cleanup_after_upload"] = cleanup_upload

        account_groups = {}
        for vid in selected_vids:
            acc = video_accounts_dict.get(vid)
            if acc not in account_groups:
                account_groups[acc] = []
            account_groups[acc].append(vid)

        import asyncio
        asyncio.run(self._async_upload_groups(limit, account_groups, custom_captions_dict))

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

        # URLs
        ctk.CTkLabel(cfg, text="File URLs", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        file_row = ctk.CTkFrame(cfg, fg_color="transparent")
        file_row.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(14, 4))
        file_row.grid_columnconfigure(0, weight=1)
        self._entry_file = ctk.CTkEntry(
            file_row, placeholder_text="urls.txt",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_file.insert(0, "urls.txt")
        self._entry_file.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            file_row, text="📁", width=40, height=30,
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._browse,
        ).grid(row=0, column=1, padx=(8, 0))

        # Mode
        ctk.CTkLabel(cfg, text="Chế độ", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self._mode_var = ctk.StringVar(value="once")
        mode_frame = ctk.CTkFrame(cfg, fg_color="transparent")
        mode_frame.grid(row=1, column=1, sticky="w", pady=4)
        ctk.CTkRadioButton(mode_frame, text="Chạy 1 lần", variable=self._mode_var, value="once",
                            font=("Segoe UI", 12), text_color=TEXT_MAIN).pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="Chạy 24/7 theo lịch", variable=self._mode_var, value="schedule",
                            font=("Segoe UI", 12), text_color=TEXT_MAIN).pack(side="left", padx=10)

        # Schedule times
        ctk.CTkLabel(cfg, text="Giờ post", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=2, column=0, sticky="w", padx=16, pady=(4, 4))
        self._entry_times = ctk.CTkEntry(
            cfg, placeholder_text="09:00, 12:30, 18:00, 21:30",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_times.insert(0, "09:00, 12:30, 18:00, 21:30")
        self._entry_times.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=(4, 4))
        
        # Max posts & Cleanup
        ctk.CTkLabel(cfg, text="Upload tối đa", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=3, column=0, sticky="w", padx=16, pady=(4, 14))
        opt_frame = ctk.CTkFrame(cfg, fg_color="transparent")
        opt_frame.grid(row=3, column=1, sticky="w", pady=(4, 14))
        self._entry_auto_limit = ctk.CTkEntry(
            opt_frame, width=60, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_auto_limit.insert(0, "4")
        self._entry_auto_limit.pack(side="left")
        ctk.CTkLabel(opt_frame, text="video/ngày", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(side="left", padx=(8, 20))
        
        self._sw_cleanup_auto = ctk.CTkSwitch(opt_frame, text="🧹 Tự động dọn dẹp file cục bộ",
                                                font=("Segoe UI", 12), text_color=TEXT_MAIN)
        self._sw_cleanup_auto.select()
        self._sw_cleanup_auto.pack(side="left")

        # Account selection
        ctk.CTkLabel(cfg, text="Tài khoản", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=4, column=0, sticky="w", padx=16, pady=(4, 14))
        accounts = UploadTab._get_tiktok_accounts()
        self._opt_account = ctk.CTkOptionMenu(
            cfg, values=accounts, font=("Segoe UI", 12),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account.grid(row=4, column=1, sticky="w", padx=(0, 16), pady=(4, 14))
        
        self._btn_manage_acc = ctk.CTkButton(
            cfg, text="⚙ Quản lý", width=70, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._open_account_manager
        )
        self._btn_manage_acc.grid(row=4, column=2, sticky="w", padx=(0, 16), pady=(4, 14))

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

        file_path = self._entry_file.get().strip() or "urls.txt"
        once      = self._mode_var.get() == "once"
        account_file = self._opt_account.get()
        self._run_in_thread(self._do_auto, file_path, once, account_file)

    def _do_auto(self, file_path, once, account_file):
        from scheduler.scheduler import AutoScheduler
        from config.settings import SCHEDULER_CONFIG, TIKTOK_CONFIG
        
        # Cập nhật config từ UI
        try:
            SCHEDULER_CONFIG["post_times"] = [t.strip() for t in self._entry_times.get().split(",")]
            TIKTOK_CONFIG["max_posts_per_day"] = int(self._entry_auto_limit.get() or 4)
            TIKTOK_CONFIG["auto_cleanup_after_upload"] = self._sw_cleanup_auto.get() == 1
        except Exception as e:
            self._log(f"Lỗi parse cấu hình: {e}", "WARNING")
            
        urls = Path(file_path).read_text(encoding="utf-8").strip().splitlines()
        urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
        scheduler = AutoScheduler(douyin_urls=urls, account_file=account_file)
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
#  Tab: Settings
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="⚙️  Cài đặt",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # ── Cookies section ──────────────────────────────────────────────────
        self._section("🍪  Cookies", row=1)
        cook = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        cook.grid(row=2, column=0, sticky="ew", pady=(0, 16))
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

        # ── TikTok section ───────────────────────────────────────────────────
        self._section("🎵  TikTok Upload", row=3)
        tt = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                           border_width=1, border_color=BORDER)
        tt.grid(row=4, column=0, sticky="ew", pady=(0, 16))
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
            self, text="💾  Lưu cài đặt", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save,
        ).grid(row=5, column=0, sticky="w", pady=(4, 0))

    def _section(self, title, row):
        ctk.CTkLabel(
            self, text=title,
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
        messagebox.showinfo(
            "Đã lưu",
            "Cài đặt đã được ghi nhận.\n"
            "(Lưu ý: Một số thay đổi cần khởi động lại app để có hiệu lực.)"
        )


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
        self._nav_buttons[0].set_active(True)
        self._show_tab(0)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=210, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(99, weight=1)  # pushes bottom items down

        # Logo
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 24))
        ctk.CTkLabel(
            logo, text="🎬",
            font=("Segoe UI", 30),
        ).pack(side="left")
        ctk.CTkLabel(
            logo, text=" DouyinBot",
            font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN,
        ).pack(side="left")

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 10)
        )

        # Nav buttons
        self._nav_buttons: list[SidebarButton] = []
        for i, (icon, label, _) in enumerate(self.TABS):
            btn = SidebarButton(sidebar, icon=icon, text=label,
                                command=lambda idx=i: self._nav(idx))
            btn.grid(row=i + 2, column=0, sticky="ew", padx=10, pady=2)
            self._nav_buttons.append(btn)

        # Bottom: version
        ctk.CTkLabel(
            sidebar, text="v1.0.0",
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
