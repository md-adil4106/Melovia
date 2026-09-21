"""Application configuration using Pydantic Settings.

Categories:
- DATABASE: Connection parameters and pooling
- LLM: Model selection, temperature, token limits
- PLATFORM: Music provider adapters and OAuth credentials
- CATALOG: Vector bundle path, versioning, and checksums
- ENV: Runtime environment, debugging, host, port, CORS
"""

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str = Field(
        default="postgresql+psycopg://melovia_user:melovia_password@localhost:5432/melovia_db",
        description="PostgreSQL connection string (PostgreSQL 16, no pgvector)",
    )
    pool_size: int = Field(default=10, description="Database connection pool size")
    max_overflow: int = Field(default=20, description="Maximum overflow connections")
    pool_timeout: int = Field(default=30, description="Connection acquisition timeout in seconds")


class LLMSettings(BaseModel):
    provider: str = Field(default="openai", description="LLM provider name")
    model: str = Field(default="gpt-4o-mini", description="LLM model identifier")
    api_key: str = Field(default="", description="Provider API key")
    temperature: float = Field(
        default=0.2, description="Sampling temperature for structured constraints"
    )
    max_tokens: int = Field(default=1024, description="Maximum completion tokens")
    explain_llm_polish: bool = Field(
        default=False, description="Enable verified LLM polish on explanations"
    )


class PlatformSettings(BaseModel):
    default_platform: str = Field(default="spotify", description="Default platform adapter")
    spotify_client_id: str = Field(default="", description="Spotify Developer API client ID")
    spotify_client_secret: str = Field(
        default="", description="Spotify Developer API client secret"
    )
    spotify_redirect_uri: str = Field(
        default="http://127.0.0.1:8000/export/spotify/callback",
        description="Spotify OAuth PKCE callback URL (requires 127.0.0.1, not localhost)",
    )
    client_id: str = Field(default="", description="Platform API client ID (legacy)")
    client_secret: str = Field(default="", description="Platform API client secret (legacy)")
    redirect_uri: str = Field(
        default="http://127.0.0.1:8000/export/spotify/callback",
        description="OAuth callback URL (legacy)",
    )


class CatalogSettings(BaseModel):
    bundle_path: str = Field(
        default="data/bundles/v1", description="Filesystem path to vector bundle"
    )
    version: str = Field(default="v1", description="Active catalog bundle version")
    embedding_dim: int = Field(default=128, description="High-dimensional embedding size")
    checksum: str = Field(default="", description="Expected checksum of bundle manifest")


class EnvSettings(BaseModel):
    env: str = Field(
        default="development", description="Environment mode (development, test, production)"
    )
    debug: bool = Field(default=True, description="Enable debug logging and OpenAPI docs")
    api_host: str = Field(default="0.0.0.0", description="API bind host")
    api_port: int = Field(default=8000, description="API bind port")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        description="List of allowed CORS origins",
    )


class Settings(BaseSettings):
    """Unified application settings with categorized access."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ENV
    ENV: str = Field(default="development", validation_alias="ENV")
    DEBUG: bool = Field(default=True, validation_alias="DEBUG")
    API_HOST: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    API_PORT: int = Field(default=8000, validation_alias="API_PORT")
    API_CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias="API_CORS_ORIGINS",
    )

    # DATABASE
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://melovia_user:melovia_password@localhost:5432/melovia_db",
        validation_alias="DATABASE_URL",
    )
    DB_POOL_SIZE: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")

    # LLM
    LLM_PROVIDER: str = Field(default="openai", validation_alias="LLM_PROVIDER")
    LLM_MODEL: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    LLM_API_KEY: str = Field(default="", validation_alias="LLM_API_KEY")
    LLM_TEMPERATURE: float = Field(default=0.2, validation_alias="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=1024, validation_alias="LLM_MAX_TOKENS")
    EXPLAIN_LLM_POLISH: bool = Field(default=False, validation_alias="EXPLAIN_LLM_POLISH")

    # PLATFORM
    PLATFORM_DEFAULT: str = Field(default="spotify", validation_alias="PLATFORM_DEFAULT")
    PLATFORM_CLIENT_ID: str = Field(default="", validation_alias="PLATFORM_CLIENT_ID")
    PLATFORM_CLIENT_SECRET: str = Field(default="", validation_alias="PLATFORM_CLIENT_SECRET")
    PLATFORM_REDIRECT_URI: str = Field(
        default="http://127.0.0.1:8000/export/spotify/callback",
        validation_alias="PLATFORM_REDIRECT_URI",
    )
    SPOTIFY_CLIENT_ID: str = Field(default="", validation_alias="SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET: str = Field(default="", validation_alias="SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI: str = Field(
        default="http://127.0.0.1:8000/export/spotify/callback",
        validation_alias="SPOTIFY_REDIRECT_URI",
    )

    # CATALOG
    CATALOG_BUNDLE_PATH: str = Field(
        default="data/bundles/v1", validation_alias="CATALOG_BUNDLE_PATH"
    )
    CATALOG_VERSION: str = Field(default="v1", validation_alias="CATALOG_VERSION")
    CATALOG_EMBEDDING_DIM: int = Field(default=128, validation_alias="CATALOG_EMBEDDING_DIM")
    CATALOG_CHECKSUM: str = Field(default="", validation_alias="CATALOG_CHECKSUM")
    # STUDY MODE
    STUDY_ADMIN_TOKEN: str = Field(
        default="melovia-study-secret-token", validation_alias="STUDY_ADMIN_TOKEN"
    )

    @property
    def DATABASE(self) -> DatabaseSettings:
        return DatabaseSettings(
            url=self.DATABASE_URL,
            pool_size=self.DB_POOL_SIZE,
            max_overflow=self.DB_MAX_OVERFLOW,
            pool_timeout=self.DB_POOL_TIMEOUT,
        )

    @property
    def LLM(self) -> LLMSettings:
        return LLMSettings(
            provider=self.LLM_PROVIDER,
            model=self.LLM_MODEL,
            api_key=self.LLM_API_KEY,
            temperature=self.LLM_TEMPERATURE,
            max_tokens=self.LLM_MAX_TOKENS,
            explain_llm_polish=self.EXPLAIN_LLM_POLISH,
        )

    @property
    def PLATFORM(self) -> PlatformSettings:
        cid = self.SPOTIFY_CLIENT_ID or self.PLATFORM_CLIENT_ID
        csec = self.SPOTIFY_CLIENT_SECRET or self.PLATFORM_CLIENT_SECRET
        redir = self.SPOTIFY_REDIRECT_URI or self.PLATFORM_REDIRECT_URI
        return PlatformSettings(
            default_platform=self.PLATFORM_DEFAULT,
            spotify_client_id=cid,
            spotify_client_secret=csec,
            spotify_redirect_uri=redir,
            client_id=cid,
            client_secret=csec,
            redirect_uri=redir,
        )

    @property
    def CATALOG(self) -> CatalogSettings:
        return CatalogSettings(
            bundle_path=self.CATALOG_BUNDLE_PATH,
            version=self.CATALOG_VERSION,
            embedding_dim=self.CATALOG_EMBEDDING_DIM,
            checksum=self.CATALOG_CHECKSUM,
        )

    @property
    def ENV_CATEGORY(self) -> EnvSettings:
        return EnvSettings(
            env=self.ENV,
            debug=self.DEBUG,
            api_host=self.API_HOST,
            api_port=self.API_PORT,
            cors_origins=self.API_CORS_ORIGINS,
        )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
