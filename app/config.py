from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/db/bot.db"
    timezone: str = "Asia/Bangkok"
    lesson_hour: int = 9
    lesson_minute: int = 0
    new_words_per_day: int = 10
    admin_username: str = "maxim_beloprosov"
    admin_user_id: int = 0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
