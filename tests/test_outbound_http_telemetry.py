from types import SimpleNamespace

import pytest

from app.services.outbound_http_telemetry import observed_http_call, observed_async_http_call


def test_outbound_http_logs_sizes_and_host_without_url_or_payload(caplog):
    payload = b"private-guest-payload"
    secret_url = "https://provider.example.test/send?token=do-not-log"
    response = SimpleNamespace(
        request=SimpleNamespace(
            url=secret_url,
            headers={"content-length": str(len(payload))},
            body=payload,
        ),
        content=b"provider response",
        status_code=202,
    )

    def fake_sender(url, **kwargs):
        assert url == secret_url
        assert kwargs["json"] == {"message": payload.decode()}
        return response

    with caplog.at_level("INFO", logger="app.services.outbound_http_telemetry"):
        result = observed_http_call(
            "email.provider",
            fake_sender,
            secret_url,
            json={"message": payload.decode()},
        )

    assert result is response
    assert "host=provider.example.test" in caplog.text
    assert f"request_bytes_estimate={len(secret_url.encode()) + len(payload)}" in caplog.text
    assert f"response_body_bytes={len(response.content)}" in caplog.text
    assert "private-guest-payload" not in caplog.text
    assert "do-not-log" not in caplog.text


def test_outbound_http_logs_failed_request_without_sensitive_data(caplog):
    secret_url = "https://provider.example.test/submit?access_token=private"

    def fake_sender(url, **kwargs):
        raise RuntimeError("private guest payload")

    with caplog.at_level("WARNING", logger="app.services.outbound_http_telemetry"):
        with pytest.raises(RuntimeError):
            observed_http_call(
                "payment.provider",
                fake_sender,
                secret_url,
                json={"guest": "private guest payload"},
            )

    assert "host=provider.example.test" in caplog.text
    assert "status=failed" in caplog.text
    assert "private guest payload" not in caplog.text
    assert "access_token" not in caplog.text


def test_outbound_http_supports_method_and_url_sender_signature(caplog):
    url = "https://booking.example.test/availability?hotel_id=private"
    response = SimpleNamespace(
        request=SimpleNamespace(url=url, headers={"content-length": "3"}, body=b"{}"),
        content=b"ok",
        status_code=200,
    )

    def fake_request(method, request_url, **kwargs):
        assert method == "POST"
        assert request_url == url
        return response

    with caplog.at_level("INFO", logger="app.services.outbound_http_telemetry"):
        observed_http_call("booking.connectivity", fake_request, "POST", url, json={"a": 1})

    assert "host=booking.example.test" in caplog.text
    assert "hotel_id=private" not in caplog.text
    assert "request_bytes_estimate=" in caplog.text


@pytest.mark.asyncio
async def test_outbound_async_http_logs_sizes_without_payload(caplog):
    secret_url = "https://fx.example.test/rates"
    response = SimpleNamespace(
        request=SimpleNamespace(
            url=secret_url,
            headers={"content-length": "4"},
            body=b"data",
        ),
        content=b"{}",
        status_code=200,
    )

    async def fake_sender(url, **kwargs):
        return response

    with caplog.at_level("INFO", logger="app.services.outbound_http_telemetry"):
        result = await observed_async_http_call("fx.provider", fake_sender, secret_url)

    assert result is response
    assert "host=fx.example.test" in caplog.text
    assert f"request_bytes_estimate={len(secret_url.encode()) + 4}" in caplog.text
    assert "data" not in caplog.text
