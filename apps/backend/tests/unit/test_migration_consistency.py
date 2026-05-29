"""Anti-drift: the SQLAlchemy models and the Alembic head must agree.

`alembic check` autogenerates against the live (migrated) DB and fails if any
difference is detected. This is what keeps models == migration head.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_models_match_migration_head(_migrate):
    result = subprocess.run(
        ["alembic", "check"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Models drifted from migration head:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
