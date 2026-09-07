"""
Common reusable UI components and mixins for TikTok/Douyin Desktop App.
"""

import sys
import os
import inspect
import asyncio
import threading
import tkinter as tk
from datetime import datetime
from typing import Optional, Dict, Any

import customtkinter as ctk

from ui.theme import (
    BG_DARK, BG_CARD, BG_SIDEBAR, ACCENT, ACCENT_HOVER,
    SUCCESS, WARNING, DANGER, TEXT_MAIN, TEXT_DIM, BORDER
)
from utils.session_logger import SessionLogManager


# ═══════════════════════════════════════════════════════════════════════════════
#  LogWidget
# ═══════════════════════════════════════════════════════════════════════════════
class LogWidget(ctk.CTkTextbox):
    """Textbox hiển thị log với màu sắc theo cấp độ log."""

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
        for tag, color in self.COLORS.items():
            self._textbox.tag_configure(tag, foreground=color)

    def append(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
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
    """Huy hiệu trạng thái có bo góc mềm."""

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
#  ToolTip
# ═══════════════════════════════════════════════════════════════════════════════
class ToolTip:
    """Hiển thị gợi ý dạng popup khi hover chuột vào widget."""

    def __init__(self, widget, text, wraplength=250):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.tooltip_window = None
        self.tw = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + 20
            
            self.tw = tk.Toplevel(self.widget)
            self.tw.wm_overrideredirect(True)
            self.tw.wm_geometry(f"+{x}+{y}")
            self.tw.attributes("-topmost", True)
            
            label = tk.Label(
                self.tw, text=self.text, justify='left',
                background="#2d3436", foreground="#dfe6e9", 
                relief='solid', borderwidth=1, highlightbackground="#636e72",
                font=("Segoe UI", 10), padx=8, pady=6, wraplength=self.wraplength
            )
            label.pack()
        except Exception:
            pass

    def leave(self, event=None):
        if hasattr(self, 'tw') and self.tw:
            try:
                self.tw.destroy()
            except Exception:
                pass
            self.tw = None


# ═══════════════════════════════════════════════════════════════════════════════
#  ToastNotification
# ═══════════════════════════════════════════════════════════════════════════════
class ToastNotification(ctk.CTkToplevel):
    """
    Toast popup góc trên màn hình.
    - Tự tắt sau `duration` giây.
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
        
        accent, _ = self._COLORS.get(type_, self._COLORS["info"])
        
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.configure(fg_color=BG_CARD)
        
        self._duration = duration
        self._remaining = duration
        
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
        
        icons = {"info": "ℹ️", "warning": "📢", "error": "⚠️", "update": "🚀"}
        icon_text = icons.get(type_, "ℹ️")
        ctk.CTkLabel(
            header, text=f"{icon_text}  {title}",
            font=("Segoe UI", 13, "bold"),
            text_color=accent
        ).pack(side="left")
        
        # Countdown & Đóng
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")
        
        self._lbl_countdown = ctk.CTkLabel(
            right, text=f"{duration}s",
            font=("Segoe UI", 10), text_color=TEXT_DIM
        )
        self._lbl_countdown.pack(side="left", padx=(0, 6))
        
        ctk.CTkButton(
            right, text="✕", width=24, height=24,
            fg_color="transparent", hover_color=BORDER,
            font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM,
            command=self.close_toast
        ).pack(side="left")
        
        ctk.CTkLabel(
            content, text=message,
            font=("Segoe UI", 12), text_color=TEXT_MAIN,
            wraplength=310, justify="left", anchor="w"
        ).pack(fill="x", padx=14, pady=(0, 12), anchor="w")
        
        # Progress bar
        prog_bg = ctk.CTkFrame(content, fg_color=BORDER, height=3, corner_radius=0)
        prog_bg.pack(fill="x", side="bottom")
        self._prog = ctk.CTkFrame(prog_bg, fg_color=accent, height=3, corner_radius=0)
        self._prog.pack(side="left", fill="y")
        
        self.configure(border_width=1, border_color=BORDER)
        self.update_idletasks()
        self._position_toast(master)
        self.after(100, self._tick)
    
    def _position_toast(self, master):
        try:
            master.update_idletasks()
            self.update_idletasks()
            mx = master.winfo_x()
            my = master.winfo_y()
            mw = master.winfo_width()
            
            tw = 420
            th = 110
            x = mx + (mw // 2) - (tw // 2)
            y = my + 24
            self.geometry(f"{tw}x{th}+{x}+{y}")
        except Exception:
            self.geometry("420x110+300+60")
    
    def _tick(self):
        if not self.winfo_exists():
            return
        self._remaining -= 1
        if self._remaining <= 0:
            self.close_toast()
            return
        self._lbl_countdown.configure(text=f"{self._remaining}s")
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
    """Helper bắn toast notification từ bất kỳ vị trí nào."""
    try:
        return ToastNotification(master, title=title, message=message, type_=type_, duration=duration)
    except Exception as e:
        print(f"Toast error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  StatsCard
# ═══════════════════════════════════════════════════════════════════════════════
class StatsCard(ctk.CTkFrame):
    """Thẻ thống kê số liệu trên Dashboard."""

    def __init__(self, master, label: str, value: str = "0", color=ACCENT, icon: str = "", **kwargs):
        super().__init__(
            master, fg_color=BG_CARD, corner_radius=10,
            border_width=1, border_color=BORDER, **kwargs
        )
        self.pack_propagate(False)
        self.configure(height=90)
        
        accent_line = ctk.CTkFrame(self, fg_color=color, width=5, corner_radius=0)
        accent_line.pack(side="left", fill="y", pady=15)
        
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


# ═══════════════════════════════════════════════════════════════════════════════
#  SystemInfoWidget
# ═══════════════════════════════════════════════════════════════════════════════
class SystemInfoWidget(ctk.CTkFrame):
    """Widget theo dõi CPU, RAM, Disk của hệ thống."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        
        ctk.CTkLabel(
            self, text="💻  Tài nguyên Hệ thống",
            font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN
        ).pack(anchor="w", padx=20, pady=(16, 10))
        
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
        except Exception:
            for n in ["CPU", "RAM", "Disk"]:
                self.bars[n][1].configure(text="N/A")


# ═══════════════════════════════════════════════════════════════════════════════
#  SidebarButton
# ═══════════════════════════════════════════════════════════════════════════════
class SidebarButton(ctk.CTkButton):
    """Nút bấm thanh điều hướng Sidebar."""

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
#  TaskMixin
# ═══════════════════════════════════════════════════════════════════════════════
class TaskMixin:
    """Mixin cho các Tab cần chạy lệnh Python nền và quản lý phiên nhật ký."""

    def __init__(self, *args, **kwargs):
        self.cancel_flag = False
        self._current_session_id = None
        self._session_module = None

    def _start_logging_session(self, module: str, title: str, details: Optional[Dict[str, Any]] = None) -> str:
        """Bắt đầu phiên ghi log cho phân hệ hiện tại."""
        try:
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            self._session_module = module
            self._current_session_id = SessionLogManager.start_session(
                module=module,
                title=title,
                username=username,
                details=details or {},
            )
            return self._current_session_id
        except Exception:
            self._current_session_id = None
            return ""

    def _finish_logging_session(
        self,
        status: str = "SUCCESS",
        summary: str = "",
        details: Optional[Dict[str, Any]] = None,
        cancelled: bool = False,
    ):
        """Kết thúc phiên ghi log của phân hệ hiện tại."""
        sid = getattr(self, "_current_session_id", None)
        if sid:
            try:
                mod = getattr(self, "_session_module", "general") or "general"
                is_canc = cancelled or bool(getattr(self, "cancel_flag", False))
                SessionLogManager.finish_session(
                    module=mod,
                    session_id=sid,
                    status=status,
                    summary=summary,
                    details=details,
                    cancelled=is_canc,
                )
            except Exception:
                pass
            finally:
                self._current_session_id = None

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
        """Ghi log (gọi được từ thread bất kỳ). Hiển thị lên UI và lưu file phiên."""
        if hasattr(self, "_log_widget"):
            self.after(0, lambda: self._log_widget.append(msg, level))

        sid = getattr(self, "_current_session_id", None)
        if sid:
            mod = getattr(self, "_session_module", "general") or "general"
            SessionLogManager.append_log(mod, sid, msg, level)

    def _on_task_done(self):
        """Gọi sau khi task hoàn tất."""
        if getattr(self, "_current_session_id", None):
            self._finish_logging_session(
                status="CANCELLED" if getattr(self, "cancel_flag", False) else "SUCCESS",
                summary="Hoàn tất tác vụ." if not getattr(self, "cancel_flag", False) else "Tiến trình đã bị dừng.",
            )
        self.cancel_flag = False


# ═══════════════════════════════════════════════════════════════════════════════
#  DonutChart
# ═══════════════════════════════════════════════════════════════════════════════
class DonutChart(ctk.CTkFrame):
    """Biểu đồ hình vành khuyên Donut hiển thị tỷ lệ thống kê."""

    def __init__(self, master, title="Biểu đồ", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.canvas_size = 150
        self.thickness = 22
        
        ctk.CTkLabel(
            self, text=title, font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 0))
        
        self.canvas = tk.Canvas(self, width=self.canvas_size, height=self.canvas_size, bg=BG_CARD, highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=(20, 10), pady=(10, 20), sticky="e")
        
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
            if val == 0:
                continue
            extent = (val / total) * 360
            self.canvas.create_arc(
                15, 15, self.canvas_size-15, self.canvas_size-15,
                start=start_angle, extent=extent, style=tk.ARC, outline=color, width=self.thickness
            )
            start_angle += extent
            
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
