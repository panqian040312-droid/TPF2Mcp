"""TPF2 铁路图 —— 后台常驻服务 + 系统托盘图标（单文件集成版）。

一个文件干完所有事：
  · 以后台方式拉起地图 HTTP 服务（无控制台窗口）
  · 在**任务栏右下角托盘**显示一个图标 —— 就是那个「^」展开后的一格
  · 托盘**左键单击 = 打开地图**，右键 = 菜单（打开日志 / 日志文件夹 / 重启服务 / 退出）
  · 每次运行的日志单独存一份，**永不删除**，排障时按时间找

用法：双击 `start_rail_map.bat`（桌面「TPF2 铁路图」快捷方式指向它）。
      本文件也可以直接双击，但需要 .pyw 已关联到 pythonw。

命令行（一般不用）：
    python.exe rail-map-service.pyw --tail 40      # 打印最新日志尾部（排障用）

为什么用 ctypes 直调 Win32 而不是 pystray：
    本机没装 pystray / Pillow，也没有 tkinter；装包在这台机器上很慢、还要写 C 盘。
    `Shell_NotifyIcon` 是 Windows 自带的东西，走 ctypes 零依赖、立刻能用。

日志策略（用户 2026-09-29 要求"完整保留以便排障"）：
    目录  E:\\workbody\\TPF2Mcp\\logs\\
    文件  服务会话-YYYYMMDD-HHMMSS.log   （每次启动新开一个，**旧的从不删除**）
    内容  服务自己的 stdout/stderr（用 -u -X utf8 跑，实时落盘、UTF-8）
         + 本程序的动作记录（前缀 [tray]）
    → 想清理就自己按月/按大小删，程序绝不自动删。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path

# ─────────────────────────── 本机路径配置 ───────────────────────────
HERE = Path(__file__).resolve().parent
MOD_DIRECTORY = Path(
    r"C:\Program Files (x86)\Steam\userdata\1070536217\1066780\local\staging_area\tpf2mcp_1"
)
PYTHON = Path(r"C:\Users\RailG\.workbuddy\binaries\python\versions\3.13.12\python.exe")
SERVICE_ENTRY = MOD_DIRECTORY / "mcp_server" / "start_ui.py"
UI_DIRECTORY = HERE / "ui" / "rail-map"
LOG_DIRECTORY = HERE / "logs"
ICON_PATH = HERE / "rail-map.ico"
# 拿现成的一张游戏图标做托盘图标（PNG 直接包进 .ico，不用图像库）
ICON_SOURCE_PNG = UI_DIRECTORY / "assets" / "icons" / "vehicle_train_diesel.png"

URL = "http://127.0.0.1:8790/?view=network"
PORT = 8790

# ─────────────────────────── Win32 常量 ───────────────────────────
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_TIMER = 0x0113
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
WM_DESTROY = 0x0002
WM_NULL = 0x0000

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04

MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100

IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
IDI_APPLICATION = 32512

CREATE_NO_WINDOW = 0x08000000

MENU_OPEN = 1
MENU_LOG = 2
MENU_LOG_DIR = 3
MENU_RESTART = 4
MENU_QUIT = 5

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


# ─────────────────────────── Win32 结构体 ───────────────────────────
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


user32.DefWindowProcW.restype = LRESULT
# 🔴 必须声明 argtypes：不声明的话 ctypes 会把 Python int 当 **32 位** C int 传，
#    而 WM_NCCREATE 等消息的 lparam 是 64 位指针 → OverflowError，
#    回调里一旦抛异常就不会再调 DefWindowProcW，窗口行为会不正常。
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadIconW.restype = wintypes.HANDLE
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.CreateWindowExW.restype = wintypes.HWND
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


# ─────────────────────────── 日志 ───────────────────────────
def _new_log_path() -> Path:
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return LOG_DIRECTORY / f"服务会话-{time.strftime('%Y%m%d-%H%M%S')}.log"


def _latest_log_path() -> Path | None:
    files = sorted(LOG_DIRECTORY.glob("服务会话-*.log"))
    return files[-1] if files else None


class RunLog:
    """一次运行一个日志文件；本程序与服务的输出都写进同一份，本程序的带 [tray] 前缀。"""

    def __init__(self) -> None:
        self.path = _new_log_path()
        self._handle = open(self.path, "ab", buffering=0)
        self.note(f"服务会话开始（tray pid={os.getpid()}）")

    def note(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        try:
            self._handle.write(f"[{stamp}] [tray] {text}\n".encode("utf-8"))
        except OSError:
            pass

    def fileno(self) -> int:
        return self._handle.fileno()

    def close(self) -> None:
        try:
            self.note("日志关闭")
            self._handle.close()
        except OSError:
            pass


def print_tail(count: int) -> int:
    path = _latest_log_path()
    if path is None:
        print(f"还没有日志文件（{LOG_DIRECTORY}）")
        return 0
    data = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = data[-count:] if count > 0 else data
    print(f"--- {path}  (最后 {len(tail)} / 共 {len(data)} 行) ---")
    for line in tail:
        print(line)
    return 0


# ─────────────────────────── 托盘图标 ───────────────────────────
def build_icon_file() -> None:
    """把现成的 PNG 包成 .ico（vista+ 支持 PNG 压缩的图标），避免依赖图像库。

    失败也无所谓 —— 下面 load_icon() 会退回系统默认图标。
    """
    try:
        if ICON_PATH.is_file() and ICON_PATH.stat().st_size > 0:
            return
        png = ICON_SOURCE_PNG.read_bytes()
        if png[:8] != b"\x89PNG\r\n\x1a\n":
            return
        width = int.from_bytes(png[16:20], "big")
        height = int.from_bytes(png[20:24], "big")
        entry_w = 0 if width >= 256 else width
        entry_h = 0 if height >= 256 else height
        header = (
            (0).to_bytes(2, "little")      # reserved
            + (1).to_bytes(2, "little")    # type = icon
            + (1).to_bytes(2, "little")    # 只放一张
        )
        entry = (
            bytes([entry_w, entry_h, 0, 0])
            + (1).to_bytes(2, "little")    # planes
            + (32).to_bytes(2, "little")   # bpp
            + len(png).to_bytes(4, "little")
            + (22).to_bytes(4, "little")   # 数据偏移 = 6 + 16
        )
        ICON_PATH.write_bytes(header + entry + png)
    except OSError:
        pass


def load_icon():
    handle = None
    if ICON_PATH.is_file():
        handle = user32.LoadImageW(
            None, str(ICON_PATH), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
    if not handle:
        handle = user32.LoadIconW(None, ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wintypes.LPCWSTR))
    return handle


# ─────────────────────────── 服务进程管理 ───────────────────────────
class ServiceSupervisor:
    """拉起 / 停掉 / 重启地图服务，并把输出实时接到日志文件。"""

    def __init__(self, log: RunLog) -> None:
        self.log = log
        self.proc: subprocess.Popen | None = None

    def _child_env(self) -> dict:
        env = dict(os.environ)
        # 与老 start_rail_map.bat 保持一致：清掉这两个，免得外部设置干扰服务
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONSTARTUP", None)
        env["PYTHONPATH"] = ""
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def start(self) -> bool:
        if not PYTHON.is_file():
            self.log.note(f"启动失败：找不到 python.exe（{PYTHON}）")
            return False
        if not SERVICE_ENTRY.is_file():
            self.log.note(f"启动失败：找不到服务入口（{SERVICE_ENTRY}）")
            return False
        # -u：不缓冲，日志实时落盘（排障关键）；-X utf8：中文不乱码
        command = [
            str(PYTHON),
            "-X",
            "utf8",
            "-u",
            str(SERVICE_ENTRY),
            "--ui-directory",
            str(UI_DIRECTORY),
        ]
        self.log.note(f"启动服务：{' '.join(command)}")
        try:
            self.proc = subprocess.Popen(
                command,
                stdout=self.log.fileno(),
                stderr=subprocess.STDOUT,
                cwd=str(HERE),
                env=self._child_env(),
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as error:
            self.log.note(f"启动失败：{error}")
            self.proc = None
            return False
        self.log.note(f"服务进程已起 pid={self.proc.pid}")
        return True

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.log.note(f"停止服务 pid={self.proc.pid}")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.log.note("服务未在 8 秒内退出，强制结束")
                self.proc.kill()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.log.note("强制结束也超时，放弃等待")
        else:
            self.log.note(f"服务已自行退出（returncode={self.proc.returncode}）")
        self.proc = None


def port_is_listening() -> bool:
    """8790 是否已被占用（判断是不是已经有实例在跑 / 服务是否已起来）。

    ⚠️ 这里**故意不解码**：中文 Windows 的 netstat 输出是 GBK，
    用 `text=True`（UTF-8）解码会抛 UnicodeDecodeError，
    而且异常发生在 subprocess 的读取线程里 → stdout 变成 None（2026-09-29 实测踩到）。
    所以直接拿 bytes 找 b":8790" 和 b"LISTENING"。
    """
    try:
        completed = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            timeout=8,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = completed.stdout or b""
    needle = f":{PORT}".encode("ascii")
    return any(needle in line and b"LISTENING" in line for line in output.splitlines())


# ─────────────────────────── 托盘应用 ───────────────────────────
class RailMapTray:
    CLASS_NAME = "Tpf2RailMapTrayWindow"
    MUTEX_NAME = "Local\\Tpf2RailMapTray"

    def __init__(self, log: RunLog, selftest_seconds: int = 0) -> None:
        self.log = log
        self.selftest_seconds = selftest_seconds   # >0 时：跑满这么多秒就自己收工
        self.supervisor = ServiceSupervisor(log)
        self.hwnd = None
        self.icon = None
        self._wndproc_ref = None
        self._mutex = None
        self.nid = NOTIFYICONDATAW()
        self._stopping = False

    # ---- 托盘图标 ----
    def _tooltip(self) -> str:
        state = "运行中" if self.supervisor.alive() else "已停止"
        return f"TPF2 铁路图 · {state} · {URL}"[:127]

    def _notify(self, message: int) -> bool:
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self.nid.uCallbackMessage = WM_TRAYICON
        self.nid.hIcon = self.icon
        self.nid.szTip = self._tooltip()
        return bool(shell32.Shell_NotifyIconW(message, ctypes.byref(self.nid)))

    def _refresh(self) -> None:
        if self.hwnd:
            self._notify(NIM_MODIFY)

    # ---- 菜单动作 ----
    def open_page(self) -> None:
        self.log.note("打开地图页")
        webbrowser.open(URL)

    def open_log(self) -> None:
        self.log.note("打开当前日志")
        subprocess.Popen(["notepad.exe", str(self.log.path)], creationflags=CREATE_NO_WINDOW)

    def open_log_dir(self) -> None:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(LOG_DIRECTORY)], creationflags=CREATE_NO_WINDOW)

    def restart(self) -> None:
        self.log.note("重启服务")
        self.supervisor.stop()
        # 等端口真正释放，否则新进程会 "address already in use"
        for _ in range(30):
            if not port_is_listening():
                break
            time.sleep(0.3)
        self.supervisor.start()
        self._refresh()

    def quit(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.log.note("退出（停止服务并移除托盘图标）")
        self.supervisor.stop()
        if self.hwnd:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
        self.log.close()
        user32.PostQuitMessage(0)

    def _show_menu(self) -> None:
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, MENU_OPEN, "打开地图页")
        user32.AppendMenuW(menu, MF_STRING, MENU_LOG, "打开当前日志")
        user32.AppendMenuW(menu, MF_STRING, MENU_LOG_DIR, "打开日志文件夹")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, MENU_RESTART, "重启服务")
        user32.AppendMenuW(menu, MF_STRING, MENU_QUIT, "退出（停止服务）")
        # 先抢前台，否则点菜单外面菜单不会消失
        user32.SetForegroundWindow(self.hwnd)
        choice = user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, point.x, point.y, 0, self.hwnd, None
        )
        user32.DestroyMenu(menu)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)  # 让菜单干净收尾
        {
            MENU_OPEN: self.open_page,
            MENU_LOG: self.open_log,
            MENU_LOG_DIR: self.open_log_dir,
            MENU_RESTART: self.restart,
            MENU_QUIT: self.quit,
        }.get(choice, lambda: None)()

    # ---- 窗口过程 ----
    def _wnd_proc(self, hwnd, message, wparam, lparam):
        if message == WM_TRAYICON:
            if lparam == WM_LBUTTONUP:
                self.open_page()
            elif lparam in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._show_menu()
            return 0
        if message == WM_TIMER:
            if wparam == 2:                      # 自检模式：到点自己收工
                self.log.note(f"自检完成（{self.selftest_seconds} 秒），移除托盘图标并退出")
                self.quit()
                return 0
            self._refresh()
            return 0
        if message == WM_DESTROY:
            self.quit()
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    # ---- 主流程 ----
    def _already_running(self) -> bool:
        """单实例锁。进程活着锁就在；进程没了系统自动释放。

        为什么要有它：连点两次图标时，两个实例会各自拉起一个服务去抢 8790，
        后起来的那个必然失败 —— 用户只会看到一个"已停止"的托盘图标，莫名其妙。
        """
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._mutex = kernel32.CreateMutexW(None, True, self.MUTEX_NAME)
        return ctypes.get_last_error() == 183   # ERROR_ALREADY_EXISTS

    def run(self) -> int:
        if self._already_running():
            self.log.note("已有实例在跑（单实例锁）→ 只打开页面，不再起第二个")
            self.open_page()
            self.log.close()
            return 0

        if port_is_listening():
            # 端口被别的进程占着 —— 不重复起，只开页面
            self.log.note(f"端口 {PORT} 已被占用，判定为已在运行 → 只打开页面")
            self.open_page()
            self.log.close()
            return 0

        if not self.supervisor.start():
            self.log.close()
            return 1

        build_icon_file()
        self.icon = load_icon()
        if not self.icon:
            self.log.note("图标加载失败，托盘图标可能不显示（err=%d）" % ctypes.get_last_error())

        hinstance = kernel32.GetModuleHandleW(None)
        self._wndproc_ref = WNDPROC(self._wnd_proc)   # 必须留引用，否则回调被回收
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinstance
        wc.lpszClassName = self.CLASS_NAME
        if not user32.RegisterClassW(ctypes.byref(wc)):
            self.log.note(f"RegisterClassW 失败（err={ctypes.get_last_error()}）")
        self.hwnd = user32.CreateWindowExW(
            0, self.CLASS_NAME, "TPF2 Rail Map", 0, 0, 0, 0, 0, None, None, hinstance, None
        )
        if not self.hwnd:
            self.log.note("CreateWindowExW 失败，托盘图标无法创建")
            self.supervisor.stop()
            self.log.close()
            return 1

        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 1
        if self._notify(NIM_ADD):
            self.log.note("托盘图标已就位（任务栏右下角的 ^ 展开里）")
        else:
            self.log.note(f"Shell_NotifyIcon(NIM_ADD) 失败（err={ctypes.get_last_error()}）")

        user32.SetTimer(self.hwnd, 1, 3000, None)   # 每 3 秒刷新提示文字
        if self.selftest_seconds > 0:
            user32.SetTimer(self.hwnd, 2, self.selftest_seconds * 1000, None)

        # 服务起来后自动开一次页面（后台线程里等端口）；自检模式不弹浏览器
        def _open_when_ready() -> None:
            for _ in range(60):
                if port_is_listening():
                    if self.selftest_seconds > 0:
                        self.log.note("服务已监听端口（自检模式，不打开浏览器）")
                    else:
                        self.log.note("服务已监听端口，自动打开地图页")
                        webbrowser.open(URL)
                    return
                if not self.supervisor.alive():
                    self.log.note("服务进程已退出，放弃自动开页面（看日志排障）")
                    return
                time.sleep(0.5)
            self.log.note("等了 30 秒端口仍未起来，不自动开页面（看日志排障）")

        threading.Thread(target=_open_when_ready, daemon=True).start()

        message = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--tail":
        try:
            count = int(argv[1]) if len(argv) > 1 else 40
        except ValueError:
            count = 40
        return print_tail(count)
    if argv and argv[0] == "--selftest":
        # 自检：完整拉一遍（起服务 + 挂托盘图标），N 秒后自己收工，不留痕迹。
        # 用来验证"托盘链路通不通"，比人肉点菜单可靠。
        try:
            seconds = int(argv[1]) if len(argv) > 1 else 8
        except ValueError:
            seconds = 8
        return RailMapTray(RunLog(), selftest_seconds=seconds).run()
    return RailMapTray(RunLog()).run()


if __name__ == "__main__":
    raise SystemExit(main())
