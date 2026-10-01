import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query, status

from .database import Database
from .schemas import UserCreate, UserRead


def create_app(database_path: str | Path | None = None) -> FastAPI:
    database = Database(database_path or os.getenv("DATABASE_PATH", "data/users.db"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        yield

    app = FastAPI(
        title="사용자 서비스",
        description="사용자를 등록하고 조회하는 독립적인 FastAPI 서비스입니다.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["상태"], summary="서버와 DB 상태 확인")
    def health():
        try:
            database.check()
        except sqlite3.Error as exc:
            raise HTTPException(503, "사용자 DB를 사용할 수 없습니다.") from exc
        return {"status": "ok", "service": "user-service"}

    @app.post(
        "/users",
        response_model=UserRead,
        status_code=status.HTTP_201_CREATED,
        tags=["사용자"],
        summary="사용자 등록",
        responses={409: {"description": "이미 등록된 이메일"}},
    )
    def create_user(payload: UserCreate):
        # 이 예제에서는 이메일의 대소문자를 구분하지 않습니다.
        try:
            return database.create_user(
                name=payload.name,
                email=str(payload.email).lower(),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "이미 등록된 이메일입니다.") from exc

    @app.get("/users", response_model=list[UserRead], tags=["사용자"], summary="사용자 목록")
    def list_users(
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ):
        return database.list_users(offset, limit)

    @app.get(
        "/users/{user_id}",
        response_model=UserRead,
        tags=["사용자"],
        summary="사용자 단건 조회",
        responses={404: {"description": "사용자가 존재하지 않음"}},
    )
    def get_user(user_id: Annotated[int, ApiPath(ge=1)]):
        user = database.get_user(user_id)
        if user is None:
            raise HTTPException(404, "사용자를 찾을 수 없습니다.")
        return user

    return app


app = create_app()
