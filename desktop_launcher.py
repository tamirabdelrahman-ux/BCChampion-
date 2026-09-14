"""BCChampion desktop launcher: no console, local-only web app."""
from __future__ import annotations
import os, socket, threading, time, webbrowser
from pathlib import Path

APP_NAME = "BCChampion"
PORT = 8790
URL = f"http://127.0.0.1:{PORT}"
DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("BLOOD_DASHBOARD_AUTH_MODE", "development")
os.environ.setdefault("BLOOD_DASHBOARD_ADMINS", "admin")
os.environ.setdefault("BLOOD_DASHBOARD_SECRET_KEY", "BCChampion-local-desktop-v1.0.0")
os.environ.setdefault("BLOOD_DASHBOARD_DATA_DIR", str(DATA_DIR))
os.environ.setdefault("BLOOD_DASHBOARD_DATABASE", str(DATA_DIR / "bchampion.sqlite3"))

from waitress import serve
from app import app


def port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.2):
            return True
    except OSError:
        return False


def open_browser_when_ready():
    for _ in range(80):
        if port_open():
            webbrowser.open(URL)
            return
        time.sleep(0.15)


def main():
    if port_open():
        webbrowser.open(URL)
        return
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    (DATA_DIR / "bchampion.pid").write_text(str(os.getpid()), encoding="ascii")
    try:
        serve(app, host="127.0.0.1", port=PORT, threads=4)
    finally:
        (DATA_DIR / "bchampion.pid").unlink(missing_ok=True)

if __name__ == "__main__":
    main()
