"""Shared test fixtures.

Environment is set *before* importing the app so config picks up:
  - an in-memory SQLite database (StaticPool => shared across threads)
  - a throw-away folder for generated PDFs
"""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CERT_STORAGE_DIR"] = tempfile.mkdtemp(prefix="cert-tests-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """Each test starts from empty tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    # The context manager runs the lifespan (init_db). Starlette's TestClient
    # also executes BackgroundTasks before returning the response, so when
    # POST /jobs returns, generation has already run. Tests assert on final
    # state without polling.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def payload():
    return {
        "event_name": "Python Backend Bootcamp 2026",
        "issuer": "Aereo Academy",
        "issue_date": "2026-10-07",
        "recipients": [
            {"name": "Arun Kumar", "email": "arun@example.com"},
            {"name": "Priya Sharma", "email": "priya@example.com", "completion_date": "2026-10-01"},
            {"name": "Rahul Verma", "email": "rahul@example.com"},
        ],
    }
