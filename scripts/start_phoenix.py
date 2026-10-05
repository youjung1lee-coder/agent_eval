"""Run an installed Phoenix server with workspace-local storage and optional features off."""
import os
from pathlib import Path

os.environ.setdefault("PHOENIX_WORKING_DIR", str(Path("data/phoenix").resolve()))
os.environ.setdefault("PHOENIX_HOST", "127.0.0.1")
os.environ.setdefault("PHOENIX_PORT", "6006")
os.environ.setdefault("PHOENIX_TELEMETRY_ENABLED", "false")
os.environ.setdefault("PHOENIX_DISABLE_AGENT_ASSISTANT", "true")
os.environ.setdefault("PHOENIX_LOGGING_LEVEL", "WARNING")

if __name__ == "__main__":
    import runpy
    import sys
    sys.argv = ["phoenix", "serve"]
    runpy.run_module("phoenix.server.main", run_name="__main__")
