import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sandbox = tempfile.TemporaryDirectory()
os.environ.update(
    DATABASE_URL="sqlite:///" + sandbox.name + "/test.db",
    DEMO_MODE="true",
    PHOENIX_MODE="fixture",
    AGENT_MODE="mock",
    DEEPEVAL_TELEMETRY_OPT_OUT="YES",
    RAGAS_DO_NOT_TRACK="true",
)
from backend.api import app
from backend.db import engine
from backend.schema_v1 import metadata
from backend.seed import seed


@pytest.fixture
def client():
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    with engine.begin() as c:
        for t in reversed(metadata.sorted_tables):
            c.execute(t.delete())
    seed()
    with TestClient(app) as client:
        yield client


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def service(module):
    port = free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            module,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=root,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/health", timeout=0.2).is_success:
                    break
            except httpx.TransportError:
                pass
            if proc.poll() is not None:
                raise RuntimeError("service stopped")
            time.sleep(0.05)
        else:
            raise RuntimeError("service startup timeout")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def agent_url(monkeypatch):
    for url in service("backend.mock_agent:app"):
        monkeypatch.setenv("MOCK_AGENT_URL", url)
        yield url
