from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    refresh_token_cookie_name: str = "refresh_token"
    cookie_secure: bool = True         # Set COOKIE_SECURE=false in .env for local dev
    cookie_samesite: str = "lax"       # "strict" is safest, "lax" for dev
    cookie_domain: str | None = None  

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    S3_BUCKET_NAME: str
    S3_REGION: str

    debug: bool = False                # ← new. Set DEBUG=true in .env for dev


    class Config:
        env_file = ".env"

settings = Settings()