import httpx
import pytest
from fastapi.testclient import TestClient

from services.order_service.app.main import create_app as create_order_app
from services.order_service.app.main import get_user_client
from services.user_service.app.main import create_app as create_user_app


@pytest.fixture
def user_client(tmp_path):
    with TestClient(create_user_app(tmp_path / "users.db")) as client:
        yield client


@pytest.fixture
def order_client(tmp_path, user_client):
    app = create_order_app(tmp_path / "orders.db")

    async def user_api():
        # 실제 사용자 FastAPI 앱에 HTTP 요청을 전달합니다. DB 접근을 공유하지 않습니다.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=user_client.app),
            base_url="http://user-service",
        ) as client:
            yield client

    app.dependency_overrides[get_user_client] = user_api
    with TestClient(app) as client:
        yield client
