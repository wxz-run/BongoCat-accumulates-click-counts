import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput.mouse import Controller, Button
from pynput import keyboard


class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("自动点击器")
        self.root.geometry("340x270")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.mouse = Controller()
        self.running = False
        self.cps = 10.0
        self.hold = 0.01        # 按住时长（秒）
        self.interval = 0.1     # 点击间隔（秒）
        self.click_thread = None

        # ---------- 界面 ----------
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="每秒点击次数 (CPS):").pack(anchor="w")
        self.cps_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=self.cps_var).pack(fill="x", pady=(4, 10))

        ttk.Label(frame, text="按住时长 (毫秒):").pack(anchor="w")
        self.hold_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=self.hold_var).pack(fill="x", pady=(4, 10))

        self.btn = ttk.Button(frame, text="开始 (F8)", command=self.toggle)
        self.btn.pack(fill="x")

        self.status = ttk.Label(frame, text="状态: 已停止", foreground="red")
        self.status.pack(anchor="w", pady=(10, 0))

        ttk.Label(
            frame,
            text="F8: 开始 / 停止     ESC: 退出程序",
            foreground="gray",
        ).pack(anchor="w", pady=(8, 0))

        # ---------- 全局键盘监听 ----------
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.daemon = True
        self.listener.start()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------- 全局热键 ----------
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

    def start(self):
        # 解析 CPS
        try:
            cps = float(self.cps_var.get().strip())
            if cps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正数（每秒点击次数）")
            return

        # 解析按住时长（毫秒）
        try:
            hold_ms = float(self.hold_var.get().strip())
            if hold_ms < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入有效的非负数（按住时长，毫秒）")
            return

        interval = 1.0 / cps
        hold = hold_ms / 1000.0

        # 按住时长不能占满整个周期，否则无法维持目标 CPS
        # 至少留出 10% 周期用于「松开状态」
        max_hold = interval * 0.9
        if hold > max_hold:
            hold = max_hold
            messagebox.showwarning(
                "按住时长已自动调整",
                f"按住时长过长，已限制为 {hold*1000:.2f} ms\n"
                f"（约为周期 {interval*1000:.2f} ms 的 90%，以维持 {cps:g} CPS）"
            )

        self.cps = cps
        self.interval = interval
        self.hold = hold

        self.running = True
        self.status.config(
            text=f"状态: 运行中 ({cps:g} CPS, 按住 {hold*1000:.1f} ms)",
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

            # 1) 鼠标按下
            self.mouse.press(Button.left)

            # 2) 按住（用短睡眠轮询，便于及时响应停止）
            while self.running:
                if time.perf_counter() - t0 >= self.hold:
                    break
                time.sleep(min(0.005, self.hold))

            # 3) 鼠标松开
            self.mouse.release(Button.left)

            # 4) 补足剩余时间，保证周期 = 1/CPS
            elapsed = time.perf_counter() - t0
            remaining = self.interval - elapsed
            if remaining > 0:
                # 分片睡眠，避免按下停止后还要等很久
                end = time.perf_counter() + remaining
                while self.running and time.perf_counter() < end:
                    time.sleep(min(0.005, remaining))
            # 若 elapsed > interval（说明这一轮超时了），直接进入下一轮，不累计误差

    # ---------- 退出 ----------
    def quit(self):
        self.running = False
        # 让可能正在按下的鼠标复位，避免「卡住按下」状态
        try:
            self.mouse.release(Button.left)
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