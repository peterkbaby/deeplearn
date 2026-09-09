from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


from database.db import init_db, close_db
from routers.auth import auth
from routers.oauth import router as oauth_router
from core.config import settings
from services.exceptions import ServiceError
from core.limiter import limiter
from core.storage import init_s3, close_s3



@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(app)
    await init_s3(app)
    yield
    await close_s3(app)
    await close_db(app)

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/")
def read_root():
    return {"god is good"}

app.include_router(auth)
app.include_router(oauth_router)
