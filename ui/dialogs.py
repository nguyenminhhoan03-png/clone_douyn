"""
Secondary dialog windows and modals for TikTok/Douyin Desktop App.
Includes InputJSONWindow, RegisterWindow, and LoginWindow.
"""

import os
import json
import threading
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ui.theme import (
    BG_DARK, BG_CARD, ACCENT, ACCENT_HOVER,
    SUCCESS, WARNING, DANGER, TEXT_MAIN, TEXT_DIM, BORDER
)
from auth_client import auth_client


def get_user_cookies_dir() -> Path:
    """Lấy đường dẫn thư mục cookies của người dùng hiện tại."""
    from config.settings import COOKIES_DIR
    username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
    username = username.replace("@", "_").replace(".", "_")
    user_dir = COOKIES_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


# ═══════════════════════════════════════════════════════════════════════════════
#  InputJSONWindow - Cửa sổ nhập/sửa cookie JSON
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

        ctk.CTkLabel(
            self, text="Tên tài khoản (vd: tiktok_acc1):", font=("Segoe UI", 12)
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        
        self.name_entry = ctk.CTkEntry(self, font=("Segoe UI", 12))
        self.name_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=0)
        self.name_entry.insert(0, initial_name if initial_name else "tiktok_")
        
        ctk.CTkLabel(
            self, text="Dán nội dung JSON (từ Cookie Editor):", font=("Segoe UI", 12)
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(10, 4))
        
        self.json_text = ctk.CTkTextbox(self, font=("Consolas", 11), wrap="word")
        self.json_text.grid(row=3, column=0, sticky="nsew", padx=16, pady=0)
        if initial_content:
            self.json_text.insert("1.0", initial_content)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=16)
        
        ctk.CTkButton(
            btn_frame, text="Lưu", fg_color=SUCCESS, hover_color="#27ae60", command=self._save_json
        ).pack(side="left")
        ctk.CTkButton(
            btn_frame, text="Hủy", fg_color=BORDER, hover_color=BG_CARD, command=self._on_close
        ).pack(side="right")

    def _save_json(self):
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
            json.loads(content)
            user_dir = get_user_cookies_dir()
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
#  RegisterWindow - Cửa sổ Đăng ký
# ═══════════════════════════════════════════════════════════════════════════════
class RegisterWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        
        self.title("🎁 Đăng ký (Free 10 Ngày Full AI)")
        self.geometry("440x420")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self.transient(master)
        self.grab_set()
        
        ctk.CTkLabel(
            self, text="Tạo Tài Khoản Mới",
            font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN
        ).pack(pady=(20, 6))

        promo_box = ctk.CTkFrame(self, fg_color="#271E08", border_width=1, border_color="#D97706", corner_radius=8)
        promo_box.pack(padx=24, pady=(0, 12), fill="x")
        ctk.CTkLabel(
            promo_box, text="🎁 Tặng 10 ngày dùng thử Full tính năng AI!",
            font=("Segoe UI", 11, "bold"), text_color="#FDE68A", justify="center"
        ).pack(padx=10, pady=8)
        
        self.entry_user = ctk.CTkEntry(self, placeholder_text="Tên đăng nhập", width=270)
        self.entry_user.pack(pady=8)
        
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Mật khẩu", show="*", width=270)
        self.entry_pass.pack(pady=8)
        
        self.entry_pass_confirm = ctk.CTkEntry(self, placeholder_text="Xác nhận Mật khẩu", show="*", width=270)
        self.entry_pass_confirm.pack(pady=8)
        
        self.btn_register = ctk.CTkButton(
            self, text="🎉 Đăng ký nhận 10 ngày Free", width=270, height=40,
            command=self._do_register, font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#059669"
        )
        self.btn_register.pack(pady=(14, 10))
        
    def _do_register(self):
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get()
        pwd2 = self.entry_pass_confirm.get()
        
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
            
        threading.Thread(target=run, daemon=True).start()
        
    def _handle_result(self, success, msg):
        if success:
            messagebox.showinfo("Thành công", "Đăng ký thành công!\n🎁 Kích hoạt 10 ngày dùng thử Free Full tính năng AI.")
            self.destroy()
        else:
            messagebox.showerror("Lỗi", msg)
            self.btn_register.configure(state="normal", text="🎉 Đăng ký nhận 10 ngày Free")


# ═══════════════════════════════════════════════════════════════════════════════
#  LoginWindow - Cửa sổ Đăng nhập
# ═══════════════════════════════════════════════════════════════════════════════
class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        
        self.title("🎬 DouyinBot | Đăng Nhập (🎁 Free 10 Ngày)")
        self.geometry("440x420")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        ctk.CTkLabel(
            self, text="DouyinBot SaaS",
            font=("Segoe UI", 26, "bold"), text_color=TEXT_MAIN
        ).pack(pady=(20, 6))

        promo_box = ctk.CTkFrame(self, fg_color="#271E08", border_width=1, border_color="#D97706", corner_radius=8)
        promo_box.pack(padx=24, pady=(0, 12), fill="x")
        ctk.CTkLabel(
            promo_box, text="🎁 Đăng ký mới nhận ngay 10 ngày dùng thử Full AI!",
            font=("Segoe UI", 11, "bold"), text_color="#FDE68A", justify="center"
        ).pack(padx=10, pady=8)
        
        self.entry_user = ctk.CTkEntry(self, placeholder_text="Tên đăng nhập", width=270)
        self.entry_user.pack(pady=8)
        
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Mật khẩu", show="*", width=270)
        self.entry_pass.pack(pady=8)
        
        self.btn_login = ctk.CTkButton(
            self, text="Đăng nhập", width=270, height=38,
            command=self._do_login, font=("Segoe UI", 13, "bold")
        )
        self.btn_login.pack(pady=(14, 8))
        
        self.btn_register = ctk.CTkButton(
            self, text="🎁 Chưa có tài khoản? Đăng ký nhận 10 ngày Free", width=300, height=30,
            command=self._open_register, font=("Segoe UI", 12, "bold"),
            fg_color="transparent", text_color="#FBBF24", hover_color=BG_CARD
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
            
        threading.Thread(target=run, daemon=True).start()
        
    def _handle_result(self, success, msg):
        if success:
            self.grab_release()
            self.destroy()
            self.on_success()
        else:
            messagebox.showerror("Lỗi", msg)
            self.btn_login.configure(state="normal", text="Đăng nhập")

    def _on_close(self):
        self.master.destroy()
