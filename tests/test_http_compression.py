import gzip

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient


def test_application_compresses_large_json_responses():
    from app.main import app

    client = TestClient(app)
    with client.stream(
        "GET",
        "/openapi.json",
        headers={"accept-encoding": "gzip"},
    ) as response:
        raw_body = b"".join(response.iter_raw())
        response_headers = response.headers
        status_code = response.status_code

    assert status_code == 200
    assert response_headers.get("content-encoding") == "gzip"
    assert len(raw_body) < len(gzip.decompress(raw_body))


def test_gzip_middleware_leaves_server_sent_events_uncompressed():
    app = FastAPI()
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=1)

    @app.get("/events")
    async def events():
        async def stream():
            yield f"data: {'x' * 2048}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    response = TestClient(app).get(
        "/events",
        headers={"accept-encoding": "gzip"},
    )

    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert len(response.content) > 1024
