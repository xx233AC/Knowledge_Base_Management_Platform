from pathlib import Path
from functools import lru_cache
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", case_sensitive=False,
                                      populate_by_name=True)
    app_name: str = "知识库管理平台"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://kb_admin:CHANGE_ME@127.0.0.1:15432/knowledge_base"
    jwt_secret: SecretStr
    jwt_ttl_seconds: int = 28800
    encryption_key: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    redis_url: SecretStr = SecretStr("redis://:CHANGE_ME@127.0.0.1:6379/0")
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: SecretStr = SecretStr("")
    minio_secret_key: SecretStr = SecretStr("")
    minio_secure: bool = False
    minio_bucket: str = "kb-documents"
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: SecretStr = SecretStr("")
    milvus_collection: str = "kb_chunks_bge_m3_v1"
    embedding_model_path: str = r"D:\ai_models\modelscope_cache\models\models\BAAI--bge-m3"
    embedding_dimension: int = 1024
    embedding_device: str = "cpu"
    embedding_dtype: str = "float32"
    embedding_batch_size: int = 4
    embedding_max_tokens: int = 1024
    chunk_size: int = 800
    chunk_overlap: int = 100
    upload_max_bytes: int = 50 * 1024 * 1024
    upload_max_files: int = 30
    retrieval_top_k: int = 12
    retrieval_min_score: float = 0.35
    faq_min_frequency: int = 3
    faq_semantic_threshold: float = 0.92
    worker_auto_start: bool = True
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 1800
    worker_max_attempts: int = 3
    import_wait_timeout_seconds: int = 120
    mining_interval_seconds: int = 3600
    llm_enabled: bool = False
    llm_base_url: str = "https://api.deepseek.com"
    # Prefixed so an unrelated LLM_API_KEY exported by other tools cannot silently override this app.
    llm_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="KB_LLM_API_KEY")
    llm_model: str = "deepseek-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048
    llm_timeout_seconds: int = 120
    llm_thinking_enabled: bool = False
    llm_reasoning_effort: str = "high"
    llm_vision_enabled: bool = False
    llm_vision_model: str = "deepseek-flash"
    llm_vision_max_images: int = 100
    llm_answer_max_images: int = 3
    llm_answer_image_max_bytes: int = 5 * 1024 * 1024
    mineru_enabled: bool = False
    mineru_base_url: str = "https://mineru.net/api/v4"
    mineru_api_key: SecretStr = SecretStr("")
    mineru_model_version: str = "pipeline"
    mineru_enable_ocr: bool = True
    mineru_language: str = "ch"
    mineru_poll_seconds: float = 5.0
    mineru_timeout_seconds: int = 900
    mineru_login_url: str = ""
    mineru_username: str = ""
    mineru_password: SecretStr = SecretStr("")
    mineru_callback_url: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def strong_secret(cls, value):
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET 至少需要 32 个字符，请运行 python scripts/init_env.py")
        return value

    @field_validator("embedding_dimension")
    @classmethod
    def dimension(cls, value):
        if value != 1024:
            raise ValueError("本地 bge-m3 使用 1024 维向量，请为其他模型创建独立集合")
        return value

    @field_validator("embedding_dtype")
    @classmethod
    def dtype(cls, value):
        if value not in {"float32", "float16"}:
            raise ValueError("EMBEDDING_DTYPE 只支持 float32 或 float16")
        return value


@lru_cache
def get_settings():
    return Settings()
