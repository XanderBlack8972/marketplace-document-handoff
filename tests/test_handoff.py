from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from marketplace_handoff.infrai_pdf import InfraiPdfClient
from marketplace_handoff.service import app, get_pdf_client


def test_handoff_keeps_storefront_assets_before_buyer_updates() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read().decode()
        captured["idempotency_key"] = request.headers["Idempotency-Key"]
        return httpx.Response(200, json={"ok": True, "data": {"job_id": "job_42"}, "error": None, "metadata": {}})

    pdf_client = InfraiPdfClient("test-key", transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_pdf_client] = lambda: pdf_client
    try:
        response = TestClient(app).post(
            "/orders/handoff",
            json={
                "order_id": "order-1048",
                "seller_assets": ["manual.pdf", "warranty.pdf"],
                "buyer_updates": ["gift-note.pdf"],
            },
        )
    finally:
        app.dependency_overrides.clear()
        pdf_client.close()

    assert response.status_code == 200
    assert response.json()["document_count"] == 3
    assert captured["payload"] == '{"inputs":["manual.pdf","warranty.pdf","gift-note.pdf"]}'
    assert captured["idempotency_key"] == "order-handoff:order-1048"


def test_merge_retries_rate_limit_after_reading_envelope() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"ok": False, "data": None, "error": {"code": "RATE_LIMITED"}, "metadata": {}})
        return httpx.Response(200, json={"ok": True, "data": {"job_id": "job_43"}, "error": None, "metadata": {}})

    client = InfraiPdfClient("test-key", transport=httpx.MockTransport(handler), sleep=delays.append)
    try:
        result = client.merge(["manual.pdf"], "order-handoff:order-1049")
    finally:
        client.close()

    assert result == {"job_id": "job_43"}
    assert attempts == 2
    assert delays == [1.0]

