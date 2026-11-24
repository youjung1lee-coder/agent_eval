"""Compose entry point. Keep the API, durable worker and fixture HTTP server isolated processes."""

import os
import signal
import subprocess
import sys
import time
from alembic import command
from alembic.config import Config
from .seed import seed


def main():
    command.upgrade(Config("alembic.ini"), "head")
    seed()
    commands = [
        ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"],
        ["backend.worker"],
    ]
    if os.getenv("AGENT_MODE", "mock") == "mock":
        commands.append(["uvicorn", "backend.mock_agent:app", "--port", "8101"])
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for args in commands:
            children.append(subprocess.Popen([sys.executable, "-m", *args]))
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("GAIA child process stopped")
            time.sleep(0.3)
    finally:
        for child in children:
            child.terminate()
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
