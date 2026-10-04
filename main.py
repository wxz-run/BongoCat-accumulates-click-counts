import sys
import time
import threading

try:
    from pynput.keyboard import Controller, Key, Listener
except ImportError:
    print("缺少 pynput，请先安装：pip install pynput")
    sys.exit(1)


# ==================== 可调参数 ====================
PRESS_TIME = 0.05          # 按下后保持的时间（秒）
INTERVAL = 0.05            # 松开后等待的时间（秒）
# 单次周期 ≈ PRESS_TIME + INTERVAL ≈ 0.1 秒（和原版速度一致）
# 想更快就调小这两个值，但别小到 BongoCat 反应不过来

# 要模拟的按键：F13 ~ F14，每个键一个独立线程
# 想加更多就继续写，例如 [Key.f13, Key.f14, Key.f15, Key.f16]
KEY_LIST = [Key.f13, Key.f14, Key.f15, Key.f16,Key.f17,Key.f18,Key.f19,Key.f20,Key.f21,Key.f22,Key.f23,Key.f24]
# =================================================


running = threading.Event()   # 置位 = 正在刷；清除 = 停止
exit_program = False
kb = Controller()
threads = []


def _sleep(seconds: float) -> bool:
    """
    可被中断的 sleep。
    返回 True  = 睡满了
    返回 False = 中途 running 被清掉，需要退出
    """
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if not running.is_set():
            return False
        time.sleep(0.001)
    return running.is_set()


def key_worker(key):
    """单个按键的循环线程：按下 -> 保持 -> 松开 -> 等待 -> 循环"""
    while running.is_set():
        try:
            kb.press(key)
            if not _sleep(PRESS_TIME):
                kb.release(key)
                break
            kb.release(key)
            if not _sleep(INTERVAL):
                break
        except Exception as e:
            print(f"> 线程 {key} 异常，已退出：{type(e).__name__}: {e}")
            try:
                kb.release(key)
            except Exception:
                pass
            break


def start_workers():
    """为每个按键启动一个线程"""
    global threads
    running.set()
    threads = []
    for key in KEY_LIST:
        t = threading.Thread(
            target=key_worker,
            args=(key,),
            daemon=True,
            name=f"kb-{key}",
        )
        t.start()
        threads.append(t)


def stop_workers():
    """停止所有线程，并兜底释放按键，避免卡键"""
    running.clear()
    for t in threads:
        t.join(timeout=0.3)
    threads.clear()

    for key in KEY_LIST:
        try:
            kb.release(key)
        except Exception:
            pass


def on_press(key):
    global exit_program

    if key == Key.f8:
        if not running.is_set():
            start_workers()
            print("▶ 开始")
        else:
            stop_workers()
            print("■ 停止")

    elif key == Key.esc:
        if running.is_set():
            stop_workers()
        exit_program = True
        print("退出")
        return False   # 停止监听


def main():
    print("BongoCat 刷点击器 V0.2（多线程版）")
    print("将同时模拟：" + "、".join(str(k) for k in KEY_LIST))
    print("大部分电脑没有这些键，但无法保证不干扰其他软件。")
    print("请确保 BongoCat 已开启。")
    print("-" * 40)
    print("F8  开始 / 停止")
    print("ESC 退出")
    print("-" * 40)

    listener = Listener(on_press=on_press)
    listener.start()
    try:
        while not exit_program:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n> 用户中断")
    finally:
        if running.is_set():
            stop_workers()
        listener.stop()


if __name__ == "__main__":
    main()