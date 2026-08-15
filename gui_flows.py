import customtkinter as ctk
from tkinter import messagebox
import json
from pathlib import Path

class FlowBuilderDialog(ctk.CTkToplevel):
    def __init__(self, master, on_close_callback=None):
        super().__init__(master)
        self.title("Quản lý Kịch bản Nuôi Nick (Flow Builder)")
        self.geometry("900x600")
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.on_close_callback = on_close_callback
        
        self.flows_file = Path("config/flows.json")
        self.flows = self._load_flows()
        self.current_flow_index = 0 if self.flows else -1
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        
        self._build_ui()
        self.load_flow_list()

    def _load_flows(self):
        if self.flows_file.exists():
            try:
                with open(self.flows_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_flows(self):
        self.flows_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.flows_file, "w", encoding="utf-8") as f:
            json.dump(self.flows, f, ensure_ascii=False, indent=4)
        if self.on_close_callback:
            self.on_close_callback()

    def _build_ui(self):
        # Left Panel: List of flows
        left_panel = ctk.CTkFrame(self, fg_color="#1E293B", width=250)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_panel.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(left_panel, text="Danh sách Kịch bản", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, pady=10)
        
        self.listbox_flows = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.listbox_flows.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        btn_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", pady=10)
        ctk.CTkButton(btn_frame, text="➕ Thêm mới", width=100, fg_color="#2ecc71", hover_color="#27ae60", command=self._add_flow).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🗑 Xóa", width=80, fg_color="#e74c3c", hover_color="#c0392b", command=self._delete_flow).pack(side="right", padx=5)

        # Right Panel: Flow Editor
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.right_panel.grid_rowconfigure(2, weight=1)
        
        # Tiêu đề Kịch bản
        header_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkLabel(header_frame, text="Tên Kịch bản:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
        self.entry_flow_name = ctk.CTkEntry(header_frame, width=300)
        self.entry_flow_name.pack(side="left", padx=5)
        ctk.CTkButton(header_frame, text="💾 Lưu lại toàn bộ", fg_color="#3498db", command=self._save_current_flow).pack(side="right", padx=5)

        # Add step buttons
        add_step_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        add_step_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(add_step_frame, text="Thêm hành động:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
        
        ctk.CTkButton(add_step_frame, text="+ Lướt Xu Hướng", width=120, command=lambda: self._add_step("scroll_foryou")).pack(side="left", padx=5)
        ctk.CTkButton(add_step_frame, text="+ Tìm kiếm & Tương tác", width=150, command=lambda: self._add_step("search_and_interact")).pack(side="left", padx=5)
        ctk.CTkButton(add_step_frame, text="+ Ngâm máy", width=100, command=lambda: self._add_step("rest")).pack(side="left", padx=5)
        ctk.CTkButton(add_step_frame, text="+ Xem Livestream", width=130, fg_color="#e74c3c", hover_color="#c0392b", command=lambda: self._add_step("watch_livestream")).pack(side="left", padx=5)

        # Steps list
        self.steps_container = ctk.CTkScrollableFrame(self.right_panel, fg_color="transparent")
        self.steps_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        self.step_widgets = []

    def load_flow_list(self):
        for widget in self.listbox_flows.winfo_children():
            widget.destroy()
            
        for idx, flow in enumerate(self.flows):
            btn = ctk.CTkButton(
                self.listbox_flows, text=flow.get("name", f"Flow {idx}"), 
                fg_color="#334155" if idx != self.current_flow_index else "#3B82F6",
                anchor="w",
                command=lambda i=idx: self.select_flow(i)
            )
            btn.pack(fill="x", pady=2)
            
        if self.flows and self.current_flow_index >= 0:
            self.load_flow_details(self.flows[self.current_flow_index])
        else:
            self.entry_flow_name.delete(0, 'end')
            self._clear_steps()

    def select_flow(self, idx):
        self.current_flow_index = idx
        self.load_flow_list()

    def _add_flow(self):
        new_flow = {
            "id": f"flow_{len(self.flows)+1}",
            "name": "Kịch bản mới",
            "steps": []
        }
        self.flows.append(new_flow)
        self.current_flow_index = len(self.flows) - 1
        self.load_flow_list()

    def _delete_flow(self):
        if self.current_flow_index >= 0 and self.current_flow_index < len(self.flows):
            if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa kịch bản này?"):
                self.flows.pop(self.current_flow_index)
                self.current_flow_index = len(self.flows) - 1
                self.load_flow_list()
                self._save_flows()

    def _clear_steps(self):
        for w in self.step_widgets:
            w['frame'].destroy()
        self.step_widgets.clear()

    def load_flow_details(self, flow):
        self.entry_flow_name.delete(0, 'end')
        self.entry_flow_name.insert(0, flow.get("name", ""))
        
        self._clear_steps()
        
        for step in flow.get("steps", []):
            self._render_step(step)

    def _add_step(self, step_type):
        step = {"type": step_type}
        if step_type == "scroll_foryou":
            step.update({"duration": 10, "like_ratio": 0.2})
        elif step_type == "search_and_interact":
            step.update({"keyword": "", "watch_count": 3, "like_ratio": 0.5, "follow_ratio": 0.1})
        elif step_type == "rest":
            step.update({"duration": 5})
        elif step_type == "watch_livestream":
            step.update({"live_url": "", "duration": 15, "heart_interval_min": 10, "heart_interval_max": 30, "comment_enabled": False})
            
        self._render_step(step)

    def _render_step(self, step):
        idx = len(self.step_widgets)
        
        frame = ctk.CTkFrame(self.steps_container, fg_color="#1E293B", corner_radius=8)
        frame.pack(fill="x", pady=5, ipady=5)
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        
        step_type = step.get("type")
        title = "Chưa rõ"
        if step_type == "scroll_foryou": title = "📜 Lướt Xu Hướng (For You)"
        elif step_type == "search_and_interact": title = "🔍 Tìm kiếm & Tương tác"
        elif step_type == "rest": title = "💤 Ngâm máy (Nghỉ ngơi)"
        elif step_type == "watch_livestream": title = "📺 Xem Livestream"
        
        ctk.CTkLabel(header, text=f"{idx+1}. {title}", font=("Segoe UI", 12, "bold")).pack(side="left")
        ctk.CTkButton(header, text="🗑", width=30, fg_color="#e74c3c", hover_color="#c0392b", command=lambda f=frame, i=idx: self._remove_step_ui(f, i)).pack(side="right")
        
        # Params body
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="x", padx=10, pady=5)
        
        entries = {}
        
        if step_type == "scroll_foryou":
            ctk.CTkLabel(body, text="Thời gian (phút):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            e_dur = ctk.CTkEntry(body, width=80)
            e_dur.insert(0, str(step.get("duration", 10)))
            e_dur.grid(row=0, column=1, sticky="w", padx=5, pady=2)
            entries["duration"] = e_dur
            
            ctk.CTkLabel(body, text="Tỷ lệ Thả tim (0-1):").grid(row=0, column=2, sticky="w", padx=20, pady=2)
            e_like = ctk.CTkEntry(body, width=80)
            e_like.insert(0, str(step.get("like_ratio", 0.2)))
            e_like.grid(row=0, column=3, sticky="w", padx=5, pady=2)
            entries["like_ratio"] = e_like
            
        elif step_type == "search_and_interact":
            ctk.CTkLabel(body, text="Từ khóa tìm kiếm:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            e_kw = ctk.CTkEntry(body, width=150)
            e_kw.insert(0, str(step.get("keyword", "")))
            e_kw.grid(row=0, column=1, sticky="w", padx=5, pady=2)
            entries["keyword"] = e_kw
            
            ctk.CTkLabel(body, text="Xem mấy video?").grid(row=0, column=2, sticky="w", padx=20, pady=2)
            e_count = ctk.CTkEntry(body, width=80)
            e_count.insert(0, str(step.get("watch_count", 3)))
            e_count.grid(row=0, column=3, sticky="w", padx=5, pady=2)
            entries["watch_count"] = e_count
            
            ctk.CTkLabel(body, text="Tỷ lệ Thả tim (0-1):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            e_like = ctk.CTkEntry(body, width=80)
            e_like.insert(0, str(step.get("like_ratio", 0.5)))
            e_like.grid(row=1, column=1, sticky="w", padx=5, pady=5)
            entries["like_ratio"] = e_like
            
            ctk.CTkLabel(body, text="Tỷ lệ Follow (0-1):").grid(row=1, column=2, sticky="w", padx=20, pady=5)
            e_follow = ctk.CTkEntry(body, width=80)
            e_follow.insert(0, str(step.get("follow_ratio", 0.1)))
            e_follow.grid(row=1, column=3, sticky="w", padx=5, pady=5)
            entries["follow_ratio"] = e_follow
            
        elif step_type == "rest":
            ctk.CTkLabel(body, text="Thời gian nghỉ (phút):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            e_dur = ctk.CTkEntry(body, width=80)
            e_dur.insert(0, str(step.get("duration", 5)))
            e_dur.grid(row=0, column=1, sticky="w", padx=5, pady=2)
            entries["duration"] = e_dur

        elif step_type == "watch_livestream":
            ctk.CTkLabel(body, text="URL Phòng Live:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            e_url = ctk.CTkEntry(body, width=300)
            e_url.insert(0, str(step.get("live_url", "")))
            e_url.grid(row=0, column=1, columnspan=3, sticky="w", padx=5, pady=2)
            entries["live_url"] = e_url

            ctk.CTkLabel(body, text="Thời gian xem (phút):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
            e_dur = ctk.CTkEntry(body, width=80)
            e_dur.insert(0, str(step.get("duration", 15)))
            e_dur.grid(row=1, column=1, sticky="w", padx=5, pady=2)
            entries["duration"] = e_dur

            ctk.CTkLabel(body, text="Thả tim mỗi (giây min-max):").grid(row=1, column=2, sticky="w", padx=20, pady=2)
            e_hmin = ctk.CTkEntry(body, width=50)
            e_hmin.insert(0, str(step.get("heart_interval_min", 10)))
            e_hmin.grid(row=1, column=3, sticky="w", padx=5, pady=2)
            entries["heart_interval_min"] = e_hmin

            e_hmax = ctk.CTkEntry(body, width=50)
            e_hmax.insert(0, str(step.get("heart_interval_max", 30)))
            e_hmax.grid(row=1, column=4, sticky="w", padx=5, pady=2)
            entries["heart_interval_max"] = e_hmax

        self.step_widgets.append({
            "frame": frame,
            "type": step_type,
            "entries": entries
        })

    def _remove_step_ui(self, frame, idx):
        # We just hide it and remove it from logic list when saving
        frame.destroy()
        # Mark as destroyed
        if idx < len(self.step_widgets):
            self.step_widgets[idx]["destroyed"] = True

    def _save_current_flow(self):
        if self.current_flow_index < 0 or self.current_flow_index >= len(self.flows):
            return
            
        flow = self.flows[self.current_flow_index]
        flow["name"] = self.entry_flow_name.get()
        
        steps = []
        for w in self.step_widgets:
            if w.get("destroyed"): continue
            
            step = {"type": w["type"]}
            entries = w["entries"]
            try:
                if w["type"] == "scroll_foryou":
                    step["duration"] = float(entries["duration"].get())
                    step["like_ratio"] = float(entries["like_ratio"].get())
                elif w["type"] == "search_and_interact":
                    step["keyword"] = entries["keyword"].get()
                    step["watch_count"] = int(entries["watch_count"].get())
                    step["like_ratio"] = float(entries["like_ratio"].get())
                    step["follow_ratio"] = float(entries["follow_ratio"].get())
                elif w["type"] == "rest":
                    step["duration"] = float(entries["duration"].get())
                elif w["type"] == "watch_livestream":
                    step["live_url"] = entries["live_url"].get()
                    step["duration"] = float(entries["duration"].get())
                    step["heart_interval_min"] = int(entries["heart_interval_min"].get())
                    step["heart_interval_max"] = int(entries["heart_interval_max"].get())
            except ValueError:
                messagebox.showerror("Lỗi dữ liệu", "Vui lòng nhập đúng định dạng số cho các trường thời gian, tỷ lệ!")
                return
                
            steps.append(step)
            
        flow["steps"] = steps
        self._save_flows()
        messagebox.showinfo("Thành công", f"Đã lưu kịch bản: {flow['name']}")
        self.load_flow_list()
