"""Inko — local receipt generator. Entry point.

Starts the Flask backend on a free localhost port in a daemon thread,
then opens a native pywebview window pointed at it.
"""
import socket
import threading
import time

import webview

import paths
from server import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)


def main() -> None:
    port = _free_port()
    app = create_app()

    def run() -> None:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    threading.Thread(target=run, daemon=True).start()
    _wait_for_server(port)

    env = paths.env()
    title = "Inko" if env == "prod" else f"Inko — {env.upper()}"
    webview.create_window(
        title,
        f"http://127.0.0.1:{port}/",
        width=1000, height=750, min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
