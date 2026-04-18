from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_repo_dotenv() -> None:
    """Populate os.environ from the repo `.env` so ADK / LiteLLM see GOOGLE_API_KEY etc.

    Pydantic only injects declared `Settings` fields; `llm_runtime` reads `os.environ` directly.
    """
    if load_dotenv is None:
        return
    here = Path(__file__).resolve()
    for i in range(8):
        candidate = here.parents[i] / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


_load_repo_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://prism:prism@localhost:5433/prism"
    prism_repo_root: str | None = None


settings = Settings()
