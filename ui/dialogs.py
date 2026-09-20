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
    SUCCESS, WARNING, DANGER, TEXT_MAIN, TEXT_DIM, TEXT_MUTED, BORDER
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
#  RegisterWindow - Cửa sổ Đăng ký (Hỗ trợ mở độc lập hoặc từ modal khác)
# ═══════════════════════════════════════════════════════════════════════════════
class RegisterWindow(ctk.CTkToplevel):
    def __init__(self, master, on_registered=None):
        super().__init__(master)
        self.on_registered = on_registered
        
        # Đọc cấu hình gói Free động từ Server (không hardcode)
        self.free_info = auth_client.get_free_plan_info()
        self.free_days = self.free_info.get("days", 10)

        self.title(f"🎁 Đăng Ký Tài Khoản Mới (Free {self.free_days} Ngày Full AI)")
        self.geometry("460x520")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self.transient(master)
        self.grab_set()

        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 460, 520
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(
            hdr, text="🎉 Tạo Tài Khoản Mới",
            font=("Segoe UI", 22, "bold"), text_color=TEXT_MAIN
        ).pack()
        ctk.CTkLabel(
            hdr, text=f"Kích hoạt ngay {self.free_days} ngày trải nghiệm Full AI Cloud & Quota VIP",
            font=("Segoe UI", 11), text_color=TEXT_MUTED
        ).pack(pady=(2, 0))

        # Gift Promo
        promo_box = ctk.CTkFrame(self, fg_color="#271E08", border_width=1, border_color="#D97706", corner_radius=10)
        promo_box.pack(padx=24, pady=(0, 14), fill="x")
        ctk.CTkLabel(
            promo_box, text="🎁 Đăng ký xong là sử dụng được ngay, không cần cấu hình phức tạp!",
            font=("Segoe UI", 11, "bold"), text_color="#FDE68A", justify="center"
        ).pack(padx=10, pady=8)

        # Form
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=24)

        ctk.CTkLabel(form, text="Tên đăng nhập:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.entry_user = ctk.CTkEntry(
            form, placeholder_text="Tên đăng nhập (viết liền, không dấu)...",
            height=38, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.entry_user.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(form, text="Mật khẩu:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.entry_pass = ctk.CTkEntry(
            form, placeholder_text="Nhập mật khẩu...", show="*",
            height=38, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.entry_pass.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(form, text="Xác nhận mật khẩu:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.entry_pass_confirm = ctk.CTkEntry(
            form, placeholder_text="Nhập lại mật khẩu...", show="*",
            height=38, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.entry_pass_confirm.pack(fill="x", pady=(0, 14))

        self.btn_register = ctk.CTkButton(
            form, text=f"🎉 ĐĂNG KÝ NHẬN {self.free_days} NGÀY FREE", height=42,
            command=self._do_register, font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#059669", corner_radius=8
        )
        self.btn_register.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            form, text="✕ Đóng cửa sổ", height=30,
            command=self.destroy, font=("Segoe UI", 11),
            fg_color="transparent", text_color=TEXT_MUTED, hover_color="#131826"
        ).pack()

        self.bind("<Return>", lambda e: self._do_register())
        self.after(100, self.entry_user.focus_set)

    def _do_register(self):
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get()
        pwd2 = self.entry_pass_confirm.get()
        
        if not user or not pwd:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!")
            return
            
        if len(user) < 3:
            messagebox.showwarning("Lỗi", "Tên đăng nhập phải có ít nhất 3 ký tự!")
            return

        if pwd != pwd2:
            messagebox.showwarning("Lỗi", "Mật khẩu xác nhận không khớp!")
            return
            
        self.btn_register.configure(state="disabled", text="⏳ Đang khởi tạo tài khoản...")
        
        def run():
            success, msg = auth_client.register(user, pwd)
            self.after(0, self._handle_result, success, msg, user, pwd)
            
        threading.Thread(target=run, daemon=True).start()
        
    def _handle_result(self, success, msg, user, pwd):
        if success:
            messagebox.showinfo("Thành công 🎉", f"Đăng ký thành công tài khoản '{user}'!\n🎁 Kích hoạt {self.free_days} ngày dùng thử Free Full tính năng AI.")
            if self.on_registered:
                self.on_registered(user, pwd)
            self.destroy()
        else:
            messagebox.showerror("Đăng ký thất bại", msg)
            self.btn_register.configure(state="normal", text=f"🎉 ĐĂNG KÝ NHẬN {self.free_days} NGÀY FREE")


# ═══════════════════════════════════════════════════════════════════════════════
#  LoginWindow - Cửa sổ Đăng nhập & Đăng ký Tích hợp (Tabs Mượt mà, Nổi bật)
# ═══════════════════════════════════════════════════════════════════════════════
class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        
        # Đọc cấu hình gói Free động từ Server (không hardcode)
        self.free_info = auth_client.get_free_plan_info()
        self.free_days = self.free_info.get("days", 10)
        days_txt = f"{self.free_days} Ngày"

        self.title(f"🎬 DouyinBot | Đăng Nhập & Kích Hoạt (🎁 Free {days_txt})")
        self.geometry("460x540")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Căn giữa màn hình
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 460, 540
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        # ── 1. Branding Header ──
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(18, 8))
        
        ctk.CTkLabel(
            hdr, text="🎬 DouyinBot SaaS",
            font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN
        ).pack()
        ctk.CTkLabel(
            hdr, text="Hệ Thống Tự Động Hóa Video TikTok / Douyin Chuyên Nghiệp",
            font=("Segoe UI", 11), text_color=TEXT_MUTED
        ).pack(pady=(2, 0))

        # ── 2. Gift Promo Box (Golden Amber Glow) ──
        promo_box = ctk.CTkFrame(self, fg_color="#271E08", border_width=1, border_color="#D97706", corner_radius=10)
        promo_box.pack(padx=24, pady=(0, 12), fill="x")
        
        p_row = ctk.CTkFrame(promo_box, fg_color="transparent")
        p_row.pack(fill="x", padx=12, pady=7)
        
        ctk.CTkLabel(
            p_row, text="🎁 ƯU ĐÃI THÀNH VIÊN MỚI:",
            font=("Segoe UI", 11, "bold"), text_color="#F59E0B"
        ).pack(side="left")
        ctk.CTkLabel(
            p_row, text=f" Tặng {self.free_days} ngày Full AI Cloud & Quota VIP!",
            font=("Segoe UI", 11), text_color="#FDE68A"
        ).pack(side="left")

        # ── 3. Segmented Switcher (Tab Đăng Nhập / Đăng Ký) ──
        self.tab_reg_label = f"🎁 Đăng Ký (Free {days_txt})"
        self.tab_switch = ctk.CTkSegmentedButton(
            self, values=["🔑 Đăng Nhập", self.tab_reg_label],
            command=self._on_tab_change, height=36,
            font=("Segoe UI", 12, "bold"),
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            unselected_color="#131826", unselected_hover_color="#1E293B"
        )
        self.tab_switch.set("🔑 Đăng Nhập")
        self.tab_switch.pack(padx=24, pady=(0, 12), fill="x")

        # ── 4. Main Container ──
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=24)

        # ── 4A. Login Form Frame ──
        self.frame_login = ctk.CTkFrame(self.container, fg_color="transparent")
        
        ctk.CTkLabel(self.frame_login, text="Tên đăng nhập:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.entry_user = ctk.CTkEntry(
            self.frame_login, placeholder_text="Nhập username của bạn...",
            height=38, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.entry_user.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self.frame_login, text="Mật khẩu:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.entry_pass = ctk.CTkEntry(
            self.frame_login, placeholder_text="Nhập mật khẩu...", show="*",
            height=38, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.entry_pass.pack(fill="x", pady=(0, 12))

        self.btn_login = ctk.CTkButton(
            self.frame_login, text="🚀 ĐĂNG NHẬP NGAY", height=42,
            command=self._do_login, font=("Segoe UI", 13, "bold"),
            fg_color="#2563EB", hover_color="#1D4ED8", corner_radius=8
        )
        self.btn_login.pack(fill="x", pady=(0, 12))

        # Phân cách
        div_frame = ctk.CTkFrame(self.frame_login, fg_color="transparent")
        div_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkFrame(div_frame, fg_color=BORDER, height=1).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(div_frame, text="  Chưa có tài khoản?  ", font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(side="left")
        ctk.CTkFrame(div_frame, fg_color=BORDER, height=1).pack(side="left", fill="x", expand=True)

        # Nút Đăng Ký nổi bật (Golden CTA Button siêu dễ nhìn & kích thích người dùng bấm)
        self.btn_goto_register = ctk.CTkButton(
            self.frame_login,
            text=f"🎁 Đăng Ký Tài Khoản Mới (Nhận {days_txt} Free)",
            height=40, font=("Segoe UI", 12, "bold"),
            fg_color="#3B2A10", hover_color="#78350F",
            text_color="#FDE68A", border_width=1.5, border_color="#F59E0B", corner_radius=8,
            command=lambda: self._set_mode("register")
        )
        self.btn_goto_register.pack(fill="x")

        # ── 4B. Register Form Frame ──
        self.frame_register = ctk.CTkFrame(self.container, fg_color="transparent")

        ctk.CTkLabel(self.frame_register, text="Tên đăng nhập mới:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.reg_user = ctk.CTkEntry(
            self.frame_register, placeholder_text="Chọn tên đăng nhập (viết liền, không dấu)...",
            height=36, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.reg_user.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self.frame_register, text="Mật khẩu:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.reg_pass = ctk.CTkEntry(
            self.frame_register, placeholder_text="Nhập mật khẩu...", show="*",
            height=36, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.reg_pass.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self.frame_register, text="Xác nhận lại mật khẩu:", font=("Segoe UI", 11, "bold"), text_color=TEXT_DIM).pack(anchor="w", padx=4, pady=(0, 2))
        self.reg_pass_confirm = ctk.CTkEntry(
            self.frame_register, placeholder_text="Nhập lại mật khẩu vừa đặt...", show="*",
            height=36, font=("Segoe UI", 12), fg_color="#131826", border_color=BORDER, corner_radius=8
        )
        self.reg_pass_confirm.pack(fill="x", pady=(0, 12))

        self.btn_register_submit = ctk.CTkButton(
            self.frame_register,
            text=f"🎉 ĐĂNG KÝ & KÍCH HOẠT {days_txt.upper()} FREE",
            height=42, font=("Segoe UI", 13, "bold"),
            fg_color=SUCCESS, hover_color="#059669", corner_radius=8,
            command=self._do_register
        )
        self.btn_register_submit.pack(fill="x", pady=(0, 10))

        self.btn_goto_login = ctk.CTkButton(
            self.frame_register,
            text="👈 Đã có tài khoản? Bấm để Đăng nhập",
            height=28, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", text_color="#38BDF8", hover_color="#131826",
            command=lambda: self._set_mode("login")
        )
        self.btn_goto_login.pack()

        # Hiển thị mặc định
        self._current_mode = "login"
        self._set_mode("login")

        # Bắt phím Enter
        self.bind("<Return>", self._on_enter_pressed)
        self.after(100, self.entry_user.focus_set)

    def _on_tab_change(self, value):
        if "Đăng Ký" in value:
            self._set_mode("register")
        else:
            self._set_mode("login")

    def _set_mode(self, mode):
        self._current_mode = mode
        if mode == "login":
            self.tab_switch.set("🔑 Đăng Nhập")
            self.frame_register.pack_forget()
            self.frame_login.pack(fill="both", expand=True)
            self.after(50, self.entry_user.focus_set)
        else:
            self.tab_switch.set(self.tab_reg_label)
            self.frame_login.pack_forget()
            self.frame_register.pack(fill="both", expand=True)
            self.after(50, self.reg_user.focus_set)

    def _on_enter_pressed(self, event=None):
        if self._current_mode == "login":
            self._do_login()
        else:
            self._do_register()

    def _do_login(self):
        user = self.entry_user.get().strip()
        pwd = self.entry_pass.get()
        if not user or not pwd:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!")
            return
            
        self.btn_login.configure(state="disabled", text="⏳ Đang xác thực...")
        
        def run():
            success, msg = auth_client.login(user, pwd)
            self.after(0, self._handle_login_result, success, msg)
            
        threading.Thread(target=run, daemon=True).start()
        
    def _handle_login_result(self, success, msg):
        if success:
            self.grab_release()
            self.destroy()
            self.on_success()
        else:
            messagebox.showerror("Lỗi đăng nhập", msg)
            self.btn_login.configure(state="normal", text="🚀 ĐĂNG NHẬP NGAY")

    def _do_register(self):
        user = self.reg_user.get().strip()
        pwd = self.reg_pass.get()
        pwd2 = self.reg_pass_confirm.get()
        
        if not user or not pwd:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu!")
            return
            
        if len(user) < 3:
            messagebox.showwarning("Lỗi", "Tên đăng nhập phải có ít nhất 3 ký tự!")
            return

        if pwd != pwd2:
            messagebox.showwarning("Lỗi", "Mật khẩu xác nhận không khớp!")
            return
            
        self.btn_register_submit.configure(state="disabled", text="⏳ Đang khởi tạo tài khoản...")
        
        def run():
            success, msg = auth_client.register(user, pwd)
            self.after(0, self._handle_register_result, success, msg, user, pwd)
            
        threading.Thread(target=run, daemon=True).start()

    def _handle_register_result(self, success, msg, user, pwd):
        if success:
            days_txt = f"{self.free_days} Ngày"
            messagebox.showinfo(
                "Đăng Ký Thành Công! 🎉",
                f"Chúc mừng bạn đã tạo tài khoản '{user}' thành công!\n"
                f"🎁 Hệ thống đã kích hoạt {self.free_days} ngày dùng thử Free Full tính năng AI.\n\n"
                f"Hệ thống sẽ tự động đăng nhập vào phần mềm..."
            )
            # Tự động đăng nhập
            def auto_login():
                succ, lmsg = auth_client.login(user, pwd)
                def _done():
                    if succ:
                        self.grab_release()
                        self.destroy()
                        self.on_success()
                    else:
                        self.entry_user.delete(0, "end")
                        self.entry_user.insert(0, user)
                        self.entry_pass.delete(0, "end")
                        self.entry_pass.insert(0, pwd)
                        self._set_mode("login")
                        self.btn_register_submit.configure(state="normal", text=f"🎉 ĐĂNG KÝ & KÍCH HOẠT {days_txt.upper()} FREE")
                self.after(0, _done)
            threading.Thread(target=auto_login, daemon=True).start()
        else:
            days_txt = f"{self.free_days} Ngày"
            messagebox.showerror("Đăng ký thất bại", msg)
            self.btn_register_submit.configure(state="normal", text=f"🎉 ĐĂNG KÝ & KÍCH HOẠT {days_txt.upper()} FREE")

    def _on_close(self):
        self.master.destroy()
