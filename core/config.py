from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    frontend_url: str = "http://localhost:3000"

    refresh_token_cookie_name: str = "refresh_token"
    cookie_secure: bool = True         # Set COOKIE_SECURE=false in .env for local dev
    cookie_samesite: str = "lax"       # "strict" is safest, "lax" for dev
    cookie_domain: str | None = None

    aws_access_key_id: str
    aws_secret_access_key: str
    s3_bucket_name: str
    s3_region: str

    debug: bool = False                # ← new. Set DEBUG=true in .env for dev


    class Config:
        env_file = ".env"

settings = Settings()
