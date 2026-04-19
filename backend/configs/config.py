# STL

# External
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field

# Custom
from app_common.enums import RequestEnum


class Settings(BaseSettings):
    """Config for the server"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8"
    )
    # Server
    app_host: str = Field(default="localhost")
    app_port: int = Field(default=8000)
    debug: bool = Field(default=True)
    public_api_url: str = Field(default="")

    # Database
    database: str = Field(default="appdb")
    database_password: str = Field(default="dbadmin")
    database_username: str = Field(default="dbuser")
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    database_driver: str = Field(default="postgresql+psycopg2")
    # Managed services (Timescale Cloud, Railway, etc.) expose a single
    # DATABASE_URL. When set, it wins over the six individual components.
    database_url_override: str = Field(default="", validation_alias="DATABASE_URL")

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"{self.database_driver}://"
            f"{self.database_username}:"
            f"{self.database_password}@"
            f"{self.database_host}:"
            f"{self.database_port}/"
            f"{self.database}"
        )

    # caching
    valkey_scheme: str = Field(default="redis")
    valkey_host: str = Field(default="localhost")
    valkey_port: int = Field(default=6379)
    valkey_db: int = Field(default=0)
    valkey_password: str = Field(default="")

    @computed_field
    @property
    def valkey_url(self) -> str:
        auth = f":{self.valkey_password}@" if self.valkey_password else ""
        base = f"{self.valkey_scheme}://{auth}{self.valkey_host}:{self.valkey_port}/{self.valkey_db}"
        if self.valkey_scheme == "rediss":
            base += "?ssl_cert_reqs=CERT_NONE"
        return base

    # Security
    jwt_secret_key: str = Field(default="123")
    algorithm: str = Field(default="HS256")
    access_token_expire_hour: int = Field(default=24)

    remember_me_expire_day: int = Field(default=30)

    # Frontend origin — used to build email links (e.g. password reset URL).
    # Override via FRONTEND_URL env var in production.
    frontend_url: str = Field(default="http://localhost:5173")

    # Fundamentals (Financial Modeling Prep)
    # `fundamentals_source` chooses which fetcher CLI/Celery tasks route to.
    # Default "fmp" — yfinance is kept for dev/smoke tests only; Yahoo exposes
    # ~5 recent quarters, insufficient for any real backtest window.
    fmp_api_key: str = Field(default="")
    fundamentals_source: str = Field(default="fmp")
    # OHLC daily-bar source. Default "fmp" because yfinance has proven
    # rate-limit flaky; kept as a fallback via `--source yfinance` on the
    # CLI and via `OHLC_SOURCE=yfinance` in the environment.
    ohlc_source: str = Field(default="fmp")

    # email
    resend_api_key: str = Field(default="")
    resend_from_email: str = Field(default="onboarding@resend.dev")
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=456)
    smtp_user: str = Field(default="test@gmail.com")
    smtp_password: str = Field(default="12345")

    allowed_origin: list[str] = Field(default=["http://localhost:5173", "http://localhost:5174"])

    allowed_methods: list[str] = Field(
        default_factory=lambda: [method.value for method in RequestEnum]
    )

    allowed_headers: list[str] = Field(default=["*"])

    # Header fields
    max_body_log_size: int = Field(default=1024 * 1024)

    sensitive_headers: list[str] = Field(
        default=[
            "password",
            "token",
            "access_token",
            "refresh_token",
            "credit_card",
            "cvv",
            "ssn",
            "secret",
        ]
    )
    sensitive_body_fields: list[str] = Field(
        default=[
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
            "x-auth-token",
            "proxy-authorization",
        ]
    )
