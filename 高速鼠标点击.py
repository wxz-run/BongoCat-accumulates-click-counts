import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput.mouse import Controller, Button
from pynput import keyboard


# 预设：(名称, CPS, 按住时长(毫秒), 说明)
PRESETS = [
    ("自定义",   10.0,  10.0, "恢复为默认参数（10 CPS / 10 ms）"),
    ("网页连点", 15.0,   5.0, "高频、极短按住，适合翻页 / 点赞"),
    ("游戏点射",  5.0,  30.0, "中频、稍长按住，更接近人手点击"),
    ("长按蓄力",  2.0, 200.0, "低频长按，用于蓄力 / 持续瞄准"),
    ("极限连点", 30.0,   2.0, "高 CPS、极短按住，用于极限测试"),
]


class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("自动点击器")
        self.root.geometry("280x285")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)   # 默认置顶

        self.mouse = Controller()
        self.running = False
        self.cps = 10.0
        self.hold = 0.01
        self.interval = 0.1
        self.click_thread = None

        self.current_preset = "自定义"
        self.preset_window = None
        self.preset_vars = []

        self.cps_var = tk.StringVar(value="10")
        self.hold_var = tk.StringVar(value="10")
        self._suppress_trace = False

        # —— 启动键 ——
        self.start_key = keyboard.Key.f8
        self.start_key_name = "F8"
        self.capturing = False

        # —— 始终置顶 ——
        self.topmost_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._setup_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ==================== 主界面 ====================
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        # row0: 预设
        preset_row = ttk.Frame(main)
        preset_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(preset_row, text="预设:").pack(side="left")
        self.preset_label = ttk.Label(
            preset_row, text=self.current_preset, foreground="blue"
        )
        self.preset_label.pack(side="left", padx=(2, 0))
        ttk.Button(
            preset_row, text="选择…", width=6,
            command=self.open_preset_window,
        ).pack(side="right")

        # row1: CPS
        ttk.Label(main, text="CPS:").grid(row=1, column=0, sticky="w")
        ttk.Entry(main, textvariable=self.cps_var, width=8).grid(
            row=1, column=1, sticky="e"
        )

        # row2: 按住时长
        ttk.Label(main, text="按住(ms):").grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Entry(main, textvariable=self.hold_var, width=8).grid(
            row=2, column=1, sticky="e", pady=(4, 0)
        )

        # row3: 启动键
        key_row = ttk.Frame(main)
        key_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Label(key_row, text="启动键:").pack(side="left")
        self.key_label = ttk.Label(key_row, text=self.start_key_name, foreground="blue")
        self.key_label.pack(side="left", padx=(2, 0))
        ttk.Button(
            key_row, text="更改", width=6, command=self.start_capture
        ).pack(side="right")

        # row4: 开始/停止
        self.btn = ttk.Button(main, text="开始 (F8)", command=self.toggle)
        self.btn.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # row5: 状态
        self.status = ttk.Label(main, text="状态: 已停止", foreground="red")
        self.status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # row6: 始终置顶（新增）
        ttk.Checkbutton(
            main,
            text="始终置顶",
            variable=self.topmost_var,
            command=self._on_topmost_toggle,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # row7: 热键提示
        self.hint_label = ttk.Label(
            main, text="F8 开始/停止    ESC 退出", foreground="gray"
        )
        self.hint_label.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # 手动编辑参数 -> 预设标签变成「手动调整」
        self.cps_var.trace_add("write", self._on_param_edited)
        self.hold_var.trace_add("write", self._on_param_edited)

    # ==================== 始终置顶 ====================
    def _on_topmost_toggle(self):
        on = self.topmost_var.get()
        self.root.attributes("-topmost", on)
        # 若弹窗开着，同步切换
        if self.preset_window is not None and self.preset_window.winfo_exists():
            try:
                self.preset_window.attributes("-topmost", on)
            except Exception:
                pass

    def _on_param_edited(self, *args):
        if self._suppress_trace:
            return
        if self.current_preset != "":
            self.current_preset = ""
            self.preset_label.config(text="手动调整")

    def _apply_preset(self, name, cps, hold):
        self.current_preset = name
        self._suppress_trace = True
        self.cps_var.set(f"{cps:g}")
        self.hold_var.set(f"{hold:g}")
        self._suppress_trace = False
        self.preset_label.config(text=name)

    # ==================== 启动键捕获 ====================
    def start_capture(self):
        if self.capturing:
            self.capturing = False
            self.key_label.config(text=self.start_key_name, foreground="blue")
            return
        self.capturing = True
        self.key_label.config(text="按下按键…", foreground="orange")
        self.root.lift()
        self.root.focus_force()

    def _handle_capture(self, key):
        if key == keyboard.Key.esc:
            self.capturing = False
            self.key_label.config(text=self.start_key_name, foreground="blue")
            return
        self.start_key = key
        self.start_key_name = self._key_display_name(key)
        self.capturing = False
        self.key_label.config(text=self.start_key_name, foreground="blue")
        self._refresh_button_and_hint()

    def _key_display_name(self, key):
        if isinstance(key, keyboard.Key):
            name = key.name
            for suffix in ("_l", "_r"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            return name.upper()
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.upper()
            if key.vk is not None:
                return f"VK{key.vk}"
        return str(key)

    def _keys_equal(self, k1, k2):
        if k1 is k2:
            return True
        if isinstance(k1, keyboard.Key) and isinstance(k2, keyboard.Key):
            return k1 == k2
        if isinstance(k1, keyboard.KeyCode) and isinstance(k2, keyboard.KeyCode):
            c1 = (k1.char or "").lower()
            c2 = (k2.char or "").lower()
            if c1 and c2:
                return c1 == c2
            return k1.vk is not None and k1.vk == k2.vk
        return False

    def _refresh_button_and_hint(self):
        action = "停止" if self.running else "开始"
        self.btn.config(text=f"{action} ({self.start_key_name})")
        self.hint_label.config(
            text=f"{self.start_key_name} 开始/停止    ESC 退出"
        )

    # ==================== 预设弹窗 ====================
    def open_preset_window(self):
        if self.preset_window is not None and self.preset_window.winfo_exists():
            self.preset_window.lift()
            self.preset_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("选择预设")
        win.transient(self.root)
        win.resizable(False, False)
        # 跟随主窗口的置顶设置
        win.attributes("-topmost", self.topmost_var.get())
        win.grab_set()

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame, text="请选择一个预设（勾选即应用，单选）：",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 6))

        self.preset_vars = []
        for name, cps, hold, desc in PRESETS:
            var = tk.BooleanVar(value=(name == self.current_preset))
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=1)
            ttk.Checkbutton(
                row,
                text=f"{name}  ({cps:g} CPS / {hold:g} ms)",
                variable=var,
                command=lambda n=name, c=cps, h=hold, v=var:
                    self._on_preset_check(n, c, h, v),
            ).pack(anchor="w")
            ttk.Label(row, text=f"    {desc}", foreground="gray").pack(
                anchor="w", padx=(22, 0)
            )
            self.preset_vars.append((name, var, cps, hold))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(frame, text="关闭", command=win.destroy).pack(anchor="e")

        self.preset_window = win

    def _on_preset_check(self, name, cps, hold, var):
        if var.get():
            for n, v, _, _ in self.preset_vars:
                if n != name:
                    v.set(False)
            self._apply_preset(name, cps, hold)
        else:
            var.set(True)

    # ==================== 全局热键 ====================
    def _setup_hotkeys(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.daemon = True
        self.listener.start()

    def on_press(self, key):
        if self.capturing:
            self.root.after(0, lambda k=key: self._handle_capture(k))
            return
        if self._keys_equal(key, self.start_key):
            self.root.after(0, self.toggle)
        elif key == keyboard.Key.esc:
            self.root.after(0, self._on_esc)

    def _on_esc(self):
        if self.preset_window is not None and self.preset_window.winfo_exists():
            self.preset_window.destroy()
            self.preset_window = None
        elif self.capturing:
            self.capturing = False
            self.key_label.config(text=self.start_key_name, foreground="blue")
        else:
            self.quit()

    # ==================== 开始 / 停止 ====================
    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        try:
            cps = float(self.cps_var.get().strip())
            if cps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正数 CPS")
            return

        try:
            hold_ms = float(self.hold_var.get().strip())
            if hold_ms < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入有效的非负数按住时长")
            return

        interval = 1.0 / cps
        hold = hold_ms / 1000.0

        max_hold = interval * 0.9
        if hold > max_hold:
            hold = max_hold
            messagebox.showwarning(
                "按住时长已自动调整",
                f"按住时长过长，已限制为 {hold*1000:.2f} ms\n"
                f"（周期 {interval*1000:.2f} ms 的 90%，以维持 {cps:g} CPS）",
            )

        self.cps = cps
        self.interval = interval
        self.hold = hold

        self.running = True
        self.status.config(
            text=f"运行中 [{self.current_preset or '手动调整'}]  "
                 f"{cps:g} CPS / {hold*1000:.1f} ms",
            foreground="green",
        )
        self.btn.config(text=f"停止 ({self.start_key_name})")

        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop(self):
        self.running = False
        self.status.config(text="状态: 已停止", foreground="red")
        self.btn.config(text=f"开始 ({self.start_key_name})")

    # ==================== 点击循环 ====================
    def click_loop(self):
        while self.running:
            t0 = time.perf_counter()
            self.mouse.press(Button.left)

            while self.running:
                if time.perf_counter() - t0 >= self.hold:
                    break
                time.sleep(min(0.005, self.hold))

            self.mouse.release(Button.left)

            elapsed = time.perf_counter() - t0
            remaining = self.interval - elapsed
            if remaining > 0:
                end = time.perf_counter() + remaining
                while self.running and time.perf_counter() < end:
                    time.sleep(min(0.005, remaining))

    # ==================== 退出 ====================
    def quit(self):
        self.running = False
        try:
            self.mouse.release(Button.left)
        except Exception:
            pass
        try:
            self.listener.stop()
        except Exception:
            pass
        if self.preset_window is not None and self.preset_window.winfo_exists():
            try:
                self.preset_window.destroy()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoClicker(root)
    root.mainloop()