"""Сборка приложения в один исполняемый файл (PyInstaller).

    pip install -r requirements-build.txt
    python build_desktop.py

Результат — в папке dist/:
    macOS:   LJ_MD-macos-arm64 (или -x86_64)
    Windows: LJ_MD-windows-AMD64.exe
    Linux:   LJ_MD-linux-x86_64

PyInstaller не умеет кросс-компиляцию: файл для Windows собирается на Windows,
для macOS — на macOS (и под ту же архитектуру процессора).
"""

import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OS_NAME = {"darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
NAME = f"LJ_MD-{OS_NAME}-{platform.machine()}"


def main() -> None:
    try:
        import PyInstaller.__main__
    except ModuleNotFoundError:
        sys.exit("Не установлен PyInstaller. Выполните:  pip install -r requirements-build.txt")

    data = [
        ("lj_md/view/templates", "lj_md/view/templates"),
        ("lj_md/view/static", "lj_md/view/static"),
    ]
    args = [
        str(ROOT / "desktop.py"),
        "--onefile",
        "--name", NAME,
        "--noconfirm",
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # не тащим в сборку то, что приложению не нужно
        "--exclude-module", "pytest",
        "--exclude-module", "tkinter",
    ]
    for src, dst in data:
        args += ["--add-data", f"{ROOT / src}{os.pathsep}{dst}"]

    PyInstaller.__main__.run(args)
    print(f"\nГотово: {ROOT / 'dist' / NAME}{'.exe' if sys.platform == 'win32' else ''}")


if __name__ == "__main__":
    main()
