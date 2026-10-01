import httpx
import pytest
from fastapi.testclient import TestClient

from services.order_service.app.main import create_app, get_user_client


ORDER = {"user_id": 1, "product_name": "파이썬 교재", "quantity": 2, "unit_price": 15000}


def test_order_creation_uses_user_service(user_client, order_client):
    user = user_client.post("/users", json={"name": "홍길동", "email": "hong@example.com"}).json()
    response = order_client.post("/orders", json={**ORDER, "user_id": user["id"]})
    assert response.status_code == 201
    order = response.json()
    assert order["total_price"] == 30000
    assert order["user_id"] == user["id"]
    assert order_client.get(f"/orders/{order['id']}").json() == order
    assert order_client.get(f"/orders?user_id={user['id']}").json() == [order]
    assert order_client.get("/orders?user_id=9999").json() == []


def test_nonexistent_user_cannot_place_order(order_client):
    assert order_client.post("/orders", json=ORDER).status_code == 404
    assert order_client.get("/orders").json() == []


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"quantity": 1001},
        {"quantity": True},
        {"unit_price": -1},
        {"unit_price": 1.5},
        {"unit_price": 1_000_000_001},
        {"user_id": 0},
        {"product_name": "   "},
        {"total_price": 1},
    ],
)
def test_invalid_order_is_rejected(order_client, changes):
    assert order_client.post("/orders", json={**ORDER, **changes}).status_code == 422
    assert order_client.get("/orders").json() == []


def test_order_pagination_and_missing_order(user_client, order_client):
    user_client.post("/users", json={"name": "홍길동", "email": "hong@example.com"})
    for quantity in range(1, 4):
        assert order_client.post("/orders", json={**ORDER, "quantity": quantity}).status_code == 201
    assert [order["quantity"] for order in order_client.get("/orders?offset=1&limit=1").json()] == [2]
    assert order_client.get("/orders/9999").status_code == 404
    assert order_client.get("/orders/0").status_code == 422
    assert order_client.get("/orders?limit=101").status_code == 422
    assert order_client.get("/orders?user_id=0").status_code == 422


@pytest.mark.parametrize("failure", ["timeout", "connection", "server", "unexpected"])
def test_user_service_failure_does_not_create_order(tmp_path, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if failure == "connection":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(500 if failure == "server" else 302)

    async def unavailable_user_api():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://user-service"
        ) as client:
            yield client

    app = create_app(tmp_path / "orders.db")
    app.dependency_overrides[get_user_client] = unavailable_user_api
    with TestClient(app) as client:
        assert client.post("/orders", json=ORDER).status_code == 503
        assert client.get("/orders").json() == []
        assert client.get("/health").status_code == 200


def test_existing_orders_are_readable_after_restart_without_user_service(tmp_path, order_client, user_client):
    user_client.post("/users", json={"name": "홍길동", "email": "hong@example.com"})
    order = order_client.post("/orders", json=ORDER).json()
    # 같은 SQLite 파일을 새 앱으로 다시 엽니다. 조회에는 사용자 서버가 필요 없습니다.
    with TestClient(create_app(tmp_path / "orders.db", "http://127.0.0.1:1")) as restarted:
        assert restarted.get(f"/orders/{order['id']}").json() == order
        assert restarted.get("/health").json() == {"status": "ok", "service": "order-service"}
