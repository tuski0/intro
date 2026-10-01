"""실행 중인 두 서버를 실제 HTTP로 검사합니다. Python 표준 라이브러리만 사용합니다."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from uuid import uuid4


def request(base_url, path, *, method="GET", payload=None, expected=200):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.status
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        code = exc.code
        body = json.load(exc)
    if code != expected:
        raise RuntimeError(f"{method} {path}: expected {expected}, received {code}: {body}")
    return body


def run(user_url, order_url):
    assert request(user_url, "/health")["status"] == "ok"
    assert request(order_url, "/health")["status"] == "ok"
    email = f"demo-{uuid4().hex}@example.com"
    user = request(user_url, "/users", method="POST", payload={"name": "테스트 사용자", "email": email}, expected=201)
    assert request(user_url, f"/users/{user['id']}") == user
    order_payload = {"user_id": user["id"], "product_name": "파이썬 교재", "quantity": 2, "unit_price": 15000}
    order = request(order_url, "/orders", method="POST", payload=order_payload, expected=201)
    assert order["total_price"] == 30000
    assert request(order_url, f"/orders/{order['id']}") == order
    assert request(order_url, f"/orders?user_id={user['id']}") == [order]
    request(user_url, "/users", method="POST", payload={"name": "중복", "email": email}, expected=409)
    request(order_url, "/orders", method="POST", payload={**order_payload, "quantity": 0}, expected=422)
    print(f"PASS: 사용자 등록·조회, 주문 생성·조회, 금액 계산, 중복 이메일, 입력 검증 (user_id={user['id']}, order_id={order['id']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-url", default="http://127.0.0.1:8001")
    parser.add_argument("--order-url", default="http://127.0.0.1:8002")
    args = parser.parse_args()
    try:
        run(args.user_url, args.order_url)
    except (AssertionError, RuntimeError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
