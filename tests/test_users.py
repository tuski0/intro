import pytest
from fastapi.testclient import TestClient

from services.user_service.app.main import create_app


def test_user_registration_and_lookup(user_client):
    response = user_client.post("/users", json={"name": " 홍길동 ", "email": "Hong@example.com"})
    assert response.status_code == 201
    user = response.json()
    assert user["name"] == "홍길동"
    assert user["email"] == "hong@example.com"
    assert user["created_at"].endswith(("Z", "+00:00"))
    assert user_client.get(f"/users/{user['id']}").json() == user
    assert user_client.get("/users").json() == [user]


def test_duplicate_email_is_rejected_case_insensitively(user_client):
    user_client.post("/users", json={"name": "첫 번째", "email": "hong@example.com"})
    response = user_client.post("/users", json={"name": "두 번째", "email": "HONG@example.com"})
    assert response.status_code == 409
    assert len(user_client.get("/users").json()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "email": "hong@example.com"},
        {"name": "홍길동", "email": "invalid-email"},
        {"name": "홍길동"},
        {"name": "홍길동", "email": "hong@example.com", "id": 1},
    ],
)
def test_invalid_user_input_is_rejected(user_client, payload):
    assert user_client.post("/users", json=payload).status_code == 422
    assert user_client.get("/users").json() == []


def test_user_pagination_and_missing_user(user_client):
    for index in range(3):
        user_client.post("/users", json={"name": str(index), "email": f"user{index}@example.com"})
    result = user_client.get("/users?offset=1&limit=1").json()
    assert [user["name"] for user in result] == ["1"]
    assert user_client.get("/users/9999").status_code == 404
    assert user_client.get("/users/0").status_code == 422
    assert user_client.get("/users?limit=101").status_code == 422
    assert user_client.get("/users?offset=-1").status_code == 422


def test_users_survive_app_restart(tmp_path):
    database_path = tmp_path / "persistent-users.db"
    with TestClient(create_app(database_path)) as first:
        user = first.post("/users", json={"name": "홍길동", "email": "hong@example.com"}).json()
    with TestClient(create_app(database_path)) as restarted:
        assert restarted.get(f"/users/{user['id']}").json() == user
        assert restarted.get("/health").json() == {"status": "ok", "service": "user-service"}
