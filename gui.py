"""
GUI Entry Point - Giao diện desktop cho Douyin Crawler & TikTok Auto-Uploader
Yêu cầu: pip install customtkinter
Chạy:    python gui.py
"""
import sys
import os
import subprocess

# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: Ẩn MỌI cửa sổ console đen (FFmpeg, FFprobe, yt-dlp, Pydub...) 
# trên Windows. Phải đặt ở ĐẦU TIÊN trước khi import bất kỳ thư viện nào!
# ═══════════════════════════════════════════════════════════════════════════════
if os.name == 'nt':
    _OriginalPopen = subprocess.Popen
    class _SilentPopen(_OriginalPopen):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
            super().__init__(*args, **kwargs)
    subprocess.Popen = _SilentPopen

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

from utils.session_logger import SessionLogManager
from auth_client import auth_client
from config.settings import PROCESSOR_CONFIG
from ui.log_toolbar import LogToolbar
from ui.tabs.livestream_tab import LivestreamTab
from uploader.upload_logger import UploadLogManager
from ui.upload_log_dialog import UploadLogHistoryDialog
from ui.theme import (
    BG_DARK, BG_CARD, BG_CARD_HOVER, BG_SIDEBAR, ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_BG,
    CYAN, CYAN_HOVER, CYAN_BG, SUCCESS, SUCCESS_HOVER, SUCCESS_BG, WARNING, WARNING_HOVER, WARNING_BG,
    DANGER, DANGER_HOVER, DANGER_BG, PINK, PINK_BG, TEXT_MAIN, TEXT_DIM, TEXT_MUTED, BORDER, BORDER_FOCUS, BORDER_GLOW
)
from ui.components import (
    LogWidget, StatusBadge, ToolTip, ToastNotification, show_toast,
    StatsCard, SystemInfoWidget, SidebarButton, TaskMixin, DonutChart
)
from ui.dialogs import (
    get_user_cookies_dir, InputJSONWindow, RegisterWindow, LoginWindow
)

# ─── Cấu hình Theme ──────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=4, sticky="ew", padx=4, pady=(0, 16))
        
        # Tiêu đề + Sub-caption bên trái
        title_box = ctk.CTkFrame(hdr, fg_color="transparent")
        title_box.pack(side="left")
        
        ctk.CTkLabel(
            title_box, text="🎬  Dashboard Điều Khiển",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box, text="Tự động hóa Video AI • 🎁 Miễn phí 10 ngày Full tính năng",
            font=("Segoe UI", 11, "bold"), text_color="#FBBF24",
        ).pack(anchor="w", pady=(2, 0))

        # Nút hành động + Status Badge bên phải
        right_box = ctk.CTkFrame(hdr, fg_color="transparent")
        right_box.pack(side="right")
        
        # System Online Chip
        chip_online = ctk.CTkLabel(
            right_box, text=" ● Hệ thống Hoạt động ",
            font=("Segoe UI", 11, "bold"), text_color=SUCCESS,
            fg_color="#064E3B", corner_radius=8
        )
        chip_online.pack(side="left", padx=(0, 10))

        btn_refresh = ctk.CTkButton(
            right_box, text="⟳  Làm mới", width=100, height=36,
            font=("Segoe UI", 12, "bold"), command=self.refresh_stats,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8,
        )
        btn_refresh.pack(side="left")

        self._btn_help_dash = ctk.CTkButton(
            right_box, text="❓ Hướng dẫn A-Z", width=125, height=36,
            font=("Segoe UI", 11, "bold"), fg_color="transparent", border_width=1, border_color=BORDER,
            hover_color=BG_CARD, corner_radius=8, command=self._toggle_dash_help
        )
        self._btn_help_dash.pack(side="left", padx=(8, 0))

        # Guide frame cho người mới (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="🗺️ LỘ TRÌNH 4 BƯỚC VẬN HÀNH DÀNH CHO NGƯỜI MỚI BẮT ĐẦU (MÙ CÔNG NGHỆ CŨNG LÀM ĐƯỢC)", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• Bước 1 - CÀO VIDEO SẠCH (Tab Crawl):\n"
            "  Sao chép link video Douyin (TikTok Trung Quốc) dán vào tool -> Bấm 'Bắt đầu Crawl'. Video được tải về máy chuẩn Full HD, không dính logo watermark.\n"
            "• Bước 2 - XỬ LÝ & LÁCH BẢN QUYỀN AI (Tab Process):\n"
            "  Chọn video vừa tải -> Bật tính năng 'Làm mờ viền 9:16', 'Lồng tiếng Việt AI' hoặc 'Hiệu ứng lách âm thanh' -> Bấm 'Bắt đầu Xử lý'. AI tự động dịch chữ tiếng Trung và đọc lồng tiếng Việt chuẩn hay.\n"
            "• Bước 3 - QUẢN LÝ DÀN NICK & PROXY (Tab Accounts):\n"
            "  Thêm tài khoản TikTok / YouTube Shorts / Facebook Reels. Gán Proxy riêng biệt cho từng nick để chống quét trùng IP, chống khoá tài khoản hoặc bóp tương tác.\n"
            "• Bước 4 - ĐĂNG BÀI HOẶC CẮM MÁY AUTO 100% (Tab Upload / Tab Auto):\n"
            "  - Tab Upload: Chọn video -> Bấm '✨ AI Caption' để AI tự viết tiêu đề bắt trend -> Bấm Đăng ngay hoặc Hẹn giờ đăng.\n"
            "  - Tab Auto: Chỉ cần nạp sẵn danh sách link vào file urls.txt -> Tool tự cào -> Tự edit -> Tự đăng theo lịch 24/7 không cần can thiệp tay."
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=980).pack(anchor="w", padx=14, pady=(0, 8))
        
        # Thanh nút điều hướng nhanh các bước
        nav_box = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        nav_box.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(nav_box, text="Truy cập nhanh:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=(0, 8))
        ctk.CTkButton(nav_box, text="1. Sang Tab Crawl ➔", width=120, height=28, font=("Segoe UI", 11), fg_color="#1E293B", hover_color="#334155", command=lambda: self.app._nav(1)).pack(side="left", padx=3)
        ctk.CTkButton(nav_box, text="2. Sang Tab Process ➔", width=130, height=28, font=("Segoe UI", 11), fg_color="#1E293B", hover_color="#334155", command=lambda: self.app._nav(2)).pack(side="left", padx=3)
        ctk.CTkButton(nav_box, text="3. Sang Tab Accounts ➔", width=135, height=28, font=("Segoe UI", 11), fg_color="#1E293B", hover_color="#334155", command=lambda: self.app._nav(5)).pack(side="left", padx=3)
        ctk.CTkButton(nav_box, text="4. Sang Tab Upload ➔", width=125, height=28, font=("Segoe UI", 11), fg_color="#1E293B", hover_color="#334155", command=lambda: self.app._nav(3)).pack(side="left", padx=3)
        ctk.CTkButton(nav_box, text="🤖 Sang Tab Auto ➔", width=125, height=28, font=("Segoe UI", 11, "bold"), fg_color="#065F46", hover_color="#047857", text_color="#34D399", command=lambda: self.app._nav(4)).pack(side="left", padx=3)
        # Không grid lúc khởi tạo để không chiếm bất kỳ khoảng trống nào

        # Stats cards - Account
        self._card_role = StatsCard(self, "Tài khoản", value="USER", color="#06B6D4", icon="👤")
        self._card_expire = StatsCard(self, "Hạn Sử Dụng", value="Chưa có", color="#F59E0B", icon="⏳")
        self._card_status = StatsCard(self, "Trạng Thái", value="Hoạt động", color="#10B981", icon="🟢")
        self._card_features = StatsCard(self, "Gói Bản Quyền", value="Mở khóa (Full)", color="#8B5CF6", icon="💎")
        
        for col, card in enumerate([self._card_role, self._card_expire, self._card_status, self._card_features]):
            card.grid(row=2, column=col, padx=5, pady=5, sticky="ew")

        # Stats cards - Local Production
        self._card_crawled   = StatsCard(self, "Đã Crawl",   color="#06B6D4", icon="📥")
        self._card_processed = StatsCard(self, "Đã Xử Lý AI", color="#8B5CF6", icon="⚙")
        self._card_posted    = StatsCard(self, "Đã Upload",   color="#10B981", icon="📤")
        self._card_pending   = StatsCard(self, "Chờ Upload",  color="#F59E0B", icon="⏳")

        for col, card in enumerate([
            self._card_crawled, self._card_processed,
            self._card_posted, self._card_pending
        ]):
            card.grid(row=3, column=col, padx=5, pady=5, sticky="ew")

        # Performance Chart
        self._chart = DonutChart(self, title="📈  Tiến Độ Tổng Quan", fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._chart.grid(row=4, column=0, sticky="nsew", padx=(4, 4), pady=(16, 0))
        
        # System Info
        self._sys_info = SystemInfoWidget(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._sys_info.grid(row=4, column=1, sticky="nsew", padx=(4, 4), pady=(16, 0))

        # Recent activity log
        log_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        log_frame.grid(row=4, column=2, columnspan=2, sticky="nsew", padx=(4, 4), pady=(16, 0))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._log_widget = LogWidget(log_frame)
        self._log_toolbar = LogToolbar(log_frame, self._log_widget, module="all", title="📋  Nhật ký Hệ thống (Logs):")
        self._log_toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
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
            self._sys_info.update_stats()
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
            crawled = s.get("total_crawled", 0)
            processed = s.get("total_processed", 0)
            posted = s.get("total_posted", 0)
            pending = s.get("pending_post", 0)
            
            self._card_crawled.set_value(crawled)
            self._card_processed.set_value(processed)
            self._card_posted.set_value(posted)
            self._card_pending.set_value(pending)
            
            # Update Chart
            self._chart.update_data([
                ("Video đã Upload", posted, SUCCESS),
                ("Video chờ Upload", pending, WARNING),
                ("Đã Crawl/Xử lý", max(0, crawled - posted - pending), ACCENT)
            ])
            
            # Fetch Account Info
            from auth_client import auth_client
            success, _ = auth_client.get_me()
            if success and auth_client.user_info:
                self._card_role.set_value(auth_client.user_info.get("role", "user").upper())
                self._card_expire.set_value(auth_client.user_info.get("expire_date", "Chưa có"))
                
                is_expired = auth_client.user_info.get("is_expired", True)
                is_free = auth_client.user_info.get("is_free", False)
                if is_expired:
                    self._card_status.set_value("HẾT HẠN")
                    self._card_features.set_value("Đã khóa")
                elif is_free:
                    self._card_status.set_value("Dùng thử Free")
                    self._card_features.set_value("🎁 Free 10 Ngày")
                else:
                    self._card_status.set_value("Hoạt động")
                    self._card_features.set_value("Mở khóa (Full)")
                
            # Load announcement từ server → hiện Toast
            succ, pay_info = auth_client.get_payment_info()
            if succ and pay_info:
                announcement = pay_info.get("system_announcement", "").strip()
                version = pay_info.get("client_version", "").strip()
                
                # Chỉ hiện toast 1 lần khi refresh lần đầu (not silent)
                if not silent:
                    if version and version != "1.0":
                        show_toast(
                            self.winfo_toplevel(),
                            title="Cập Nhật Phiên Bản Mới!",
                            message=f"Phiên bản v{version} đã ra mắt.\nTải lại Tool mới nhất để có tính năng mới & vá lỗi!",
                            type_="update",
                            duration=15
                        )
                    elif announcement:
                        show_toast(
                            self.winfo_toplevel(),
                            title="Thông Báo Hệ Thống",
                            message=announcement,
                            type_="warning",
                            duration=10
                        )

            
            if not silent:
                self._log_widget.append("Stats đã được cập nhật.", "SUCCESS")
        except Exception as e:
            if not silent:
                self._log_widget.append(f"Không thể tải stats: {e}", "WARNING")

    def _toggle_dash_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_dash"):
                self._btn_help_dash.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 12))
                if hasattr(self, "_btn_help_dash"):
                    self._btn_help_dash.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")


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
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        t_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        t_box.pack(side="left")
        ctk.CTkLabel(
            t_box, text="🔍  Crawl Video từ Douyin",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            t_box, text="Tải video sạch không logo/watermark từ Douyin (TikTok Trung Quốc) theo link hoặc cả kênh",
            font=("Segoe UI", 11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        
        self._btn_help_crawl = ctk.CTkButton(
            hdr_frame, text="❓ Hướng dẫn", width=105, height=32, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_CARD,
            command=self._toggle_crawl_help
        )
        self._btn_help_crawl.pack(side="right")
        
        # Guide frame (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 HƯỚNG DẪN CÀO VIDEO DOUYIN DÀNH CHO NGƯỜI MỚI", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• 🔗 1. Cào Video đơn lẻ / Danh sách link (Khuyên dùng - Nhanh & Ổn định nhất):\n"
            "  - Mở app Douyin/TikTok -> Bấm nút 'Chia sẻ' -> 'Sao chép liên kết'.\n"
            "  - Dán thẳng vào ô text (chấp nhận cả đoạn văn bản tiếng Trung, Tool tự động trích xuất link dạng https://v.douyin.com/...).\n"
            "  - Có thể dán nhiều link cùng lúc, mỗi dòng 1 link -> Bấm '▶ Bắt đầu Crawl'.\n"
            "• 👤 2. Cào Cả Kênh / Profile tác giả:\n"
            "  - Dán đường link web trang cá nhân (VD: https://www.douyin.com/user/MS4wLjABAAAA...).\n"
            "  - ⚠️ Tuyệt đối KHÔNG nhập ID chữ số ngắn (như 1862039527lm) vì Douyin không nhận diện được.\n"
            "  - Lưu ý: Cào cả kênh yêu cầu phải có Cookie Douyin để tránh bị thuật toán Douyin chặn.\n"
            "• 📄 3. Cào từ file .txt:\n"
            "  - Tạo file .txt chứa sẵn danh sách link video -> Bấm '📁 Chọn' file và nhấn 'Bắt đầu Crawl'."
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không grid lúc khởi tạo

        # Input card
        self._input_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._input_card.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self._input_card.grid_columnconfigure(1, weight=1)
        self._input_card.grid_columnconfigure(0, minsize=120)

        # Mode chọn
        ctk.CTkLabel(self._input_card, text="Chế độ:", font=("Segoe UI", 12, "bold"),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 10))

        self._mode_var = ctk.StringVar(value="urls")
        mode_frame = ctk.CTkFrame(self._input_card, fg_color="transparent")
        mode_frame.grid(row=0, column=1, sticky="w", padx=0, pady=(16, 10))
        for val, lbl in [("urls", "🔗 Link Video (Khuyên dùng)"), ("profile", "👤 Cả Kênh / Profile"), ("file", "📄 Đọc từ File .txt")]:
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
        ctk.CTkLabel(url_inner, text="💡 Hỗ trợ: Dán 1 hoặc nhiều link (v.douyin.com hoặc douyin.com/video/...) mỗi dòng 1 link.", font=("Segoe UI", 10, "italic"), text_color=TEXT_DIM, anchor="w").grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # --- ROW 3: Profile ---
        self._frame_profile = ctk.CTkFrame(self._input_card, fg_color="transparent")
        self._frame_profile.grid_columnconfigure(1, weight=1)
        self._frame_profile.grid_columnconfigure(0, minsize=120)

        ctk.CTkLabel(self._frame_profile, text="Profile URL:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=16, pady=4)
        self._entry_profile = ctk.CTkEntry(self._frame_profile, placeholder_text="https://www.douyin.com/user/MS4wLjABAAAA...", font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._entry_profile.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=4)
        ctk.CTkLabel(self._frame_profile, text="⚠️ Lưu ý: Chỉ dán link web dạng https://www.douyin.com/user/... (Không nhập mã số hay Douyin ID ngắn)", font=("Segoe UI", 10, "italic"), text_color=WARNING, anchor="w").grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(2, 4))

        ctk.CTkLabel(self._frame_profile, text="Số lượng:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=2, column=0, sticky="w", padx=16, pady=4)
        self._spin_count = ctk.CTkEntry(self._frame_profile, width=80, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._spin_count.insert(0, "1000")
        self._spin_count.grid(row=2, column=1, sticky="w", padx=(0, 16), pady=4)
        
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

        ctk.CTkLabel(self._frame_file, text="Giới hạn (Profile):", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self._spin_count_file = ctk.CTkEntry(self._frame_file, width=80, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._spin_count_file.insert(0, "150")
        self._spin_count_file.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=4)

        # --- Buttons ---
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        self._btn_crawl = ctk.CTkButton(btn_row, text="▶  Bắt đầu Crawl", height=42, width=150, font=("Segoe UI", 14, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._start_crawl)
        self._btn_crawl.pack(side="left", padx=(0, 15))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(side="left")

        # Log Toolbar & Log Widget
        self._log_widget = LogWidget(self)
        self._log_toolbar = LogToolbar(self, self._log_widget, module="crawl", title="📋  Nhật ký Crawl (Logs):")
        self._log_toolbar.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        self._log_widget.grid(row=5, column=0, sticky="nsew")
        self.grid_rowconfigure(5, weight=1)

        self._on_mode_change()

    def _toggle_crawl_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_crawl"):
                self._btn_help_crawl.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
                if hasattr(self, "_btn_help_crawl"):
                    self._btn_help_crawl.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

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
        from auth_client import auth_client
        if auth_client.user_info and auth_client.user_info.get("is_expired", True):
            messagebox.showerror("Bản quyền", "Tài khoản của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục sử dụng!")
            return
            
        self._btn_crawl.configure(state="disabled")
        self._status_badge.set("Đang crawl...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu crawl...", "INFO")

        mode  = self._mode_var.get()
        count = int(self._spin_count.get() or 10)
        self._start_logging_session("crawl", f"Crawl Douyin Video ({mode.upper()})", {"mode": mode, "count": count})

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
            count_file = int(self._spin_count_file.get() or 150)
            self._run_in_thread(self._do_crawl_file, file_path, count_file)

    def _do_crawl_urls(self, urls):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        crawler.current_username = auth_client.user_info.get("username") if auth_client.user_info else None
        self._log(f"Crawling {len(urls)} URLs...", "INFO")
        try:
            results = asyncio.run(crawler.crawl_multiple_videos(urls))
            if results:
                self._log(f"✅ Crawled thành công {len(results)}/{len(urls)} video!", "SUCCESS")
                auth_client.send_telemetry("CRAWL", f"Tải xong {len(results)}/{len(urls)} video từ list URL")
            else:
                err_detail = getattr(crawler, "last_error", None) or "Tất cả link đều thất bại hoặc không thể tải file"
                self._log(f"⚠️ Crawled 0/{len(urls)} video. Chi tiết: {err_detail}", "WARNING")
                self.after(0, lambda: self._status_badge.set("Thất bại", WARNING))
                auth_client.send_telemetry("ERROR", f"[CRAWL THẤT BẠI] 0/{len(urls)} video từ danh sách URL. Lỗi: {err_detail}")
        except Exception as e:
            self._log(f"❌ Lỗi ngoại lệ Crawl URL: {e}", "ERROR")
            auth_client.send_telemetry("ERROR", f"[CRAWL NGOẠI LỆ] Lỗi cào URL: {str(e)[:250]}")

    def _do_crawl_profile(self, profile, count):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        crawler.current_username = auth_client.user_info.get("username") if auth_client.user_info else None
        self._log(f"Crawling profile ({count} videos)...", "INFO")
        try:
            results = asyncio.run(crawler.crawl_user_profile(profile, max_videos=count))
            if results:
                self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")
                auth_client.send_telemetry("CRAWL", f"Tải xong {len(results)} video từ profile: {profile}")
            else:
                err_detail = getattr(crawler, "last_error", None) or "Không tải được video nào (Kênh riêng tư hoặc Douyin chặn)"
                self._log(f"⚠️ Không tải được video nào từ profile {profile}. Chi tiết: {err_detail}", "WARNING")
                self.after(0, lambda: self._status_badge.set("Thất bại", WARNING))
                auth_client.send_telemetry("ERROR", f"[CRAWL THẤT BẠI] 0 video từ profile: {profile}. Lỗi: {err_detail}")
        except Exception as e:
            self._log(f"❌ Lỗi ngoại lệ Crawl Profile: {e}", "ERROR")
            auth_client.send_telemetry("ERROR", f"[CRAWL PROFILE NGOẠI LỆ] Profile {profile} | {str(e)[:250]}")

    def _do_crawl_file(self, file_path, limit=150):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        
        try:
            urls = Path(file_path).read_text(encoding="utf-8").strip().splitlines()
        except Exception as e:
            self._log(f"❌ Lỗi đọc file: {e}", "ERROR")
            auth_client.send_telemetry("ERROR", f"[CRAWL FILE LỖI] Đọc file {Path(file_path).name}: {str(e)[:200]}")
            self._on_task_done()
            return
            
        urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
        if not urls:
            self._log(f"❌ File rỗng hoặc không có URL hợp lệ!", "ERROR")
            auth_client.send_telemetry("ERROR", f"[CRAWL FILE LỖI] File {Path(file_path).name} rỗng hoặc không có URL hợp lệ")
            self._on_task_done()
            return
            
        db      = DatabaseManager()
        crawler = DouyinCrawler(db=db)
        crawler.current_username = auth_client.user_info.get("username") if auth_client.user_info else None
        
        # Tự động phân loại Profile URL và Video URL
        profile_urls = [u for u in urls if "user/" in u or ("modal_id=" not in u and "video/" not in u and "v.douyin.com" not in u)]
        video_urls = [u for u in urls if u not in profile_urls]
        
        self._log(f"Đọc {len(urls)} URLs từ file {Path(file_path).name}...", "INFO")
        total_crawled = 0
        
        try:
            if profile_urls:
                self._log(f"Phát hiện {len(profile_urls)} link Profile. Cào tối đa {limit} video/người.", "INFO")
                for idx, p_url in enumerate(profile_urls):
                    self._log(f"[{idx+1}/{len(profile_urls)}] Đang cào Profile: {p_url}", "INFO")
                    res = asyncio.run(crawler.crawl_user_profile(p_url, max_videos=limit))
                    total_crawled += len(res)
                    
            if video_urls:
                self._log(f"Phát hiện {len(video_urls)} link Video đơn lẻ. Đang cào...", "INFO")
                res = asyncio.run(crawler.crawl_multiple_videos(video_urls))
                total_crawled += len(res)
                
            if total_crawled > 0:
                self._log(f"✅ Tổng cộng cào thành công {total_crawled} video!", "SUCCESS")
                auth_client.send_telemetry("CRAWL", f"Tải xong {total_crawled} video từ file {Path(file_path).name}")
            else:
                err_detail = getattr(crawler, "last_error", None) or "Tất cả URL trong file đều không cào được video"
                self._log(f"⚠️ Không cào được video nào từ file {Path(file_path).name}! Chi tiết: {err_detail}", "WARNING")
                auth_client.send_telemetry("ERROR", f"[CRAWL THẤT BẠI] 0 video từ file {Path(file_path).name}. Lỗi: {err_detail}")
        except Exception as e:
            self._log(f"❌ Lỗi ngoại lệ cào file: {e}", "ERROR")
            auth_client.send_telemetry("ERROR", f"[CRAWL FILE NGOẠI LỆ] File {Path(file_path).name} | {str(e)[:250]}")

    def _on_task_done(self):
        super()._on_task_done()
        self.after(0, lambda: self._btn_crawl.configure(state="normal"))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS) if not getattr(self, "cancel_flag", False) else self._status_badge.set("Đã dừng", DANGER))


def show_rename_author_dialog(parent, opt_widget, reload_callback):
    """Mở hộp thoại đổi tên Kênh/Tác giả Douyin thân thiện."""
    from database.db_manager import DatabaseManager
    from auth_client import auth_client
    db = DatabaseManager()
    current_user = auth_client.user_info.get("username") if auth_client.user_info else None

    current_authors = db.get_authors(username=current_user)
    if not current_authors:
        messagebox.showinfo("Thông báo", "Chưa có kênh nào trong cơ sở dữ liệu để đổi tên!")
        return

    curr_selected = opt_widget.get() if opt_widget else "Tất cả Kênh"

    dialog = ctk.CTkToplevel(parent)
    dialog.title("Đổi tên Kênh Douyin")
    dialog.geometry("440x260")
    dialog.resizable(False, False)
    dialog.configure(fg_color=BG_CARD)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    # Căn giữa cửa sổ
    dialog.update_idletasks()
    try:
        x = parent.winfo_toplevel().winfo_x() + (parent.winfo_toplevel().winfo_width() - 440) // 2
        y = parent.winfo_toplevel().winfo_y() + (parent.winfo_toplevel().winfo_height() - 260) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
    except Exception:
        pass

    frame = ctk.CTkFrame(dialog, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=24, pady=20)

    ctk.CTkLabel(frame, text="🏷️ Đổi Tên Kênh Douyin", font=("Segoe UI", 16, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 12))

    ctk.CTkLabel(frame, text="Chọn kênh Douyin cần đổi tên:", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(anchor="w", pady=(0, 4))
    opt_choose = ctk.CTkOptionMenu(
        frame, values=current_authors, font=("Segoe UI", 12),
        fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
    )
    if curr_selected in current_authors:
        opt_choose.set(curr_selected)
    else:
        opt_choose.set(current_authors[0])
    opt_choose.pack(fill="x", pady=(0, 12))

    ctk.CTkLabel(frame, text="Nhập tên mới dễ nhớ (VD: Kênh Bác Sĩ, Kênh Hài):", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(anchor="w", pady=(0, 4))
    entry_new_name = ctk.CTkEntry(
        frame, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        placeholder_text="Nhập tên mới gợi nhớ..."
    )
    entry_new_name.pack(fill="x", pady=(0, 16))
    entry_new_name.focus()

    def on_confirm():
        old_name = opt_choose.get().strip()
        new_name = entry_new_name.get().strip()
        if not new_name:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên mới!", parent=dialog)
            return
        if old_name == new_name:
            messagebox.showinfo("Thông báo", "Tên mới trùng với tên cũ!", parent=dialog)
            dialog.destroy()
            return

        affected = db.rename_author(old_name, new_name, username=current_user)
        dialog.destroy()

        if opt_widget:
            all_authors = db.get_authors(username=current_user)
            opt_widget.configure(values=["Tất cả Kênh"] + all_authors)
            opt_widget.set(new_name)

        reload_callback()
        messagebox.showinfo("Thành công", f"Đã đổi tên kênh '{old_name}' thành '{new_name}' ({affected} video được cập nhật)!")

    btn_row = ctk.CTkFrame(frame, fg_color="transparent")
    btn_row.pack(fill="x")

    ctk.CTkButton(btn_row, text="Hủy", width=80, fg_color=BORDER, hover_color=BG_CARD, command=dialog.destroy).pack(side="right", padx=(10, 0))
    ctk.CTkButton(btn_row, text="💾 Lưu Tên", width=110, fg_color=SUCCESS, hover_color="#27ae60", command=on_confirm).pack(side="right")

    entry_new_name.bind("<Return>", lambda _: on_confirm())


def show_delete_author_dialog(parent, opt_widget, reload_callback):
    """Mở hộp thoại xác nhận xóa Kênh/Nhóm Douyin và toàn bộ video của nhóm."""
    from database.db_manager import DatabaseManager
    from auth_client import auth_client
    db = DatabaseManager()
    current_user = auth_client.user_info.get("username") if auth_client.user_info else None

    curr_selected = opt_widget.get().strip() if opt_widget else "Tất cả Kênh"
    if curr_selected == "Tất cả Kênh" or not curr_selected:
        messagebox.showwarning(
            "Chưa chọn nhóm",
            "Vui lòng chọn một nhóm/kênh cụ thể từ danh sách để xóa (không thể chọn 'Tất cả Kênh')!",
            parent=parent
        )
        return

    # Kiểm tra số lượng video của nhóm
    conn = db._get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM crawled_videos WHERE author = ?"
        params = [curr_selected]
        if current_user:
            clean_user = current_user.replace("@", "_").replace(".", "_")
            query += " AND (username = ? OR REPLACE(REPLACE(username, '@', '_'), '.', '_') = ?)"
            params.extend([current_user, clean_user])
        cursor.execute(query, tuple(params))
        total_vids = cursor.fetchone()[0]
    finally:
        conn.close()

    msg = f"Bạn có chắc chắn muốn xóa nhóm/kênh '{curr_selected}' không?\n\n"
    if total_vids > 0:
        msg += f"⚠️ Thao tác này sẽ XÓA VĨNH VIỄN tất cả {total_vids} video thuộc nhóm này (bao gồm file trên máy tính, Google Drive và toàn bộ dữ liệu liên quan)."
    else:
        msg += "Nhóm này hiện không còn video nào trong hệ thống. Nhóm sẽ được xóa sạch khỏi danh sách lựa chọn."

    if not messagebox.askyesno("Xác nhận xóa nhóm", msg, icon="warning", parent=parent):
        return

    deleted = db.delete_author_data(curr_selected, username=current_user)

    if opt_widget:
        opt_widget.set("Tất cả Kênh")

    reload_callback()
    messagebox.showinfo(
        "Đã xóa nhóm",
        f"Đã xóa thành công nhóm '{curr_selected}' ({deleted} video đã được dọn sạch)!",
        parent=parent
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Process
# ═══════════════════════════════════════════════════════════════════════════════
class ProcessTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self._checkboxes = {} # Lưu trạng thái {video_id: BooleanVar}
        self._progress_bars = {} # {video_id: CTkProgressBar}
        self._progress_labels = {} # {video_id: CTkLabel}
        self._progress_labels = {} # {video_id: CTkLabel}
        self._selected_music_path = None
        self._build()
        self.after(200, self._load_videos)
        self.after(300, self._load_process_config)

    def _build(self):
        # Header
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        t_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        t_box.pack(side="left")
        ctk.CTkLabel(
            t_box, text="🎞️  Xử Lý & Edit Video AI",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            t_box, text="Tự động lách bản quyền, căn chỉnh khung hình 9:16, bóc phụ đề tiếng Trung và lồng tiếng Việt",
            font=("Segoe UI", 11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        
        self._btn_help_proc = ctk.CTkButton(
            hdr_frame, text="❓ Hướng dẫn", width=105, height=32, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_CARD,
            command=self._toggle_proc_help
        )
        self._btn_help_proc.pack(side="right")
        
        # Guide frame (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 QUY TRÌNH 3 BƯỚC XỬ LÝ & LÁCH BẢN QUYỀN DÀNH CHO NGƯỜI MỚI", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• Bước 1 - Chọn Video Cần Làm:\n"
            "  - Xem danh sách video ở bảng bên trái (được tải về từ tab Crawl).\n"
            "  - Tích chọn (☑) vào các video muốn làm (hoặc bấm nút '☑ Chọn' để chọn nhanh tất cả).\n"
            "  - 💡 Nếu chưa có video nào, hãy sang tab 'Crawl' tải về trước, hoặc bấm nút '📥 Import Video' để nạp video có sẵn trong máy.\n"
            "• Bước 2 - Chọn Cấu Hình Lách Bản Quyền (Cột Bên Phải):\n"
            "  - 'Title overlay': Để trống để AI tự động nhận diện và dịch tiêu đề gốc sang tiếng Việt hấp dẫn.\n"
            "  - 'Làm mờ viền (Blur)': Tự động căn chỉnh video về chuẩn khung dọc 9:16 của TikTok/Reels/Shorts.\n"
            "  - 'Lồng tiếng AI & Phụ đề': Tự động đọc chữ tiếng Trung trên màn hình -> Dịch sang tiếng Việt -> Lồng giọng đọc AI cực hay.\n"
            "  - 'Hiệu ứng lách âm thanh / hình ảnh': Lật video, đổi MD5, đổi tone màu để chống thuật toán quét trùng lặp.\n"
            "• Bước 3 - Bắt Đầu Render:\n"
            "  - Bấm nút '▶ Bắt đầu Xử lý' ở góc dưới cột phải. Chờ thanh tiến trình đạt 100%.\n"
            "  - Video render xong sẽ tự động chuyển sang tab 'Upload' để sẵn sàng đăng lên các kênh!"
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không grid lúc khởi tạo

        # Khởi tạo 2 cột (Trái: Danh sách, Phải: Sidebar công cụ cố định 380px)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(2, weight=1)

        # --- LEFT PANE ---
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 15))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        list_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(list_header, text="Danh sách Video đã tải:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        self._opt_author_filter = ctk.CTkOptionMenu(list_header, values=["Tất cả Kênh"], width=130, command=lambda _: self._load_videos())
        self._opt_author_filter.pack(side="left", padx=(10, 0))
        self._btn_rename_author = ctk.CTkButton(
            list_header, text="✏️ Đổi tên", width=75, height=24, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=self._rename_author_dialog
        )
        self._btn_rename_author.pack(side="left", padx=(6, 0))
        self._btn_delete_author = ctk.CTkButton(
            list_header, text="🗑 Xóa nhóm", width=85, height=24, font=("Segoe UI", 11, "bold"),
            fg_color="#c0392b", hover_color="#e74c3c", command=self._delete_author_dialog
        )
        self._btn_delete_author.pack(side="left", padx=(6, 0))
        
        ctk.CTkButton(list_header, text="🔄 Refresh", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._load_videos).pack(side="right")
        ctk.CTkButton(list_header, text="🗑 Xóa", width=60, height=24, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_selected).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="☑ Chọn", width=60, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._toggle_selection).pack(side="right", padx=(0, 10))
        ctk.CTkButton(list_header, text="📥 Import Video", width=100, height=24, fg_color=SUCCESS, hover_color="#27ae60", command=self._import_local_video).pack(side="right", padx=(0, 10))
        
        self._video_list_frame = ctk.CTkScrollableFrame(left_frame, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._video_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

        self._log_widget = LogWidget(left_frame, height=120)
        self._log_toolbar = LogToolbar(left_frame, self._log_widget, module="process", title="📋  Nhật ký Xử lý Video (Logs):")
        self._log_toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self._log_widget.grid(row=3, column=0, sticky="nsew")

        # --- RIGHT PANE (SIDEBAR CẤU HÌNH CỐ ĐỊNH) ---
        right_frame = ctk.CTkScrollableFrame(self, width=380, fg_color="transparent")
        right_frame.grid(row=2, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        # Options card
        opts = ctk.CTkFrame(right_frame, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        opts.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(1, weight=1)

        # Title
        lbl_title = ctk.CTkLabel(opts, text="Title overlay ❔", font=("Segoe UI", 12), text_color=TEXT_DIM, cursor="hand2")
        lbl_title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))
        ToolTip(lbl_title, "Tiêu đề video mới. Để trống hệ thống sẽ tự động dùng AI dịch tiêu đề gốc sang Tiếng Việt.")
        self._entry_title = ctk.CTkEntry(
            opts, placeholder_text="Để trống = Dịch tự động",
            font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_title.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(14, 4))

        # Limit
        lbl_limit = ctk.CTkLabel(opts, text="Số lượng ❔", font=("Segoe UI", 12), text_color=TEXT_DIM, cursor="hand2")
        lbl_limit.grid(row=1, column=0, sticky="w", padx=16, pady=4)
        ToolTip(lbl_limit, "Giới hạn số lượng video được xử lý trong lần chạy này (mặc định 10).")
        self._entry_limit = ctk.CTkEntry(
            opts, width=80, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_limit.insert(0, "10")
        self._entry_limit.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(4, 6))

        # Threads (Số luồng xử lý song song)
        lbl_threads = ctk.CTkLabel(opts, text="Số luồng xử lý ❔", font=("Segoe UI", 12), text_color=TEXT_DIM, cursor="hand2")
        lbl_threads.grid(row=2, column=0, sticky="w", padx=16, pady=4)
        ToolTip(lbl_threads, "Số lượng video xử lý song song cùng lúc (Khuyên dùng: 2-3 luồng cho Ollama Local; 3-5 luồng cho Cloud API như Groq/Gemini).")
        self._entry_threads = ctk.CTkEntry(
            opts, width=80, font=("Segoe UI", 12),
            fg_color=BG_DARK, border_color=BORDER,
        )
        self._entry_threads.insert(0, "2")
        self._entry_threads.grid(row=2, column=1, sticky="w", padx=(0, 16), pady=(4, 14))

        # Cấu hình xếp dọc theo Sidebar
        config_frame = ctk.CTkFrame(opts, fg_color="transparent")
        config_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

        # --- Hình ảnh & Âm thanh ---
        ctk.CTkLabel(config_frame, text="Hiệu ứng cơ bản", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row1 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))

        self._sw_mirror = ctk.CTkSwitch(row1, text="Mirror (Lật video) ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, cursor="hand2")
        self._sw_mirror.select()
        self._sw_mirror.pack(anchor="w", pady=(0, 10))
        ToolTip(self._sw_mirror, "Lật ngang hình ảnh video để chống quét bản quyền (MD5) của nền tảng.")

        self._sw_music = ctk.CTkSwitch(row1, text="Ghép nhạc nền ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, cursor="hand2")
        self._sw_music.select()
        self._sw_music.pack(anchor="w", pady=(0, 10))
        ToolTip(self._sw_music, "Xóa âm thanh gốc và thay bằng một bản nhạc nền tiếng Việt ngẫu nhiên.")

        music_tools = ctk.CTkFrame(row1, fg_color="transparent")
        music_tools.pack(fill="x")
        self._btn_open_music = ctk.CTkButton(music_tools, text="🎵 Chọn...", width=70, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._select_music_file)
        self._btn_open_music.pack(side="left", padx=(0, 10))
        self._lbl_music_file = ctk.CTkLabel(music_tools, text="(Mặc định)", font=("Segoe UI", 11), text_color=TEXT_DIM)
        self._lbl_music_file.pack(side="left")
        
        vol_frame = ctk.CTkFrame(row1, fg_color="transparent")
        vol_frame.pack(fill="x", pady=(10, 0))
        lbl_vol = ctk.CTkLabel(vol_frame, text="Âm lượng gốc: ❔", font=("Segoe UI", 11), text_color=TEXT_DIM, cursor="hand2")
        lbl_vol.pack(side="left", padx=(0, 5))
        ToolTip(lbl_vol, "Mức âm lượng của nhạc nền MP3 (nếu bật Ghép nhạc nền) hoặc của video gốc.")
        self._entry_bg_vol = ctk.CTkEntry(vol_frame, width=45, placeholder_text="15%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_bg_vol.insert(0, "15%")
        self._entry_bg_vol.pack(side="left")
        def _toggle_mute():
            # Nếu bật Mute mà KHÔNG bật ghép nhạc nền, thì vô hiệu hoá slider.
            # Nếu có ghép nhạc nền, slider vẫn dùng để chỉnh âm lượng nhạc nền.
            if self._sw_mute_original.get() == 1 and self._sw_music.get() == 0:
                self._entry_bg_vol.configure(state="disabled", fg_color=BORDER)
            else:
                self._entry_bg_vol.configure(state="normal", fg_color=BG_DARK)
                
        self._sw_mute_original = ctk.CTkSwitch(vol_frame, text="Tắt âm thanh gốc ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, command=_toggle_mute, cursor="hand2")
        self._sw_mute_original.pack(side="left", padx=(15, 0))
        ToolTip(self._sw_mute_original, "Loại bỏ hoàn toàn tiếng Trung/tiếng ồn của video gốc để giọng AI đọc rõ hơn.")
        
        # Sửa event command của sw_music để gọi update_mute
        self._sw_music.configure(command=_toggle_mute)

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Xử lý Chữ & Vietsub ---
        ctk.CTkLabel(config_frame, text="Subtitles & Blur", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row2 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))

        # --- Chế độ Tùy chỉnh Cao cấp ---
        sub_frame = ctk.CTkFrame(row2, fg_color="transparent")
        sub_frame.pack(fill="x", pady=(0, 10))
        
        def _toggle_sub_widgets():
            is_on = int(self._sw_subtitle.get()) == 1
            self._opt_sub_pos.configure(state="normal" if is_on else "disabled")
            
        self._toggle_sub_widgets = _toggle_sub_widgets
        self._sw_subtitle = ctk.CTkSwitch(sub_frame, text="Auto-Vietsub ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, command=_toggle_sub_widgets, cursor="hand2")
        self._sw_subtitle.select()
        self._sw_subtitle.pack(side="left")
        ToolTip(self._sw_subtitle, "Tự động trích xuất phụ đề gốc, dịch sang tiếng Việt và gắn cứng (hardsub) lên video mới.")
        
        self._opt_sub_pos = ctk.CTkOptionMenu(
            sub_frame, values=["Đè lên vùng mờ", "Cao (Tránh TikTok UI)", "Dưới cùng (Chuẩn đáy)", "Giữa màn hình"], 
            width=140, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_sub_pos.set("Đè lên vùng mờ")
        self._opt_sub_pos.pack(side="left", padx=(10, 0))
        ToolTip(self._opt_sub_pos, "Đè lên vùng mờ: Tự động in đè lên đúng tâm dải mờ.\nCao: Đẩy lên cách đáy 35% tránh khung chat TikTok.\nDưới cùng: Nằm ở đáy video (cách đáy 12%).\nGiữa màn hình: Nằm ở chính giữa.")

        blur_tools = ctk.CTkFrame(row2, fg_color="transparent")
        
        lbl_blur_h = ctk.CTkLabel(blur_tools, text="Vị trí mờ: ❔", font=("Segoe UI", 11), text_color=TEXT_DIM, cursor="hand2")
        lbl_blur_h.pack(side="left", padx=(0, 5))
        ToolTip(lbl_blur_h, "🤖 Tự động quét: AI phân tích khung hình video để tìm chính xác dòng chữ phụ đề tiếng Trung cũ và tạo dải mờ vừa khít.\nHoặc chọn các vị trí cố định theo ý bạn.")

        lbl_blur_pct = ctk.CTkLabel(blur_tools, text="Độ dày:", font=("Segoe UI", 11), text_color=TEXT_DIM)
        self._entry_blur_height = ctk.CTkEntry(blur_tools, width=46, placeholder_text="Auto", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_blur_height.insert(0, "Auto")
        ToolTip(self._entry_blur_height, "Độ dày dải mờ (% chiều cao video). Nhập 'Auto' hoặc để AI tự đo độ cao chữ gốc.")

        def _update_blur_ui(choice=None):
            if choice is None:
                choice = self._opt_blur_pos.get()
            is_on = int(self._sw_blur.get()) == 1
            is_auto = "tự động" in choice.lower() or "auto" in choice.lower()

            if not is_on:
                self._opt_blur_pos.configure(state="disabled")
                lbl_blur_pct.pack_forget()
                self._entry_blur_height.pack_forget()
                self._opt_blur_pos.configure(width=220)
                return

            self._opt_blur_pos.configure(state="normal")
            if is_auto:
                # Ẩn ô Độ dày khi chọn AI Auto-Detect vì AI tự đo vừa khít chữ (tránh tràn viền đè chữ)
                lbl_blur_pct.pack_forget()
                self._entry_blur_height.pack_forget()
                self._opt_blur_pos.configure(width=220)
                self._entry_blur_height.delete(0, "end")
                self._entry_blur_height.insert(0, "Auto")
            else:
                # Hiện ô Độ dày khi chọn vị trí thủ công (Douyin, Dưới cùng...) để tùy biến
                self._opt_blur_pos.configure(width=165)
                lbl_blur_pct.pack(side="left", padx=(6, 4))
                self._entry_blur_height.pack(side="left")
                self._entry_blur_height.configure(state="normal", fg_color=BG_DARK)

        self._update_blur_ui = _update_blur_ui

        def _on_blur_pos_changed(choice):
            self._entry_blur_height.delete(0, "end")
            if "tự động" in choice.lower() or "auto" in choice.lower():
                self._entry_blur_height.insert(0, "Auto")
            elif "douyin" in choice.lower() or "20%" in choice:
                self._entry_blur_height.insert(0, "8%")
            elif "cao" in choice.lower() or "tiktok" in choice.lower():
                self._entry_blur_height.insert(0, "8%")
            elif "trên cùng" in choice.lower():
                self._entry_blur_height.insert(0, "8%")
            else: # Dưới cùng
                self._entry_blur_height.insert(0, "14%")
            _update_blur_ui(choice)

        def _toggle_blur_widgets():
            _update_blur_ui()

        self._toggle_blur_widgets = _toggle_blur_widgets
        self._sw_blur = ctk.CTkSwitch(row2, text="Làm mờ phụ đề gốc ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, command=_toggle_blur_widgets, cursor="hand2")
        self._sw_blur.select()
        self._sw_blur.pack(anchor="w", pady=(0, 10))
        ToolTip(self._sw_blur, "Tự động phát hiện vị trí phụ đề tiếng Trung cũ bằng Computer Vision (OpenCV) và tạo dải mờ vừa khít che đi, sau đó in đè phụ đề tiếng Việt lên đúng vị trí.")

        blur_tools.pack(fill="x")

        blur_pos_values = [
            "🤖 Tự động (AI Auto-Detect)",
            "Chuẩn Douyin (Cách đáy ~20%)",
            "Phụ đề cao (Tránh UI TikTok)",
            "Dưới cùng (Đáy video)",
            "Trên cùng (Đỉnh video)"
        ]
        self._opt_blur_pos = ctk.CTkOptionMenu(
            blur_tools, values=blur_pos_values, width=220, font=("Segoe UI", 11, "bold"),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD,
            command=_on_blur_pos_changed
        )
        self._opt_blur_pos.set("🤖 Tự động (AI Auto-Detect)")
        self._opt_blur_pos.pack(side="left", padx=(0, 4))
        
        # Khởi tạo trạng thái ẩn ô độ dày vì mặc định đang là Auto-Detect
        _update_blur_ui("🤖 Tự động (AI Auto-Detect)")
        
        ctk.CTkLabel(row2, text="💡 Chọn Ollama (Local) hoặc API Key ở mục Settings để AI dịch Sub chuẩn nhất", font=("Segoe UI", 10, "italic"), text_color="#F9A826").pack(anchor="w", pady=(10, 0))

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Thuyết minh AI ---
        ctk.CTkLabel(config_frame, text="Voiceover AI", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        row3 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 12))

        self._sw_dubbing = ctk.CTkSwitch(row3, text="Thuyết minh AI ❔", font=("Segoe UI", 12), text_color=TEXT_MAIN, cursor="hand2")
        self._sw_dubbing.select()
        self._sw_dubbing.pack(anchor="w", pady=(0, 10))
        ToolTip(self._sw_dubbing, "Sử dụng Edge TTS để lồng tiếng Việt Nam dựa trên phụ đề đã dịch.")
        
        ai_mode_frame = ctk.CTkFrame(row3, fg_color="transparent")
        ai_mode_frame.pack(fill="x", pady=(0, 10))
        lbl_ai_mode = ctk.CTkLabel(ai_mode_frame, text="Chế độ: ❔", font=("Segoe UI", 11), text_color=TEXT_DIM, cursor="hand2")
        lbl_ai_mode.pack(side="left", padx=(0, 5))
        ToolTip(lbl_ai_mode, "Thuyết minh nguyên bản: Đọc chính xác từng câu khớp với miệng nhân vật.\nReview Phim: Tóm tắt lại nội dung và đọc một mạch từ đầu đến cuối.")
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
            values=["Giọng Nam", "Giọng Nữ", "Đa giọng (Đoản kịch)", "Vbee - Ngọc Huyền (Nữ)", "Vbee - Mai Phương (Nữ)", "Vbee - Minh Hoàng (Nam)", "Vbee - Đa giọng (Đoản kịch)"], 
            width=140, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_voice.set("Đa giọng (Đoản kịch)")
        self._opt_voice.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(voice_tools, text="Tốc độ:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_tts_rate = ctk.CTkEntry(voice_tools, width=45, placeholder_text="15%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_tts_rate.insert(0, "15%")
        self._entry_tts_rate.pack(side="left", padx=(0, 5))
        
        def _on_tts_slider(val):
            self._entry_tts_rate.delete(0, "end")
            self._entry_tts_rate.insert(0, f"{int(val)}%")
            
        self._slider_tts_rate = ctk.CTkSlider(voice_tools, from_=-50, to=50, width=80, command=_on_tts_slider)
        self._slider_tts_rate.set(15)
        self._slider_tts_rate.pack(side="left")

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

        ctk.CTkButton(
            btn_row, text="💾 Lưu Cấu Hình Setup", height=36,
            font=("Segoe UI", 12, "bold"),
            fg_color=BORDER, hover_color=BG_CARD,
            command=self._save_process_config,
        ).pack(fill="x", pady=(0, 8))

        self._btn_process = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Xử lý", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
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

    def _toggle_proc_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_proc"):
                self._btn_help_proc.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
                if hasattr(self, "_btn_help_proc"):
                    self._btn_help_proc.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

    def _load_videos(self):
        """Hiển thị danh sách video đã tải vào scrollable frame."""
        # Xóa các checkbox cũ
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._checkboxes = {}
        self._progress_bars = {}
        self._progress_labels = {}

        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username") if auth_client.user_info else None

        # Hiển thị số lượt render dùng thử nếu tài khoản chưa mua gói
        if hasattr(self, "_status_badge") and not getattr(self, "is_running", False):
            trial_info = auth_client.get_trial_info()
            if not trial_info["is_unlimited"]:
                max_allowed = trial_info.get("max_allowed", 5)
                if trial_info["remaining"] > 0:
                    self._status_badge.set(f"Dùng thử: Còn {trial_info['remaining']}/{max_allowed} video hôm nay", WARNING)
                else:
                    self._status_badge.set(f"Hết {max_allowed} lượt render hôm nay", DANGER)
            else:
                self._status_badge.set("Sẵn sàng", SUCCESS)

        
        # Lấy 100 video tải gần nhất để hiển thị
        
        author_val = self._opt_author_filter.get() if hasattr(self, "_opt_author_filter") else "Tất cả Kênh"
        if hasattr(self, "_opt_author_filter"):
            authors = db.get_authors(status="downloaded", username=current_user)
            new_values = ["Tất cả Kênh"] + authors
            self._opt_author_filter.configure(values=new_values)
            if author_val not in new_values:
                author_val = "Tất cả Kênh"
                self._opt_author_filter.set("Tất cả Kênh")
        author_filter = None if author_val == "Tất cả Kênh" else author_val
        videos = db.get_downloaded_videos(limit=100, username=current_user, author=author_filter)

        
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
            
            var = ctk.BooleanVar(value=False) # Không chọn mặc định
            self._checkboxes[vid] = var
            
            # Checkbox bên trái
            cb = ctk.CTkCheckBox(
                card, text="", variable=var, width=24,
                command=self._update_limit_state
            )
            cb.pack(side="left", padx=(10, 0), pady=10)
            
            # Action buttons (pack bên phải trước để không bị đẩy mất bởi text dài)
            action_frame = ctk.CTkFrame(card, fg_color="transparent")
            action_frame.pack(side="right", padx=10, pady=8)
            
            path = video.get("download_path")
            drive_id = video.get("drive_download_id")
            source_url = video.get("source_url")
            
            import os
            import webbrowser
            if path and os.path.exists(path):
                ctk.CTkButton(
                    action_frame, text="▶ Xem", width=60, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda p=path: os.startfile(p) if os.name == 'nt' else None
                ).pack(side="left")
            elif drive_id:
                ctk.CTkButton(
                    action_frame, text="☁️ Xem Drive", width=80, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda d_id=drive_id: webbrowser.open(f"https://drive.google.com/file/d/{d_id}/view")
                ).pack(side="left")
            elif source_url:
                ctk.CTkButton(
                    action_frame, text="🌐 Xem Gốc", width=75, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda url=source_url: webbrowser.open(url)
                ).pack(side="left")

            # Thông tin video (pack sau action_frame, expand=True)
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)
            
            author_name = video.get("author")
            id_text = f"ID: {vid}" + (f"  |  🏷️ {author_name}" if author_name else "")
            id_lbl = ctk.CTkLabel(info_frame, text=id_text, font=("Segoe UI", 10, "bold" if author_name else "normal"), text_color="#3498db" if author_name else ACCENT)
            id_lbl.pack(anchor="w")
            
            title_lbl = ctk.CTkLabel(info_frame, text=title[:80] + ("..." if len(title) > 80 else ""), 
                                      font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN, wraplength=400, justify="left")
            title_lbl.pack(anchor="w", pady=(2, 4))
            
            # Progress bar và Label (Mặc định ẩn)
            prog_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            
            prog_bar = ctk.CTkProgressBar(prog_frame, height=8, width=200, progress_color=SUCCESS, fg_color=BG_DARK)
            prog_bar.set(0)
            prog_bar.pack(side="left", pady=(2, 0))
            
            prog_lbl = ctk.CTkLabel(prog_frame, text="0%", font=("Segoe UI", 10, "italic"), text_color=TEXT_DIM)
            prog_lbl.pack(side="left", padx=(8, 0))
            
            self._progress_bars[vid] = prog_bar
            self._progress_labels[vid] = prog_lbl
            
            # Không pack prog_frame ngay, chỉ pack khi bắt đầu xử lý để đỡ rối mắt
            # Nhưng ta lưu lại frame vào dictionary nếu muốn hiện/ẩn
            self._progress_bars[vid].frame = prog_frame
            
            # Kiểm tra dung lượng và nguồn lưu trữ
            size_mb = 0
            is_cloud = False
            if path and os.path.exists(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
            elif video.get("drive_download_id"):
                is_cloud = True
                    
            duration = video.get("duration", 0)
            if duration > 0:
                mins = int(duration // 60)
                secs = int(duration % 60)
                duration_str = f"({mins}:{secs:02d})"
            else:
                duration_str = "(Chưa xử lý)"
                
            storage_str = f"☁️ Google Drive {duration_str}" if is_cloud else f"📦 {size_mb:.1f} MB {duration_str}"
            ctk.CTkLabel(info_frame, text=storage_str, font=("Segoe UI", 11), text_color=ACCENT if is_cloud else TEXT_DIM).pack(anchor="w", pady=(2, 0))
            
        self._update_limit_state()

    def _update_limit_state(self):
        selected_count = sum(1 for var in self._checkboxes.values() if var.get())
        self._entry_limit.configure(state="normal")
        if selected_count > 0:
            self._entry_limit.delete(0, "end")
            self._entry_limit.insert(0, str(selected_count))
            self._entry_limit.configure(state="disabled", text_color=TEXT_DIM)
        else:
            self._entry_limit.configure(text_color=TEXT_MAIN)

    def _rename_author_dialog(self):
        show_rename_author_dialog(self, self._opt_author_filter, self._load_videos)

    def _delete_author_dialog(self):
        show_delete_author_dialog(self, self._opt_author_filter, self._load_videos)

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
                
        self._log(f"Đã xóa vĩnh viễn {deleted} video (gồm cả file gốc & trên Google Drive).", "SUCCESS")
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
        
        from config.settings import get_user_downloads_dir
        # Thư mục lưu trữ video cục bộ
        local_dir = get_user_downloads_dir(current_user)
        
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
                    import subprocess as sp_local
                    from processor.video_processor import FFPROBE_BIN
                    _cf = sp_local.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    res = sp_local.run([
                        FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration", 
                        "-of", "default=noprint_wrappers=1:nokey=1", str(dest_path)
                    ], capture_output=True, text=True, creationflags=_cf)
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
            if vid in selected_ids and (video.get("download_path") or video.get("drive_download_id")):
                # Khi bypass, file gốc sẽ trở thành file processed
                # Phải copy drive_download_id sang drive_processed_id để VPS biết đường tải về
                db.update_video_status(
                    vid, 
                    "processed", 
                    video.get("download_path") or "",
                    drive_processed_id=video.get("drive_download_id")
                )
                count += 1
                
        self._log(f"Đã chuyển {count} video thẳng sang tab Upload thành công!", "SUCCESS")
        self._load_videos()

    def _save_process_config(self):
        config = {
            "sw_mirror": self._sw_mirror.get(),
            "sw_music": self._sw_music.get(),
            "sw_mute_original": self._sw_mute_original.get(),
            "sw_subtitle": self._sw_subtitle.get(),
            "sw_blur": self._sw_blur.get(),
            "sw_dubbing": self._sw_dubbing.get(),
            "opt_platform": self._opt_platform.get(),
            "opt_ai_mode": self._opt_ai_mode.get(),
            "opt_voice": self._opt_voice.get(),
            "tts_rate": self._entry_tts_rate.get(),
            "opt_sub_pos": self._opt_sub_pos.get(),
            "opt_blur_pos": self._opt_blur_pos.get(),
            "blur_height": self._entry_blur_height.get(),
            "bg_vol": self._entry_bg_vol.get(),
            "sw_yt_crop": self._sw_yt_crop.get(),
            "sw_yt_noise": self._sw_yt_noise.get(),
            "opt_logo_pos": self._opt_logo_pos.get(),
            "process_threads": getattr(self, "_entry_threads", ctk.CTkEntry(self)).get()
        }
        from config.settings import BASE_DIR
        try:
            with open(BASE_DIR / "config" / "process_ui.json", "w", encoding="utf-8") as f:
                import json
                json.dump(config, f, ensure_ascii=False, indent=2)
            from tkinter import messagebox
            messagebox.showinfo("Thành công", "Đã lưu cấu hình Process chung!")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", f"Lỗi lưu config: {e}")

    def _load_process_config(self):
        from config.settings import BASE_DIR
        cfg_path = BASE_DIR / "config" / "process_ui.json"
        if cfg_path.exists():
            try:
                import json
                with open(cfg_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                if "sw_mirror" in config:
                    self._sw_mirror.select() if config["sw_mirror"] else self._sw_mirror.deselect()
                if "sw_music" in config:
                    self._sw_music.select() if config["sw_music"] else self._sw_music.deselect()
                if "sw_mute_original" in config:
                    self._sw_mute_original.select() if config["sw_mute_original"] else self._sw_mute_original.deselect()
                if "sw_subtitle" in config:
                    self._sw_subtitle.select() if config["sw_subtitle"] else self._sw_subtitle.deselect()
                if "sw_blur" in config:
                    self._sw_blur.select() if config["sw_blur"] else self._sw_blur.deselect()
                if "sw_dubbing" in config:
                    self._sw_dubbing.select() if config["sw_dubbing"] else self._sw_dubbing.deselect()
                
                if "opt_platform" in config: self._opt_platform.set(config["opt_platform"])
                if "opt_ai_mode" in config: self._opt_ai_mode.set(config["opt_ai_mode"])
                if "opt_voice" in config: self._opt_voice.set(config["opt_voice"])
                if "opt_sub_pos" in config: self._opt_sub_pos.set(config["opt_sub_pos"])
                if "opt_blur_pos" in config:
                    loaded_pos = config["opt_blur_pos"]
                    if loaded_pos == "Dưới cùng":
                        self._opt_blur_pos.set("Dưới cùng (Đáy video)")
                    elif loaded_pos == "Trên cùng":
                        self._opt_blur_pos.set("Trên cùng (Đỉnh video)")
                    elif loaded_pos in self._opt_blur_pos.cget("values"):
                        self._opt_blur_pos.set(loaded_pos)
                if "opt_logo_pos" in config: self._opt_logo_pos.set(config["opt_logo_pos"])
                
                if "blur_height" in config:
                    b_h = str(config["blur_height"]).strip()
                    if b_h == "15%" and ("tự động" in self._opt_blur_pos.get().lower() or "auto" in self._opt_blur_pos.get().lower()):
                        b_h = "Auto"
                    self._entry_blur_height.delete(0, "end")
                    self._entry_blur_height.insert(0, b_h)
                if hasattr(self, "_update_blur_ui"):
                    self._update_blur_ui(self._opt_blur_pos.get())
                if "bg_vol" in config:
                    self._entry_bg_vol.delete(0, "end")
                    self._entry_bg_vol.insert(0, config["bg_vol"])
                if "process_threads" in config and hasattr(self, "_entry_threads"):
                    self._entry_threads.delete(0, "end")
                    self._entry_threads.insert(0, str(config["process_threads"]))
                    
                if "sw_yt_crop" in config:
                    self._sw_yt_crop.select() if config["sw_yt_crop"] else self._sw_yt_crop.deselect()
                if "sw_yt_noise" in config:
                    self._sw_yt_noise.select() if config["sw_yt_noise"] else self._sw_yt_noise.deselect()
                
                if "tts_rate" in config:
                    self._entry_tts_rate.delete(0, "end")
                    self._entry_tts_rate.insert(0, config["tts_rate"])
                    # Sync slider
                    try:
                        rate_val = int(config["tts_rate"].replace("%",""))
                        self._slider_tts_rate.set(rate_val)
                    except:
                        pass
                
                if hasattr(self, "_toggle_sub_widgets"):
                    self._toggle_sub_widgets()
                if hasattr(self, "_toggle_blur_widgets"):
                    self._toggle_blur_widgets()
            except:
                pass

    def _start_process(self):
        from auth_client import auth_client
        if auth_client.user_info and auth_client.user_info.get("is_expired", True):
            messagebox.showerror("Bản quyền", "Tài khoản của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục sử dụng!")
            return
            
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        
        # Kiểm tra quyền & giới hạn render video:
        # - Admin / Super Admin: Không giới hạn (Full luôn)
        # - Tài khoản đã mua gói (1M, 3M, 6M, 1Y, LT): Dùng theo gói, không giới hạn video
        # - Tài khoản dùng thử (Free Trial 10 ngày): Giới hạn tối đa 5 video/ngày
        trial_info = auth_client.get_trial_info()
        if not trial_info["is_unlimited"]:
            max_allowed = trial_info.get("max_allowed", 5)
            if trial_info["remaining"] <= 0:
                msg = (
                    "🎁 TÀI KHOẢN DÙNG THỬ ĐÃ HẾT HẠN MỨC HÔM NAY\n\n"
                    f"Bạn đã sử dụng hết hạn mức {max_allowed} video/ngày của gói dùng thử miễn phí.\n\n"
                    f"Hạn mức sẽ được làm mới {max_allowed} video vào ngày mai.\n"
                    "👉 Để tiếp tục render video KHÔNG GIỚI HẠN ngay bây giờ, vui lòng nâng cấp gói bản quyền tại tab [Cài đặt ➔ Bản Quyền]!"
                )
                if messagebox.askyesno("Hết Lượt Dùng Thử", msg + "\n\nBạn có muốn mở trang Gia Hạn ngay không?"):
                    try:
                        app_inst = self.winfo_toplevel()
                        if hasattr(app_inst, "_show_tab"):
                            app_inst._show_tab(8)
                            tab_settings = app_inst._tab_frames[8]
                            if hasattr(tab_settings, "_show_payment_dialog"):
                                tab_settings._show_payment_dialog()
                    except Exception:
                        pass
                return

            selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
            if selected_ids and len(selected_ids) > trial_info["remaining"]:
                ans = messagebox.askyesno(
                    "Giới Hạn Dùng Thử Trong Ngày",
                    f"Tài khoản dùng thử hôm nay chỉ còn lại {trial_info['remaining']}/{max_allowed} lượt render video "
                    f"(bạn đang chọn {len(selected_ids)} video).\n\n"
                    f"Hệ thống sẽ chỉ render {trial_info['remaining']} video đầu tiên. Bạn có muốn tiếp tục không?"
                )
                if not ans:
                    return

            
        self._btn_process.configure(state="disabled")
        self._log_widget.clear()
        self._log("Bắt đầu xử lý video...", "INFO")
        if getattr(self, "is_running", False):
            self._cancel_task()
            self._btn_process.configure(state="disabled", text="Đang dừng...")
            return

        self.is_running = True
        self._btn_process.configure(state="normal", text="⏹ Dừng lại", fg_color=DANGER, hover_color="#c0392b")
        self._status_badge.set("Đang xử lý...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu xử lý video...", "INFO")

        title = self._entry_title.get().strip() or None
        limit = int(self._entry_limit.get() or 10)
        try:
            threads = int(self._entry_threads.get().strip() or 2)
            if threads < 1: threads = 1
            if threads > 10: threads = 10
        except Exception:
            threads = 2

        self._start_logging_session(
            "process",
            f"Xử lý {limit} Video (Luồng: {threads})",
            {"title": title, "limit": limit, "threads": threads}
        )
        self._run_in_thread(self._do_process, title, limit, username, threads)

    def _do_process(self, title, limit, username, threads=2):
        from processor.video_processor import VideoProcessor
        from database.db_manager import DatabaseManager
        from config.settings import PROCESSOR_CONFIG
        from loguru import logger
        
        # Bắt toàn bộ log Sub/Voice/TTS và in trực tiếp vào khung Log của GUI
        def _gui_log_sink(message):
            try:
                record = message.record
                text = record["message"].strip()
                if any(k in text for k in ["Sub", "Voice", "TTS", "ĐỐI CHIẾU", "📝", "🎙️", "Dịch", "Whisper", "Model", "CUDA", "CPU"]):
                    lvl = record["level"].name
                    self._log(text, lvl if lvl in ["INFO", "WARNING", "ERROR", "DEBUG", "SUCCESS"] else "INFO")
            except Exception:
                pass
        
        sink_id = logger.add(_gui_log_sink, level="INFO")
        
        def progress_cb(vid, pct, status):
            # Hàm này được gọi từ thread, dùng after để update UI an toàn
            def update_ui():
                if "Lỗi" in status or "Error" in status:
                    self._log(f"[{vid[:10]}] {status}", "ERROR")
                elif "DEBUG" in status:
                    # Gỡ bỏ prefix [DEBUG] nếu có và in ra log
                    clean_status = status.replace("[DEBUG]", "").strip()
                    self._log(clean_status, "INFO")
                    return
                elif any(k in status for k in ["📝", "🎙️", "Sub", "Voice", "ĐỐI CHIẾU"]):
                    self._log(status, "INFO")
                    return
                    
                bar = self._progress_bars.get(vid)
                lbl = self._progress_labels.get(vid)
                if bar and lbl:
                    if not bar.frame.winfo_ismapped():
                        bar.frame.pack(anchor="w", pady=(0, 4))
                    bar.set(pct / 100.0)
                    lbl.configure(text=f"{status} {int(pct)}%")
            self.after(0, update_ui)
        
        # Lấy danh sách ID đã tick
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        self._log(f"[DEBUG] Đã phát hiện {len(selected_ids)} video được tick chọn.", "INFO")
        
        # Giới hạn số lượng nếu là tài khoản dùng thử
        from auth_client import auth_client
        trial_info = auth_client.get_trial_info()
        if not trial_info["is_unlimited"]:
            max_allowed = trial_info.get("max_allowed", 5)
            if trial_info["remaining"] <= 0:
                self._log(f"Tài khoản dùng thử đã hết hạn mức {max_allowed} video hôm nay. Vui lòng đợi qua ngày mai hoặc nâng cấp bản quyền!", "ERROR")
                self._on_task_done()
                return
            if len(selected_ids) > trial_info["remaining"]:
                self._log(f"Tài khoản dùng thử: Giới hạn chỉ render {trial_info['remaining']} video còn lại trong hạn mức hôm nay.", "WARNING")
                selected_ids = selected_ids[:trial_info["remaining"]]

        self._log(f"Bắt đầu xử lý {len(selected_ids)} video với {threads} luồng song song...", "INFO")

        
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
        try:
            PROCESSOR_CONFIG["mute_original_audio"] = int(getattr(self, "_sw_mute_original", ctk.CTkSwitch(self)).get()) == 1
        except Exception:
            PROCESSOR_CONFIG["mute_original_audio"] = False
            
        bg_vol_str = getattr(self, "_entry_bg_vol", ctk.CTkEntry(self)).get().strip().replace("%", "")
        try:
            vol_float = float(bg_vol_str) / 100.0
            if vol_float < 0: vol_float = 0.0
            if vol_float > 1: vol_float = 1.0
            PROCESSOR_CONFIG["bg_music_volume"] = vol_float
        except Exception:
            PROCESSOR_CONFIG["bg_music_volume"] = 0.15 # fallback
            
        # Parse Blur Options
        try:
            PROCESSOR_CONFIG["blur_enabled"] = int(getattr(self, "_sw_blur", ctk.CTkSwitch(self)).get()) == 1
        except Exception:
            PROCESSOR_CONFIG["blur_enabled"] = False
            
        blur_height_str = getattr(self, "_entry_blur_height", ctk.CTkEntry(self)).get().strip().replace("%", "").lower()
        if blur_height_str in ("auto", "tự động", ""):
            PROCESSOR_CONFIG["blur_height"] = None
        else:
            try:
                blur_height_float = float(blur_height_str) / 100.0
                if blur_height_float <= 0: PROCESSOR_CONFIG["blur_enabled"] = False
                if blur_height_float > 1: blur_height_float = 1.0
                PROCESSOR_CONFIG["blur_height"] = blur_height_float
            except Exception:
                PROCESSOR_CONFIG["blur_height"] = None
        
        raw_blur_pos = getattr(self, "_opt_blur_pos", ctk.CTkOptionMenu(self, values=[""])).get()
        if "tự động" in raw_blur_pos.lower() or "auto" in raw_blur_pos.lower():
            PROCESSOR_CONFIG["blur_position"] = "auto"
        elif "douyin" in raw_blur_pos.lower() or "20%" in raw_blur_pos:
            PROCESSOR_CONFIG["blur_position"] = "douyin"
        elif "cao" in raw_blur_pos.lower() or "tiktok" in raw_blur_pos.lower():
            PROCESSOR_CONFIG["blur_position"] = "high"
        elif "trên cùng" in raw_blur_pos.lower():
            PROCESSOR_CONFIG["blur_position"] = "top"
        else:
            PROCESSOR_CONFIG["blur_position"] = "bottom"
        
        # Parse TTS Options
        voice_sel = self._opt_voice.get()
        if "Vbee" in voice_sel:
            if "Ngọc Huyền" in voice_sel:
                PROCESSOR_CONFIG["tts_voice"] = "vbee-hn_female_ngochuyen_vdc_cg"
            elif "Mai Phương" in voice_sel:
                PROCESSOR_CONFIG["tts_voice"] = "vbee-hn_female_maiphuong_vdc_cg"
            elif "Minh Hoàng" in voice_sel:
                PROCESSOR_CONFIG["tts_voice"] = "vbee-sg_male_minhhoang_vdc_cg"
            elif "Đa giọng" in voice_sel:
                PROCESSOR_CONFIG["tts_voice"] = "vbee-multi"
            else:
                PROCESSOR_CONFIG["tts_voice"] = "vbee-hn_female_ngochuyen_vdc_cg"
        elif "Đa giọng" in voice_sel:
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
        processor = VideoProcessor(db=db, username=username)
        titles    = {}
        if title:
            for vid in selected_ids:
                titles[vid] = title
                
        try:
            results = processor.process_downloaded_videos(
                titles=titles, 
                limit=limit, 
                video_ids=selected_ids, 
                cancel_check=lambda: self.cancel_flag,
                progress_callback=progress_cb,
                max_workers=threads
            )
            if self.cancel_flag:
                self._log("Đã ngắt quá trình xử lý (Stop).", "WARNING")
            else:
                from auth_client import auth_client
                if not trial_info["is_unlimited"]:
                    auth_client.record_trial_render(len(results))

                failed_items = getattr(processor, "last_failed_videos", [])
                
                if len(results) == 0:
                    self._log("❌ Xử lý hoàn tất nhưng 0 video thành công!", "ERROR")
                    if failed_items:
                        for it in failed_items:
                            self._log(f"  ❌ Video #{it['video_id']}: {it['error']}", "ERROR")
                        err_reasons = "; ".join([f"Video #{it['video_id']}: {it['error']}" for it in failed_items])
                        auth_client.send_telemetry("ERROR", f"[PROCESS THẤT BẠI] 0/{len(failed_items)} video. Lỗi chi tiết: {err_reasons} (Blur: {PROCESSOR_CONFIG.get('blur_enabled')}, Sub: {PROCESSOR_CONFIG.get('subtitle_overlay')}, TTS: {PROCESSOR_CONFIG.get('tts_voice')})")
                    else:
                        if selected_ids:
                            self._log(f"  ❌ Không tìm thấy video hợp lệ trong CSDL để xử lý (đã chọn {len(selected_ids)} ID: {selected_ids})!", "ERROR")
                            auth_client.send_telemetry("ERROR", f"[PROCESS THẤT BẠI] 0 video. Không tìm thấy video hợp lệ trong CSDL ứng với IDs: {selected_ids}")
                        else:
                            self._log("  ❌ Hàng đợi trống: Không có video nào ở trạng thái 'Đã tải về' trong CSDL!", "ERROR")
                            auth_client.send_telemetry("ERROR", "[PROCESS THẤT BẠI] 0 video. Hàng đợi CSDL không có video nào ở trạng thái 'Đã tải về'.")
                elif failed_items:
                    self._log(f"⚠️ Đã xử lý {len(results)} videos ({len(failed_items)} video lỗi)!", "WARNING")
                    for it in failed_items:
                        self._log(f"  ❌ Video #{it['video_id']}: {it['error']}", "ERROR")
                    err_reasons = "; ".join([f"Video #{it['video_id']}: {it['error']}" for it in failed_items])
                    auth_client.send_telemetry("ERROR", f"[PROCESS CÓ LỖI] {len(results)} thành công, {len(failed_items)} lỗi: {err_reasons}")
                else:
                    self._log(f"✅ Đã xử lý thành công {len(results)}/{len(results)} videos!", "SUCCESS")
                    auth_client.send_telemetry("PROCESS", f"Hoàn thành xử lý {len(results)} video (Blur: {PROCESSOR_CONFIG.get('blur_enabled')}, Sub: {PROCESSOR_CONFIG.get('subtitle_overlay')}, TTS: {PROCESSOR_CONFIG.get('tts_voice')})")
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self._log(f"❌ Lỗi ngoại lệ hệ thống xử lý video: {e}", "ERROR")
            from auth_client import auth_client
            auth_client.send_telemetry("ERROR", f"[PROCESS NGOẠI LỆ] {str(e)} | Trace: {tb_str[-250:]}")
        finally:
            try:
                logger.remove(sink_id)
            except Exception:
                pass
            # Load lại danh sách sau khi xử lý xong
            self.after(0, self._load_videos)
            self._on_task_done()

    def _on_task_done(self):
        super()._on_task_done()
        self.is_running = False
        self.after(0, lambda: self._btn_process.configure(state="normal", text="▶  Bắt đầu Xử lý", fg_color=ACCENT, hover_color=ACCENT_HOVER))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS))


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
        self._video_accounts_fb = {}
        self._saved_assigned_accounts = {}
        self._current_session_id = None
        self._build()
        self.after(200, self._load_videos)

    @staticmethod
    def _get_user_cookies_dir():
        return get_user_cookies_dir()

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

    @staticmethod
    def _get_facebook_accounts():
        user_dir = UploadTab._get_user_cookies_dir()
        accounts = [f.name for f in user_dir.glob("facebook_*.json")]
        return ["Không up"] + accounts if accounts else ["Không up"]

    def _build(self):
        # Header
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        t_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        t_box.pack(side="left")
        ctk.CTkLabel(
            t_box, text="📤  Upload & Lên Lịch Đăng Đa Nền Tảng",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            t_box, text="Tự động phân phối video lên TikTok, YouTube Shorts & Facebook Reels với AI Caption bắt trend",
            font=("Segoe UI", 11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        
        self._btn_help_upload = ctk.CTkButton(
            hdr_frame, text="❓ Hướng dẫn", width=105, height=32, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_CARD,
            command=self._toggle_upload_help
        )
        self._btn_help_upload.pack(side="right")
        
        # Guide frame (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 QUY TRÌNH 3 BƯỚC ĐĂNG BÀI & HẸN GIỜ DÀNH CHO NGƯỜI MỚI", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• Bước 1 - Chọn Video & Gán Nick Đăng:\n"
            "  - Danh sách video bên trái là những video đã qua bước 'Process' (sẵn sàng đăng).\n"
            "  - Tích chọn (☑) vào các video muốn đăng.\n"
            "  - Chọn tài khoản TikTok / YouTube / Facebook tương ứng ở từng video (hoặc gán nhanh ở sidebar bên phải).\n"
            "  - 💡 Nếu chưa thấy nick của bạn trong menu, hãy qua tab 'Accounts' để thêm nick & cấu hình Proxy trước!\n"
            "• Bước 2 - Sáng Tạo Tiêu Đề & Hashtags (Viral AI):\n"
            "  - Bấm nút '✨ AI Caption' ở thanh công cụ để AI (Gemini / Groq) tự động phân tích video và viết tiêu đề giật tít + bộ hashtags triệu view theo ngách.\n"
            "  - Bạn cũng có thể click trực tiếp vào ô tiêu đề trên từng card video để tự chỉnh sửa theo ý thích.\n"
            "• Bước 3 - Lên Lịch & Bắt Đầu Upload:\n"
            "  - 'Đăng ngay': Tool sẽ mở trình duyệt tự động và đăng bài lần lượt.\n"
            "  - 'Hẹn giờ đăng': Chọn các khung giờ vàng (11h trưa, 19h tối, 21h tối) để hệ thống tự động đăng rải đều, tránh đăng dồn dập bị bóp tương tác.\n"
            "  - Bấm nút '🚀 Bắt đầu Upload' để hệ thống tự động hoàn thành!"
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không grid lúc khởi tạo

        # Khởi tạo 2 cột (Trái: Danh sách video, Phải: Sidebar cấu hình cố định độ rộng 380px)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(2, weight=1)

        # --- LEFT PANE ---
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 15))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        # Danh sách chọn video - Header chia 2 hàng khoa học tránh tràn ngang
        list_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # Hàng 1: Bộ lọc tác giả / kênh + Refresh
        row_filter = ctk.CTkFrame(list_header, fg_color="transparent")
        row_filter.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row_filter, text="Danh sách Video đã xử lý:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left")
        self._opt_author_filter_up = ctk.CTkOptionMenu(row_filter, values=["Tất cả Kênh"], width=130, command=lambda _: self._load_videos())
        self._opt_author_filter_up.pack(side="left", padx=(10, 0))
        self._btn_rename_author_up = ctk.CTkButton(
            row_filter, text="✏️ Đổi tên", width=75, height=24, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=self._rename_author_dialog
        )
        self._btn_rename_author_up.pack(side="left", padx=(6, 0))
        self._btn_delete_author_up = ctk.CTkButton(
            row_filter, text="🗑 Xóa nhóm", width=85, height=24, font=("Segoe UI", 11, "bold"),
            fg_color="#c0392b", hover_color="#e74c3c", command=self._delete_author_dialog
        )
        self._btn_delete_author_up.pack(side="left", padx=(6, 0))

        ctk.CTkButton(row_filter, text="🔄 Refresh", width=65, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._load_videos).pack(side="right")
        ctk.CTkButton(row_filter, text="🧹 Dọn rác", width=65, height=24, fg_color="#7f8c8d", hover_color="#95a5a6", command=self._clean_missing_videos).pack(side="right", padx=(0, 6))

        # Hàng 2: Thanh công cụ thao tác hàng loạt
        row_actions = ctk.CTkFrame(list_header, fg_color="transparent")
        row_actions.pack(fill="x")
        ctk.CTkButton(row_actions, text="☑ Chọn tất cả", width=90, height=24, fg_color=BORDER, hover_color=BG_CARD, command=self._toggle_selection).pack(side="left")
        ctk.CTkButton(row_actions, text="✨ AI Caption", width=95, height=24, font=("Segoe UI", 11, "bold"), fg_color="#8e44ad", hover_color="#9b59b6", command=self._generate_batch_ai_captions).pack(side="left", padx=(6, 0))
        ctk.CTkButton(row_actions, text="⏪ Về Process", width=85, height=24, fg_color="#f39c12", hover_color="#e67e22", command=self._revert_to_process).pack(side="left", padx=(6, 0))
        ctk.CTkButton(row_actions, text="🗑 Xóa đã chọn", width=95, height=24, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_selected).pack(side="left", padx=(6, 0))
        
        self._video_list_frame = ctk.CTkScrollableFrame(left_frame, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._video_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        self._log_widget = LogWidget(left_frame, height=125)
        self._log_toolbar = LogToolbar(left_frame, self._log_widget, module="upload", title="📋  Nhật ký Upload (Logs):")
        self._log_toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self._log_widget.grid(row=3, column=0, sticky="nsew")

        # --- RIGHT PANE (SIDEBAR CẤU HÌNH CỐ ĐỊNH) ---
        right_frame = ctk.CTkScrollableFrame(self, width=380, fg_color="transparent")
        right_frame.grid(row=2, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        # Options card
        opts = ctk.CTkFrame(right_frame, fg_color=BG_CARD, corner_radius=12,
                             border_width=1, border_color=BORDER)
        opts.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(0, weight=1)

        # Cấu hình xếp dọc theo Sidebar
        config_frame = ctk.CTkFrame(opts, fg_color="transparent")
        config_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 14))
        
        # --- Cấu hình chung ---
        row_cfg_top = ctk.CTkFrame(config_frame, fg_color="transparent")
        row_cfg_top.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(row_cfg_top, text="⚙️ Cấu hình chung", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(side="left")
        ctk.CTkButton(
            row_cfg_top, text="💾 Lưu cấu hình", width=100, height=26, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=self._save_upload_config
        ).pack(side="right")
        
        row_limit = ctk.CTkFrame(config_frame, fg_color="transparent")
        row_limit.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row_limit, text="Số video upload:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 8))
        self._entry_limit = ctk.CTkEntry(row_limit, width=50, height=26, font=("Segoe UI", 11, "bold"), justify="center", fg_color=BG_DARK, border_color=BORDER)
        self._entry_limit.insert(0, "4")
        self._entry_limit.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row_limit, text="video / lần", font=("Segoe UI", 10), text_color=TEXT_MUTED).pack(side="left")
        
        # Các switch cấu hình - Mỗi switch 1 dòng riêng để không bị đè mất chữ
        self._sw_cleanup_upload = ctk.CTkSwitch(
            config_frame, text="Dọn dẹp file sau khi đăng", font=("Segoe UI", 11), text_color=TEXT_MAIN
        )
        self._sw_cleanup_upload.select()
        self._sw_cleanup_upload.pack(anchor="w", pady=(0, 8))

        # Bật/Tắt Hiện Trình Duyệt khi Upload (Headless)
        self._sw_show_browser = ctk.CTkSwitch(
            config_frame, text="Hiện trình duyệt khi upload ❔", font=("Segoe UI", 11, "bold"),
            text_color=TEXT_MAIN, cursor="hand2"
        )
        self._sw_show_browser.select() # Mặc định BẬT
        self._sw_show_browser.pack(anchor="w", pady=(0, 4))
        ToolTip(self._sw_show_browser, "BẬT (ON): Mở cửa sổ trình duyệt Chrome để xem trực tiếp quá trình tải video lên TikTok.\nTẮT (OFF): Chạy ẩn ngầm (Headless) tiết kiệm tối đa RAM & CPU, không mở cửa sổ làm phiền màn hình làm việc.")

        # Khôi phục cấu hình trước đó nếu có
        try:
            from config.settings import BASE_DIR
            import json
            cfg_path = BASE_DIR / "config" / "upload_ui.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    u_cfg = json.load(f)
                    if "show_browser" in u_cfg:
                        if u_cfg["show_browser"]:
                            self._sw_show_browser.select()
                        else:
                            self._sw_show_browser.deselect()
        except Exception:
            pass

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Nền tảng Đăng ---
        ctk.CTkLabel(config_frame, text="Nền tảng Upload", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 6))
        
        row2 = ctk.CTkFrame(config_frame, fg_color=BG_DARK, corner_radius=8, border_width=1, border_color=BORDER)
        row2.pack(fill="x", pady=(0, 6), ipady=4)
        row2.grid_columnconfigure((0, 1, 2), weight=1)
        
        self._sw_platform_tt = ctk.CTkSwitch(row2, text="TikTok", font=("Segoe UI", 11, "bold"))
        self._sw_platform_tt.select()
        self._sw_platform_tt.grid(row=0, column=0, padx=(10, 4), pady=4, sticky="w")
        
        self._sw_platform_yt = ctk.CTkSwitch(row2, text="YouTube", font=("Segoe UI", 11, "bold"))
        self._sw_platform_yt.select()
        self._sw_platform_yt.grid(row=0, column=1, padx=(4, 4), pady=4, sticky="w")
        
        self._sw_platform_fb = ctk.CTkSwitch(row2, text="Facebook", font=("Segoe UI", 11, "bold"))
        self._sw_platform_fb.select()
        self._sw_platform_fb.grid(row=0, column=2, padx=(4, 6), pady=4, sticky="w")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Phân bổ tự động (Dải đều video) ---
        ctk.CTkLabel(config_frame, text="⚡ Phân bổ tự động (Dải đều nick)", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 6))
        
        row_dist = ctk.CTkFrame(config_frame, fg_color="transparent")
        row_dist.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(row_dist, text="Số video / nick:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 6))
        self._entry_vids_per_acc = ctk.CTkEntry(row_dist, width=45, height=26, font=("Segoe UI", 11, "bold"), justify="center", fg_color=BG_DARK, border_color=BORDER)
        self._entry_vids_per_acc.insert(0, "2")
        self._entry_vids_per_acc.pack(side="left", padx=(0, 10))
        
        self._sw_round_robin = ctk.CTkSwitch(row_dist, text="Lặp vòng", font=("Segoe UI", 11), text_color=TEXT_MAIN)
        self._sw_round_robin.pack(side="right")
        
        self._btn_dist_all = ctk.CTkButton(
            config_frame, text="🔀 Dải đều tất cả nền tảng", height=30, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=self._distribute_all
        )
        self._btn_dist_all.pack(fill="x", pady=(0, 8))

        # --- Cấu hình Đa luồng Upload (Concurrent Threads) ---
        row_threads = ctk.CTkFrame(config_frame, fg_color="transparent")
        row_threads.pack(fill="x", pady=(2, 4))

        lbl_threads = ctk.CTkLabel(row_threads, text="🚀 Số luồng upload: ❔", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN, cursor="hand2")
        lbl_threads.pack(side="left", padx=(0, 6))
        ToolTip(lbl_threads, "Số lượng tài khoản / trình duyệt chạy upload đồng thời cùng lúc.\nVí dụ: Nhập 5 thì hệ thống sẽ mở 5 luồng upload song song cho 5 tài khoản thay vì chờ lần lượt từng nick.")

        self._entry_upload_threads = ctk.CTkEntry(row_threads, width=45, height=26, font=("Segoe UI", 11, "bold"), fg_color=BG_DARK, border_color=BORDER, justify="center")
        self._entry_upload_threads.insert(0, "3")
        self._entry_upload_threads.pack(side="right")

        # Nút chọn nhanh số luồng
        row_thread_btns = ctk.CTkFrame(config_frame, fg_color="transparent")
        row_thread_btns.pack(fill="x", pady=(2, 6))
        row_thread_btns.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for idx, t_val in enumerate(["1", "2", "3", "5"]):
            ctk.CTkButton(
                row_thread_btns, text=f"{t_val} luồng", height=24, font=("Segoe UI", 10, "bold"),
                fg_color=BORDER, hover_color=BG_CARD,
                command=lambda v=t_val: self._set_upload_threads(v)
            ).grid(row=0, column=idx, padx=2, sticky="ew")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Tài khoản TikTok ---
        ctk.CTkLabel(config_frame, text="🎵 Tài khoản TikTok mặc định", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row3 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 10))
        
        accounts = self._get_tiktok_accounts()
        self._opt_account = ctk.CTkOptionMenu(
            row3, values=accounts, font=("Segoe UI", 11),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account.pack(fill="x", pady=(0, 6))
        
        tt_btns = ctk.CTkFrame(row3, fg_color="transparent")
        tt_btns.pack(fill="x")
        tt_btns.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_apply_acc = ctk.CTkButton(
            tt_btns, text="Áp dụng All", height=26, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._apply_account_to_all
        )
        self._btn_apply_acc.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        
        self._btn_dist_acc = ctk.CTkButton(
            tt_btns, text="🔀 Dải đều", height=26, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=lambda: self._distribute_single("tiktok")
        )
        self._btn_dist_acc.grid(row=0, column=1, sticky="ew", padx=3)
        
        self._btn_manage_acc = ctk.CTkButton(
            tt_btns, text="⚙ Quản lý", height=26, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc.grid(row=0, column=2, sticky="ew", padx=(3, 0))

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Tài khoản YouTube ---
        ctk.CTkLabel(config_frame, text="🎬 Tài khoản YouTube mặc định", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row4 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row4.pack(fill="x", pady=(0, 10))
        
        yt_accounts = self._get_youtube_accounts()
        self._opt_account_yt = ctk.CTkOptionMenu(
            row4, values=yt_accounts, font=("Segoe UI", 11),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_yt.pack(fill="x", pady=(0, 6))
        
        yt_btns = ctk.CTkFrame(row4, fg_color="transparent")
        yt_btns.pack(fill="x")
        yt_btns.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_apply_acc_yt = ctk.CTkButton(
            yt_btns, text="Áp dụng All", height=26, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._apply_account_to_all_yt
        )
        self._btn_apply_acc_yt.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        
        self._btn_dist_acc_yt = ctk.CTkButton(
            yt_btns, text="🔀 Dải đều", height=26, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=lambda: self._distribute_single("youtube")
        )
        self._btn_dist_acc_yt.grid(row=0, column=1, sticky="ew", padx=3)
        
        self._btn_manage_acc_yt = ctk.CTkButton(
            yt_btns, text="⚙ Quản lý", height=26, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc_yt.grid(row=0, column=2, sticky="ew", padx=(3, 0))

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Tài khoản Facebook ---
        ctk.CTkLabel(config_frame, text="📘 Tài khoản Facebook mặc định", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row5 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row5.pack(fill="x", pady=(0, 10))
        
        fb_accounts = self._get_facebook_accounts()
        self._opt_account_fb = ctk.CTkOptionMenu(
            row5, values=fb_accounts, font=("Segoe UI", 11),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_fb.pack(fill="x", pady=(0, 6))
        
        fb_btns = ctk.CTkFrame(row5, fg_color="transparent")
        fb_btns.pack(fill="x")
        fb_btns.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_apply_acc_fb = ctk.CTkButton(
            fb_btns, text="Áp dụng All", height=26, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._apply_account_to_all_fb
        )
        self._btn_apply_acc_fb.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        
        self._btn_dist_acc_fb = ctk.CTkButton(
            fb_btns, text="🔀 Dải đều", height=26, font=("Segoe UI", 11, "bold"),
            fg_color="#2980b9", hover_color="#3498db", command=lambda: self._distribute_single("facebook")
        )
        self._btn_dist_acc_fb.grid(row=0, column=1, sticky="ew", padx=3)
        
        self._btn_manage_acc_fb = ctk.CTkButton(
            fb_btns, text="⚙ Quản lý", height=26, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc_fb.grid(row=0, column=2, sticky="ew", padx=(3, 0))

        # Buttons
        btn_row = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._btn_save_config = ctk.CTkButton(
            btn_row, text="💾  Lưu Cấu Hình Upload", height=36,
            font=("Segoe UI", 12, "bold"),
            fg_color="#2980b9", hover_color="#3498db",
            command=self._save_upload_config,
        )
        self._btn_save_config.pack(fill="x", pady=(0, 8))

        self._btn_upload = ctk.CTkButton(
            btn_row, text="▶  Bắt đầu Upload", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._start_upload,
        )
        self._btn_upload.pack(fill="x", pady=(0, 6))

        self._status_badge = StatusBadge(btn_row, "Idle", TEXT_DIM)
        self._status_badge.pack(anchor="center")

        # Nạp cấu hình đã lưu trước đó
        self._load_upload_config()

    def _toggle_upload_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_upload"):
                self._btn_help_upload.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
                if hasattr(self, "_btn_help_upload"):
                    self._btn_help_upload.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

    def _load_videos(self):
        """Hiển thị danh sách video đã processed vào scrollable frame."""
        for widget in self._video_list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        self._video_accounts.clear()
        self._video_accounts_yt.clear()
        self._video_accounts_fb.clear()
        self._custom_captions = {}

        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username") if auth_client.user_info else None
        
        author_val = self._opt_author_filter_up.get() if hasattr(self, "_opt_author_filter_up") else "Tất cả Kênh"
        if hasattr(self, "_opt_author_filter_up"):
            authors = db.get_authors(status="processed", username=current_user, pending_only=True)
            new_values = ["Tất cả Kênh"] + authors
            self._opt_author_filter_up.configure(values=new_values)
            if author_val not in new_values:
                author_val = "Tất cả Kênh"
                self._opt_author_filter_up.set("Tất cả Kênh")
        author_filter = None if author_val == "Tất cả Kênh" else author_val
        videos = db.get_pending_videos(limit=100, username=current_user, author=author_filter)

        
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
            
            # --- ROW 1: Header (Checkbox, ID, Size, Xem) ---
            row1 = ctk.CTkFrame(card, fg_color="transparent")
            row1.pack(fill="x", padx=10, pady=(10, 4))
            
            cb = ctk.CTkCheckBox(row1, text="", variable=var, width=24, command=self._update_selected_count)
            cb.pack(side="left")
            
            ctk.CTkLabel(row1, text=f"ID: {vid}", font=("Consolas", 11, "bold"), text_color=ACCENT).pack(side="left", padx=5)
            author_name = video.get("author")
            if author_name:
                ctk.CTkLabel(row1, text=f"🏷️ {author_name}", font=("Segoe UI", 11, "bold"), text_color="#3498db").pack(side="left", padx=(2, 8))
            
            path = video.get("processed_path")
            drive_processed_id = video.get("drive_processed_id")
            drive_download_id = video.get("drive_download_id")
            drive_id = drive_processed_id or drive_download_id
            
            size_mb = 0
            import os
            import webbrowser
            if path and os.path.exists(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                ctk.CTkLabel(row1, text=f"📦 {size_mb:.1f} MB", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(5, 10))
                ctk.CTkButton(
                    row1, text="▶ Xem", width=60, height=24, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda p=path: os.startfile(p) if os.name == 'nt' else None
                ).pack(side="left", padx=(0, 10))
            elif drive_id:
                ctk.CTkLabel(row1, text="☁️ Google Drive", font=("Segoe UI", 11), text_color=ACCENT).pack(side="left", padx=(5, 10))
                ctk.CTkButton(
                    row1, text="☁️ Xem Drive", width=90, height=24, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda d_id=drive_id: webbrowser.open(f"https://drive.google.com/file/d/{d_id}/view")
                ).pack(side="left", padx=(0, 10))
            else:
                ctk.CTkLabel(row1, text=f"📦 {size_mb:.1f} MB", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(5, 10))

            # --- THỜI LƯỢNG (Duration) & THỜI GIAN XỬ LÝ (Timestamp) ---
            duration = video.get("duration")
            if duration and float(duration) > 0:
                d_sec = int(float(duration))
                d_min = d_sec // 60
                d_rem = d_sec % 60
                duration_text = f"⏱️ {d_min:02d}:{d_rem:02d}"
                ctk.CTkLabel(row1, text=duration_text, font=("Segoe UI", 11, "bold"), text_color=SUCCESS).pack(side="left", padx=(0, 10))

            ts_raw = video.get("processed_at") or video.get("crawled_at")
            if ts_raw:
                try:
                    clean_ts = str(ts_raw).replace("T", " ").split(".")[0].strip()
                    parts = clean_ts.split(" ")
                    if len(parts) == 2:
                        d_part, t_part = parts
                        ymd = d_part.split("-")
                        time_hm = ":".join(t_part.split(":")[:2])
                        if len(ymd) == 3:
                            time_disp = f"🕒 {time_hm} ({ymd[2]}/{ymd[1]})"
                        else:
                            time_disp = f"🕒 {time_hm}"
                    else:
                        time_disp = f"🕒 {clean_ts[:16]}"
                except Exception:
                    time_disp = f"🕒 {str(ts_raw)[:16]}"
                ctk.CTkLabel(row1, text=time_disp, font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 10))

            # --- ROW 1.5: Platform Account Selector Bar ---
            acc_bar = ctk.CTkFrame(card, fg_color=BG_DARK, corner_radius=6)
            acc_bar.pack(fill="x", padx=10, pady=(2, 6), ipady=2)
            
            saved_acc = getattr(self, "_saved_assigned_accounts", {}).get(vid, {})

            # TikTok
            ctk.CTkLabel(acc_bar, text="🎵 TikTok:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=(10, 4), pady=4)
            accounts = self._get_tiktok_accounts()
            opt_acc = ctk.CTkOptionMenu(acc_bar, values=accounts, font=("Segoe UI", 11), width=120, height=26, fg_color=BG_CARD, button_color=BORDER, button_hover_color=BG_DARK)
            opt_acc.pack(side="left", padx=(0, 14), pady=4)
            saved_tt = saved_acc.get("tt")
            if saved_tt and saved_tt in accounts:
                opt_acc.set(saved_tt)
            else:
                global_acc = getattr(self, "_opt_account", None)
                if global_acc and global_acc.get() in accounts:
                    opt_acc.set(global_acc.get())
            self._video_accounts[vid] = opt_acc

            # YouTube
            ctk.CTkLabel(acc_bar, text="🎬 YouTube:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=(0, 4), pady=4)
            yt_accounts = self._get_youtube_accounts()
            opt_acc_yt = ctk.CTkOptionMenu(acc_bar, values=yt_accounts, font=("Segoe UI", 11), width=120, height=26, fg_color=BG_CARD, button_color=BORDER, button_hover_color=BG_DARK)
            opt_acc_yt.pack(side="left", padx=(0, 14), pady=4)
            saved_yt = saved_acc.get("yt")
            if saved_yt and saved_yt in yt_accounts:
                opt_acc_yt.set(saved_yt)
            else:
                global_acc_yt = getattr(self, "_opt_account_yt", None)
                if global_acc_yt and global_acc_yt.get() in yt_accounts:
                    opt_acc_yt.set(global_acc_yt.get())
            self._video_accounts_yt[vid] = opt_acc_yt

            # Facebook
            ctk.CTkLabel(acc_bar, text="📘 Facebook:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=(0, 4), pady=4)
            fb_accounts = self._get_facebook_accounts()
            opt_acc_fb = ctk.CTkOptionMenu(acc_bar, values=fb_accounts, font=("Segoe UI", 11), width=120, height=26, fg_color=BG_CARD, button_color=BORDER, button_hover_color=BG_DARK)
            opt_acc_fb.pack(side="left", padx=(0, 10), pady=4)
            saved_fb = saved_acc.get("fb")
            if saved_fb and saved_fb in fb_accounts:
                opt_acc_fb.set(saved_fb)
            else:
                global_acc_fb = getattr(self, "_opt_account_fb", None)
                if global_acc_fb and global_acc_fb.get() in fb_accounts:
                    opt_acc_fb.set(global_acc_fb.get())
            self._video_accounts_fb[vid] = opt_acc_fb

            # --- ROW 2: Editable Caption Title ---
            display_title = video.get("title_vi") or video.get("title") or "No title"
            if isinstance(display_title, str) and display_title.startswith("['") and "'," in display_title:
                try:
                    import ast
                    parsed = ast.literal_eval(display_title)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        display_title = str(parsed[0])
                except Exception:
                    pass
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
                
            def make_apply_all_cmd(tb_widget):
                def cmd():
                    new_cap = tb_widget.get("1.0", "end-1c")
                    selected_ids = [v_id for v_id, var in self._checkboxes.items() if var.get()]
                    if not selected_ids:
                        messagebox.showwarning("Cảnh báo", "Vui lòng tick chọn ít nhất 1 video để áp dụng!")
                        return
                    from database.db_manager import DatabaseManager
                    db_tmp = DatabaseManager()
                    count = 0
                    for v_id in selected_ids:
                        db_tmp.update_custom_caption(v_id, new_cap)
                        if v_id in self._custom_captions:
                            self._custom_captions[v_id].delete("1.0", "end")
                            self._custom_captions[v_id].insert("1.0", new_cap)
                        count += 1
                    messagebox.showinfo("Thành công", f"Đã áp dụng Caption cho {count} video được chọn!")
                return cmd
                
            def make_ai_cmd(video_dict, tb_widget, btn_widget):
                def cmd():
                    btn_widget.configure(text="⏳ Đang tạo...", state="disabled")
                    def _worker():
                        try:
                            from utils.translator import generate_tiktok_metadata_with_ai
                            from database.db_manager import DatabaseManager
                            res = generate_tiktok_metadata_with_ai(
                                original_title=video_dict.get("title", ""),
                                translated_title=video_dict.get("title_vi", ""),
                            )
                            new_cap = res.get("caption", "").strip()
                            if new_cap:
                                db_tmp = DatabaseManager()
                                db_tmp.update_custom_caption(video_dict["video_id"], new_cap)
                                def _ui():
                                    tb_widget.delete("1.0", "end")
                                    tb_widget.insert("1.0", new_cap)
                                    btn_widget.configure(text="✨ AI Caption", state="normal")
                                    self._log(f"✨ Đã tạo AI Caption ({res.get('category')}): {new_cap[:60]}...", "SUCCESS")
                                self.after(0, _ui)
                            else:
                                self.after(0, lambda: btn_widget.configure(text="✨ AI Caption", state="normal"))
                        except Exception as e:
                            self.after(0, lambda: btn_widget.configure(text="✨ AI Caption", state="normal"))
                            self._log(f"Lỗi tạo AI Caption: {e}", "ERROR")
                    threading.Thread(target=_worker, daemon=True).start()
                return cmd
                
            btn_save = ctk.CTkButton(row4, text="💾 Lưu Caption", width=110, height=26, font=("Segoe UI", 12, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=make_save_cmd(vid, textbox))
            btn_save.pack(side="left")
            
            btn_ai = ctk.CTkButton(row4, text="✨ AI Caption", width=110, height=26, font=("Segoe UI", 12, "bold"), fg_color="#8e44ad", hover_color="#9b59b6")
            btn_ai.configure(command=make_ai_cmd(video, textbox, btn_ai))
            btn_ai.pack(side="left", padx=(8, 0))
            
            btn_apply_all = ctk.CTkButton(row4, text="📑 Áp dụng cho Video đã chọn", width=160, height=26, font=("Segoe UI", 12, "bold"), fg_color=BORDER, hover_color=BG_CARD, command=make_apply_all_cmd(textbox))
            btn_apply_all.pack(side="left", padx=(8, 0))

        self._update_selected_count()

    def _generate_batch_ai_captions(self):
        """Chạy AI tạo tiêu đề và hashtag chuẩn thể loại hàng loạt cho các video được chọn."""
        selected_ids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng tick chọn ít nhất 1 video để tạo Caption bằng AI!")
            return

        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username") if auth_client.user_info else None
        pending_list = db.get_pending_videos(limit=1000, username=current_user)
        all_videos = {v["video_id"]: v for v in pending_list}

        self._log(f"✨ Bắt đầu tạo Caption & Hashtag AI cho {len(selected_ids)} video...", "INFO")

        def _worker():
            from utils.translator import generate_tiktok_metadata_with_ai
            success_count = 0
            for idx, vid in enumerate(selected_ids):
                v_data = all_videos.get(vid)
                if not v_data:
                    continue
                try:
                    res = generate_tiktok_metadata_with_ai(
                        original_title=v_data.get("title", ""),
                        translated_title=v_data.get("title_vi", ""),
                    )
                    new_cap = res.get("caption", "").strip()
                    if new_cap:
                        db.update_custom_caption(vid, new_cap)
                        def _update_ui(v_id=vid, cap=new_cap):
                            if v_id in self._custom_captions:
                                self._custom_captions[v_id].delete("1.0", "end")
                                self._custom_captions[v_id].insert("1.0", cap)
                        self.after(0, _update_ui)
                        success_count += 1
                        self._log(f"  [{idx+1}/{len(selected_ids)}] ✅ {vid} ({res.get('category')}): {new_cap[:60]}...", "SUCCESS")
                except Exception as err:
                    self._log(f"  [{idx+1}/{len(selected_ids)}] ❌ Lỗi video {vid}: {err}", "WARNING")

            self._log(f"✨ Hoàn tất tạo Caption AI cho {success_count}/{len(selected_ids)} video!", "SUCCESS")
            self.after(0, lambda: messagebox.showinfo("Hoàn thành", f"Đã tạo Caption AI thành công cho {success_count}/{len(selected_ids)} video!"))

        threading.Thread(target=_worker, daemon=True).start()

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

    def _clean_missing_videos(self):
        """Quét và tự động ẩn (archived) các video trong tab Upload mà file đã bị xóa trên máy tính và Google Drive."""
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        from pathlib import Path
        
        db = DatabaseManager()
        current_user = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        videos = db.get_pending_videos(limit=1000, username=current_user)
        if not videos:
            messagebox.showinfo("Dọn dẹp", "Không có video nào trong hàng chờ Upload.")
            return

        if not messagebox.askyesno("Dọn dẹp video mất file", f"Hệ thống sẽ quét {len(videos)} video trong tab Upload và tự động ẩn (lưu trữ) những video không còn file trên máy và đã bị xóa trên Google Drive.\n\nBạn có muốn thực hiện không?"):
            return

        self._log("🔍 Đang kiểm tra file cục bộ và Google Drive...", "INFO")
        
        # Lấy danh sách ID file còn sống trên Google Drive (nhanh ~0.5s)
        drive_file_ids = set()
        try:
            from uploader.google_drive_uploader import GoogleDriveUploader
            uploader = GoogleDriveUploader(current_user)
            uploader.authenticate()
            page_token = None
            while True:
                res = uploader.service.files().list(
                    pageSize=1000, 
                    fields='nextPageToken, files(id, trashed)',
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                for f in res.get('files', []):
                    if not f.get('trashed'):
                        drive_file_ids.add(f['id'])
                page_token = res.get('nextPageToken')
                if not page_token:
                    break
        except Exception as e:
            self._log(f"⚠️ Không thể kiểm tra Google Drive: {e}. Sẽ chỉ kiểm tra file local.", "WARNING")
            drive_file_ids = None

        archived_count = 0
        for v in videos:
            vid = v["video_id"]
            p_path = v.get("processed_path")
            local_ok = bool(p_path and Path(p_path).exists())
            
            d_id = v.get("drive_processed_id") or v.get("drive_download_id")
            drive_ok = False
            if drive_file_ids is not None:
                drive_ok = bool(d_id and d_id in drive_file_ids)
            else:
                drive_ok = bool(d_id)

            if not local_ok and not drive_ok:
                db.update_video_status(vid, "archived")
                archived_count += 1

        self._log(f"🧹 Đã dọn dẹp và ẩn {archived_count} video mất file/đã xóa trên Drive.", "SUCCESS")
        self._load_videos()

    def _rename_author_dialog(self):
        show_rename_author_dialog(self, self._opt_author_filter_up, self._load_videos)

    def _delete_author_dialog(self):
        show_delete_author_dialog(self, self._opt_author_filter_up, self._load_videos)

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
                
        self._log(f"Đã xóa vĩnh viễn {deleted} video (gồm cả file trên Google Drive).", "SUCCESS")
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
        from auth_client import auth_client
        if auth_client.user_info and auth_client.user_info.get("is_expired", True):
            messagebox.showerror("Bản quyền", "Tài khoản của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục sử dụng!")
            return
            
        role = auth_client.user_info.get("role", "user") if auth_client.user_info else "user"
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        
        # Kiểm tra giới hạn Role
        if role != "admin":
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            today_count = db.get_today_post_count(platform="tiktok", username=username)
            if today_count >= 10:
                messagebox.showerror("Giới hạn", "Tài khoản của bạn đã đạt giới hạn 10 video upload/ngày. Vui lòng nâng cấp gói hoặc liên hệ Admin!")
                return
            
        self._btn_upload.configure(state="disabled")
        self._log_widget.clear()
        self._log("Bắt đầu chuẩn bị Upload...", "INFO")
        if getattr(self, "is_running", False):
            self._cancel_task()
            self._btn_upload.configure(state="disabled", text="Đang dừng...")
            return

        self.is_running = True
        self._btn_upload.configure(state="normal", text="⏹ Dừng lại", fg_color=DANGER, hover_color="#c0392b")
        self._status_badge.set("Đang upload...", WARNING)
        self._log_widget.clear()
        self._log("Bắt đầu chuẩn bị upload video...", "INFO")
        
        # Lấy tất cả giá trị GUI ở thread chính trước khi chạy ngầm
        selected_vids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_vids:
            self._log("Không có video nào được chọn!", "WARNING")
            self._on_task_done()
            return
            
        custom_captions_dict = {vid: tb.get("1.0", "end-1c") for vid, tb in self._custom_captions.items()}
        video_accounts_tt_dict = {vid: opt.get() for vid, opt in self._video_accounts.items()}
        video_accounts_yt_dict = {vid: opt.get() for vid, opt in self._video_accounts_yt.items()}
        video_accounts_fb_dict = {vid: opt.get() for vid, opt in self._video_accounts_fb.items()}
        cleanup_upload = self._sw_cleanup_upload.get() == 1
        
        do_tt = self._sw_platform_tt.get() == 1
        do_yt = self._sw_platform_yt.get() == 1
        do_fb = self._sw_platform_fb.get() == 1
        
        if not do_tt and not do_yt and not do_fb:
            self._log("Vui lòng chọn ít nhất 1 nền tảng để upload!", "WARNING")
            self._on_task_done()
            return
        
        # Override limit bằng đúng số lượng video được chọn để đảm bảo up đủ
        limit = len(selected_vids)

        try:
            threads_str = getattr(self, "_entry_upload_threads", None)
            threads_val = int(threads_str.get().strip()) if threads_str else 3
            upload_threads = max(1, min(20, threads_val))
        except Exception:
            upload_threads = 3

        # Bật/Tắt Trình duyệt (Headless)
        show_browser = getattr(self, "_sw_show_browser", None)
        headless = not (show_browser.get() == 1) if show_browser else False

        # Tự động lưu toàn bộ cấu hình Upload
        try:
            self._save_upload_config(show_msg=False)
        except Exception:
            pass

        # Xác định danh sách nền tảng
        active_platforms = []
        if do_tt: active_platforms.append("TikTok")
        if do_yt: active_platforms.append("YouTube")
        if do_fb: active_platforms.append("Facebook")
        self._log(f"🎯 Nền tảng kích hoạt: {', '.join(active_platforms)}", "INFO")

        # Bắt đầu session ghi log độc lập
        try:
            self._current_session_id = UploadLogManager.start_session(
                platforms=active_platforms,
                total_videos=len(selected_vids),
                headless=headless,
                upload_threads=upload_threads,
                username=username,
            )
        except Exception:
            self._current_session_id = None

        self._run_in_thread(
            self._do_upload, limit, selected_vids, custom_captions_dict,
            video_accounts_tt_dict, video_accounts_yt_dict, video_accounts_fb_dict,
            cleanup_upload, do_tt, do_yt, do_fb, upload_threads, headless
        )

    def _on_task_done(self):
        self._current_session_id = None
        super()._on_task_done()
        self.is_running = False
        self.after(0, lambda: self._btn_upload.configure(text="▶  Bắt đầu Upload", state="normal", fg_color="#e74c3c", hover_color="#c0392b"))
        self.after(0, lambda: self._status_badge.set("Xong", SUCCESS) if not getattr(self, "cancel_flag", False) else self._status_badge.set("Đã dừng", DANGER))

    def _log(self, msg: str, level: str = "INFO"):
        """Ghi log hiển thị UI và đồng thời lưu vào file log của phiên (không bị trùng lặp)."""
        if hasattr(self, "_log_widget"):
            self.after(0, lambda: self._log_widget.append(msg, level))
        sid = getattr(self, "_current_session_id", None)
        if sid:
            UploadLogManager.append_log(sid, msg, level)

    def _open_log_history_dialog(self):
        """Mở cửa sổ tra cứu lịch sử logs."""
        try:
            UploadLogHistoryDialog(self)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở lịch sử logs: {e}")

    def _open_logs_folder(self):
        """Mở thư mục lưu file logs trong Explorer."""
        try:
            logs_dir = UploadLogManager.get_logs_dir()
            if os.name == "nt":
                os.startfile(str(logs_dir))
            else:
                subprocess.Popen(["xdg-open", str(logs_dir)])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")

    def _copy_current_log(self):
        """Sao chép toàn bộ text đang có trong khung log hiện tại."""
        try:
            content = self._log_widget._textbox.get("1.0", "end-1c")
            if not content.strip():
                messagebox.showwarning("Thông báo", "Khung log hiện đang trống!")
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Thành công", "Đã sao chép nhật ký hiện tại vào Clipboard!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sao chép: {e}")

    def _save_upload_config(self, show_msg=True):
        """Lưu toàn bộ cấu hình Upload vào config/upload_config.json."""
        try:
            from config.settings import BASE_DIR
            import json
            cfg_path = BASE_DIR / "config" / "upload_config.json"
            cfg_path.parent.mkdir(parents=True, exist_ok=True)

            # Thu thập tài khoản đã gán cho từng video
            assigned_accounts = {}
            if hasattr(self, "_video_accounts"):
                for vid in self._video_accounts:
                    assigned_accounts[vid] = {
                        "tt": self._video_accounts[vid].get() if vid in self._video_accounts else "Không up",
                        "yt": self._video_accounts_yt[vid].get() if hasattr(self, "_video_accounts_yt") and vid in self._video_accounts_yt else "Không up",
                        "fb": self._video_accounts_fb[vid].get() if hasattr(self, "_video_accounts_fb") and vid in self._video_accounts_fb else "Không up",
                    }
            self._saved_assigned_accounts = assigned_accounts

            data = {
                "limit": self._entry_limit.get().strip() if hasattr(self, "_entry_limit") else "4",
                "cleanup_upload": bool(self._sw_cleanup_upload.get() == 1) if hasattr(self, "_sw_cleanup_upload") else True,
                "show_browser": bool(self._sw_show_browser.get() == 1) if hasattr(self, "_sw_show_browser") else True,
                "platform_tt": bool(self._sw_platform_tt.get() == 1) if hasattr(self, "_sw_platform_tt") else True,
                "platform_yt": bool(self._sw_platform_yt.get() == 1) if hasattr(self, "_sw_platform_yt") else True,
                "platform_fb": bool(self._sw_platform_fb.get() == 1) if hasattr(self, "_sw_platform_fb") else True,
                "vids_per_acc": self._entry_vids_per_acc.get().strip() if hasattr(self, "_entry_vids_per_acc") else "2",
                "round_robin": bool(self._sw_round_robin.get() == 1) if hasattr(self, "_sw_round_robin") else False,
                "upload_threads": self._entry_upload_threads.get().strip() if hasattr(self, "_entry_upload_threads") else "3",
                "account_tt": self._opt_account.get() if hasattr(self, "_opt_account") else "",
                "account_yt": self._opt_account_yt.get() if hasattr(self, "_opt_account_yt") else "",
                "account_fb": self._opt_account_fb.get() if hasattr(self, "_opt_account_fb") else "",
                "author_filter": self._opt_author_filter_up.get() if hasattr(self, "_opt_author_filter_up") else "Tất cả Kênh",
                "assigned_accounts": assigned_accounts,
            }

            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Đồng thời cập nhật upload_ui.json để đồng bộ với các module khác
            ui_path = BASE_DIR / "config" / "upload_ui.json"
            with open(ui_path, "w", encoding="utf-8") as f:
                json.dump({"show_browser": data["show_browser"]}, f, indent=2)

            if show_msg:
                active_plist = [p for p, act in [('TikTok', data['platform_tt']), ('YouTube', data['platform_yt']), ('Facebook', data['platform_fb'])] if act]
                p_str = ", ".join(active_plist) if active_plist else "Không chọn"
                mode_str = "Hiện trình duyệt" if data["show_browser"] else "Ẩn ngầm (Headless)"
                msg = (
                    "✅ Đã lưu cấu hình Upload thành công!\n\n"
                    f"• Trình duyệt: {mode_str}\n"
                    f"• Nền tảng: {p_str}\n"
                    f"• Số luồng: {data['upload_threads']} luồng | Phân bổ: {data['vids_per_acc']} video/nick\n"
                    f"• Tài khoản mặc định:\n"
                    f"   - TikTok: {data['account_tt']}\n"
                    f"   - YouTube: {data['account_yt']}\n"
                    f"   - Facebook: {data['account_fb']}\n"
                    f"• Đã lưu tài khoản đã gán cho {len(assigned_accounts)} video hiện có.\n\n"
                    "Cấu hình này sẽ tự động được tải lại mỗi khi bạn mở ứng dụng."
                )
                messagebox.showinfo("Thành công", msg)
        except Exception as e:
            if show_msg:
                messagebox.showerror("Lỗi", f"Không thể lưu cấu hình: {e}")

    def _load_upload_config(self):
        """Khôi phục toàn bộ cài đặt từ config/upload_config.json."""
        try:
            from config.settings import BASE_DIR
            import json
            cfg_path = BASE_DIR / "config" / "upload_config.json"
            if not cfg_path.exists():
                return

            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            if "limit" in cfg and hasattr(self, "_entry_limit"):
                self._entry_limit.delete(0, "end")
                self._entry_limit.insert(0, str(cfg["limit"]))

            if "cleanup_upload" in cfg and hasattr(self, "_sw_cleanup_upload"):
                if cfg["cleanup_upload"]: self._sw_cleanup_upload.select()
                else: self._sw_cleanup_upload.deselect()

            if "show_browser" in cfg and hasattr(self, "_sw_show_browser"):
                if cfg["show_browser"]: self._sw_show_browser.select()
                else: self._sw_show_browser.deselect()

            if "platform_tt" in cfg and hasattr(self, "_sw_platform_tt"):
                if cfg["platform_tt"]: self._sw_platform_tt.select()
                else: self._sw_platform_tt.deselect()

            if "platform_yt" in cfg and hasattr(self, "_sw_platform_yt"):
                if cfg["platform_yt"]: self._sw_platform_yt.select()
                else: self._sw_platform_yt.deselect()

            if "platform_fb" in cfg and hasattr(self, "_sw_platform_fb"):
                if cfg["platform_fb"]: self._sw_platform_fb.select()
                else: self._sw_platform_fb.deselect()

            if "vids_per_acc" in cfg and hasattr(self, "_entry_vids_per_acc"):
                self._entry_vids_per_acc.delete(0, "end")
                self._entry_vids_per_acc.insert(0, str(cfg["vids_per_acc"]))

            if "round_robin" in cfg and hasattr(self, "_sw_round_robin"):
                if cfg["round_robin"]: self._sw_round_robin.select()
                else: self._sw_round_robin.deselect()

            if "upload_threads" in cfg and hasattr(self, "_entry_upload_threads"):
                self._entry_upload_threads.delete(0, "end")
                self._entry_upload_threads.insert(0, str(cfg["upload_threads"]))

            acc_tt = cfg.get("account_tt")
            if acc_tt and hasattr(self, "_opt_account"):
                vals = self._opt_account.cget("values") if hasattr(self._opt_account, "cget") else []
                if acc_tt in vals: self._opt_account.set(acc_tt)

            acc_yt = cfg.get("account_yt")
            if acc_yt and hasattr(self, "_opt_account_yt"):
                vals = self._opt_account_yt.cget("values") if hasattr(self._opt_account_yt, "cget") else []
                if acc_yt in vals: self._opt_account_yt.set(acc_yt)

            acc_fb = cfg.get("account_fb")
            if acc_fb and hasattr(self, "_opt_account_fb"):
                vals = self._opt_account_fb.cget("values") if hasattr(self._opt_account_fb, "cget") else []
                if acc_fb in vals: self._opt_account_fb.set(acc_fb)

            author_filter = cfg.get("author_filter")
            if author_filter and hasattr(self, "_opt_author_filter_up"):
                vals = self._opt_author_filter_up.cget("values") if hasattr(self._opt_author_filter_up, "cget") else []
                if author_filter in vals: self._opt_author_filter_up.set(author_filter)

            self._saved_assigned_accounts = cfg.get("assigned_accounts", {})

        except Exception as e:
            print(f"Error loading upload config: {e}")

    async def _async_upload_groups(self, limit, account_groups_tt, account_groups_yt, account_groups_fb, custom_captions_dict, do_tt, do_yt, do_fb, max_workers=3, headless=False):
        import asyncio
        from database.db_manager import DatabaseManager
        from config.settings import COOKIES_DIR
        db = DatabaseManager()
        
        from auth_client import auth_client
        current_user = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        
        max_workers = max(1, int(max_workers))
        self._log(f"⚙️ Chế độ Upload: Đa luồng ({max_workers} luồng đồng thời mỗi nền tảng)", "INFO")

        # Thống kê kết quả cho toàn bộ phiên
        total_success = 0
        total_vids_count = 0
        if do_tt and account_groups_tt:
            for v_list in account_groups_tt.values(): total_vids_count += len(v_list)
        if do_yt and account_groups_yt:
            for v_list in account_groups_yt.values(): total_vids_count += len(v_list)
        if do_fb and account_groups_fb:
            for v_list in account_groups_fb.values(): total_vids_count += len(v_list)

        semaphore_tt = asyncio.Semaphore(max_workers)
        window_slots = asyncio.Queue()
        for i in range(max_workers):
            await window_slots.put(i)

        semaphore_yt = asyncio.Semaphore(max_workers)
        semaphore_fb = asyncio.Semaphore(max_workers)

        platform_tasks = []

        # ─── NỀN TẢNG 1: TIKTOK ───
        if do_tt and account_groups_tt:
            async def _run_all_tt():
                nonlocal total_success
                from uploader.tiktok_uploader import TikTokUploader
                mode_str = "Ẩn ngầm (Headless)" if headless else "Hiện trình duyệt"
                self._log(f"🎬 Bắt đầu upload TikTok cho {len(account_groups_tt)} tài khoản ({max_workers} luồng song song, chế độ: {mode_str})...", "INFO")
                
                async def _upload_single_tt(account_file, vids):
                    nonlocal total_success
                    if self.cancel_flag:
                        return
                    async with semaphore_tt:
                        if self.cancel_flag:
                            return
                        slot = await window_slots.get()
                        try:
                            self._log(f"🚀 [TikTok - Luồng {slot+1}] Bắt đầu upload {len(vids)} video ({account_file})...", "INFO")
                            user_dir = self._get_user_cookies_dir()
                            cookies_path = str(user_dir / account_file)
                            
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
                                
                            uploader = TikTokUploader(db=db, cookies_file=cookies_path, proxy=proxy_str, window_idx=slot, username=current_user, headless=headless)
                            
                            captions_to_pass = {
                                vid: custom_captions_dict[vid] 
                                for vid in vids if vid in custom_captions_dict
                            }
                            
                            def _tt_log_cb(msg, lvl="INFO"):
                                self._log(f"[TikTok - Luồng {slot+1}] {msg}", lvl)

                            try:
                                results = await uploader.upload_pending_videos(
                                    limit=len(vids), 
                                    video_ids=vids,
                                    custom_captions=captions_to_pass,
                                    cancel_check=lambda: self.cancel_flag,
                                    log_callback=_tt_log_cb
                                )
                                if len(results) > 0:
                                    total_success += len(results)
                                    self._log(f"✅ [TikTok - Luồng {slot+1}] Upload xong {len(results)}/{len(vids)} video ({account_file})!", "SUCCESS")
                                else:
                                    self._log(f"⚠️ [TikTok - Luồng {slot+1}] Không upload được video nào ({account_file})! Vui lòng kiểm tra lại file.", "WARNING")
                                    try:
                                        from auth_client import auth_client
                                        auth_client.send_telemetry("ERROR", f"[TikTok - {account_file}] 0/{len(vids)} video tải lên thành công (lỗi cookie hoặc bị chặn)")
                                    except Exception:
                                        pass
                            except Exception as e:
                                self._log(f"❌ [TikTok - Luồng {slot+1}] Lỗi upload TikTok {account_file}: {e}", "ERROR")
                                try:
                                    from auth_client import auth_client
                                    auth_client.send_telemetry("ERROR", f"[TikTok - {account_file}] Ngoại lệ: {e}")
                                except Exception:
                                    pass
                            finally:
                                await uploader.close()
                        finally:
                            await window_slots.put(slot)

                tt_tasks = [_upload_single_tt(acc, vids) for acc, vids in account_groups_tt.items()]
                await asyncio.gather(*tt_tasks, return_exceptions=True)

            platform_tasks.append(_run_all_tt())

        # ─── NỀN TẢNG 2: YOUTUBE ───
        if do_yt and account_groups_yt:
            async def _run_all_yt():
                nonlocal total_success
                from uploader.youtube_uploader import YouTubeUploader
                self._log(f"🎬 Bắt đầu upload YouTube cho {len(account_groups_yt)} tài khoản ({max_workers} luồng song song)...", "INFO")
                
                async def _upload_single_yt(account_file, vids, worker_idx):
                    nonlocal total_success
                    if self.cancel_flag:
                        return
                    async with semaphore_yt:
                        if self.cancel_flag:
                            return
                        self._log(f"🚀 [YouTube - Luồng {worker_idx+1}] Bắt đầu upload {len(vids)} video ({account_file})...", "INFO")
                        user_dir = self._get_user_cookies_dir()
                        token_path = str(user_dir / account_file)
                        yt_uploader = YouTubeUploader(db=db, token_file=token_path, username=current_user)
                        
                        captions_to_pass = {
                            vid: custom_captions_dict[vid] 
                            for vid in vids if vid in custom_captions_dict
                        }
                        
                        def _yt_log_cb(msg, lvl="INFO"):
                            self._log(f"[YouTube - Luồng {worker_idx+1}] {msg}", lvl)

                        try:
                            results = await yt_uploader.upload_pending_videos(
                                limit=len(vids), 
                                video_ids=vids,
                                custom_captions=captions_to_pass,
                                cancel_check=lambda: self.cancel_flag,
                                log_callback=_yt_log_cb
                            )
                            if len(results) > 0:
                                total_success += len(results)
                                self._log(f"✅ [YouTube - Luồng {worker_idx+1}] Upload xong {len(results)}/{len(vids)} video ({account_file})!", "SUCCESS")
                            else:
                                self._log(f"⚠️ [YouTube - Luồng {worker_idx+1}] Không upload được video nào ({account_file})! Vui lòng kiểm tra lại file.", "WARNING")
                        except Exception as e:
                            self._log(f"❌ [YouTube - Luồng {worker_idx+1}] Lỗi upload YouTube {account_file}: {e}", "ERROR")
                        finally:
                            await yt_uploader.close()

                yt_tasks = [_upload_single_yt(acc, vids, i % max_workers) for i, (acc, vids) in enumerate(account_groups_yt.items())]
                await asyncio.gather(*yt_tasks, return_exceptions=True)

            platform_tasks.append(_run_all_yt())

        # ─── NỀN TẢNG 3: FACEBOOK REELS ───
        if do_fb and account_groups_fb:
            async def _run_all_fb():
                nonlocal total_success
                from uploader.facebook_uploader import FacebookUploader
                self._log(f"🎬 Bắt đầu upload Facebook Reels cho {len(account_groups_fb)} tài khoản ({max_workers} luồng song song)...", "INFO")
                
                async def _upload_single_fb(account_file, vids, worker_idx):
                    nonlocal total_success
                    if self.cancel_flag:
                        return
                    async with semaphore_fb:
                        if self.cancel_flag:
                            return
                        self._log(f"🚀 [Facebook - Luồng {worker_idx+1}] Bắt đầu upload {len(vids)} video ({account_file})...", "INFO")
                        user_dir = self._get_user_cookies_dir()
                        token_path = str(user_dir / account_file)
                        fb_uploader = FacebookUploader(db=db, token_file=token_path, username=current_user)
                        
                        captions_to_pass = {
                            vid: custom_captions_dict[vid] 
                            for vid in vids if vid in custom_captions_dict
                        }
                        
                        def _fb_log_cb(msg, lvl="INFO"):
                            self._log(f"[Facebook - Luồng {worker_idx+1}] {msg}", lvl)

                        try:
                            results = await fb_uploader.upload_pending_videos(
                                limit=len(vids), 
                                video_ids=vids,
                                custom_captions=captions_to_pass,
                                cancel_check=lambda: self.cancel_flag,
                                log_callback=_fb_log_cb
                            )
                            if len(results) > 0:
                                total_success += len(results)
                                self._log(f"✅ [Facebook - Luồng {worker_idx+1}] Upload xong {len(results)}/{len(vids)} video ({account_file})!", "SUCCESS")
                            else:
                                self._log(f"⚠️ [Facebook - Luồng {worker_idx+1}] Không upload được video nào ({account_file})! Vui lòng kiểm tra lại file.", "WARNING")
                        except Exception as e:
                            self._log(f"❌ [Facebook - Luồng {worker_idx+1}] Lỗi upload Facebook Reels {account_file}: {e}", "ERROR")
                        finally:
                            await fb_uploader.close()

                fb_tasks = [_upload_single_fb(acc, vids, i % max_workers) for i, (acc, vids) in enumerate(account_groups_fb.items())]
                await asyncio.gather(*fb_tasks, return_exceptions=True)

            platform_tasks.append(_run_all_fb())

        # ⚡ Chạy ĐỒNG THỜI cả 3 nền tảng (TikTok, YouTube, Facebook Reels) song song
        if platform_tasks:
            await asyncio.gather(*platform_tasks, return_exceptions=True)
                
        # Hoàn tất phiên upload và ghi tổng kết
        fail_count = max(0, total_vids_count - total_success)
        sid = getattr(self, "_current_session_id", None)
        if sid:
            UploadLogManager.finish_session(
                session_id=sid,
                success_count=total_success,
                fail_count=fail_count,
                cancelled=bool(getattr(self, "cancel_flag", False)),
            )
            self._log(f"💾 Đã lưu toàn bộ nhật ký phiên upload ({sid}).", "SUCCESS")
            status_msg = f"📊 Kết quả: {total_success}/{total_vids_count} video tải lên thành công."
            if fail_count > 0:
                status_msg += f" Có {fail_count} video thất bại hoặc bị bỏ qua."
            self._log(status_msg, "SUCCESS" if fail_count == 0 else "WARNING")
            self._log("💡 Bạn có thể bấm nút '📜 Xem lịch sử Logs' ở trên để xem lại chi tiết bất cứ lúc nào.", "INFO")
            self._current_session_id = None

        # Gửi telemetry về server cho Admin giám sát
        try:
            from auth_client import auth_client
            active_p = []
            if do_tt: active_p.append("TikTok")
            if do_yt: active_p.append("YouTube")
            if do_fb: active_p.append("Facebook")
            p_str = ", ".join(active_p) if active_p else "Nền tảng"
            if fail_count > 0:
                auth_client.send_telemetry("ERROR", f"[Upload {p_str}] Hoàn tất {total_success}/{total_vids_count} video ({fail_count} thất bại/bỏ qua)")
            elif total_vids_count > 0:
                auth_client.send_telemetry("UPLOAD", f"[Upload {p_str}] Đã upload thành công {total_success}/{total_vids_count} video")
        except Exception:
            pass

        self.after(0, self._load_videos)

    def _set_upload_threads(self, val):
        if hasattr(self, "_entry_upload_threads"):
            self._entry_upload_threads.delete(0, "end")
            self._entry_upload_threads.insert(0, str(val))


    def _apply_account_to_all(self):
        selected = self._opt_account.get()
        for vid, opt in self._video_accounts.items():
            if self._checkboxes[vid].get():
                opt.set(selected)



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

    def _apply_account_to_all_fb(self):
        selected = self._opt_account_fb.get()
        for vid, opt in self._video_accounts_fb.items():
            if self._checkboxes[vid].get():
                opt.set(selected)



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

    def _refresh_facebook_accounts(self):
        accounts = self._get_facebook_accounts()
        self._opt_account_fb.configure(values=accounts)
        
        current_global = self._opt_account_fb.get()
        if not accounts:
            self._opt_account_fb.set("")
        elif current_global not in accounts:
            self._opt_account_fb.set(accounts[0])
            
        for opt in self._video_accounts_fb.values():
            opt.configure(values=accounts)
            curr = opt.get()
            if not accounts:
                opt.set("")
            elif curr not in accounts:
                opt.set(accounts[0])

    def _get_vids_per_acc_input(self):
        try:
            val = int(self._entry_vids_per_acc.get().strip())
            return max(1, val)
        except Exception:
            return 2

    def _distribute_accounts(self, platform="tiktok", vids_per_acc=2, round_robin=False):
        """Phân bổ đều vids_per_acc video cho từng tài khoản hợp lệ."""
        selected_vids = [vid for vid, var in self._checkboxes.items() if var.get()]
        if not selected_vids:
            for var in self._checkboxes.values():
                var.set(True)
            self._update_selected_count()
            selected_vids = list(self._checkboxes.keys())

        if not selected_vids:
            return 0, 0, "Không có video nào trong danh sách!"

        user_dir = self._get_user_cookies_dir()
        if platform == "tiktok":
            acc_dict = self._video_accounts
            raw_accs = [f.name for f in sorted(user_dir.glob("tiktok_*.json")) if f.stat().st_size > 10]
            proxy_file = user_dir / "proxies.json"
            if proxy_file.exists():
                try:
                    import json
                    with open(proxy_file, "r", encoding="utf-8") as f:
                        proxies = json.load(f)
                    if proxies:
                        active_set = set(proxies.keys())
                        p_accs = [a for a in raw_accs if a in active_set or a.replace(".json", "") in active_set]
                        other_accs = [a for a in raw_accs if a not in p_accs]
                        raw_accs = p_accs + other_accs
                except Exception:
                    pass
        elif platform == "youtube":
            acc_dict = self._video_accounts_yt
            raw_accs = [f.name for f in sorted(user_dir.glob("youtube_*.json")) if f.stat().st_size > 10]
        elif platform == "facebook":
            acc_dict = self._video_accounts_fb
            raw_accs = [f.name for f in sorted(user_dir.glob("facebook_*.json")) if f.stat().st_size > 10]
        else:
            return 0, 0, f"Nền tảng không hợp lệ: {platform}"

        if not raw_accs:
            return 0, 0, f"Chưa có tài khoản {platform.capitalize()} nào hợp lệ (file rỗng hoặc chưa thêm)!"

        acc_count = len(raw_accs)
        assigned_vids = 0

        for idx, vid in enumerate(selected_vids):
            if round_robin:
                acc_idx = (idx // vids_per_acc) % acc_count
                acc_name = raw_accs[acc_idx]
                assigned_vids += 1
            else:
                acc_idx = idx // vids_per_acc
                if acc_idx < acc_count:
                    acc_name = raw_accs[acc_idx]
                    assigned_vids += 1
                else:
                    acc_name = "Không up"

            if vid in acc_dict:
                acc_dict[vid].set(acc_name)

        return acc_count, assigned_vids, None

    def _distribute_single(self, platform):
        vids_per_acc = self._get_vids_per_acc_input()
        round_robin = self._sw_round_robin.get() == 1
        acc_count, assigned_count, err = self._distribute_accounts(platform, vids_per_acc, round_robin)
        if err:
            messagebox.showwarning("Cảnh báo", err)
            return

        if not round_robin:
            for vid, var in self._checkboxes.items():
                up_tt = self._video_accounts.get(vid) and self._video_accounts[vid].get() != "Không up"
                up_yt = self._video_accounts_yt.get(vid) and self._video_accounts_yt[vid].get() != "Không up"
                up_fb = self._video_accounts_fb.get(vid) and self._video_accounts_fb[vid].get() != "Không up"
                var.set(bool(up_tt or up_yt or up_fb))
            self._update_selected_count()

        p_name = "TikTok" if platform == "tiktok" else ("YouTube" if platform == "youtube" else "Facebook")
        msg = f"Đã dải đều {vids_per_acc} video/nick cho {p_name}!\n• Số tài khoản sử dụng: {acc_count}\n• Số video được gán: {assigned_count}"
        if not round_robin and assigned_count < len(self._checkboxes):
            msg += f"\n• Các video còn lại đặt 'Không up' để đúng chỉ tiêu {vids_per_acc} video/nick."
        messagebox.showinfo("Thành công", msg)

    def _distribute_all(self):
        vids_per_acc = self._get_vids_per_acc_input()
        round_robin = self._sw_round_robin.get() == 1

        do_tt = self._sw_platform_tt.get() == 1
        do_yt = self._sw_platform_yt.get() == 1
        do_fb = self._sw_platform_fb.get() == 1

        if not do_tt and not do_yt and not do_fb:
            messagebox.showwarning("Cảnh báo", "Vui lòng bật ít nhất 1 công tắc nền tảng (TikTok, YouTube, Facebook)!")
            return

        results = []
        if do_tt:
            c, a, err = self._distribute_accounts("tiktok", vids_per_acc, round_robin)
            if err:
                results.append(f"• TikTok: ⚠️ {err}")
            else:
                results.append(f"• TikTok: {c} nick → {a} video")

        if do_yt:
            c, a, err = self._distribute_accounts("youtube", vids_per_acc, round_robin)
            if err:
                results.append(f"• YouTube: ⚠️ {err}")
            else:
                results.append(f"• YouTube: {c} kênh → {a} video")

        if do_fb:
            c, a, err = self._distribute_accounts("facebook", vids_per_acc, round_robin)
            if err:
                results.append(f"• Facebook: ⚠️ {err}")
            else:
                results.append(f"• Facebook: {c} Page → {a} video")

        if not round_robin:
            for vid, var in self._checkboxes.items():
                up_tt = self._video_accounts.get(vid) and self._video_accounts[vid].get() != "Không up"
                up_yt = self._video_accounts_yt.get(vid) and self._video_accounts_yt[vid].get() != "Không up"
                up_fb = self._video_accounts_fb.get(vid) and self._video_accounts_fb[vid].get() != "Không up"
                var.set(bool(up_tt or up_yt or up_fb))
            self._update_selected_count()

        msg = f"Kết quả phân bổ {vids_per_acc} video/tài khoản:\n\n" + "\n".join(results)
        messagebox.showinfo("Phân bổ tự động hoàn tất", msg)

    def _do_upload(self, limit, selected_vids, custom_captions_dict, video_accounts_tt_dict, video_accounts_yt_dict, video_accounts_fb_dict, cleanup_upload, do_tt, do_yt, do_fb, upload_threads=3, headless=False):
        from config.settings import TIKTOK_CONFIG, YOUTUBE_CONFIG, FACEBOOK_CONFIG
        TIKTOK_CONFIG["auto_cleanup_after_upload"] = cleanup_upload
        YOUTUBE_CONFIG["auto_cleanup_after_upload"] = cleanup_upload
        FACEBOOK_CONFIG["auto_cleanup_after_upload"] = cleanup_upload

        account_groups_tt = {}
        account_groups_yt = {}
        account_groups_fb = {}
        
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

            if do_fb:
                acc_fb = video_accounts_fb_dict.get(vid)
                if acc_fb and acc_fb != "Không up":
                    if acc_fb not in account_groups_fb:
                        account_groups_fb[acc_fb] = []
                    account_groups_fb[acc_fb].append(vid)

        if not account_groups_tt and not account_groups_yt and not account_groups_fb:
            off_platforms = []
            if not do_tt: off_platforms.append("TikTok")
            if not do_yt: off_platforms.append("YouTube")
            if not do_fb: off_platforms.append("Facebook")
            off_msg = f" (Nền tảng đang bị TẮT ở cột cấu hình bên phải: {', '.join(off_platforms)})" if off_platforms else ""
            self._log(f"⚠️ Không có video nào được chỉ định tài khoản hợp lệ trên các nền tảng đang kích hoạt!{off_msg}", "WARNING")
            self._log("💡 Hướng dẫn: Cuộn thanh cuộn ở cột bên phải lên trên để BẬT công tắc nền tảng (ví dụ: TikTok), hoặc chọn tài khoản cụ thể cho từng video (tránh để 'Không up').", "INFO")
            self.after(0, self._on_task_done)
            return

        import asyncio
        import sys
        if sys.platform == 'win32' and sys.version_info < (3, 14):
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass
        asyncio.run(self._async_upload_groups(limit, account_groups_tt, account_groups_yt, account_groups_fb, custom_captions_dict, do_tt, do_yt, do_fb, upload_threads, headless))


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Auto (Pipeline)
# ═══════════════════════════════════════════════════════════════════════════════
class AutoTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._running = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self._build()

    def _build(self):
        # Header
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        t_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        t_box.pack(side="left")
        ctk.CTkLabel(
            t_box, text="🤖  Auto Pipeline (Tự Động Hóa 100%)",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            t_box, text="Chu trình khép kín: Tự cào video -> Tự edit lách bản quyền -> Tự đăng đa nền tảng theo lịch",
            font=("Segoe UI", 11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        
        self._btn_help_auto = ctk.CTkButton(
            hdr_frame, text="❓ Hướng dẫn", width=105, height=32, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_CARD,
            command=self._toggle_auto_help
        )
        self._btn_help_auto.pack(side="right")
        
        # Guide frame (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 HƯỚNG DẪN CHẠY TỰ ĐỘNG HÓA TỪ A - Z (AUTO PIPELINE)", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• 1. Auto Pipeline là gì?\n"
            "  - Đây là chế độ 'Cắm máy tự chạy': Tool tự động đọc danh sách link -> Tải video sạch -> Lách bản quyền & Lồng tiếng AI -> Đăng thẳng lên TikTok/Shorts/Reels.\n"
            "  - Thích hợp khi bạn muốn cắm máy qua đêm hoặc treo 24/7 trên VPS mà không cần thao tác từng bước bằng tay.\n"
            "• 2. Chọn Nguồn Video:\n"
            "  - 'Từ File URLs (Crawl mới)': Tải video mới từ danh sách link trong file urls.txt rồi mới edit và đăng.\n"
            "  - 'Chỉ Upload (Video đã xử lý)': Bỏ qua bước cào/edit, chỉ tự động lấy các video đã render sẵn trong máy để đăng lên dàn nick.\n"
            "• 3. Chế độ vận hành:\n"
            "  - 'Chạy 1 lần': Làm xong toàn bộ hàng đợi video rồi tự nghỉ.\n"
            "  - 'Chạy liên tục theo lịch': Cứ cách mỗi X giờ/phút hệ thống sẽ tự động thức dậy chạy 1 đợt mới."
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không grid lúc khởi tạo

        # Config card
        cfg = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        cfg.grid(row=2, column=0, sticky="ew", pady=(0, 12))
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
            command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc.pack(side="left", padx=(10, 20))

        self._sw_auto_yt = ctk.CTkSwitch(acc_frame, text="YouTube:", font=("Segoe UI", 12, "bold"), width=60)
        self._sw_auto_yt.select()
        self._sw_auto_yt.pack(side="left", padx=(0, 5))
        
        yt_accounts = UploadTab._get_youtube_accounts()
        self._opt_account_yt = ctk.CTkOptionMenu(
            acc_frame, values=yt_accounts, font=("Segoe UI", 12), width=110,
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_yt.pack(side="left")
        
        self._btn_manage_acc_yt = ctk.CTkButton(
            acc_frame, text="⚙ Quản lý", width=60, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc_yt.pack(side="left", padx=(8, 15))

        self._sw_auto_fb = ctk.CTkSwitch(acc_frame, text="Facebook:", font=("Segoe UI", 12, "bold"), width=60)
        self._sw_auto_fb.select()
        self._sw_auto_fb.pack(side="left", padx=(0, 5))
        
        fb_accounts = UploadTab._get_facebook_accounts()
        self._opt_account_fb = ctk.CTkOptionMenu(
            acc_frame, values=fb_accounts, font=("Segoe UI", 12), width=110,
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_fb.pack(side="left")
        
        self._btn_manage_acc_fb = ctk.CTkButton(
            acc_frame, text="⚙ Quản lý", width=60, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD,
            command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc_fb.pack(side="left", padx=(8, 0))

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", pady=(0, 12))

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

        # Log Toolbar & Log Widget
        self._log_widget = LogWidget(self)
        self._log_toolbar = LogToolbar(self, self._log_widget, module="auto", title="📋  Nhật ký Auto Pipeline (Logs):")
        self._log_toolbar.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        self._log_widget.grid(row=5, column=0, sticky="nsew")
        self.grid_rowconfigure(5, weight=1)

    def _toggle_auto_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_auto"):
                self._btn_help_auto.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
                if hasattr(self, "_btn_help_auto"):
                    self._btn_help_auto.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

    def _refresh_accounts(self):
        accounts = UploadTab._get_tiktok_accounts()
        self._opt_account.configure(values=accounts)
        if accounts:
            current = self._opt_account.get()
            if current not in accounts:
                self._opt_account.set(accounts[0])
        else:
            self._opt_account.set("")



    def _refresh_youtube_accounts(self):
        accounts = UploadTab._get_youtube_accounts()
        self._opt_account_yt.configure(values=accounts)
        if accounts:
            current = self._opt_account_yt.get()
            if current not in accounts:
                self._opt_account_yt.set(accounts[0])
        else:
            self._opt_account_yt.set("")

    def _refresh_facebook_accounts(self):
        accounts = UploadTab._get_facebook_accounts()
        self._opt_account_fb.configure(values=accounts)
        if accounts:
            current = self._opt_account_fb.get()
            if current not in accounts:
                self._opt_account_fb.set(accounts[0])
        else:
            self._opt_account_fb.set("")

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
        from auth_client import auth_client
        if auth_client.user_info and auth_client.user_info.get("is_expired", True):
            messagebox.showerror("Bản quyền", "Tài khoản của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục sử dụng!")
            return
            
        self._running = True
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._status_badge.set("Đang chạy...", SUCCESS)
        self._log_widget.clear()
        self._log("Auto pipeline bắt đầu...", "INFO")

        source_mode = self._source_var.get()
        file_path = self._entry_file.get().strip() or "urls.txt"
        once      = self._mode_var.get() == "once"

        if source_mode == "urls":
            trial_info = auth_client.get_trial_info()
            if not trial_info["is_unlimited"] and trial_info["remaining"] <= 0:
                max_allowed = trial_info.get("max_allowed", 5)
                messagebox.showwarning(
                    "Hết Lượt Dùng Thử Trong Ngày",
                    f"🎁 Tài khoản dùng thử của bạn đã hoàn thành tối đa {max_allowed} video render trong ngày hôm nay.\n\n"
                    "Hạn mức sẽ được làm mới vào ngày mai. Vui lòng nâng cấp gói bản quyền tại tab [Cài đặt ➔ Bản Quyền] để tiếp tục sử dụng Auto Pipeline không giới hạn!"
                )
                return

        
        do_tt = getattr(self, "_sw_auto_tt", None)
        do_tt = do_tt.get() == 1 if do_tt else True
        
        do_yt = getattr(self, "_sw_auto_yt", None)
        do_yt = do_yt.get() == 1 if do_yt else True
        
        do_fb = getattr(self, "_sw_auto_fb", None)
        do_fb = do_fb.get() == 1 if do_fb else True
        
        if not do_tt and not do_yt and not do_fb:
            self._log("LỖI: Vui lòng bật ít nhất 1 nền tảng (TikTok, YouTube hoặc Facebook)!", "WARNING")
            self._on_task_done()
            return

        account_file = self._opt_account.get() if do_tt else None
        account_file_yt = getattr(self, "_opt_account_yt", None)
        account_file_yt = account_file_yt.get() if account_file_yt and do_yt else None
        account_file_fb = getattr(self, "_opt_account_fb", None)
        account_file_fb = account_file_fb.get() if account_file_fb and do_fb else None
        
        self._start_logging_session(
            "auto",
            f"Auto Pipeline ({'Chạy 1 lần' if once else 'Chạy theo lịch'})",
            {"source_mode": source_mode, "once": once, "file": file_path, "do_tt": do_tt, "do_yt": do_yt, "do_fb": do_fb}
        )
        self._run_in_thread(self._do_auto, file_path, once, account_file, account_file_yt, account_file_fb, source_mode)

    def _do_auto(self, file_path, once, account_file, account_file_yt, account_file_fb, source_mode):
        from scheduler.scheduler import AutoScheduler
        from config.settings import SCHEDULER_CONFIG, TIKTOK_CONFIG, YOUTUBE_CONFIG, FACEBOOK_CONFIG
        
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
        fb_account_path = str(user_dir / account_file_fb) if account_file_fb else None
        
        mode_val = "full" if source_mode == "urls" else "upload_only"
        scheduler = AutoScheduler(
            douyin_urls=urls,
            tt_account_file=tt_account_path,
            yt_account_file=yt_account_path,
            fb_account_file=fb_account_path,
            source_mode=mode_val
        )
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
        super()._on_task_done()
        self.after(0, lambda: self._btn_start.configure(state="normal"))
        self.after(0, lambda: self._btn_stop.configure(state="disabled"))
        self.after(0, lambda: self._status_badge.set("Dừng", DANGER if not self._running else SUCCESS))


# ═══════════════════════════════════════════════════════════════════════════════
#  Tab: Nuôi Nick (Farm)
# ═══════════════════════════════════════════════════════════════════════════════
class AccountsTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, parent, app=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app = app
        
        # ── MAIN HEADER ──────────────────────────────────────────────────────
        main_hdr = ctk.CTkFrame(self, fg_color="transparent")
        main_hdr.pack(fill="x", padx=12, pady=(4, 6))
        
        title_box = ctk.CTkFrame(main_hdr, fg_color="transparent")
        title_box.pack(side="left")
        
        ctk.CTkLabel(
            title_box, text="👥  Quản Lý Dàn Tài Khoản Đa Nền Tảng",
            font=("Segoe UI", 21, "bold"), text_color=TEXT_MAIN
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box, text="Hồ sơ TikTok, YouTube Shorts & Facebook Reels • Tách biệt môi trường Cookies & Proxy chống Checkpoint",
            font=("Segoe UI", 11), text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(1, 0))
        
        self.tabview = ctk.CTkTabview(
            self, fg_color="transparent",
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color="#131826",
            segmented_button_unselected_hover_color="#1E293B",
            text_color=TEXT_MAIN,
            text_color_disabled=TEXT_MUTED
        )
        self.tabview.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        
        self.tab_tiktok = self.tabview.add("🎵 TikTok")
        self.tab_youtube = self.tabview.add("▶️ YouTube")
        self.tab_facebook = self.tabview.add("📘 Facebook Reels")
        
        self._all_accounts_cache = []
        self._account_card_widgets = {}
        
        self._build_tiktok_tab()
        self._build_youtube_tab()
        self._build_facebook_tab()
        
    def _build_tiktok_tab(self):
        # ── Action bar ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self.tab_tiktok, fg_color="transparent")
        hdr.pack(fill="x", pady=(2, 8), padx=2)
        
        # Chip thống kê tài khoản
        self._lbl_tt_stats = ctk.CTkLabel(
            hdr, text="📱 Đang tải dữ liệu hồ sơ...", font=("Segoe UI", 11, "bold"),
            text_color=ACCENT_LIGHT, fg_color="#182333", corner_radius=8, padx=12, pady=6
        )
        self._lbl_tt_stats.pack(side="left")
        
        # Nút công cụ & Tìm kiếm bên phải
        btn_box = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_box.pack(side="right")
        
        # Ô tìm kiếm nhanh
        self._search_entry = ctk.CTkEntry(
            btn_box, width=170, height=32, font=("Segoe UI", 11),
            placeholder_text="🔍 Tìm nick / proxy...",
            fg_color="#0D111C", border_color=BORDER, border_width=1, text_color=TEXT_MAIN
        )
        self._search_entry.pack(side="left", padx=(0, 6))
        self._search_entry.bind("<KeyRelease>", lambda e: self._filter_accounts())
        
        ctk.CTkButton(
            btn_box, text="➕ Thêm Nick", width=110, height=32,
            font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._add_new_account
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_box, text="📁 Tải JSON", width=90, height=32,
            font=("Segoe UI", 11, "bold"), fg_color="#1E293B", hover_color="#334155",
            border_width=1, border_color="#334155",
            command=self._upload_account
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_box, text="💾 Lưu Proxy", width=95, height=32,
            font=("Segoe UI", 11, "bold"), fg_color="#064E3B", hover_color="#059669",
            text_color="#10B981", border_width=1, border_color="#10B981",
            command=self._save_all_proxies_manual
        ).pack(side="left", padx=3)
        
        self._btn_help_tt = ctk.CTkButton(
            btn_box, text="❓ Hướng dẫn", width=95, height=32,
            font=("Segoe UI", 11), fg_color="transparent", border_width=1, border_color=BORDER,
            hover_color=BG_CARD, command=self._toggle_tiktok_help
        )
        self._btn_help_tt.pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_box, text="🔄", width=34, height=32,
            font=("Segoe UI", 13), fg_color="transparent", border_width=1, border_color=BORDER,
            hover_color=BG_CARD, command=self._load_accounts
        ).pack(side="left", padx=(3, 0))

        # Khung hướng dẫn sử dụng chi tiết (mặc định ẩn hoàn toàn)
        self._help_frame = ctk.CTkFrame(self.tab_tiktok, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 HƯỚNG DẪN QUẢN LÝ DÀN NICK TIKTOK & PROXY CHỐNG CHECKPOINT", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• ➕ Thêm nick mới: Tạo profile sạch để đăng nhập thủ công (ID/Mật khẩu hoặc QR Code). Hệ thống tự động lưu Cookies sau khi bạn đăng nhập thành công.\n"
            "• 📁 Tải JSON: Nhập nhanh file Cookie dạng .json (xuất từ Cookie-Editor, J2Team Cookies) mà không cần mở trình duyệt.\n"
            "• 🌐 Proxy (IP:Port:User:Pass): Gán Proxy HTTP hoặc SOCKS5 riêng biệt cho từng nick để chống trùng IP, tránh bị TikTok bóp tương tác hoặc shadowban.\n"
            "• 🚀 Mở Duyệt: Mở Chromium sạch với hồ sơ & cookie tương ứng để lướt dạo, kiểm tra video cá nhân.\n"
            "• 🛡️ Ẩn Danh (Cloak): Chế độ chạy qua CloakBrowser giả lập vân tay Canvas, WebGL, Audio và GeoIP tầng C++, vượt checkpoint bảo mật tối đa."
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không pack lúc khởi tạo
        
        # ── TABLE COLUMN HEADER BAR ──────────────────────────────────────────
        self._col_hdr = ctk.CTkFrame(self.tab_tiktok, fg_color="#0D111C", height=32, corner_radius=6, border_width=1, border_color=BORDER)
        self._col_hdr.pack(fill="x", pady=(0, 4), padx=2)
        self._col_hdr.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self._col_hdr, text="HỒ SƠ TÀI KHOẢN (TIKTOK)", font=("Segoe UI", 10, "bold"), text_color=TEXT_MUTED, width=210, anchor="w").grid(row=0, column=0, padx=(14, 10), pady=6, sticky="w")
        ctk.CTkLabel(self._col_hdr, text="CẤU HÌNH PROXY (IP:PORT:USER:PASS)", font=("Segoe UI", 10, "bold"), text_color=TEXT_MUTED, anchor="w").grid(row=0, column=1, padx=10, pady=6, sticky="w")
        ctk.CTkLabel(self._col_hdr, text="THAO TÁC / DUYỆT BROWSER", font=("Segoe UI", 10, "bold"), text_color=TEXT_MUTED, width=275, anchor="e").grid(row=0, column=2, padx=(10, 14), pady=6, sticky="e")

        self._list_frame = ctk.CTkScrollableFrame(self.tab_tiktok, fg_color=BG_DARK, corner_radius=10, border_width=1, border_color=BORDER)
        self._list_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self._proxy_entries = {}
        self._load_accounts()

    def _toggle_tiktok_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.pack_forget()
            if hasattr(self, "_btn_help_tt"):
                self._btn_help_tt.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                if hasattr(self, "_col_hdr"):
                    self._help_frame.pack(fill="x", pady=(0, 8), padx=2, before=self._col_hdr)
                else:
                    self._help_frame.pack(fill="x", pady=(0, 8), padx=2)
                if hasattr(self, "_btn_help_tt"):
                    self._btn_help_tt.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

    def _filter_accounts(self):
        query = self._search_entry.get().strip().lower()
        for acc, card in self._account_card_widgets.items():
            proxy_val = self._proxy_entries.get(acc).get().strip().lower() if acc in self._proxy_entries else ""
            if not query or query in acc.lower() or query in proxy_val:
                card.pack(fill="x", pady=4, padx=6)
            else:
                card.pack_forget()

    def _on_proxy_changed(self, acc_name=None):
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)

    def _save_all_proxies_manual(self):
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        from tkinter import messagebox
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)
        messagebox.showinfo("Thành công", "Đã lưu toàn bộ cấu hình Proxy cho các tài khoản!")

    def _build_youtube_tab(self):
        ctk.CTkLabel(self.tab_youtube, text="Danh sách tài khoản YouTube (OAuth Token):", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 8))
        
        self._yt_list_frame = ctk.CTkScrollableFrame(self.tab_youtube, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._yt_list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Khung hướng dẫn YouTube OAuth
        yt_help = ctk.CTkFrame(self.tab_youtube, fg_color="#182333", corner_radius=8, border_width=1, border_color="#2c3e50")
        yt_help.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(yt_help, text="📖 HƯỚNG DẪN KẾT NỐI TÀI KHOẢN YOUTUBE (OAUTH 2.0)", font=("Segoe UI", 11, "bold"), text_color="#e74c3c").pack(anchor="w", padx=12, pady=(6, 2))
        yt_text = (
            "• Bước 1: Vào Google Cloud Console -> Tạo Project -> Bật 'YouTube Data API v3'.\n"
            "• Bước 2: Tạo 'OAuth 2.0 Client ID' (loại Desktop App) -> Tải file client_secret.json về máy.\n"
            "• Bước 3: Chọn file bên dưới HOẶC dán mã JSON -> Bấm 'Đăng nhập' để cấp quyền tải video lên kênh."
        )
        ctk.CTkLabel(yt_help, text=yt_text, font=("Segoe UI", 10), text_color=TEXT_DIM, justify="left").pack(anchor="w", padx=12, pady=(0, 6))

        secret_frame = ctk.CTkFrame(self.tab_youtube, fg_color="transparent")
        secret_frame.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(secret_frame, text="Client Secret (File):", font=("Segoe UI", 12)).pack(side="left")
        self._secret_entry = ctk.CTkEntry(secret_frame, font=("Segoe UI", 11), width=250)
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        self._secret_entry.insert(0, str(user_dir / "client_secret.json"))
        self._secret_entry.pack(side="left", padx=10)
        ctk.CTkButton(secret_frame, text="📁", width=36, height=28, fg_color=BORDER, hover_color=BG_CARD, command=self._pick_secret).pack(side="left")
        ctk.CTkButton(secret_frame, text="Đăng nhập", fg_color=SUCCESS, hover_color="#27ae60", command=self._add_yt_account).pack(side="left", padx=(10, 0))
        
        paste_frame = ctk.CTkFrame(self.tab_youtube, fg_color="transparent")
        paste_frame.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(paste_frame, text="Hoặc dán mã JSON của Client Secret (KHÔNG PHẢI COOKIES!):", font=("Segoe UI", 12, "bold"), text_color="#e74c3c").pack(anchor="w")
        self._json_textbox = ctk.CTkTextbox(paste_frame, height=80, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._json_textbox.pack(fill="x", pady=4)
        ctk.CTkButton(paste_frame, text="Lưu JSON & Đăng nhập", fg_color=SUCCESS, hover_color="#27ae60", command=self._add_yt_account_from_json).pack(anchor="w")
        
        self._load_yt_accounts()

    def _load_accounts(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()
        if not hasattr(self, '_proxy_entries'):
            self._proxy_entries = {}
        self._proxy_entries.clear()
        self._account_card_widgets.clear()
        
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        
        accounts = sorted([f.name for f in user_dir.glob("tiktok_*.json")])
        self._all_accounts_cache = accounts
        saved_proxies = self._load_proxies(user_dir)

        # Cập nhật chip thống kê số lượng
        proxy_count = sum(1 for a in accounts if saved_proxies.get(a))
        if hasattr(self, "_lbl_tt_stats"):
            self._lbl_tt_stats.configure(text=f"📱 {len(accounts)} Tài Khoản TikTok  •  🌐 {proxy_count}/{len(accounts)} Có Proxy")

        if not accounts:
            empty_box = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            empty_box.pack(pady=40)
            ctk.CTkLabel(empty_box, text="📭", font=("Segoe UI", 36)).pack()
            ctk.CTkLabel(empty_box, text="Chưa có tài khoản TikTok nào trong hệ thống.", font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN).pack(pady=(6, 2))
            ctk.CTkLabel(empty_box, text="Hãy bấm '➕ Thêm Nick' hoặc '📁 Tải JSON' để bắt đầu quản lý.", font=("Segoe UI", 11), text_color=TEXT_DIM).pack()
            return
            
        import json
        for acc in accounts:
            card = ctk.CTkFrame(self._list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=4, padx=6)
            card.grid_columnconfigure(1, weight=1)
            self._account_card_widgets[acc] = card
            
            display_acc = acc.replace("tiktok_", "").replace(".json", "")
            full_acc_name = display_acc
            if len(display_acc) > 24:
                display_acc = display_acc[:22] + "..."
                
            # Kiểm tra tình trạng cookie thực tế
            c_file = user_dir / acc
            has_cookies = False
            cookie_count = 0
            try:
                if c_file.exists() and c_file.stat().st_size > 10:
                    with open(c_file, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                        if isinstance(c_data, list) and len(c_data) > 0:
                            has_cookies = True
                            cookie_count = len(c_data)
            except Exception:
                pass
                
            # ── CỘT 1: Avatar & Identity ─────────────────────────────────────
            col_id = ctk.CTkFrame(card, fg_color="transparent", width=210)
            col_id.grid(row=0, column=0, padx=(12, 10), pady=8, sticky="w")
            
            # Avatar tròn icon TikTok tím đậm
            avt = ctk.CTkLabel(
                col_id, text="🎵", width=36, height=36,
                fg_color="#1E1B4B", corner_radius=18, font=("Segoe UI", 13),
                text_color="#C4B5FD"
            )
            avt.pack(side="left", padx=(0, 10))
            
            info_box = ctk.CTkFrame(col_id, fg_color="transparent")
            info_box.pack(side="left")
            
            lbl_name = ctk.CTkLabel(info_box, text=display_acc, font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN, anchor="w")
            lbl_name.pack(anchor="w")
            if len(full_acc_name) > 24:
                ToolTip(lbl_name, full_acc_name)
                
            if has_cookies:
                lbl_status = ctk.CTkLabel(info_box, text=f"● Sẵn sàng ({cookie_count})", font=("Segoe UI", 10, "bold"), text_color=SUCCESS, anchor="w")
            else:
                lbl_status = ctk.CTkLabel(info_box, text="○ Chưa có Cookie", font=("Segoe UI", 10, "bold"), text_color=WARNING, anchor="w")
            lbl_status.pack(anchor="w")
            
            # ── CỘT 2: Ô Proxy hiện đại ──────────────────────────────────────
            p_box = ctk.CTkFrame(card, fg_color="#0A0D14", corner_radius=8, border_width=1, border_color="#1E293B")
            p_box.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
            p_box.grid_columnconfigure(1, weight=1)
            
            ctk.CTkLabel(p_box, text="🌐", font=("Segoe UI", 12), text_color="#06B6D4").grid(row=0, column=0, padx=(8, 4))
            
            proxy_entry = ctk.CTkEntry(
                p_box, height=30, font=("Consolas", 11),
                placeholder_text="Gán Proxy (ip:port:user:pass) - Bỏ trống để dùng IP máy",
                fg_color="transparent", border_width=0, text_color=TEXT_MAIN,
                placeholder_text_color="#475569"
            )
            proxy_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
            
            if acc in saved_proxies and saved_proxies[acc]:
                proxy_entry.insert(0, saved_proxies[acc])
            self._proxy_entries[acc] = proxy_entry
            
            # Tự động lưu proxy khi sửa
            proxy_entry.bind("<FocusOut>", lambda e, a=acc: self._on_proxy_changed(a))
            proxy_entry.bind("<KeyRelease>", lambda e, a=acc: self._on_proxy_changed(a))
            
            # ── CỘT 3: Cụm Nút Hành Động ─────────────────────────────────────
            act_box = ctk.CTkFrame(card, fg_color="transparent")
            act_box.grid(row=0, column=2, padx=(0, 10), pady=8, sticky="e")
            
            # Nút Mở duyệt thường
            btn_login = ctk.CTkButton(
                act_box, text="🚀 Mở Duyệt", width=88, height=30, corner_radius=7,
                font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=lambda a=acc: self._manual_login(a)
            )
            btn_login.pack(side="left", padx=3)
            ToolTip(btn_login, "Mở trình duyệt bình thường để kiểm tra trang cá nhân")
            
            # Nút Ẩn danh Cloak
            btn_login_cloak = ctk.CTkButton(
                act_box, text="🛡️ Ẩn Danh", width=88, height=30, corner_radius=7,
                font=("Segoe UI", 11, "bold"), fg_color="#1E1B4B", hover_color="#312E81",
                text_color="#C4B5FD", border_width=1, border_color="#8B5CF6",
                command=lambda a=acc: self._manual_login(a, use_cloak=True)
            )
            btn_login_cloak.pack(side="left", padx=3)
            ToolTip(btn_login_cloak, "Mở trình duyệt ẩn danh chuyên sâu (Fake Canvas, WebGL, Audio) vượt Checkpoint")
            
            # Nút Sửa
            btn_edit = ctk.CTkButton(
                act_box, text="✏️", width=34, height=30, corner_radius=7,
                font=("Segoe UI", 12), fg_color="#1E293B", hover_color="#334155",
                text_color=TEXT_MAIN,
                command=lambda a=acc: self._edit_account(a)
            )
            btn_edit.pack(side="left", padx=3)
            ToolTip(btn_edit, "Đổi tên hoặc chỉnh sửa cookie JSON")
            
            # Nút Xóa
            btn_delete = ctk.CTkButton(
                act_box, text="🗑️", width=34, height=30, corner_radius=7,
                font=("Segoe UI", 12), fg_color="#3B1219", hover_color="#581C26",
                text_color="#EF4444", border_width=1, border_color="#7F1D1D",
                command=lambda a=acc: self._delete_tiktok_account(a)
            )
            btn_delete.pack(side="left", padx=3)
            ToolTip(btn_delete, "Xóa tài khoản khỏi phần mềm")

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
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        user_dir.mkdir(parents=True, exist_ok=True)
        
        cookie_file = user_dir / acc_name
        if not cookie_file.exists():
            import json
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump([], f)
                
        self._load_accounts()
        from tkinter import messagebox
        messagebox.showinfo("Thành công", f"Đã tạo {acc_name}. Hãy điền Proxy và bấm '🔑 Login' để lưu phiên!")

    def _manual_login(self, acc_name, force_no_proxy=False, use_cloak=False):
        proxy_str = None
        if not force_no_proxy:
            proxy_str = self._proxy_entries[acc_name].get().strip()
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)
        
        cookie_path = str(user_dir / acc_name)
        
        def _login_worker():
            import asyncio
            from config.settings import TIKTOK_CONFIG
            from uploader.tiktok_uploader import TikTokUploader
            old_headless = TIKTOK_CONFIG["browser"].get("headless", True)
            TIKTOK_CONFIG["browser"]["headless"] = False
            try:
                async def _run():
                    uploader = TikTokUploader(cookies_file=cookie_path, proxy=proxy_str if proxy_str else None)
                    try:
                        await uploader._init_browser()
                        tiktok_page = uploader.page if uploader.page else await uploader.context.new_page()
                        try:
                            await tiktok_page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=25000)
                        except Exception as nav_err:
                            nav_str = str(nav_err)
                            if "ERR_HTTP_RESPONSE_CODE_FAILURE" in nav_str or "403" in nav_str:
                                # Cookies cũ trong máy bị TikTok từ chối (HTTP 403) -> Xóa cookie cũ để mở trang đăng nhập sạch
                                await uploader.context.clear_cookies()
                                await tiktok_page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=25000)
                            else:
                                raise nav_err

                        while len(uploader.context.pages) > 0:
                            try:
                                await uploader.context.pages[0].title()
                                await asyncio.sleep(1)
                            except:
                                break
                        # Tự động xuất cookies ra file JSON để đồng bộ lên VPS
                        try:
                            raw_cookies = await uploader.context.cookies()
                            tt_cookies = [c for c in raw_cookies if "tiktok" in c.get("domain", "")]
                            if tt_cookies:
                                import json
                                with open(cookie_path, "w", encoding="utf-8") as f:
                                    json.dump(tt_cookies, f, indent=4)
                        except Exception as err:
                            pass
                    finally:
                        await uploader.close()
                import sys
                if sys.platform == 'win32' and sys.version_info < (3, 14):
                    try:
                        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    except Exception:
                        pass
                asyncio.run(_run())
                
                def _on_succ():
                    from tkinter import messagebox
                    messagebox.showinfo("Thành công", f"Đã đóng trình duyệt và lưu phiên đăng nhập cho {acc_name}.")
                self.after(0, _on_succ)
                
            except Exception as e:
                err_msg = str(e)
                def _on_err():
                    from tkinter import messagebox
                    if "Lỗi Proxy" in err_msg or ("net::ERR_" in err_msg and "ERR_HTTP_RESPONSE_CODE_FAILURE" not in err_msg) or "Timeout" in err_msg:
                        msg = f"Proxy có vẻ đã chết hoặc sai thông tin!\n\nLỗi:\n{err_msg}\n\nBạn có muốn BỎ QUA PROXY và dùng IP thật của máy để tiếp tục không?"
                        if messagebox.askyesno("Proxy Hết Hạn / Lỗi", msg):
                            self._manual_login(acc_name, force_no_proxy=True)
                    else:
                        messagebox.showerror("Lỗi", f"Lỗi khi mở đăng nhập:\n{err_msg}")
                self.after(0, _on_err)
            finally:
                TIKTOK_CONFIG["browser"]["headless"] = old_headless
                
        import threading
        threading.Thread(target=_login_worker, daemon=True).start()

    def _load_proxies(self, user_dir) -> dict:
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
        import json
        proxies = {}
        for acc, entry in self._proxy_entries.items():
            val = entry.get().strip()
            if val:
                proxies[acc] = val
        proxy_file = user_dir / "proxies.json"
        with open(proxy_file, "w", encoding="utf-8") as f:
            json.dump(proxies, f, indent=2, ensure_ascii=False)

    def _delete_tiktok_account(self, filename):
        from tkinter import messagebox
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa {filename}?"):
            try:
                from config.settings import COOKIES_DIR
                from auth_client import auth_client
                username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
                username = username.replace("@", "_").replace(".", "_")
                user_dir = COOKIES_DIR / username
                (user_dir / filename).unlink(missing_ok=True)
                self._load_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa file: {e}")

    def _upload_account(self):
        from tkinter import filedialog, messagebox
        import shutil
        import os
        path = filedialog.askopenfilename(
            title="Chọn file cookie JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                dest_name = os.path.basename(path)
                if not dest_name.startswith("tiktok_"):
                    dest_name = f"tiktok_{dest_name}"
                from config.settings import COOKIES_DIR
                from auth_client import auth_client
                username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
                username = username.replace("@", "_").replace(".", "_")
                user_dir = COOKIES_DIR / username
                user_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, user_dir / dest_name)
                messagebox.showinfo("Thành công", f"Đã tải lên tài khoản: {dest_name}")
                self._load_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể tải lên file: {e}")

    def _edit_account(self, filename):
        from tkinter import messagebox
        try:
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            username = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / username
            with open(user_dir / filename, "r", encoding="utf-8") as f:
                content = f.read()
            InputJSONWindow(self.winfo_toplevel(), on_close_callback=self._load_accounts, initial_name=filename, initial_content=content)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

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

    def _load_yt_accounts(self):
        for widget in self._yt_list_frame.winfo_children():
            widget.destroy()
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        accounts = [f.name for f in user_dir.glob("youtube_*.json")]
        
        if not accounts:
            empty_box = ctk.CTkFrame(self._yt_list_frame, fg_color="transparent")
            empty_box.pack(pady=30)
            ctk.CTkLabel(empty_box, text="📭", font=("Segoe UI", 32)).pack()
            ctk.CTkLabel(empty_box, text="Chưa có kênh YouTube nào được kết nối.", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).pack(pady=(4, 0))
            return
            
        for acc in accounts:
            card = ctk.CTkFrame(self._yt_list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=4, padx=6)
            
            # Avatar
            avt = ctk.CTkLabel(
                card, text="🎬", width=36, height=36,
                fg_color="#3d1f1f", corner_radius=18, font=("Segoe UI", 13)
            )
            avt.pack(side="left", padx=10, pady=8)
            
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="y", pady=8)
            ctk.CTkLabel(info, text=f"Kênh YouTube: {acc.replace('.json', '')}", font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
            ctk.CTkLabel(info, text=f"● OAuth Token sẵn sàng  •  {acc}", font=("Segoe UI", 10), text_color=SUCCESS).pack(anchor="w")
            
            btn_del = ctk.CTkButton(
                card, text="🗑️", width=34, height=30, corner_radius=7, font=("Segoe UI", 12),
                fg_color="#3B1219", hover_color="#581C26", text_color="#EF4444",
                border_width=1, border_color="#7F1D1D",
                command=lambda a=acc: self._delete_yt_account(a)
            )
            btn_del.pack(side="right", padx=12, pady=8)
            ToolTip(btn_del, "Xóa tài khoản YouTube này")

    def _delete_yt_account(self, name):
        from tkinter import messagebox
        import os
        if messagebox.askyesno("Xác nhận", f"Xóa tài khoản YouTube: {name}?"):
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            username = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / username
            path = user_dir / name
            try:
                if path.exists():
                    os.remove(path)
                self._load_yt_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa: {e}")

    def _add_yt_account_from_json(self):
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
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        secret_path = str(user_dir / "client_secret.json")
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(json_text)
            
        self._secret_entry.delete(0, "end")
        self._secret_entry.insert(0, secret_path)
        self._json_textbox.delete("1.0", "end")
        self._add_yt_account()

    def _add_yt_account(self):
        secret_path = self._secret_entry.get().strip()
        import os
        if not os.path.exists(secret_path):
            from tkinter import messagebox
            messagebox.showerror("Lỗi", "Không tìm thấy file client_secret.json! Vui lòng tải từ Google Cloud Console hoặc dán code JSON vào ô bên dưới.")
            return
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
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
            self._load_yt_accounts()
            
        t = threading.Thread(target=_auth_thread, daemon=True)
        t.start()



    def _build_facebook_tab(self):
        ctk.CTkLabel(self.tab_facebook, text="Danh sách Fanpage Facebook (Reels Token):", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 8))
        
        self._fb_list_frame = ctk.CTkScrollableFrame(self.tab_facebook, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._fb_list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Khung hướng dẫn Facebook Fanpage
        fb_help = ctk.CTkFrame(self.tab_facebook, fg_color="#182333", corner_radius=8, border_width=1, border_color="#2c3e50")
        fb_help.pack(fill="x", pady=(0, 8), padx=4)
        ctk.CTkLabel(fb_help, text="📖 HƯỚNG DẪN KẾT NỐI FANPAGE FACEBOOK REELS", font=("Segoe UI", 11, "bold"), text_color="#3498db").pack(anchor="w", padx=12, pady=(6, 2))
        fb_text = (
            "• Page ID: ID của Fanpage bạn quản lý (Lấy trong Cài đặt Trang -> Thông tin Trang hoặc findmyfbid.in).\n"
            "• Access Token: Nhập Page Access Token dài hạn (bắt đầu bằng EAA...) có quyền pages_manage_posts.\n"
            "• Cookie (Tùy chọn): Bạn cũng có thể dán Cookie tài khoản Facebook cá nhân đang làm Quản trị viên của Trang."
        )
        ctk.CTkLabel(fb_help, text=fb_text, font=("Segoe UI", 10), text_color=TEXT_DIM, justify="left").pack(anchor="w", padx=12, pady=(0, 6))

        self._editing_fb_filename = None
        form_frame = ctk.CTkFrame(self.tab_facebook, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER)
        form_frame.pack(fill="x", pady=(0, 8), padx=4, ipady=8)
        
        self._lbl_fb_title = ctk.CTkLabel(form_frame, text="Thêm Fanpage Mới (Graph API):", font=("Segoe UI", 13, "bold"), text_color=ACCENT)
        self._lbl_fb_title.pack(anchor="w", padx=12, pady=(0, 6))
        
        # Row 1: Page ID & Name
        row1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row1, text="Page ID:", width=90, font=("Segoe UI", 12)).pack(side="left")
        self._fb_page_id_entry = ctk.CTkEntry(row1, font=("Consolas", 12), placeholder_text="VD: 100085678912345")
        self._fb_page_id_entry.pack(side="left", fill="x", expand=True, padx=(0, 15))
        
        ctk.CTkLabel(row1, text="Tên gợi nhớ (Tùy chọn):", width=140, font=("Segoe UI", 12)).pack(side="left")
        self._fb_name_entry = ctk.CTkEntry(row1, font=("Segoe UI", 12), placeholder_text="VD: Page Gái Xinh")
        self._fb_name_entry.pack(side="left", fill="x", expand=True)
        
        # Row 2: Page Access Token
        row2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(row2, text="Access Token:", width=90, font=("Segoe UI", 12)).pack(side="left")
        self._fb_token_entry = ctk.CTkEntry(row2, font=("Consolas", 11), placeholder_text="Dán Page Access Token (EAA...) HOẶC Cookie Facebook vào đây")
        self._fb_token_entry.pack(side="left", fill="x", expand=True, padx=(0, 15))
        
        self._btn_add_fb = ctk.CTkButton(row2, text="🔍 Kiểm tra & Thêm", fg_color=SUCCESS, hover_color="#27ae60", width=140, command=self._add_fb_account)
        self._btn_add_fb.pack(side="left")
        
        self._btn_cancel_fb_edit = ctk.CTkButton(row2, text="❌ Hủy Sửa", fg_color=BORDER, hover_color=BG_DARK, width=80, command=self._cancel_edit_fb)
        
        self._load_fb_accounts()

    def _load_fb_accounts(self):
        for widget in self._fb_list_frame.winfo_children():
            widget.destroy()
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        import json
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        accounts = [f.name for f in user_dir.glob("facebook_*.json")]
        
        if not accounts:
            empty_box = ctk.CTkFrame(self._fb_list_frame, fg_color="transparent")
            empty_box.pack(pady=30)
            ctk.CTkLabel(empty_box, text="📭", font=("Segoe UI", 32)).pack()
            ctk.CTkLabel(empty_box, text="Chưa có Fanpage Facebook nào được kết nối.", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).pack(pady=(4, 0))
            return
            
        for acc in accounts:
            card = ctk.CTkFrame(self._fb_list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=4, padx=6)
            
            # Avatar Facebook
            avt = ctk.CTkLabel(
                card, text="📘", width=36, height=36,
                fg_color="#1a2d4c", corner_radius=18, font=("Segoe UI", 13)
            )
            avt.pack(side="left", padx=10, pady=8)
            
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="y", pady=8)
            
            # Read info
            page_name = acc
            page_id = "N/A"
            try:
                with open(user_dir / acc, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    page_name = data.get('page_name') or acc
                    page_id = data.get('page_id') or "N/A"
            except Exception:
                pass
                
            ctk.CTkLabel(info, text=f"{page_name}", font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
            ctk.CTkLabel(info, text=f"● Page ID: {page_id}  •  Tệp: {acc}", font=("Segoe UI", 10), text_color=SUCCESS).pack(anchor="w")
            
            btn_del = ctk.CTkButton(
                card, text="🗑️", width=34, height=30, corner_radius=7, font=("Segoe UI", 12),
                fg_color="#3B1219", hover_color="#581C26", text_color="#EF4444",
                border_width=1, border_color="#7F1D1D",
                command=lambda a=acc: self._delete_fb_account(a)
            )
            btn_del.pack(side="right", padx=10, pady=8)
            ToolTip(btn_del, "Xóa Fanpage này")
            
            btn_edit = ctk.CTkButton(
                card, text="✏️", width=34, height=30, corner_radius=7, font=("Segoe UI", 12),
                fg_color="#1E293B", hover_color="#334155", text_color=TEXT_MAIN,
                command=lambda a=acc: self._edit_fb_account(a)
            )
            btn_edit.pack(side="right", padx=(0, 4), pady=8)
            ToolTip(btn_edit, "Chỉnh sửa Page ID / Access Token")

    def _edit_fb_account(self, filename):
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        import json
        from tkinter import messagebox
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        file_path = user_dir / filename
        if not file_path.exists():
            messagebox.showerror("Lỗi", f"Không tìm thấy file: {filename}")
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._fb_page_id_entry.delete(0, "end")
            self._fb_page_id_entry.insert(0, str(data.get("page_id", "")))
            
            self._fb_name_entry.delete(0, "end")
            self._fb_name_entry.insert(0, str(data.get("page_name", "")))
            
            self._fb_token_entry.delete(0, "end")
            self._fb_token_entry.insert(0, str(data.get("page_access_token", "")))
            
            self._editing_fb_filename = filename
            self._lbl_fb_title.configure(text=f"✏️ Đang chỉnh sửa Fanpage [{filename}]:", text_color="#f39c12")
            self._btn_add_fb.configure(text="💾 Lưu Thay Đổi", fg_color=ACCENT)
            self._btn_cancel_fb_edit.pack(side="left", padx=(8, 0))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc file {filename}: {e}")

    def _cancel_edit_fb(self):
        self._editing_fb_filename = None
        self._fb_page_id_entry.delete(0, "end")
        self._fb_name_entry.delete(0, "end")
        self._fb_token_entry.delete(0, "end")
        self._lbl_fb_title.configure(text="Thêm Fanpage Mới (Graph API):", text_color=ACCENT)
        self._btn_add_fb.configure(text="🔍 Kiểm tra & Thêm", fg_color=SUCCESS)
        self._btn_cancel_fb_edit.pack_forget()

    def _add_fb_account(self):
        page_id = self._fb_page_id_entry.get().strip()
        token = self._fb_token_entry.get().strip()
        custom_name = self._fb_name_entry.get().strip()
        
        from tkinter import messagebox
        if not token:
            messagebox.showerror("Lỗi", "Vui lòng nhập Access Token.")
            return
            
        from uploader.facebook_uploader import FacebookUploader
        self._btn_add_fb.configure(text="Đang kiểm tra...", state="disabled")
        
        import threading
        def _verify():
            res = FacebookUploader.extract_from_cookie_or_token(token, page_id)
            self.after(0, lambda: _on_verify_done(res))
            
        def _on_verify_done(res):
            btn_text = "💾 Lưu Thay Đổi" if self._editing_fb_filename else "🔍 Kiểm tra & Thêm"
            self._btn_add_fb.configure(text=btn_text, state="normal")
            if not res.get("valid"):
                err_msg = res.get('error', '')
                prompt = f"Lỗi xác thực Graph API:\n{err_msg}\n\n👉 Bạn có muốn BỎ QUA KIỂM TRA và LƯU TRỰC TIẾP Fanpage này vào tool để đăng Reels không?"
                if messagebox.askyesno("Xác thực không thành công", prompt):
                    real_page_id = page_id or "me"
                    real_token = token
                    page_name = custom_name or f"Fanpage {real_page_id}"
                else:
                    return
            else:
                real_page_id = str(res.get("page_id") or page_id)
                real_token = str(res.get("page_access_token") or token)
                page_name = custom_name or res.get("page_name") or f"Page {real_page_id}"
            
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            import json
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            username = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / username
            user_dir.mkdir(parents=True, exist_ok=True)
            
            if self._editing_fb_filename:
                target_file = self._editing_fb_filename
                success_msg = f"Đã cập nhật Fanpage: {page_name} ({target_file})"
            else:
                idx = 1
                while (user_dir / f"facebook_{idx}.json").exists():
                    idx += 1
                target_file = f"facebook_{idx}.json"
                success_msg = f"Đã thêm Fanpage: {page_name} ({target_file})"
            
            save_data = {
                "page_id": real_page_id,
                "page_name": page_name,
                "page_access_token": real_token,
                "created_at": str(Path(__file__).stat().st_mtime)
            }
            with open(user_dir / target_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
                
            self._cancel_edit_fb()
            messagebox.showinfo("Thành công", success_msg)
            self._load_fb_accounts()
            
        threading.Thread(target=_verify, daemon=True).start()

    def _delete_fb_account(self, name):
        from tkinter import messagebox
        import os
        if messagebox.askyesno("Xác nhận", f"Xóa tài khoản Facebook: {name}?"):
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            username = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / username
            path = user_dir / name
            try:
                if path.exists():
                    os.remove(path)
                if getattr(self, "_editing_fb_filename", None) == name:
                    self._cancel_edit_fb()
                self._load_fb_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa: {e}")


class FarmTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self._checkboxes = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build()
        self.after(200, self._load_accounts)

    def _build(self):
        # Header
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        t_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        t_box.pack(side="left")
        ctk.CTkLabel(
            t_box, text="🌱  Nuôi Nick Tự Động (Farm Account)",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            t_box, text="Giả lập hành vi người dùng thật: Lướt dạo, xem video, thả tim để tăng uy tín tài khoản, chống bóp tương tác",
            font=("Segoe UI", 11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        
        self._btn_help_farm = ctk.CTkButton(
            hdr_frame, text="❓ Hướng dẫn", width=105, height=32, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_CARD,
            command=self._toggle_farm_help
        )
        self._btn_help_farm.pack(side="right")
        
        # Guide frame (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 HƯỚNG DẪN NUÔI NICK TĂNG TƯƠNG TÁC (CHỐNG FLOP & KHÓA NICK)", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• 1. Tại sao cần Nuôi nick (Farm) trước khi đăng bài?\n"
            "  - Nick mới hoặc lâu ngày không hoạt động nếu vừa mở lên đã đăng video ngay sẽ bị thuật toán TikTok đánh dấu spam/bot -> Rất dễ bị 0 view hoặc checkpoint.\n"
            "  - Nuôi nick giúp nick có 'lịch sử người dùng thật': Có lượt xem, thời gian dừng trên video (watch time), thả tim, lướt đọc comment tự nhiên.\n"
            "• 2. Chọn Kịch bản nuôi:\n"
            "  - Chọn kịch bản có sẵn ở menu (hoặc bấm '⚙ Quản lý Kịch bản' để tùy chỉnh thời gian lướt, tỉ lệ thả tim ngẫu nhiên 20-30%).\n"
            "• 3. Cấu hình số luồng & Hiện trình duyệt:\n"
            "  - Số luồng: Khuyên dùng 2-3 luồng cho máy cá nhân để máy chạy mượt, 5-10 luồng nếu chạy máy trâu hoặc VPS.\n"
            "  - 'Hiện trình duyệt': BẬT để mở cửa sổ Chrome theo dõi thao tác thực tế; TẮT để chạy ngầm tiết kiệm tối đa RAM & CPU.\n"
            "• 4. Bắt đầu nuôi:\n"
            "  - Tích chọn các nick TikTok ở cột bên trái -> Bấm nút '▶ Bắt đầu Nuôi'. Xem nhật ký hoạt động trực tiếp ở khung Log bên phải."
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không grid lúc khởi tạo

        # Cấu hình
        cfg = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        cfg.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        cfg.grid_columnconfigure(0, weight=1)
        
        row1 = ctk.CTkFrame(cfg, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew", padx=20, pady=16)
        row1.grid_columnconfigure(6, weight=1) # Đẩy nút Start sang phải

        ctk.CTkLabel(row1, text="📜 Kịch bản Nuôi:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=0, padx=(0, 10))
        
        self.flows = []
        self._load_flows()
        
        flow_names = [f["name"] for f in self.flows] if self.flows else ["Chưa có kịch bản"]
        self._combo_flow = ctk.CTkOptionMenu(row1, values=flow_names, width=280)
        self._combo_flow.grid(row=0, column=1, padx=(0, 10))
        
        btn_manage_flow = ctk.CTkButton(
            row1, text="⚙ Quản lý Kịch bản", width=120, height=28, font=("Segoe UI", 11, "bold"),
            fg_color=BORDER, hover_color=BG_DARK, text_color=TEXT_MAIN,
            command=self._open_flow_manager
        )
        btn_manage_flow.grid(row=0, column=2, padx=(0, 10))

        ctk.CTkLabel(row1, text="Số luồng:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=0, column=3, padx=(10, 5))
        self._opt_threads = ctk.CTkOptionMenu(row1, values=["1", "2", "3", "5", "10", "15"], width=60)
        self._opt_threads.grid(row=0, column=4, padx=(0, 10))
        self._opt_threads.set("3")

        # Bật/Tắt Hiện Trình Duyệt (Headless)
        self._sw_show_browser = ctk.CTkSwitch(
            row1, text="Hiện trình duyệt ❔", font=("Segoe UI", 11, "bold"),
            text_color=TEXT_MAIN, cursor="hand2"
        )
        self._sw_show_browser.select() # Mặc định BẬT (Hiện trình duyệt)
        self._sw_show_browser.grid(row=0, column=5, padx=(10, 15))
        ToolTip(self._sw_show_browser, "BẬT (ON): Mở cửa sổ trình duyệt Chrome để xem trực tiếp các thao tác lướt, tim, xem video.\nTẮT (OFF): Chạy ẩn ngầm (Headless) tiết kiệm tối đa RAM & CPU, không mở cửa sổ làm phiền màn hình làm việc.")

        # Nạp cấu hình lưu trước đó (nếu có)
        try:
            from config.settings import BASE_DIR
            import json
            cfg_path = BASE_DIR / "config" / "farm_ui.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    f_cfg = json.load(f)
                    if "show_browser" in f_cfg:
                        if f_cfg["show_browser"]:
                            self._sw_show_browser.select()
                        else:
                            self._sw_show_browser.deselect()
                    if "threads" in f_cfg and str(f_cfg["threads"]) in ["1", "2", "3", "5", "10", "15"]:
                        self._opt_threads.set(str(f_cfg["threads"]))
        except Exception:
            pass

        self._btn_start = ctk.CTkButton(
            row1, text="▶  Bắt đầu Nuôi", height=36, font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60", command=self._start_farm
        )
        self._btn_start.grid(row=0, column=6, sticky="e")

        # Layout cột: Trái (Danh sách Acc), Phải (Log)
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=3, column=0, sticky="nsew")
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
        ctk.CTkButton(hdr, text="☑ Chọn tất cả", width=90, height=24, command=self._toggle_all).pack(side="right", padx=(0, 10))
        
        self._list_frame = ctk.CTkScrollableFrame(acc_frame, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Log
        log_frame = ctk.CTkFrame(split, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        log_frame.grid(row=0, column=1, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        self._log_widget = LogWidget(log_frame)
        self._log_toolbar = LogToolbar(log_frame, self._log_widget, module="farm", title="📋  Nhật ký Nuôi Nick (Logs):")
        self._log_toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self._log_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _toggle_farm_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_farm"):
                self._btn_help_farm.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
                if hasattr(self, "_btn_help_farm"):
                    self._btn_help_farm.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

    def _toggle_all(self):
        if not hasattr(self, "_select_all_state"):
            self._select_all_state = False
        self._select_all_state = not self._select_all_state
        for cb in getattr(self, "_checkboxes", {}).values():
            cb.set(self._select_all_state)
            
    def _load_flows(self):
        import json
        from pathlib import Path
        flows_path = Path("config/flows.json")
        self.flows = []
        if flows_path.exists():
            try:
                with open(flows_path, "r", encoding="utf-8") as f:
                    self.flows = json.load(f)
            except Exception as e:
                self._log(f"Lỗi đọc kịch bản: {e}", "ERROR")

    def _open_flow_manager(self):
        from gui_flows import FlowBuilderDialog
        
        def on_close():
            self._load_flows()
            flow_names = [f["name"] for f in self.flows] if self.flows else ["Chưa có kịch bản"]
            self._combo_flow.configure(values=flow_names)
            if self.flows:
                self._combo_flow.set(flow_names[0])
                
        FlowBuilderDialog(self, on_close_callback=on_close)
        
    def _load_accounts(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        self._proxy_entries = {}
        
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        
        accounts = [f.name for f in user_dir.glob("tiktok_*.json")]
        if not accounts:
            ctk.CTkLabel(self._list_frame, text="Chưa có tài khoản nào. Vui lòng sang tab 'Tài khoản' để thêm.", text_color=TEXT_DIM).pack(pady=20)
            return
            
        for acc in accounts:
            row = ctk.CTkFrame(self._list_frame, fg_color=BG_CARD, corner_radius=6, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=(0, 6), padx=4)
            row.grid_columnconfigure(0, weight=1)
            
            var = ctk.BooleanVar(value=False)
            self._checkboxes[acc] = var
            
            display_acc = acc.replace("tiktok_", "").replace(".json", "")
            if len(display_acc) > 30:
                display_acc = display_acc[:27] + "..."
                
            cb = ctk.CTkCheckBox(row, text=f"  {display_acc}", variable=var, font=("Segoe UI", 13, "bold"), fg_color=SUCCESS, hover_color="#27ae60")
            cb.grid(row=0, column=0, padx=(16, 10), pady=12, sticky="w")
            
            status_lbl = ctk.CTkLabel(row, text="● Sẵn sàng", font=("Segoe UI", 11, "bold"), text_color=SUCCESS)
            status_lbl.grid(row=0, column=1, padx=(10, 16), pady=12, sticky="e")

    def _start_farm(self):
        from auth_client import auth_client
        if auth_client.user_info and auth_client.user_info.get("is_expired", True):
            messagebox.showerror("Bản quyền", "Tài khoản của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục sử dụng!")
            return
            
        if getattr(self, "is_running", False):
            self._cancel_task()
            self._btn_start.configure(state="disabled", text="Đang dừng...")
            return

        selected = [acc for acc, var in self._checkboxes.items() if var.get()]
        if not selected:
            self._log("Vui lòng chọn ít nhất 1 tài khoản để nuôi!", "WARNING")
            return
            
        if not self.flows:
            self._log("Chưa có kịch bản nào. Vui lòng tạo kịch bản trước!", "ERROR")
            return
            
        flow_name = self._combo_flow.get()
        selected_flow = next((f for f in self.flows if f.get("name") == flow_name), None)
        if not selected_flow:
            self._log("Lỗi không tìm thấy kịch bản đã chọn!", "ERROR")
            return
        
        # Thu thập proxy cho mỗi account
        # Đọc từ proxies.json (đã được lưu bởi tab Tài khoản)
        import json
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        proxy_file = user_dir / "proxies.json"
        saved_proxies = {}
        if proxy_file.exists():
            try:
                with open(proxy_file, "r", encoding="utf-8") as f:
                    saved_proxies = json.load(f)
            except Exception:
                pass
        
        proxies = {}
        for acc in selected:
            # Ưu tiên proxy từ giao diện (nếu có), sau đó từ file đã lưu
            if acc in getattr(self, '_proxy_entries', {}) and hasattr(self._proxy_entries[acc], 'get'):
                val = self._proxy_entries[acc].get().strip()
                if val:
                    proxies[acc] = val
                    continue
            if acc in saved_proxies and saved_proxies[acc]:
                proxies[acc] = saved_proxies[acc]
                    
        self.is_running = True
        self._btn_start.configure(state="normal", text="⏹ Dừng lại", fg_color=DANGER, hover_color="#c0392b")
        self._log_widget.clear()
        self._log(f"Bắt đầu nuôi {len(selected)} tài khoản với Kịch bản '{flow_name}'...", "INFO")
        
        try:
            threads = int(self._opt_threads.get())
        except:
            threads = 3

        show_browser = int(self._sw_show_browser.get()) == 1
        headless = not show_browser

        # Lưu cấu hình đã chọn
        try:
            from config.settings import BASE_DIR
            import json
            cfg_path = BASE_DIR / "config" / "farm_ui.json"
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({
                    "show_browser": show_browser,
                    "threads": self._opt_threads.get()
                }, f, indent=2)
        except Exception:
            pass

        self._start_logging_session(
            "farm",
            f"Nuôi {len(selected)} Nick (Kịch bản: {flow_name})",
            {
                "flow": flow_name,
                "accounts_count": len(selected),
                "threads": threads,
                "headless": headless,
            }
        )
        self._run_in_thread(self._do_farm, selected, selected_flow, proxies, max_concurrent=threads, headless=headless)

    async def _do_farm(self, accounts, flow, proxies=None, max_concurrent=3, headless=False):
        import random
        import asyncio
        from uploader.tiktok_uploader import TikTokUploader
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        
        proxies = proxies or {}
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        user_dir = COOKIES_DIR / username
        
        # Giới hạn số luồng (browser) mở cùng lúc để tránh tràn RAM/CPU (Tối đa 3)
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
                mode_str = "Ẩn (Headless)" if headless else "Hiện trình duyệt"
                
                self._log(f"-------------------------------------", "INFO")
                self._log(f"{prefix} 🌱 Bắt đầu Kịch bản: {flow.get('name')} | Chế độ: {mode_str}", "INFO")
                if proxy_str:
                    display_proxy = proxy_str.split("@")[-1] if "@" in proxy_str else proxy_str
                    self._log(f"{prefix} 🌐 Proxy: {display_proxy}", "INFO")
                else:
                    self._log(f"{prefix} ⚠️ Dùng mạng thật (Không Proxy)", "WARNING")
                
                uploader = TikTokUploader(cookies_file=cookie_path, proxy=proxy_str, window_idx=idx, headless=headless)
                try:
                    def update_cb(msg, lvl="INFO"):
                        if "Đang xem video" not in msg: 
                            self._log(f"{prefix} {msg}", lvl)
                    
                    await uploader.execute_farm_flow(
                        flow=flow,
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
        self._built_role = None
        self.refresh_ui()

    def refresh_ui(self, force=False):
        from auth_client import auth_client
        is_adm = auth_client.is_admin()
        
        # Nếu đã dựng giao diện đúng phân quyền và không ép buộc (force), giữ nguyên không reset tab của người dùng
        if not force and self._built_role == is_adm and len(self.winfo_children()) > 0:
            return

        self._built_role = is_adm
        for widget in self.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass
            
        if is_adm:
            self._build_admin()
        else:
            self._build_user()

    def _build_user(self):
        # Header
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        t_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        t_box.pack(side="left")
        ctk.CTkLabel(
            t_box, text="⚙️  Cài Đặt & Bản Quyền Hệ Thống",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN,
        ).pack(anchor="w")
        ctk.CTkLabel(
            t_box, text="Quản lý thời hạn bản quyền, kết nối AI dịch thuật (Ollama/Gemini/Groq) & Sao lưu đám mây",
            font=("Segoe UI", 11), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        
        self._btn_help_settings = ctk.CTkButton(
            hdr_frame, text="❓ Hướng dẫn", width=105, height=32, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_CARD,
            command=self._toggle_settings_help
        )
        self._btn_help_settings.pack(side="right")
        
        # Guide frame (mặc định ẩn hoàn toàn, không chiếm diện tích)
        self._help_frame = ctk.CTkFrame(self, fg_color="#0E1726", corner_radius=10, border_width=1, border_color="#1E3A8A")
        h_title = ctk.CTkFrame(self._help_frame, fg_color="transparent")
        h_title.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(h_title, text="📖 HƯỚNG DẪN CẤU HÌNH HỆ THỐNG & KẾT NỐI AI (DÀNH CHO NGƯỜI MỚI)", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        help_content = (
            "• 1. Quản lý Bản quyền & Gia hạn:\n"
            "  - Hiển thị ngày hết hạn và trạng thái gói cước. Bấm 'Gia Hạn (Thanh Toán QR)' để quét mã VietQR tự động cộng ngày 24/7.\n"
            "• 2. Cấu hình AI Dịch thuật (Nên chọn loại nào?):\n"
            "  - ⚡ Cloud API (Khuyên dùng cho người mới): Chọn 'Chỉ dùng Cloud API' -> Dán Gemini API Key (lấy miễn phí tại aistudio.google.com) hoặc Groq Key (gsk_...). AI xử lý trên đám mây, cực nhanh, không tốn RAM máy tính.\n"
            "  - 💻 Ollama Local (Chạy Offline không cần mạng): Dành cho máy có card đồ họa rời (VGA Nvidia RTX). Tải phần mềm Ollama (ollama.com) -> Cài model qwen2.5 -> Miễn phí vĩnh viễn không giới hạn.\n"
            "  - 🔄 Tự động dự phòng: Chọn 'Cloud API trước ➔ Dự phòng Ollama' để hệ thống luôn dịch trơn tru kể cả khi mất mạng.\n"
            "• 3. Google Drive Backup:\n"
            "  - Bật tính năng này để video sau khi render tự động tải lên Google Drive cá nhân, chống đầy bộ nhớ máy tính."
        )
        ctk.CTkLabel(self._help_frame, text=help_content, font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", wraplength=960).pack(anchor="w", padx=14, pady=(0, 10))
        # Không grid lúc khởi tạo
        
        from auth_client import auth_client
        expire_date = auth_client.user_info.get("expire_date", "Chưa có") if auth_client.user_info else "Chưa có"
        is_expired = auth_client.user_info.get("is_expired", True) if auth_client.user_info else True
        
        status_color = DANGER if is_expired else SUCCESS
        status_text = "Đã hết hạn" if is_expired else "Đang hoạt động"
        
        plan_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=status_color)
        plan_frame.grid(row=2, column=0, sticky="ew")
        
        ctk.CTkLabel(plan_frame, text="Trạng thái:", font=("Segoe UI", 16)).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        ctk.CTkLabel(plan_frame, text=status_text, font=("Segoe UI", 18, "bold"), text_color=status_color).grid(row=0, column=1, pady=(20, 10), sticky="w")
        
        ctk.CTkLabel(plan_frame, text="Ngày Hết Hạn:", font=("Segoe UI", 16)).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
        ctk.CTkLabel(plan_frame, text=expire_date, font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN).grid(row=1, column=1, pady=(0, 20), sticky="w")
        
        ctk.CTkButton(
            plan_frame, text="Gia Hạn (Thanh Toán QR)", fg_color=ACCENT, hover_color=ACCENT_HOVER, 
            command=self._show_payment_dialog
        ).grid(row=0, column=2, rowspan=2, padx=20, pady=20, sticky="e")
        
        plan_frame.grid_columnconfigure(1, weight=1)
        
        # ── AI Provider (Ollama Local / Cloud API) ──
        ctk.CTkLabel(
            self, text="🧠  Cấu Hình AI Dịch Thuật (Ollama Local / API Key)",
            font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN,
        ).grid(row=3, column=0, sticky="w", pady=(24, 8))
        
        ai_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        ai_frame.grid(row=4, column=0, sticky="ew")
        ai_frame.grid_columnconfigure(1, weight=1)

        import os
        import json
        from dotenv import load_dotenv
        load_dotenv()
        from auth_client import auth_client
        from config.settings import COOKIES_DIR
        
        user_is_free = not auth_client.is_paid_user() and not auth_client.is_admin()
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_clean = username.replace("@", "_").replace(".", "_")
        user_settings_file = COOKIES_DIR / user_clean / "settings.json"

        user_custom_key = ""
        user_custom_model = "gemini-3.6-flash-high"
        user_saved_provider = None
        ollama_url_val = os.getenv("OLLAMA_URL", "http://localhost:11434")
        ollama_model_val = os.getenv("OLLAMA_MODEL", "qwen2.5")

        if user_settings_file.exists():
            try:
                with open(user_settings_file, "r", encoding="utf-8") as f:
                    u_cfg = json.load(f)
                    user_custom_key = u_cfg.get("gemini_api_key", "").strip()
                    user_saved_provider = u_cfg.get("ai_provider")
                    if u_cfg.get("ollama_url"):
                        ollama_url_val = u_cfg.get("ollama_url")
                    if u_cfg.get("ollama_model"):
                        ollama_model_val = u_cfg.get("ollama_model")
                    if u_cfg.get("custom_ai_model"):
                        user_custom_model = u_cfg.get("custom_ai_model")
            except Exception:
                pass

        saved_provider = user_saved_provider or PROCESSOR_CONFIG.get("ai_provider")
        if user_is_free and not saved_provider:
            current_provider = "cloud_first"
        else:
            current_provider = (saved_provider or os.getenv("AI_PROVIDER", "cloud_first")).lower()

        # Kiểm tra quyền hạn Cloud AI hệ thống
        has_shared_ai = auth_client.user_info.get("is_ai_enabled", True) if auth_client.user_info else True

        ctk.CTkLabel(ai_frame, text="Nhà cung cấp AI:", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        
        provider_options = [
            "Ollama trước ➔ Dự phòng Cloud API",
            "Cloud API trước ➔ Dự phòng Ollama",
            "Chỉ dùng Cloud API (Vilao / Gemini / Groq)",
            "Chỉ dùng Ollama (Offline)"
        ]
        if current_provider == "ollama_first":
            default_choice = "Ollama trước ➔ Dự phòng Cloud API"
        elif current_provider == "cloud_first":
            default_choice = "Cloud API trước ➔ Dự phòng Ollama"
        elif current_provider == "cloud_only":
            default_choice = "Chỉ dùng Cloud API (Vilao / Gemini / Groq)"
        elif current_provider == "ollama_only":
            default_choice = "Chỉ dùng Ollama (Offline)"
        elif current_provider in ("gemini", "groq", "vilao"):
            default_choice = "Cloud API trước ➔ Dự phòng Ollama"
        elif current_provider == "ollama":
            default_choice = "Ollama trước ➔ Dự phòng Cloud API" if user_custom_key else "Chỉ dùng Ollama (Offline)"
        else:
            default_choice = "Cloud API trước ➔ Dự phòng Ollama"

        self._opt_provider_user = ctk.CTkOptionMenu(
            ai_frame, values=provider_options, font=("Segoe UI", 12),
            fg_color=BG_DARK, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=self._on_provider_change_user
        )
        self._opt_provider_user.set(default_choice)
        self._opt_provider_user.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(16, 8))

        # Subframe cho Ollama
        self._frame_ollama_user = ctk.CTkFrame(ai_frame, fg_color="transparent")
        self._frame_ollama_user.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._frame_ollama_user, text="Ollama URL:", font=("Segoe UI", 12), text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        row_url_user = ctk.CTkFrame(self._frame_ollama_user, fg_color="transparent")
        row_url_user.grid(row=0, column=1, sticky="ew", pady=6)
        row_url_user.grid_columnconfigure(0, weight=1)

        self._entry_ollama_url_user = ctk.CTkEntry(row_url_user, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_ollama_url_user.insert(0, ollama_url_val)
        self._entry_ollama_url_user.grid(row=0, column=0, sticky="ew")

        btn_test_ollama_user = ctk.CTkButton(
            row_url_user, text="🔍 Kiểm tra & Lấy Model", width=160, font=("Segoe UI", 11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._test_ollama_user
        )
        btn_test_ollama_user.grid(row=0, column=1, padx=(8, 0))

        ctk.CTkLabel(self._frame_ollama_user, text="Model Ollama:", font=("Segoe UI", 12), text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        model_suggestions = ["qwen2.5", "qwen2.5:7b", "qwen2.5:3b", "qwen3:4b", "qwen:latest"]
        self._combo_ollama_model_user = ctk.CTkComboBox(
            self._frame_ollama_user, values=model_suggestions, font=("Consolas", 11),
            fg_color=BG_DARK, border_color=BORDER, dropdown_fg_color=BG_CARD
        )
        self._combo_ollama_model_user.set(ollama_model_val)
        self._combo_ollama_model_user.grid(row=1, column=1, sticky="ew", pady=6)

        self._lbl_ollama_status_user = ctk.CTkLabel(
            self._frame_ollama_user,
            text="* Chạy 100% trên máy tính qua Ollama, miễn phí không giới hạn. Khuyên dùng qwen2.5 để dịch nhanh nhất.",
            font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM
        )
        self._lbl_ollama_status_user.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 8))

        # Subframe cho Cloud Key
        self._frame_cloud_user = ctk.CTkFrame(ai_frame, fg_color="transparent")
        self._frame_cloud_user.grid_columnconfigure(1, weight=1)

        # Thông báo trạng thái AI hệ thống
        if has_shared_ai:
            card_system_ai = ctk.CTkFrame(self._frame_cloud_user, fg_color="#0F291E", corner_radius=8, border_width=1, border_color="#10B981")
            card_system_ai.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            ctk.CTkLabel(
                card_system_ai,
                text="✨ Tài khoản được cấp quyền dùng Cloud AI Máy Chủ Hệ Thống (Bảo mật - Tự động kết nối).",
                font=("Segoe UI", 11, "bold"), text_color="#34D399"
            ).pack(anchor="w", padx=12, pady=8)
            placeholder_text = "🔒 Đang dùng AI hệ thống (Chỉ nhập nếu muốn dùng API Key riêng)..."
        else:
            card_system_ai = ctk.CTkFrame(self._frame_cloud_user, fg_color="#2D1B00", corner_radius=8, border_width=1, border_color="#F59E0B")
            card_system_ai.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            ctk.CTkLabel(
                card_system_ai,
                text="⚠️ Gói cước cần tự túc API Key: Vui lòng nhập API Key cá nhân để sử dụng Cloud AI.",
                font=("Segoe UI", 11, "bold"), text_color="#FBBF24"
            ).pack(anchor="w", padx=12, pady=8)
            placeholder_text = "Dán API Key Gemini / Groq cá nhân của bạn vào đây..."

        self._lbl_key_title_user = ctk.CTkLabel(self._frame_cloud_user, text="API Key Cá Nhân:", font=("Segoe UI", 12), text_color=TEXT_DIM)
        self._lbl_key_title_user.grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)

        row_key_user = ctk.CTkFrame(self._frame_cloud_user, fg_color="transparent")
        row_key_user.grid(row=1, column=1, sticky="ew", pady=6)
        row_key_user.grid_columnconfigure(0, weight=1)

        # KHÔNG nạp token hệ thống vào đây; chỉ nạp user_custom_key nếu chính user tự lưu trước đó
        self._entry_user_gemini = ctk.CTkEntry(
            row_key_user, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER,
            show="*", placeholder_text=placeholder_text
        )
        if user_custom_key:
            self._entry_user_gemini.insert(0, user_custom_key)
        self._entry_user_gemini.grid(row=0, column=0, sticky="ew")

        # TUYỆT ĐỐI KHÔNG để nút con mắt [👁] cho user thường và chặn copy / cut / chuột phải
        def _block_action(e):
            return "break"
        self._entry_user_gemini.bind("<Control-c>", _block_action)
        self._entry_user_gemini.bind("<Control-C>", _block_action)
        self._entry_user_gemini.bind("<<Copy>>", _block_action)
        self._entry_user_gemini.bind("<Control-x>", _block_action)
        self._entry_user_gemini.bind("<Control-X>", _block_action)
        self._entry_user_gemini.bind("<<Cut>>", _block_action)
        self._entry_user_gemini.bind("<Button-3>", _block_action)

        # Model AI (cho Vilao.ai / Groq / Custom)
        ctk.CTkLabel(self._frame_cloud_user, text="Model AI:", font=("Segoe UI", 12), text_color=TEXT_DIM).grid(row=2, column=0, sticky="w", padx=(0, 12), pady=6)
        self._entry_user_model = ctk.CTkEntry(self._frame_cloud_user, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_user_model.insert(0, user_custom_model)
        self._entry_user_model.grid(row=2, column=1, sticky="ew", pady=6)

        self._lbl_cloud_hint_user = ctk.CTkLabel(
            self._frame_cloud_user,
            text="* Hệ thống tự động dịch thuật qua Cloud AI. Tài nguyên máy chủ được mã hóa và bảo mật tối đa.",
            font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM
        )
        self._lbl_cloud_hint_user.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 8))

        # Nút Lưu cấu hình
        btn_save_key = ctk.CTkButton(
            ai_frame, text="💾 Lưu Cấu Hình AI", width=150, height=36, font=("Segoe UI", 12, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._save_user_gemini_key
        )
        btn_save_key.grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 16), sticky="w")

        self._on_provider_change_user(default_choice)

        self._build_drive_settings()

    def _build_drive_settings(self):
        ctk.CTkLabel(
            self, text="☁️  Google Drive Backup",
            font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN,
        ).grid(row=5, column=0, sticky="w", pady=(24, 8))

        drive_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        drive_frame.grid(row=6, column=0, sticky="ew")
        drive_frame.grid_columnconfigure(1, weight=1)

        from config.settings import GOOGLE_DRIVE_CONFIG
        
        # Checkbox Tự động Backup
        self._var_auto_backup = ctk.BooleanVar(value=GOOGLE_DRIVE_CONFIG.get("auto_backup", False))
        ctk.CTkCheckBox(
            drive_frame, text="Tự động Upload video lên Google Drive sau khi xử lý/crawl",
            font=("Segoe UI", 13), variable=self._var_auto_backup,
            command=self._save_drive_settings
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w")
        
        # Checkbox Xóa file gốc
        self._var_delete_local = ctk.BooleanVar(value=GOOGLE_DRIVE_CONFIG.get("delete_local_after_backup", False))
        ctk.CTkCheckBox(
            drive_frame, text="Xóa file video ở máy sau khi Upload Drive thành công (Tiết kiệm dung lượng)",
            font=("Segoe UI", 13), variable=self._var_delete_local, text_color=WARNING,
            command=self._save_drive_settings
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="w")

        # Nút xác thực
        btn_auth = ctk.CTkButton(
            drive_frame, text="🔑 Xác thực Google Drive", width=150, font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._auth_google_drive
        )
        btn_auth.grid(row=0, column=2, rowspan=2, padx=(0, 16), pady=16)

    def _save_drive_settings(self):
        # Update in-memory config for now
        from config.settings import GOOGLE_DRIVE_CONFIG, BASE_DIR
        GOOGLE_DRIVE_CONFIG["auto_backup"] = self._var_auto_backup.get()
        GOOGLE_DRIVE_CONFIG["delete_local_after_backup"] = self._var_delete_local.get()
        
        # Write to .env
        import os
        from dotenv import set_key
        env_path = BASE_DIR / ".env"
        set_key(env_path, "DRIVE_AUTO_BACKUP", str(self._var_auto_backup.get()))
        set_key(env_path, "DRIVE_DELETE_LOCAL", str(self._var_delete_local.get()))
        os.environ["DRIVE_AUTO_BACKUP"] = str(self._var_auto_backup.get())
        os.environ["DRIVE_DELETE_LOCAL"] = str(self._var_delete_local.get())
        
    def _auth_google_drive(self):
        def _do_auth():
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            username = username.replace("@", "_").replace(".", "_")
            try:
                from uploader.google_drive_uploader import GoogleDriveUploader
                uploader = GoogleDriveUploader(username)
                uploader.authenticate()
                
                # Cập nhật UI
                def update_ui():
                    messagebox.showinfo("Thành công", f"Đã xác thực Google Drive cho tài khoản {username}!")
                    if hasattr(self, "lbl_auth_status_admin"):
                        self.lbl_auth_status_admin.configure(text="✅ Đã liên kết", text_color=SUCCESS)
                
                self.app.after(0, update_ui)
            except Exception as e:
                self.app.after(0, lambda: messagebox.showerror("Lỗi xác thực", str(e)))
        
        import threading
        threading.Thread(target=_do_auth, daemon=True).start()


    def _on_provider_change_user(self, choice):
        if "Chỉ dùng Ollama" in choice:
            self._frame_cloud_user.grid_forget()
            self._frame_ollama_user.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
        elif "Chỉ dùng Cloud" in choice:
            self._frame_ollama_user.grid_forget()
            self._frame_cloud_user.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
            self._lbl_key_title_user.configure(text="API Key Cá Nhân:")
            self._lbl_cloud_hint_user.configure(text="* Tự động dịch thuật qua Cloud AI máy chủ hệ thống.")
        elif "Cloud API trước" in choice:
            self._frame_cloud_user.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 6))
            self._frame_ollama_user.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
            self._lbl_key_title_user.configure(text="API Key Cá Nhân:")
            self._lbl_cloud_hint_user.configure(text="* [ƯU TIÊN #1: CLOUD AI] Tự động dịch qua Cloud Server. Nếu lỗi/mất mạng sẽ chuyển qua Ollama Local.")
        else: # Ollama trước ➔ Dự phòng Cloud API
            self._frame_ollama_user.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 6))
            self._frame_cloud_user.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
            self._lbl_key_title_user.configure(text="API Key Cá Nhân:")
            self._lbl_cloud_hint_user.configure(text="* [ƯU TIÊN #1: OLLAMA LOCAL] Chạy máy tính trước. Nếu Ollama lỗi sẽ chuyển qua Cloud Server dự phòng.")

    def _test_ollama_user(self):
        url = self._entry_ollama_url_user.get().strip() or "http://localhost:11434"
        self._lbl_ollama_status_user.configure(text="⏳ Đang kiểm tra kết nối tới Ollama...", text_color=TEXT_DIM)
        
        def _test():
            from auth_client import auth_client
            ok, res = auth_client.test_ollama_connection(url)
            def _update():
                if ok:
                    models = res
                    if models:
                        self._combo_ollama_model_user.configure(values=models)
                        curr = self._combo_ollama_model_user.get().strip()
                        if curr not in models:
                            self._combo_ollama_model_user.set(models[0])
                        self._lbl_ollama_status_user.configure(
                            text=f"✅ Đã kết nối Ollama! Tìm thấy {len(models)} model ({', '.join(models[:4])})",
                            text_color=SUCCESS
                        )
                    else:
                        self._lbl_ollama_status_user.configure(
                            text="✅ Kết nối thành công, nhưng chưa có model nào tải xong trong Ollama.",
                            text_color=WARNING
                        )
                else:
                    self._lbl_ollama_status_user.configure(
                        text=f"❌ Lỗi: {res[:50]}. Hãy kiểm tra app Ollama đang bật!",
                        text_color=DANGER
                    )
            self.after(0, _update)
            
        import threading
        threading.Thread(target=_test, daemon=True).start()

    def _save_user_gemini_key(self):
        choice = getattr(self, "_opt_provider_user", None)
        provider_choice = choice.get() if choice else "Ollama trước ➔ Dự phòng Cloud API"
        
        if "Ollama trước" in provider_choice:
            provider = "ollama_first"
        elif "Cloud API trước" in provider_choice:
            provider = "cloud_first"
        elif "Chỉ dùng Cloud" in provider_choice:
            provider = "cloud_only"
        elif "Chỉ dùng Ollama" in provider_choice:
            provider = "ollama_only"
        elif "Ollama" in provider_choice:
            provider = "ollama_first"
        else:
            provider = "cloud_first"
        ollama_url = getattr(self, "_entry_ollama_url_user", ctk.CTkEntry(self)).get().strip() or "http://localhost:11434"
        ollama_model = getattr(self, "_combo_ollama_model_user", ctk.CTkComboBox(self)).get().strip() or "qwen2.5"
        gemini_key = self._entry_user_gemini.get().strip() if hasattr(self, "_entry_user_gemini") else ""
        custom_model = self._entry_user_model.get().strip() if hasattr(self, "_entry_user_model") else "gemini-3.6-flash-high"
        
        from config.settings import BASE_DIR, PROCESSOR_CONFIG, COOKIES_DIR
        from auth_client import auth_client
        import os
        import json

        # CHỈ ADMIN mới có quyền ghi đè file .env của hệ thống
        if auth_client.is_admin():
            from dotenv import set_key
            env_path = BASE_DIR / ".env"
            set_key(env_path, "AI_PROVIDER", provider)
            set_key(env_path, "OLLAMA_URL", ollama_url)
            set_key(env_path, "OLLAMA_MODEL", ollama_model)
            os.environ["AI_PROVIDER"] = provider
            os.environ["OLLAMA_URL"] = ollama_url
            os.environ["OLLAMA_MODEL"] = ollama_model
            if gemini_key:
                set_key(env_path, "GEMINI_API_KEY", gemini_key)
                os.environ["GEMINI_API_KEY"] = gemini_key
            if custom_model:
                set_key(env_path, "CUSTOM_AI_MODEL", custom_model)
                os.environ["CUSTOM_AI_MODEL"] = custom_model

        # Cập nhật runtime cho phiên làm việc
        PROCESSOR_CONFIG["ai_provider"] = provider
        PROCESSOR_CONFIG["ollama_url"] = ollama_url
        PROCESSOR_CONFIG["ollama_model"] = ollama_model
        if custom_model:
            PROCESSOR_CONFIG["custom_ai_model"] = custom_model
            
        if gemini_key:
            PROCESSOR_CONFIG["gemini_api_keys"] = [k.strip() for k in gemini_key.split(",") if k.strip()]
        else:
            # Nếu user không dùng key riêng, nạp key hệ thống nội bộ từ env (không lộ ra UI)
            raw_env = os.getenv("GEMINI_API_KEY", "")
            PROCESSOR_CONFIG["gemini_api_keys"] = [k.strip() for k in raw_env.split(",") if k.strip()]

        # Lưu riêng vào settings.json của user
        try:
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            user_clean = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / user_clean
            user_dir.mkdir(parents=True, exist_ok=True)
            user_settings_path = user_dir / "settings.json"
            
            user_data = {}
            if user_settings_path.exists():
                try:
                    with open(user_settings_path, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                except:
                    pass
                    
            user_data["ai_provider"] = provider
            user_data["ollama_url"] = ollama_url
            user_data["ollama_model"] = ollama_model
            if gemini_key:
                user_data["gemini_api_key"] = gemini_key
            elif "gemini_api_key" in user_data:
                del user_data["gemini_api_key"] # User xóa key để dùng lại key hệ thống
                
            if custom_model:
                user_data["custom_ai_model"] = custom_model
                
            with open(user_settings_path, "w", encoding="utf-8") as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
        messagebox.showinfo(
            "Đã lưu",
            f"Đã lưu cấu hình AI ({provider_choice}). Bạn có thể sử dụng tính năng Auto-Vietsub & Thuyết minh!"
        )
        self.app._update_user_ui()

    def _toggle_settings_help(self):
        if hasattr(self, "_help_frame") and self._help_frame.winfo_ismapped():
            self._help_frame.grid_remove()
            if hasattr(self, "_btn_help_settings"):
                self._btn_help_settings.configure(fg_color="transparent", border_width=1, border_color=BORDER)
        else:
            if hasattr(self, "_help_frame"):
                self._help_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
                if hasattr(self, "_btn_help_settings"):
                    self._btn_help_settings.configure(fg_color="#1E3A8A", border_width=1, border_color="#38BDF8")

    def _show_payment_dialog(self):
        from auth_client import auth_client
        success, payment_info = auth_client.get_payment_info()
        if not success or not payment_info.get("bank_bin"):
            messagebox.showerror("Lỗi", "Hệ thống chưa cấu hình thanh toán. Vui lòng liên hệ Admin!")
            return
            
        win = ctk.CTkToplevel(self)
        win.title("💎 Nâng Cấp VIP - Thanh Toán Tự Động VietQR")
        
        # Căn giữa cửa sổ popup trên màn hình
        win_w, win_h = 560, 780
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2 - 25)
        win.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        win.minsize(520, 680)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.configure(fg_color=BG_DARK)
        
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)
        
        # ─── 1. Header VIP ──────────────────────────────────────────────────────────
        header_f = ctk.CTkFrame(scroll, fg_color="transparent")
        header_f.pack(fill="x", pady=(0, 14))
        
        badge_f = ctk.CTkFrame(header_f, fg_color=ACCENT_BG, border_width=1, border_color=ACCENT, corner_radius=12)
        badge_f.pack(anchor="center", pady=(0, 6))
        ctk.CTkLabel(badge_f, text="👑  BẢN QUYỀN CAO CẤP VIP  👑", font=("Segoe UI", 11, "bold"), text_color=ACCENT_LIGHT).pack(padx=14, pady=3)
        
        ctk.CTkLabel(header_f, text="Nâng Cấp & Gia Hạn Bản Quyền", font=("Segoe UI", 20, "bold"), text_color=TEXT_MAIN).pack(anchor="center")
        ctk.CTkLabel(header_f, text="Quét mã VietQR bằng app ngân hàng để kích hoạt tự động tức thì (3 - 5s)", font=("Segoe UI", 12), text_color=TEXT_DIM).pack(anchor="center", pady=(2, 0))

        username = auth_client.user_info.get("username", "Unknown") if auth_client.user_info else "Unknown"
        prefix = payment_info.get("payment_prefix", "DOUYIN")
        
        # ─── 2. Package Selector Card ────────────────────────────────────────────────
        pkg_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        pkg_card.pack(fill="x", pady=(0, 12), padx=4)
        
        ctk.CTkLabel(pkg_card, text="📦  CHỌN GÓI DỊCH VỤ:", font=("Segoe UI", 12, "bold"), text_color=CYAN).pack(anchor="w", padx=16, pady=(12, 6))
        
        packages = payment_info.get("packages", [])
        # Lọc bỏ các gói dùng thử / miễn phí (FREE, TRIAL hoặc giá <= 0đ) vì đây là popup quét QR thanh toán có phí
        paid_packages = [
            p for p in packages 
            if str(p.get("code", "")).strip().upper() not in ("FREE", "TRIAL") and int(p.get("price", 0)) > 0
        ]
        if not paid_packages:
            paid_packages = [p for p in packages if int(p.get("price", 0)) > 0]
            
        if not paid_packages:
            paid_packages = [
                {"code": "1M", "name": "1 Tháng (30 ngày)", "price": int(payment_info.get("price_1_month", "69000"))},
                {"code": "3M", "name": "3 Tháng (90 ngày)", "price": int(payment_info.get("price_3_months", "200000"))},
                {"code": "6M", "name": "6 Tháng (180 ngày)", "price": int(payment_info.get("price_6_months", "450000"))},
                {"code": "1Y", "name": "1 Năm (365 ngày)", "price": int(payment_info.get("price_1_year", "1000000"))},
                {"code": "LT", "name": "Vĩnh viễn (10 Năm)", "price": int(payment_info.get("price_lifetime", "4000000"))}
            ]
            
        price_map = {}
        pkg_detail_map = {}
        for p in paid_packages:
            can_ai = bool(p.get("can_use_ai", True))
            ai_tag = "  [✨ Sẵn API AI]" if can_ai else "  [⚠️ Tự túc API Key]"
            label = f"{p['name']}  —  {int(p['price']):,} đ{ai_tag}"
            price_map[label] = (int(p["price"]), p["code"])
            pkg_detail_map[label] = p
            
        options = list(price_map.keys())

        # Dropdown chọn gói
        opt_plan = ctk.CTkOptionMenu(
            pkg_card, values=options, 
            height=38, font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, button_color=ACCENT_HOVER, button_hover_color="#6D28D9",
            dropdown_font=("Segoe UI", 12)
        )
        opt_plan.pack(fill="x", padx=16, pady=(0, 10))

        # Khung thông tin chi tiết quyền lợi & lưu ý AI API của gói được chọn
        detail_frame = ctk.CTkFrame(pkg_card, fg_color="#101726", corner_radius=10, border_width=1, border_color="#1E293B")
        detail_frame.pack(fill="x", padx=16, pady=(0, 14))

        meta_row = ctk.CTkFrame(detail_frame, fg_color="transparent")
        meta_row.pack(fill="x", padx=12, pady=(10, 4))
        
        lbl_pkg_days = ctk.CTkLabel(meta_row, text="⏳ Thời hạn: 30 ngày", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN)
        lbl_pkg_days.pack(side="left", padx=(0, 16))
        
        lbl_pkg_quota = ctk.CTkLabel(meta_row, text="🚀 Hạn mức: Không giới hạn", font=("Segoe UI", 11, "bold"), text_color=CYAN)
        lbl_pkg_quota.pack(side="left")

        ai_note_card = ctk.CTkFrame(detail_frame, fg_color="#064E3B", corner_radius=8, border_width=1, border_color="#059669")
        ai_note_card.pack(fill="x", padx=12, pady=(4, 10))

        lbl_ai_note_title = ctk.CTkLabel(ai_note_card, text="✨ BAO GỒM API AI DÙNG CHUNG", font=("Segoe UI", 11, "bold"), text_color="#6EE7B7", anchor="w")
        lbl_ai_note_title.pack(fill="x", padx=10, pady=(6, 2))

        lbl_ai_note_desc = ctk.CTkLabel(
            ai_note_card,
            text="Đã tích hợp sẵn API Key máy chủ. Dịch Vietsub & lồng tiếng AI sẵn sàng sử dụng ngay mà không cần cấu hình thêm.",
            font=("Segoe UI", 10), text_color="#D1FAE5", justify="left", wraplength=480, anchor="w"
        )
        lbl_ai_note_desc.pack(fill="x", padx=10, pady=(0, 6))
        
        # ─── 3. VietQR Card ──────────────────────────────────────────────────────────
        qr_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        qr_card.pack(fill="x", pady=(0, 12), padx=4)
        
        ctk.CTkLabel(qr_card, text="⚡  QUÉT MÃ VIETQR QUA APP NGÂN HÀNG:", font=("Segoe UI", 12, "bold"), text_color=WARNING).pack(anchor="center", pady=(12, 8))
        
        # Khung nền trắng cho ảnh QR code để app quét cực nhanh và chuẩn nét
        qr_white_box = ctk.CTkFrame(qr_card, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#E2E8F0")
        qr_white_box.pack(anchor="center", padx=20, pady=(0, 8))
        
        lbl_qr = ctk.CTkLabel(qr_white_box, text="⚡ Đang tạo mã VietQR...", font=("Segoe UI", 13), text_color="#334155")
        lbl_qr.pack(padx=14, pady=14)
        
        bank_name = payment_info.get("bank_name", "NGUYEN MINH HOAN")
        bank_account = payment_info.get("bank_account", "")
        bank_bin = payment_info.get("bank_bin", "")
        
        lbl_owner = ctk.CTkLabel(qr_card, text=f"Chủ tài khoản: {bank_name.upper()}", font=("Segoe UI", 13, "bold"), text_color=TEXT_MAIN)
        lbl_owner.pack(anchor="center", pady=(0, 10))

        # ─── 4. Manual Banking Info Card with 1-Click Copy ─────────────────────────
        info_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        info_card.pack(fill="x", pady=(0, 12), padx=4)
        
        ctk.CTkLabel(info_card, text="📝  THÔNG TIN CHUYỂN KHOẢN THỦ CÔNG:", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=16, pady=(12, 6))
        
        def _copy_val(val_str, btn):
            try:
                win.clipboard_clear()
                win.clipboard_append(str(val_str))
                win.update()
                orig = btn.cget("text")
                btn.configure(text="✓ Đã chép", fg_color=SUCCESS)
                win.after(1400, lambda: btn.configure(text=orig, fg_color=ACCENT))
            except Exception:
                pass
                
        def make_row(parent, label_text, val_text, is_highlight=False):
            rf = ctk.CTkFrame(parent, fg_color="#182032" if is_highlight else "transparent", corner_radius=8)
            rf.pack(fill="x", padx=14, pady=3)
            
            ctk.CTkLabel(rf, text=label_text, width=105, anchor="w", font=("Segoe UI", 12), text_color=TEXT_MUTED).pack(side="left", padx=8, pady=6)
            
            val_color = SUCCESS if is_highlight else TEXT_MAIN
            val_lbl = ctk.CTkLabel(rf, text=val_text, anchor="w", font=("Segoe UI", 13, "bold" if is_highlight else "normal"), text_color=val_color)
            val_lbl.pack(side="left", fill="x", expand=True, padx=4)
            
            btn_cp = ctk.CTkButton(rf, text="📋 Chép", width=64, height=28, font=("Segoe UI", 11, "bold"),
                                   fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=6)
            btn_cp.configure(command=lambda: _copy_val(val_lbl.cget("text"), btn_cp))
            btn_cp.pack(side="right", padx=6, pady=4)
            return val_lbl, btn_cp
            
        make_row(info_card, "Ngân hàng:", "MB Bank (Napas 247)")
        lbl_acc, _ = make_row(info_card, "Số tài khoản:", str(bank_account))
        lbl_amount, _ = make_row(info_card, "Số tiền:", "0 đ")
        lbl_syntax_val, btn_cp_syntax = make_row(info_card, "Nội dung CK:", f"{prefix} {username.upper()}", is_highlight=True)

        # ─── 5. Status & Notice ─────────────────────────────────────────────────────
        status_card = ctk.CTkFrame(scroll, fg_color="#0D2818", corner_radius=10, border_width=1, border_color="#10B981")
        status_card.pack(fill="x", pady=(0, 10), padx=4)
        
        stat_f = ctk.CTkFrame(status_card, fg_color="transparent")
        stat_f.pack(fill="x", padx=14, pady=10)
        
        ctk.CTkLabel(stat_f, text="●", font=("Segoe UI", 14, "bold"), text_color=SUCCESS).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(stat_f, text="Đang lắng nghe giao dịch... Hệ thống sẽ tự động kích hoạt ngay sau khi nhận tiền.",
                     font=("Segoe UI", 11, "bold"), text_color=SUCCESS, anchor="w").pack(side="left")
                     
        ctk.CTkLabel(
            scroll, text="⚠️ Lưu ý quan trọng: Vui lòng ghi ĐÚNG NỘI DUNG CHUYỂN KHOẢN để được tự động cộng hạn dùng trong 3-5 giây.",
            font=("Segoe UI", 11, "bold"), text_color=DANGER, wraplength=500, justify="center"
        ).pack(pady=(0, 6))
        
        supp_text = payment_info.get("system_announcement") or "Mọi thắc mắc vui lòng liên hệ Admin qua Zalo/Tele: 0866655803 (@hoannm)"
        ctk.CTkLabel(scroll, text=f"💬 {supp_text}", font=("Segoe UI", 11, "italic"), text_color=TEXT_MUTED, wraplength=500, justify="center").pack(pady=(0, 12))

        # ─── 6. Logic Update QR & Plan ──────────────────────────────────────────────
        def _update_qr(selected_plan):
            amount, package_code = price_map[selected_plan]
            lbl_amount.configure(text=f"{amount:,} đ")
            
            p_data = pkg_detail_map.get(selected_plan, {})
            days_val = p_data.get("days", 30)
            max_daily = p_data.get("max_daily_videos", 9999)
            can_ai = p_data.get("can_use_ai", True)

            lbl_pkg_days.configure(text=f"⏳ Thời hạn: {days_val} ngày")
            if max_daily >= 9999:
                lbl_pkg_quota.configure(text="🚀 Hạn mức: Không giới hạn video/ngày", text_color=SUCCESS)
            else:
                lbl_pkg_quota.configure(text=f"📊 Hạn mức: Tối đa {max_daily} video/ngày", text_color=CYAN)

            if can_ai:
                ai_note_card.configure(fg_color="#064E3B", border_color="#059669")
                lbl_ai_note_title.configure(text="✨ BAO GỒM API AI DÙNG CHUNG TỪ MÁY CHỦ", text_color="#6EE7B7")
                lbl_ai_note_desc.configure(
                    text="Gói này đã tích hợp sẵn API Key máy chủ. Dịch phụ đề Vietsub và lồng tiếng AI sẵn sàng sử dụng ngay mà không cần cấu hình thêm.",
                    text_color="#D1FAE5"
                )
            else:
                ai_note_card.configure(fg_color="#451A03", border_color="#D97706")
                lbl_ai_note_title.configure(text="⚠️ LƯU Ý: GÓI TỰ TÚC API KEY (KHÔNG DÙNG API CHUNG)", text_color="#FDE68A")
                lbl_ai_note_desc.configure(
                    text="Gói này KHÔNG bao gồm API Key AI dùng chung từ máy chủ. Khách hàng chỉ cần nhập Gemini API Key cá nhân miễn phí (tạo tại aistudio.google.com) hoặc Groq/Ollama tại tab [Cài Đặt] để sử dụng các tính năng AI.",
                    text_color="#FEF3C7"
                )

            # Cập nhật lại nội dung chuyển khoản chứa Mã gói
            new_syntax = f"{prefix} {username.upper()} {package_code}"
            lbl_syntax_val.configure(text=new_syntax)
            
            qr_url = f"https://img.vietqr.io/image/{bank_bin}-{bank_account}-compact2.png?amount={amount}&addInfo={new_syntax.replace(' ', '%20')}"
            
            lbl_qr.configure(image=None, text="⚡ Đang tạo mã VietQR...")
            
            def fetch_qr():
                import urllib.request
                import io
                from PIL import Image
                try:
                    req = urllib.request.Request(qr_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=8) as u:
                        raw_data = u.read()
                    img = Image.open(io.BytesIO(raw_data))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(240, 290))
                    if win.winfo_exists():
                        def _set_img():
                            lbl_qr.configure(image=ctk_img, text="")
                            lbl_qr._ctk_img = ctk_img
                        win.after(0, _set_img)
                except Exception as e:
                    if win.winfo_exists():
                        win.after(0, lambda: lbl_qr.configure(text=f"Lỗi tải QR: {e}", image=None))
            
            import threading
            threading.Thread(target=fetch_qr, daemon=True).start()

        opt_plan.configure(command=_update_qr)
        opt_plan.set(options[0])
        
        # Load default QR
        _update_qr(options[0])

        # ─── 7. Auto Payment Verification Loop (Real-time 2s) ───────────────────────
        original_expire = auth_client.user_info.get("expire_date") if auth_client.user_info else None
        original_role = auth_client.user_info.get("role") if auth_client.user_info else None
        original_plan = auth_client.user_info.get("plan_name") if auth_client.user_info else None
        check_job = None
        
        def _check_payment():
            nonlocal check_job
            if not win.winfo_exists():
                return
            try:
                success, data = auth_client.get_me()
                if success and data:
                    new_expire = data.get("expire_date")
                    new_role = data.get("role")
                    new_plan = data.get("plan_name")
                    is_upgraded = (
                        (new_expire and new_expire != original_expire) or
                        (new_role == "vip" and original_role != "vip") or
                        (new_plan and str(new_plan).lower() != "free" and str(original_plan).lower() == "free")
                    )
                    if is_upgraded:
                        try:
                            auth_client.mark_user_paid(username=username)
                        except Exception:
                            pass
                        messagebox.showinfo(
                            "🎉 Nâng Cấp Thành Công",
                            f"Chúc mừng bạn!\nTài khoản '{username}' đã được kích hoạt VIP thành công.\n"
                            f"Gói: {new_plan}\nHạn dùng đến: {new_expire}\n\n"
                            "Toàn bộ tính năng không giới hạn render video đã sẵn sàng!"
                        )
                        win.destroy()
                        if hasattr(self, "app") and hasattr(self.app, "_update_user_ui"):
                            self.app._update_user_ui()
                        elif hasattr(self, "_update_user_ui"):
                            self._update_user_ui()
                        return
            except Exception:
                pass
            check_job = win.after(2000, _check_payment)
            
        check_job = win.after(2000, _check_payment)
        
        def _on_close():
            if check_job:
                win.after_cancel(check_job)
            win.destroy()
            
        win.protocol("WM_DELETE_WINDOW", _on_close)
        
        ctk.CTkButton(
            scroll, text="✕  Đóng Cửa Sổ", command=_on_close, 
            width=160, height=36, font=("Segoe UI", 12, "bold"),
            fg_color=BG_CARD, hover_color="#222B42", border_width=1, border_color=BORDER
        ).pack(pady=(2, 16))

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
        self.tab_sys.grid_rowconfigure(0, weight=1)
        self.tab_users = self.tabview.add("Người dùng")
        self.tab_users.grid_columnconfigure(0, weight=1)
        self.tab_devices = self.tabview.add("Thiết bị (HWID)")
        self.tab_devices.grid_columnconfigure(0, weight=1)
        self.tab_stats = self.tabview.add("Thống kê")
        self.tab_stats.grid_columnconfigure(0, weight=1)
        self.tab_payment = self.tabview.add("Ngân hàng")
        self.tab_payment.grid_columnconfigure(0, weight=1)
        self.tab_packages = self.tabview.add("Quản lý Gói")
        self.tab_packages.grid_columnconfigure(0, weight=1)
        self.tab_noti = self.tabview.add("Thông báo")
        self.tab_noti.grid_columnconfigure(0, weight=1)
        self.tab_logs = self.tabview.add("Hoạt động")
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_feedbacks = self.tabview.add("Đánh giá & Góp ý")
        self.tab_feedbacks.grid_columnconfigure(0, weight=1)
        
        self._build_admin_system(self.tab_sys)
        self._build_admin_users(self.tab_users)
        self._build_admin_devices(self.tab_devices)
        self._build_admin_stats(self.tab_stats)
        self._build_admin_payment(self.tab_payment)
        self._build_admin_packages(self.tab_packages)
        self._build_admin_noti(self.tab_noti)
        self._build_admin_logs(self.tab_logs)
        self._build_admin_feedbacks(self.tab_feedbacks)

        def _on_admin_tab_change():
            curr = self.tabview.get()
            if curr == "Hoạt động" and hasattr(self, "_fetch_admin_logs"):
                self._fetch_admin_logs()
            elif curr == "Người dùng":
                self._load_users()
            elif curr == "Thiết bị (HWID)" and hasattr(self, "_load_admin_devices"):
                self._load_admin_devices()
            elif curr == "Đánh giá & Góp ý" and hasattr(self, "_fetch_admin_feedbacks"):
                self._fetch_admin_feedbacks()
        self.tabview.configure(command=_on_admin_tab_change)

    def _build_admin_system(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        # ── Cookies section ──────────────────────────────────────────────────
        self._section(scroll, "🍪  Cookies", row=0)
        cook = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12,
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

        # ── AI Provider section ──────────────────────────────────────────────
        self._section(scroll, "🧠  AI Dịch thuật & Phụ đề (AI Provider)", row=2)
        ai = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12,
                           border_width=1, border_color=BORDER)
        ai.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        ai.grid_columnconfigure(1, weight=1)

        import os
        from dotenv import load_dotenv
        load_dotenv()
        current_provider = (PROCESSOR_CONFIG.get("ai_provider") or os.getenv("AI_PROVIDER", "cloud_first")).lower()
        existing_key = os.getenv("GEMINI_API_KEY", "")
        if not existing_key and PROCESSOR_CONFIG.get("gemini_api_keys"):
            existing_key = ",".join(PROCESSOR_CONFIG["gemini_api_keys"])
        ollama_url_val = os.getenv("OLLAMA_URL", "http://localhost:11434")
        ollama_model_val = os.getenv("OLLAMA_MODEL", "qwen2.5")

        # Row 0: Chọn Nhà Cung Cấp
        ctk.CTkLabel(ai, text="Nhà cung cấp AI:", font=("Segoe UI", 12, "bold"),
                     text_color=TEXT_MAIN).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))
        
        provider_options = [
            "Ollama trước ➔ Dự phòng Cloud API",
            "Cloud API trước ➔ Dự phòng Ollama",
            "Chỉ dùng Cloud API (Vilao / Gemini / Groq)",
            "Chỉ dùng Ollama (Offline)"
        ]
        if current_provider == "ollama_first":
            default_choice = "Ollama trước ➔ Dự phòng Cloud API"
        elif current_provider == "cloud_first":
            default_choice = "Cloud API trước ➔ Dự phòng Ollama"
        elif current_provider == "cloud_only":
            default_choice = "Chỉ dùng Cloud API (Vilao / Gemini / Groq)"
        elif current_provider == "ollama_only":
            default_choice = "Chỉ dùng Ollama (Offline)"
        elif current_provider in ("gemini", "groq", "vilao"):
            default_choice = "Cloud API trước ➔ Dự phòng Ollama"
        elif current_provider == "ollama":
            default_choice = "Ollama trước ➔ Dự phòng Cloud API" if existing_key else "Chỉ dùng Ollama (Offline)"
        else:
            default_choice = "Cloud API trước ➔ Dự phòng Ollama"

        self._opt_provider_admin = ctk.CTkOptionMenu(
            ai, values=provider_options, font=("Segoe UI", 12),
            fg_color=BG_DARK, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=self._on_provider_change_admin
        )
        self._opt_provider_admin.set(default_choice)
        self._opt_provider_admin.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(14, 8))

        # ── Frame cho Ollama Local ──
        self._frame_ollama_admin = ctk.CTkFrame(ai, fg_color="transparent")
        self._frame_ollama_admin.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._frame_ollama_admin, text="Ollama Server URL:", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        
        row_url = ctk.CTkFrame(self._frame_ollama_admin, fg_color="transparent")
        row_url.grid(row=0, column=1, sticky="ew", pady=6)
        row_url.grid_columnconfigure(0, weight=1)

        self._entry_ollama_url_admin = ctk.CTkEntry(
            row_url, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER
        )
        self._entry_ollama_url_admin.insert(0, ollama_url_val)
        self._entry_ollama_url_admin.grid(row=0, column=0, sticky="ew")

        btn_test_ollama = ctk.CTkButton(
            row_url, text="🔍 Kiểm tra & Lấy Model", width=160, font=("Segoe UI", 11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._test_ollama_admin
        )
        btn_test_ollama.grid(row=0, column=1, padx=(8, 0))

        ctk.CTkLabel(self._frame_ollama_admin, text="Model Ollama:", font=("Segoe UI", 12),
                     text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)

        model_suggestions = ["qwen2.5", "qwen2.5:7b", "qwen2.5:3b", "qwen3:4b", "qwen:latest"]
        self._combo_ollama_model_admin = ctk.CTkComboBox(
            self._frame_ollama_admin, values=model_suggestions, font=("Consolas", 11),
            fg_color=BG_DARK, border_color=BORDER, dropdown_fg_color=BG_CARD
        )
        self._combo_ollama_model_admin.set(ollama_model_val)
        self._combo_ollama_model_admin.grid(row=1, column=1, sticky="ew", pady=6)

        self._lbl_ollama_status_admin = ctk.CTkLabel(
            self._frame_ollama_admin,
            text="* Chạy 100% trên máy tính qua Ollama, miễn phí không giới hạn. Khuyên dùng qwen2.5 để dịch nhanh nhất.",
            font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM
        )
        self._lbl_ollama_status_admin.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 8))

        # ── Frame cho Cloud Key (Gemini / Groq) ──
        self._frame_cloud_admin = ctk.CTkFrame(ai, fg_color="transparent")
        self._frame_cloud_admin.grid_columnconfigure(1, weight=1)

        self._lbl_key_title_admin = ctk.CTkLabel(
            self._frame_cloud_admin, text="API Key:", font=("Segoe UI", 12), text_color=TEXT_DIM
        )
        self._lbl_key_title_admin.grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)

        row_key = ctk.CTkFrame(self._frame_cloud_admin, fg_color="transparent")
        row_key.grid(row=0, column=1, sticky="ew", pady=6)
        row_key.grid_columnconfigure(0, weight=1)

        self._entry_gemini = ctk.CTkEntry(
            row_key, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER, show="*"
        )
        if existing_key:
            self._entry_gemini.insert(0, existing_key)
        self._entry_gemini.grid(row=0, column=0, sticky="ew")

        btn_toggle_key = ctk.CTkButton(
            row_key, text="👁", width=30, height=28, fg_color="transparent", hover_color=BG_CARD, text_color=TEXT_DIM,
            command=lambda: self._entry_gemini.configure(show="" if self._entry_gemini.cget("show") == "*" else "*")
        )
        btn_toggle_key.grid(row=0, column=1, padx=(6, 0))

        # Model AI (cho Vilao.ai / Groq / Custom)
        existing_model = os.getenv("CUSTOM_AI_MODEL", "gemini-3.6-flash-high")
        ctk.CTkLabel(self._frame_cloud_admin, text="Model AI:", font=("Segoe UI", 12), text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        self._entry_admin_model = ctk.CTkEntry(self._frame_cloud_admin, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_admin_model.insert(0, existing_model)
        self._entry_admin_model.grid(row=1, column=1, sticky="ew", pady=6)

        self._lbl_cloud_hint_admin = ctk.CTkLabel(
            self._frame_cloud_admin,
            text="* Hỗ trợ key Gemini / Groq (gsk_) / Vilao.ai (sk-...). Model mặc định: gemini-3.6-flash-high.",
            font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM
        )
        self._lbl_cloud_hint_admin.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 8))

        # Nút Lưu Cấu Hình AI nhanh ngay trong mục AI (không cần cuộn chuột)
        btn_quick_save_ai = ctk.CTkButton(
            ai, text="💾 Lưu Cấu Hình AI", width=160, height=34,
            font=("Segoe UI", 12, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._save
        )
        btn_quick_save_ai.grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 14), sticky="w")

        # Khởi tạo frame tương ứng
        self._on_provider_change_admin(default_choice)

        # ── TikTok section ───────────────────────────────────────────────────
        self._section(scroll, "🎵  TikTok Upload", row=4)
        tt = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12,
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

        # ── Google Drive section ─────────────────────────────────────────────
        self._section(scroll, "☁️  Google Drive Backup", row=6)
        drive_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12,
                                   border_width=1, border_color=BORDER)
        drive_frame.grid(row=7, column=0, sticky="ew", pady=(0, 16))
        drive_frame.grid_columnconfigure(1, weight=1)

        from config.settings import GOOGLE_DRIVE_CONFIG
        
        # Checkbox Tự động Backup
        self._var_auto_backup_admin = ctk.BooleanVar(value=GOOGLE_DRIVE_CONFIG.get("auto_backup", False))
        ctk.CTkCheckBox(
            drive_frame, text="Tự động Upload video lên Google Drive sau khi xử lý/crawl",
            font=("Segoe UI", 13), variable=self._var_auto_backup_admin,
            command=self._save_drive_settings_admin
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="w")
        
        # Checkbox Xóa file gốc
        self._var_delete_local_admin = ctk.BooleanVar(value=GOOGLE_DRIVE_CONFIG.get("delete_local_after_backup", False))
        ctk.CTkCheckBox(
            drive_frame, text="Xóa file video ở máy sau khi Upload Drive thành công",
            font=("Segoe UI", 13), variable=self._var_delete_local_admin, text_color=WARNING,
            command=self._save_drive_settings_admin
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="w")

        # Nút xác thực
        btn_auth = ctk.CTkButton(
            drive_frame, text="🔑 Xác thực Google Drive", width=150, font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._auth_google_drive
        )
        btn_auth.grid(row=0, column=2, padx=(0, 16), pady=(16, 4))
        
        # Trạng thái xác thực
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
        from config.settings import COOKIES_DIR
        token_path = COOKIES_DIR / username / "drive_token.json"
        
        status_text = "✅ Đã liên kết" if token_path.exists() else "❌ Chưa liên kết"
        status_color = SUCCESS if token_path.exists() else WARNING
        
        self.lbl_auth_status_admin = ctk.CTkLabel(
            drive_frame, text=status_text, font=("Segoe UI", 11, "italic"), text_color=status_color
        )
        self.lbl_auth_status_admin.grid(row=1, column=2, padx=(0, 16), pady=(0, 16))

        # Save button
        ctk.CTkButton(
            scroll, text="💾  Lưu cài đặt", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save,
        ).grid(row=8, column=0, sticky="w", pady=(8, 30))

    def _save_drive_settings_admin(self):
        from config.settings import GOOGLE_DRIVE_CONFIG, BASE_DIR
        GOOGLE_DRIVE_CONFIG["auto_backup"] = self._var_auto_backup_admin.get()
        GOOGLE_DRIVE_CONFIG["delete_local_after_backup"] = self._var_delete_local_admin.get()
        
        # Write to .env
        import os
        from dotenv import set_key
        env_path = BASE_DIR / ".env"
        set_key(env_path, "DRIVE_AUTO_BACKUP", str(self._var_auto_backup_admin.get()))
        set_key(env_path, "DRIVE_DELETE_LOCAL", str(self._var_delete_local_admin.get()))
        os.environ["DRIVE_AUTO_BACKUP"] = str(self._var_auto_backup_admin.get())
        os.environ["DRIVE_DELETE_LOCAL"] = str(self._var_delete_local_admin.get())

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

    def _on_provider_change_admin(self, choice):
        if "Chỉ dùng Ollama" in choice:
            self._frame_cloud_admin.grid_forget()
            self._frame_ollama_admin.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
        elif "Chỉ dùng Cloud" in choice:
            self._frame_ollama_admin.grid_forget()
            self._frame_cloud_admin.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
            self._lbl_key_title_admin.configure(text="Cloud API Key:")
            self._lbl_cloud_hint_admin.configure(text="* Hỗ trợ key Gemini / Groq (gsk_) / Vilao.ai (sk-...).")
        elif "Cloud API trước" in choice:
            self._frame_cloud_admin.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 6))
            self._frame_ollama_admin.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
            self._lbl_key_title_admin.configure(text="Cloud API Key:")
            self._lbl_cloud_hint_admin.configure(text="* [ƯU TIÊN #1: CLOUD API] Nếu Cloud API lỗi/hết quota ➔ Tự động chuyển qua Ollama Local dự phòng.")
        else: # Ollama trước ➔ Dự phòng Cloud API
            self._frame_ollama_admin.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 6))
            self._frame_cloud_admin.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 10))
            self._lbl_key_title_admin.configure(text="Cloud API Key:")
            self._lbl_cloud_hint_admin.configure(text="* [ƯU TIÊN #1: OLLAMA LOCAL] Nếu Ollama lỗi/chưa bật ➔ Tự động chuyển qua Cloud API dự phòng.")

    def _test_ollama_admin(self):
        url = self._entry_ollama_url_admin.get().strip() or "http://localhost:11434"
        self._lbl_ollama_status_admin.configure(text="⏳ Đang kiểm tra kết nối tới Ollama...", text_color=TEXT_DIM)
        
        def _test():
            from auth_client import auth_client
            ok, res = auth_client.test_ollama_connection(url)
            def _update():
                if ok:
                    models = res
                    if models:
                        self._combo_ollama_model_admin.configure(values=models)
                        curr = self._combo_ollama_model_admin.get().strip()
                        if curr not in models:
                            self._combo_ollama_model_admin.set(models[0])
                        self._lbl_ollama_status_admin.configure(
                            text=f"✅ Đã kết nối Ollama! Tìm thấy {len(models)} model ({', '.join(models[:4])})",
                            text_color=SUCCESS
                        )
                    else:
                        self._lbl_ollama_status_admin.configure(
                            text="✅ Kết nối thành công, nhưng chưa có model nào tải xong trong Ollama.",
                            text_color=WARNING
                        )
                else:
                    self._lbl_ollama_status_admin.configure(
                        text=f"❌ Lỗi: {res[:50]}. Hãy kiểm tra app Ollama đang bật!",
                        text_color=DANGER
                    )
            self.after(0, _update)
            
        import threading
        threading.Thread(target=_test, daemon=True).start()

    def _save(self):
        choice = getattr(self, "_opt_provider_admin", None)
        provider_choice = choice.get() if choice else "Ollama trước ➔ Dự phòng Cloud API"
        
        if "Ollama trước" in provider_choice:
            provider = "ollama_first"
        elif "Cloud API trước" in provider_choice:
            provider = "cloud_first"
        elif "Chỉ dùng Cloud" in provider_choice:
            provider = "cloud_only"
        elif "Chỉ dùng Ollama" in provider_choice:
            provider = "ollama_only"
        elif "Ollama" in provider_choice:
            provider = "ollama_first"
        else:
            provider = "cloud_first"
        ollama_url = getattr(self, "_entry_ollama_url_admin", ctk.CTkEntry(self)).get().strip() or "http://localhost:11434"
        ollama_model = getattr(self, "_combo_ollama_model_admin", ctk.CTkComboBox(self)).get().strip() or "qwen2.5"
        gemini_key = self._entry_gemini.get().strip() if hasattr(self, "_entry_gemini") else ""
        vbee_key = getattr(self, "_entry_vbee", ctk.CTkEntry(self)).get().strip()
        
        from config.settings import BASE_DIR, PROCESSOR_CONFIG, COOKIES_DIR
        env_path = BASE_DIR / ".env"
        from dotenv import set_key
        import os
        
        set_key(env_path, "AI_PROVIDER", provider)
        set_key(env_path, "OLLAMA_URL", ollama_url)
        set_key(env_path, "OLLAMA_MODEL", ollama_model)
        os.environ["AI_PROVIDER"] = provider
        os.environ["OLLAMA_URL"] = ollama_url
        os.environ["OLLAMA_MODEL"] = ollama_model
        
        PROCESSOR_CONFIG["ai_provider"] = provider
        PROCESSOR_CONFIG["ollama_url"] = ollama_url
        PROCESSOR_CONFIG["ollama_model"] = ollama_model
        
        if gemini_key:
            set_key(env_path, "GEMINI_API_KEY", gemini_key)
            os.environ["GEMINI_API_KEY"] = gemini_key
            PROCESSOR_CONFIG["gemini_api_keys"] = [k.strip() for k in gemini_key.split(",") if k.strip()]
        if vbee_key:
            set_key(env_path, "VBEE_API_KEY", vbee_key)

        custom_model = self._entry_admin_model.get().strip() if hasattr(self, "_entry_admin_model") else "gemini-3.6-flash-high"
        if custom_model:
            set_key(env_path, "CUSTOM_AI_MODEL", custom_model)
            os.environ["CUSTOM_AI_MODEL"] = custom_model
            PROCESSOR_CONFIG["custom_ai_model"] = custom_model

        # Lưu cả vào settings.json của current user
        try:
            from auth_client import auth_client
            import json
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            user_clean = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / user_clean
            user_dir.mkdir(parents=True, exist_ok=True)
            user_settings_path = user_dir / "settings.json"
            
            user_data = {}
            if user_settings_path.exists():
                try:
                    with open(user_settings_path, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                except:
                    pass
                    
            user_data["ai_provider"] = provider
            user_data["ollama_url"] = ollama_url
            user_data["ollama_model"] = ollama_model
            if gemini_key:
                user_data["gemini_api_key"] = gemini_key
            if custom_model:
                user_data["custom_ai_model"] = custom_model
                
            with open(user_settings_path, "w", encoding="utf-8") as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
        messagebox.showinfo(
            "Đã lưu",
            f"Cấu hình AI ({provider_choice}) đã được lưu thành công!\n"
            "(Cài đặt sẽ có hiệu lực ngay trong lần dịch tiếp theo.)"
        )
        self.app._update_user_ui()

    # ── ADMIN: User Management ────────────────────────────────────────────────
    def _build_admin_users(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # 1. Top Bar
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="👥 Quản Lý Tài Khoản Người Dùng", font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        self._lbl_users_count = ctk.CTkLabel(title_box, text="Xem thông tin chi tiết, gia hạn ngày và mở khóa thiết bị (HWID)", font=("Segoe UI", 11), text_color=TEXT_MUTED)
        self._lbl_users_count.pack(anchor="w", pady=(1, 0))

        ctk.CTkButton(top_bar, text="➕ Thêm User", width=110, height=32, font=("Segoe UI", 11, "bold"), fg_color=SUCCESS, hover_color="#27ae60", command=self._add_user_dialog).pack(side="right", padx=(6, 0))
        ctk.CTkButton(top_bar, text="🔄 Làm mới", width=95, height=32, font=("Segoe UI", 11, "bold"), fg_color=BORDER, hover_color=BG_CARD, command=self._load_users).pack(side="right")

        # 2. Filter Bar
        filter_bar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        filter_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        fb_inner = ctk.CTkFrame(filter_bar, fg_color="transparent")
        fb_inner.pack(fill="x", padx=12, pady=8)

        self._entry_search_user = ctk.CTkEntry(fb_inner, placeholder_text="🔍 Tìm kiếm theo Username, Role hoặc gói cước...", height=32, font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_search_user.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._opt_filter_user = ctk.CTkOptionMenu(
            fb_inner, values=["Tất cả User", "Active (Hoạt động)", "Hết hạn", "Quản trị viên (Admin)", "Gói Free"],
            width=180, height=32, font=("Segoe UI", 11)
        )
        self._opt_filter_user.set("Tất cả User")
        self._opt_filter_user.pack(side="left")

        # 3. User List Frame (Scrollable)
        self.user_list_frame = ctk.CTkScrollableFrame(parent, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self.user_list_frame.grid(row=2, column=0, sticky="nsew")

        self._cached_users_list = []

        def _on_filter_changed(e=None):
            self._render_filtered_users()

        self._entry_search_user.bind("<KeyRelease>", _on_filter_changed)
        self._opt_filter_user.configure(command=lambda c: self._render_filtered_users())

        # Gọi load user
        self.after(200, self._load_users)

    def _render_filtered_users(self):
        for w in self.user_list_frame.winfo_children():
            try: w.destroy()
            except Exception: pass

        query = self._entry_search_user.get().strip().lower() if hasattr(self, "_entry_search_user") else ""
        filt = self._opt_filter_user.get() if hasattr(self, "_opt_filter_user") else "Tất cả User"

        filtered = []
        for u in getattr(self, "_cached_users_list", []):
            u_name = str(u.get("username", "")).lower()
            role = str(u.get("role", "")).lower()
            plan = str(u.get("plan_name", "")).lower()
            is_exp = u.get("is_expired", True)

            if query and (query not in u_name and query not in role and query not in plan):
                continue

            if filt == "Active (Hoạt động)" and is_exp:
                continue
            elif filt == "Hết hạn" and not is_exp:
                continue
            elif filt == "Quản trị viên (Admin)" and role not in ("admin", "super_admin"):
                continue
            elif filt == "Gói Free" and plan != "free":
                continue

            filtered.append(u)

        if hasattr(self, "_lbl_users_count"):
            tot = len(getattr(self, "_cached_users_list", []))
            self._lbl_users_count.configure(text=f"Hiển thị: {len(filtered)}/{tot} tài khoản • Nhấn vào tài khoản để xem chi tiết thông tin")

        if not filtered:
            empty_box = ctk.CTkFrame(self.user_list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            empty_box.pack(fill="x", pady=20, padx=10)
            ctk.CTkLabel(empty_box, text="📭 Không tìm thấy tài khoản phù hợp.", font=("Segoe UI", 12), text_color=TEXT_MUTED).pack(pady=24)
            return

        for u in filtered:
            card = ctk.CTkFrame(self.user_list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=4, padx=10)

            # Left side
            left_f = ctk.CTkFrame(card, fg_color="transparent")
            left_f.pack(side="left", padx=12, pady=10, fill="x", expand=True)

            role = u.get("role", "user")
            is_adm = role in ("admin", "super_admin")
            is_exp = u.get("is_expired", True)

            # Row 1: Avatar, Username, Badges
            r1 = ctk.CTkFrame(left_f, fg_color="transparent")
            r1.pack(anchor="w")

            u_btn = ctk.CTkButton(
                r1, text=f"👤 {u['username']}", font=("Segoe UI", 13, "bold"),
                fg_color="transparent", hover_color=BG_DARK, text_color="#A78BFA" if is_adm else TEXT_MAIN,
                anchor="w", height=24, command=lambda user_obj=u: self._show_user_detail_dialog(user_obj)
            )
            u_btn.pack(side="left")

            # Role chip
            ctk.CTkLabel(
                r1, text=f" {'👑 Admin' if is_adm else '👤 User'} ",
                font=("Segoe UI", 10, "bold"),
                text_color="#C4B5FD" if is_adm else "#94A3B8",
                fg_color="#312E81" if is_adm else "#1E293B", corner_radius=6
            ).pack(side="left", padx=6)

            # Plan chip
            plan_name = u.get("plan_name", "Free")
            ctk.CTkLabel(
                r1, text=f" 💎 {plan_name} ",
                font=("Segoe UI", 10, "bold"), text_color="#FBBF24",
                fg_color="#3B2A10", corner_radius=6
            ).pack(side="left", padx=(0, 6))

            # Status chip
            stat_str = "Hết hạn" if is_exp else "Active"
            ctk.CTkLabel(
                r1, text=f" {stat_str} ",
                font=("Segoe UI", 10, "bold"),
                text_color=DANGER if is_exp else SUCCESS,
                fg_color=DANGER_BG if is_exp else SUCCESS_BG, corner_radius=6
            ).pack(side="left")

            # Row 2: Sub-info (Expire date, HWID lock status, Created date)
            r2 = ctk.CTkFrame(left_f, fg_color="transparent")
            r2.pack(anchor="w", pady=(4, 0))

            exp_d = u.get('expire_date', 'Chưa có')
            hwid_txt = "🔒 Đã khóa máy" if (u.get("hwid") and "chưa" not in str(u.get("hwid")).lower()) else "🔓 Chưa gán máy"
            sub_info = f"⏳ Hạn: {exp_d}   •   {hwid_txt}   •   📅 Tạo: {u.get('created_at', 'N/A')}"
            ctk.CTkLabel(r2, text=sub_info, font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(side="left")

            # Right action buttons
            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(side="right", padx=12, pady=10)

            ctk.CTkButton(
                btn_box, text="👁️ Chi tiết", width=75, height=28,
                font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=lambda user_obj=u: self._show_user_detail_dialog(user_obj)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                btn_box, text="✏️ Sửa", width=60, height=28,
                font=("Segoe UI", 11), fg_color=BORDER, hover_color=BG_CARD,
                command=lambda user_obj=u: self._edit_user_dialog(user_obj)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                btn_box, text="🗑 Xóa", width=60, height=28,
                font=("Segoe UI", 11), fg_color=DANGER, hover_color="#c0392b",
                command=lambda user_id=u['id']: self._delete_user(user_id)
            ).pack(side="left", padx=3)

    def _load_users(self):
        if getattr(self, "_cached_users_list", None):
            self._render_filtered_users()
        else:
            for w in self.user_list_frame.winfo_children():
                try: w.destroy()
                except Exception: pass
            ctk.CTkLabel(self.user_list_frame, text="⏳ Đang tải danh sách tài khoản...", text_color=TEXT_MUTED).pack(pady=20)

        def _worker():
            from auth_client import auth_client
            success, users = auth_client.admin_get_users()
            def _done():
                if not success:
                    for w in self.user_list_frame.winfo_children():
                        try: w.destroy()
                        except Exception: pass
                    ctk.CTkLabel(self.user_list_frame, text=f"Lỗi tải danh sách: {users}", text_color=DANGER).pack(pady=20)
                    return
                self._cached_users_list = users if isinstance(users, list) else []
                self._render_filtered_users()

            try:
                if self.winfo_exists():
                    self.after(0, _done)
            except Exception:
                pass

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _add_user_dialog(self):
        self._user_form_dialog()
        
    def _edit_user_dialog(self, user):
        self._user_form_dialog(user)
        
    def _user_form_dialog(self, user=None):
        win = ctk.CTkToplevel(self)
        title = "Sửa Tài khoản" if user else "Thêm Tài khoản"
        win.title(title)
        win.geometry("400x480")
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
        
        from auth_client import auth_client
        import json
        success, configs = auth_client.admin_get_config()
        if not success: configs = {}
        
        raw_pkgs = configs.get("packages", "")
        packages = []
        if raw_pkgs:
            try: packages = json.loads(raw_pkgs)
            except: pass
            
        duration_map = {}
        for p in packages:
            duration_map[f"{p['name']} ({p['days']} ngày)"] = int(p["days"])
            
        if not duration_map:
            duration_map = {
                "Gia hạn 1 Tháng (30 ngày)": 30,
                "Gia hạn 3 Tháng (90 ngày)": 90,
                "Gia hạn 6 Tháng (180 ngày)": 180,
                "Gia hạn 1 Năm (365 ngày)": 365,
                "Vĩnh viễn (10 Năm)": 3650
            }
            
        if user:
            ctk.CTkLabel(win, text="Chỉ chọn nếu muốn gia hạn thêm:", text_color=TEXT_DIM).pack(pady=(10, 0))
            duration_map["Không gia hạn thêm"] = 0
            
        duration_map["Tuỳ chỉnh số ngày..."] = -1
        
        opt_duration = ctk.CTkOptionMenu(win, values=list(duration_map.keys()), width=250)
        if user: opt_duration.set("Không gia hạn thêm")
        else: opt_duration.set(list(duration_map.keys())[0])
        opt_duration.pack(pady=5)
        
        custom_days_frame = ctk.CTkFrame(win, fg_color="transparent")
        ctk.CTkLabel(custom_days_frame, text="Số ngày:").pack(side="left")
        entry_custom_days = ctk.CTkEntry(custom_days_frame, width=100)
        entry_custom_days.pack(side="left", padx=5)
        entry_custom_days.insert(0, "1")
        
        def on_duration_change(choice):
            if duration_map[choice] == -1:
                custom_days_frame.pack(pady=5)
            else:
                custom_days_frame.pack_forget()
                
        opt_duration.configure(command=on_duration_change)
        
        def _save():
            u_name = entry_user.get()
            u_pass = entry_pass.get()
            u_role = opt_role.get()
            days = duration_map[opt_duration.get()]
            
            if days == -1:
                try:
                    days = int(entry_custom_days.get())
                except:
                    messagebox.showerror("Lỗi", "Số ngày tuỳ chỉnh phải là số!")
                    return
            
            if not user:
                if not u_name or not u_pass:
                    messagebox.showerror("Lỗi", "Username và Password là bắt buộc")
                    return
                success, msg = auth_client.admin_create_user(u_name, u_pass, u_role, days_to_add=days)
            else:
                success, msg = auth_client.admin_update_user(user["id"], password=u_pass if u_pass else None, role=u_role, days_to_add=days if days > 0 else None)
                
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

    def _show_user_detail_dialog(self, user_or_username):
        """Hiển thị popup xem đầy đủ thông tin chi tiết của tài khoản người dùng."""
        root_win = self.winfo_toplevel()
        dlg = ctk.CTkToplevel(root_win)
        dlg.title("👤 Chi Tiết Tài Khoản Người Dùng")
        dlg.geometry("580x660")
        dlg.minsize(540, 560)
        dlg.configure(fg_color=BG_DARK)
        dlg.transient(root_win)
        dlg.grab_set()

        try:
            rx = root_win.winfo_rootx()
            ry = root_win.winfo_rooty()
            rw = root_win.winfo_width()
            rh = root_win.winfo_height()
            x = rx + max(0, (rw - 580) // 2)
            y = ry + max(0, (rh - 660) // 2)
            dlg.geometry(f"580x660+{x}+{y}")
        except Exception:
            pass

        target_user = None
        if isinstance(user_or_username, dict):
            target_user = dict(user_or_username)
        else:
            u_name = str(user_or_username).strip().lower()
            cached = getattr(self, "_cached_users_list", [])
            for u in cached:
                if str(u.get("username", "")).lower() == u_name:
                    target_user = dict(u)
                    break
            if not target_user:
                from auth_client import auth_client
                succ, u_list = auth_client.admin_get_users()
                if succ and isinstance(u_list, list):
                    self._cached_users_list = u_list
                    for u in u_list:
                        if str(u.get("username", "")).lower() == u_name:
                            target_user = dict(u)
                            break

        # Tự động đồng bộ thêm id, hwid, created_at nếu bị thiếu (ví dụ truyền từ Feedback/Logs/Sidebar)
        u_name = str(target_user.get("username", "") if target_user else user_or_username).strip().lower()
        if target_user and (not target_user.get("id") or not target_user.get("created_at") or target_user.get("hwid") in (None, "Chưa có dữ liệu")):
            cached = getattr(self, "_cached_users_list", [])
            found_c = False
            for u in cached:
                if str(u.get("username", "")).lower() == u_name:
                    target_user = {**u, **target_user}
                    found_c = True
                    break
            if not found_c or not target_user.get("id"):
                from auth_client import auth_client
                succ, u_list = auth_client.admin_get_users()
                if succ and isinstance(u_list, list):
                    self._cached_users_list = u_list
                    for u in u_list:
                        if str(u.get("username", "")).lower() == u_name:
                            target_user = {**u, **target_user}
                            break

        if not target_user:
            target_user = {
                "id": None,
                "username": str(user_or_username),
                "role": "user",
                "plan_name": "Free",
                "expire_date": "Chưa có",
                "is_expired": True,
                "hwid": "Chưa có dữ liệu",
                "created_at": "Không xác định",
                "max_daily_videos": 5,
                "can_use_ai_script": False
            }

        # 1. Header Card
        hdr_card = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        hdr_card.pack(fill="x", padx=20, pady=(16, 10))

        h_row = ctk.CTkFrame(hdr_card, fg_color="transparent")
        h_row.pack(fill="x", padx=16, pady=12)

        avatar_box = ctk.CTkFrame(h_row, width=48, height=48, corner_radius=12, fg_color="#1E1B4B", border_width=1, border_color="#6366F1")
        avatar_box.pack(side="left", padx=(0, 12))
        avatar_box.pack_propagate(False)
        ctk.CTkLabel(avatar_box, text="👤", font=("Segoe UI", 22)).place(relx=0.5, rely=0.5, anchor="center")

        t_box = ctk.CTkFrame(h_row, fg_color="transparent")
        t_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(t_box, text=target_user.get("username", "Unknown"), font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(anchor="w")

        b_row = ctk.CTkFrame(t_box, fg_color="transparent")
        b_row.pack(anchor="w", pady=(4, 0))

        role_str = target_user.get("role", "user")
        is_admin_user = role_str in ("admin", "super_admin")
        ctk.CTkLabel(
            b_row, text=f" {'👑 Quản trị viên' if is_admin_user else '👤 Người dùng'} ",
            font=("Segoe UI", 10, "bold"), text_color="#C4B5FD" if is_admin_user else "#94A3B8",
            fg_color="#312E81" if is_admin_user else "#1E293B", corner_radius=6
        ).pack(side="left", padx=(0, 6))

        plan_display = target_user.get("plan_name", "Free")
        ctk.CTkLabel(
            b_row, text=f" 💎 Gói {plan_display} ",
            font=("Segoe UI", 10, "bold"), text_color="#FBBF24",
            fg_color="#3B2A10", corner_radius=6
        ).pack(side="left", padx=(0, 6))

        exp_raw = target_user.get("expire_date", "Chưa có")
        is_exp = target_user.get("is_expired", False)
        if exp_raw == "Chưa có":
            stat_lbl = "⚠️ Chưa kích hoạt ngày"
            stat_color = WARNING
            stat_bg = "#451A03"
            exp_display = "Chưa kích hoạt (Bấm gia hạn bên dưới)"
            exp_col = WARNING
        elif is_exp:
            stat_lbl = "❌ Đã hết hạn"
            stat_color = DANGER
            stat_bg = DANGER_BG
            exp_display = exp_raw
            exp_col = DANGER
        else:
            stat_lbl = "✅ Đang hoạt động"
            stat_color = SUCCESS
            stat_bg = SUCCESS_BG
            exp_display = exp_raw
            exp_col = SUCCESS

        ctk.CTkLabel(
            b_row, text=f" {stat_lbl} ",
            font=("Segoe UI", 10, "bold"), text_color=stat_color,
            fg_color=stat_bg, corner_radius=6
        ).pack(side="left")

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        def _info_row(parent, label, value, val_color=TEXT_MAIN):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(r, text=label, font=("Segoe UI", 11), text_color=TEXT_MUTED, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=str(value), font=("Segoe UI", 11, "bold"), text_color=val_color, anchor="w").pack(side="left", fill="x", expand=True)

        # 2. Box Bản Quyền & Gói Cước
        p_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        p_card.pack(fill="x", pady=(0, 10))

        p_hdr = ctk.CTkFrame(p_card, fg_color="transparent")
        p_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(p_hdr, text="💎 Bản Quyền & Hạn Mức", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(side="left")

        # Tra cứu hạn mức và quyền AI chuẩn xác theo cấu hình Packages hiện tại
        max_vids = target_user.get("max_daily_videos")
        can_ai = target_user.get("can_use_ai_script")
        if max_vids is None or can_ai is None or max_vids == 5:
            cached_pkgs = getattr(self, "_cached_packages_list", None)
            if not cached_pkgs:
                try:
                    from auth_client import auth_client
                    _, cfg = auth_client.admin_get_config()
                    if cfg and "packages" in cfg:
                        import json
                        cached_pkgs = json.loads(cfg["packages"]) if isinstance(cfg["packages"], str) else cfg["packages"]
                        self._cached_packages_list = cached_pkgs
                except Exception:
                    cached_pkgs = []
            if cached_pkgs:
                for p in cached_pkgs:
                    p_code = str(p.get("code", "")).strip().upper()
                    p_name = str(p.get("name", "")).strip().upper()
                    target_plan_upper = str(plan_display).strip().upper()
                    if p_code == target_plan_upper or p_name == target_plan_upper or (target_plan_upper == "FREE" and p_code == "FREE"):
                        if max_vids is None or max_vids == 5:
                            max_vids = int(p.get("max_daily_videos", 8))
                        if can_ai is None:
                            can_ai = bool(p.get("can_use_ai", True))
                        break

        if max_vids is None:
            max_vids = 8 if str(plan_display).lower() == "free" else 9999
        if can_ai is None:
            can_ai = True

        _info_row(p_card, "Gói kích hoạt:", f"Gói {plan_display}", "#FBBF24")
        _info_row(p_card, "Hạn sử dụng:", exp_display, exp_col)
        _info_row(p_card, "Hạn mức xử lý:", f"{max_vids} video/ngày" if max_vids < 9999 else "Không giới hạn (VIP)")
        _info_row(p_card, "Tính năng AI Voice/Sub:", "✅ Được cấp quyền AI Cloud" if can_ai else "⚠️ Tự túc API Key", SUCCESS if can_ai else WARNING)

        # Thanh nút gia hạn nhanh ngày sử dụng
        quick_ext_lbl = ctk.CTkLabel(p_card, text="⚡ Gia hạn nhanh ngày sử dụng:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED)
        quick_ext_lbl.pack(anchor="w", padx=14, pady=(6, 4))
        quick_ext_row = ctk.CTkFrame(p_card, fg_color="transparent")
        quick_ext_row.pack(fill="x", padx=14, pady=(0, 10))

        def _do_quick_extend(days, label_desc):
            u_id = target_user.get("id")
            if not u_id:
                messagebox.showerror("Lỗi", "Không tìm thấy User ID để gia hạn.")
                return
            if messagebox.askyesno("Xác nhận", f"Gia hạn thêm {label_desc} cho user '{target_user.get('username')}'?"):
                from auth_client import auth_client
                succ, msg = auth_client.admin_update_user(u_id, days_to_add=days)
                if succ:
                    messagebox.showinfo("Thành công", f"Đã gia hạn thành công {label_desc} cho tài khoản {target_user.get('username')}!")
                    dlg.destroy()
                    self._load_users()
                else:
                    messagebox.showerror("Lỗi", msg)

        # Danh sách nút gia hạn nhanh (có thêm +10 Ngày Free)
        for days_val, btn_lbl in [(10, "+10 Ngày Free"), (30, "+30 Ngày"), (90, "+90 Ngày"), (365, "+1 Năm"), (3650, "+Vĩnh Viễn")]:
            ctk.CTkButton(
                quick_ext_row, text=btn_lbl, width=86, height=26,
                font=("Segoe UI", 10, "bold"), fg_color="#1E293B", hover_color=ACCENT, corner_radius=6,
                command=lambda d=days_val, l=btn_lbl: _do_quick_extend(d, l)
            ).pack(side="left", padx=2)

        # 3. Box Thiết Bị & Bảo Mật (HWID Lock)
        dev_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        dev_card.pack(fill="x", pady=(0, 10))

        dev_hdr = ctk.CTkFrame(dev_card, fg_color="transparent")
        dev_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(dev_hdr, text="🔒 Thiết Bị & Khóa Máy (HWID Lock)", font=("Segoe UI", 12, "bold"), text_color=CYAN).pack(side="left")

        hwid_val = str(target_user.get("hwid") or "Chưa gán máy")
        is_locked = bool(hwid_val and "chưa" not in hwid_val.lower() and "không" not in hwid_val.lower())
        
        # Row HWID with Copy button
        hw_r = ctk.CTkFrame(dev_card, fg_color="transparent")
        hw_r.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(hw_r, text="Mã phần cứng (HWID):", font=("Segoe UI", 11), text_color=TEXT_MUTED, width=150, anchor="w").pack(side="left")
        ctk.CTkLabel(hw_r, text=hwid_val, font=("Consolas", 11, "bold"), text_color="#38BDF8" if is_locked else TEXT_DIM, anchor="w").pack(side="left", fill="x", expand=True)
        
        if is_locked:
            def _copy_hwid():
                dlg.clipboard_clear()
                dlg.clipboard_append(hwid_val)
                btn_copy_hw.configure(text="✅ Đã chép!")
                dlg.after(1500, lambda: btn_copy_hw.configure(text="📋 Copy"))
            btn_copy_hw = ctk.CTkButton(hw_r, text="📋 Copy", width=60, height=22, font=("Segoe UI", 10), fg_color=BORDER, hover_color=BG_DARK, command=_copy_hwid)
            btn_copy_hw.pack(side="right")

        _info_row(dev_card, "Trạng thái thiết bị:", "🔒 Đã khóa trên máy này" if is_locked else "🔓 Chưa gán máy (Đăng nhập máy bất kỳ)", SUCCESS if is_locked else WARNING)
        _info_row(dev_card, "Ngày đăng ký / tạo:", target_user.get("created_at", "Không xác định"), TEXT_DIM)

        hwid_btn_row = ctk.CTkFrame(dev_card, fg_color="transparent")
        hwid_btn_row.pack(fill="x", padx=14, pady=(6, 10))

        def _do_reset_hwid():
            u_id = target_user.get("id")
            if not u_id:
                messagebox.showerror("Lỗi", "Không tìm thấy User ID để reset.")
                return
            u_name_val = target_user.get("username", "")
            if messagebox.askyesno("Xác nhận", f"Mở khóa thiết bị cho user '{u_name_val}'?\nUser sẽ có thể đăng nhập trên máy tính mới."):
                from auth_client import auth_client
                succ, msg = auth_client.admin_reset_hwid(u_id, username=u_name_val)
                if succ:
                    messagebox.showinfo("Thành công", msg)
                    dlg.destroy()
                    self._load_users()
                else:
                    messagebox.showerror("Lỗi Reset HWID", msg)

        ctk.CTkButton(
            hwid_btn_row, text="🔓 Mở Khóa Đổi Máy (Reset HWID)", width=230, height=30,
            font=("Segoe UI", 11, "bold"), fg_color="#0F2937", hover_color="#0369A1",
            text_color="#38BDF8", border_width=1, border_color="#0EA5E9",
            command=_do_reset_hwid
        ).pack(side="left")

        # 4. Box Hoạt Động Gần Đây
        act_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        act_card.pack(fill="x", pady=(0, 10))

        act_hdr = ctk.CTkFrame(act_card, fg_color="transparent")
        act_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(act_hdr, text="⚡ Hoạt Động Gần Đây", font=("Segoe UI", 12, "bold"), text_color="#67E8F9").pack(side="left")

        def _view_all_logs_of_user():
            dlg.destroy()
            if hasattr(self, "tabview"):
                self.tabview.set("Hoạt động")
            if hasattr(self, "_filter_logs_by_user"):
                self._filter_logs_by_user(target_user.get("username", ""))

        btn_view_logs = ctk.CTkButton(
            act_hdr, text="📜 Xem toàn bộ logs", width=125, height=24,
            font=("Segoe UI", 10, "bold"), fg_color="#0F2937", hover_color="#0369A1",
            text_color="#38BDF8", border_width=1, border_color="#0EA5E9",
            command=_view_all_logs_of_user
        )
        btn_view_logs.pack(side="right")

        from auth_client import auth_client
        _, logs_data = auth_client.admin_get_logs(limit=500)
        u_logs = [
            l for l in (logs_data if isinstance(logs_data, list) else [])
            if str(l.get("username", "")).lower() == u_name or f"'{u_name}'" in str(l.get("details", "")).lower() or f" {u_name} " in f" {str(l.get('details', '')).lower()} "
        ][:5]

        if not u_logs:
            ctk.CTkLabel(
                act_card,
                text="ℹ️ Chưa ghi nhận hoạt động nào (Tài khoản này chưa từng đăng nhập vào app GUI hoặc chưa có thao tác Crawl / Process / Upload nào).",
                font=("Segoe UI", 11, "italic"), text_color=TEXT_MUTED, justify="left", wraplength=480
            ).pack(padx=14, pady=(0, 10), anchor="w")
        else:
            for l in u_logs:
                l_box = ctk.CTkFrame(act_card, fg_color=BG_DARK, corner_radius=6)
                l_box.pack(fill="x", padx=14, pady=(0, 6))
                act = str(l.get("action", "INFO")).upper()
                dt = str(l.get("details", "")).replace("\n", " ")[:110]
                is_err = "ERROR" in act or any(w in dt.lower() for w in ["lỗi", "fail", "thất bại", "0 video"])
                if is_err:
                    tag_col = DANGER
                elif act == "UPLOAD":
                    tag_col = SUCCESS
                elif act == "RESET_HWID":
                    tag_col = "#38BDF8"
                else:
                    tag_col = ACCENT_LIGHT
                tag_icon = "🔓 " if act == "RESET_HWID" else "🕒 "
                ctk.CTkLabel(l_box, text=f"{tag_icon}[{l.get('time', '')}] {act}", font=("Consolas", 10, "bold"), text_color=tag_col).pack(anchor="w", padx=8, pady=(4, 1))
                ctk.CTkLabel(l_box, text=dt, font=("Segoe UI", 11), text_color=TEXT_MAIN, wraplength=480, justify="left").pack(anchor="w", padx=8, pady=(0, 5))

        # 5. Box Lịch Sử Góp Ý Của User Này
        fb_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        fb_card.pack(fill="x", pady=(0, 10))

        fb_hdr = ctk.CTkFrame(fb_card, fg_color="transparent")
        fb_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(fb_hdr, text="⭐ Đánh Giá & Góp Ý Từ User Này", font=("Segoe UI", 12, "bold"), text_color="#F59E0B").pack(side="left")

        _, fb_data = auth_client.admin_get_feedbacks()
        all_fbs = fb_data.get("feedbacks", []) if isinstance(fb_data, dict) else []
        u_fbs = [f for f in all_fbs if str(f.get("username", "")).lower() == u_name]

        if not u_fbs:
            ctk.CTkLabel(fb_card, text="Người dùng này chưa gửi đánh giá nào.", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(padx=14, pady=(0, 10), anchor="w")
        else:
            for f in u_fbs[:4]:
                f_box = ctk.CTkFrame(fb_card, fg_color=BG_DARK, corner_radius=6)
                f_box.pack(fill="x", padx=14, pady=(0, 6))
                r = f.get("rating", 5)
                star_s = "★" * r
                ctk.CTkLabel(f_box, text=f"⭐ {star_s} ({f.get('category')}) - 🕒 {f.get('created_at')}", font=("Segoe UI", 10, "bold"), text_color="#FDE68A").pack(anchor="w", padx=8, pady=(4, 2))
                ctk.CTkLabel(f_box, text=f.get("content", ""), font=("Segoe UI", 11), text_color=TEXT_MAIN, wraplength=480, justify="left").pack(anchor="w", padx=8, pady=(0, 6))

        # 6. Bottom Action Buttons
        bottom_bar = ctk.CTkFrame(dlg, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=20, pady=(4, 16))

        def _do_edit_from_detail():
            dlg.destroy()
            self._edit_user_dialog(target_user)

        def _do_del_from_detail():
            u_id = target_user.get("id")
            if u_id:
                dlg.destroy()
                self._delete_user(u_id)

        def _do_quick_change_pass():
            u_id = target_user.get("id")
            if not u_id:
                messagebox.showerror("Lỗi", "Không tìm thấy User ID để đổi mật khẩu.")
                return
            input_dlg = ctk.CTkInputDialog(text=f"Nhập mật khẩu mới cho user '{target_user.get('username')}':", title="🔑 Đổi Mật Khẩu Nhanh")
            new_pass = input_dlg.get_input()
            if new_pass and new_pass.strip():
                succ, msg = auth_client.admin_update_user(u_id, password=new_pass.strip())
                if succ:
                    messagebox.showinfo("Thành công", f"Đã đổi mật khẩu cho user '{target_user.get('username')}' thành công!")
                else:
                    messagebox.showerror("Lỗi", msg)

        ctk.CTkButton(
            bottom_bar, text="✏️ Sửa Nâng Cao", width=125, height=34,
            font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=_do_edit_from_detail
        ).pack(side="left")

        ctk.CTkButton(
            bottom_bar, text="🔑 Đổi Password", width=120, height=34,
            font=("Segoe UI", 11, "bold"), fg_color="#1E293B", hover_color=BG_CARD,
            command=_do_quick_change_pass
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            bottom_bar, text="🗑 Xóa User", width=95, height=34,
            font=("Segoe UI", 11, "bold"), fg_color=DANGER, hover_color="#c0392b",
            command=_do_del_from_detail
        ).pack(side="left")

        ctk.CTkButton(
            bottom_bar, text="✕ Đóng", width=80, height=34,
            font=("Segoe UI", 11), fg_color=BORDER, hover_color=BG_CARD,
            command=dlg.destroy
        ).pack(side="right")

    # ── ADMIN: Device Management (HWID) ───────────────────────────────────────
    def _build_admin_devices(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        # 1. Top Bar
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="💻 Quản Lý Thiết Bị Phần Cứng (HWID Lock)", font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        self._lbl_devices_count = ctk.CTkLabel(title_box, text="Theo dõi máy đã đăng ký, mở khóa cho phép tạo nick mới hoặc chặn thiết bị vi phạm", font=("Segoe UI", 11), text_color=TEXT_MUTED)
        self._lbl_devices_count.pack(anchor="w", pady=(1, 0))

        btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_box.pack(side="right")
        
        def _manual_block_dialog():
            input_dlg = ctk.CTkInputDialog(
                text="Nhập mã HWID (Machine GUID) cần đưa vào Blacklist:",
                title="🚫 Chặn Thiết Bị Thủ Công"
            )
            hw_input = input_dlg.get_input()
            if hw_input and hw_input.strip():
                from auth_client import auth_client
                succ, msg = auth_client.admin_toggle_block_device(hw_input.strip())
                if succ:
                    messagebox.showinfo("Thành công", msg)
                    self._load_admin_devices()
                else:
                    messagebox.showerror("Lỗi", msg)

        ctk.CTkButton(btn_box, text="🚫 Chặn HWID Thủ Công", width=160, height=32, font=("Segoe UI", 11, "bold"),
                      fg_color=DANGER, hover_color="#c0392b", command=_manual_block_dialog).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_box, text="🔄 Làm mới", width=95, height=32, font=("Segoe UI", 11, "bold"),
                      fg_color=BORDER, hover_color=BG_CARD, command=self._load_admin_devices).pack(side="left")

        # 2. Stats Bar
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        def make_stat_card(master, col, title, initial_val, color):
            c = ctk.CTkFrame(master, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            c.grid(row=0, column=col, sticky="ew", padx=4)
            ctk.CTkLabel(c, text=title, font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(pady=(8, 0))
            lbl = ctk.CTkLabel(c, text=initial_val, font=("Segoe UI", 18, "bold"), text_color=color)
            lbl.pack(pady=(0, 8))
            return lbl

        self._stat_devices_total = make_stat_card(stats_frame, 0, "📱 Tổng Thiết Bị Ghi Nhận", "0", TEXT_MAIN)
        self._stat_devices_active = make_stat_card(stats_frame, 1, "🟢 Đang Liên Kết Tài Khoản", "0", SUCCESS)
        self._stat_devices_blocked = make_stat_card(stats_frame, 2, "🚫 Bị Chặn (Blacklist)", "0", DANGER)

        # 3. Filter Bar
        filter_bar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        filter_bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        fb_inner = ctk.CTkFrame(filter_bar, fg_color="transparent")
        fb_inner.pack(fill="x", padx=12, pady=8)

        self._entry_search_device = ctk.CTkEntry(
            fb_inner, placeholder_text="🔍 Tìm kiếm theo Mã máy HWID, Tên tài khoản hoặc Gói...",
            height=32, font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER
        )
        self._entry_search_device.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._opt_filter_device = ctk.CTkOptionMenu(
            fb_inner, values=["Tất cả thiết bị", "🟢 Đang liên kết", "🚫 Bị chặn (Blacklist)"],
            width=200, height=32, font=("Segoe UI", 11)
        )
        self._opt_filter_device.set("Tất cả thiết bị")
        self._opt_filter_device.pack(side="left")

        # 4. Scrollable Frame for Devices List
        self.devices_list_frame = ctk.CTkScrollableFrame(parent, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self.devices_list_frame.grid(row=3, column=0, sticky="nsew")

        self._cached_devices_list = []

        def _on_device_filter_changed(e=None):
            self._render_filtered_devices()

        self._entry_search_device.bind("<KeyRelease>", _on_device_filter_changed)
        self._opt_filter_device.configure(command=lambda c: self._render_filtered_devices())

        # Load devices when user switches to tab (handled by _on_admin_tab_change)

    def _load_admin_devices(self):
        def _fetch():
            try:
                from auth_client import auth_client
                succ, data = auth_client.admin_get_devices()
            except Exception:
                succ, data = False, {}
            devs = data.get("devices", []) if (succ and isinstance(data, dict)) else []
            bl_count = data.get("blacklisted_count", 0) if (succ and isinstance(data, dict)) else 0

            def _apply():
                try:
                    if self.winfo_exists():
                        self._apply_devices_data(devs, bl_count)
                except Exception:
                    pass

            for _ in range(30):
                try:
                    if not self.winfo_exists():
                        return
                    self.after(0, _apply)
                    return
                except (RuntimeError, Exception):
                    import time
                    time.sleep(0.1)

        import threading
        threading.Thread(target=_fetch, daemon=True).start()

    def _apply_devices_data(self, devices, bl_count):
        self._cached_devices_list = devices
        total = len(devices)
        active = sum(1 for d in devices if not d.get("is_blocked"))
        blocked = sum(1 for d in devices if d.get("is_blocked"))

        if hasattr(self, "_stat_devices_total"): self._stat_devices_total.configure(text=str(total))
        if hasattr(self, "_stat_devices_active"): self._stat_devices_active.configure(text=str(active))
        if hasattr(self, "_stat_devices_blocked"): self._stat_devices_blocked.configure(text=str(blocked))
        if hasattr(self, "_lbl_devices_count"): self._lbl_devices_count.configure(text=f"Đang quản lý {total} thiết bị ({active} hoạt động, {blocked} bị chặn)")

        self._render_filtered_devices()

    def _render_filtered_devices(self):
        if not hasattr(self, "devices_list_frame"):
            return
        try:
            if not self.devices_list_frame.winfo_exists():
                return
        except Exception:
            return

        for w in self.devices_list_frame.winfo_children():
            try: w.destroy()
            except Exception: pass

        query = self._entry_search_device.get().strip().lower() if hasattr(self, "_entry_search_device") else ""
        filt = self._opt_filter_device.get() if hasattr(self, "_opt_filter_device") else "Tất cả thiết bị"

        filtered = []
        for d in getattr(self, "_cached_devices_list", []):
            hw = str(d.get("hwid", "")).lower()
            u_name = str(d.get("username", "")).lower()
            plan = str(d.get("plan_name", "")).lower()
            is_bl = d.get("is_blocked", False)

            if query and (query not in hw and query not in u_name and query not in plan):
                continue

            if filt == "🟢 Đang liên kết" and is_bl:
                continue
            if filt == "🚫 Đang bị chặn (Blacklist)" and not is_bl:
                continue

            filtered.append(d)

        if not filtered:
            ctk.CTkLabel(
                self.devices_list_frame, text="Không tìm thấy thiết bị nào phù hợp.",
                font=("Segoe UI", 12, "italic"), text_color=TEXT_MUTED
            ).pack(pady=40)
            return

        for dev in filtered:
            self._render_device_item(dev)

    def _render_device_item(self, dev):
        hwid = dev.get("hwid", "")
        username = dev.get("username", "Unknown")
        user_id = dev.get("user_id")
        plan = dev.get("plan_name", "Free")
        created = dev.get("created_at", "")
        is_blocked = dev.get("is_blocked", False)

        card = ctk.CTkFrame(self.devices_list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color="#EF4444" if is_blocked else BORDER)
        card.pack(fill="x", padx=6, pady=4)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)

        # Icon
        icon_box = ctk.CTkFrame(row, width=42, height=42, fg_color="#1E293B" if not is_blocked else "#4C0519", corner_radius=8)
        icon_box.pack(side="left", padx=(0, 12))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="💻" if not is_blocked else "🚫", font=("Segoe UI", 18)).pack(expand=True)

        # Info Box
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        # HWID line
        hw_row = ctk.CTkFrame(info, fg_color="transparent")
        hw_row.pack(anchor="w", fill="x")

        # Rút gọn HWID để hiển thị đẹp
        hw_short = f"{hwid[:10]}...{hwid[-8:]}" if len(hwid) > 20 else hwid
        ctk.CTkLabel(hw_row, text=f"HWID: {hw_short}", font=("Consolas", 12, "bold"), text_color="#38BDF8").pack(side="left")

        def _copy_hw():
            self.clipboard_clear()
            self.clipboard_append(hwid)
            messagebox.showinfo("Đã sao chép", f"Đã sao chép mã HWID đầy đủ vào Clipboard:\n{hwid}")

        ctk.CTkButton(hw_row, text="📋 Copy", width=55, height=22, font=("Segoe UI", 10), fg_color=BORDER, hover_color="#334155", command=_copy_hw).pack(side="left", padx=(8, 0))

        # Sub line: User, Plan, Created
        sub_row = ctk.CTkFrame(info, fg_color="transparent")
        sub_row.pack(anchor="w", fill="x", pady=(3, 0))

        ctk.CTkLabel(sub_row, text=f"👤 Tài khoản: {username}", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(sub_row, text=f"💎 Gói: {plan}", font=("Segoe UI", 11), text_color="#FBBF24").pack(side="left", padx=(0, 8))
        if created:
            ctk.CTkLabel(sub_row, text=f"🕒 Tạo: {created}", font=("Segoe UI", 10), text_color=TEXT_MUTED).pack(side="left")

        # Right Column: Badge & Actions
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right")

        # Status badge
        badge_text = "🚫 Đang bị chặn (Blacklist)" if is_blocked else "🟢 Đang liên kết"
        badge_color = DANGER if is_blocked else SUCCESS
        badge_bg = "#4C0519" if is_blocked else "#064E3B"
        ctk.CTkLabel(right, text=f" {badge_text} ", font=("Segoe UI", 10, "bold"), text_color=badge_color, fg_color=badge_bg, corner_radius=6).pack(side="left", padx=(0, 10))

        # Nút Mở Khóa Cho Tạo Nick Mới
        def _do_unlock():
            if messagebox.askyesno("Mở Khóa Thiết Bị", f"Mở khóa thiết bị [{hw_short}]?\n\n• Thao tác này sẽ gỡ mã máy khỏi tài khoản '{username}' (nếu có).\n• Máy tính này sẽ có thể đăng ký tài khoản mới hoặc đổi sang máy khác."):
                from auth_client import auth_client
                succ, msg = auth_client.admin_unlock_device(hwid, user_id=user_id, username=username)
                if succ:
                    messagebox.showinfo("Thành công 🎉", msg)
                    self._load_admin_devices()
                else:
                    messagebox.showerror("Lỗi", msg)

        ctk.CTkButton(
            right, text="🔓 Mở Khóa Đổi Máy", width=140, height=30,
            font=("Segoe UI", 11, "bold"), fg_color="#0284C7", hover_color="#0369A1",
            command=_do_unlock
        ).pack(side="left", padx=(0, 6))

        # Nút Chặn / Bỏ Chặn
        def _do_toggle_block():
            prompt_msg = f"Gỡ bỏ chặn cho thiết bị [{hw_short}]?" if is_blocked else f"Chặn thiết bị [{hw_short}] vào Blacklist?\n(Thiết bị này sẽ KHÔNG THỂ tạo bất kỳ tài khoản nào nữa)."
            if messagebox.askyesno("Xác nhận", prompt_msg):
                from auth_client import auth_client
                succ, msg = auth_client.admin_toggle_block_device(hwid)
                if succ:
                    messagebox.showinfo("Thành công", msg)
                    self._load_admin_devices()
                else:
                    messagebox.showerror("Lỗi", msg)

        btn_block_text = "✅ Bỏ Chặn" if is_blocked else "🚫 Chặn Máy"
        btn_block_color = SUCCESS if is_blocked else DANGER
        btn_block_hover = "#059669" if is_blocked else "#b91c1c"

        ctk.CTkButton(
            right, text=btn_block_text, width=95, height=30,
            font=("Segoe UI", 11, "bold"), fg_color=btn_block_color, hover_color=btn_block_hover,
            command=_do_toggle_block
        ).pack(side="left")

    def _build_admin_stats(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        self._section(scroll, "📊 Tổng Quan", row=0)
        
        overview = ctk.CTkFrame(scroll, fg_color="transparent")
        overview.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        overview.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Thẻ thông tin
        def create_card(master, title, value, color, col):
            card = ctk.CTkFrame(master, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
            card.grid(row=0, column=col, sticky="ew", padx=8)
            ctk.CTkLabel(card, text=title, font=("Segoe UI", 12), text_color=TEXT_DIM).pack(pady=(12, 0))
            lbl_val = ctk.CTkLabel(card, text=str(value), font=("Segoe UI", 24, "bold"), text_color=color)
            lbl_val.pack(pady=(0, 12))
            return lbl_val
            
        lbl_total = create_card(overview, "👥 Tổng số User", "...", TEXT_MAIN, 0)
        lbl_active = create_card(overview, "🔥 Đang hoạt động", "...", SUCCESS, 1)
        lbl_revenue = create_card(overview, "💰 Doanh thu", "...", WARNING, 2)
        
        self._section(scroll, "📝 Lịch sử Giao dịch (Gần đây)", row=2)
        
        import tkinter.ttk as ttk
        # Style cho Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background=BG_CARD, 
                        foreground=TEXT_MAIN, 
                        fieldbackground=BG_CARD, 
                        rowheight=30,
                        bordercolor=BORDER,
                        font=("Segoe UI", 11))
        style.map('Treeview', background=[('selected', ACCENT)])
        style.configure("Treeview.Heading", 
                        background=BG_DARK, 
                        foreground=TEXT_MAIN, 
                        font=("Segoe UI", 11, "bold"))
        
        tree_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        tree_frame.grid(row=3, column=0, sticky="nsew", pady=10)
        
        tree = ttk.Treeview(tree_frame, columns=("time", "user", "pkg", "days", "amount", "method"), show="headings", height=15)
        tree.heading("time", text="Thời gian")
        tree.heading("user", text="Tài khoản")
        tree.heading("pkg", text="Mã gói")
        tree.heading("days", text="Ngày thêm")
        tree.heading("amount", text="Số tiền")
        tree.heading("method", text="Hình thức")
        
        tree.column("time", width=140, anchor="center")
        tree.column("user", width=120, anchor="w")
        tree.column("pkg", width=140, anchor="w")
        tree.column("days", width=80, anchor="center")
        tree.column("amount", width=120, anchor="e")
        tree.column("method", width=100, anchor="center")
        
        tree.pack(side="left", fill="both", expand=True)
        
        # Scrollbar cho Treeview
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
        def _load_stats():
            from auth_client import auth_client
            for item in tree.get_children():
                tree.delete(item)
                
            success, data = auth_client.admin_get_stats()
            if success:
                lbl_total.configure(text=str(data.get("total_users", 0)))
                lbl_active.configure(text=str(data.get("active_users", 0)))
                lbl_revenue.configure(text=f"{int(data.get('total_revenue', 0)):,}đ")
                
                for t in data.get("recent_transactions", []):
                    time_str = t.get("created_at", "")[:19].replace("T", " ")
                    amt = f"{int(t.get('amount', 0)):,}đ" if t.get('amount', 0) > 0 else "-"
                    tree.insert("", "end", values=(
                        time_str,
                        t.get("username", ""),
                        t.get("package_name", ""),
                        f"+{t.get('days_added', 0)} ngày",
                        amt,
                        t.get("payment_method", "")
                    ))
            else:
                lbl_total.configure(text="Lỗi")
                
        btn_refresh = ctk.CTkButton(scroll, text="🔄 Làm mới Dữ liệu", width=160, command=_load_stats, fg_color=ACCENT)
        btn_refresh.grid(row=4, column=0, pady=(10, 20), sticky="w")
        
        # Tải lần đầu
        _load_stats()

    def _build_admin_payment(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        self._section(scroll, "🏦  Thông tin Ngân hàng", row=0)
        bank = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        bank.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        bank.grid_columnconfigure(1, weight=1)
        
        from auth_client import auth_client
        success, configs = auth_client.admin_get_config()
        if not success: configs = {}
        
        # Bank Info
        for i, (label, key) in enumerate([
            ("Mã BIN Ngân hàng (VD: 970436)", "bank_bin"),
            ("Số Tài khoản", "bank_account"),
            ("Tên Tài khoản", "bank_name"),
            ("SePay Webhook Token", "webhook_token"),
            ("Tiền tố Chuyển khoản (VD: DOUYIN)", "payment_prefix"),
        ]):
            ctk.CTkLabel(bank, text=label, font=("Segoe UI", 12), text_color=TEXT_DIM).grid(row=i, column=0, sticky="w", padx=16, pady=(14 if i==0 else 4, 4))
            entry = ctk.CTkEntry(bank, width=300, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
            entry.insert(0, configs.get(key, ""))
            entry.grid(row=i, column=1, sticky="w", padx=16, pady=(14 if i==0 else 4, 4))
            setattr(self, f"_entry_{key}", entry)
            
        def _save_payment():
            data = {
                "bank_bin": self._entry_bank_bin.get(),
                "bank_account": self._entry_bank_account.get(),
                "bank_name": self._entry_bank_name.get(),
                "webhook_token": self._entry_webhook_token.get(),
                "payment_prefix": self._entry_payment_prefix.get().upper(),
            }
            succ, msg = auth_client.admin_save_config(data)
            if succ:
                messagebox.showinfo("Thành công", "Đã lưu cấu hình Ngân hàng!")
            else:
                messagebox.showerror("Lỗi", msg)
                
        ctk.CTkButton(scroll, text="💾  Lưu Cấu Hình Ngân Hàng", width=240, command=_save_payment,
                      fg_color=SUCCESS, hover_color="#27ae60",
                      font=("Segoe UI", 13, "bold")).grid(row=4, column=0, pady=(8, 24), sticky="w")

    def _build_admin_packages(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        self._section(scroll, "💰  Quản Lý & Phân Quyền Các Gói Cước (Package Management)", row=0)

        # Hộp hướng dẫn và giải thích cơ chế
        hint_card = ctk.CTkFrame(scroll, fg_color="#0F172A", corner_radius=10, border_width=1, border_color="#1E3A8A")
        hint_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        
        hint_top = ctk.CTkFrame(hint_card, fg_color="transparent")
        hint_top.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(hint_top, text="💡 HƯỚNG DẪN CẤU HÌNH GÓI & PHÂN BỔ TÀI NGUYÊN API CHUNG:", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")
        
        hint_txt = (
            "• Gói FREE (Mặc định): Tự động cấp cho mọi tài khoản mới đăng ký. Tùy chỉnh Số ngày dùng thử và Hạn mức video mỗi ngày.\n"
            "• Các Gói Trả Phí (1M, 3M, 6M, 1Y, LT,...): Tùy chỉnh số ngày, hạn mức video (nhập 9999 để Không giới hạn), giá tiền và quyền AI.\n"
            "• Phân Quyền 'Dùng AI' (Cực kỳ quan trọng):\n"
            "   + TÍCH CHỌN [✔]: Gói được cấp quyền dùng chung API Key AI đám mây của máy chủ (Khách hàng không cần tự cài đặt API key).\n"
            "   + BỎ CHỌN [ ]: Gói 'Tự túc API' - Cắt quyền gọi API chung của máy chủ để tiết kiệm chi phí cho Admin. Khi mua gói này, giao diện VietQR sẽ tự động hiển thị LƯU Ý RÕ RÀNG để khách hàng biết phải tự lấy Gemini API Key miễn phí (hoặc Groq/Ollama) và nhập vào tab [Cài Đặt]."
        )
        ctk.CTkLabel(hint_card, text=hint_txt, font=("Segoe UI", 11), text_color=TEXT_MUTED, justify="left", wraplength=950).pack(anchor="w", padx=14, pady=(0, 10))

        # Khung bảng cấu hình gói
        price = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        price.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        price.grid_columnconfigure(0, weight=1)
        
        from auth_client import auth_client
        import json
        success, configs = auth_client.admin_get_config()
        if not success or not isinstance(configs, dict):
            configs = {}
        
        raw_pkgs = configs.get("packages", "")
        packages = []
        if raw_pkgs:
            try:
                packages = json.loads(raw_pkgs) if isinstance(raw_pkgs, str) else raw_pkgs
            except Exception:
                pass
                
        # Nếu chưa có gói FREE trong danh sách, tự động chèn vào đầu
        has_free = any(str(p.get("code", "")).strip().upper() == "FREE" for p in packages)
        if not packages:
            packages = [
                {"code": "FREE", "name": "Miễn Phí Dùng Thử", "days": 10, "max_daily_videos": 5, "price": 0, "can_use_ai": True},
                {"code": "1M", "name": "1 Tháng (30 ngày)", "days": 30, "max_daily_videos": 50, "price": int(configs.get("price_1_month", "600000")), "can_use_ai": True},
                {"code": "3M", "name": "3 Tháng (90 ngày)", "days": 90, "max_daily_videos": 100, "price": int(configs.get("price_3_months", "1500000")), "can_use_ai": True},
                {"code": "6M", "name": "6 Tháng (180 ngày)", "days": 180, "max_daily_videos": 200, "price": int(configs.get("price_6_months", "2500000")), "can_use_ai": True},
                {"code": "1Y", "name": "1 Năm (365 ngày)", "days": 365, "max_daily_videos": 500, "price": int(configs.get("price_1_year", "4500000")), "can_use_ai": True},
                {"code": "LT", "name": "Vĩnh viễn (10 Năm)", "days": 3650, "max_daily_videos": 99999, "price": int(configs.get("price_lifetime", "10000000")), "can_use_ai": True}
            ]
        elif not has_free:
            packages.insert(0, {"code": "FREE", "name": "Miễn Phí Dùng Thử", "days": 10, "max_daily_videos": 5, "price": 0, "can_use_ai": True})

        self._pkg_rows = []
        pkg_container = ctk.CTkFrame(price, fg_color="transparent")
        pkg_container.pack(fill="x", padx=16, pady=10)
        
        # Tiêu đề bảng
        hdr = ctk.CTkFrame(pkg_container, fg_color="#182032", height=36, corner_radius=6)
        hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(hdr, text="Mã Gói", width=90, anchor="w", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(hdr, text="Tên Hiển Thị Gói", width=180, anchor="w", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(hdr, text="Số Ngày", width=75, anchor="w", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(hdr, text="Video / Ngày", width=95, anchor="w", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(hdr, text="Giá Tiền (VNĐ)", width=120, anchor="w", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(hdr, text="Dùng AI", width=80, anchor="w", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)
        ctk.CTkLabel(hdr, text="Thao Tác", width=70, anchor="center", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=6, pady=6)

        def add_pkg_row(p_code="", p_name="", p_days=0, p_max_daily=5, p_price=0, p_ai=True):
            is_free_pkg = str(p_code).strip().upper() == "FREE"
            row_f = ctk.CTkFrame(pkg_container, fg_color="#101522" if is_free_pkg else "transparent", corner_radius=6)
            row_f.pack(fill="x", pady=3)
            
            e_code = ctk.CTkEntry(row_f, width=90, font=("Consolas", 11, "bold"), fg_color=BG_DARK, border_color=BORDER)
            e_code.insert(0, str(p_code))
            if is_free_pkg:
                e_code.configure(state="disabled")
            e_code.pack(side="left", padx=6, pady=4)
            
            e_name = ctk.CTkEntry(row_f, width=180, font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
            e_name.insert(0, str(p_name))
            e_name.pack(side="left", padx=6, pady=4)
            
            e_days = ctk.CTkEntry(row_f, width=75, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
            e_days.insert(0, str(p_days))
            e_days.pack(side="left", padx=6, pady=4)

            e_max_v = ctk.CTkEntry(row_f, width=95, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
            e_max_v.insert(0, str(p_max_daily))
            e_max_v.pack(side="left", padx=6, pady=4)
            
            e_price = ctk.CTkEntry(row_f, width=120, font=("Consolas", 11), fg_color=BG_DARK, border_color=BORDER)
            e_price.insert(0, str(p_price))
            if is_free_pkg:
                e_price.configure(state="disabled")
            e_price.pack(side="left", padx=6, pady=4)

            var_ai = ctk.BooleanVar(value=bool(p_ai))
            chk_ai = ctk.CTkCheckBox(row_f, text="Cho phép", variable=var_ai, width=80, font=("Segoe UI", 10))
            chk_ai.pack(side="left", padx=6, pady=4)
            
            def remove():
                row_f.destroy()
                if row_data in self._pkg_rows:
                    self._pkg_rows.remove(row_data)
                
            if not is_free_pkg:
                btn_del = ctk.CTkButton(row_f, text="Xoá", width=60, height=26, font=("Segoe UI", 10, "bold"), fg_color=DANGER, hover_color="#c0392b", command=remove)
                btn_del.pack(side="left", padx=6, pady=4)
            else:
                lbl_lock = ctk.CTkLabel(row_f, text="🔒 Cố định", width=60, font=("Segoe UI", 10, "italic"), text_color=TEXT_MUTED)
                lbl_lock.pack(side="left", padx=6, pady=4)
            
            row_data = {
                "code": e_code, "name": e_name, "days": e_days,
                "max_daily_videos": e_max_v, "price": e_price,
                "can_use_ai": var_ai, "is_free": is_free_pkg
            }
            self._pkg_rows.append(row_data)

        for pkg in packages:
            add_pkg_row(
                p_code=pkg.get("code", ""),
                p_name=pkg.get("name", ""),
                p_days=pkg.get("days", 0),
                p_max_daily=pkg.get("max_daily_videos", 5),
                p_price=pkg.get("price", 0),
                p_ai=pkg.get("can_use_ai", True)
            )
            
        btn_add = ctk.CTkButton(
            price, text="➕ Thêm Gói Mới", fg_color=BORDER, hover_color=BG_DARK,
            font=("Segoe UI", 11, "bold"), width=140, height=32,
            command=lambda: add_pkg_row("NEW", "Gói Mới", 30, 50, 500000, True)
        )
        btn_add.pack(anchor="w", padx=16, pady=(4, 16))
        
        # ── Khung cấu hình chống spam HWID ──
        hwid_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        hwid_card.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        hwid_card.grid_columnconfigure(0, weight=1)

        hw_top = ctk.CTkFrame(hwid_card, fg_color="transparent")
        hw_top.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(hw_top, text="🛡️  CẤU HÌNH KHÓA THIẾT BỊ & CHỐNG SPAM (HWID LOCK)", font=("Segoe UI", 12, "bold"), text_color="#38BDF8").pack(side="left")

        hw_val = str(configs.get("enforce_hwid_register", "true")).lower() != "false"
        self._var_enforce_hwid = ctk.BooleanVar(value=hw_val)
        chk_hwid = ctk.CTkCheckBox(
            hwid_card,
            text="Bật chặn thiết bị khi đăng ký Free (Chống spam: Mỗi máy chỉ được đăng ký 1 tài khoản Free)",
            variable=self._var_enforce_hwid,
            font=("Segoe UI", 12, "bold"),
            text_color=TEXT_MAIN,
            fg_color=ACCENT, hover_color=ACCENT_HOVER
        )
        chk_hwid.pack(anchor="w", padx=16, pady=(4, 6))

        ctk.CTkLabel(
            hwid_card,
            text="• BẬT (Khuyến nghị khi mở tool cho khách): Mỗi máy tính chỉ được tự tạo 1 nick Free 10 ngày để tránh bị bào bản quyền.\n"
                 "• TẮT (Khi Admin đang kiểm thử hoặc chạy sự kiện): Cho phép 1 máy có thể tự do bấm Đăng Ký thêm nhiều tài khoản Free liên tiếp.",
            font=("Segoe UI", 11), text_color=TEXT_MUTED, justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 14))

        def _save_packages():
            new_pkgs = []
            for r in getattr(self, "_pkg_rows", []):
                c_val = "FREE" if r.get("is_free") else r["code"].get().strip().upper()
                new_pkgs.append({
                    "code": c_val,
                    "name": r["name"].get().strip(),
                    "days": int(r["days"].get().strip() or 0),
                    "max_daily_videos": int(r["max_daily_videos"].get().strip() or 5),
                    "price": 0 if r.get("is_free") else int(r["price"].get().strip() or 0),
                    "can_use_ai": r["can_use_ai"].get()
                })
            data = {
                "packages": json.dumps(new_pkgs, ensure_ascii=False),
                "enforce_hwid_register": "true" if getattr(self, "_var_enforce_hwid", None) and self._var_enforce_hwid.get() else "false"
            }
            from auth_client import auth_client
            succ, msg = auth_client.admin_save_config(data)
            if succ:
                messagebox.showinfo("Thành công", "Đã lưu cấu hình danh sách Gói Dịch Vụ và Cài đặt Khóa máy thành công!\nHạn mức, quyền hạn và chế độ chống spam đã được đồng bộ.")
            else:
                messagebox.showerror("Lỗi", msg)
                
        ctk.CTkButton(scroll, text="💾  Lưu Cấu Hình Gói & Khóa Máy", width=280, height=38, command=_save_packages,
                      fg_color=SUCCESS, hover_color="#27ae60",
                      font=("Segoe UI", 13, "bold")).grid(row=4, column=0, pady=(8, 24), sticky="w")

    def _build_admin_noti(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        from auth_client import auth_client
        success, configs = auth_client.admin_get_config()
        if not success: configs = {}
        
        self._section(scroll, "📢  Thông Báo & Cập Nhật Phiên Bản", row=0)
        
        noti_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        noti_card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        noti_card.grid_columnconfigure(0, weight=1)
        
        desc_frame = ctk.CTkFrame(noti_card, fg_color="#1e2a3a", corner_radius=8)
        desc_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        desc_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(desc_frame, text="ℹ️  Hướng dẫn sử dụng",
                     font=("Segoe UI", 12, "bold"), text_color=ACCENT,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(desc_frame,
                     text="• Thông báo hệ thống sẽ hiển thị banner vàng trên Dashboard của TẤT CẢ người dùng.\n"
                          "• Phiên bản Tool: Nhập số phiên bản mới nhất (VD: 1.1). Nếu khác phiên bản client,\n"
                          "  banner đỏ ép buộc user tải bản mới sẽ xuất hiện. Để trống = không thông báo update.",
                     font=("Segoe UI", 11), text_color=TEXT_DIM, justify="left", anchor="w",
                     wraplength=700).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))
        
        inner = ctk.CTkFrame(noti_card, fg_color="transparent")
        inner.grid(row=1, column=0, sticky="ew", padx=16, pady=0)
        inner.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(inner, text="📢  Thông báo hệ thống", font=("Segoe UI", 12, "bold"),
                     text_color=WARNING, anchor="w").grid(row=0, column=0, sticky="nw", padx=(0, 16), pady=(8, 0))
        self._entry_system_announcement = ctk.CTkTextbox(inner, height=80, font=("Segoe UI", 12),
                                                          fg_color=BG_DARK, border_color=BORDER,
                                                          border_width=1, corner_radius=8)
        self._entry_system_announcement.grid(row=0, column=1, sticky="ew", pady=8)
        ann_val = configs.get("system_announcement", "")
        if ann_val:
            self._entry_system_announcement.insert("0.0", ann_val)
        
        ctk.CTkLabel(inner, text="🚀  Phiên bản mới nhất", font=("Segoe UI", 12, "bold"),
                     text_color=ACCENT, anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(0, 8))
        ver_frame = ctk.CTkFrame(inner, fg_color="transparent")
        ver_frame.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self._entry_client_version = ctk.CTkEntry(ver_frame, width=140, font=("Consolas", 13, "bold"),
                                                   fg_color=BG_DARK, border_color=ACCENT,
                                                   placeholder_text="VD: 1.1")
        self._entry_client_version.pack(side="left")
        ver_val = configs.get("client_version", "")
        if ver_val:
            self._entry_client_version.insert(0, ver_val)
        ctk.CTkLabel(ver_frame, text="  (Tool client hiện tại: v1.0)",
                     font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left")
        
        def _save_noti():
            announcement_text = self._entry_system_announcement.get("0.0", "end").strip()
            ver_text = self._entry_client_version.get().strip()
            data = {
                "system_announcement": announcement_text,
                "client_version": ver_text,
            }
            from auth_client import auth_client
            succ, msg = auth_client.admin_save_config(data)
            if succ:
                if announcement_text:
                    messagebox.showinfo("Thành công", f"📢 Thông báo đã được gửi tới tất cả người dùng!\n\nNội dung: {announcement_text[:100]}...")
                else:
                    messagebox.showinfo("Thành công", "Đã xóa thông báo hệ thống.")
            else:
                messagebox.showerror("Lỗi", msg)
        
        btn_row = ctk.CTkFrame(noti_card, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="e", padx=16, pady=(4, 16))
        
        ctk.CTkButton(btn_row, text="🗑  Xóa Thông Báo", width=160, command=lambda: (
            self._entry_system_announcement.delete("0.0", "end"),
            _save_noti()
        ), fg_color=BORDER, hover_color=BG_DARK, font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(btn_row, text="📢  Gửi Thông Báo", width=160, command=_save_noti,
                      fg_color=WARNING, hover_color="#d68910", text_color=BG_DARK,
                      font=("Segoe UI", 12, "bold")).pack(side="left")

    def _build_admin_logs(self, parent):
        # ── Biến trạng thái ──
        all_logs_data = []
        filtered_logs_cache = []
        current_page = [1]
        page_size_val = [25]
        selected_log_ref = [None]
        active_row_widget = [None]
        search_timer = [None]
        is_loading = [False]

        def _get_action_style(action, details):
            action_up = str(action).upper()
            dt = str(details).lower()
            is_err = action_up == "ERROR" or any(w in dt for w in ["lỗi", "thất bại", "0 video", "hết hạn", "error", "failed"])
            
            if is_err:
                return f"⚠️ {action_up if action_up != 'INFO' else 'LỖI'}", DANGER_BG, "#FCA5A5", True
            elif action_up == "UPLOAD":
                return "🚀 UPLOAD", SUCCESS_BG, "#6EE7B7", False
            elif action_up == "PROCESS":
                return "🎬 PROCESS", WARNING_BG, "#FDE68A", False
            elif action_up == "CRAWL":
                return "📥 CRAWL", CYAN_BG, "#67E8F9", False
            elif action_up == "LOGIN":
                return "🔑 LOGIN", ACCENT_BG, "#C4B5FD", False
            elif action_up == "RESET_HWID":
                return "🔓 RESET_HWID", "#0C4A6E", "#38BDF8", False
            else:
                return f"ℹ️ {action_up}", "#1E293B", "#CBD5E1", False

        # ── Dialog Popup xem chi tiết log ──
        def _show_log_detail_dialog(log):
            if not log:
                return
            root_win = self.winfo_toplevel()
            dlg = ctk.CTkToplevel(root_win)
            dlg.title(f"Chi tiết Hoạt động - {log.get('username', 'N/A')}")
            w, h = 760, 520
            dlg.minsize(580, 400)
            dlg.transient(root_win)

            try:
                rx = root_win.winfo_rootx()
                ry = root_win.winfo_rooty()
                rw = root_win.winfo_width()
                rh = root_win.winfo_height()
                x = rx + max(0, (rw - w) // 2)
                y = ry + max(0, (rh - h) // 2)
                dlg.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                dlg.geometry(f"{w}x{h}")

            dlg.lift()
            dlg.focus_force()

            hdr_card = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            hdr_card.pack(fill="x", padx=20, pady=(16, 8))

            action = log.get("action", "INFO")
            details_content = str(log.get("details", ""))
            act_text, act_bg, act_fg, is_error = _get_action_style(action, details_content)

            row_title = ctk.CTkFrame(hdr_card, fg_color="transparent")
            row_title.pack(fill="x", padx=16, pady=(12, 6))
            ctk.CTkLabel(row_title, text=f" {act_text} ", font=("Segoe UI", 11, "bold"), text_color=act_fg, fg_color=act_bg, corner_radius=6).pack(side="left")
            ctk.CTkLabel(row_title, text=f"  Nhật ký #{log.get('id', '')} - Người dùng: {log.get('username', 'N/A')}", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=8)

            info_frame = ctk.CTkFrame(hdr_card, fg_color="transparent")
            info_frame.pack(fill="x", padx=16, pady=(0, 12))
            info_frame.grid_columnconfigure(1, weight=1)
            info_frame.grid_columnconfigure(3, weight=1)

            ctk.CTkLabel(info_frame, text="🕒 Thời gian:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", pady=2)
            ctk.CTkLabel(info_frame, text=log.get("time", ""), font=("Consolas", 12), text_color=TEXT_MAIN).grid(row=0, column=1, sticky="w", padx=8, pady=2)

            ctk.CTkLabel(info_frame, text="🌐 Địa chỉ IP:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).grid(row=0, column=2, sticky="w", padx=(15, 0), pady=2)
            ctk.CTkLabel(info_frame, text=log.get("ip_address", "N/A"), font=("Consolas", 12), text_color=TEXT_MAIN).grid(row=0, column=3, sticky="w", padx=8, pady=2)

            ctk.CTkLabel(info_frame, text="👤 Tài khoản:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).grid(row=1, column=0, sticky="w", pady=2)
            u_box = ctk.CTkFrame(info_frame, fg_color="transparent")
            u_box.grid(row=1, column=1, sticky="w", padx=8, pady=2)
            ctk.CTkButton(
                u_box, text=f"👤 {log.get('username', '')} ℹ️", height=24,
                font=("Segoe UI", 11, "bold"), fg_color="#1E1B4B", hover_color="#312E81",
                text_color="#C4B5FD", border_width=1, border_color="#6366F1", corner_radius=6,
                command=lambda u_name=log.get("username"): [dlg.destroy(), self._show_user_detail_dialog(u_name)]
            ).pack(side="left")

            ctk.CTkLabel(info_frame, text="⚡ Trạng thái:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).grid(row=1, column=2, sticky="w", padx=(15, 0), pady=2)
            stat_text = "Phát hiện LỖI / Thất bại" if is_error else "Hoạt động bình thường"
            ctk.CTkLabel(info_frame, text=stat_text, font=("Segoe UI", 11, "bold"), text_color=DANGER if is_error else SUCCESS).grid(row=1, column=3, sticky="w", padx=8, pady=2)

            ctk.CTkLabel(dlg, text="📋 Nội dung chi tiết hoạt động & Thông báo lỗi:", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", padx=20, pady=(4, 6))

            txt_details = ctk.CTkTextbox(dlg, font=("Consolas", 12), fg_color=BG_CARD, border_width=1, border_color="#f38ba8" if is_error else BORDER, wrap="word")
            txt_details.pack(fill="both", expand=True, padx=20, pady=(0, 14))
            txt_details.insert("1.0", details_content)
            txt_details.configure(state="disabled")

            btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
            btn_row.pack(fill="x", padx=20, pady=(0, 16))

            def _copy_details():
                dlg.clipboard_clear()
                copy_text = f"Thời gian: {log.get('time')}\nUser: {log.get('username')}\nAction: {action}\nIP: {log.get('ip_address')}\nTrạng thái: {stat_text}\n\nNội dung chi tiết:\n{details_content}"
                dlg.clipboard_append(copy_text)
                btn_copy.configure(text="✅ Đã sao chép!", fg_color=SUCCESS)
                dlg.after(2000, lambda: btn_copy.configure(text="📋 Sao chép toàn bộ", fg_color=BORDER))

            btn_copy = ctk.CTkButton(btn_row, text="📋 Sao chép toàn bộ", width=160, height=32, font=("Segoe UI", 11, "bold"), fg_color=BORDER, hover_color=BG_CARD, command=_copy_details)
            btn_copy.pack(side="left")

            btn_close = ctk.CTkButton(btn_row, text="✕ Đóng", width=100, height=32, font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=dlg.destroy)
            btn_close.pack(side="right")

        # ── 1. Top Bar: Header & Live Action Buttons ──
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(14, 6))

        title_box = ctk.CTkFrame(top_frame, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(title_box, text="⚡ Nhật Ký Hoạt Động & Live Telemetry", font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Theo dõi sự kiện thời gian thực, giám sát tiến trình người dùng và chẩn đoán sự cố hệ thống", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(anchor="w", pady=(1, 0))

        btn_refresh = ctk.CTkButton(top_frame, text="🔄 Làm mới dữ liệu", width=135, height=32, font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8)
        btn_refresh.pack(side="right")

        # ── 2. KPI Stat Cards (4 Metric Badges) ──
        kpi_frame = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_frame.pack(fill="x", padx=20, pady=(4, 10))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        def _create_kpi_card(col_idx, icon, title, initial_val, text_col, border_glow, click_filter_val=None):
            card = ctk.CTkFrame(kpi_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER, cursor="hand2")
            card.grid(row=0, column=col_idx, sticky="ew", padx=4 if col_idx not in (0, 3) else (0 if col_idx == 0 else 0))
            
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=12, pady=8)
            
            t_box = ctk.CTkFrame(inner, fg_color="transparent")
            t_box.pack(fill="x")
            ctk.CTkLabel(t_box, text=f"{icon}  {title}", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left")
            
            lbl_v = ctk.CTkLabel(inner, text=str(initial_val), font=("Segoe UI", 20, "bold"), text_color=text_col)
            lbl_v.pack(anchor="w", pady=(2, 0))

            def _on_enter(e):
                card.configure(border_color=border_glow, fg_color=BG_CARD_HOVER)
            def _on_leave(e):
                card.configure(border_color=BORDER, fg_color=BG_CARD)
            
            card.bind("<Enter>", _on_enter)
            card.bind("<Leave>", _on_leave)
            lbl_v.bind("<Enter>", _on_enter)
            lbl_v.bind("<Leave>", _on_leave)
            
            if click_filter_val is not None:
                def _on_click(e=None):
                    entry_search.delete(0, "end")
                    opt_user.set("Tất cả User")
                    opt_action.set(click_filter_val)
                    _apply_filter()
                card.bind("<Button-1>", _on_click)
                inner.bind("<Button-1>", _on_click)
                t_box.bind("<Button-1>", _on_click)
                lbl_v.bind("<Button-1>", _on_click)
                
            return lbl_v

        lbl_kpi_total = _create_kpi_card(0, "📊", "Tổng Sự Kiện", "0", ACCENT_LIGHT, ACCENT, "Tất cả Action")
        lbl_kpi_error = _create_kpi_card(1, "⚠️", "Sự Cố & Lỗi", "0", DANGER, DANGER, "⚠️ Chỉ xem LỖI / 0 video")
        lbl_kpi_upload = _create_kpi_card(2, "🚀", "Tải Lên (Upload)", "0", SUCCESS, SUCCESS, "UPLOAD")
        lbl_kpi_process = _create_kpi_card(3, "🎬", "Xử Lý & Cào", "0", CYAN, CYAN, "PROCESS")

        def _update_kpi_metrics():
            tot = len(all_logs_data)
            err_cnt = 0
            up_cnt = 0
            proc_cnt = 0
            for l in all_logs_data:
                act = str(l.get("action", "")).upper()
                dt = str(l.get("details", "")).lower()
                if act == "ERROR" or any(w in dt for w in ["lỗi", "thất bại", "0 video", "hết hạn", "error", "failed"]):
                    err_cnt += 1
                if act == "UPLOAD":
                    up_cnt += 1
                elif act in ("PROCESS", "CRAWL"):
                    proc_cnt += 1
            lbl_kpi_total.configure(text=str(tot))
            lbl_kpi_error.configure(text=str(err_cnt))
            lbl_kpi_upload.configure(text=str(up_cnt))
            lbl_kpi_process.configure(text=str(proc_cnt))

        # ── 3. Toolbar Lọc & Tìm Kiếm ──
        filter_bar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        filter_bar.pack(fill="x", padx=20, pady=(0, 10))

        row_filter = ctk.CTkFrame(filter_bar, fg_color="transparent")
        row_filter.pack(fill="x", padx=14, pady=8)

        entry_search = ctk.CTkEntry(
            row_filter, placeholder_text="🔍 Tìm User, IP, nội dung lỗi...",
            width=250, height=30, font=("Segoe UI", 11),
            fg_color=BG_DARK, border_color=BORDER, corner_radius=8
        )
        entry_search.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(row_filter, text="👤 User:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=(0, 5))
        opt_user = ctk.CTkOptionMenu(row_filter, values=["Tất cả User"], width=135, height=30, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, corner_radius=8)
        opt_user.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(row_filter, text="⚡ Hành động:", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=(0, 5))
        opt_action = ctk.CTkOptionMenu(
            row_filter,
            values=["Tất cả Action", "⚠️ Chỉ xem LỖI / 0 video", "UPLOAD", "PROCESS", "CRAWL", "LOGIN", "RESET_HWID"],
            width=175, height=30, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, corner_radius=8
        )
        opt_action.pack(side="left", padx=(0, 12))

        lbl_filter_status = ctk.CTkLabel(
            row_filter, text="Khớp: 0 logs", font=("Segoe UI", 11, "bold"),
            text_color=CYAN, fg_color=CYAN_BG, corner_radius=6, padx=10, pady=3
        )
        lbl_filter_status.pack(side="left")

        def _reset_filters():
            entry_search.delete(0, "end")
            opt_user.set("Tất cả User")
            opt_action.set("Tất cả Action")
            _apply_filter()

        btn_reset = ctk.CTkButton(
            row_filter, text="✕ Đặt lại", width=75, height=28, font=("Segoe UI", 10, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_DARK,
            text_color=TEXT_MUTED, corner_radius=6, command=_reset_filters
        )
        btn_reset.pack(side="right")

        # ── 4. Card Chứa Bảng Dữ Liệu & Phân Trang ──
        table_card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        table_card.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # Header Bảng
        header = ctk.CTkFrame(table_card, fg_color="#182032", height=38, corner_radius=6)
        header.pack(fill="x", padx=6, pady=(6, 2))

        # Cột Xem ở bên phải ghim cố định
        lbl_xem = ctk.CTkLabel(header, text="🔍 Xem", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED, width=70, anchor="center")
        lbl_xem.pack(side="right", padx=(6, 12), pady=6)

        left_cols = [
            ("🕒 Thời gian", 135),
            ("👤 Người dùng", 125),
            ("⚡ Hành động", 115),
            ("🌐 Địa chỉ IP", 115),
        ]
        for text, width in left_cols:
            lbl = ctk.CTkLabel(header, text=text, font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED, width=width, anchor="w")
            lbl.pack(side="left", padx=8, pady=6)

        lbl_details_hdr = ctk.CTkLabel(header, text="📋 Chi tiết hoạt động & Thông báo sự cố", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED, anchor="w")
        lbl_details_hdr.pack(side="left", fill="x", expand=True, padx=8, pady=6)

        # Scrollable rows
        scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=(0, 2))

        # Pagination Bar (đặt gọn gàng ngay đáy table_card)
        pagi_bar = ctk.CTkFrame(table_card, fg_color="#101522", height=38, corner_radius=6)
        pagi_bar.pack(fill="x", padx=6, pady=(2, 6))

        btn_prev = ctk.CTkButton(pagi_bar, text="◀ Trước", width=85, height=26, font=("Segoe UI", 10, "bold"), fg_color=BORDER, hover_color=BG_CARD, corner_radius=6)
        btn_prev.pack(side="left", padx=(10, 6), pady=6)

        lbl_pagination = ctk.CTkLabel(pagi_bar, text="Trang 1 / 1", font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN)
        lbl_pagination.pack(side="left", padx=8)

        btn_next = ctk.CTkButton(pagi_bar, text="Sau ▶", width=85, height=26, font=("Segoe UI", 10, "bold"), fg_color=BORDER, hover_color=BG_CARD, corner_radius=6)
        btn_next.pack(side="left", padx=(6, 16), pady=6)

        ctk.CTkLabel(pagi_bar, text="Hiển thị mỗi trang:", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(side="left", padx=(10, 4))
        opt_page_size = ctk.CTkOptionMenu(
            pagi_bar, values=["25 logs", "50 logs", "100 logs"], width=95, height=26, font=("Segoe UI", 10),
            fg_color=BG_DARK, button_color=BORDER, corner_radius=6
        )
        opt_page_size.pack(side="left")

        def _on_page_size_change(val):
            try:
                page_size_val[0] = int(val.split()[0])
            except Exception:
                page_size_val[0] = 25
            current_page[0] = 1
            _render_current_page()

        opt_page_size.configure(command=_on_page_size_change)

        def _go_prev():
            if current_page[0] > 1:
                current_page[0] -= 1
                _render_current_page()

        def _go_next():
            total_items = len(filtered_logs_cache)
            total_pages = max(1, (total_items + page_size_val[0] - 1) // page_size_val[0])
            if current_page[0] < total_pages:
                current_page[0] += 1
                _render_current_page()

        btn_prev.configure(command=_go_prev)
        btn_next.configure(command=_go_next)

        # ── 5. Khung Kiểm Tra Nhanh (Smart Inspector Drawer) ──
        inspector_frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        inspector_frame.pack(fill="x", padx=20, pady=(0, 10))

        # View thu gọn mặc định
        collapsed_view = ctk.CTkFrame(inspector_frame, fg_color="transparent")
        collapsed_view.pack(fill="x", padx=14, pady=6)

        ctk.CTkLabel(
            collapsed_view,
            text="💡 Nhấp chuột vào bất kỳ dòng nào trên bảng để mở nhanh Khung kiểm tra chi tiết & Chẩn đoán sự cố tại đây",
            font=("Segoe UI", 11), text_color=TEXT_MUTED
        ).pack(side="left")

        # View mở rộng chi tiết
        expanded_view = ctk.CTkFrame(inspector_frame, fg_color="transparent")

        exp_top = ctk.CTkFrame(expanded_view, fg_color="transparent")
        exp_top.pack(fill="x", pady=(0, 6))

        badge_inspect_action = ctk.CTkLabel(exp_top, text=" ACTION ", font=("Segoe UI", 10, "bold"), fg_color=ACCENT_BG, text_color=ACCENT_LIGHT, corner_radius=6)
        badge_inspect_action.pack(side="left")

        def _open_user_from_inspector():
            log = selected_log_ref[0]
            if log and log.get("username"):
                self._show_user_detail_dialog(log.get("username"))

        lbl_inspect_user = ctk.CTkLabel(exp_top, text="User", font=("Segoe UI", 12, "bold"), text_color="#A78BFA", cursor="hand2")
        lbl_inspect_user.pack(side="left", padx=(8, 12))
        lbl_inspect_user.bind("<Button-1>", lambda e: _open_user_from_inspector())

        lbl_inspect_time = ctk.CTkLabel(exp_top, text="", font=("Consolas", 11), text_color=TEXT_MUTED)
        lbl_inspect_time.pack(side="left", padx=(0, 12))

        lbl_inspect_ip = ctk.CTkLabel(exp_top, text="", font=("Consolas", 11), text_color=TEXT_MUTED)
        lbl_inspect_ip.pack(side="left")

        btn_inspect_close = ctk.CTkButton(
            exp_top, text="✕ Thu gọn", width=75, height=22, font=("Segoe UI", 10, "bold"),
            fg_color="transparent", border_width=1, border_color=BORDER, hover_color=BG_DARK, text_color=TEXT_MUTED
        )
        btn_inspect_close.pack(side="right")

        btn_inspect_popup = ctk.CTkButton(
            exp_top, text="🔍 Cửa sổ riêng", width=105, height=22, font=("Segoe UI", 10, "bold"),
            fg_color="#2563EB", hover_color="#1D4ED8"
        )
        btn_inspect_popup.pack(side="right", padx=6)

        btn_inspect_user = ctk.CTkButton(
            exp_top, text="👤 Xem User", width=100, height=22, font=("Segoe UI", 10, "bold"),
            fg_color="#312E81", hover_color="#4338CA", text_color="#C4B5FD",
            command=_open_user_from_inspector
        )
        btn_inspect_user.pack(side="right", padx=6)

        btn_inspect_copy = ctk.CTkButton(
            exp_top, text="📋 Sao chép", width=85, height=22, font=("Segoe UI", 10, "bold"),
            fg_color=BORDER, hover_color=BG_DARK
        )
        btn_inspect_copy.pack(side="right")

        # Khung nội dung chi tiết trong Drawer (Toàn chiều rộng)
        exp_body = ctk.CTkFrame(expanded_view, fg_color="transparent")
        exp_body.pack(fill="x", pady=(0, 4))

        txt_inspect_details = ctk.CTkTextbox(
            exp_body, height=80, font=("Consolas", 11),
            fg_color=BG_DARK, border_width=1, border_color=BORDER, wrap="word"
        )
        txt_inspect_details.pack(fill="x", expand=True)

        def _collapse_inspector():
            if expanded_view.winfo_ismapped():
                expanded_view.pack_forget()
                collapsed_view.pack(fill="x", padx=14, pady=6)
            if active_row_widget[0] and active_row_widget[0].winfo_exists():
                try:
                    active_row_widget[0].configure(fg_color=getattr(active_row_widget[0], "_def_bg", "transparent"))
                except Exception:
                    pass
                active_row_widget[0] = None

        btn_inspect_close.configure(command=_collapse_inspector)

        def _select_log(log, row_widget=None):
            selected_log_ref[0] = log
            if active_row_widget[0] and active_row_widget[0].winfo_exists():
                try:
                    active_row_widget[0].configure(fg_color=getattr(active_row_widget[0], "_def_bg", "transparent"))
                except Exception:
                    pass
            if row_widget and row_widget.winfo_exists():
                row_widget.configure(fg_color="#263352")
                active_row_widget[0] = row_widget

            action = log.get("action", "")
            details = str(log.get("details", ""))
            act_text, act_bg, act_fg, is_err = _get_action_style(action, details)

            if collapsed_view.winfo_ismapped():
                collapsed_view.pack_forget()
                expanded_view.pack(fill="x", padx=12, pady=8)

            badge_inspect_action.configure(text=f" {act_text} ", fg_color=act_bg, text_color=act_fg)
            lbl_inspect_user.configure(text=log.get("username", "N/A"))
            lbl_inspect_time.configure(text=f"🕒 {log.get('time', '')}")
            lbl_inspect_ip.configure(text=f"🌐 {log.get('ip_address', '')}")

            txt_inspect_details.configure(state="normal")
            txt_inspect_details.delete("1.0", "end")
            txt_inspect_details.insert("1.0", details)
            txt_inspect_details.configure(state="disabled", border_color="#f38ba8" if is_err else BORDER)

        def _do_quick_copy():
            log = selected_log_ref[0]
            if not log:
                return
            self.clipboard_clear()
            copy_text = f"Thời gian: {log.get('time')}\nUser: {log.get('username')}\nAction: {log.get('action')}\nIP: {log.get('ip_address')}\nChi tiết: {log.get('details')}"
            self.clipboard_append(copy_text)
            btn_inspect_copy.configure(text="✅ Đã chép!", fg_color=SUCCESS)
            self.after(1500, lambda: btn_inspect_copy.configure(text="📋 Sao chép", fg_color=BORDER))

        btn_inspect_copy.configure(command=_do_quick_copy)
        btn_inspect_popup.configure(command=lambda: _show_log_detail_dialog(selected_log_ref[0]))

        # ── 6. Render Trang Hiện Tại ──
        def _render_current_page():
            if not scroll.winfo_exists():
                return
            for widget in scroll.winfo_children():
                try: widget.destroy()
                except Exception: pass

            total_items = len(filtered_logs_cache)
            total_pages = max(1, (total_items + page_size_val[0] - 1) // page_size_val[0])
            if current_page[0] > total_pages: current_page[0] = total_pages
            if current_page[0] < 1: current_page[0] = 1

            start_idx = (current_page[0] - 1) * page_size_val[0]
            end_idx = min(start_idx + page_size_val[0], total_items)
            page_items = filtered_logs_cache[start_idx:end_idx]

            lbl_pagination.configure(text=f"Trang {current_page[0]} / {total_pages} • Hiển thị {start_idx+1 if total_items else 0} - {end_idx} trong {total_items} logs")
            btn_prev.configure(state="normal" if current_page[0] > 1 else "disabled")
            btn_next.configure(state="normal" if current_page[0] < total_pages else "disabled")

            if not page_items:
                empty_box = ctk.CTkFrame(scroll, fg_color="transparent")
                empty_box.pack(pady=40)
                ctk.CTkLabel(empty_box, text="🔍 Không tìm thấy nhật ký phù hợp", font=("Segoe UI", 13, "bold"), text_color=TEXT_MUTED).pack()
                ctk.CTkLabel(empty_box, text="Thử thay đổi từ khóa tìm kiếm hoặc chọn 'Tất cả Action'", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(pady=(2, 0))
                return

            for idx, log in enumerate(page_items):
                bg_col = "#111624" if idx % 2 == 0 else "transparent"
                row = ctk.CTkFrame(scroll, fg_color=bg_col, height=36, corner_radius=6, cursor="hand2")
                row._def_bg = bg_col
                row.pack(fill="x", pady=1.5)

                action = log.get("action", "")
                details_str = str(log.get("details", ""))
                act_text, act_bg, act_fg, is_error = _get_action_style(action, details_str)

                # Hover row highlight effect
                def _on_row_enter(e, r=row):
                    if active_row_widget[0] != r:
                        r.configure(fg_color="#1D2538")

                def _on_row_leave(e, r=row, def_bg=bg_col):
                    if active_row_widget[0] != r:
                        r.configure(fg_color=def_bg)

                row.bind("<Enter>", _on_row_enter)
                row.bind("<Leave>", _on_row_leave)
                row.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))

                # Time
                t_lbl = ctk.CTkLabel(row, text=log.get("time", ""), font=("Consolas", 11), text_color=TEXT_DIM, width=135, anchor="w")
                t_lbl.pack(side="left", padx=8, pady=4)
                t_lbl.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))

                # User
                u_lbl = ctk.CTkLabel(row, text=f"👤 {log.get('username', '')}", font=("Segoe UI", 11, "bold"), text_color="#A78BFA", width=125, anchor="w")
                u_lbl.pack(side="left", padx=8, pady=4)
                u_lbl.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))

                # Action Badge
                a_box = ctk.CTkFrame(row, fg_color="transparent", width=115)
                a_box.pack(side="left", padx=6, pady=4)
                a_lbl = ctk.CTkLabel(a_box, text=f" {act_text} ", font=("Segoe UI", 10, "bold"), text_color=act_fg, fg_color=act_bg, corner_radius=6)
                a_lbl.pack(side="left")
                a_lbl.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))
                a_box.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))

                # IP
                i_lbl = ctk.CTkLabel(row, text=log.get("ip_address", "N/A"), font=("Consolas", 11), text_color=TEXT_MUTED, width=115, anchor="w")
                i_lbl.pack(side="left", padx=8, pady=4)
                i_lbl.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))

                # Button Xem (Ghim cố định ở mép phải trước để luôn luôn hiển thị)
                btn_v = ctk.CTkButton(
                    row, text="Chi tiết", width=66, height=24, font=("Segoe UI", 10, "bold"),
                    fg_color="#1E293B", hover_color=ACCENT, text_color="#F8FAFC", corner_radius=6,
                    command=lambda l=log: _show_log_detail_dialog(l)
                )
                btn_v.pack(side="right", padx=(6, 12), pady=6)

                # Details (Preview 1 dòng ngắn gọn, tự co giãn theo khoảng trống còn lại)
                clean_dt = details_str.replace("\n", " ").strip()
                if len(clean_dt) > 90:
                    clean_dt = clean_dt[:87] + "..."
                d_text = clean_dt if not is_error else f"⚠️  {clean_dt}"
                d_color = "#FCA5A5" if is_error else TEXT_MAIN
                d_lbl = ctk.CTkLabel(row, text=d_text, font=("Segoe UI", 11), text_color=d_color, anchor="w")
                d_lbl.pack(side="left", fill="x", expand=True, padx=8, pady=4)
                d_lbl.bind("<Button-1>", lambda e, l=log, r=row: _select_log(l, r))

            try:
                scroll._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        # ── 7. Lọc Dữ Liệu ──
        def _apply_filter(*args):
            query = entry_search.get().strip().lower()
            selected_user = opt_user.get()
            selected_action = opt_action.get()

            filtered = []
            for log in all_logs_data:
                u = str(log.get("username", ""))
                ip = str(log.get("ip_address", ""))
                details = str(log.get("details", ""))
                action = str(log.get("action", ""))

                is_err = action == "ERROR" or any(w in details.lower() for w in ["lỗi", "thất bại", "0 video", "hết hạn", "error", "failed"])

                if selected_user != "Tất cả User" and u != selected_user:
                    continue

                if selected_action == "⚠️ Chỉ xem LỖI / 0 video":
                    if not is_err:
                        continue
                elif selected_action != "Tất cả Action":
                    if action != selected_action:
                        continue

                if query:
                    combined = f"{u} {ip} {details} {action}".lower()
                    if query not in combined:
                        continue

                filtered.append(log)

            filtered_logs_cache.clear()
            filtered_logs_cache.extend(filtered)
            current_page[0] = 1
            lbl_filter_status.configure(text=f"Khớp: {len(filtered)}/{len(all_logs_data)} logs")
            _render_current_page()

        def _on_search_key(event=None):
            if search_timer[0]:
                self.after_cancel(search_timer[0])
            search_timer[0] = self.after(250, _apply_filter)

        def _filter_logs_by_user(target_uname):
            if not target_uname:
                return
            entry_search.delete(0, "end")
            opt_action.set("Tất cả Action")
            vals = list(opt_user.cget("values"))
            for v in vals:
                if str(v).lower() == str(target_uname).lower():
                    opt_user.set(v)
                    _apply_filter()
                    return
            entry_search.insert(0, target_uname)
            _apply_filter()

        self._filter_logs_by_user = _filter_logs_by_user

        entry_search.bind("<KeyRelease>", _on_search_key)
        opt_user.configure(command=_apply_filter)
        opt_action.configure(command=_apply_filter)

        def _render_logs(succ, logs):
            nonlocal all_logs_data
            if not scroll.winfo_exists():
                return

            if not succ or not isinstance(logs, list):
                for widget in scroll.winfo_children():
                    try: widget.destroy()
                    except Exception: pass
                ctk.CTkLabel(scroll, text="Không thể tải dữ liệu nhật ký từ server", text_color=DANGER).pack(pady=20)
                return

            all_logs_data = logs
            _update_kpi_metrics()

            unique_users = sorted(list(set(str(l.get("username", "")) for l in logs if l.get("username"))))
            curr_user_sel = opt_user.get()
            opt_user.configure(values=["Tất cả User"] + unique_users)
            if curr_user_sel in unique_users:
                opt_user.set(curr_user_sel)
            else:
                opt_user.set("Tất cả User")

            _apply_filter()

        def _fetch_logs():
            if is_loading[0]:
                return
            is_loading[0] = True
            btn_refresh.configure(state="disabled", text="⏳ Đang tải...")
            def _worker():
                try:
                    from auth_client import auth_client
                    succ, logs = auth_client.admin_get_logs(limit=500)
                except Exception:
                    succ, logs = False, []
                finally:
                    is_loading[0] = False
                try:
                    if scroll.winfo_exists():
                        scroll.after(0, lambda: [
                            btn_refresh.configure(state="normal", text="🔄 Làm mới dữ liệu"),
                            _render_logs(succ, logs)
                        ])
                except Exception:
                    pass
            threading.Thread(target=_worker, daemon=True).start()

        btn_refresh.configure(command=_fetch_logs)
        self._fetch_admin_logs = _fetch_logs

        self.after(300, lambda: _fetch_logs() if self.tabview.get() == "Hoạt động" else None)

    def _build_admin_feedbacks(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        # 1. Top Header
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))

        title_box = ctk.CTkFrame(top_frame, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="⭐ Đánh Giá & Góp Ý Từ Người Dùng", font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Thống kê mức độ hài lòng, tổng hợp ý kiến đóng góp và phản hồi lỗi từ người dùng toàn hệ thống", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(anchor="w", pady=(1, 0))

        btn_refresh = ctk.CTkButton(top_frame, text="🔄 Làm mới dữ liệu", width=135, height=32, font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8)
        btn_refresh.pack(side="right")

        # 2. KPI Stat Cards
        kpi_frame = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 10))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi_fb")

        def _create_kpi_card(col_idx, icon, title, initial_val, text_col):
            card = ctk.CTkFrame(kpi_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
            card.grid(row=0, column=col_idx, sticky="ew", padx=4 if col_idx not in (0, 3) else (0 if col_idx == 0 else 0))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=12, pady=8)
            ctk.CTkLabel(inner, text=f"{icon}  {title}", font=("Segoe UI", 11, "bold"), text_color=TEXT_MUTED).pack(anchor="w")
            lbl_v = ctk.CTkLabel(inner, text=str(initial_val), font=("Segoe UI", 20, "bold"), text_color=text_col)
            lbl_v.pack(anchor="w", pady=(2, 0))
            return lbl_v

        lbl_kpi_avg = _create_kpi_card(0, "⭐", "Điểm Đánh Giá TB", "5.0 / 5.0", "#FBBF24")
        lbl_kpi_total = _create_kpi_card(1, "📊", "Tổng Đánh Giá", "0", ACCENT_LIGHT)
        lbl_kpi_ideas = _create_kpi_card(2, "💡", "Đề Xuất Mới", "0", CYAN)
        lbl_kpi_bugs = _create_kpi_card(3, "🐞", "Báo Cáo Sự Cố", "0", DANGER)

        # 3. Filter Row
        filter_card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        filter_card.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        f_inner = ctk.CTkFrame(filter_card, fg_color="transparent")
        f_inner.pack(fill="x", padx=12, pady=8)

        entry_search = ctk.CTkEntry(f_inner, placeholder_text="🔍 Tìm kiếm theo User hoặc nội dung góp ý...", height=32, font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        entry_search.pack(side="left", fill="x", expand=True, padx=(0, 8))

        opt_filter_cat = ctk.CTkOptionMenu(
            f_inner, values=["Tất cả Danh Mục", "Đánh giá", "Đề xuất", "Báo cáo lỗi", "Góp ý"],
            width=160, height=32, font=("Segoe UI", 11)
        )
        opt_filter_cat.pack(side="left", padx=(0, 8))

        opt_filter_star = ctk.CTkOptionMenu(
            f_inner, values=["Tất cả Sao", "5 Sao ⭐⭐⭐⭐⭐", "4 Sao ⭐⭐⭐⭐", "3 Sao ⭐⭐⭐", "1-2 Sao ⭐"],
            width=150, height=32, font=("Segoe UI", 11)
        )
        opt_filter_star.pack(side="left")

        # 4. Feedback List Scrollable
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 16))
        scroll.grid_columnconfigure(0, weight=1)

        feedbacks_data = []
        is_loading = [False]

        def _render_feedbacks():
            if not scroll.winfo_exists():
                return
            for w in scroll.winfo_children():
                try: w.destroy()
                except Exception: pass

            query = entry_search.get().strip().lower()
            cat_filter = opt_filter_cat.get()
            star_filter = opt_filter_star.get()

            filtered = []
            for item in feedbacks_data:
                u = str(item.get("username", "")).lower()
                content = str(item.get("content", "")).lower()
                cat = str(item.get("category", ""))
                rating = item.get("rating", 5)

                if query and (query not in u and query not in content):
                    continue

                if cat_filter != "Tất cả Danh Mục":
                    if cat_filter.lower() not in cat.lower():
                        continue

                if star_filter == "5 Sao ⭐⭐⭐⭐⭐" and rating != 5:
                    continue
                elif star_filter == "4 Sao ⭐⭐⭐⭐" and rating != 4:
                    continue
                elif star_filter == "3 Sao ⭐⭐⭐" and rating != 3:
                    continue
                elif star_filter == "1-2 Sao ⭐" and rating > 2:
                    continue

                filtered.append(item)

            if not filtered:
                empty_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
                empty_card.pack(fill="x", pady=20)
                ctk.CTkLabel(empty_card, text="📭 Chưa có đánh giá nào phù hợp với bộ lọc hiện tại.", font=("Segoe UI", 13), text_color=TEXT_MUTED).pack(pady=30)
                return

            for fb in filtered:
                rating = fb.get("rating", 5)
                username = fb.get("username", "Anonymous")
                category = fb.get("category", "Đánh giá")
                content = fb.get("content", "")
                created_at = fb.get("created_at", "")

                card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
                card.pack(fill="x", pady=5)

                top_r = ctk.CTkFrame(card, fg_color="transparent")
                top_r.pack(fill="x", padx=14, pady=(10, 4))

                u_badge = ctk.CTkButton(
                    top_r, text=f"👤 {username}  ℹ️", height=26,
                    font=("Segoe UI", 11, "bold"), fg_color="#1E1B4B", hover_color="#312E81",
                    text_color="#C4B5FD", border_width=1, border_color="#6366F1", corner_radius=6,
                    command=lambda u_name=username: self._show_user_detail_dialog(u_name)
                )
                u_badge.pack(side="left")

                star_text = "★" * rating + "☆" * (5 - rating)
                r_badge = ctk.CTkFrame(top_r, fg_color="#3B2A10", corner_radius=6, border_width=1, border_color="#F59E0B")
                r_badge.pack(side="left", padx=8)
                ctk.CTkLabel(r_badge, text=f"⭐ {star_text} ({rating}/5)", font=("Segoe UI", 11, "bold"), text_color="#FDE68A").pack(padx=8, pady=3)

                cat_badge = ctk.CTkFrame(top_r, fg_color="#0F2937", corner_radius=6, border_width=1, border_color="#0EA5E9")
                cat_badge.pack(side="left")
                ctk.CTkLabel(cat_badge, text=category, font=("Segoe UI", 10, "bold"), text_color="#7DD3FC").pack(padx=8, pady=3)

                ctk.CTkLabel(top_r, text=f"🕒 {created_at}", font=("Segoe UI", 10), text_color=TEXT_MUTED).pack(side="right")

                txt_lbl = ctk.CTkLabel(card, text=content, font=("Segoe UI", 12), text_color=TEXT_MAIN, justify="left", wraplength=950)
                txt_lbl.pack(anchor="w", padx=14, pady=(4, 12))

        def _update_kpis(data_obj):
            total = data_obj.get("total", 0)
            avg = data_obj.get("avg_rating", 5.0)
            lbl_kpi_total.configure(text=str(total))
            lbl_kpi_avg.configure(text=f"{avg:.1f} / 5.0")

            fbs = data_obj.get("feedbacks", [])
            ideas = sum(1 for f in fbs if "đề xuất" in str(f.get("category", "")).lower() or "tính năng" in str(f.get("content", "")).lower())
            bugs = sum(1 for f in fbs if "lỗi" in str(f.get("category", "")).lower() or f.get("rating", 5) <= 2)
            lbl_kpi_ideas.configure(text=str(ideas))
            lbl_kpi_bugs.configure(text=str(bugs))

        def _fetch_feedbacks():
            if is_loading[0]:
                return
            is_loading[0] = True
            btn_refresh.configure(state="disabled", text="⏳ Đang tải...")
            def _worker():
                try:
                    succ, data = auth_client.admin_get_feedbacks()
                except Exception:
                    succ, data = False, {}
                finally:
                    is_loading[0] = False
                try:
                    if scroll.winfo_exists():
                        scroll.after(0, lambda: [
                            btn_refresh.configure(state="normal", text="🔄 Làm mới dữ liệu"),
                            _on_data_loaded(succ, data)
                        ])
                except Exception:
                    pass
            threading.Thread(target=_worker, daemon=True).start()

        def _on_data_loaded(succ, data):
            nonlocal feedbacks_data
            if not succ or not isinstance(data, dict):
                return
            feedbacks_data = data.get("feedbacks", [])
            _update_kpis(data)
            _render_feedbacks()

        btn_refresh.configure(command=_fetch_feedbacks)
        entry_search.bind("<KeyRelease>", lambda e: _render_feedbacks())
        opt_filter_cat.configure(command=lambda c: _render_feedbacks())
        opt_filter_star.configure(command=lambda s: _render_feedbacks())

        self._fetch_admin_feedbacks = _fetch_feedbacks
        self.after(300, lambda: _fetch_feedbacks() if hasattr(self, "tabview") and self.tabview.get() == "Đánh giá & Góp ý" else None)




# ═══════════════════════════════════════════════════════════════════════════════
#  Main App Window
# ═══════════════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    TABS = [
        ("📊", "Dashboard", DashboardTab),
        ("🔍", "Crawl",     CrawlTab),
        ("🎥", "Process",   ProcessTab),
        ("📤", "Upload",    UploadTab),
        ("🤖", "Auto",      AutoTab),
        ("👥", "Accounts",  AccountsTab),
        ("🌱", "Farm",      FarmTab),
        ("📡", "Livestream", LivestreamTab),
        ("⚙️", "Settings",  SettingsTab),
    ]

    def __init__(self):
        super().__init__()

        self.title("🎬 Douyin → TikTok Auto-Uploader | 🎁 Free 10 Ngày Full AI")
        self.geometry("1240x760")
        self.minsize(1050, 650)
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
            self.after(100, lambda: self.state("zoomed"))  # Full màn hình sau khi load xong
            import threading
            threading.Thread(target=auth_client.sync_douyin_cookie, daemon=True).start()
            self.after(5000, self._auto_sync_user_status)
        else:
            self.withdraw() # Ẩn main window
            LoginWindow(self, self._on_login_success)

    def _auto_sync_user_status(self):
        """Đồng bộ trạng thái bản quyền/VIP theo thời gian thực từ Cloud không cần khởi động lại app."""
        def _bg():
            from auth_client import auth_client
            if getattr(auth_client, "token", None):
                succ, data = auth_client.get_me()
                if succ and isinstance(data, dict):
                    last_exp = getattr(self, "_cached_exp_sync", None)
                    last_role = getattr(self, "_cached_role_sync", None)
                    last_plan = getattr(self, "_cached_plan_sync", None)
                    cur_exp = data.get("expire_date")
                    cur_role = data.get("role")
                    cur_plan = data.get("plan_name")
                    if cur_exp != last_exp or cur_role != last_role or cur_plan != last_plan:
                        self._cached_exp_sync = cur_exp
                        self._cached_role_sync = cur_role
                        self._cached_plan_sync = cur_plan
                        try:
                            if self.winfo_exists():
                                self.after(0, self._update_user_ui)
                        except Exception:
                            pass
        import threading
        threading.Thread(target=_bg, daemon=True).start()
        try:
            if self.winfo_exists():
                self.after(10000, self._auto_sync_user_status)
        except Exception:
            pass

    def _update_user_ui(self):
        # Cập nhật UI theo trạng thái bản quyền
        if auth_client.user_info:
            role = auth_client.user_info.get("role", "user")
            
            if role in ("admin", "super_admin"):
                is_expired = False
                expire = "Vĩnh viễn (Admin)"
                status = "👑 Quản trị viên"
            else:
                expire = auth_client.user_info.get("expire_date", "Chưa có")
                is_expired = auth_client.user_info.get("is_expired", False)
                plan_name = str(auth_client.user_info.get("plan_name") or "Free").strip()
                days_left = auth_client.user_info.get("days_left")
                if (days_left is None or days_left == 0) and expire and expire not in ("Chưa có", "Chưa thiết lập", "Vĩnh viễn (Admin)"):
                    try:
                        from datetime import datetime
                        exp_dt = datetime.strptime(expire, "%d/%m/%Y")
                        days_left = max(0, (exp_dt.date() - datetime.now().date()).days)
                    except Exception:
                        days_left = 0
                        
                is_free = (plan_name.lower() == "free")
                if is_expired:
                    status = "❌ Hết hạn"
                elif is_free:
                    status = f"🎁 Gói Free (Còn {days_left} ngày)" if days_left else "🎁 Gói Free"
                else:
                    status = f"✅ VIP Hoạt động (Còn {days_left} ngày)" if days_left else "✅ VIP Hoạt động"
                
            user = auth_client.user_info.get("username", "Unknown")
            
            if hasattr(self, "lbl_user_info"):
                self.lbl_user_info.configure(text=f"👤 User: {user}\n⏳ Hạn: {expire}\n🌟 {status}")
            
            # ── Ẩn nút Nâng cấp VIP nếu là Admin ──
            if hasattr(self, "_nav_buttons"):
                if role in ("admin", "super_admin"):
                    if hasattr(self, "btn_upgrade_sidebar"):
                        self.btn_upgrade_sidebar.pack_forget()
                else:
                    if hasattr(self, "btn_upgrade_sidebar"):
                        self.btn_upgrade_sidebar.pack(padx=12, pady=(0, 10), fill="x")
                        
            # Chỉ làm mới SettingsTab nếu phân quyền (role) thay đổi
            prev_role = getattr(self, "_last_ui_role", None)
            if prev_role != role:
                self._last_ui_role = role
                if hasattr(self, "_tab_frames") and len(self._tab_frames) > 7:
                    for i, tab in enumerate(self._tab_frames):
                        if hasattr(tab, "refresh_ui") and tab.__class__.__name__ == "SettingsTab":
                            tab.refresh_ui(force=True)
                
                # Hiển thị toàn bộ các tab cho cả Admin và User
                nav_container = getattr(self, "_nav_scroll", None)
                if nav_container:
                    for i, btn in enumerate(self._nav_buttons):
                        btn.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            
            has_custom_key = False
            from config.settings import COOKIES_DIR, PROCESSOR_CONFIG
            import json
            user_dir = COOKIES_DIR / user
            user_settings = user_dir / "settings.json"
            
            if user_settings.exists():
                try:
                    with open(user_settings, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        key = data.get("gemini_api_key", "").strip()
                        if key:
                            has_custom_key = True
                            PROCESSOR_CONFIG["gemini_api_keys"] = [k.strip() for k in key.split(",") if k.strip()]
                        else:
                            raw_env = os.getenv("GEMINI_API_KEY", "")
                            PROCESSOR_CONFIG["gemini_api_keys"] = [k.strip() for k in raw_env.split(",") if k.strip()]
                        
                        # Load Ollama / AI Provider
                        if data.get("ai_provider"):
                            PROCESSOR_CONFIG["ai_provider"] = data.get("ai_provider")
                            os.environ["AI_PROVIDER"] = data.get("ai_provider")
                        else:
                            PROCESSOR_CONFIG["ai_provider"] = "cloud_first"
                            os.environ["AI_PROVIDER"] = "cloud_first"
                        if data.get("ollama_url"):
                            PROCESSOR_CONFIG["ollama_url"] = data.get("ollama_url")
                            os.environ["OLLAMA_URL"] = data.get("ollama_url")
                        if data.get("ollama_model"):
                            PROCESSOR_CONFIG["ollama_model"] = data.get("ollama_model")
                            os.environ["OLLAMA_MODEL"] = data.get("ollama_model")
                        if data.get("custom_ai_model"):
                            PROCESSOR_CONFIG["custom_ai_model"] = data.get("custom_ai_model")
                            os.environ["CUSTOM_AI_MODEL"] = data.get("custom_ai_model")
                except:
                    pass
            else:
                raw_env = os.getenv("GEMINI_API_KEY", "")
                PROCESSOR_CONFIG["gemini_api_keys"] = [k.strip() for k in raw_env.split(",") if k.strip()]
                PROCESSOR_CONFIG["ai_provider"] = "cloud_first"
                os.environ["AI_PROVIDER"] = "cloud_first"
            # Cập nhật quyền hạn ở tab Process
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 2:
                process_tab = self._tab_frames[2]
                if hasattr(process_tab, "_sw_dubbing"):
                    process_tab._sw_dubbing.configure(state="normal", text="Thuyết minh AI")
                        
            # Update Dashboard
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 0:
                dashboard_tab = self._tab_frames[0]
                if hasattr(dashboard_tab, "refresh_stats"):
                    dashboard_tab.refresh_stats(silent=True)
                    
            # Update Settings UI based on role
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 7:
                settings_tab = self._tab_frames[7]
                if hasattr(settings_tab, "refresh_ui"):
                    settings_tab.refresh_ui()
                    
            # Update UploadTab accounts
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 3:
                upload_tab = self._tab_frames[3]
                if hasattr(upload_tab, "_refresh_accounts"):
                    upload_tab._refresh_accounts()
                if hasattr(upload_tab, "_refresh_youtube_accounts"):
                    upload_tab._refresh_youtube_accounts()
                if hasattr(upload_tab, "_refresh_facebook_accounts"):
                    upload_tab._refresh_facebook_accounts()
                    
            # Update AutoTab accounts
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 4:
                auto_tab = self._tab_frames[4]
                if hasattr(auto_tab, "_refresh_accounts"):
                    auto_tab._refresh_accounts()
                    
            # Update AccountsTab
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 5:
                acc_tab = self._tab_frames[5]
                if hasattr(acc_tab, "_load_accounts"):
                    acc_tab._load_accounts()
                if hasattr(acc_tab, "_load_yt_accounts"):
                    acc_tab._load_yt_accounts()
                if hasattr(acc_tab, "_load_fb_accounts"):
                    acc_tab._load_fb_accounts()
                    
            # Update FarmTab accounts
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 6:
                farm_tab = self._tab_frames[6]
                if hasattr(farm_tab, "_load_accounts"):
                    farm_tab._load_accounts()

    def _on_login_success(self):
        auth_client.get_me()
        self.deiconify() # Hiện lại main window
        self.after(100, lambda: self.state("zoomed"))  # Giữ full màn hình sau khi login
        self._nav_buttons[0].set_active(True)
        self._show_tab(0)
        self._update_user_ui()
        
        auth_client.send_telemetry("LOGIN", "Đăng nhập phần mềm thành công")
        
        import threading
        threading.Thread(target=auth_client.sync_douyin_cookie, daemon=True).start()
        self.after(5000, self._auto_sync_user_status)
        
        # Hiện toast thông báo nếu có
        def _show_noti_after_login():
            try:
                succ, pay_info = auth_client.get_payment_info()
                if succ and pay_info:
                    announcement = pay_info.get("system_announcement", "").strip()
                    version = pay_info.get("client_version", "").strip()
                    if version and version != "1.0":
                        show_toast(self, title="Cập Nhật Phìiên Bản Mới!",
                                   message=f"Phìiên bản v{version} đã ra mắt.\nTải lại Tool mới để có tính năng mới & vá lỗi!",
                                   type_="update", duration=15)
                    elif announcement:
                        show_toast(self, title="Thông Báo Hệ Thống",
                                   message=announcement,
                                   type_="warning", duration=12)
            except Exception:
                pass
        self.after(800, _show_noti_after_login)

    def _do_logout(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn đăng xuất?"):
            auth_client.logout()
            self.withdraw()
            LoginWindow(self, self._on_login_success)

    def _handle_sidebar_upgrade(self):
        # Tìm index của SettingsTab động để tránh lệch khi thêm bớt tab
        settings_idx = None
        for i, (_, _, TabClass) in enumerate(self.TABS):
            if TabClass == SettingsTab:
                settings_idx = i
                break
        if settings_idx is None:
            settings_idx = len(self.TABS) - 1

        self._nav(settings_idx)
        if hasattr(self, "_tab_frames") and len(self._tab_frames) > settings_idx:
            tab_obj = self._tab_frames[settings_idx]
            if hasattr(tab_obj, "_show_payment_dialog"):
                tab_obj._show_payment_dialog()

    def _show_feedback_dialog(self):
        """Hiển thị modal gửi đánh giá và góp ý của người dùng."""
        root_win = self.winfo_toplevel()
        dlg = ctk.CTkToplevel(root_win)
        dlg.title("⭐ Gửi Đánh Giá & Góp Ý Phát Triển Tool")
        dlg.geometry("540x550")
        dlg.minsize(500, 480)
        dlg.configure(fg_color=BG_DARK)
        dlg.transient(root_win)
        dlg.grab_set()

        try:
            rx = root_win.winfo_rootx()
            ry = root_win.winfo_rooty()
            rw = root_win.winfo_width()
            rh = root_win.winfo_height()
            x = rx + max(0, (rw - 540) // 2)
            y = ry + max(0, (rh - 550) // 2)
            dlg.geometry(f"540x550+{x}+{y}")
        except Exception:
            pass

        # Header card
        hdr_card = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#F59E0B")
        hdr_card.pack(fill="x", padx=20, pady=(16, 12))
        
        h_row = ctk.CTkFrame(hdr_card, fg_color="transparent")
        h_row.pack(fill="x", padx=16, pady=12)
        
        star_icon = ctk.CTkFrame(h_row, width=42, height=42, corner_radius=10, fg_color="#3B2A10", border_width=1, border_color="#F59E0B")
        star_icon.pack(side="left", padx=(0, 12))
        star_icon.pack_propagate(False)
        ctk.CTkLabel(star_icon, text="⭐", font=("Segoe UI", 20)).place(relx=0.5, rely=0.5, anchor="center")
        
        t_box = ctk.CTkFrame(h_row, fg_color="transparent")
        t_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(t_box, text="Đóng Góp Ý Kiến & Đánh Giá", font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(t_box, text="Ý kiến của bạn là động lực để đội ngũ cải tiến phần mềm tốt hơn!", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        # Content frame
        body = ctk.CTkFrame(dlg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 1. Rating Stars selection
        ctk.CTkLabel(body, text="1. Mức độ hài lòng của bạn:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 6))
        
        selected_rating = [5]
        star_buttons = []
        
        rating_frame = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER)
        rating_frame.pack(fill="x", pady=(0, 12))
        
        lbl_rating_text = ctk.CTkLabel(rating_frame, text="⭐⭐⭐⭐⭐ 5/5 - Cực kỳ hài lòng & Tool hoạt động rất tốt", font=("Segoe UI", 11, "bold"), text_color="#FBBF24")
        lbl_rating_text.pack(pady=(8, 4))
        
        stars_row = ctk.CTkFrame(rating_frame, fg_color="transparent")
        stars_row.pack(pady=(0, 8))
        
        rating_descs = {
            1: "⭐ 1/5 - Chưa hài lòng / Cần cải thiện nhiều",
            2: "⭐⭐ 2/5 - Tạm được / Còn nhiều lỗi",
            3: "⭐⭐⭐ 3/5 - Khá ổn / Đạt yêu cầu cơ bản",
            4: "⭐⭐⭐⭐ 4/5 - Hài lòng / Tính năng hữu ích",
            5: "⭐⭐⭐⭐⭐ 5/5 - Cực kỳ hài lòng & Tool hoạt động rất tốt",
        }
        
        def _set_rating(val):
            selected_rating[0] = val
            lbl_rating_text.configure(text=rating_descs.get(val, f"{val} sao"))
            for i, btn in enumerate(star_buttons, 1):
                if i <= val:
                    btn.configure(fg_color="#F59E0B", text_color="#000000")
                else:
                    btn.configure(fg_color="#1E293B", text_color="#64748B")
                    
        for r in range(1, 6):
            btn_s = ctk.CTkButton(
                stars_row, text=f"★ {r}", width=50, height=32,
                font=("Segoe UI", 12, "bold"),
                fg_color="#F59E0B" if r <= 5 else "#1E293B",
                text_color="#000000" if r <= 5 else "#64748B",
                corner_radius=6,
                command=lambda v=r: _set_rating(v)
            )
            btn_s.pack(side="left", padx=4)
            star_buttons.append(btn_s)

        # 2. Category selection
        ctk.CTkLabel(body, text="2. Chủ đề góp ý:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 4))
        opt_category = ctk.CTkOptionMenu(
            body,
            values=[
                "⭐ Đánh giá & Khen ngợi trải nghiệm",
                "💡 Đề xuất tính năng mới cần có",
                "🐞 Báo cáo lỗi / Thắc mắc kỹ thuật",
                "📝 Góp ý giao diện & trải nghiệm khác"
            ],
            width=500, height=34, font=("Segoe UI", 12),
            fg_color=BG_CARD, button_color=ACCENT, button_hover_color=ACCENT_HOVER
        )
        opt_category.pack(fill="x", pady=(0, 12))

        # 3. Content Textbox
        ctk.CTkLabel(body, text="3. Nội dung nhận xét / đề xuất chi tiết:", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 4))
        txt_content = ctk.CTkTextbox(body, height=100, font=("Segoe UI", 12), fg_color=BG_CARD, border_width=1, border_color=BORDER, wrap="word")
        txt_content.pack(fill="both", expand=True, pady=(0, 12))

        # Bottom buttons
        btn_box = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(0, 16))

        def _do_submit():
            text = txt_content.get("1.0", "end").strip()
            if not text:
                messagebox.showwarning("Nhắc nhở", "Vui lòng nhập nội dung đánh giá hoặc góp ý trước khi gửi!")
                return
            btn_submit.configure(state="disabled", text="⏳ Đang gửi...")
            def _worker():
                cat = opt_category.get()
                succ, msg = auth_client.send_feedback(rating=selected_rating[0], category=cat, content=text)
                def _done():
                    if succ:
                        messagebox.showinfo("Cảm ơn bạn!", msg)
                        dlg.destroy()
                    else:
                        messagebox.showerror("Thông báo", msg)
                        btn_submit.configure(state="normal", text="🚀 Gửi Đánh Giá Ngay")
                dlg.after(0, _done)
            threading.Thread(target=_worker, daemon=True).start()

        btn_cancel = ctk.CTkButton(btn_box, text="Đóng", width=100, height=36, font=("Segoe UI", 11), fg_color=BORDER, hover_color=BG_CARD, command=dlg.destroy)
        btn_cancel.pack(side="left")

        btn_submit = ctk.CTkButton(
            btn_box, text="🚀 Gửi Đánh Giá Ngay", width=220, height=36,
            font=("Segoe UI", 12, "bold"),
            fg_color="#D97706", hover_color="#B45309", text_color="#FFFFFF",
            corner_radius=8, command=_do_submit
        )
    def show_user_detail(self, user_or_username):
        """Mở dialog chi tiết user từ bất kỳ vị trí nào trong app."""
        if hasattr(self, "_tab_frames") and len(self._tab_frames) > 8:
            settings_tab = self._tab_frames[8]
            if hasattr(settings_tab, "_show_user_detail_dialog"):
                settings_tab._show_user_detail_dialog(user_or_username)
                return
        self._show_my_account_dialog()

    def _show_my_account_dialog(self):
        """Hiển thị modal chi tiết tài khoản của chính user đang đăng nhập."""
        from auth_client import auth_client
        if not auth_client.user_info:
            auth_client.get_me()
        if not auth_client.user_info:
            messagebox.showinfo("Thông báo", "Bạn chưa đăng nhập hoặc phiên làm việc đã hết hạn.")
            return
            
        role = auth_client.user_info.get("role", "user")
        if role in ("admin", "super_admin"):
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 8:
                settings_tab = self._tab_frames[8]
                if hasattr(settings_tab, "_show_user_detail_dialog"):
                    settings_tab._show_user_detail_dialog(auth_client.user_info)
                    return

        # Modal thông tin tài khoản cá nhân dành cho người dùng
        root_win = self
        dlg = ctk.CTkToplevel(root_win)
        dlg.title("👤 Thông Tin Tài Khoản & Bản Quyền")
        dlg.geometry("540x600")
        dlg.minsize(480, 520)
        dlg.configure(fg_color=BG_DARK)
        dlg.transient(root_win)
        dlg.grab_set()

        try:
            rx = root_win.winfo_rootx()
            ry = root_win.winfo_rooty()
            rw = root_win.winfo_width()
            rh = root_win.winfo_height()
            x = rx + max(0, (rw - 540) // 2)
            y = ry + max(0, (rh - 600) // 2)
            dlg.geometry(f"540x600+{x}+{y}")
        except Exception:
            pass

        u_info = auth_client.user_info or {}
        username = u_info.get("username", "Unknown")
        plan_name = str(u_info.get("plan_name") or "Free").strip()
        expire_date = u_info.get("expire_date", "Chưa có")
        is_expired = u_info.get("is_expired", False)
        days_left = u_info.get("days_left")
        if (days_left is None or days_left == 0) and expire_date and expire_date not in ("Chưa có", "Chưa thiết lập", "Vĩnh viễn (Admin)"):
            try:
                from datetime import datetime
                exp_dt = datetime.strptime(expire_date, "%d/%m/%Y")
                days_left = max(0, (exp_dt.date() - datetime.now().date()).days)
            except Exception:
                days_left = 0

        # 1. Header Card
        hdr_card = ctk.CTkFrame(dlg, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        hdr_card.pack(fill="x", padx=20, pady=(16, 12))

        h_row = ctk.CTkFrame(hdr_card, fg_color="transparent")
        h_row.pack(fill="x", padx=16, pady=12)

        avatar_box = ctk.CTkFrame(h_row, width=48, height=48, corner_radius=12, fg_color="#1E1B4B", border_width=1, border_color="#6366F1")
        avatar_box.pack(side="left", padx=(0, 12))
        avatar_box.pack_propagate(False)
        ctk.CTkLabel(avatar_box, text="👤", font=("Segoe UI", 22)).place(relx=0.5, rely=0.5, anchor="center")

        t_box = ctk.CTkFrame(h_row, fg_color="transparent")
        t_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(t_box, text=username, font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(anchor="w")

        b_row = ctk.CTkFrame(t_box, fg_color="transparent")
        b_row.pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            b_row, text=f" 💎 Gói {plan_name} ",
            font=("Segoe UI", 10, "bold"), text_color="#FBBF24",
            fg_color="#3B2A10", corner_radius=6
        ).pack(side="left", padx=(0, 6))

        stat_lbl = "❌ Đã hết hạn" if is_expired else "✅ Đang hoạt động"
        stat_col = DANGER if is_expired else SUCCESS
        stat_bg = DANGER_BG if is_expired else SUCCESS_BG
        ctk.CTkLabel(
            b_row, text=f" {stat_lbl} ",
            font=("Segoe UI", 10, "bold"), text_color=stat_col,
            fg_color=stat_bg, corner_radius=6
        ).pack(side="left")

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        def _row(parent, label, value, val_color=TEXT_MAIN):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(r, text=label, font=("Segoe UI", 11), text_color=TEXT_MUTED, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=str(value), font=("Segoe UI", 11, "bold"), text_color=val_color, anchor="w").pack(side="left", fill="x", expand=True)

        # Box 1: Bản quyền & thời hạn
        p_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        p_card.pack(fill="x", pady=(0, 10))

        p_hdr = ctk.CTkFrame(p_card, fg_color="transparent")
        p_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(p_hdr, text="💎 Thông Tin Bản Quyền & Thời Hạn", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(side="left")

        _row(p_card, "Tài khoản đăng nhập:", username)
        _row(p_card, "Gói kích hoạt:", f"Gói {plan_name}", "#FBBF24")
        _row(p_card, "Hạn sử dụng:", f"{expire_date} (Còn {days_left} ngày)" if not is_expired else f"{expire_date} (Đã hết hạn)", SUCCESS if not is_expired else DANGER)

        # Box 2: Hạn mức render hôm nay
        trial_info = auth_client.get_trial_info()
        is_unlimited = trial_info.get("is_unlimited", False)
        used_count = trial_info.get("used_count", 0)
        max_vids = trial_info.get("max_allowed", 5)
        rem = trial_info.get("remaining", 0)

        q_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        q_card.pack(fill="x", pady=(0, 10))

        q_hdr = ctk.CTkFrame(q_card, fg_color="transparent")
        q_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(q_hdr, text="📊 Hạn Mức Render Video Hôm Nay", font=("Segoe UI", 12, "bold"), text_color=CYAN).pack(side="left")

        can_ai_user = u_info.get("can_use_ai", True)
        if is_unlimited:
            _row(q_card, "Hạn mức hôm nay:", "🚀 Không giới hạn (Gói VIP/Bản quyền)", SUCCESS)
        else:
            _row(q_card, "Đã xử lý hôm nay:", f"{used_count} / {max_vids} video", WARNING if used_count >= max_vids else TEXT_MAIN)
            _row(q_card, "Số lượt còn lại:", f"{rem} video", SUCCESS if rem > 0 else DANGER)
            
            # Progress bar
            prog_f = ctk.CTkFrame(q_card, fg_color="transparent")
            prog_f.pack(fill="x", padx=14, pady=(6, 12))
            pct = min(1.0, used_count / max(1, max_vids))
            bar = ctk.CTkProgressBar(prog_f, height=8, corner_radius=4)
            bar.pack(fill="x")
            bar.set(pct)
            bar.configure(progress_color=DANGER if pct >= 1.0 else ACCENT)

        if can_ai_user:
            _row(q_card, "Tài nguyên AI:", "✅ Sử dụng API Key AI dùng chung từ hệ thống", SUCCESS)
        else:
            _row(q_card, "Tài nguyên AI:", "⚠️ Gói Tự Túc (Cần nhập Gemini API Key tại tab Cài đặt)", WARNING)

        # Box 3: Thiết bị & Bảo mật
        d_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        d_card.pack(fill="x", pady=(0, 10))

        d_hdr = ctk.CTkFrame(d_card, fg_color="transparent")
        d_hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(d_hdr, text="🔒 Thiết Bị Đang Sử Dụng (HWID)", font=("Segoe UI", 12, "bold"), text_color="#A78BFA").pack(side="left")

        my_hwid = auth_client.get_hwid()
        _row(d_card, "Mã máy của bạn:", my_hwid, "#38BDF8")
        _row(d_card, "Trạng thái:", "🔒 Tài khoản đã được bảo vệ trên thiết bị này", SUCCESS)

        # Bottom actions
        bot_bar = ctk.CTkFrame(dlg, fg_color="transparent")
        bot_bar.pack(fill="x", padx=20, pady=(4, 16))

        def _do_open_upgrade():
            dlg.destroy()
            self._handle_sidebar_upgrade()

        def _do_open_feedback():
            dlg.destroy()
            self._show_feedback_dialog()

        ctk.CTkButton(
            bot_bar, text="💎 Nâng Cấp VIP", width=140, height=34,
            font=("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=_do_open_upgrade
        ).pack(side="left")

        ctk.CTkButton(
            bot_bar, text="⭐ Góp Ý & Đánh Giá", width=150, height=34,
            font=("Segoe UI", 11, "bold"), fg_color="#3B2A10", hover_color="#78350F",
            text_color="#FDE68A", border_width=1, border_color="#F59E0B",
            command=_do_open_feedback
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            bot_bar, text="✕ Đóng", width=80, height=34,
            font=("Segoe UI", 11), fg_color=BORDER, hover_color=BG_CARD,
            command=dlg.destroy
        ).pack(side="right")

    # ── Sidebar ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=224, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(2, weight=1)  # Nav scroll chiếm hết không gian còn lại
        sidebar.grid_columnconfigure(0, weight=1)

        # Logo Brand Header
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 10))
        
        icon_box = ctk.CTkFrame(logo, width=38, height=38, corner_radius=10, fg_color="#1E1B4B", border_width=1, border_color="#6366F1")
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="⚡", font=("Segoe UI", 18), text_color="#A78BFA").place(relx=0.5, rely=0.5, anchor="center")
        
        name_box = ctk.CTkFrame(logo, fg_color="transparent")
        name_box.pack(side="left")
        ctk.CTkLabel(name_box, text="DouyinBot", font=("Segoe UI", 17, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(name_box, text="AUTOMATION SUITE", font=("Segoe UI", 8, "bold"), text_color="#06B6D4").pack(anchor="w")

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(0, 6)
        )

        # ── Scrollable Nav Area ────────────────────────────────────────────────
        nav_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT
        )
        nav_scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        nav_scroll.grid_columnconfigure(0, weight=1)

        # Nav buttons
        self._nav_buttons: list[SidebarButton] = []
        for i, (icon, label, _) in enumerate(self.TABS):
            btn = SidebarButton(nav_scroll, icon=icon, text=label,
                                command=lambda idx=i: self._nav(idx))
            btn.grid(row=i, column=0, sticky="ew", padx=10, pady=2)
            self._nav_buttons.append(btn)
        
        self._nav_scroll = nav_scroll
        
        # ── Bottom fixed area ──────────────────────────────────────────────────
        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        # Premium User Profile Card
        self.user_card = ctk.CTkFrame(bottom, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER, cursor="hand2")
        self.user_card.grid(row=0, column=0, pady=(8, 6), padx=12, sticky="ew")
        
        self.lbl_user_info = ctk.CTkLabel(
            self.user_card, text="👤  Chưa đăng nhập",
            font=("Segoe UI", 11, "bold"), text_color=TEXT_MAIN, justify="left", cursor="hand2"
        )
        self.lbl_user_info.pack(padx=12, pady=(10, 4), anchor="w")

        # Nút xem thông tin tài khoản
        self.btn_view_account = ctk.CTkButton(
            self.user_card, text="ℹ️ Xem Thông Tin Tài Khoản", height=24,
            font=("Segoe UI", 10, "bold"), fg_color="#1E1B4B", hover_color="#312E81",
            text_color="#C4B5FD", corner_radius=6,
            command=self._show_my_account_dialog
        )
        self.btn_view_account.pack(padx=12, pady=(0, 8), fill="x")

        self.user_card.bind("<Button-1>", lambda e: self._show_my_account_dialog())
        self.lbl_user_info.bind("<Button-1>", lambda e: self._show_my_account_dialog())
        
        self.btn_upgrade_sidebar = ctk.CTkButton(
            self.user_card, text="💎 Nâng Cấp VIP", height=32,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8,
            command=self._handle_sidebar_upgrade
        )
        self.btn_upgrade_sidebar.pack(padx=12, pady=(0, 10), fill="x")

        # Nút Đánh giá & Góp ý (Nổi bật màu vàng hổ phách)
        self.btn_feedback = ctk.CTkButton(
            bottom, text="⭐ Góp Ý & Đánh Giá", height=36,
            font=("Segoe UI", 12, "bold"),
            fg_color="#3B2A10", hover_color="#78350F", text_color="#FDE68A",
            border_width=1, border_color="#F59E0B", corner_radius=8,
            command=self._show_feedback_dialog
        )
        self.btn_feedback.grid(row=1, column=0, pady=(0, 6), padx=12, sticky="ew")

        # Logout button
        btn_logout = ctk.CTkButton(
            bottom, text="🚪 Đăng xuất", height=34,
            font=("Segoe UI", 12, "bold"),
            fg_color="#3B1D28", hover_color="#7F1D1D", text_color="#FCA5A5",
            border_width=1, border_color="#EF4444", corner_radius=8,
            command=self._do_logout
        )
        btn_logout.grid(row=2, column=0, pady=(0, 6), padx=12, sticky="ew")

        # Support info
        import webbrowser
        support_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        support_frame.grid(row=3, column=0, sticky="ew")
        
        ctk.CTkLabel(support_frame, text="📞 Hotline hỗ trợ:", font=("Segoe UI", 10, "bold"), text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(2, 3))
        
        self.btn_zalo = ctk.CTkButton(
            support_frame, text="💬 Zalo: 0866655803", font=("Segoe UI", 11, "bold"),
            fg_color="#0A1E40", hover_color="#0068FF", height=28, corner_radius=6,
            border_width=1, border_color="#0055D4",
            command=lambda: webbrowser.open("https://zalo.me/0866655803")
        )
        self.btn_zalo.pack(anchor="w", padx=16, pady=2, fill="x")
        
        self.btn_tele = ctk.CTkButton(
            support_frame, text="✈️ Telegram: @hoannm", font=("Segoe UI", 11, "bold"),
            fg_color="#0B273A", hover_color="#24A1DE", height=28, corner_radius=6,
            border_width=1, border_color="#1D84B5",
            command=lambda: webbrowser.open("https://t.me/hoannm")
        )
        self.btn_tele.pack(anchor="w", padx=16, pady=2, fill="x")

        # Bottom: version
        ctk.CTkLabel(
            bottom, text="⚡ v2.0.0 PRO (Obsidian Edition)",
            font=("Segoe UI", 9, "bold"), text_color=TEXT_MUTED,
        ).grid(row=4, column=0, pady=(4, 10))

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
        if idx == 3 and len(self._tab_frames) > 3:
            upload_tab = self._tab_frames[3]
            if hasattr(upload_tab, "_refresh_accounts"):
                upload_tab._refresh_accounts()
            if hasattr(upload_tab, "_refresh_youtube_accounts"):
                upload_tab._refresh_youtube_accounts()
            if hasattr(upload_tab, "_refresh_facebook_accounts"):
                upload_tab._refresh_facebook_accounts()


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════
def _auto_install_playwright():
    """Tự động cài đặt Playwright Chromium ngầm nếu chưa có."""
    try:
        import subprocess
        import sys
        import os
        
        print("Đang kiểm tra môi trường Playwright...")
        
        startupinfo = None
        creationflags = 0
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
            
        # Nếu đang chạy dạng EXE đóng gói (PyInstaller)
        if getattr(sys, 'frozen', False):
            from playwright._impl._driver import compute_driver_executable, get_driver_env
            driver_executable = compute_driver_executable()
            env = get_driver_env()
            subprocess.run([str(driver_executable), "install", "chromium"], env=env, 
                           startupinfo=startupinfo, creationflags=creationflags)
        else:
            # Chạy dạng Python script thường
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                           startupinfo=startupinfo, creationflags=creationflags)
            
        print("Playwright Chromium sẵn sàng!")
    except Exception as e:
        print(f"Lỗi tự động cài Playwright: {e}")

def _cleanup_zombie_browsers():
    """Dọn dẹp các cửa sổ Chrome/Edge do Playwright sinh ra bị kẹt."""
    try:
        import psutil
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info.get('name', '').lower()
                if name in ('chrome.exe', 'msedge.exe'):
                    cmdline = proc.info.get('cmdline') or []
                    cmd_str = " ".join(cmdline).lower()
                    if ".profiles" in cmd_str or "tiktok-upload-video" in cmd_str:
                        proc.kill()
                        count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if count > 0:
            print(f"Đã tự động dọn dẹp {count} tiến trình Chrome/Edge bị kẹt từ lần chạy trước.")
    except Exception as e:
        print(f"Lỗi dọn dẹp: {e}")

if __name__ == "__main__":
    _cleanup_zombie_browsers()
    # Chạy ngầm cài đặt Playwright để không làm đơ giao diện lúc mở
    threading.Thread(target=_auto_install_playwright, daemon=True).start()
    app = App()
    app.mainloop()