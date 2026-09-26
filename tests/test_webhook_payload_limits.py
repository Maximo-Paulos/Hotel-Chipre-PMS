import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.webhook_payloads import read_bounded_body


def _request(chunks: list[bytes], *, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    messages = [
        {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
        for index, chunk in enumerate(chunks)
    ]
    receive_count = 0

    async def receive():
        nonlocal receive_count
        receive_count += 1
        if receive_count > len(messages):
            return {"type": "http.disconnect"}
        return messages[receive_count - 1]

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhook",
        "headers": headers or [],
    }
    return Request(scope, receive)


def test_rejects_oversized_content_length_before_reading_body():
    request = _request([b"should-not-read"], headers=[(b"content-length", b"11")])

    with pytest.raises(HTTPException) as raised:
        asyncio.run(read_bounded_body(request, max_bytes=10))

    assert raised.value.status_code == 413


def test_rejects_chunked_body_that_exceeds_limit():
    request = _request([b"1234", b"5678", b"90"])

    with pytest.raises(HTTPException) as raised:
        asyncio.run(read_bounded_body(request, max_bytes=9))

    assert raised.value.status_code == 413


def test_accepts_body_at_exact_limit():
    request = _request([b"1234", b"5678"])

    assert asyncio.run(read_bounded_body(request, max_bytes=8)) == b"12345678"


def test_rejects_malformed_content_length():
    request = _request([], headers=[(b"content-length", b"many")])

    with pytest.raises(HTTPException) as raised:
        asyncio.run(read_bounded_body(request, max_bytes=8))

    assert raised.value.status_code == 400
