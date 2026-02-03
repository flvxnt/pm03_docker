from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SED_API"

    SECRET_KEY: str = "CHANGE_ME_SUPER_SECRET"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "sed_db"
    DB_USER: str = "sed_user"
    DB_PASSWORD: str = "sed_password"

    STORAGE_PATH: str = "/data/storage"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
