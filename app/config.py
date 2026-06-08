"""Application settings loaded from environment / .env."""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")

    # Postgres
    database_url: str = Field(
        default="postgresql+asyncpg://oci:oci@localhost:5433/oci",
        alias="DATABASE_URL",
    )

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="parcels", alias="QDRANT_COLLECTION")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7688", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="ocirealestate", alias="NEO4J_PASSWORD")

    # External data
    attom_api_key: str = Field(default="", alias="ATTOM_API_KEY")
    zillow_api_key: str = Field(default="", alias="ZILLOW_API_KEY")

    # Langfuse — empty values disable tracing (no-op handler).
    # Accept LANGFUSE_HOST or LANGFUSE_BASE_URL (Langfuse's other SDKs use the latter).
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://us.cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


settings = Settings()
