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
        self.root.geometry("380x345")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.mouse = Controller()
        self.running = False
        self.cps = 10.0
        self.hold = 0.01        # 秒
        self.interval = 0.1     # 秒
        self.click_thread = None

        self.current_preset = "自定义"
        self.preset_window = None
        self.preset_vars = []       # [(name, BooleanVar, cps, hold), ...]

        self.cps_var = tk.StringVar(value="10")
        self.hold_var = tk.StringVar(value="10")
        self._suppress_trace = False

        self._build_ui()
        self._setup_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ==================== 主界面 ====================
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        # —— 预设行 ——
        preset_row = ttk.Frame(main)
        preset_row.pack(fill="x", pady=(0, 12))

        ttk.Label(preset_row, text="当前预设：").pack(side="left")
        self.preset_label = ttk.Label(preset_row, text=self.current_preset, foreground="blue")
        self.preset_label.pack(side="left")
        ttk.Button(preset_row, text="选择预设…", command=self.open_preset_window).pack(side="right")

        # —— CPS ——
        ttk.Label(main, text="每秒点击次数 (CPS):").pack(anchor="w")
        ttk.Entry(main, textvariable=self.cps_var).pack(fill="x", pady=(4, 10))

        # —— 按住时长 ——
        ttk.Label(main, text="按住时长 (毫秒):").pack(anchor="w")
        ttk.Entry(main, textvariable=self.hold_var).pack(fill="x", pady=(4, 10))

        # —— 开始 / 停止 ——
        self.btn = ttk.Button(main, text="开始 (F8)", command=self.toggle)
        self.btn.pack(fill="x")

        # —— 状态 ——
        self.status = ttk.Label(main, text="状态: 已停止", foreground="red")
        self.status.pack(anchor="w", pady=(10, 0))

        # —— 热键提示 ——
        ttk.Label(
            main,
            text="F8: 开始 / 停止     ESC: 退出程序",
            foreground="gray",
        ).pack(anchor="w", pady=(8, 0))

        # 手动编辑参数 -> 预设标签变成「手动调整」
        self.cps_var.trace_add("write", self._on_param_edited)
        self.hold_var.trace_add("write", self._on_param_edited)

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

    # ==================== 预设弹窗 ====================
    def open_preset_window(self):
        # 已打开就聚焦，避免重复创建
        if self.preset_window is not None and self.preset_window.winfo_exists():
            self.preset_window.lift()
            self.preset_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("选择预设")
        win.transient(self.root)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.grab_set()          # 模态：主窗口暂时不可操作

        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="请选择一个预设（勾选即应用，单选）：",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 8))

        # 用 Checkbutton 实现单选效果
        self.preset_vars = []
        for name, cps, hold, desc in PRESETS:
            var = tk.BooleanVar(value=(name == self.current_preset))
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)

            cb = ttk.Checkbutton(
                row,
                text=f"{name}  （{cps:g} CPS / 按住 {hold:g} ms）",
                variable=var,
                command=lambda n=name, c=cps, h=hold, v=var:
                    self._on_preset_check(n, c, h, v),
            )
            cb.pack(anchor="w")
            ttk.Label(row, text=f"    {desc}", foreground="gray").pack(
                anchor="w", padx=(22, 0)
            )
            self.preset_vars.append((name, var, cps, hold))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(frame, text="关闭", command=win.destroy).pack(anchor="e")

        self.preset_window = win

    def _on_preset_check(self, name, cps, hold, var):
        """复选框的点选回调：实现单选逻辑"""
        if var.get():
            # 勾选新的 -> 取消其他所有
            for n, v, _, _ in self.preset_vars:
                if n != name:
                    v.set(False)
            self._apply_preset(name, cps, hold)
        else:
            # 想取消唯一勾选项 -> 不允许，重新勾上
            var.set(True)

    # ==================== 全局热键 ====================
    def _setup_hotkeys(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.daemon = True
        self.listener.start()

    def on_press(self, key):
        if key == keyboard.Key.f8:
            self.root.after(0, self.toggle)
        elif key == keyboard.Key.esc:
            self.root.after(0, self._on_esc)

    def _on_esc(self):
        # 预设弹窗打开时，ESC 只关闭弹窗；否则退出程序
        if self.preset_window is not None and self.preset_window.winfo_exists():
            self.preset_window.destroy()
            self.preset_window = None
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
                 f"{cps:g} CPS / 按住 {hold*1000:.1f} ms",
            foreground="green",
        )
        self.btn.config(text="停止 (F8)")

        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop(self):
        self.running = False
        self.status.config(text="状态: 已停止", foreground="red")
        self.btn.config(text="开始 (F8)")

    # ==================== 点击循环 ====================
    def click_loop(self):
        while self.running:
            t0 = time.perf_counter()

            self.mouse.press(Button.left)          # 按下

            while self.running:                    # 保持按住
                if time.perf_counter() - t0 >= self.hold:
                    break
                time.sleep(min(0.005, self.hold))

            self.mouse.release(Button.left)        # 松开

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