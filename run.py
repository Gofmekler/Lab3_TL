"""Точка входа: запускает веб-приложение и открывает его в браузере.

    python run.py                    # http://127.0.0.1:8000
    python run.py --port 8080 --no-browser

Порт по умолчанию 8000, а не 5000: на macOS 12+ порт 5000 занят AirPlay Receiver.
"""

import argparse
import logging
import socket
import sys
import threading
import webbrowser


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


def main() -> None:
    parser = argparse.ArgumentParser(description="MD: атомы в ячейке (LJ-потенциал)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="не открывать браузер")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    try:
        from lj_md.view.app import create_app
    except ModuleNotFoundError as exc:
        sys.exit(f"Не установлена зависимость «{exc.name}».\n"
                 f"Выполните в терминале PyCharm:  pip install -r requirements.txt")

    if not port_is_free(args.host, args.port):
        sys.exit(f"Порт {args.port} занят. Остановите предыдущий запуск (красный квадрат "
                 f"в PyCharm) или укажите другой порт:  --port {args.port + 1}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    # запросы кадров анимации идут ~30 раз в секунду — не засоряем ими консоль
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    url = f"http://{args.host}:{args.port}"
    print(f"\n  Приложение запущено: {url}\n  Остановка: Ctrl+C или ⌘F2 в PyCharm\n")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True,
            use_reloader=False)


if __name__ == "__main__":
    main()
