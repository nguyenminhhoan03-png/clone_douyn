import re
with open('e:/Project_ItWebDev/Python/tiktok-upload-video/gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_accounts_tab = '''class AccountsTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, parent, app=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app = app
        
        self.tabview = ctk.CTkTabview(self, fg_color="transparent")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.tab_tiktok = self.tabview.add("🎵 TikTok")
        self.tab_youtube = self.tabview.add("▶️ YouTube")
        
        self._build_tiktok_tab()
        self._build_youtube_tab()
        
    def _build_tiktok_tab(self):
        hdr = ctk.CTkFrame(self.tab_tiktok, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(hdr, text="Quản lý Tài khoản TikTok", font=("Segoe UI", 16, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="🔄 Làm mới", width=80, height=28, fg_color=BORDER, hover_color=BG_CARD, command=self._load_accounts).pack(side="right", padx=5)
        ctk.CTkButton(hdr, text="➕ Thêm nick mới", width=120, height=28, fg_color=SUCCESS, hover_color="#27ae60", command=self._add_new_account).pack(side="right", padx=(0, 5))
        
        self._list_frame = ctk.CTkScrollableFrame(self.tab_tiktok, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._list_frame.pack(fill="both", expand=True)
        
        self._proxy_entries = {}
        self._load_accounts()

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
        
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        username = username.replace("@", "_").replace(".", "_")
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

    def _manual_login(self, acc_name):
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
                from tkinter import messagebox
                messagebox.showinfo("Thành công", f"Đã đóng trình duyệt và lưu phiên đăng nhập cho {acc_name}.")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Lỗi", f"Lỗi khi mở đăng nhập: {e}")
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
'''

accounts_pattern = re.compile(r"class AccountsTab.*?class FarmTab", re.DOTALL)
content = accounts_pattern.sub(new_accounts_tab + "\n\nclass FarmTab", content)

youtube_manager_pattern = re.compile(r"class YouTubeAccountManagerWindow.*?def _delete_account.*?messagebox.showerror[^\n]*\n", re.DOTALL)
content = youtube_manager_pattern.sub("", content)

# Update buttons in UploadTab and AutoTab
content = content.replace(
    'command=self._open_youtube_account_manager',
    'command=lambda: self.app._nav(5)'
)
content = content.replace(
    'def _open_youtube_account_manager(self):',
    'def _open_youtube_account_manager_old(self):'
)

# Rename the label button from Quản lý Kênh to Quản lý Kênh (AccountsTab) or just remove the reference.
# Let's write the file.
with open('e:/Project_ItWebDev/Python/tiktok-upload-video/gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch 2 successfully applied")