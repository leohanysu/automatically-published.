"""恢复 SunBrowser 窗口到屏幕内正常大小（修复视口被压缩到 ~100px 导致的点击失败）

用法: python restore_sunbrowser_window.py [窗口标题关键字]
默认关键字: SunBrowser

背景: 窗口被最小化/移到屏幕外时，Chromium 把视口压缩到 ~100px 高，
Meta 等页面布局错乱，所有点击报 "subtree intercepts pointer events"。
cua-driver bring_to_front 只恢复可见性，不保证恢复视口大小；本脚本用
Win32 API 强制恢复窗口尺寸。

验证: 恢复后刷新页面，检查 window.innerHeight > 500 再继续操作。
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

KEYWORD = sys.argv[1] if len(sys.argv) > 1 else "SunBrowser"


def find_window(keyword):
    results = []

    def cb(h, _):
        length = user32.GetWindowTextLengthW(h)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h, buf, length + 1)
            title = buf.value
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if keyword.lower() in title.lower():
                results.append((h, title, pid.value))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return results


def main():
    found = find_window(KEYWORD)
    if not found:
        print(f"❌ 找不到标题含 '{KEYWORD}' 的窗口")
        sys.exit(1)

    # 优先选主窗口（面积最大/可见）
    hwnd, title, pid = found[0]
    print(f"✅ 找到: hwnd=0x{hwnd:x} title='{title}' pid={pid}")

    # SW_RESTORE = 9
    user32.ShowWindow(hwnd, 9)
    time.sleep(0.5)

    # SetWindowPos: HWND_TOP=0, SWP_SHOWWINDOW=0x40；1280x1400 是已验证可用的尺寸
    user32.SetWindowPos(hwnd, 0, 100, 50, 1280, 1400, 0x0040)
    time.sleep(1)

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    print(f"✅ 窗口已恢复: {w}x{h} @ ({rect.left},{rect.top}) visible={user32.IsWindowVisible(hwnd)}")
    print("⚠️ 之后请刷新目标页面并验证 window.innerHeight > 500")


if __name__ == "__main__":
    main()
