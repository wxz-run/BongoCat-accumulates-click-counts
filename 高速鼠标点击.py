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
        self.root.geometry("320x210")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)  # 窗口置顶方便操作

        self.mouse = Controller()
        self.running = False
        self.cps = 10.0
        self.click_thread = None

        # ---------- 界面 ----------
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="每秒点击次数 (CPS):").pack(anchor="w")
        self.cps_var = tk.StringVar(value="10")
        entry = ttk.Entry(frame, textvariable=self.cps_var)
        entry.pack(fill="x", pady=(4, 10))

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

        # 关闭窗口也退出
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------- 全局热键回调（在监听线程里执行） ----------
    def on_press(self, key):
        if key == keyboard.Key.f8:
            self.root.after(0, self.toggle)     # 切回主线程操作界面
        elif key == keyboard.Key.esc:
            self.root.after(0, self.quit)

    # ---------- 开始 / 停止 ----------
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
            messagebox.showerror("错误", "请输入有效的正数（每秒点击次数）")
            return

        self.cps = cps
        self.running = True
        self.status.config(text=f"状态: 运行中 ({cps:g} CPS)", foreground="green")
        self.btn.config(text="停止 (F8)")

        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop(self):
        self.running = False
        self.status.config(text="状态: 已停止", foreground="red")
        self.btn.config(text="开始 (F8)")

    # ---------- 点击循环（高精度节拍） ----------
    def click_loop(self):
        interval = 1.0 / self.cps
        next_t = time.perf_counter()

        while self.running:
            self.mouse.click(Button.left)

            # 用绝对时间基准累加，避免累积误差
            next_t += interval
            sleep_time = next_t - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # 如果上一次点击耗时已经超过间隔，就重置基准，防止“追赶式连点”
                next_t = time.perf_counter()

    # ---------- 退出 ----------
    def quit(self):
        self.running = False
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