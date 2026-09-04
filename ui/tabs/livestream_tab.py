import customtkinter as ctk
import threading
from tkinter import messagebox

# Colors
BG_DARK = "#1E1E2E"
BG_CARD = "#2A2A3C"
BORDER = "#3B3B54"
TEXT_MAIN = "#FFFFFF"
TEXT_MUTED = "#A0A0B0"
PURPLE = "#8E44AD"
ORANGE = "#E67E22"
GREEN = "#2ECC71"

class TaskMixin:
    """Mock TaskMixin if not inherited properly"""
    def log(self, msg):
        if hasattr(self, "_txt_log"):
            self._txt_log.configure(state="normal")
            self._txt_log.insert("end", f"{msg}\n")
            self._txt_log.see("end")
            self._txt_log.configure(state="disabled")
        else:
            print(msg)

class LivestreamTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        
        self.grid_columnconfigure(0, weight=6)  # Left column
        self.grid_columnconfigure(1, weight=4)  # Right column
        self.grid_rowconfigure(1, weight=1)
        
        # --- HEADER ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            header_frame, 
            text="📺 Seeding Livestream MKT Pro ❓", 
            font=("Segoe UI", 22, "bold"), 
            text_color=TEXT_MAIN
        ).grid(row=0, column=0, sticky="w")
        
        btn_select_all = ctk.CTkButton(
            header_frame, text="☑ Chọn tất", width=100, height=30, 
            fg_color=PURPLE, hover_color="#9B59B6", font=("Segoe UI", 12, "bold")
        )
        btn_select_all.grid(row=0, column=2, padx=10)
        
        btn_refresh = ctk.CTkButton(
            header_frame, text="⟲ Làm mới", width=100, height=30,
            fg_color=BORDER, hover_color=BG_CARD, font=("Segoe UI", 12, "bold")
        )
        btn_refresh.grid(row=0, column=3)

        # --- LEFT COLUMN (Accounts & Log) ---
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=6) # Accounts
        left_frame.grid_rowconfigure(1, weight=4) # Log

        # 1. Accounts Table
        acc_frame = ctk.CTkFrame(left_frame, fg_color=BG_CARD, corner_radius=8)
        acc_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        acc_frame.grid_columnconfigure(1, weight=2)
        acc_frame.grid_columnconfigure(2, weight=3)
        acc_frame.grid_columnconfigure(3, weight=1)
        
        # Table Header
        header_bg = BORDER
        ctk.CTkLabel(acc_frame, text="[]", fg_color=header_bg, font=("Segoe UI", 12, "bold"), height=35).grid(row=0, column=0, sticky="ew", padx=1)
        ctk.CTkLabel(acc_frame, text="Tài khoản", fg_color=header_bg, font=("Segoe UI", 12, "bold"), anchor="w").grid(row=0, column=1, sticky="ew", padx=1)
        ctk.CTkLabel(acc_frame, text="Proxy/IP", fg_color=header_bg, font=("Segoe UI", 12, "bold"), anchor="w").grid(row=0, column=2, sticky="ew", padx=1)
        ctk.CTkLabel(acc_frame, text="Trạng thái", fg_color=header_bg, font=("Segoe UI", 12, "bold")).grid(row=0, column=3, sticky="ew", padx=1)
        
        self.scroll_accs = ctk.CTkScrollableFrame(acc_frame, fg_color="transparent")
        self.scroll_accs.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=5)
        self.scroll_accs.grid_columnconfigure(1, weight=2)
        self.scroll_accs.grid_columnconfigure(2, weight=3)
        self.scroll_accs.grid_columnconfigure(3, weight=1)
        
        self._acc_vars = {}
        self._load_accounts()
        
        # 2. Log Area
        log_frame = ctk.CTkFrame(left_frame, fg_color=BG_CARD, corner_radius=8)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(log_frame, text="📄 Nhật ký hoạt động (Log)", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self._txt_log = ctk.CTkTextbox(log_frame, fg_color=BG_DARK, text_color=TEXT_MAIN, font=("Consolas", 11))
        self._txt_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._txt_log.configure(state="disabled")

        # --- RIGHT COLUMN (Configurations) ---
        right_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        right_frame.grid(row=1, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Panel 1: Cấu hình chung
        p1 = self._create_panel(right_frame, "⚙ Cấu hình chung", row=0)
        
        self._add_config_row(p1, 0, "Động cơ chạy (Engine)", ctk.CTkOptionMenu(p1, values=["CloakBrowser (Siêu sạch)", "Chromium (Mặc định)"], fg_color=PURPLE, button_color="#732D91"))
        self._add_config_row(p1, 1, "Số luồng chạy đồng thời 🛈", ctk.CTkOptionMenu(p1, values=["1", "2", "3", "5", "10"], width=60))
        self._add_config_row(p1, 2, "Khoảng thời gian giữa hai lần hành động 🛈", self._create_range_input(p1, "20", "30", "giây"))
        self._add_config_row(p1, 3, "Đổi tài khoản nếu lỗi liên tục 🛈", self._create_single_input(p1, "5", "lần"))
        
        row4 = ctk.CTkFrame(p1, fg_color="transparent")
        row4.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        row4.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row4, text="Lặp lại hành động 🛈", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w")
        ctk.CTkSwitch(row4, text="", width=40).grid(row=0, column=1, sticky="e")
        
        self._add_config_row(p1, 5, "Lặp lại hành động từ 🛈", self._create_range_input(p1, "1", "3", "lần"))
        self._add_config_row(p1, 6, "Thời gian dừng giữa hai lần lặp 🛈", self._create_single_input(p1, "10", "giây"))
        
        # Panel 2: Cấu hình lập lịch
        p2 = self._create_panel(right_frame, "🔗 Cấu hình lập lịch", row=1)
        self._add_config_row(p2, 0, "Chọn loại seeding", ctk.CTkOptionMenu(p2, values=["Seeding livestream", "Seeding video"]))
        
        row_link = ctk.CTkFrame(p2, fg_color="transparent")
        row_link.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        btn_nhap = ctk.CTkButton(row_link, text="Nhập link", fg_color=PURPLE, hover_color="#9B59B6", width=100, command=self._open_link_popup)
        btn_nhap.pack(side="left")
        self.lbl_link_count = ctk.CTkLabel(row_link, text="Số lượng đã chọn: 0", font=("Segoe UI", 12, "italic"))
        self.lbl_link_count.pack(side="left", padx=10)
        self.links = []
        
        row_order = ctk.CTkFrame(p2, fg_color="transparent")
        row_order.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        ctk.CTkLabel(row_order, text="Seeding theo", font=("Segoe UI", 12)).pack(side="left", padx=(0, 20))
        self.radio_var = ctk.StringVar(value="Theo thứ tự")
        ctk.CTkRadioButton(row_order, text="Theo thứ tự", variable=self.radio_var, value="Theo thứ tự").pack(side="left", padx=10)
        ctk.CTkRadioButton(row_order, text="Ngẫu nhiên", variable=self.radio_var, value="Ngẫu nhiên").pack(side="left", padx=10)
        
        self._add_config_row(p2, 3, "Mỗi tài khoản seeding từ 🛈", self._create_range_input(p2, "1", "1", "link"))
        
        ctk.CTkCheckBox(p2, text="Không seeding trùng link giữa các tài khoản 🛈").grid(row=4, column=0, columnspan=2, sticky="w", pady=5)
        ctk.CTkCheckBox(p2, text="Xóa link khỏi danh sách sau khi seeding hoàn thành 🛈").grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        
        # Panel 3: Cấu hình hành động
        p3 = self._create_panel(right_frame, "🎯 Cấu hình hành động", row=2)
        
        row_time = ctk.CTkFrame(p3, fg_color="transparent")
        row_time.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        row_time.grid_columnconfigure(1, weight=1)
        chk_time = ctk.CTkCheckBox(row_time, text="Thời gian xem: 🛈")
        chk_time.select()
        chk_time.grid(row=0, column=0, sticky="w")
        self._create_range_input(row_time, "20", "30", "phút").grid(row=0, column=1, sticky="e")
        
        row_heart = ctk.CTkFrame(p3, fg_color="transparent")
        row_heart.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        row_heart.grid_columnconfigure(1, weight=1)
        chk_heart = ctk.CTkCheckBox(row_heart, text="Thả tim ngẫu nhiên: 🛈")
        chk_heart.select()
        chk_heart.grid(row=0, column=0, sticky="w")
        self._create_range_input(row_heart, "10", "30", "lần").grid(row=0, column=1, sticky="e")

    def _create_panel(self, parent, title, row):
        frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 15))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        
        lbl = ctk.CTkLabel(frame, text=title, font=("Segoe UI", 14, "bold"), text_color=PURPLE)
        lbl.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 15))
        return frame

    def _add_config_row(self, parent, row, label_text, widget):
        # row starts from 1 because 0 is title
        lbl = ctk.CTkLabel(parent, text=label_text, font=("Segoe UI", 12))
        lbl.grid(row=row+1, column=0, sticky="w", padx=10, pady=5)
        widget.grid(row=row+1, column=1, sticky="e", padx=10, pady=5)
        
    def _create_range_input(self, parent, val1, val2, suffix):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkEntry(f, width=40).pack(side="left")
        f.winfo_children()[0].insert(0, val1)
        ctk.CTkLabel(f, text="đến").pack(side="left", padx=5)
        ctk.CTkEntry(f, width=40).pack(side="left")
        f.winfo_children()[2].insert(0, val2)
        ctk.CTkLabel(f, text=suffix).pack(side="left", padx=5)
        return f

    def _create_single_input(self, parent, val, suffix):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkEntry(f, width=40).pack(side="left")
        f.winfo_children()[0].insert(0, val)
        ctk.CTkLabel(f, text=suffix).pack(side="left", padx=5)
        return f
        
    def _load_accounts(self):
        try:
            from config.settings import COOKIES_DIR
            from auth_client import auth_client
            username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
            username = username.replace("@", "_").replace(".", "_")
            user_dir = COOKIES_DIR / username
            
            if user_dir.exists():
                r = 0
                for file in user_dir.glob("*.json"):
                    if file.name.startswith("tiktok_"):
                        acc_name = file.stem.replace("tiktok_", "")
                        var = ctk.BooleanVar(value=False)
                        self._acc_vars[acc_name] = var
                        
                        chk = ctk.CTkCheckBox(self.scroll_accs, text="", variable=var, width=30)
                        chk.grid(row=r, column=0, padx=5, pady=5, sticky="w")
                        
                        ctk.CTkLabel(self.scroll_accs, text=acc_name, font=("Segoe UI", 12)).grid(row=r, column=1, sticky="w")
                        ctk.CTkLabel(self.scroll_accs, text="---", text_color=TEXT_MUTED).grid(row=r, column=2, sticky="w")
                        
                        status_lbl = ctk.CTkLabel(self.scroll_accs, text="🟢 Còn Cookie", text_color=GREEN, font=("Segoe UI", 12, "bold"))
                        status_lbl.grid(row=r, column=3, sticky="w")
                        
                        btn_frame = ctk.CTkFrame(self.scroll_accs, fg_color="transparent")
                        btn_frame.grid(row=r, column=4, sticky="e", padx=5)
                        

                        
                        btn_cloak = ctk.CTkButton(btn_frame, text="🕵️ Cloak", width=60, height=24, fg_color=PURPLE, hover_color="#732D91", command=lambda a=acc_name: self._open_browser(a, "cloak"))
                        btn_cloak.pack(side="left", padx=2)
                        
                        r += 1
        except Exception as e:
            print(f"Lỗi tải tài khoản: {e}")
            
    def _open_browser(self, acc_name, browser_type):
        self.log(f"Đang mở {browser_type.upper()} cho tài khoản: {acc_name}...")
        messagebox.showinfo("Mở Browser", f"Tính năng mở {browser_type.upper()} cho {acc_name} đang được tích hợp.")
        
    def _open_link_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Nhập Link Livestream")
        popup.geometry("400x300")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        
        ctk.CTkLabel(popup, text="Nhập danh sách link Livestream (mỗi link 1 dòng):").pack(pady=10, padx=10, anchor="w")
        txt = ctk.CTkTextbox(popup, width=380, height=200)
        txt.pack(padx=10, pady=5)
        txt.insert("1.0", "\\n".join(self.links))
        
        def save():
            raw = txt.get("1.0", "end-1c")
            self.links = [l.strip() for l in raw.split("\\n") if l.strip()]
            self.lbl_link_count.configure(text=f"Số lượng đã chọn: {len(self.links)}")
            popup.destroy()
            self.log(f"Đã cập nhật {len(self.links)} link Livestream.")
            
        ctk.CTkButton(popup, text="Lưu", command=save, fg_color=PURPLE, hover_color="#9B59B6").pack(pady=10)