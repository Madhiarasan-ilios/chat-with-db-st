"""
Centralised configuration.

Secret resolution order for each value:
  1. GCP Secret Manager  (when GCP_PROJECT_ID is set)
  2. Environment variable / .env file
  3. Hard-coded default  (dev only – never ship secrets here)
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Optional GCP Secret Manager helper
# ---------------------------------------------------------------------------

def _fetch_gcp_secret(project_id: str, secret_name: str, version: str = "latest") -> Optional[str]:
    """Return the secret value from GCP Secret Manager, or None on any error."""
    try:
        from google.cloud import secretmanager  # type: ignore

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8").strip()
    except Exception as exc:
        logger.debug("GCP Secret Manager unavailable for %s: %s", secret_name, exc)
        return None


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── GCP ───────────────────────────────────────────────────────────────────
    GCP_PROJECT_ID: str = ""

    # ── Database ──────────────────────────────────────────────────────────────
    DB_HOST: str = "12.25.11.2"
    DB_PORT: int = 3306
    DB_NAME: str = "stm_db"
    DB_USER: str = "app_user"
    DB_PASS: str = ""

    # ── AWS / Bedrock ─────────────────────────────────────────────────────────
    AWS_REGION: str = "ap-south-1"
    BEDROCK_MODEL_ID: str = "global.qwen.qwen3-235b-a22b-2507-v1:0"

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    def _resolve(self, env_value: str, secret_name: str) -> str:
        """
        If a GCP project is configured and the env value looks like a placeholder,
        try fetching the real value from Secret Manager.
        """
        if self.GCP_PROJECT_ID and (not env_value or env_value.startswith("sm://")):
            gcp_val = _fetch_gcp_secret(self.GCP_PROJECT_ID, secret_name)
            if gcp_val:
                return gcp_val
        return env_value

    def resolved_db_pass(self) -> str:
        return self._resolve(self.DB_PASS, "DB_PASS")

    def resolved_jwt_secret(self) -> str:
        return self._resolve(self.JWT_SECRET_KEY, "JWT_SECRET_KEY")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.resolved_db_pass()}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Module-level shortcut used by the rest of the codebase
settings: Settings = get_settings()
