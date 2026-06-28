"""Tests for run-market-watcher-scan-staging.sh guardrails (Slice 73)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run-market-watcher-scan-staging.sh"


def _run(*env: str, unset: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    command_env = {
        "BACKEND_URL": "https://alphatrade-api-staging.onrender.com",
        "CONFIRM": "RUN_READ_ONLY_SCAN",
        **{k: v for item in env for k, v in [item.split("=", 1)]},
    }
    merged_env = {**dict(__import__("os").environ), **command_env}
    for key in unset:
        merged_env.pop(key, None)
    return subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=merged_env,
        capture_output=True,
        text=True,
        check=False,
    )


def _build_scan_body(*, dry_run: str, create_confirm: str = "") -> dict[str, object]:
    """Build scan JSON body using the same Python logic as the staging script."""
    result = subprocess.run(
        [
            "bash",
            "-c",
            f"""
set -euo pipefail
DRY_RUN="{dry_run}"
CONFIRM="RUN_READ_ONLY_SCAN"
CREATE_IN_APP_ALERTS_CONFIRM="{create_confirm}"
symbols_json='["BTCUSDT"]'
timeframes_json='["15m"]'
python3 - <<PY
import json
dry_run = True if "${{DRY_RUN}}" == "true" else False
body = {{
    "confirm": "${{CONFIRM}}",
    "symbols": json.loads('''${{symbols_json}}'''),
    "timeframes": json.loads('''${{timeframes_json}}'''),
    "dry_run": dry_run,
}}
if not dry_run:
    body["create_in_app_alerts_confirm"] = "${{CREATE_IN_APP_ALERTS_CONFIRM}}"
print(json.dumps(body))
PY
""",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip())


def test_scan_body_dry_run_true_uses_python_true() -> None:
    body = _build_scan_body(dry_run="true")
    assert body["dry_run"] is True
    assert "create_in_app_alerts_confirm" not in body


def test_scan_body_dry_run_false_uses_python_false_and_includes_confirm() -> None:
    body = _build_scan_body(
        dry_run="false",
        create_confirm="CREATE_IN_APP_ALERTS_ONLY",
    )
    assert body["dry_run"] is False
    assert body["create_in_app_alerts_confirm"] == "CREATE_IN_APP_ALERTS_ONLY"


def test_script_refuses_non_dry_run_without_create_in_app_confirm() -> None:
    result = _run(
        "DRY_RUN=false",
        "STAGING_DEMO_PASSWORD=local-test-password",
    )
    assert result.returncode != 0
    assert "CREATE_IN_APP_ALERTS_CONFIRM=CREATE_IN_APP_ALERTS_ONLY" in result.stderr


def test_script_refuses_missing_demo_password() -> None:
    result = _run("DRY_RUN=true", unset=("STAGING_DEMO_PASSWORD",))
    assert result.returncode != 0
    assert "STAGING_DEMO_PASSWORD required" in result.stderr


def test_script_dry_run_default_does_not_require_create_in_app_confirm() -> None:
    result = _run("DRY_RUN=true", unset=("STAGING_DEMO_PASSWORD",))
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


def test_script_scan_body_heredoc_does_not_use_json_booleans_in_python() -> None:
    content = SCRIPT.read_text()
    assert 'dry_run = True if "${DRY_RUN}" == "true" else False' in content
    assert "if not ${DRY_RUN_JSON}:" not in content
    assert '"dry_run": ${DRY_RUN_JSON}' not in content
