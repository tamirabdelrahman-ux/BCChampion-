"""Stop a locally running BCChampion process by PID file if present."""
from pathlib import Path
import os, subprocess
DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "BCChampion"
PID = DATA_DIR / "bchampion.pid"
if PID.exists():
    try:
        pid = int(PID.read_text().strip())
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        PID.unlink(missing_ok=True)
