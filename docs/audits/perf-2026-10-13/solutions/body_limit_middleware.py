"""Tope global de tamaño de cuerpo como middleware ASGI puro (hallazgo N13 del informe).

Hoy solo algunos endpoints acotan el cuerpo (`api/webhook_payloads.py`: webhooks 2 MB; imágenes
base64 5–7 MB por campo). Cualquier otra ruta lee el cuerpo entero en memoria. Este middleware
responde 413 antes de que FastAPI lo parsee: por `Content-Length` declarado y, para cuerpos sin
longitud (chunked), contando bytes a medida que llegan. Es ASGI puro (no `BaseHTTPMiddleware`),
así que no agrega un hilo ni copia el cuerpo.

Montaje en `app/main.py` (después de los middlewares existentes):
    app.add_middleware(BodyLimitMiddleware, default_limit=1 * 1024 * 1024,
                       overrides={"/api/payment-proofs": 8 * 1024 * 1024,
                                  "/api/company-documents/upload": 8 * 1024 * 1024})

Autoprueba:  python docs/audits/perf-2026-10-13/solutions/body_limit_middleware.py
"""
from __future__ import annotations

import json


class _TooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app, default_limit: int, overrides: dict[str, int] | None = None):
        self.app = app
        self.default_limit = default_limit
        self.overrides = overrides or {}

    def _limit_for(self, path: str) -> int:
        for prefix, limit in self.overrides.items():
            if path.startswith(prefix):
                return limit
        return self.default_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        limit = self._limit_for(scope["path"])
        headers = dict(scope["headers"])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    return await self._reject(send, limit)
            except ValueError:
                return await self._reject(send, limit, status=400, detail="Content-Length inválido")

        received = 0
        started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send, limit: int, status: int = 413, detail: str | None = None):
        body = json.dumps({"detail": detail or f"Cuerpo demasiado grande (máximo {limit} bytes)"}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


if __name__ == "__main__":
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, default_limit=1000, overrides={"/big": 100_000})

    @app.post("/small")
    async def small(request: Request):
        return {"n": len(await request.body())}

    @app.post("/big")
    async def big(request: Request):
        return {"n": len(await request.body())}

    c = TestClient(app)
    assert c.post("/small", content=b"x" * 900).json() == {"n": 900}
    r = c.post("/small", content=b"x" * 1500)
    assert r.status_code == 413, r.status_code
    assert c.post("/big", content=b"x" * 50_000).json() == {"n": 50_000}
    assert c.post("/big", content=b"x" * 150_000).status_code == 413
    # sin Content-Length (chunked): se cuenta lo recibido
    r = c.post("/small", content=(b"x" * 400 for _ in range(10)))
    assert r.status_code == 413, r.status_code
    assert c.get("/docs").status_code == 200
    print("ok · 413 por Content-Length y por conteo en cuerpos chunked; GET intacto")
