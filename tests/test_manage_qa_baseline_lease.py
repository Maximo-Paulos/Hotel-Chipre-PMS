"""Security contract for the dedicated Render QA baseline lease manager."""

from __future__ import annotations

import copy
import io
import json
import urllib.error

import pytest

from scripts.agent_ops.manage_qa_baseline_lease import (
    LEASE_BRANCH_KEY,
    LEASE_ID_KEY,
    LEASE_SHA_KEY,
    LeaseError,
    RenderClient,
    acquire,
    acquire_to_github_output,
    release,
)


SHA = "abcdef1234567890abcdef1234567890abcdef12"
BRANCH = "codex/feature-preview"
QA_SERVICE_ID = "srv-preview"
PRODUCTION_SERVICE_ID = "srv-production"
REPOSITORY = "Maximo-Paulos/Hotel-Chipre-PMS"
LEASE_ID = "4Xg_G8qKL90Bct2WjR6nVmZkAwYx7PSfE3uQ1iNo5Lc"


def env_page(values: dict[str, str]) -> list[dict[str, object]]:
    return [
        {"envVar": {"key": key, "value": value}, "cursor": f"cursor-{index}"}
        for index, (key, value) in enumerate(values.items())
    ]


class FakeRender:
    def __init__(self, *, fail_on: tuple[str, str] | None = None) -> None:
        self.service = {
            "id": QA_SERVICE_ID,
            "repo": f"https://github.com/{REPOSITORY}",
            "branch": BRANCH,
            "type": "web_service",
            "suspended": "not_suspended",
        }
        self.env = {"QA_BASELINE_ONLY": "true", "APP_ENV": "preview"}
        self.calls: list[tuple[str, str, object | None]] = []
        self.fail_on = fail_on

    @property
    def service_path(self) -> str:
        return f"/services/{QA_SERVICE_ID}"

    @property
    def env_path(self) -> str:
        return f"{self.service_path}/env-vars"

    def request(self, method: str, path: str, payload: object | None = None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if self.fail_on == (method, path):
            raise LeaseError("redacted provider failure")
        if method == "GET" and path == self.service_path:
            return copy.deepcopy(self.service)
        if method == "GET" and path == self.env_path:
            return env_page(self.env)
        prefix = f"{self.env_path}/"
        if path.startswith(prefix):
            key = path.removeprefix(prefix)
            if method == "PUT":
                assert isinstance(payload, dict)
                self.env[key] = payload["value"]
                return {"envVar": {"key": key, "value": payload["value"]}}
            if method == "DELETE":
                self.env.pop(key, None)
                return None
        raise AssertionError(f"Unexpected Render call: {method} {path}")


def mutations(render: FakeRender) -> list[tuple[str, str, object | None]]:
    return [call for call in render.calls if call[0] in {"PUT", "DELETE"}]


def acquire_lease(render: FakeRender) -> str:
    return acquire(
        target_sha=SHA,
        target_branch=BRANCH,
        qa_service_id=QA_SERVICE_ID,
        production_service_id=PRODUCTION_SERVICE_ID,
        github_repository=REPOSITORY,
        client=render,
        token_factory=lambda size: LEASE_ID if size == 32 else "wrong-size-request",
    )


def release_lease(render: FakeRender) -> None:
    release(
        lease_id=LEASE_ID,
        target_sha=SHA,
        target_branch=BRANCH,
        qa_service_id=QA_SERVICE_ID,
        production_service_id=PRODUCTION_SERVICE_ID,
        github_repository=REPOSITORY,
        client=render,
    )


def test_acquire_validates_before_writing_and_commits_id_last() -> None:
    render = FakeRender()

    assert acquire_lease(render) == LEASE_ID

    assert [call[0] for call in render.calls[:2]] == ["GET", "GET"]
    assert mutations(render) == [
        ("PUT", f"{render.env_path}/{LEASE_SHA_KEY}", {"value": SHA}),
        ("PUT", f"{render.env_path}/{LEASE_BRANCH_KEY}", {"value": BRANCH}),
        ("PUT", f"{render.env_path}/{LEASE_ID_KEY}", {"value": LEASE_ID}),
    ]


@pytest.mark.parametrize(
    ("drift", "value"),
    [
        ("id", "srv-attacker"),
        ("repo", "https://github.com/attacker/other"),
        ("branch", "attacker/branch"),
        ("type", "static_site"),
        ("suspended", "suspended"),
        ("baseline_only", "false"),
        (LEASE_ID_KEY, LEASE_ID),
        (LEASE_SHA_KEY, SHA),
        (LEASE_BRANCH_KEY, BRANCH),
        ("QA_BASELINE_LEASE_UNKNOWN", "stale"),
    ],
)
def test_acquire_refuses_every_drift_without_mutation(drift: str, value: str) -> None:
    render = FakeRender()
    if drift == "baseline_only":
        render.env["QA_BASELINE_ONLY"] = value
    elif drift.startswith("QA_BASELINE_LEASE_"):
        render.env[drift] = value
    else:
        render.service[drift] = value

    with pytest.raises(LeaseError):
        acquire_lease(render)

    assert mutations(render) == []


def test_same_production_and_qa_identity_is_rejected_before_get() -> None:
    render = FakeRender()

    with pytest.raises(LeaseError):
        acquire(
            target_sha=SHA,
            target_branch=BRANCH,
            qa_service_id=PRODUCTION_SERVICE_ID,
            production_service_id=PRODUCTION_SERVICE_ID,
            github_repository=REPOSITORY,
            client=render,
            token_factory=lambda _: LEASE_ID,
        )

    assert render.calls == []


def test_acquire_failure_rolls_back_marker_first_then_target_fields() -> None:
    env_path = f"/services/{QA_SERVICE_ID}/env-vars"
    render = FakeRender(fail_on=("PUT", f"{env_path}/{LEASE_BRANCH_KEY}"))

    with pytest.raises(LeaseError, match="cleanup completed"):
        acquire_lease(render)

    assert mutations(render) == [
        ("PUT", f"{env_path}/{LEASE_SHA_KEY}", {"value": SHA}),
        ("PUT", f"{env_path}/{LEASE_BRANCH_KEY}", {"value": BRANCH}),
        ("DELETE", f"{env_path}/{LEASE_ID_KEY}", None),
        ("DELETE", f"{env_path}/{LEASE_SHA_KEY}", None),
        ("DELETE", f"{env_path}/{LEASE_BRANCH_KEY}", None),
    ]
    assert not ({LEASE_ID_KEY, LEASE_SHA_KEY, LEASE_BRANCH_KEY} & render.env.keys())


def test_release_revalidates_exact_lease_and_deletes_marker_first() -> None:
    render = FakeRender()
    render.env.update(
        {
            LEASE_ID_KEY: LEASE_ID,
            LEASE_SHA_KEY: SHA,
            LEASE_BRANCH_KEY: BRANCH,
        }
    )

    release_lease(render)

    assert [call[0] for call in render.calls[:2]] == ["GET", "GET"]
    assert mutations(render) == [
        ("DELETE", f"{render.env_path}/{LEASE_ID_KEY}", None),
        ("DELETE", f"{render.env_path}/{LEASE_SHA_KEY}", None),
        ("DELETE", f"{render.env_path}/{LEASE_BRANCH_KEY}", None),
    ]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (LEASE_ID_KEY, "K7pV2bN9wQ4mX6sD8fH1jL3cR5tY0uA2eG9iO7zC4Bk"),
        (LEASE_SHA_KEY, "b" * 40),
        (LEASE_BRANCH_KEY, "other/branch"),
    ],
)
def test_release_refuses_mismatched_lease_without_mutation(key: str, value: str) -> None:
    render = FakeRender()
    render.env.update(
        {
            LEASE_ID_KEY: LEASE_ID,
            LEASE_SHA_KEY: SHA,
            LEASE_BRANCH_KEY: BRANCH,
            key: value,
        }
    )

    with pytest.raises(LeaseError):
        release_lease(render)

    assert mutations(render) == []


def test_all_mutations_are_allowlisted_to_qa_and_never_touch_production() -> None:
    render = FakeRender()
    acquire_lease(render)
    render.calls.clear()
    release_lease(render)

    mutation_paths = [path for method, path, _ in render.calls if method in {"PUT", "DELETE"}]
    assert mutation_paths
    assert all(path.startswith(f"/services/{QA_SERVICE_ID}/env-vars/") for path in mutation_paths)
    assert all(PRODUCTION_SERVICE_ID not in path for path in mutation_paths)


def test_github_output_contains_only_lease_id(tmp_path) -> None:
    output = tmp_path / "github-output"
    output.write_text("", encoding="utf-8")
    render = FakeRender()

    acquire_to_github_output(
        output,
        target_sha=SHA,
        target_branch=BRANCH,
        qa_service_id=QA_SERVICE_ID,
        production_service_id=PRODUCTION_SERVICE_ID,
        github_repository=REPOSITORY,
        client=render,
        token_factory=lambda _: LEASE_ID,
    )

    assert output.read_text(encoding="utf-8") == f"lease_id={LEASE_ID}\n"


class Response:
    def __init__(self, payload: object) -> None:
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size: int) -> bytes:
        return self.raw


def test_http_failures_redact_response_body_and_credentials() -> None:
    secret = "provider-secret-never-log"

    def opener(request, timeout):
        assert timeout == 30
        assert request.headers["Authorization"] == f"Bearer {secret}"
        raise urllib.error.HTTPError(
            request.full_url,
            500,
            "failure containing database-password",
            {},
            io.BytesIO(b'{"value":"database-password"}'),
        )

    client = RenderClient(secret, QA_SERVICE_ID, opener=opener)
    with pytest.raises(LeaseError) as caught:
        client.request("GET", f"/services/{QA_SERVICE_ID}")

    message = str(caught.value)
    assert secret not in message
    assert "database-password" not in message
    assert "HTTP 500" in message


def test_render_client_refuses_production_and_nonlease_mutations_before_network() -> None:
    calls = []

    def opener(*args, **kwargs):
        calls.append((args, kwargs))
        return Response({})

    client = RenderClient("unused", QA_SERVICE_ID, opener=opener)
    with pytest.raises(LeaseError):
        client.request("GET", f"/services/{PRODUCTION_SERVICE_ID}")
    with pytest.raises(LeaseError):
        client.request("PUT", f"/services/{QA_SERVICE_ID}/env-vars/JWT_SECRET", {"value": "x"})
    with pytest.raises(LeaseError):
        client.request("DELETE", f"/services/{QA_SERVICE_ID}/env-vars/QA_BASELINE_ONLY")

    assert calls == []
