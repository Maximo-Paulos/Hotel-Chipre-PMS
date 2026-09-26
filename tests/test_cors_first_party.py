"""The marketing site's own origin must not depend on an env var being set.

hotels-pms.com calls api.hotels-pms.com for pricing and lead capture. When
CORS_ORIGINS was the only source of allowed origins, a service missing that
variable answered the preflight with 400 and no Access-Control-Allow-Origin,
which silently broke the pricing section and the access form in the browser
while every server-side check still passed.

These assertions are about the middleware configuration, so they use routes
that do not need a database.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIRST_PARTY = ["https://hotels-pms.com", "https://www.hotels-pms.com", "https://app.hotels-pms.com"]
PUBLIC_MARKETING_ROUTES = ["/api/public/pricing", "/api/public/leads"]


@pytest.mark.parametrize("origin", FIRST_PARTY)
def test_a_simple_request_from_our_own_hosts_is_readable(origin):
    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", FIRST_PARTY)
@pytest.mark.parametrize("path", PUBLIC_MARKETING_ROUTES)
def test_marketing_routes_survive_preflight_from_our_own_hosts(path, origin):
    response = client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_an_unrelated_origin_is_still_refused():
    response = client.get("/health", headers={"Origin": "https://not-ours.example"})

    assert response.headers.get("access-control-allow-origin") is None


def test_an_arbitrary_vercel_preview_is_not_implicitly_trusted():
    response = client.get("/health", headers={"Origin": "https://untrusted-preview-74291.vercel.app"})

    assert response.headers.get("access-control-allow-origin") is None
