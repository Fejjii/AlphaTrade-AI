"""Repositories: the only place that reads/writes the database.

Repositories contain no prompts, no LLM calls, and no business reasoning — they
are pure persistence boundaries (master prompt §6).
"""
