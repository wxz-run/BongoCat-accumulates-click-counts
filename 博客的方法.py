import time
import threading
from pynput import keyboard
from pynput.keyboard import Controller

INTERVAL = 0.03
KEY_LIST = list("0123456789abcdefghijklmnopqrstuvwxyz")

running = False
exit_program = False
kb = Controller()
threads = []


# 每个按键线程
def key_worker(key):
    global running
    while running:
        if not running:
            break
        kb.press(key)
        # 检查退出标志
        for _ in range(int(INTERVAL * 1000 // 1)):
            if not running:
                kb.release(key)  # 确保释放
                return
            time.sleep(0.001)
        kb.release(key)
        for _ in range(int(INTERVAL * 1000 // 1)):
            if not running:
                return
            time.sleep(0.001)


# 启动所有线程
def start_workers():
    global threads
    threads = []
    for key in KEY_LIST:
        t = threading.Thread(target=key_worker, args=(key,), daemon=True)
        t.start()
        threads.append(t)


# 键盘监听
def on_press(key):
    global running, exit_program
    if key == keyboard.Key.f8:
        if not running:
            running = True
            start_workers()
            print("开始")
        else:
            running = False
            print("停止")
    elif key == keyboard.Key.esc:
        time.sleep(0.1)

        running = False
        exit_program = True
        # 确保退出前释放所有按键
        for k in KEY_LIST:
            try:
                kb.release(k)
            except:
                pass
        print("退出")
        return False


print("F8 开始 / 停止")
print("ESC 退出")

with keyboard.Listener(on_press=on_press) as listener:
    while not exit_program:
        time.sleep(0.1)

