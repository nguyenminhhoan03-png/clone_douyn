from ui.tabs.livestream_tab import LivestreamTab
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

# ─── Theme ───────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Palette (Sleek Dark Theme) ─────────────────────────────────────────────
BG_DARK      = "#0E1015" # Nền tối nhất
BG_CARD      = "#1C1F2E" # Nền Card/Panel
BG_SIDEBAR   = "#141620" # Nền Sidebar
ACCENT       = "#8B5CF6" # Tím Violet (giống nút Upload & Enhance)
ACCENT_HOVER = "#7C3AED" # Tím đậm khi hover
SUCCESS      = "#10B981"
WARNING      = "#F59E0B"
DANGER       = "#EF4444"
TEXT_MAIN    = "#F8FAFC"
TEXT_DIM     = "#94A3B8"
BORDER       = "#2D3142"


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
#  ToolTip - Hiển thị popup khi hover
# ═══════════════════════════════════════════════════════════════════════════════
class ToolTip:
    def __init__(self, widget, text, wraplength=250):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tooltip_window = tw = ctk.CTkFrame(self.widget, fg_color="#2d3436", corner_radius=6, border_width=1, border_color="#636e72")
        
        # We use a Toplevel to hover over other widgets
        import tkinter as tk
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        self.tw.attributes("-topmost", True)
        
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background="#2d3436", foreground="#dfe6e9", 
                         relief='solid', borderwidth=1, highlightbackground="#636e72",
                         font=("Segoe UI", 10), padx=8, pady=6, wraplength=self.wraplength)
        label.pack()

    def leave(self, event=None):
        if hasattr(self, 'tw') and self.tw:
            self.tw.destroy()
            self.tw = None



# ═══════════════════════════════════════════════════════════════════════════════
#  ToastNotification - Popup thông báo kiểu Toast
# ═══════════════════════════════════════════════════════════════════════════════
class ToastNotification(ctk.CTkToplevel):
    """
    Toast popup góc dưới phải màn hình.
    - Tự tắt sau `duration` giây nếu không đóng tay.
    - Có nút X để đóng ngay.
    - type_: 'info' | 'warning' | 'error' | 'update'
    """
    _COLORS = {
        "info":    ("#2980b9", "#d6eaf8"),
        "warning": ("#e67e22", "#fdebd0"),
        "error":   ("#c0392b", "#fadbd8"),
        "update":  ("#8e44ad", "#e8daef"),
    }

    def __init__(self, master, title: str, message: str, type_: str = "info", duration: int = 8):
        super().__init__(master)
        
        # Lấy màu theo type
        accent, bg_light = self._COLORS.get(type_, self._COLORS["info"])
        
        # Cấu hình cửa sổ - không có border, không có titlebar
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.configure(fg_color=BG_CARD)
        
        self._duration = duration
        self._remaining = duration
        
        # ── Layout chính ──────────────────────────────────────────────────────
        self.configure(width=380)
        
        # Accent bar bên trái
        bar = ctk.CTkFrame(self, fg_color=accent, width=6, corner_radius=0)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)
        
        # Nội dung
        content = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        content.pack(side="left", fill="both", expand=True, padx=0)
        
        # Header row
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))
        
        # Icon theo type
        icons = {"info": "ℹ️", "warning": "📢", "error": "⚠️", "update": "🚀"}
        icon_text = icons.get(type_, "ℹ️")
        ctk.CTkLabel(header, text=f"{icon_text}  {title}",
                     font=("Segoe UI", 13, "bold"),
                     text_color=accent).pack(side="left")
        
        # Nút X và countdown
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")
        
        self._lbl_countdown = ctk.CTkLabel(right, text=f"{duration}s",
                                            font=("Segoe UI", 10), text_color=TEXT_DIM)
        self._lbl_countdown.pack(side="left", padx=(0, 6))
        
        ctk.CTkButton(right, text="✕", width=24, height=24,
                      fg_color="transparent", hover_color=BORDER,
                      font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM,
                      command=self.close_toast).pack(side="left")
        
        # Message
        ctk.CTkLabel(content, text=message,
                     font=("Segoe UI", 12), text_color=TEXT_MAIN,
                     wraplength=310, justify="left", anchor="w"
                     ).pack(fill="x", padx=14, pady=(0, 12), anchor="w")
        
        # Progress bar (tự thu nhỏ theo thời gian)
        prog_bg = ctk.CTkFrame(content, fg_color=BORDER, height=3, corner_radius=0)
        prog_bg.pack(fill="x", side="bottom")
        self._prog = ctk.CTkFrame(prog_bg, fg_color=accent, height=3, corner_radius=0)
        self._prog.pack(side="left", fill="y")
        
        # Border
        self.configure(border_width=1, border_color=BORDER)
        
        # Đặt vị trí góc dưới phải
        self.update_idletasks()
        self._position_toast(master)
        
        # Bắt đầu đếm ngược
        self.after(100, self._tick)
    
    def _position_toast(self, master):
        """Đặt toast ở trên cùng, ở giữa cửa sổ chính."""
        try:
            master.update_idletasks()
            self.update_idletasks()
            mx = master.winfo_x()
            my = master.winfo_y()
            mw = master.winfo_width()
            
            tw = 420
            th = 110
            
            x = mx + (mw // 2) - (tw // 2)
            y = my + 24  # margin top 24px
            self.geometry(f"{tw}x{th}+{x}+{y}")
        except Exception:
            self.geometry("420x110+300+60")
    
    def _tick(self):
        """Cập nhật countdown mỗi giây."""
        if not self.winfo_exists():
            return
        self._remaining -= 1
        if self._remaining <= 0:
            self.close_toast()
            return
        self._lbl_countdown.configure(text=f"{self._remaining}s")
        # Thu nhỏ progress bar
        ratio = self._remaining / self._duration
        try:
            total_w = self._prog.master.winfo_width()
            self._prog.configure(width=int(total_w * ratio))
        except Exception:
            pass
        self.after(1000, self._tick)
    
    def close_toast(self):
        try:
            self.destroy()
        except Exception:
            pass


def show_toast(master, title: str, message: str, type_: str = "info", duration: int = 8):
    """Helper function để bắn toast từ bất kỳ đâu."""
    try:
        toast = ToastNotification(master, title=title, message=message, type_=type_, duration=duration)
        return toast
    except Exception as e:
        print(f"Toast error: {e}")
        return None



class StatsCard(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "0", color=ACCENT, icon: str = "", **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10,
                         border_width=1, border_color=BORDER, **kwargs)
        
        self.pack_propagate(False)
        self.configure(height=90)
        
        # Đường viền màu bên trái đặc trưng của Web Dashboard
        accent_line = ctk.CTkFrame(self, fg_color=color, width=5, corner_radius=0)
        accent_line.pack(side="left", fill="y", pady=15)
        
        # Nội dung
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=16, pady=12)
        
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, text=label.upper(),
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT_DIM,
        ).pack(side="left")
        
        if icon:
            ctk.CTkLabel(
                header, text=icon,
                font=("Segoe UI", 16),
                text_color=color,
            ).pack(side="right")
        
        self._lbl_value = ctk.CTkLabel(
            content, text=value,
            font=("Segoe UI", 22, "bold"),
            text_color=TEXT_MAIN,
            anchor="w",
            justify="left"
        )
        self._lbl_value.pack(side="left", fill="x", expand=True, pady=(2, 0))

    def set_value(self, v):
        self._lbl_value.configure(text=str(v))


class SystemInfoWidget(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        
        ctk.CTkLabel(self, text="💻  Tài nguyên Hệ thống", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=20, pady=(16, 10))
        
        self.bars = {}
        for name, color in [("CPU", "#e74c3c"), ("RAM", "#3498db"), ("Disk", "#2ecc71")]:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)
            
            header = ctk.CTkFrame(row, fg_color="transparent")
            header.pack(fill="x", pady=(0, 4))
            
            ctk.CTkLabel(header, text=name, font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(side="left")
            lbl_val = ctk.CTkLabel(header, text="--%", font=("Segoe UI", 11, "bold"), text_color=color)
            lbl_val.pack(side="right")
            
            pb = ctk.CTkProgressBar(row, height=8, progress_color=color, fg_color=BG_DARK, corner_radius=4)
            pb.pack(fill="x")
            pb.set(0)
            
            self.bars[name] = (pb, lbl_val)
            
    def update_stats(self):
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            self.bars["CPU"][0].set(cpu / 100)
            self.bars["CPU"][1].configure(text=f"{cpu:.1f}%")
            
            self.bars["RAM"][0].set(ram / 100)
            self.bars["RAM"][1].configure(text=f"{ram:.1f}%")
            
            self.bars["Disk"][0].set(disk / 100)
            self.bars["Disk"][1].configure(text=f"{disk:.1f}%")
        except ImportError:
            for n in ["CPU", "RAM", "Disk"]:
                self.bars[n][1].configure(text="N/A")


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
            hover_color=BG_CARD,
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
import math
import tkinter as tk

class DonutChart(ctk.CTkFrame):
    def __init__(self, master, title="Biểu đồ", **kwargs):
        # Mặc định nền trong suốt nếu không truyền fg_color
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.canvas_size = 150
        self.thickness = 22
        
        # Tiêu đề
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 0))
        
        # Canvas
        self.canvas = tk.Canvas(self, width=self.canvas_size, height=self.canvas_size, bg=BG_CARD, highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=(20, 10), pady=(10, 20), sticky="e")
        
        # Legend Frame
        self.legend_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.legend_frame.grid(row=1, column=1, padx=(10, 20), pady=(10, 20), sticky="w")
        
    def update_data(self, data):
        self.canvas.delete("all")
        for widget in self.legend_frame.winfo_children():
            widget.destroy()
            
        total = sum(v for _, v, _ in data)
        if total == 0:
            self.canvas.create_oval(15, 15, self.canvas_size-15, self.canvas_size-15, outline=BG_DARK, width=self.thickness)
            self._draw_center_text(0)
            return
            
        start_angle = 90
        for label, val, color in data:
            if val == 0: continue
            extent = (val / total) * 360
            self.canvas.create_arc(15, 15, self.canvas_size-15, self.canvas_size-15,
                                   start=start_angle, extent=extent, style=tk.ARC, outline=color, width=self.thickness)
            start_angle += extent
            
            # Draw Legend Item
            row = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
            row.pack(fill="x", pady=6)
            
            dot = tk.Canvas(row, width=12, height=12, bg=BG_CARD, highlightthickness=0)
            dot.create_oval(2, 2, 10, 10, fill=color, outline=color)
            dot.pack(side="left", padx=(0, 8))
            
            percent = int((val/total)*100)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).pack(side="left")
            ctk.CTkLabel(row, text=f"  {val} ({percent}%)", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="right")
            
        self._draw_center_text(total)
        
    def _draw_center_text(self, total):
        self.canvas.create_text(self.canvas_size/2, self.canvas_size/2 - 10, text="Tổng số", font=("Segoe UI", 11), fill=TEXT_DIM)
        self.canvas.create_text(self.canvas_size/2, self.canvas_size/2 + 10, text=str(total), font=("Segoe UI", 20, "bold"), fill="white")


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
        self._card_role = StatsCard(self, "Tài khoản", value="User", color="#3498db", icon="👤")
        self._card_expire = StatsCard(self, "Ngày Hết Hạn", value="Chưa có", color="#e67e22", icon="⏳")
        self._card_status = StatsCard(self, "Trạng Thái", value="Active", color="#2ecc71", icon="🟢")
        self._card_features = StatsCard(self, "Chức năng", value="Mở khóa (Full)", color="#9b59b6", icon="💎")
        
        for col, card in enumerate([self._card_role, self._card_expire, self._card_status, self._card_features]):
            card.grid(row=2, column=col, padx=6, pady=4, sticky="ew")

        # Stats cards - Local
        self._card_crawled   = StatsCard(self, "Đã Crawl",   color=ACCENT, icon="📥")
        self._card_processed = StatsCard(self, "Đã Xử lý",   color=ACCENT, icon="⚙")
        self._card_posted    = StatsCard(self, "Đã Upload",   color=SUCCESS, icon="📤")
        self._card_pending   = StatsCard(self, "Chờ Upload",  color=WARNING, icon="⏳")

        for col, card in enumerate([
            self._card_crawled, self._card_processed,
            self._card_posted, self._card_pending
        ]):
            card.grid(row=3, column=col, padx=6, pady=4, sticky="ew")

        # Performance Chart
        self._chart = DonutChart(self, title="📈  Tiến Độ Tổng Quan", fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._chart.grid(row=4, column=0, sticky="nsew", padx=(4, 2), pady=(20, 0))
        
        # System Info
        self._sys_info = SystemInfoWidget(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._sys_info.grid(row=4, column=1, sticky="nsew", padx=(2, 2), pady=(20, 0))

        # Recent activity log
        log_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        log_frame.grid(row=4, column=2, columnspan=2, sticky="nsew", padx=(2, 4), pady=(20, 0))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

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
                if is_expired:
                    self._card_status.set_value("HẾT HẠN")
                    self._card_features.set_value("Đã khóa")
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
        self._spin_count.insert(0, "1000")
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

        ctk.CTkLabel(self._frame_file, text="Giới hạn (Profile):", font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self._spin_count_file = ctk.CTkEntry(self._frame_file, width=80, font=("Segoe UI", 12), fg_color=BG_DARK, border_color=BORDER)
        self._spin_count_file.insert(0, "150")
        self._spin_count_file.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=4)

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
        results = asyncio.run(crawler.crawl_multiple_videos(urls))
        self._log(f"✅ Crawled {len(results)} videos!", "SUCCESS")
        auth_client.send_telemetry("CRAWL", f"Tải xong {len(results)} video từ list URL")

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
        auth_client.send_telemetry("CRAWL", f"Tải xong {len(results)} video từ profile: {profile}")

    def _do_crawl_file(self, file_path, limit=150):
        from crawler.douyin_crawler import DouyinCrawler
        from database.db_manager import DatabaseManager
        from auth_client import auth_client
        
        try:
            urls = Path(file_path).read_text(encoding="utf-8").strip().splitlines()
        except Exception as e:
            self._log(f"❌ Lỗi đọc file: {e}", "ERROR")
            self._on_task_done()
            return
            
        urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]
        if not urls:
            self._log(f"❌ File rỗng hoặc không có URL hợp lệ!", "ERROR")
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
            
        self._log(f"✅ Tổng cộng cào thành công {total_crawled} video!", "SUCCESS")
        auth_client.send_telemetry("CRAWL", f"Tải xong {total_crawled} video từ file .txt")

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
        self._progress_bars = {} # {video_id: CTkProgressBar}
        self._progress_labels = {} # {video_id: CTkLabel}
        self._progress_labels = {} # {video_id: CTkLabel}
        self._selected_music_path = None
        self._build()
        self.after(200, self._load_videos)
        self.after(300, self._load_process_config)

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
        self._opt_author_filter = ctk.CTkOptionMenu(list_header, values=["Tất cả Kênh"], width=130, command=lambda _: self._load_videos())
        self._opt_author_filter.pack(side="left", padx=(10, 0))
        
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
        self._entry_limit.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(4, 14))

        # Cấu hình xếp dọc theo Sidebar
        config_frame = ctk.CTkFrame(opts, fg_color="transparent")
        config_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

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
        self._sw_subtitle = ctk.CTkSwitch(sub_frame, text="Auto-Vietsub ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, cursor="hand2")
        self._sw_subtitle.select()
        self._sw_subtitle.pack(side="left")
        ToolTip(self._sw_subtitle, "Tự động trích xuất phụ đề gốc, dịch sang tiếng Việt và gắn cứng (hardsub) lên video mới.")
        
        self._opt_sub_pos = ctk.CTkOptionMenu(
            sub_frame, values=["Đè lên vùng mờ", "Cao (Tránh TikTok UI)", "Giữa màn hình"], 
            width=130, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_sub_pos.set("Đè lên vùng mờ")
        self._opt_sub_pos.pack(side="left", padx=(10, 0))

        self._sw_blur = ctk.CTkSwitch(row2, text="Làm mờ phụ đề gốc ❔", font=("Segoe UI", 11), text_color=TEXT_MAIN, cursor="hand2")
        self._sw_blur.select()
        self._sw_blur.pack(anchor="w", pady=(0, 10))
        ToolTip(self._sw_blur, "Tạo một dải mờ (blur) ở dưới cùng hoặc trên cùng để che đi chữ Trung Quốc cũ.")

        blur_tools = ctk.CTkFrame(row2, fg_color="transparent")
        blur_tools.pack(fill="x")
        lbl_blur_h = ctk.CTkLabel(blur_tools, text="Vùng làm mờ: ❔", font=("Segoe UI", 11), text_color=TEXT_DIM, cursor="hand2")
        lbl_blur_h.pack(side="left", padx=(0, 5))
        ToolTip(lbl_blur_h, "Kích thước của dải làm mờ tính theo % chiều cao video (15% là mức tối ưu).")
        self._entry_blur_height = ctk.CTkEntry(blur_tools, width=45, placeholder_text="15%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_blur_height.insert(0, "15%")
        self._entry_blur_height.pack(side="left", padx=(0, 10))
        
        self._opt_blur_pos = ctk.CTkOptionMenu(blur_tools, values=["Dưới cùng", "Trên cùng"], width=100, font=("Segoe UI", 11), fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD)
        self._opt_blur_pos.set("Dưới cùng")
        self._opt_blur_pos.pack(side="left")
        
        ctk.CTkLabel(row2, text="💡 Gán API Key (Gemini/Groq) ở mục Settings để AI dịch Sub chuẩn nhất", font=("Segoe UI", 10, "italic"), text_color="#F9A826").pack(anchor="w", pady=(10, 0))

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
        self._opt_voice.set("Giọng Nữ")
        self._opt_voice.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(voice_tools, text="Tốc độ:", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(0, 5))
        self._entry_tts_rate = ctk.CTkEntry(voice_tools, width=45, placeholder_text="0%", font=("Segoe UI", 11), fg_color=BG_DARK, border_color=BORDER)
        self._entry_tts_rate.insert(0, "0%")
        self._entry_tts_rate.pack(side="left", padx=(0, 5))
        
        def _on_tts_slider(val):
            self._entry_tts_rate.delete(0, "end")
            self._entry_tts_rate.insert(0, f"{int(val)}%")
            
        self._slider_tts_rate = ctk.CTkSlider(voice_tools, from_=-50, to=50, width=80, command=_on_tts_slider)
        self._slider_tts_rate.set(0)
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
            
            id_lbl = ctk.CTkLabel(info_frame, text=f"ID: {vid}", font=("Segoe UI", 10), text_color=ACCENT)
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
            "opt_logo_pos": self._opt_logo_pos.get()
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
                if "opt_blur_pos" in config: self._opt_blur_pos.set(config["opt_blur_pos"])
                if "opt_logo_pos" in config: self._opt_logo_pos.set(config["opt_logo_pos"])
                
                if "blur_height" in config:
                    self._entry_blur_height.delete(0, "end")
                    self._entry_blur_height.insert(0, config["blur_height"])
                if "bg_vol" in config:
                    self._entry_bg_vol.delete(0, "end")
                    self._entry_bg_vol.insert(0, config["bg_vol"])
                    
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
            except:
                pass

    def _start_process(self):
        from auth_client import auth_client
        if auth_client.user_info and auth_client.user_info.get("is_expired", True):
            messagebox.showerror("Bản quyền", "Tài khoản của bạn đã hết hạn. Vui lòng gia hạn để tiếp tục sử dụng!")
            return
            
        role = auth_client.user_info.get("role", "user") if auth_client.user_info else "user"
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        
        # Kiểm tra giới hạn Role
        if role != "admin":
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            today_count = db.get_today_processed_count(username=username)
            if today_count >= 10:
                messagebox.showerror("Giới hạn", "Tài khoản của bạn đã đạt giới hạn 10 video process/ngày. Vui lòng nâng cấp gói hoặc liên hệ Admin!")
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
        self._run_in_thread(self._do_process, title, limit, username)

    def _do_process(self, title, limit, username):
        from processor.video_processor import VideoProcessor
        from database.db_manager import DatabaseManager
        from config.settings import PROCESSOR_CONFIG
        
        def progress_cb(vid, pct, status):
            # Hàm này được gọi từ thread, dùng after để update UI an toàn
            def update_ui():
                if "Lỗi" in status or "Error" in status:
                    self._log(f"[{vid[:10]}] {status}", "ERROR")
                elif "DEBUG" in status:
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
                
        results = processor.process_downloaded_videos(
            titles=titles, 
            limit=limit, 
            video_ids=selected_ids, 
            cancel_check=lambda: self.cancel_flag,
            progress_callback=progress_cb
        )
        if self.cancel_flag:
            self._log("Đã ngắt quá trình xử lý (Stop).", "WARNING")
        else:
            self._log(f"✅ Đã xử lý {len(results)} videos!", "SUCCESS")
            from auth_client import auth_client
            auth_client.send_telemetry("PROCESS", f"Hoàn thành xử lý {len(results)} video (Blur: {PROCESSOR_CONFIG.get('blur_enabled')}, Sub: {PROCESSOR_CONFIG.get('subtitle_overlay')}, TTS: {PROCESSOR_CONFIG.get('tts_voice')})")
        # Load lại danh sách sau khi xử lý xong
        self.after(0, self._load_videos)
        self._on_task_done()

    def _on_task_done(self):
        super()._on_task_done()
        self.is_running = False
        self.after(0, lambda: self._btn_process.configure(state="normal", text="▶  Bắt đầu Xử lý", fg_color=ACCENT, hover_color=ACCENT_HOVER))
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

    @staticmethod
    def _get_facebook_accounts():
        user_dir = UploadTab._get_user_cookies_dir()
        accounts = [f.name for f in user_dir.glob("facebook_*.json")]
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
        self._opt_author_filter_up = ctk.CTkOptionMenu(list_header, values=["Tất cả Kênh"], width=130, command=lambda _: self._load_videos())
        self._opt_author_filter_up.pack(side="left", padx=(10, 0))
        
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
        self._sw_platform_yt.pack(side="left", padx=(0, 20))
        
        self._sw_platform_fb = ctk.CTkSwitch(row2, text="Facebook", font=("Segoe UI", 11))
        self._sw_platform_fb.select()
        self._sw_platform_fb.pack(side="left")

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
            fg_color=BORDER, hover_color=BG_CARD, command=lambda: self.app._nav(5)
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
            fg_color=BORDER, hover_color=BG_CARD, command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc_yt.pack(side="left")

        ctk.CTkFrame(config_frame, height=1, fg_color=BORDER).pack(fill="x", pady=10) # Divider

        # --- Tài khoản Facebook ---
        ctk.CTkLabel(config_frame, text="Tài khoản Facebook mặc định", font=("Segoe UI", 12, "bold"), text_color=ACCENT).pack(anchor="w", pady=(0, 5))
        
        row5 = ctk.CTkFrame(config_frame, fg_color="transparent")
        row5.pack(fill="x", pady=(0, 12))
        
        fb_accounts = self._get_facebook_accounts()
        self._opt_account_fb = ctk.CTkOptionMenu(
            row5, values=fb_accounts, font=("Segoe UI", 11),
            fg_color=BG_DARK, button_color=BORDER, button_hover_color=BG_CARD
        )
        self._opt_account_fb.pack(fill="x", pady=(0, 5))
        
        fb_btns = ctk.CTkFrame(row5, fg_color="transparent")
        fb_btns.pack(fill="x")
        self._btn_apply_acc_fb = ctk.CTkButton(
            fb_btns, text="Áp dụng All", width=90, height=24, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=self._apply_account_to_all_fb
        )
        self._btn_apply_acc_fb.pack(side="left", padx=(0, 10))
        
        self._btn_manage_acc_fb = ctk.CTkButton(
            fb_btns, text="⚙ Quản lý", width=70, height=24, font=("Segoe UI", 11),
            fg_color=BORDER, hover_color=BG_CARD, command=lambda: self.app._nav(5)
        )
        self._btn_manage_acc_fb.pack(side="left")

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
        
        author_val = self._opt_author_filter_up.get() if hasattr(self, "_opt_author_filter_up") else "Tất cả Kênh"
        if hasattr(self, "_opt_author_filter_up"):
            authors = db.get_authors(status="processed", username=current_user)
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
            
            # --- ROW 1: Header (Checkbox, ID, Size, Xem, Tài khoản) ---
            row1 = ctk.CTkFrame(card, fg_color="transparent")
            row1.pack(fill="x", padx=10, pady=(10, 5))
            
            cb = ctk.CTkCheckBox(row1, text="", variable=var, width=24, command=self._update_selected_count)
            cb.pack(side="left")
            
            ctk.CTkLabel(row1, text=f"ID: {vid}", font=("Consolas", 11, "bold"), text_color=ACCENT).pack(side="left", padx=5)
            
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
                    row1, text="▶ Xem", width=50, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda p=path: os.startfile(p) if os.name == 'nt' else None
                ).pack(side="left", padx=(0, 15))
            elif drive_id:
                ctk.CTkLabel(row1, text="☁️ Google Drive", font=("Segoe UI", 11), text_color=ACCENT).pack(side="left", padx=(5, 10))
                ctk.CTkButton(
                    row1, text="☁️ Xem Drive", width=80, font=("Segoe UI", 11),
                    fg_color=BORDER, hover_color=BG_CARD,
                    command=lambda d_id=drive_id: webbrowser.open(f"https://drive.google.com/file/d/{d_id}/view")
                ).pack(side="left", padx=(0, 15))
            else:
                ctk.CTkLabel(row1, text=f"📦 {size_mb:.1f} MB", font=("Segoe UI", 11), text_color=TEXT_DIM).pack(side="left", padx=(5, 10))
                
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
                
            btn_save = ctk.CTkButton(row4, text="💾 Lưu Caption", width=120, height=26, font=("Segoe UI", 12, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER, command=make_save_cmd(vid, textbox))
            btn_save.pack(side="left")
            
            btn_apply_all = ctk.CTkButton(row4, text="📑 Áp dụng cho Video đã chọn", width=160, height=26, font=("Segoe UI", 12, "bold"), fg_color=BORDER, hover_color=BG_CARD, command=make_apply_all_cmd(textbox))
            btn_apply_all.pack(side="left", padx=(10, 0))

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
        do_fb = self._sw_platform_fb.get() == 1
        
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
        
        from auth_client import auth_client
        current_user = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        
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
                    
                uploader = TikTokUploader(db=db, cookies_file=cookies_path, proxy=proxy_str, username=current_user)
                
                captions_to_pass = {
                    vid: custom_captions_dict[vid] 
                    for vid in vids_to_upload if vid in custom_captions_dict
                }
                
                try:
                    results = await uploader.upload_pending_videos(
                        limit=len(vids_to_upload), 
                        video_ids=vids_to_upload,
                        custom_captions=captions_to_pass,
                        cancel_check=lambda: self.cancel_flag
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
                yt_uploader = YouTubeUploader(db=db, token_file=token_path, username=current_user)
                
                captions_to_pass = {
                    vid: custom_captions_dict[vid] 
                    for vid in vids_to_upload if vid in custom_captions_dict
                }
                
                try:
                    results = await yt_uploader.upload_pending_videos(
                        limit=len(vids_to_upload), 
                        video_ids=vids_to_upload,
                        custom_captions=captions_to_pass,
                        cancel_check=lambda: self.cancel_flag
                    )
                    total_uploaded += len(results)
                    self._log(f"✅ Upload xong {len(results)} videos lên YouTube ({account_file})!", "SUCCESS")
                except Exception as e:
                    self._log(f"Lỗi upload YouTube {account_file}: {e}", "ERROR")
                finally:
                    await yt_uploader.close()

        if do_fb:
            from uploader.facebook_uploader import FacebookUploader
            total_uploaded = 0
            for account_file, vids in account_groups_fb.items():
                if total_uploaded >= limit:
                    break
                    
                vids_to_upload = vids[:limit - total_uploaded]
                self._log(f"Bắt đầu upload {len(vids_to_upload)} video lên Facebook Reels bằng {account_file}...", "INFO")
                user_dir = self._get_user_cookies_dir()
                token_path = str(user_dir / account_file)
                fb_uploader = FacebookUploader(db=db, token_file=token_path, username=current_user)
                
                captions_to_pass = {
                    vid: custom_captions_dict[vid] 
                    for vid in vids_to_upload if vid in custom_captions_dict
                }
                
                try:
                    results = await fb_uploader.upload_pending_videos(
                        limit=len(vids_to_upload), 
                        video_ids=vids_to_upload,
                        custom_captions=captions_to_pass,
                        cancel_check=lambda: self.cancel_flag
                    )
                    total_uploaded += len(results)
                    self._log(f"✅ Upload xong {len(results)} videos lên Facebook Reels ({account_file})!", "SUCCESS")
                except Exception as e:
                    self._log(f"Lỗi upload Facebook Reels {account_file}: {e}", "ERROR")
                finally:
                    await fb_uploader.close()
                
        self.after(0, self._load_videos)
        self._on_task_done()


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

    def _do_upload(self, limit, selected_vids, custom_captions_dict, video_accounts_tt_dict, video_accounts_yt_dict, cleanup_upload, do_tt, do_yt):
        from config.settings import TIKTOK_CONFIG, YOUTUBE_CONFIG
        TIKTOK_CONFIG["auto_cleanup_after_upload"] = cleanup_upload
        YOUTUBE_CONFIG["auto_cleanup_after_upload"] = cleanup_upload

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
        
        self.tabview = ctk.CTkTabview(self, fg_color="transparent")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.tab_tiktok = self.tabview.add("🎵 TikTok")
        self.tab_youtube = self.tabview.add("▶️ YouTube")
        self.tab_facebook = self.tabview.add("📘 Facebook Reels")
        
        self._build_tiktok_tab()
        self._build_youtube_tab()
        self._build_facebook_tab()
        
    def _build_tiktok_tab(self):
        hdr = ctk.CTkFrame(self.tab_tiktok, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(hdr, text="Quản lý Tài khoản TikTok", font=("Segoe UI", 16, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="🔄 Làm mới", width=70, height=28, fg_color=BORDER, hover_color=BG_CARD, command=self._load_accounts).pack(side="right", padx=5)
        ctk.CTkButton(hdr, text="💾 Lưu cấu hình Proxy", width=140, height=28, fg_color="#2980b9", hover_color="#3498db", command=self._save_all_proxies_manual).pack(side="right", padx=(0, 5))
        ctk.CTkButton(hdr, text="📁 Tải JSON", width=90, height=28, fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._upload_account).pack(side="right", padx=(0, 5))
        ctk.CTkButton(hdr, text="➕ Thêm nick mới", width=120, height=28, fg_color=SUCCESS, hover_color="#27ae60", command=self._add_new_account).pack(side="right", padx=(0, 5))
        
        self._list_frame = ctk.CTkScrollableFrame(self.tab_tiktok, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._list_frame.pack(fill="both", expand=True)
        
        self._proxy_entries = {}
        self._load_accounts()

    def _on_proxy_changed(self, acc_name=None):
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)

    def _save_all_proxies_manual(self):
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        from tkinter import messagebox
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        self._save_proxies(user_dir)
        messagebox.showinfo("Thành công", "Đã lưu toàn bộ cấu hình Proxy cho các tài khoản!")

    def _build_youtube_tab(self):
        ctk.CTkLabel(self.tab_youtube, text="Danh sách tài khoản YouTube (Token):", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 8))
        
        self._yt_list_frame = ctk.CTkScrollableFrame(self.tab_youtube, fg_color=BG_DARK, border_color=BORDER, border_width=1)
        self._yt_list_frame.pack(fill="both", expand=True, pady=(0, 16))
        
        secret_frame = ctk.CTkFrame(self.tab_youtube, fg_color="transparent")
        secret_frame.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(secret_frame, text="Client Secret (File):", font=("Segoe UI", 12)).pack(side="left")
        self._secret_entry = ctk.CTkEntry(secret_frame, font=("Segoe UI", 11), width=250)
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
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
        
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        
        accounts = [f.name for f in user_dir.glob("tiktok_*.json")]
        if not accounts:
            ctk.CTkLabel(self._list_frame, text="Chưa có tài khoản nào.", text_color=TEXT_DIM).pack(pady=20)
            return
        
        saved_proxies = self._load_proxies(user_dir)
            
        for acc in accounts:
            row = ctk.CTkFrame(self._list_frame, fg_color=BG_DARK, corner_radius=8, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=4, ipady=2)
            row.grid_columnconfigure(1, weight=1)
            
            display_acc = acc.replace("tiktok_", "").replace(".json", "")
            if len(display_acc) > 15:
                display_acc = display_acc[:12] + "..."
                
            ctk.CTkLabel(row, text=display_acc, font=("Segoe UI", 13, "bold"), text_color=ACCENT, width=120, anchor="w").grid(row=0, column=0, padx=(12, 10), pady=10, sticky="w")
            
            proxy_frame = ctk.CTkFrame(row, fg_color="transparent")
            proxy_frame.grid(row=0, column=1, sticky="ew", padx=10)
            proxy_frame.grid_columnconfigure(1, weight=1)
            
            ctk.CTkLabel(proxy_frame, text="🌐 Proxy:", font=("Segoe UI", 11), text_color=TEXT_DIM).grid(row=0, column=0, padx=(0, 8))
            proxy_entry = ctk.CTkEntry(
                proxy_frame, height=28, font=("Consolas", 11),
                placeholder_text="ip:port:user:pass", fg_color=BG_CARD, border_color=BORDER
            )
            proxy_entry.grid(row=0, column=1, sticky="ew")
            
            if acc in saved_proxies and saved_proxies[acc]:
                proxy_entry.insert(0, saved_proxies[acc])
            self._proxy_entries[acc] = proxy_entry
            
            # Tự động lưu proxy khi chỉnh sửa hoặc chuyển ô
            proxy_entry.bind("<FocusOut>", lambda e, a=acc: self._on_proxy_changed(a))
            proxy_entry.bind("<KeyRelease>", lambda e, a=acc: self._on_proxy_changed(a))
            
            btn_login = ctk.CTkButton(
                row, text="🔑 Login", width=70, height=28, font=("Segoe UI", 11, "bold"),
                fg_color=BORDER, hover_color=BG_CARD, text_color=TEXT_MAIN,
                command=lambda a=acc: self._manual_login(a)
            )
            btn_login.grid(row=0, column=2, padx=(0, 5))
            btn_login_cloak = ctk.CTkButton(
                row, text="🌐 Cloak Login", width=90, height=28, font=("Segoe UI", 11, "bold"),
                fg_color="#8E44AD", hover_color="#9B59B6", text_color="white",
                command=lambda a=acc: self._manual_login(a, use_cloak=True)
            )
            btn_login_cloak.grid(row=0, column=3, padx=(0, 5))

            
            btn_edit = ctk.CTkButton(
                row, text="Sửa", width=50, height=28, font=("Segoe UI", 11),
                fg_color=WARNING, hover_color="#d35400",
                command=lambda a=acc: self._edit_account(a)
            )
            btn_edit.grid(row=0, column=4, padx=(0, 5))
            
            btn_delete = ctk.CTkButton(
                row, text="Xóa", width=50, height=28, font=("Segoe UI", 11),
                fg_color=DANGER, hover_color="#c0392b",
                command=lambda a=acc: self._delete_tiktok_account(a)
            )
            btn_delete.grid(row=0, column=5, padx=(0, 12))

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
        from tkinter import messagebox
        messagebox.showinfo("Thành công", f"Đã tạo {acc_name}. Hãy điền Proxy và bấm '🔑 Login' để lưu phiên!")

    def _manual_login(self, acc_name, force_no_proxy=False, use_cloak=False):
        proxy_str = None
        if not force_no_proxy:
            proxy_str = self._proxy_entries[acc_name].get().strip()
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
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
                    await uploader._init_browser()
                    tiktok_page = await uploader.context.new_page()
                    await tiktok_page.goto("https://www.tiktok.com/")
                    while len(uploader.context.pages) > 0:
                        try:
                            await uploader.context.pages[0].title()
                            await asyncio.sleep(1)
                        except:
                            break
                    await uploader.close()
                asyncio.run(_run())
                
                def _on_succ():
                    from tkinter import messagebox
                    messagebox.showinfo("Thành công", f"Đã đóng trình duyệt và lưu phiên đăng nhập cho {acc_name}.")
                self.after(0, _on_succ)
                
            except Exception as e:
                err_msg = str(e)
                def _on_err():
                    from tkinter import messagebox
                    if "Lỗi Proxy" in err_msg or "net::ERR_" in err_msg or "Timeout" in err_msg:
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
        user_dir = COOKIES_DIR / username
        accounts = [f.name for f in user_dir.glob("youtube_*.json")]
            
        for acc in accounts:
            item = ctk.CTkFrame(self._yt_list_frame, fg_color=BG_CARD, corner_radius=6)
            item.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(item, text=acc, font=("Consolas", 12)).pack(side="left", padx=10, pady=8)
            ctk.CTkButton(item, text="Xóa", width=50, fg_color=DANGER, hover_color="#c0392b", command=lambda a=acc: self._delete_yt_account(a)).pack(side="right", padx=10, pady=8)

    def _delete_yt_account(self, name):
        from tkinter import messagebox
        import os
        if messagebox.askyesno("Xác nhận", f"Xóa tài khoản YouTube: {name}?"):
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
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
        self._fb_list_frame.pack(fill="both", expand=True, pady=(0, 16))
        
        form_frame = ctk.CTkFrame(self.tab_facebook, fg_color=BG_CARD, corner_radius=8, border_width=1, border_color=BORDER)
        form_frame.pack(fill="x", pady=(0, 8), padx=4, ipady=8)
        
        ctk.CTkLabel(form_frame, text="Thêm Fanpage Mới (Graph API):", font=("Segoe UI", 13, "bold"), text_color=ACCENT).pack(anchor="w", padx=12, pady=(0, 6))
        
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
        
        self._load_fb_accounts()

    def _load_fb_accounts(self):
        for widget in self._fb_list_frame.winfo_children():
            widget.destroy()
            
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        import json
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        accounts = [f.name for f in user_dir.glob("facebook_*.json")]
        
        if not accounts:
            ctk.CTkLabel(self._fb_list_frame, text="Chưa có Fanpage Facebook nào.", text_color=TEXT_DIM).pack(pady=20)
            return
            
        for acc in accounts:
            item = ctk.CTkFrame(self._fb_list_frame, fg_color=BG_CARD, corner_radius=6)
            item.pack(fill="x", pady=4, padx=4)
            
            # Read info
            page_name = acc
            try:
                with open(user_dir / acc, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    page_name = f"{data.get('page_name', acc)} (ID: {data.get('page_id', 'N/A')})"
            except Exception:
                pass
                
            ctk.CTkLabel(item, text=f"📘 {page_name}", font=("Segoe UI", 12, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(item, text=f"[{acc}]", font=("Consolas", 11), text_color=TEXT_DIM).pack(side="left", padx=5)
            ctk.CTkButton(item, text="Xóa", width=50, fg_color=DANGER, hover_color="#c0392b", command=lambda a=acc: self._delete_fb_account(a)).pack(side="right", padx=10, pady=8)

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
            self._btn_add_fb.configure(text="🔍 Kiểm tra & Thêm", state="normal")
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
            user_dir = COOKIES_DIR / username
            user_dir.mkdir(parents=True, exist_ok=True)
            
            idx = 1
            while (user_dir / f"facebook_{idx}.json").exists():
                idx += 1
            new_file = f"facebook_{idx}.json"
            
            save_data = {
                "page_id": real_page_id,
                "page_name": page_name,
                "page_access_token": real_token,
                "created_at": str(Path(__file__).stat().st_mtime)
            }
            with open(user_dir / new_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
                
            self._fb_page_id_entry.delete(0, "end")
            self._fb_token_entry.delete(0, "end")
            self._fb_name_entry.delete(0, "end")
            messagebox.showinfo("Thành công", f"Đã thêm Fanpage: {page_name} ({new_file})")
            self._load_fb_accounts()
            
        threading.Thread(target=_verify, daemon=True).start()

    def _delete_fb_account(self, name):
        from tkinter import messagebox
        import os
        if messagebox.askyesno("Xác nhận", f"Xóa tài khoản Facebook: {name}?"):
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            user_dir = COOKIES_DIR / username
            path = user_dir / name
            try:
                if path.exists():
                    os.remove(path)
                self._load_fb_accounts()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa: {e}")


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
        row1.grid_columnconfigure(5, weight=1) # Đẩy nút Start sang phải

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


        self._btn_start = ctk.CTkButton(
            row1, text="▶  Bắt đầu Nuôi", height=36, font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60", command=self._start_farm
        )
        self._btn_start.grid(row=0, column=5, sticky="e")

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
        ctk.CTkButton(hdr, text="☑ Chọn tất cả", width=90, height=24, command=self._toggle_all).pack(side="right", padx=(0, 10))
        
        self._list_frame = ctk.CTkScrollableFrame(acc_frame, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Log
        log_frame = ctk.CTkFrame(split, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        log_frame.grid(row=0, column=1, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        self._log_widget = LogWidget(log_frame)
        self._log_widget.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)


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
        self._run_in_thread(self._do_farm, selected, selected_flow, proxies, max_concurrent=threads)

    async def _do_farm(self, accounts, flow, proxies=None, max_concurrent=3):
        import random
        import asyncio
        from uploader.tiktok_uploader import TikTokUploader
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        
        proxies = proxies or {}
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
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
                
                self._log(f"-------------------------------------", "INFO")
                self._log(f"{prefix} 🌱 Bắt đầu Kịch bản: {flow.get('name')}", "INFO")
                if proxy_str:
                    display_proxy = proxy_str.split("@")[-1] if "@" in proxy_str else proxy_str
                    self._log(f"{prefix} 🌐 Proxy: {display_proxy}", "INFO")
                else:
                    self._log(f"{prefix} ⚠️ Dùng mạng thật (Không Proxy)", "WARNING")
                
                uploader = TikTokUploader(cookies_file=cookie_path, proxy=proxy_str, window_idx=idx)
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
        self.refresh_ui()

    def refresh_ui(self):
        for widget in self.winfo_children():
            widget.destroy()
            
        from auth_client import auth_client
        role = auth_client.user_info.get("role", "user") if auth_client.user_info else "user"
        
        if role in ("admin", "super_admin"):
            self._build_admin()
        else:
            self._build_user()

    def _build_user(self):
        ctk.CTkLabel(
            self, text="💎  Bản Quyền & Gia Hạn",
            font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        from auth_client import auth_client
        expire_date = auth_client.user_info.get("expire_date", "Chưa có") if auth_client.user_info else "Chưa có"
        is_expired = auth_client.user_info.get("is_expired", True) if auth_client.user_info else True
        
        status_color = DANGER if is_expired else SUCCESS
        status_text = "Đã hết hạn" if is_expired else "Đang hoạt động"
        
        plan_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=status_color)
        plan_frame.grid(row=1, column=0, sticky="ew")
        
        ctk.CTkLabel(plan_frame, text="Trạng thái:", font=("Segoe UI", 16)).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        ctk.CTkLabel(plan_frame, text=status_text, font=("Segoe UI", 18, "bold"), text_color=status_color).grid(row=0, column=1, pady=(20, 10), sticky="w")
        
        ctk.CTkLabel(plan_frame, text="Ngày Hết Hạn:", font=("Segoe UI", 16)).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
        ctk.CTkLabel(plan_frame, text=expire_date, font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN).grid(row=1, column=1, pady=(0, 20), sticky="w")
        
        ctk.CTkButton(
            plan_frame, text="Gia Hạn (Thanh Toán QR)", fg_color=ACCENT, hover_color=ACCENT_HOVER, 
            command=self._show_payment_dialog
        ).grid(row=0, column=2, rowspan=2, padx=20, pady=20, sticky="e")
        
        plan_frame.grid_columnconfigure(1, weight=1)
        
        # ── Gemini API Key (Người dùng tự điền) ──
        ctk.CTkLabel(
            self, text="🔑  Tự Túc API Key (Sử dụng AI Tốc độ cao)",
            font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN,
        ).grid(row=2, column=0, sticky="w", pady=(30, 10))
        
        ai_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        ai_frame.grid(row=3, column=0, sticky="ew")
        ai_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(ai_frame, text="Gemini API Key:", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, padx=16, pady=16)
        
        self._entry_user_gemini = ctk.CTkEntry(ai_frame, font=("Consolas", 12), fg_color=BG_DARK, border_color=BORDER, show="*")
        self._entry_user_gemini.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=16)
        
        btn_toggle_user_key = ctk.CTkButton(
            ai_frame, text="👁", width=30, height=28, fg_color="transparent", hover_color=BG_CARD, text_color=TEXT_DIM,
            command=lambda: self._entry_user_gemini.configure(show="" if self._entry_user_gemini.cget("show") == "*" else "*")
        )
        btn_toggle_user_key.grid(row=0, column=2, padx=(0, 16), pady=16)
        
        # Load existing key
        import os
        existing_key = os.getenv("GEMINI_API_KEY", "")
            
        if existing_key:
            self._entry_user_gemini.insert(0, existing_key)
            
        btn_save_key = ctk.CTkButton(
            ai_frame, text="💾 Lưu Key", width=100, font=("Segoe UI", 12, "bold"),
            fg_color=SUCCESS, hover_color="#27ae60",
            command=self._save_user_gemini_key
        )
        btn_save_key.grid(row=0, column=3, padx=(0, 16), pady=16)
        
        ctk.CTkLabel(
            ai_frame, text="*Sử dụng API Key cá nhân để mở khóa tính năng AI mạnh mẽ nhất mà không phụ thuộc Server.", 
            font=("Segoe UI", 11, "italic"), text_color=TEXT_DIM
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 16))

        self._build_drive_settings()

    def _build_drive_settings(self):
        ctk.CTkLabel(
            self, text="☁️  Google Drive Backup",
            font=("Segoe UI", 18, "bold"), text_color=TEXT_MAIN,
        ).grid(row=4, column=0, sticky="w", pady=(30, 10))

        drive_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        drive_frame.grid(row=5, column=0, sticky="ew")
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


    def _save_user_gemini_key(self):
        gemini_key = self._entry_user_gemini.get().strip()
        from config.settings import BASE_DIR
        env_path = BASE_DIR / ".env"
        from dotenv import set_key
        set_key(env_path, "GEMINI_API_KEY", gemini_key)
            
        import os
        os.environ["GEMINI_API_KEY"] = gemini_key # Update immediately in current process
            
        messagebox.showinfo(
            "Đã lưu",
            "Đã lưu Gemini API Key. Bạn có thể sử dụng các tính năng AI không giới hạn!"
        )
        self.app._update_user_ui()

    def _show_payment_dialog(self):
        from auth_client import auth_client
        success, payment_info = auth_client.get_payment_info()
        if not success or not payment_info.get("bank_bin"):
            messagebox.showerror("Lỗi", "Hệ thống chưa cấu hình thanh toán. Vui lòng liên hệ Admin!")
            return
            
        win = ctk.CTkToplevel(self)
        win.title("Gia Hạn Bản Quyền")
        win.geometry("500x650")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        
        ctk.CTkLabel(win, text="Thanh Toán Qua VietQR", font=("Segoe UI", 20, "bold")).pack(pady=(20, 10))
        
        username = auth_client.user_info.get("username", "Unknown") if auth_client.user_info else "Unknown"
        prefix = payment_info.get("payment_prefix", "DOUYIN")
        syntax = f"{prefix} {username.upper()}"
        
        ctk.CTkLabel(win, text="Chọn gói gia hạn:", font=("Segoe UI", 14)).pack(pady=(5, 5))
        
        # Sẽ được khởi tạo sau khi định nghĩa _update_qr
        opt_plan_frame = ctk.CTkFrame(win, fg_color="transparent")
        opt_plan_frame.pack(pady=5)
        
        # Tạo mapping giá kèm theo Mã Gói
        packages = payment_info.get("packages", [])
        if not packages:
            packages = [
                {"code": "1M", "name": "1 Tháng (30 ngày)", "price": int(payment_info.get("price_1_month", "600000"))},
                {"code": "3M", "name": "3 Tháng (90 ngày)", "price": int(payment_info.get("price_3_months", "1500000"))},
                {"code": "6M", "name": "6 Tháng (180 ngày)", "price": int(payment_info.get("price_6_months", "2500000"))},
                {"code": "1Y", "name": "1 Năm (365 ngày)", "price": int(payment_info.get("price_1_year", "4500000"))},
                {"code": "LT", "name": "Vĩnh viễn (10 Năm)", "price": int(payment_info.get("price_lifetime", "10000000"))}
            ]
            
        price_map = {}
        for p in packages:
            price_map[f"{p['name']} - {int(p['price']):,}đ"] = (int(p["price"]), p["code"])
            
        options = list(price_map.keys())
        
        lbl_syntax = ctk.CTkLabel(win, text=f"Nội dung CK: {syntax}", font=("Consolas", 16, "bold"), text_color=SUCCESS)
        lbl_syntax.pack(pady=10)
        
        # Label chứa ảnh QR
        lbl_qr = ctk.CTkLabel(win, text="Đang tải QR Code...")
        lbl_qr.pack(pady=10)
        
        def _update_qr(selected_plan):
            amount, package_code = price_map[selected_plan]
            bank_bin = payment_info.get("bank_bin", "")
            bank_account = payment_info.get("bank_account", "")
            
            # Cập nhật lại nội dung chuyển khoản chứa Mã gói
            new_syntax = f"{prefix} {username.upper()} {package_code}"
            lbl_syntax.configure(text=f"Nội dung CK: {new_syntax}")
            
            qr_url = f"https://img.vietqr.io/image/{bank_bin}-{bank_account}-compact2.png?amount={amount}&addInfo={new_syntax.replace(' ', '%20')}"
            
            def fetch_qr():
                import urllib.request
                import io
                from PIL import Image
                try:
                    req = urllib.request.Request(qr_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as u:
                        raw_data = u.read()
                    img = Image.open(io.BytesIO(raw_data))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(250, 300))
                    self.after(0, lambda: lbl_qr.configure(image=ctk_img, text=""))
                except Exception as e:
                    self.after(0, lambda: lbl_qr.configure(text=f"Lỗi tải QR: {e}", image=""))
            
            import threading
            threading.Thread(target=fetch_qr, daemon=True).start()

        opt_plan = ctk.CTkOptionMenu(opt_plan_frame, values=options, command=_update_qr, width=300)
        opt_plan.set(options[0])
        opt_plan.pack()
        
        # Load default QR
        _update_qr(options[0])
        
        ctk.CTkLabel(win, text=f"Chủ thẻ: {payment_info.get('bank_name', 'UNKNOWN')}", font=("Segoe UI", 12, "bold")).pack(pady=5)
        ctk.CTkLabel(win, text="⚠️ Vui lòng chuyển khoản ĐÚNG NỘI DUNG để được cộng ngày tự động.", font=("Segoe UI", 12), text_color=DANGER).pack(pady=5)
        ctk.CTkLabel(win, text="Hệ thống đang tự động kiểm tra trạng thái thanh toán...", font=("Segoe UI", 11, "italic")).pack(pady=(0, 10))
        
        original_expire = auth_client.user_info.get("expire_date") if auth_client.user_info else None
        check_job = None
        
        def _check_payment():
            nonlocal check_job
            if not win.winfo_exists():
                return
            try:
                success, data = auth_client.get_me()
                if success:
                    new_expire = data.get("expire_date")
                    if new_expire and new_expire != original_expire:
                        messagebox.showinfo("Thành công", f"Thanh toán thành công!\nTài khoản đã được gia hạn đến: {new_expire}")
                        win.destroy()
                        self.app._update_user_ui()
                        return
            except Exception:
                pass
            check_job = win.after(5000, _check_payment)
            
        check_job = win.after(5000, _check_payment)
        
        def _on_close():
            if check_job:
                win.after_cancel(check_job)
            win.destroy()
            
        win.protocol("WM_DELETE_WINDOW", _on_close)
        
        ctk.CTkButton(win, text="Đóng", command=_on_close, fg_color=BORDER, hover_color=BG_CARD).pack(pady=(10, 20))
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
        
        self._build_admin_system(self.tab_sys)
        self._build_admin_users(self.tab_users)
        self._build_admin_stats(self.tab_stats)
        self._build_admin_payment(self.tab_payment)
        self._build_admin_packages(self.tab_packages)
        self._build_admin_noti(self.tab_noti)
        self._build_admin_logs(self.tab_logs)

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
            
        self._entry_gemini.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(14, 14))
        
        btn_toggle_key = ctk.CTkButton(
            ai, text="👁", width=30, height=28, fg_color="transparent", hover_color=BG_CARD, text_color=TEXT_DIM,
            command=lambda: self._entry_gemini.configure(show="" if self._entry_gemini.cget("show") == "*" else "*")
        )
        btn_toggle_key.grid(row=0, column=2, padx=(0, 16), pady=(14, 14))

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

        # ── Google Drive section ─────────────────────────────────────────────
        self._section(parent, "☁️  Google Drive Backup", row=6)
        drive_frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
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
            parent, text="💾  Lưu cài đặt", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._save,
        ).grid(row=8, column=0, sticky="w", pady=(4, 0))

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

    def _save(self):
        gemini_key = self._entry_gemini.get().strip()
        vbee_key = getattr(self, "_entry_vbee", ctk.CTkEntry(self)).get().strip()
        env_path = Path(__file__).parent / ".env"
        
        from dotenv import set_key
        if gemini_key:
            set_key(env_path, "GEMINI_API_KEY", gemini_key)
        if vbee_key:
            set_key(env_path, "VBEE_API_KEY", vbee_key)
            
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
            
            status_text = "Hết hạn" if u.get('is_expired', True) else "Active"
            info_str = f"👤 {u['username']}  |  🎖️ Role: {u['role']}  |  ⏳ Hết hạn: {u.get('expire_date', 'Chưa có')} ({status_text})"
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
        
        self._section(scroll, "💰  Quản Lý Gói (Dynamic Packages)", row=0)
        price = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        price.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        price.grid_columnconfigure(0, weight=1)
        
        from auth_client import auth_client
        import json
        success, configs = auth_client.admin_get_config()
        if not success: configs = {}
        
        raw_pkgs = configs.get("packages", "")
        packages = []
        if raw_pkgs:
            try: packages = json.loads(raw_pkgs)
            except: pass
        if not packages:
            packages = [
                {"code": "1M", "name": "1 Tháng (30 ngày)", "days": 30, "price": int(configs.get("price_1_month", "600000"))},
                {"code": "3M", "name": "3 Tháng (90 ngày)", "days": 90, "price": int(configs.get("price_3_months", "1500000"))},
                {"code": "6M", "name": "6 Tháng (180 ngày)", "days": 180, "price": int(configs.get("price_6_months", "2500000"))},
                {"code": "1Y", "name": "1 Năm (365 ngày)", "days": 365, "price": int(configs.get("price_1_year", "4500000"))},
                {"code": "LT", "name": "Vĩnh viễn (10 Năm)", "days": 3650, "price": int(configs.get("price_lifetime", "10000000"))}
            ]

        self._pkg_rows = []
        pkg_container = ctk.CTkFrame(price, fg_color="transparent")
        pkg_container.pack(fill="x", padx=16, pady=10)
        
        hdr = ctk.CTkFrame(pkg_container, fg_color="transparent")
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="Mã Gói (VD: 1M)", width=100, anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
        ctk.CTkLabel(hdr, text="Tên Gói", width=180, anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
        ctk.CTkLabel(hdr, text="Số Ngày", width=80, anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
        ctk.CTkLabel(hdr, text="Giá Tiền (VNĐ)", width=120, anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)

        def add_pkg_row(p_code="", p_name="", p_days=0, p_price=0):
            row_f = ctk.CTkFrame(pkg_container, fg_color="transparent")
            row_f.pack(fill="x", pady=2)
            
            e_code = ctk.CTkEntry(row_f, width=100, font=("Consolas", 12))
            e_code.insert(0, str(p_code))
            e_code.pack(side="left", padx=5)
            
            e_name = ctk.CTkEntry(row_f, width=180)
            e_name.insert(0, str(p_name))
            e_name.pack(side="left", padx=5)
            
            e_days = ctk.CTkEntry(row_f, width=80)
            e_days.insert(0, str(p_days))
            e_days.pack(side="left", padx=5)
            
            e_price = ctk.CTkEntry(row_f, width=120)
            e_price.insert(0, str(p_price))
            e_price.pack(side="left", padx=5)
            
            def remove():
                row_f.destroy()
                self._pkg_rows.remove(row_data)
                
            btn_del = ctk.CTkButton(row_f, text="Xoá", width=50, fg_color=DANGER, hover_color="#c0392b", command=remove)
            btn_del.pack(side="left", padx=5)
            
            row_data = {"code": e_code, "name": e_name, "days": e_days, "price": e_price}
            self._pkg_rows.append(row_data)

        for pkg in packages:
            add_pkg_row(pkg.get("code",""), pkg.get("name",""), pkg.get("days",0), pkg.get("price",0))
            
        ctk.CTkButton(price, text="➕ Thêm Gói Mới", fg_color=ACCENT, width=120, command=add_pkg_row).pack(pady=(0, 16))
        
        def _save_packages():
            new_pkgs = []
            for r in getattr(self, "_pkg_rows", []):
                new_pkgs.append({
                    "code": r["code"].get().strip(),
                    "name": r["name"].get().strip(),
                    "days": int(r["days"].get().strip() or 0),
                    "price": int(r["price"].get().strip() or 0)
                })
            data = {
                "packages": json.dumps(new_pkgs),
            }
            from auth_client import auth_client
            succ, msg = auth_client.admin_save_config(data)
            if succ:
                messagebox.showinfo("Thành công", "Đã lưu Danh sách Gói!")
            else:
                messagebox.showerror("Lỗi", msg)
                
        ctk.CTkButton(scroll, text="💾  Lưu Danh Sách Gói", width=240, command=_save_packages,
                      fg_color=SUCCESS, hover_color="#27ae60",
                      font=("Segoe UI", 13, "bold")).grid(row=2, column=0, pady=(8, 24), sticky="w")

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
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(top_frame, text="Nhật ký Hoạt động (Realtime)", font=("Segoe UI", 16, "bold"), text_color=TEXT_MAIN).pack(side="left")
        
        btn_refresh = ctk.CTkButton(top_frame, text="🔄 Làm mới", width=100, fg_color=BORDER, hover_color=BG_CARD)
        btn_refresh.pack(side="right")
        
        # Table Header
        header = ctk.CTkFrame(parent, fg_color=BG_CARD, height=40, corner_radius=8)
        header.pack(fill="x", padx=20, pady=(0, 10))
        
        cols = [("Thời gian", 150), ("User", 150), ("Action", 100), ("IP", 120), ("Chi tiết", 0)]
        for text, width in cols:
            lbl = ctk.CTkLabel(header, text=text, font=("Segoe UI", 12, "bold"), text_color=TEXT_DIM, anchor="w")
            if width > 0:
                lbl.pack(side="left", padx=10, pady=8)
                lbl.configure(width=width)
            else:
                lbl.pack(side="left", fill="x", expand=True, padx=10, pady=8)
                
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        def _load_logs():
            for widget in scroll.winfo_children():
                widget.destroy()
                
            from auth_client import auth_client
            succ, logs = auth_client.admin_get_logs(limit=100)
            if not succ or not isinstance(logs, list):
                ctk.CTkLabel(scroll, text="Không thể tải dữ liệu", text_color=DANGER).pack(pady=20)
                return
                
            for idx, log in enumerate(logs):
                bg_col = "#1e212b" if idx % 2 == 0 else "transparent"
                row = ctk.CTkFrame(scroll, fg_color=bg_col, height=36, corner_radius=4)
                row.pack(fill="x", pady=2)
                
                # Time
                t_lbl = ctk.CTkLabel(row, text=log.get("time", ""), font=("Consolas", 11), text_color=TEXT_DIM, width=150, anchor="w")
                t_lbl.pack(side="left", padx=10, pady=4)
                
                # User
                u_lbl = ctk.CTkLabel(row, text=log.get("username", ""), font=("Segoe UI", 12, "bold"), text_color="#f38ba8", width=150, anchor="w")
                u_lbl.pack(side="left", padx=10, pady=4)
                
                # Action
                action = log.get("action", "")
                act_col = SUCCESS if action == "UPLOAD" else (WARNING if action == "PROCESS" else (ACCENT if action == "CRAWL" else "#cba6f7"))
                a_lbl = ctk.CTkLabel(row, text=f" {action} ", font=("Segoe UI", 10, "bold"), text_color=BG_DARK, fg_color=act_col, corner_radius=6, width=100)
                a_lbl.pack(side="left", padx=10, pady=8)
                
                # IP
                i_lbl = ctk.CTkLabel(row, text=log.get("ip_address", ""), font=("Consolas", 11), text_color=TEXT_DIM, width=120, anchor="w")
                i_lbl.pack(side="left", padx=10, pady=4)
                
                # Details
                d_lbl = ctk.CTkLabel(row, text=log.get("details", ""), font=("Segoe UI", 12), text_color=TEXT_MAIN, anchor="w")
                d_lbl.pack(side="left", fill="x", expand=True, padx=10, pady=4)
                
        btn_refresh.configure(command=lambda: __import__('threading').Thread(target=_load_logs, daemon=True).start())
        
        # Load lần đầu khi click tab
        def _on_tab_select(*args):
            if self.tabview.get() == "Hoạt động":
                __import__('threading').Thread(target=_load_logs, daemon=True).start()
                
        self.tabview._segmented_button.configure(command=lambda v: (self.tabview.set(v), _on_tab_select()))
        # Khởi tạo mặc định
        self.after(500, lambda: __import__('threading').Thread(target=_load_logs, daemon=True).start() if self.tabview.get() == "Hoạt động" else None)

# ═══════════════════════════════════════════════════════════════════════════════
#  Login Window
# ═══════════════════════════════════════════════════════════════════════════════
from auth_client import auth_client

class RegisterWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        
        self.title("Đăng ký Tài khoản")
        self.geometry("400x350")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self.transient(master) # Nổi lên trên LoginWindow
        self.grab_set()        # Khoá cửa sổ Login khi đang đăng ký
        
        ctk.CTkLabel(
            self, text="Tạo Tài Khoản",
            font=("Segoe UI", 28, "bold"), text_color=TEXT_MAIN
        ).pack(pady=(30, 20))
        
        self.entry_user = ctk.CTkEntry(self, placeholder_text="Tên đăng nhập", width=250)
        self.entry_user.pack(pady=10)
        
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Mật khẩu", show="*", width=250)
        self.entry_pass.pack(pady=10)
        
        self.entry_pass_confirm = ctk.CTkEntry(self, placeholder_text="Xác nhận Mật khẩu", show="*", width=250)
        self.entry_pass_confirm.pack(pady=10)
        
        self.btn_register = ctk.CTkButton(
            self, text="Đăng ký", width=250, height=40,
            command=self._do_register, font=("Segoe UI", 14, "bold"),
            fg_color=SUCCESS, hover_color="#059669"
        )
        self.btn_register.pack(pady=20)
        
    def _do_register(self):
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get()
        pwd2 = self.entry_pass_confirm.get()
        
        from tkinter import messagebox
        if not user or not pwd:
            messagebox.showwarning("Lỗi", "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!")
            return
            
        if pwd != pwd2:
            messagebox.showwarning("Lỗi", "Mật khẩu xác nhận không khớp!")
            return
            
        self.btn_register.configure(state="disabled", text="Đang xử lý...")
        
        def run():
            success, msg = auth_client.register(user, pwd)
            self.after(0, self._handle_result, success, msg)
            
        import threading
        threading.Thread(target=run, daemon=True).start()
        
    def _handle_result(self, success, msg):
        from tkinter import messagebox
        if success:
            messagebox.showinfo("Thành công", msg)
            self.grab_release()
            self.destroy()
        else:
            messagebox.showerror("Lỗi", msg)
            self.btn_register.configure(state="normal", text="Đăng ký")

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        
        self.title("Đăng nhập Hệ thống")
        self.geometry("400x380")
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
        
        self.btn_register = ctk.CTkButton(
            self, text="Chưa có tài khoản? Đăng ký ngay", width=250, height=30,
            command=self._open_register, font=("Segoe UI", 12),
            fg_color="transparent", text_color=ACCENT, hover_color=BG_CARD
        )
        self.btn_register.pack(pady=0)
        
    def _open_register(self):
        RegisterWindow(self)
        
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
            self.after(100, lambda: self.state("zoomed"))  # Full màn hình sau khi load xong
            import threading
            threading.Thread(target=auth_client.sync_douyin_cookie, daemon=True).start()
        else:
            self.withdraw() # Ẩn main window
            LoginWindow(self, self._on_login_success)

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
                is_expired = auth_client.user_info.get("is_expired", True)
                status = "❌ Hết hạn" if is_expired else "✅ Hoạt động"
                
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
                        
            # Force refresh SettingsTab
            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 7:
                for i, tab in enumerate(self._tab_frames):
                    if hasattr(tab, "refresh_ui") and tab.__class__.__name__ == "SettingsTab":
                        tab.refresh_ui()
                
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
                            PROCESSOR_CONFIG["gemini_api_keys"] = []
                except:
                    pass
            else:
                PROCESSOR_CONFIG["gemini_api_keys"] = []
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
        # Chuyển sang tab Settings
        self._nav(7)
        # Gọi hộp thoại thanh toán
        if hasattr(self, "_tab_frames") and len(self._tab_frames) > 7:
            self._tab_frames[7]._show_payment_dialog()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(2, weight=1)  # Nav scroll chiếm hết không gian còn lại
        sidebar.grid_columnconfigure(0, weight=1)

        # Logo
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=16, pady=(24, 12))
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
            row=1, column=0, sticky="ew", padx=16, pady=(0, 8)
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
            btn.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            self._nav_buttons.append(btn)
        
        self._nav_scroll = nav_scroll
        
        # ── Bottom fixed area ──────────────────────────────────────────────────
        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        # Premium User Profile Card
        self.user_card = ctk.CTkFrame(bottom, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#334155")
        self.user_card.grid(row=0, column=0, pady=(8, 6), padx=12, sticky="ew")
        
        self.lbl_user_info = ctk.CTkLabel(
            self.user_card, text="👤  Chưa đăng nhập",
            font=("Segoe UI", 12), text_color=TEXT_MAIN, justify="left"
        )
        self.lbl_user_info.pack(padx=12, pady=12, anchor="w")
        
        self.btn_upgrade_sidebar = ctk.CTkButton(
            self.user_card, text="💎 Nâng Cấp VIP", height=32,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=6,
            command=self._handle_sidebar_upgrade
        )
        self.btn_upgrade_sidebar.pack(padx=12, pady=(0, 12), fill="x")

        # Logout button
        btn_logout = ctk.CTkButton(
            bottom, text="🚪 Đăng xuất", height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#EF4444", hover_color="#B91C1C", corner_radius=8,
            command=self._do_logout
        )
        btn_logout.grid(row=1, column=0, pady=(0, 6), padx=12, sticky="ew")

        # Support info
        import webbrowser
        support_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        support_frame.grid(row=2, column=0, sticky="ew")
        
        ctk.CTkLabel(support_frame, text="📞 Hotline hỗ trợ:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=16, pady=(2, 4))
        
        self.btn_zalo = ctk.CTkButton(
            support_frame, text="💬 Zalo: 0866655803", font=("Segoe UI", 11, "bold"),
            fg_color="#0068FF", hover_color="#0055D4", height=28,
            command=lambda: webbrowser.open("https://zalo.me/0866655803")
        )
        self.btn_zalo.pack(anchor="w", padx=16, pady=2, fill="x")
        
        self.btn_tele = ctk.CTkButton(
            support_frame, text="✈️ Telegram: @hoannm", font=("Segoe UI", 11, "bold"),
            fg_color="#24A1DE", hover_color="#1D84B5", height=28,
            command=lambda: webbrowser.open("https://t.me/hoannm")
        )
        self.btn_tele.pack(anchor="w", padx=16, pady=2, fill="x")

        # Bottom: version
        ctk.CTkLabel(
            bottom, text="v1.0.0 (Premium)",
            font=("Segoe UI", 10), text_color=TEXT_DIM,
        ).grid(row=3, column=0, pady=(4, 10))

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
