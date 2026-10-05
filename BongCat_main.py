# -*- coding: utf-8 -*-
"""
BongoCat刷点击器 V0.4(Tkinter 窗口版)
在 V0.3 基础上加入防溢出：
  - 每连续运行 60 秒，自动暂停 3 秒，然后继续
  - 其他功能完全不变
依赖:pip install pynput
"""

import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from pynput.keyboard import Controller, Key, Listener
except ImportError:
    print("缺少 pynput，请先安装：pip install pynput")
    sys.exit(1)

# ==================== 可调参数（默认值） ====================
DEFAULT_PRESS_TIME = 0.025  # 按下后保持的时间（秒）
DEFAULT_INTERVAL = 0.025    # 松开后等待的时间（秒）

RUN_DURATION = 60.0         # 【新增】连续运行多少秒后暂停一次
PAUSE_DURATION = 3.0        # 【新增】每次暂停多少秒（防溢出）
# =========================================================

# 可模拟的按键：名称 -> pynput 键
ALL_KEYS = [
    ("F13", Key.f13), ("F14", Key.f14), ("F15", Key.f15), ("F16", Key.f16),
    ("F17", Key.f17), ("F18", Key.f18), ("F19", Key.f19), ("F20", Key.f20),
    ("F21", Key.f21), ("F22", Key.f22), ("F23", Key.f23), ("F24", Key.f24),
]

#连发引擎（纯逻辑，不碰 UI）
class AutoClicker:
    """多线程按键连发引擎：每个按键一个独立线程。"""

    def __init__(self, notify=None):
        self.kb = Controller()
        self.running = threading.Event()   # 置位 = 正在刷；清除 = 停止
        self.paused = threading.Event()    # 【新增】置位 = 暂停中（防溢出）
        self.lock = threading.Lock()
        self.threads = []
        self.watchdog_thread = None        # 【新增】防溢出计时线程
        self.keys = []
        self.press_time = DEFAULT_PRESS_TIME
        self.interval = DEFAULT_INTERVAL
        self.notify = notify               # 【新增】通知 UI 的回调（可选）

    #内部工具
    def _notify(self, msg):
        """【新增】向 UI 线程发消息，出错就忽略。"""
        if self.notify is None:
            return
        try:
            self.notify(msg)
        except Exception:
            pass

    def _sleep(self, seconds: float) -> bool:
        """可被中断的 sleep。True = 睡满；False = 中途被停止。"""
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            if not self.running.is_set():
                return False
            time.sleep(0.001)
        return self.running.is_set()

    def _wait_unpaused(self) -> bool:
        """【新增】暂停时在此等待。True = 可以继续；False = 已被停止。"""
        while self.running.is_set() and self.paused.is_set():
            time.sleep(0.005)
        return self.running.is_set()

    def _release(self, key):
        """兜底释放，避免卡键。"""
        try:
            self.kb.release(key)
        except Exception:
            pass

    def _worker(self, key, press_time: float, interval: float):
        """单个按键的循环线程：按下 -> 保持 -> 松开 -> 等待 -> 循环。"""
        while self.running.is_set():
            # 【新增】暂停期间不产生任何按键
            if not self._wait_unpaused():
                break

            try:
                self.kb.press(key)
                if not self._sleep(press_time):
                    self._release(key)
                    break
                self.kb.release(key)
                if not self._sleep(interval):
                    break
            except Exception as e:
                print(f"> 线程 {key} 异常，已退出：{type(e).__name__}: {e}")
                self._release(key)
                break

    def _watchdog(self):
        """【新增】防溢出计时线程：运行 RUN_DURATION 秒 -> 暂停 PAUSE_DURATION 秒 -> 循环。"""
        while self.running.is_set():
            # ---- 运行阶段 ----
            deadline = time.perf_counter() + RUN_DURATION
            while time.perf_counter() < deadline:
                if not self.running.is_set():
                    return
                time.sleep(0.05)

            if not self.running.is_set():
                return

            # ---- 暂停阶段 ----
            self.paused.set()
            self._notify("paused")

            deadline = time.perf_counter() + PAUSE_DURATION
            while time.perf_counter() < deadline:
                if not self.running.is_set():
                    break
                time.sleep(0.02)

            self.paused.clear()

            if self.running.is_set():
                self._notify("resumed")
            else:
                return

    # ---------------- 对外接口 ----------------
    @property
    def is_running(self) -> bool:
        return self.running.is_set()

    @property
    def is_paused(self) -> bool:
        return self.paused.is_set()

    def start(self, keys, press_time: float, interval: float) -> bool:
        """启动所有按键线程 + 防溢出计时线程。已在运行则返回 False。"""
        with self.lock:
            if self.running.is_set():
                return False

            self.keys = list(keys)
            self.press_time = press_time
            self.interval = interval
            self.paused.clear()
            self.running.set()

            self.threads = []
            for key in self.keys:
                t = threading.Thread(
                    target=self._worker,
                    args=(key, press_time, interval),   # 参数快照，避免竞态
                    daemon=True,
                    name=f"kb-{key}",
                )
                t.start()
                self.threads.append(t)

            # 【新增】启动防溢出计时线程
            self.watchdog_thread = threading.Thread(
                target=self._watchdog, daemon=True, name="watchdog"
            )
            self.watchdog_thread.start()
        return True

    def stop(self):
        """停止所有线程，并兜底释放按键。"""
        with self.lock:
            if not self.running.is_set() and not self.threads:
                return
            self.running.clear()
            self.paused.clear()          # 【新增】解除暂停，让线程立刻退出
            threads = self.threads
            self.threads = []
            watchdog = self.watchdog_thread
            self.watchdog_thread = None
            keys = list(self.keys)

        for t in threads:
            t.join(timeout=0.3)
        if watchdog is not None:
            watchdog.join(timeout=0.3)

        for key in keys:
            self._release(key)

#窗口
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.msg_queue = queue.Queue()      # 监听线程 -> 主线程 的消息通道
        # 【新增】把 engine 的通知也丢进同一个队列，统一在主线程处理
        self.engine = AutoClicker(notify=self.msg_queue.put)
        self.key_vars = {}                  # 名称 -> (BooleanVar, key)
        self.listener = None
        self._closing = False

        self._build_ui()
        self._start_listener()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(50, self._poll_queue)

    # ---------------- 界面构建 ----------------
    def _build_ui(self):
        self.root.title("BongoCat刷点击器 V0.4") #窗口标题
        self.root.resizable(False, False)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            main, text="BongoCat刷点击器 V0.4", font=("", 12, "bold")
        ).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        # ---- 参数 ----
        pf = ttk.LabelFrame(main, text="参数", padding=10)
        pf.grid(row=1, column=0, columnspan=4, sticky="ew", pady=4)

        ttk.Label(pf, text="按住时长(秒)").grid(row=0, column=0, sticky="w")
        self.press_var = tk.StringVar(value=str(DEFAULT_PRESS_TIME))
        ttk.Entry(pf, textvariable=self.press_var, width=8, justify="center").grid(
            row=0, column=1, padx=(6, 16)
        )

        ttk.Label(pf, text="间隔(秒)").grid(row=0, column=2, sticky="w")
        self.interval_var = tk.StringVar(value=str(DEFAULT_INTERVAL))
        ttk.Entry(pf, textvariable=self.interval_var, width=8, justify="center").grid(
            row=0, column=3, padx=6
        )

        # ---- 按键选择 ----
        kf = ttk.LabelFrame(main, text="模拟按键(可多选,大部分电脑没有这些键,勾选越少性能越好)", padding=10)
        kf.grid(row=2, column=0, columnspan=4, sticky="ew", pady=4)

        for i, (name, key) in enumerate(ALL_KEYS):
            var = tk.BooleanVar(value=True)
            self.key_vars[name] = (var, key)
            ttk.Checkbutton(kf, text=name, variable=var).grid(
                row=i // 4, column=i % 4, sticky="w", padx=6, pady=3
            )

        sel = ttk.Frame(main)
        sel.grid(row=3, column=0, columnspan=4, sticky="w", pady=(2, 0))
        ttk.Button(sel, text="全选", width=8, command=lambda: self._set_all(True)).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(sel, text="全不选", width=8, command=lambda: self._set_all(False)).grid(
            row=0, column=1
        )
        

        # ---- 控制按钮 ----
        cf = ttk.Frame(main)
        cf.grid(row=4, column=0, columnspan=4, pady=(14, 4))

        self.toggle_btn = ttk.Button(
            cf, text="开始(F8)", width=16, command=self.toggle
        )
        self.toggle_btn.grid(row=0, column=0, padx=6)

        ttk.Button(cf, text="退出(ESC)", width=16, command=self.quit).grid(
            row=0, column=1, padx=6
        )
        
        # ---- 状态栏 ----
        self.status_var = tk.StringVar(value="·就绪，请确保 BongoCat 已开启")
        ttk.Label(main, textvariable=self.status_var, foreground="#555").grid(
            row=5, column=0, columnspan=4, pady=(10, 0)
        )
        
        tip = ttk.Label(sel, text="(tip:结束时会卡一段时间)", foreground="#888").grid(row=0, column=2, padx=(12, 0))

        ttk.Separator(main, orient="horizontal").grid(
            row=6, column=0, columnspan=4, sticky="ew", pady=8
        )
        ttk.Label(
            main,
            text=f"   全局热键:F8开始/停止;ESC退出\n(每运行 {RUN_DURATION:.0f} 秒自动暂停 {PAUSE_DURATION:.0f} 秒防溢出)",
            foreground="#888",
        ).grid(row=7, column=0, columnspan=4)

    def _set_all(self, value: bool):
        for var, _ in self.key_vars.values():
            var.set(value)

    #全局热键监听
    def _start_listener(self):
        """pynput 监听器跑在自己的线程里，只往队列里丢消息。"""
        def on_press(key):
            if key == Key.f8:
                self.msg_queue.put("toggle")
            elif key == Key.esc:
                self.msg_queue.put("quit")
                return False        # 停止监听
            return None

        try:
            self.listener = Listener(on_press=on_press)
            self.listener.daemon = True
            self.listener.start()
        except Exception as e:
            self.status_var.set(f"全局热键不可用：{type(e).__name__}: {e}")

    def _poll_queue(self):
        """主线程定时轮询消息队列（Tk 只能在主线程里操作）。"""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg == "toggle":
                    self.toggle()
                elif msg == "quit":
                    self.quit()
                    return
                # 【新增】防溢出状态反馈
                elif msg == "paused":
                    if self.engine.is_running:
                        self.status_var.set(
                            f"⏸ 暂停中（防溢出，{PAUSE_DURATION:.0f} 秒后自动继续）…"
                        )
                elif msg == "resumed":
                    if self.engine.is_running:
                        self.status_var.set("▶ 运行中")
        except queue.Empty:
            pass

        if not self._closing:
            self.root.after(50, self._poll_queue)

    # ---------------- 开始 / 停止 ----------------
    def toggle(self):
        if self.engine.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        # 校验参数
        try:
            press_time = float(self.press_var.get())
            interval = float(self.interval_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "“按住时长”和“间隔”必须是数字。")
            return

        if press_time < 0.001 or interval < 0.001:
            messagebox.showerror("参数错误", "参数太小了，最小 0.001 秒。")
            return

        keys = [k for var, k in self.key_vars.values() if var.get()]
        if not keys:
            messagebox.showwarning("未选择按键", "请至少勾选一个按键。")
            return

        if self.engine.start(keys, press_time, interval):
            self.toggle_btn.config(text="停止(F8)")
            names = [n for n, (v, _) in self.key_vars.items() if v.get()]
            self.status_var.set(f"▶ 运行中")
            self.root.title("运行中")

    def stop(self):
        self.engine.stop()
        self.toggle_btn.config(text="开始(F8)")
        self.status_var.set("■ 已停止")
        self.root.title("BongoCat刷点击器 V0.4")

    # ---------------- 退出 ----------------
    def quit(self):
        if self._closing:
            return
        self._closing = True

        try:
            if self.engine.is_running:
                self.engine.stop()
        except Exception:
            pass

        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass

        try:
            self.root.destroy()
        except Exception:
            pass


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()