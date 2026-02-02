import os
import subprocess
import time

import requests
from fastapi import FastAPI

# Usa OLLAMA_BASE_URL se presente (coerente con il parser),
# altrimenti fallback a localhost per ambienti non containerizzati.
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def check_ollama_api(timeout: int = 2) -> bool:
    """Check Ollama HTTP API quickly (non-blocking)."""
    try:
        r = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=timeout,
        )
        return r.status_code == 200
    except Exception:
        return False


def list_models_cli() -> str:
    """Return output of `ollama list` (empty string on error)."""
    try:
        cmd = ["ollama", "list"]
        out = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return out.strip()
    except Exception:
        return ""


def ensure_ollama_nonblocking(app: FastAPI, retries: int = 3, wait: int = 2) -> bool:
    """Try a few quick attempts to detect Ollama; set app.state flags
    and return readiness.

    This MUST NOT block startup for long. Use small retries and mark state
    for the app.
    """
    ready = False

    for _ in range(retries):
        if check_ollama_api(timeout=2):
            ready = True
            break
        time.sleep(wait)

    app.state.ollama_ready = ready
    app.state.ollama_models = list_models_cli() if ready else ""
    return ready
