import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query, Request, status
from starlette.concurrency import run_in_threadpool

from .database import Database
from .schemas import OrderCreate, OrderRead


def get_user_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.user_client


def create_app(
    database_path: str | Path | None = None,
    user_service_url: str | None = None,
) -> FastAPI:
    database = Database(database_path or os.getenv("DATABASE_PATH", "data/orders.db"))
    user_url = user_service_url or os.getenv("USER_SERVICE_URL", "http://127.0.0.1:8001")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        # 연결을 재사용하고, 응답이 없는 서버를 무한정 기다리지 않습니다.
        async with httpx.AsyncClient(base_url=user_url, timeout=3.0, trust_env=False) as client:
            app.state.user_client = client
            yield

    app = FastAPI(
        title="주문 서비스",
        description="사용자 서비스와 HTTP로 통신하며 주문을 생성하고 조회합니다. 금액 단위는 원입니다.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["상태"], summary="서버와 자체 DB 상태 확인")
    def health():
        try:
            database.check()
        except sqlite3.Error as exc:
            raise HTTPException(503, "주문 DB를 사용할 수 없습니다.") from exc
        return {"status": "ok", "service": "order-service"}

    @app.post(
        "/orders",
        response_model=OrderRead,
        status_code=status.HTTP_201_CREATED,
        tags=["주문"],
        summary="사용자 확인 후 주문 생성",
        responses={
            404: {"description": "사용자가 존재하지 않음"},
            503: {"description": "사용자 서비스를 사용할 수 없음"},
        },
    )
    async def create_order(
        payload: OrderCreate,
        client: Annotated[httpx.AsyncClient, Depends(get_user_client)],
    ):
        # 다른 서비스의 DB 대신 공개 API를 사용합니다.
        try:
            response = await client.get(f"/users/{payload.user_id}")
        except httpx.RequestError as exc:
            raise HTTPException(503, "사용자 서비스에 연결할 수 없습니다. 잠시 후 다시 시도하세요.") from exc

        if response.status_code == 404:
            raise HTTPException(404, "주문할 사용자를 찾을 수 없습니다.")
        if response.status_code != 200:
            raise HTTPException(503, "사용자 서비스가 정상 응답을 반환하지 않았습니다.")

        # 동기 SQLite 작업을 별도 스레드에서 수행해 이벤트 루프를 막지 않습니다.
        return await run_in_threadpool(
            database.create_order,
            user_id=payload.user_id,
            product_name=payload.product_name,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/orders", response_model=list[OrderRead], tags=["주문"], summary="주문 목록")
    def list_orders(
        user_id: Annotated[int | None, Query(ge=1)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ):
        return database.list_orders(user_id, offset, limit)

    @app.get(
        "/orders/{order_id}",
        response_model=OrderRead,
        tags=["주문"],
        summary="주문 단건 조회",
        responses={404: {"description": "주문이 존재하지 않음"}},
    )
    def get_order(order_id: Annotated[int, ApiPath(ge=1)]):
        order = database.get_order(order_id)
        if order is None:
            raise HTTPException(404, "주문을 찾을 수 없습니다.")
        return order

    return app


app = create_app()
