"""Runtime configuration, read once from environment variables.

Defaults let the app run with zero setup (SQLite file + local folder).
Override via env for other environments, e.g. DATABASE_URL=postgresql+psycopg://...
"""

import os
from pathlib import Path

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")

# Where generated PDFs are written. One sub-folder per job.
CERT_STORAGE_DIR: Path = Path(os.getenv("CERT_STORAGE_DIR", "./storage/certificates"))

# Upper bound per request so one call cannot monopolise the worker.
MAX_RECIPIENTS_PER_JOB: int = int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000"))
