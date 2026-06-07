from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Guard
    guard_model: str = "protectai/deberta-v3-base-prompt-injection-v2"
    guard_injection_label: str = "INJECTION"
    guard_block_threshold: float = 0.8
    guard_flag_threshold: float = 0.5
    enable_classifier: bool = True

    # Rate limiting (per identifier)
    rate_limit_max: int = 60
    rate_limit_window_seconds: int = 60

    # Comply core API (Phase 2: emit guard events as evidence)
    comply_api_url: str = "http://localhost:8000"

    # RAG
    anthropic_api_key: str = ""
    rag_answer_model: str = "claude-sonnet-4-6"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    catalog_dir: str = "../compliance"
    act_text_path: str = "data/eu_ai_act.txt"
    index_dir: str = "data/index"
    rag_top_k: int = 5

    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
