from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "sableDreams"
    OPENAI_API_KEY: str
    SECRET_KEY: str = "changeme_use_a_strong_secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    class Config:
        env_file = ".env"


settings = Settings()
