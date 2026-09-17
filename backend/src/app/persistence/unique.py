"""Classify PostgreSQL unique-constraint failures without leaking SQL details."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


def is_unique_violation(exc: IntegrityError, *constraint_names: str) -> bool:
    orig = getattr(exc, "orig", None)
    sources = [str(exc).lower()]
    pgcode = getattr(orig, "pgcode", None) if orig is not None else None
    if orig is not None:
        sources.append(str(orig).lower())
        diag = getattr(orig, "diag", None)
        if diag is not None:
            name = getattr(diag, "constraint_name", None)
            if name in constraint_names:
                return True
    joined = " ".join(sources)
    if constraint_names:
        return any(name.lower() in joined for name in constraint_names)
    if pgcode == "23505":
        return True
    return "unique" in joined or "duplicate key" in joined
