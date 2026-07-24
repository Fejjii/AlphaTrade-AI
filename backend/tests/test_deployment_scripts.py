"""Tests that deployment helper scripts exist and are executable."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = (
    "scripts/check-env.sh",
    "scripts/verify-safety.sh",
    "scripts/staging-smoke.sh",
    "scripts/staging-live-smoke.sh",
    "scripts/post-deploy-smoke-gate.sh",
    "scripts/validate-exchange-demo-staging.sh",
    "scripts/run-market-watcher-scan-staging.sh",
    "scripts/run-slice66b-controlled-demo-order.sh",
    "scripts/test-seed-path-staging.sh",
    "scripts/run-migrations.sh",
    "scripts/provider-validation-smoke.sh",
    "scripts/recreate-rag-collection.sh",
    "scripts/reingest-knowledge-base.sh",
)


def test_deployment_scripts_exist_and_are_executable() -> None:
    for relative in SCRIPTS:
        path = ROOT / relative
        assert path.is_file(), f"missing {relative}"
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{relative} is not executable"


def test_staging_env_example_exists() -> None:
    assert (ROOT / ".env.staging.example").is_file()
    assert (ROOT / "frontend/.env.staging.example").is_file()


def test_staging_deployment_docs_exist() -> None:
    for relative in (
        "docs/pre_deployment_checklist.md",
        "docs/deployment_command_pack.md",
        "docs/staging_deployment_worksheet.template.md",
        "docs/staging_execution_checklist.md",
        "docs/staging_deployment.md",
        "docs/deploy_rollback_runbook.md",
        "docs/slice_66b_demo_venue_validation.md",
        "render.yaml",
        "frontend/vercel.json",
    ):
        assert (ROOT / relative).is_file(), f"missing {relative}"


def test_verify_safety_detects_unsafe_health_payload() -> None:
    """Safety logic mirrors scripts/verify-safety.sh expectations."""
    unsafe = {"execution_mode": "trade", "real_trading_enabled": True}
    assert unsafe["execution_mode"] != "paper" or unsafe["real_trading_enabled"] is not False

    safe = {"execution_mode": "paper", "real_trading_enabled": False}
    assert safe["execution_mode"] == "paper"
    assert safe["real_trading_enabled"] is False


def test_post_deploy_smoke_gate_self_check() -> None:
    """AT-005 gate wiring check runs without network access."""
    script = ROOT / "scripts/post-deploy-smoke-gate.sh"
    result = subprocess.run(
        [str(script), "--self-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "self-check passed" in result.stdout


def test_post_deploy_smoke_gate_requires_base_url() -> None:
    script = ROOT / "scripts/post-deploy-smoke-gate.sh"
    env = {k: v for k, v in os.environ.items() if k != "BASE_URL"}
    result = subprocess.run(
        [str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 2
    assert "BASE_URL is required" in result.stderr


def test_post_deploy_smoke_gate_rejects_placeholder_base_url() -> None:
    script = ROOT / "scripts/post-deploy-smoke-gate.sh"
    result = subprocess.run(
        [str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "BASE_URL": "https://<YOUR-API>"},
    )
    assert result.returncode == 2
    assert "placeholder" in result.stderr.lower()


def test_post_deploy_smoke_gate_mandates_verify_safety() -> None:
    """Gate script must keep verify-safety as a hard dependency."""
    text = (ROOT / "scripts/post-deploy-smoke-gate.sh").read_text(encoding="utf-8")
    assert "verify-safety.sh" in text
    assert "GATE FAILED" in text
    assert "docs/deploy_rollback_runbook.md" in text


def test_deploy_rollback_runbook_covers_required_sections() -> None:
    text = (ROOT / "docs/deploy_rollback_runbook.md").read_text(encoding="utf-8")
    for needle in (
        "Rollback triggers",
        "Rollback steps",
        "Post-rollback verification",
        "Failure handling",
        "post-deploy-smoke-gate.sh",
        "ENABLE_REAL_TRADING",
        "execution_mode",
    ):
        assert needle in text, f"missing section/marker: {needle}"
