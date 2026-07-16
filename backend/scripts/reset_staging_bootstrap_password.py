"""Rotate the staging bootstrap operator account password (Postgres only).

Operator tool — never logs or prints the password. Updates a single user row
by email (default: seed-bootstrap-1782212606@example.com).

Usage:
  cd backend
  ENV_FILE=../.env.staging ../scripts/reset-staging-bootstrap-password.sh

  # Non-interactive (password in env, never echoed):
  STAGING_BOOTSTRAP_PASSWORD_NEW='...' ENV_FILE=.env.staging \\
    ./scripts/reset-staging-bootstrap-password.sh
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.db.models import User
from app.db.session import get_session_factory
from app.security.passwords import hash_password

DEFAULT_BOOTSTRAP_EMAIL = "seed-bootstrap-1782212606@example.com"


def _read_password(from_env: str) -> str:
    value = os.environ.get(from_env, "").strip()
    if value:
        return value
    first = getpass.getpass("New bootstrap password: ")
    second = getpass.getpass("Confirm bootstrap password: ")
    if first != second:
        raise ValidationAppError("Passwords do not match.")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rotate staging bootstrap account password (operator only).",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("STAGING_BOOTSTRAP_EMAIL", DEFAULT_BOOTSTRAP_EMAIL),
        help="Bootstrap user email to update.",
    )
    parser.add_argument(
        "--from-env",
        default="STAGING_BOOTSTRAP_PASSWORD_NEW",
        help="Environment variable holding the new password (non-interactive).",
    )
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not email:
        print("Email must not be empty.", file=sys.stderr)
        return 1

    try:
        password = _read_password(args.from_env)
    except ValidationAppError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not password:
        print(
            f"Set {args.from_env} or enter the password interactively (input is hidden).",
            file=sys.stderr,
        )
        return 1

    get_settings.cache_clear()
    settings = get_settings()

    with get_session_factory()() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"Bootstrap user not found: {email}", file=sys.stderr)
            return 1
        user.hashed_password = hash_password(password, settings)
        session.commit()

    print(f"Bootstrap password updated for {email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
