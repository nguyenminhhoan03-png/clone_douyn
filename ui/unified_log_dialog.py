"""
Cửa sổ Tra Cứu Lịch Sử & Chi Tiết Nhật Ký Đa Phân Hệ (Unified Log History Dialog).
Hỗ trợ xem lại và phân tích logs của tất cả các luồng:
Crawl, Xử lý Video (Process), Upload Video, Nuôi Nick (Farm), và Auto Pipeline.
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from utils.session_logger import SessionLogManager, MODULE_CONFIG, SESSIONS_ROOT_DIR

# Palette màu Sleek Dark Theme
BG_DARK = "#0E1015"
BG_CARD = "#1C1F2E"
BG_SIDEBAR = "#141620"
ACCENT = "#8B5CF6"
ACCENT_HOVER = "#7C3AED"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
TEXT_MAIN = "#F8FAFC"
TEXT_DIM = "#94A3B8"
BORDER = "#2D3142"


class UnifiedLogHistoryDialog(ctk.CTkToplevel):
    """
    Cửa sổ trung tâm hiển thị lịch sử và chi tiết nhật ký mọi phân hệ trong DouyinBot.
    Cho phép lọc theo phân hệ (Crawl, Process, Upload, Farm, Auto), lọc trạng thái,
    tìm kiếm từ khóa, sao chép log và mở trực tiếp bằng Notepad.
    """

    def __init__(self, master, initial_module: str = "all", **kwargs):
        super().__init__(master, **kwargs)

        self.title("Trung Tâm Lịch Sử & Chi Tiết Nhật Ký (Logs)")
        self.geometry("1060x680")
        self.minsize(880, 560)
        self.configure(fg_color=BG_DARK)

        # Căn giữa màn hình
        self.update_idletasks()
        try:
            mx = master.winfo_x()
            my = master.winfo_y()
            mw = master.winfo_width()
            mh = master.winfo_height()
            x = mx + max(0, (mw - 1060) // 2)
            y = my + max(0, (mh - 680) // 2)
            self.geometry(f"1060x680+{x}+{y}")
        except Exception:
            pass

        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_set()

        self._active_module = initial_module if initial_module in MODULE_CONFIG or initial_module == "all" else "all"
        self._selected_session_id = None
        self._session_cards = {}
        self._module_tab_buttons = {}

        self._build_ui()
        self._load_sessions()

    def _build_ui(self):
        # ─── HEADER BAR ─────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, height=64, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            title_frame,
            text="📜  Trung Tâm Lịch Sử & Chi Tiết Nhật Ký (Logs)",
            font=("Segoe UI", 16, "bold"),
            text_color=TEXT_MAIN,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Tra cứu trạng thái, thời gian chạy và toàn bộ nội dung logs của mọi phân hệ (Crawl, Process, Upload, Farm, Auto).",
            font=("Segoe UI", 11),
            text_color=TEXT_DIM,
        ).pack(anchor="w")

        btn_header_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_header_frame.pack(side="right", padx=16, pady=14)

        ctk.CTkButton(
            btn_header_frame,
            text="🔄 Làm mới",
            width=85,
            height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color=BORDER,
            hover_color=BG_CARD,
            command=self._load_sessions,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_header_frame,
            text="📂 Thư mục Logs",
            width=115,
            height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color=BORDER,
            hover_color=BG_CARD,
            command=self._open_logs_folder,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_header_frame,
            text="✕ Đóng",
            width=70,
            height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            command=self.destroy,
        ).pack(side="left")

        # ─── FILTER & TABS BAR ───────────────────────────────────────────────────
        filter_bar = ctk.CTkFrame(self, fg_color=BG_CARD, height=48, corner_radius=0, border_width=1, border_color=BORDER)
        filter_bar.pack(fill="x", side="top")
        filter_bar.pack_propagate(False)

        # Tabs Phân hệ (Crawl, Process, Upload, Farm, Auto, Tất cả)
        tab_frame = ctk.CTkFrame(filter_bar, fg_color="transparent")
        tab_frame.pack(side="left", padx=16, pady=8)

        tab_defs = [
            ("all", "🌟 Tất cả", None),
            ("crawl", "🌐 Crawl", MODULE_CONFIG["crawl"]["color"]),
            ("process", "⚙️ Xử lý", MODULE_CONFIG["process"]["color"]),
            ("upload", "📤 Upload", MODULE_CONFIG["upload"]["color"]),
            ("farm", "🌱 Nuôi Nick", MODULE_CONFIG["farm"]["color"]),
            ("auto", "🤖 Auto", MODULE_CONFIG["auto"]["color"]),
        ]

        for mod_key, label_text, color in tab_defs:
            is_active = (self._active_module == mod_key)
            btn = ctk.CTkButton(
                tab_frame,
                text=label_text,
                height=28,
                font=("Segoe UI", 11, "bold" if is_active else "normal"),
                fg_color=ACCENT if is_active else "transparent",
                hover_color=ACCENT_HOVER if is_active else BORDER,
                text_color=TEXT_MAIN if is_active else TEXT_DIM,
                command=lambda k=mod_key: self._set_active_module(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._module_tab_buttons[mod_key] = btn

        # Lọc Trạng thái & Ô Tìm kiếm bên phải
        right_filter = ctk.CTkFrame(filter_bar, fg_color="transparent")
        right_filter.pack(side="right", padx=16, pady=8)

        self._opt_status_filter = ctk.CTkOptionMenu(
            right_filter,
            values=["Tất cả trạng thái", "Thành công", "Có cảnh báo", "Thất bại/Lỗi", "Đã dừng", "Đang chạy"],
            width=140,
            height=28,
            font=("Segoe UI", 11),
            fg_color=BG_DARK,
            button_color=BORDER,
            button_hover_color=BG_CARD,
            command=lambda _: self._load_sessions(),
        )
        self._opt_status_filter.pack(side="right", padx=(8, 0))

        self._entry_search = ctk.CTkEntry(
            right_filter,
            placeholder_text="🔍 Tìm mã phiên, tiêu đề...",
            width=200,
            height=28,
            font=("Segoe UI", 11),
            fg_color=BG_DARK,
            border_color=BORDER,
        )
        self._entry_search.pack(side="right")
        self._entry_search.bind("<KeyRelease>", lambda _: self._load_sessions())

        # ─── BODY CONTAINER (SPLIT PANE) ─────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)
        body.grid_columnconfigure(0, weight=4, minsize=320)
        body.grid_columnconfigure(1, weight=6, minsize=480)
        body.grid_rowconfigure(0, weight=1)

        # Cột Trái: Danh sách các phiên
        left_pane = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_pane.grid_columnconfigure(0, weight=1)
        left_pane.grid_rowconfigure(1, weight=1)

        left_header = ctk.CTkFrame(left_pane, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        self._lbl_session_count = ctk.CTkLabel(
            left_header,
            text="Danh sách phiên (0):",
            font=("Segoe UI", 12, "bold"),
            text_color=TEXT_MAIN,
        )
        self._lbl_session_count.pack(side="left")

        self._scroll_sessions = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        self._scroll_sessions.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Cột Phải: Xem chi tiết phiên & Log Viewer
        right_pane = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
        right_pane.grid(row=0, column=1, sticky="nsew")
        right_pane.grid_columnconfigure(0, weight=1)
        right_pane.grid_rowconfigure(1, weight=1)

        # Banner chi tiết phiên được chọn
        self._detail_banner = ctk.CTkFrame(right_pane, fg_color=BG_DARK, corner_radius=8, border_width=1, border_color=BORDER)
        self._detail_banner.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        self._lbl_session_title = ctk.CTkLabel(
            self._detail_banner,
            text="Chọn một phiên bên trái để xem nhật ký chi tiết",
            font=("Segoe UI", 13, "bold"),
            text_color=TEXT_MAIN,
            wraplength=520,
            justify="left",
        )
        self._lbl_session_title.pack(anchor="w", padx=14, pady=(10, 4))

        self._lbl_session_meta = ctk.CTkLabel(
            self._detail_banner,
            text="Mã phiên: -- | Phân hệ: -- | Thời gian: -- | Trạng thái: --",
            font=("Consolas", 11),
            text_color=TEXT_DIM,
            justify="left",
            wraplength=520,
        )
        self._lbl_session_meta.pack(anchor="w", padx=14, pady=(0, 10))

        # Textbox hiển thị toàn bộ Log
        self._txt_log = ctk.CTkTextbox(
            right_pane,
            font=("Consolas", 11),
            fg_color=BG_DARK,
            text_color=TEXT_MAIN,
            border_width=1,
            border_color=BORDER,
            wrap="word",
        )
        self._txt_log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        # Khởi tạo color tags cho Log Viewer
        try:
            tb = self._txt_log._textbox
            tb.tag_config("INFO", foreground="#60A5FA")
            tb.tag_config("SUCCESS", foreground="#34D399")
            tb.tag_config("WARNING", foreground="#FBBF24")
            tb.tag_config("ERROR", foreground="#F87171")
            tb.tag_config("DEBUG", foreground="#A78BFA")
            tb.tag_config("HEADER", foreground="#E2E8F0", font=("Consolas", 11, "bold"))
        except Exception:
            pass

        # Action Toolbar dưới chân khung log
        log_action_bar = ctk.CTkFrame(right_pane, fg_color="transparent")
        log_action_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._btn_copy_log = ctk.CTkButton(
            log_action_bar,
            text="📋 Sao chép Log",
            width=120,
            height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color=BORDER,
            hover_color=BG_DARK,
            command=self._copy_log,
        )
        self._btn_copy_log.pack(side="left", padx=(0, 8))

        self._btn_open_notepad = ctk.CTkButton(
            log_action_bar,
            text="📝 Mở bằng Notepad",
            width=135,
            height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color=BORDER,
            hover_color=BG_DARK,
            command=self._open_in_notepad,
        )
        self._btn_open_notepad.pack(side="left", padx=(0, 8))

        self._btn_open_file = ctk.CTkButton(
            log_action_bar,
            text="📂 Vị trí file",
            width=100,
            height=30,
            font=("Segoe UI", 11),
            fg_color=BORDER,
            hover_color=BG_DARK,
            command=self._open_file_in_explorer,
        )
        self._btn_open_file.pack(side="left", padx=(0, 8))

        self._btn_delete_session = ctk.CTkButton(
            log_action_bar,
            text="🗑 Xóa log phiên này",
            width=130,
            height=30,
            font=("Segoe UI", 11, "bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self._delete_current_session,
        )
        self._btn_delete_session.pack(side="right")

    def _set_active_module(self, mod_key: str):
        """Chuyển đổi phân hệ đang lọc."""
        self._active_module = mod_key
        for k, btn in self._module_tab_buttons.items():
            is_active = (k == mod_key)
            btn.configure(
                fg_color=ACCENT if is_active else "transparent",
                hover_color=ACCENT_HOVER if is_active else BORDER,
                text_color=TEXT_MAIN if is_active else TEXT_DIM,
                font=("Segoe UI", 11, "bold" if is_active else "normal"),
            )
        self._load_sessions()

    def _load_sessions(self):
        """Đọc và hiển thị danh sách các phiên dựa theo bộ lọc."""
        # Xóa các card cũ
        for widget in self._scroll_sessions.winfo_children():
            widget.destroy()
        self._session_cards.clear()

        status_mapping = {
            "Tất cả trạng thái": "all",
            "Thành công": "SUCCESS",
            "Có cảnh báo": "WARNING",
            "Thất bại/Lỗi": "ERROR",
            "Đã dừng": "CANCELLED",
            "Đang chạy": "RUNNING",
        }
        raw_status = self._opt_status_filter.get()
        filter_status = status_mapping.get(raw_status, "all")
        filter_search = self._entry_search.get().strip()

        sessions = SessionLogManager.get_sessions(
            module=self._active_module,
            status=filter_status,
            search=filter_search,
        )

        mod_name = MODULE_CONFIG.get(self._active_module, {}).get("title", "Tất cả")
        self._lbl_session_count.configure(text=f"Danh sách phiên [{mod_name}] ({len(sessions)}):")

        if not sessions:
            ctk.CTkLabel(
                self._scroll_sessions,
                text="Không có phiên log nào phù hợp với bộ lọc.",
                font=("Segoe UI", 12),
                text_color=TEXT_DIM,
            ).pack(pady=40)
            self._display_empty_log()
            return

        # Render danh sách card phiên
        for s in sessions:
            sid = s.get("session_id", "unknown")
            card = self._create_session_card(s)
            card.pack(fill="x", pady=4, padx=4)
            self._session_cards[sid] = card

        # Mặc định chọn phiên đầu tiên nếu phiên hiện tại không còn hoặc chưa chọn
        first_sid = sessions[0].get("session_id")
        if not self._selected_session_id or self._selected_session_id not in self._session_cards:
            self._select_session(first_sid)
        else:
            self._select_session(self._selected_session_id)

    def _create_session_card(self, session: dict) -> ctk.CTkFrame:
        """Tạo 1 thẻ hiển thị tóm tắt phiên trên danh sách."""
        sid = session.get("session_id", "unknown")
        mod = session.get("module", "general")
        mod_info = MODULE_CONFIG.get(mod, MODULE_CONFIG["general"])
        status = session.get("status", "SUCCESS")
        start_time = session.get("start_time", "")
        title = session.get("title", "Không có tiêu đề")
        summary = session.get("summary", "")

        # Format thời gian ngắn gọn
        disp_time = start_time
        try:
            dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            disp_time = dt.strftime("%H:%M:%S (%d/%m)")
        except Exception:
            pass

        # Màu sắc huy hiệu trạng thái
        status_badges = {
            "SUCCESS": ("✅ Hoàn tất", "#065f46", "#34d399"),
            "WARNING": ("⚠️ Cảnh báo", "#78350f", "#fbbf24"),
            "ERROR": ("❌ Thất bại", "#7f1d1d", "#f87171"),
            "CANCELLED": ("⏹ Đã dừng", "#374151", "#9ca3af"),
            "RUNNING": ("⏳ Đang chạy", "#1e3a8a", "#60a5fa"),
        }
        badge_text, badge_bg, badge_fg = status_badges.get(status, ("ℹ️ Khác", "#374151", TEXT_DIM))

        card = ctk.CTkFrame(
            self._scroll_sessions,
            fg_color=BG_DARK,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            cursor="hand2",
        )

        # Dòng 1: Phân hệ + Thời gian + Trạng thái
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(8, 4))

        mod_tag = ctk.CTkLabel(
            row1,
            text=f" {mod_info['icon']} {mod_info['title']} ",
            font=("Segoe UI", 10, "bold"),
            text_color=mod_info["color"],
            fg_color=BG_CARD,
            corner_radius=4,
        )
        mod_tag.pack(side="left")

        ctk.CTkLabel(
            row1,
            text=f"🕒 {disp_time}",
            font=("Consolas", 10),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=(6, 0))

        st_label = ctk.CTkLabel(
            row1,
            text=badge_text,
            font=("Segoe UI", 10, "bold"),
            text_color=badge_fg,
            fg_color=badge_bg,
            corner_radius=4,
        )
        st_label.pack(side="right")

        # Dòng 2: Tiêu đề phiên
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(0, 4))
        short_title = title if len(title) <= 45 else title[:42] + "..."
        ctk.CTkLabel(
            row2,
            text=short_title,
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT_MAIN,
            anchor="w",
        ).pack(fill="x")

        # Dòng 3: Tóm tắt kết quả + thời lượng
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=(0, 8))

        duration_sec = session.get("duration_seconds")
        dur_str = f"⏱️ {duration_sec}s" if duration_sec is not None else ""
        if duration_sec and duration_sec >= 60:
            dur_str = f"⏱️ {duration_sec // 60:02d}m {duration_sec % 60:02d}s"

        sub_info = f"{dur_str}  •  {summary}" if dur_str else summary
        if len(sub_info) > 55:
            sub_info = sub_info[:52] + "..."

        ctk.CTkLabel(
            row3,
            text=sub_info,
            font=("Segoe UI", 10),
            text_color=TEXT_DIM,
            anchor="w",
        ).pack(fill="x")

        # Ràng buộc click toàn bộ card
        def _on_click(event=None, s_id=sid):
            self._select_session(s_id)

        card.bind("<Button-1>", _on_click)
        for child in [row1, row2, row3, mod_tag, st_label]:
            child.bind("<Button-1>", _on_click)

        return card

    def _select_session(self, session_id: str):
        """Chọn một phiên và nạp nội dung log lên khung phải."""
        self._selected_session_id = session_id

        # Cập nhật style active border cho cards
        for sid, card in self._session_cards.items():
            if sid == session_id:
                card.configure(border_color=ACCENT, border_width=2, fg_color=BG_CARD)
            else:
                card.configure(border_color=BORDER, border_width=1, fg_color=BG_DARK)

        # Lấy metadata phiên
        sessions = SessionLogManager.get_sessions()
        session_meta = next((s for s in sessions if s.get("session_id") == session_id), None)

        if not session_meta:
            self._display_empty_log()
            return

        # Cập nhật banner thông tin
        mod = session_meta.get("module", "general")
        mod_info = MODULE_CONFIG.get(mod, MODULE_CONFIG["general"])
        st = session_meta.get("status", "SUCCESS")
        user = session_meta.get("username", "default")
        start = session_meta.get("start_time", "--")
        end = session_meta.get("end_time", "--")
        duration = session_meta.get("duration_seconds")
        dur_str = f"{duration}s" if duration is not None else "--"
        if duration and duration >= 60:
            dur_str = f"{duration // 60:02d}m {duration % 60:02d}s"

        self._lbl_session_title.configure(text=f"{mod_info['icon']}  {session_meta.get('title', 'Phiên hoạt động')}")
        meta_str = (
            f"Mã phiên: {session_id}  |  Phân hệ: {mod_info['title']}  |  Người dùng: {user}\n"
            f"Bắt đầu: {start}  →  Kết thúc: {end} (Thời lượng: {dur_str})  |  Trạng thái: {st}\n"
            f"Tóm tắt: {session_meta.get('summary', 'Không có tóm tắt')}"
        )
        self._lbl_session_meta.configure(text=meta_str)

        # Đọc nội dung log
        log_content = SessionLogManager.get_session_log(session_id)
        self._render_log_content(log_content)

    def _render_log_content(self, content: str):
        """Hiển thị nội dung log kèm highlight cú pháp màu sắc."""
        self._txt_log.configure(state="normal")
        self._txt_log.delete("1.0", "end")

        try:
            tb = self._txt_log._textbox
            for line in content.splitlines(keepends=True):
                tag = None
                if "[INFO" in line:
                    tag = "INFO"
                elif "[SUCCESS" in line or "Thành công" in line or "✅" in line:
                    tag = "SUCCESS"
                elif "[WARN" in line or "⚠️" in line:
                    tag = "WARNING"
                elif "[ERROR" in line or "❌" in line or "Lỗi" in line:
                    tag = "ERROR"
                elif "[DEBUG" in line:
                    tag = "DEBUG"
                elif line.startswith("==="):
                    tag = "HEADER"

                if tag:
                    tb.insert("end", line, tag)
                else:
                    tb.insert("end", line)
        except Exception:
            self._txt_log.insert("1.0", content)

        self._txt_log.configure(state="disabled")

    def _display_empty_log(self):
        """Hiển thị trạng thái chưa chọn phiên."""
        self._lbl_session_title.configure(text="Chưa có phiên nào được chọn")
        self._lbl_session_meta.configure(text="Mã phiên: -- | Phân hệ: -- | Thời gian: -- | Trạng thái: --")
        self._txt_log.configure(state="normal")
        self._txt_log.delete("1.0", "end")
        self._txt_log.insert("1.0", "[Vui lòng chọn một phiên trong danh sách bên trái để xem nội dung log]")
        self._txt_log.configure(state="disabled")

    def _copy_log(self):
        """Sao chép toàn bộ text log đang xem vào Clipboard."""
        try:
            content = self._txt_log._textbox.get("1.0", "end-1c")
            if not content.strip() or content.startswith("[Vui lòng"):
                messagebox.showwarning("Thông báo", "Không có nội dung log để sao chép!")
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Thành công", "Đã sao chép toàn bộ nhật ký vào Clipboard!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sao chép: {e}")

    def _open_in_notepad(self):
        """Mở trực tiếp file log bằng Notepad của Windows."""
        if not self._selected_session_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một phiên trước!")
            return

        sessions = SessionLogManager.get_sessions()
        session_meta = next((s for s in sessions if s.get("session_id") == self._selected_session_id), None)
        if not session_meta:
            return

        raw_path = session_meta.get("log_file")
        if raw_path and Path(raw_path).exists():
            try:
                subprocess.Popen(["notepad.exe", str(Path(raw_path).resolve())])
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở Notepad: {e}")
        else:
            messagebox.showwarning("Thông báo", "Không tìm thấy file log trên đĩa!")

    def _open_file_in_explorer(self):
        """Mở và chọn chính xác file log trong Windows Explorer."""
        if not self._selected_session_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một phiên trước!")
            return

        sessions = SessionLogManager.get_sessions()
        session_meta = next((s for s in sessions if s.get("session_id") == self._selected_session_id), None)
        if not session_meta:
            return

        raw_path = session_meta.get("log_file")
        if raw_path and Path(raw_path).exists():
            try:
                if os.name == "nt":
                    subprocess.Popen(f'explorer /select,"{Path(raw_path).resolve()}"')
                else:
                    subprocess.Popen(["xdg-open", str(Path(raw_path).parent)])
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")
        else:
            self._open_logs_folder()

    def _open_logs_folder(self):
        """Mở thư mục gốc chứa toàn bộ logs."""
        try:
            folder = SessionLogManager.get_logs_dir(self._active_module if self._active_module != "all" else None)
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")

    def _delete_current_session(self):
        """Xóa vĩnh viễn phiên đang chọn."""
        if not self._selected_session_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một phiên để xóa!")
            return

        sid = self._selected_session_id
        if not messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc chắn muốn xóa vĩnh viễn nhật ký phiên:\n{sid}?"):
            return

        success = SessionLogManager.delete_session(sid)
        if success:
            self._selected_session_id = None
            self._load_sessions()
            messagebox.showinfo("Thành công", f"Đã xóa phiên {sid}!")
        else:
            messagebox.showerror("Lỗi", f"Không thể xóa phiên {sid}!")
