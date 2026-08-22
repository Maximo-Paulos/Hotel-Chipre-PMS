"""Regression: provider-supplied OAuth error text must not break out of the
inline <script> block in the popup callback page.

`message` on the error path is built from the OAuth provider's
`error_description` query param (see integrations.accept-error handling),
so it is attacker-influenceable by anyone who can redirect the popup to our
callback URL with a crafted query string.
"""

from __future__ import annotations

from app.api.integrations import _oauth_callback_page


def test_oauth_callback_page_escapes_script_close_in_message():
    malicious = "</script><script>window.top.location='https://evil.example';</script>"

    response = _oauth_callback_page(
        status="error",
        message=malicious,
        provider="mercadopago",
        integration_id=1,
        web_origin="https://app.hotels-pms.com",
    )

    body = response.body.decode("utf-8")

    assert "</script><script>window.top.location" not in body
    assert "<\\/script><script>window.top.location" in body


def test_oauth_callback_page_payload_is_valid_json_embed():
    response = _oauth_callback_page(
        status="ok",
        message="It's done — 100% \"connected\"",
        provider="p'rovider",
        integration_id=7,
        web_origin="https://app.hotels-pms.com",
    )

    body = response.body.decode("utf-8")

    assert "var payload = {" in body
    assert '"integrationId": 7' in body
