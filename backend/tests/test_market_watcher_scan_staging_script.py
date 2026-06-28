"""Tests for run-market-watcher-scan-staging.sh guardrails (Slice 73)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run-market-watcher-scan-staging.sh"


def _run(*env: str) -> subprocess.CompletedProcess[str]:
    command_env = {
        "BACKEND_URL": "https://alphatrade-api-staging.onrender.com",
        "CONFIRM": "RUN_READ_ONLY_SCAN",
        **{k: v for item in env for k, v in [item.split("=", 1)]},
    }
    return subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env={
            **dict(__import__("os").environ),
            **command_env,
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_script_refuses_non_dry_run_without_create_in_app_confirm() -> None:
    result = _run(
        "DRY_RUN=false",
        "STAGING_DEMO_PASSWORD=local-test-password",
    )
    assert result.returncode != 0
    assert "CREATE_IN_APP_ALERTS_CONFIRM=CREATE_IN_APP_ALERTS_ONLY" in result.stderr


def test_script_refuses_missing_demo_password() -> None:
    result = _run("DRY_RUN=true")
    assert result.returncode != 0
    assert "STAGING_DEMO_PASSWORD required" in result.stderr


def test_script_dry_run_default_does_not_require_create_in_app_confirm() -> None:
    result = _run("DRY_RUN=true")
    assert result.returncode != 0
    assert "CREATE_IN_APP_ALERTS_CONFIRM=CREATE_IN_APP_ALERTS_ONLY" not in result.stderr
    assert "STAGING_DEMO_PASSWORD required" in result.stderr


def test_script_output_does_not_print_secrets() -> None:
    password = "super-secret-demo-password-12345"
    result = _run("DRY_RUN=true", f"STAGING_DEMO_PASSWORD={password}")
    combined = (result.stdout or "") + (result.stderr or "")
    assert password not in combined
    forbidden = [
        r"TELEGRAM_BOT_TOKEN",
        r"postgresql\+psycopg://",
        r"rediss?://",
    ]
    for pattern in forbidden:
        assert re.search(pattern, combined, re.I) is None
