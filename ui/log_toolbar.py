"""
Component Thanh Công Cụ Nhật Ký (LogToolbar) dùng chung cho tất cả các Tab.
Cung cấp các nút thao tác tiêu chuẩn: Xóa log, Sao chép log, Mở thư mục logs,
và Xem lịch sử các phiên hoạt động.
"""
import os
import subprocess
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from utils.session_logger import SessionLogManager, MODULE_CONFIG

from ui.theme import (
    BG_CARD, BORDER, TEXT_MAIN, TEXT_DIM, ACCENT, ACCENT_HOVER, BG_CARD_HOVER
)


class LogToolbar(ctk.CTkFrame):
    """
    Thanh công cụ điều khiển khung Log cho các Tab.
    Bao gồm:
      - Nhãn tiêu đề phân hệ (có icon)
      - Nút [🧹 Xóa]: Xóa sạch nội dung khung log hiện thời
      - Nút [📋 Copy]: Sao chép toàn bộ text log vào Clipboard
      - Nút [📂 Thư mục Log]: Mở thư mục lưu file log trên Windows Explorer
      - Nút [📜 Xem lịch sử Logs]: Mở hộp thoại tra cứu lịch sử phiên tương ứng
    """

    def __init__(
        self,
        master,
        log_widget,
        module: str = "general",
        title: str = "📋 Nhật ký (Logs):",
        on_open_history=None,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self.log_widget = log_widget
        self.module = module
        self.on_open_history = on_open_history

        # Tiêu đề bên trái
        mod_info = MODULE_CONFIG.get(module, {})
        default_icon = mod_info.get("icon", "📋")
        display_title = title if title else f"{default_icon}  Nhật ký (Logs):"

        self._lbl_title = ctk.CTkLabel(
            self,
            text=display_title,
            font=("Segoe UI", 12, "bold"),
            text_color=TEXT_MAIN,
        )
        self._lbl_title.pack(side="left")

        # Nút [📜 Xem lịch sử Logs]
        self._btn_history = ctk.CTkButton(
            self,
            text="📜 Xem lịch sử Logs",
            height=26,
            corner_radius=6,
            font=("Segoe UI", 11, "bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.open_history_dialog,
        )
        self._btn_history.pack(side="right", padx=(6, 0))

        # Nút [📂 Thư mục Log]
        self._btn_folder = ctk.CTkButton(
            self,
            text="📂 Thư mục Log",
            width=95,
            height=26,
            corner_radius=6,
            border_width=1,
            border_color=BORDER,
            font=("Segoe UI", 11),
            fg_color="#182033",
            hover_color=BG_CARD_HOVER,
            command=self.open_logs_folder,
        )
        self._btn_folder.pack(side="right", padx=(6, 0))

        # Nút [📋 Copy]
        self._btn_copy = ctk.CTkButton(
            self,
            text="📋 Copy",
            width=58,
            height=26,
            corner_radius=6,
            border_width=1,
            border_color=BORDER,
            font=("Segoe UI", 11),
            fg_color="#182033",
            hover_color=BG_CARD_HOVER,
            command=self.copy_current_log,
        )
        self._btn_copy.pack(side="right", padx=(6, 0))

        # Nút [🧹 Xóa]
        self._btn_clear = ctk.CTkButton(
            self,
            text="🧹 Xóa",
            width=52,
            height=26,
            corner_radius=6,
            border_width=1,
            border_color=BORDER,
            font=("Segoe UI", 11),
            fg_color="#182033",
            hover_color=BG_CARD_HOVER,
            command=self.clear_log,
        )
        self._btn_clear.pack(side="right")

    def clear_log(self):
        """Xóa trắng khung log widget liên kết."""
        if hasattr(self.log_widget, "clear"):
            self.log_widget.clear()

    def copy_current_log(self):
        """Sao chép toàn bộ text đang có trong khung log vào Clipboard."""
        try:
            content = ""
            if hasattr(self.log_widget, "_textbox"):
                content = self.log_widget._textbox.get("1.0", "end-1c")
            elif hasattr(self.log_widget, "get"):
                content = self.log_widget.get("1.0", "end-1c")

            if not content or not content.strip():
                messagebox.showwarning("Thông báo", "Khung log hiện đang trống!")
                return

            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Thành công", "Đã sao chép nhật ký hiện tại vào Clipboard!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sao chép nhật ký: {e}")

    def open_logs_folder(self):
        """Mở thư mục lưu log của module này trong Windows Explorer."""
        try:
            folder_path = SessionLogManager.get_logs_dir(self.module)
            folder_path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder_path))
            else:
                subprocess.Popen(["xdg-open", str(folder_path)])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục logs: {e}")

    def open_history_dialog(self):
        """Mở cửa sổ tra cứu lịch sử Logs."""
        if self.on_open_history:
            self.on_open_history()
            return

        try:
            from ui.unified_log_dialog import UnifiedLogHistoryDialog
            UnifiedLogHistoryDialog(self.winfo_toplevel(), initial_module=self.module)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở cửa sổ lịch sử logs: {e}")
