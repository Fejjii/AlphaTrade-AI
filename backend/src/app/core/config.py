"""Application settings loaded from environment variables.

Settings are the single source of truth for runtime configuration. They are
validated at startup so the service fails fast on misconfiguration rather than
silently running with unsafe defaults.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment."""

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class ExecutionMode(StrEnum):
    """Trading execution mode.

    ``paper`` is the only safe default. ``trade`` additionally requires
    ``enable_real_trading=True`` (enforced below) and is intentionally not
    wired in this scaffold.
    """

    PAPER = "paper"
    READ_ONLY = "read_only"
    TRADE = "trade"


class Settings(BaseSettings):
    """Validated application configuration.

    Values are read from environment variables (and an optional ``.env`` file),
    case-insensitively. Unknown variables are ignored so the same ``.env`` can be
    shared across services.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "AlphaTrade AI"
    environment: Environment = Environment.LOCAL
    debug: bool = True
    log_level: str = "INFO"
    log_json: bool = True

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    request_id_header: str = "X-Request-ID"

    # --- Trading safety ---
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    enable_real_trading: bool = False

    # --- Data stores (placeholders; clients wired in later slices) ---
    database_url: str = "postgresql+psycopg://alphatrade:alphatrade@localhost:5432/alphatrade"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    # --- Providers (blank credentials -> mock/fallback providers) ---
    provider_mode: str = "mock"  # mock | fallback | live
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embeddings_model: str = "text-embedding-3-small"

    # --- Market data (read-only; Binance public API, no key required) ---
    market_data_enabled: bool = True
    market_data_provider: str = "binance"  # binance | mock
    market_data_spot_base_url: str = "https://api.binance.com"
    market_data_futures_base_url: str = "https://fapi.binance.com"
    market_data_cache_use_redis: bool = True
    market_data_timeout_seconds: float = 10.0

    # --- Observability ---
    langsmith_api_key: str = ""
    observability_strict_mode: bool = False
    trace_id_header: str = "X-Trace-ID"

    # --- Authentication ---
    jwt_secret: str = Field(
        default="dev-only-change-me-before-production",
        description="HS256 signing secret for access tokens.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    auth_refresh_cookie_enabled: bool = False
    auth_refresh_cookie_name: str = "alphatrade_refresh"
    auth_refresh_cookie_path: str = "/auth"
    auth_cookie_secure: bool | None = None
    auth_cookie_samesite: str = "lax"
    auth_omit_refresh_from_body: bool = True
    access_token_denylist_enabled: bool = True
    access_token_denylist_use_redis: bool = True
    password_min_length: int = 12
    password_max_length: int = 128
    bcrypt_max_password_bytes: int = 72

    # --- Journal → RAG (optional learning loop) ---
    journal_rag_sync_enabled: bool = True

    # --- LLM narrative polish (Slice 21 — explanation only, not decision authority) ---
    narrative_llm_enabled: bool = True

    # --- Rate limiting ---
    rate_limit_use_redis: bool = True
    rate_limit_allow_in_memory_fallback: bool = True
    redis_connect_timeout_seconds: float = 1.0
    jwt_secret_min_length: int = 32

    # --- Email (Slice 25 — verification, reset, invitations) ---
    email_provider: str = "mock"  # mock | smtp | resend | sendgrid
    email_from_address: str = "noreply@alphatrade.local"
    email_base_url: str = "http://localhost:3000"
    email_send_enabled: bool = True
    email_verification_expire_hours: int = 48
    password_reset_expire_hours: int = 2
    invitation_expire_hours: int = 168
    require_email_verified: bool | None = None
    email_auto_verify_local: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    resend_api_key: str = ""
    sendgrid_api_key: str = ""

    # --- Billing (Slice 26 — disabled by default; mock unless Stripe configured) ---
    billing_enabled: bool = False
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""
    billing_checkout_success_url: str = "http://localhost:3000/billing?checkout=success"
    billing_checkout_cancel_url: str = "http://localhost:3000/billing?checkout=cancel"
    billing_portal_return_url: str = "http://localhost:3000/billing"

    @field_validator("email_provider", mode="before")
    @classmethod
    def _normalize_email_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("auth_cookie_samesite", mode="before")
    @classmethod
    def _normalize_samesite(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow a comma-separated string for ``CORS_ORIGINS`` in env files."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("provider_mode", mode="before")
    @classmethod
    def _normalize_provider_mode(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value

    @model_validator(mode="after")
    def _enforce_trading_safety(self) -> Settings:
        """Refuse to start with an inconsistent/unsafe trading configuration.

        Real execution requires BOTH ``execution_mode=trade`` and
        ``enable_real_trading=True``. Any other combination is forced to a safe,
        explicit state instead of silently allowing live orders.
        """
        if self.execution_mode is ExecutionMode.TRADE and not self.enable_real_trading:
            raise ValueError(
                "execution_mode=trade requires enable_real_trading=true. "
                "Refusing to start in an ambiguous trading configuration."
            )
        return self

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> Settings:
        """Require a strong JWT secret outside local development."""
        secret_length = len(self.jwt_secret.encode("utf-8"))
        if self.environment is not Environment.LOCAL and secret_length < self.jwt_secret_min_length:
            raise ValueError(
                f"jwt_secret must be at least {self.jwt_secret_min_length} bytes in "
                f"{self.environment.value} environments."
            )
        return self

    @model_validator(mode="after")
    def _validate_deployment_safety(self) -> Settings:
        """Enforce staging/production deployment invariants."""
        from app.core.deployment_safety import validate_deployment_settings

        validate_deployment_settings(self)
        return self

    @property
    def must_verify_email(self) -> bool:
        """Whether login requires a verified email address."""
        if self.require_email_verified is not None:
            return self.require_email_verified
        return self.environment is not Environment.LOCAL

    @property
    def real_trading_enabled(self) -> bool:
        """True only when live order execution is fully and explicitly enabled."""
        return self.execution_mode is ExecutionMode.TRADE and self.enable_real_trading


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Cached so configuration is parsed once per process. Tests can clear the
    cache via ``get_settings.cache_clear()``.
    """
    return Settings()
