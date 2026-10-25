import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import AuthError
from app.config import get_settings
from app.db import DatabaseError
from app.lesson_routes import router as lesson_router
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(title="Lesson Studio", version="0.1.0")
_origins = [origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.(web\.app|firebaseapp\.com|vercel\.app)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(lesson_router)


@app.exception_handler(AuthError)
async def auth_error(_, exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(DatabaseError)
async def database_error(_, exc: DatabaseError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": exc.message})
