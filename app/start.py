from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
    mode = os.getenv("APP_MODE", "webhook").lower()
    if mode == "polling":
        subprocess.check_call([sys.executable, "-m", "app.polling"])
        return
    port = int(os.getenv("PORT", "8000"))
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--proxy-headers",
        ]
    )


if __name__ == "__main__":
    main()
