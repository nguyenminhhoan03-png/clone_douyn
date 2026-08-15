import re
import os

with open('e:/Project_ItWebDev/Python/tiktok-upload-video/gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

accounts_tab_code = """
class AccountsTab(ctk.CTkFrame, TaskMixin):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(hdr, text="Quản lý Tài khoản (TikTok)", font=("Segoe UI", 16, "bold")).pack(side="left")
        ctk.CTkButton(hdr, text="🔄 Làm mới", width=80, height=28, fg_color=BORDER, hover_color=BG_CARD, command=self._load_accounts).pack(side="right", padx=5)
        ctk.CTkButton(hdr, text="➕ Thêm nick mới", width=120, height=28, fg_color=SUCCESS, hover_color="#27ae60", command=self._add_new_account).pack(side="right", padx=(0, 5))
        
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self._list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self._proxy_entries = {}
        self._load_accounts()

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
"""

new_farm_tab_load_accounts = """
    def _load_accounts(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()
        
        from config.settings import COOKIES_DIR
        from auth_client import auth_client
        username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
        user_dir = COOKIES_DIR / username
        
        accounts = [f.name for f in user_dir.glob("tiktok_*.json")]
        if not accounts:
            ctk.CTkLabel(self._list_frame, text="Chưa có tài khoản nào. Vui lòng sang tab 'Tài khoản' để thêm.", text_color=TEXT_DIM).pack(pady=20)
            return
            
        for acc in accounts:
            row = ctk.CTkFrame(self._list_frame, fg_color=BG_DARK, corner_radius=8, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=4, ipady=2)
            row.grid_columnconfigure(0, weight=1)
            
            var = ctk.BooleanVar(value=False)
            self._checkboxes[acc] = var
            
            display_acc = acc.replace("tiktok_", "").replace(".json", "")
            if len(display_acc) > 20:
                display_acc = display_acc[:17] + "..."
                
            cb = ctk.CTkCheckBox(row, text=display_acc, variable=var, font=("Segoe UI", 12, "bold"))
            cb.grid(row=0, column=0, padx=(12, 10), pady=10, sticky="w")
"""

# Replace FarmTab's methods
# Remove _load_accounts, _add_new_account, _manual_login, _load_proxies, _save_proxies
# and insert new _load_accounts
farm_tab_pattern = re.compile(r"    def _load_accounts\(self\):.*?    def _start_farm\(self\):", re.DOTALL)
content = farm_tab_pattern.sub(new_farm_tab_load_accounts + "\n    def _start_farm(self):", content)

# Remove proxy-related stuff in FarmTab's UI (the buttons in header)
content = content.replace('ctk.CTkButton(hdr, text="➕ Thêm nick mới", width=100, height=24, fg_color="#2ecc71", hover_color="#27ae60", command=self._add_new_account).pack(side="right", padx=(0, 10))', '')

# Insert AccountsTab right before FarmTab
content = content.replace("class FarmTab(ctk.CTkFrame, TaskMixin):", accounts_tab_code + "\n\nclass FarmTab(ctk.CTkFrame, TaskMixin):")

# Update TABS
old_tabs = '''    TABS = [
        ("📊", "Dashboard", DashboardTab),
        ("🔍", "Crawl",     CrawlTab),
        ("🎞️", "Process",   ProcessTab),
        ("📤", "Upload",    UploadTab),
        ("🤖", "Auto",      AutoTab),
        ("🌱", "Farm",      FarmTab),
        ("⚙️", "Settings",  SettingsTab),
    ]'''
new_tabs = '''    TABS = [
        ("📊", "Dashboard", DashboardTab),
        ("🔍", "Crawl",     CrawlTab),
        ("🎞️", "Process",   ProcessTab),
        ("📤", "Upload",    UploadTab),
        ("🤖", "Auto",      AutoTab),
        ("👥", "Accounts",  AccountsTab),
        ("🌱", "Farm",      FarmTab),
        ("⚙️", "Settings",  SettingsTab),
    ]'''
content = content.replace(old_tabs, new_tabs)

# Update the index checks in _build_sidebar
content = content.replace('if hasattr(self, "_tab_frames") and len(self._tab_frames) > 5:\n                farm_tab = self._tab_frames[5]', 'if hasattr(self, "_tab_frames") and len(self._tab_frames) > 5:\n                acc_tab = self._tab_frames[5]\n                if hasattr(acc_tab, "_load_accounts"):\n                    acc_tab._load_accounts()\n            if hasattr(self, "_tab_frames") and len(self._tab_frames) > 6:\n                farm_tab = self._tab_frames[6]')

# update _handle_sidebar_upgrade to 7
content = content.replace('self._nav(6)', 'self._nav(7)')
content = content.replace('len(self._tab_frames) > 6:', 'len(self._tab_frames) > 7:')
content = content.replace('self._tab_frames[6]._show_payment_dialog()', 'self._tab_frames[7]._show_payment_dialog()')

with open('e:/Project_ItWebDev/Python/tiktok-upload-video/gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched successfully")
