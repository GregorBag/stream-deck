"""Поиск Windows-программ для назначения аудиоканалу."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import ntpath
import os
from pathlib import Path
from collections.abc import Callable, Iterable
import winreg


@dataclass(frozen=True)
class ApplicationCandidate:
    name: str
    path: Path


class ApplicationCatalog:
    def __init__(
        self,
        start_menu_paths: tuple[Path, ...] | None = None,
        resolve_shortcut: Callable[[Path], Path | None] | None = None,
        app_paths: Callable[[], Iterable[tuple[str, Path]]] | None = None,
    ) -> None:
        self._start_menu_paths = (
            start_menu_paths if start_menu_paths is not None else _start_menu_paths()
        )
        self._resolve_shortcut = resolve_shortcut or _resolve_shortcut
        self._app_paths = app_paths or _app_paths

    def running(self) -> tuple[ApplicationCandidate, ...]:
        return _running_windows()

    def installed(self) -> tuple[ApplicationCandidate, ...]:
        candidates: dict[str, ApplicationCandidate] = {}
        for directory in self._start_menu_paths:
            if not directory.is_dir():
                continue
            for shortcut in directory.rglob("*.lnk"):
                path = self._resolve_shortcut(shortcut)
                if path is not None and path.is_file() and path.suffix.lower() == ".exe":
                    candidates.setdefault(
                        ntpath.normcase(str(path)),
                        ApplicationCandidate(shortcut.stem, path),
                    )
        for name, path in self._app_paths():
            if path.is_file() and path.suffix.lower() == ".exe":
                candidates.setdefault(
                    ntpath.normcase(str(path)),
                    ApplicationCandidate(Path(name).stem, path),
                )
        return tuple(sorted(candidates.values(), key=lambda item: item.name.casefold()))


def _start_menu_paths() -> tuple[Path, ...]:
    locations = []
    for variable in ("APPDATA", "ProgramData"):
        root = os.environ.get(variable)
        if root:
            locations.append(Path(root) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return tuple(locations)


def _resolve_shortcut(shortcut: Path) -> Path | None:
    try:
        from _ctypes import COMError
        from comtypes.client import CreateObject

        shell = CreateObject("WScript.Shell", dynamic=True)
        target = shell.CreateShortcut(str(shortcut)).TargetPath
        return Path(os.path.expandvars(target)) if target else None
    except (OSError, COMError, AttributeError, ValueError):
        return None


def _app_paths() -> Iterable[tuple[str, Path]]:
    subkey = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as root:
                    count = winreg.QueryInfoKey(root)[0]
                    for index in range(count):
                        name = winreg.EnumKey(root, index)
                        try:
                            with winreg.OpenKey(root, name) as entry:
                                value, _ = winreg.QueryValueEx(entry, "")
                            if isinstance(value, str):
                                yield name, Path(os.path.expandvars(value))
                        except OSError:
                            continue
            except OSError:
                continue


def _running_windows() -> tuple[ApplicationCandidate, ...]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    dwmapi.DwmGetWindowAttribute.argtypes = [
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    ]
    dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

    candidates: dict[str, ApplicationCandidate] = {}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd: int, _unused: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):
            return True
        if user32.GetWindowLongW(hwnd, -20) & 0x80:
            return True
        cloaked = wintypes.DWORD()
        if dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if not process_id.value or process_id.value == os.getpid():
            return True
        handle = kernel32.OpenProcess(0x1000, False, process_id.value)
        if not handle:
            return True
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return True
            path = Path(buffer.value)
            if path.suffix.lower() != ".exe":
                return True
            key = ntpath.normcase(str(path))
            candidates.setdefault(key, ApplicationCandidate(title.value, path))
        finally:
            kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    callback = callback_type(visit)
    user32.EnumWindows(callback, 0)
    return tuple(candidates.values())
