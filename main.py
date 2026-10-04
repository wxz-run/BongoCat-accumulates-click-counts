import sys

try:
    import pyautogui
except ImportError:
    print("缺少 pyautogui，请先安装：pip install pyautogui")
    sys.exit(1)

# 保持原版速度：keyDown 后等 0.05，keyUp 后等 0.05，总周期约 0.1 秒
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True

KEY = "f13"
URL = "https://space.bilibili.com/3493081447926624"
TEXT = "访问作者主页"


def key_mapping(n):
    print(f">正在执行，预计刷（{n}）次点击，你可以去点干别的事情，你可以直接点击关闭窗口按钮退出")
    print(f"{URL}\\{TEXT}")
    done = 0

    try:
        for i in range(n):
            pyautogui.keyDown(KEY)
            try:
                # 什么都不做，pyautogui.PAUSE 已经在 keyDown 后自动暂停 0.05 秒
                pass
            finally:
                # 保证任何情况下都释放按键，避免卡键
                pyautogui.keyUp(KEY)

            done = i + 1

            # 如果追求极限速度，可以注释掉进度打印；打印会轻微拖慢速度
            # if done % 100 == 0:
            #     print(f"> 已完成 {done}/{n}")

    except pyautogui.FailSafeException:
        print("\n> 触发 pyautogui 安全保护（鼠标移到左上角），已停止。")
    except KeyboardInterrupt:
        print("\n> 用户中断，已停止。")
    except Exception as e:
        print(f"\n> 发生异常，已停止：{type(e).__name__}: {e}")
    finally:
        print(f"> 实际完成：{done}/{n}")


def main():
    print("BongoCat刷点击器 V0.1")
    print("将占用F13键，大部分电脑没有这个键，但无法保证不干扰其他软件。")
    print("请确保BongoCat已开启。")
    print("___________")

    if KEY not in pyautogui.KEYBOARD_KEYS:
        print(f"当前pyautogui不支持按键 {KEY!r}，无法继续。")
        return

    while True:
        try:
            s = input(">要刷多少次点击(输入数字<1000000，回车取消): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return

        if s == "":
            print("已取消")
            return

        try:
            count = int(s)
        except ValueError:
            print("> 请输入数字！")
            continue

        if count <= 0:
            print("> 次数必须大于 0")
            continue

        if count > 1_000_000:
            print("> 次数太大，可能会造成卡顿请输入 <= 1000000")
            continue

        break

    try:
        ans = input(f"将发送 {count} 次 {KEY}，确认？(y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return

    if ans not in ("y", "yes", "是"):
        print("已取消")
        return

    key_mapping(count)


if __name__ == "__main__":
    main()