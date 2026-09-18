import logging

import pytest

from app.main import _InvitationAccessLogFilter


@pytest.mark.parametrize(
    ("method", "request_target"),
    [
        ("GET", "/api/invitations/sensitive-invitation-token"),
        ("POST", "/api/invitations/sensitive-invitation-token/accept"),
        ("POST", "/api/invitations/sensitive-invitation-token/accept/google"),
        ("GET", "/api/invitations/sensitive-invitation-token?debug=1"),
    ],
)
def test_uvicorn_access_log_filter_redacts_invitation_capabilities(method, request_target):
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1", method, request_target, "1.1", 404),
        exc_info=None,
    )

    assert _InvitationAccessLogFilter().filter(record) is True

    rendered = record.getMessage()
    assert "sensitive-invitation-token" not in rendered
    assert "/api/invitations/[REDACTED]" in rendered


@pytest.mark.parametrize(
    ("method", "request_target", "expected"),
    [
        ("POST", "/api/invitations/preview", "/api/invitations/preview"),
        ("POST", "/api/invitations/accept", "/api/invitations/accept"),
        ("POST", "/api/invitations/accept/google", "/api/invitations/accept/google"),
        ("POST", "/api/invitations/accept?token=secret", "/api/invitations/accept"),
        ("GET", "/api/hotels/1?include=rooms", "/api/hotels/1?include=rooms"),
    ],
)
def test_uvicorn_access_log_filter_preserves_static_and_unrelated_routes(method, request_target, expected):
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1", method, request_target, "1.1", 200),
        exc_info=None,
    )

    assert _InvitationAccessLogFilter().filter(record) is True
    assert record.args[2] == expected
    assert "token=secret" not in record.getMessage()


def test_uvicorn_access_logger_redacts_legacy_invitation_route(caplog):
    access_logger = logging.getLogger("uvicorn.access")
    caplog.set_level(logging.INFO, logger="uvicorn.access")
    token = "legacy-invitation-token"

    access_logger.info(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1",
        "POST",
        f"/api/invitations/{token}/accept",
        "1.1",
        404,
    )

    assert token not in caplog.text
    assert "/api/invitations/[REDACTED]" in caplog.text
