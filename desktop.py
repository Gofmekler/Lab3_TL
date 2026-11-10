"""Точка входа для десктопной сборки (один исполняемый файл, см. build_desktop.py).

Отличия от run.py:
- порт выбирается автоматически (свободный), чтобы запуск не падал,
  если 8000 у пользователя чем-то занят;
- сервер слушает только 127.0.0.1 — приложение доступно лишь на этом компьютере;
- окно консоли остаётся открытым: закрыли его — приложение завершилось.
"""

import sys
import threading
import webbrowser

from werkzeug.serving import make_server

from lj_md.view.app import create_app


def main() -> None:
    server = make_server("127.0.0.1", 0, create_app(), threaded=True)
    url = f"http://127.0.0.1:{server.server_port}"

    print("\n  Молекулярная динамика: атомы в ячейке (потенциал Леннард-Джонса)", flush=True)
    print(f"\n  Приложение открыто в браузере: {url}", flush=True)
    print("  Если браузер не открылся — скопируйте адрес в адресную строку.", flush=True)
    print("\n  Чтобы завершить работу, закройте это окно (или нажмите Ctrl+C).\n", flush=True)

    threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    sys.exit(0)


if __name__ == "__main__":
    main()
