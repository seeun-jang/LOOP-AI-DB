from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = Field(default=60, ge=1, le=1440)
    ai_provider: Literal['demo', 'gemini'] = 'demo'
    gemini_api_key: str = ''
    gemini_model: str = ''
    ai_timeout_seconds: int = Field(default=30, ge=1, le=120)

    @model_validator(mode='after')
    def valid_configuration(self):
        if 'REPLACE_WITH' in self.jwt_secret or 'CHANGE_ME' in self.database_url:
            raise ValueError('Run python scripts/setup_env.py before starting.')
        if not self.database_url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('PostgreSQL DATABASE_URL is required.')
        if self.ai_provider == 'gemini' and (not self.gemini_api_key or not self.gemini_model):
            raise ValueError('Gemini requires GEMINI_API_KEY and GEMINI_MODEL.')
        return self
