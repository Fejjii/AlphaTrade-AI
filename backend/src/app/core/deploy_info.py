"""Deploy metadata helpers (git revision visibility for operators)."""

from __future__ import annotations

import os
import re

_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

_GIT_SHA_ENV_KEYS = ("GIT_SHA", "RENDER_GIT_COMMIT", "SOURCE_VERSION")


def resolve_git_sha() -> str | None:
    """Return the deployed git revision when available from the environment."""
    for key in _GIT_SHA_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if not value:
            continue
        if _GIT_SHA_RE.fullmatch(value):
            return value.lower()
        # Render and some CI systems may expose full refs; keep a safe prefix.
        if len(value) >= 7:
            return value[:40].lower()
    return None
