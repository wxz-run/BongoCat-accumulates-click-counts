import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput.mouse import Controller, Button
from pynput import keyboard


# 预设：(名称, CPS, 按住时长(毫秒), 说明)
PRESETS = [
    ("自定义",   10.0,  10.0, "手动填写任意 CPS 与按住时长"),
    ("网页连点", 15.0,   5.0, "高频、极短按住，适合翻页 / 点赞"),
    ("游戏点射",  5.0,  30.0, "中频、稍长按住，更接近人手点击"),
    ("长按蓄力",  2.0, 200.0, "低频长按，用于蓄力 / 持续瞄准"),
    ("极限连点", 30.0,   2.0, "高 CPS、极短按住，用于极限测试"),
]


class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("自动点击器")
        self.root.geometry("420x400")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.mouse = Controller()
        self.running = False
        self.cps = 10.0
        self.hold = 0.01        # 秒
        self.interval = 0.1     # 秒
        self.click_thread = None
        self.active_preset = ""

        self._build_ui()
        self._setup_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------- 界面 ----------
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        # 预设选项卡
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="x")

        self.tab_vars = {}   # tab_id(str) -> (name, cps_var, hold_var)
        for name, cps, hold, desc in PRESETS:
            self._add_tab(name, cps, hold, desc)

        # 开始 / 停止
        self.btn = ttk.Button(main, text="开始 (F8)", command=self.toggle)
        self.btn.pack(fill="x", pady=(12, 0))

        # 状态
        self.status = ttk.Label(main, text="状态: 已停止", foreground="red")
        self.status.pack(anchor="w", pady=(10, 0))

        ttk.Label(
            main,
            text="F8: 开始 / 停止     ESC: 退出程序",
            foreground="gray",
        ).pack(anchor="w", pady=(8, 0))

    def _add_tab(self, name, cps, hold, desc):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=name)

        ttk.Label(tab, text=desc, foreground="gray").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        cps_var = tk.StringVar(value=f"{cps:g}")
        hold_var = tk.StringVar(value=f"{hold:g}")

        ttk.Label(tab, text="每秒点击次数 (CPS):").grid(row=1, column=0, sticky="w")
        ttk.Entry(tab, textvariable=cps_var, width=10).grid(
            row=1, column=1, sticky="e"
        )

        ttk.Label(tab, text="按住时长 (毫秒):").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(tab, textvariable=hold_var, width=10).grid(
            row=2, column=1, sticky="e", pady=(8, 0)
        )

        tab.columnconfigure(0, weight=1)
        self.tab_vars[str(tab)] = (name, cps_var, hold_var)

    # ---------- 全局热键 ----------
    def _setup_hotkeys(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.daemon = True
        self.listener.start()

    def on_press(self, key):
        if key == keyboard.Key.f8:
            self.root.after(0, self.toggle)
        elif key == keyboard.Key.esc:
            self.root.after(0, self.quit)

    # ---------- 开始 / 停止 ----------
    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def _active_tab(self):
        """返回当前选中 tab 的 (name, cps_var, hold_var)"""
        tab_id = self.notebook.select()   # 返回 tab 的 widget 路径字符串
        return self.tab_vars[tab_id]

    def start(self):
        name, cps_var, hold_var = self._active_tab()

        try:
            cps = float(cps_var.get().strip())
            if cps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", f"[{name}] 请输入有效的正数 CPS")
            return

        try:
            hold_ms = float(hold_var.get().strip())
            if hold_ms < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", f"[{name}] 请输入有效的非负数按住时长")
            return

        interval = 1.0 / cps
        hold = hold_ms / 1000.0

        # 按住时长不能占满整个周期
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
        self.active_preset = name

        self.running = True
        self.status.config(
            text=f"运行中 [{name}]  {cps:g} CPS / 按住 {hold*1000:.1f} ms",
            foreground="green",
        )
        self.btn.config(text="停止 (F8)")

        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop(self):
        self.running = False
        self.status.config(text="状态: 已停止", foreground="red")
        self.btn.config(text="开始 (F8)")

    # ---------- 核心：按下 → 保持 → 松开 ----------
    def click_loop(self):
        while self.running:
            t0 = time.perf_counter()

            self.mouse.press(Button.left)                     # 按下

            while self.running:                               # 保持
                if time.perf_counter() - t0 >= self.hold:
                    break
                time.sleep(min(0.005, self.hold))

            self.mouse.release(Button.left)                   # 松开

            elapsed = time.perf_counter() - t0
            remaining = self.interval - elapsed
            if remaining > 0:
                end = time.perf_counter() + remaining
                while self.running and time.perf_counter() < end:
                    time.sleep(min(0.005, remaining))

    # ---------- 退出 ----------
    def quit(self):
        self.running = False
        try:
            self.mouse.release(Button.left)      # 防止退出后鼠标"卡在按下"
        except Exception:
            pass
        try:
            self.listener.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoClicker(root)
    root.mainloop()