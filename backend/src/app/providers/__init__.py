"""External-service provider abstractions.

Every provider exposes a common interface with a real implementation
(placeholder), a mock implementation, fallback behavior, and status reporting.
This slice ships the base contracts, a registry, and mock providers so the
``/providers/status`` endpoint is fully functional without any real credentials.
"""
