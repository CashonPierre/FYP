# STL

# External
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field

# Custom
from common.enums import RequestEnum


class Settings(BaseSettings):
    """Config for the server"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8"
    )
    # Server
    host: str = Field(default="localhost")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # Database
    database: str = Field(default="appdb")
    database_password: str = Field(default="dbadmin")
    database_username: str = Field(default="dbuser")
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5431)
    database_driver: str = Field(default="postgresql+psycopg2")

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"{self.database_driver}://"
            f"{self.database_username}:"
            f"{self.database_password}@"
            f"{self.database_host}:"
            f"{self.database_port}/"
            f"{self.database}"
        )

    # caching
    valkey_scheme: str = Field(default="redit")
    valkey_host: str = Field(default="localhost")
    valkey_port: int = Field(default=6379)
    valkey_db: int = Field(default=0)

    @computed_field
    @property
    def valkey_url(self) -> str:
        return f"{self.valkey_scheme}://{self.valkey_host}:{self.valkey_port}/{self.valkey_db}"

    # Security
    jwt_secret_key: str = Field(default="123")
    algorithm: str = Field(default="HS256")
    access_token_expire_hour: int = Field(default=24)

    remember_me_expire_day: int = Field(default=30)

    # email
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=456)
    smtp_user: str = Field(default="test@gmail.com")
    smtp_password: str = Field(default="12345")

    allowed_origin: list[str] = Field(default=["http://localhost:5173"])

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
