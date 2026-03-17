from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    ALGORITHM: str
    ACCESS_SECRET_KEY: str
    REFRESH_SECRET_KEY: str

    class Config:
        env_file = ".env"


settings = Settings()
