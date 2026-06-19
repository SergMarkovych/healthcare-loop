"""
Test fixtures for the Loop FastAPI app.

Offline/deterministic discipline: both LLM toggles are forced BEFORE any backend
module is imported, so no test can reach Ollama or the network.
  - FORCE_MOCK=1        -> backend.llm.extract uses the canned/heuristic mock
  - FORCE_DETERMINISTIC=1 -> backend.fhir.summarize never calls the local model

Each test session also gets an isolated, temp-file SQLite snapshot store via
FHIR_DB, so the diff tests don't depend on (or clobber) the repo's snapshots.db.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ["FORCE_MOCK"] = "1"
os.environ["FORCE_DETERMINISTIC"] = "1"

_DB_FILE = Path(tempfile.gettempdir()) / "loop_test_snapshots.db"
_DB_FILE.unlink(missing_ok=True)
os.environ["FHIR_DB"] = str(_DB_FILE)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def fresh_store():
    """A clean snapshot store for diff tests; reset before and after."""
    from backend.fhir import service as fhir_service

    fhir_service.reset_store()
    yield fhir_service
    fhir_service.reset_store()
