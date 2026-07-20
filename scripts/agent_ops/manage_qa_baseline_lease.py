#!/usr/bin/env python3
"""Acquire and release the exclusive lease for the dedicated Render QA baseline.

The lease lives in exactly three Render environment variables.  The target SHA
and branch are written first; the unpredictable lease ID is written last and
therefore acts as the commit marker.  Cleanup always removes that marker before
the descriptive target fields so a partial cleanup can never remain usable as
an active lease.

This utility deliberately has no access to a production service.  The
production service ID is accepted only as a negative identity assertion.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


RENDER_API = "https://api.render.com/v1"
LEASE_ONLY_KEY = "QA_BASELINE_ONLY"
LEASE_ID_KEY = "QA_BASELINE_LEASE_ID"
LEASE_SHA_KEY = "QA_BASELINE_LEASE_TARGET_SHA"
LEASE_BRANCH_KEY = "QA_BASELINE_LEASE_TARGET_BRANCH"
LEASE_KEYS = (LEASE_ID_KEY, LEASE_SHA_KEY, LEASE_BRANCH_KEY)
TARGET_KEYS = (LEASE_SHA_KEY, LEASE_BRANCH_KEY)
SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
SERVICE_ID_RE = re.compile(r"srv-[A-Za-z0-9]+")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
LEASE_ID_RE = re.compile(r"[A-Za-z0-9_-]{43}")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class LeaseError(RuntimeError):
    """Fail-closed error whose message contains no provider response values."""


class RenderRequester(Protocol):
    def request(self, method: str, path: str, payload: object | None = None) -> Any: ...


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _service_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not SERVICE_ID_RE.fullmatch(value):
        raise LeaseError(f"{field} is invalid")
    return value


def _target_sha(value: object) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise LeaseError("target SHA must be a full lowercase Git SHA")
    return value


def _target_branch(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 255
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or value.startswith(("/", "."))
        or value.endswith(("/", ".", ".lock"))
        or ".." in value
        or "//" in value
        or "@{" in value
        or "\\" in value
        or not re.fullmatch(r"[A-Za-z0-9._/-]+", value)
    ):
        raise LeaseError("target branch is invalid")
    return value


def _repository(value: object) -> str:
    if not isinstance(value, str) or not REPOSITORY_RE.fullmatch(value):
        raise LeaseError("GitHub repository must use owner/name format")
    return value.lower()


def _service_repository(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise LeaseError("Render QA service repository is invalid")
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError:
        raise LeaseError("Render QA service repository is invalid") from None
    repository = parsed.path.strip("/").removesuffix(".git")
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").rstrip(".").lower() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or not REPOSITORY_RE.fullmatch(repository)
    ):
        raise LeaseError("Render QA service repository is invalid")
    return repository.lower()


def _lease_id(value: object) -> str:
    """Require the canonical 32-byte base64url shape emitted by token_urlsafe."""

    if not isinstance(value, str) or not LEASE_ID_RE.fullmatch(value):
        raise LeaseError("baseline lease ID is invalid")
    try:
        import base64

        decoded = base64.urlsafe_b64decode(value + "=")
        canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    except (TypeError, ValueError):
        raise LeaseError("baseline lease ID is invalid") from None
    if len(decoded) != 32 or canonical != value:
        raise LeaseError("baseline lease ID is invalid")
    return value


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LeaseError(f"Render {field} response is invalid")
    return value


def _env_values(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise LeaseError("Render environment response is invalid")
    result: dict[str, str] = {}
    for wrapper in value:
        wrapper_object = _object(wrapper, "environment item")
        env_var = _object(wrapper_object.get("envVar"), "environment variable")
        key = env_var.get("key")
        env_value = env_var.get("value")
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(env_value, str)
            or key in result
        ):
            raise LeaseError("Render environment response is invalid")
        result[key] = env_value
    return result


def _paths(service_id: str) -> tuple[str, str]:
    quoted = urllib.parse.quote(service_id, safe="")
    return f"/services/{quoted}", f"/services/{quoted}/env-vars"


class RenderClient:
    """Minimal Render client allowlisted to one QA service and three lease keys."""

    def __init__(
        self,
        token: str,
        qa_service_id: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if not isinstance(token, str) or not token:
            raise LeaseError("RENDER_API_TOKEN is missing")
        self.qa_service_id = _service_id(qa_service_id, "QA service ID")
        self._token = token
        self._opener = opener
        service_path, env_path = _paths(self.qa_service_id)
        self._allowed = {
            ("GET", service_path),
            ("GET", env_path),
            *((method, f"{env_path}/{key}") for method in ("PUT", "DELETE") for key in LEASE_KEYS),
        }

    def request(self, method: str, path: str, payload: object | None = None) -> Any:
        method = method.upper()
        if (method, path) not in self._allowed:
            raise LeaseError("Render request is outside the dedicated QA lease allowlist")
        if method == "GET" and payload is not None:
            raise LeaseError("Render GET request payload is invalid")
        if method == "PUT" and (
            not isinstance(payload, dict)
            or set(payload) != {"value"}
            or not isinstance(payload.get("value"), str)
        ):
            raise LeaseError("Render PUT request payload is invalid")
        if method == "DELETE" and payload is not None:
            raise LeaseError("Render DELETE request payload is invalid")

        body = _canonical_json(payload) if payload is not None else None
        request = urllib.request.Request(
            f"{RENDER_API}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Hotel-Chipre-PMS-QA-baseline-lease/1.0",
            },
        )
        try:
            with self._opener(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise LeaseError(f"Render {method} request failed with HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise LeaseError(f"Render {method} request failed") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LeaseError("Render response exceeded the safety limit")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise LeaseError("Render returned invalid JSON") from None


def _validated_snapshot(
    client: RenderRequester,
    *,
    target_sha: str,
    target_branch: str,
    qa_service_id: str,
    production_service_id: str,
    github_repository: str,
) -> tuple[str, str, dict[str, str]]:
    """Read and validate every mutable identity before allowing a write."""

    qa_id = _service_id(qa_service_id, "QA service ID")
    production_id = _service_id(production_service_id, "production service ID")
    sha = _target_sha(target_sha)
    branch = _target_branch(target_branch)
    repository = _repository(github_repository)
    if qa_id == production_id:
        raise LeaseError("Render QA service must differ from production")

    service_path, env_path = _paths(qa_id)
    service = _object(client.request("GET", service_path), "service")
    env = _env_values(client.request("GET", env_path))
    if (
        service.get("id") != qa_id
        or _service_repository(service.get("repo")) != repository
        or service.get("branch") != branch
        or service.get("type") != "web_service"
        or service.get("suspended") != "not_suspended"
    ):
        raise LeaseError("Render QA service identity, repository, or branch drifted")
    if env.get(LEASE_ONLY_KEY) != "true":
        raise LeaseError("Render QA service is not dedicated-baseline-only")
    return sha, branch, env


def _mutate_env(
    client: RenderRequester,
    service_id: str,
    method: str,
    key: str,
    value: str | None = None,
) -> None:
    _, env_path = _paths(service_id)
    payload = {"value": value} if value is not None else None
    client.request(method, f"{env_path}/{key}", payload)


def _cleanup(client: RenderRequester, service_id: str) -> bool:
    """Best-effort fail-closed cleanup; marker is always attempted first."""

    failed = False
    for key in LEASE_KEYS:
        try:
            _mutate_env(client, service_id, "DELETE", key)
        except Exception:
            # Provider bodies and exception strings are intentionally discarded.
            failed = True
    return not failed


def acquire(
    *,
    target_sha: str,
    target_branch: str,
    qa_service_id: str,
    production_service_id: str,
    github_repository: str,
    render_token: str = "",
    client: RenderRequester | None = None,
    token_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> str:
    """Acquire one exclusive lease and return its unlogged commit-marker ID."""

    qa_id = _service_id(qa_service_id, "QA service ID")
    render = client or RenderClient(render_token, qa_id)
    sha, branch, env = _validated_snapshot(
        render,
        target_sha=target_sha,
        target_branch=target_branch,
        qa_service_id=qa_id,
        production_service_id=production_service_id,
        github_repository=github_repository,
    )
    if any(key.startswith("QA_BASELINE_LEASE_") for key in env):
        raise LeaseError("Render QA baseline already has lease state")

    try:
        lease_id = _lease_id(token_factory(32))
    except LeaseError:
        raise
    except Exception:
        raise LeaseError("baseline lease ID generation failed") from None
    try:
        # Target description first. The random ID is the final commit marker.
        _mutate_env(render, qa_id, "PUT", LEASE_SHA_KEY, sha)
        _mutate_env(render, qa_id, "PUT", LEASE_BRANCH_KEY, branch)
        _mutate_env(render, qa_id, "PUT", LEASE_ID_KEY, lease_id)
    except Exception:
        cleanup_ok = _cleanup(render, qa_id)
        detail = "cleanup completed" if cleanup_ok else "cleanup was incomplete"
        raise LeaseError(f"Render QA baseline lease acquisition failed; {detail}") from None
    return lease_id


def release(
    *,
    lease_id: str,
    target_sha: str,
    target_branch: str,
    qa_service_id: str,
    production_service_id: str,
    github_repository: str,
    render_token: str = "",
    client: RenderRequester | None = None,
) -> None:
    """Release exactly the caller's lease, invalidating its marker first."""

    qa_id = _service_id(qa_service_id, "QA service ID")
    expected_lease = _lease_id(lease_id)
    render = client or RenderClient(render_token, qa_id)
    sha, branch, env = _validated_snapshot(
        render,
        target_sha=target_sha,
        target_branch=target_branch,
        qa_service_id=qa_id,
        production_service_id=production_service_id,
        github_repository=github_repository,
    )
    if (
        env.get(LEASE_ID_KEY) != expected_lease
        or env.get(LEASE_SHA_KEY) != sha
        or env.get(LEASE_BRANCH_KEY) != branch
    ):
        raise LeaseError("Render QA baseline lease does not match the requested target")

    if not _cleanup(render, qa_id):
        raise LeaseError("Render QA baseline lease release was incomplete")


def _open_github_output(path: Path) -> int:
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        raise LeaseError("GITHUB_OUTPUT is missing, symlinked, or unwritable") from None
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise LeaseError("GITHUB_OUTPUT is not a regular file")
    return descriptor


def acquire_to_github_output(
    output_path: Path,
    *,
    target_sha: str,
    target_branch: str,
    qa_service_id: str,
    production_service_id: str,
    github_repository: str,
    render_token: str = "",
    client: RenderRequester | None = None,
    token_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> None:
    """Acquire and append only ``lease_id`` to the pre-opened GitHub output."""

    descriptor = _open_github_output(output_path)
    lease_id: str | None = None
    render = client or RenderClient(render_token, _service_id(qa_service_id, "QA service ID"))
    try:
        lease_id = acquire(
            target_sha=target_sha,
            target_branch=target_branch,
            qa_service_id=qa_service_id,
            production_service_id=production_service_id,
            github_repository=github_repository,
            render_token=render_token,
            client=render,
            token_factory=token_factory,
        )
        raw = f"lease_id={lease_id}\n".encode("ascii")
        written = os.write(descriptor, raw)
        if written != len(raw):
            raise OSError("short write")
    except Exception as error:
        if lease_id is not None:
            _cleanup(render, _service_id(qa_service_id, "QA service ID"))
        if isinstance(error, LeaseError):
            raise
        raise LeaseError("GITHUB_OUTPUT could not record the acquired lease") from None
    finally:
        os.close(descriptor)


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--qa-service-id", required=True)
    parser.add_argument("--production-service-id", required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquire_parser = commands.add_parser("acquire")
    _common_arguments(acquire_parser)
    acquire_parser.add_argument(
        "--github-output",
        type=Path,
        default=Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None,
    )
    release_parser = commands.add_parser("release")
    _common_arguments(release_parser)
    release_parser.add_argument("--lease-id", default=os.environ.get("QA_BASELINE_LEASE_ID", ""))
    args = parser.parse_args()

    try:
        common = {
            "target_sha": args.target_sha,
            "target_branch": args.target_branch,
            "qa_service_id": args.qa_service_id,
            "production_service_id": args.production_service_id,
            "github_repository": args.repository,
            "render_token": os.environ.get("RENDER_API_TOKEN", ""),
        }
        if args.command == "acquire":
            if args.github_output is None:
                raise LeaseError("GITHUB_OUTPUT is missing")
            acquire_to_github_output(args.github_output, **common)
            print("Render QA baseline lease acquired.")
        else:
            release(lease_id=args.lease_id, **common)
            print("Render QA baseline lease released.")
    except LeaseError as error:
        print(f"Render QA baseline lease operation refused: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
