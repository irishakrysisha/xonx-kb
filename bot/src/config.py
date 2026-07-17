"""Configuration for the X-ON-X KB bot.

Every setting comes from an environment variable (or a local .env file).
BOT_TOKEN is required; everything else has a sensible default.
"""
import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Live _Inbox folder of the X-ON-X Knowledge Base (see ../kb_config.json)
DEFAULT_INBOX_FOLDER = "18qyoKX44Nk4UZK5To25P3DyiLJwUz2kH"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")                      # from @BotFather
    inbox_folder_id: str = Field(default=DEFAULT_INBOX_FOLDER, alias="KB_INBOX_FOLDER_ID")
    # OAuth user-token JSON inline; empty -> fall back to ~/.claude-sheets/token.json
    google_token_json: str = Field(default="", alias="GOOGLE_TOKEN_JSON")
    # Comma-separated Telegram usernames allowed to drop files ("@" optional,
    # case-insensitive). Empty = nobody gets in. Kept as a plain str: a List
    # field makes EnvSettingsSource JSON-parse the raw value and crash before
    # any validator runs (same gotcha the sales bot hit).
    allowed_usernames_raw: str = Field(default="", alias="ALLOWED_USERNAMES")

    @property
    def allowed_usernames(self) -> List[str]:
        return [u.strip().lstrip("@").lower()
                for u in self.allowed_usernames_raw.split(",") if u.strip()]

    def is_allowed(self, username: str | None) -> bool:
        if not username:
            return False
        return username.lstrip("@").lower() in self.allowed_usernames


def load_settings() -> Settings:
    return Settings()
