#!/usr/bin/env python3
"""Discover and inspect bounded, same-origin JavaScript from a Vercel preview."""

from __future__ import annotations

import argparse
import json
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit


MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 8 * 1024 * 1024
MAX_TOTAL_ASSET_BYTES = 32 * 1024 * 1024
MAX_SCRIPT_ASSETS = 64
API_ORIGIN_RE = re.compile(rb"https://(?:api\.hotels-pms\.com|[a-z0-9.-]+\.onrender\.com)", re.IGNORECASE)


class BundleVerificationError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attributes = {key.lower(): value for key, value in attrs}
        source = attributes.get("src")
        if source is not None:
            self.sources.append(source)


def _origin(value: str, *, suffix: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").rstrip(".").lower()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or (host != suffix and not host.endswith(f".{suffix}"))
    ):
        raise BundleVerificationError(f"URL must be a credential-free HTTPS {suffix} origin")
    return f"https://{host}"


def discover_script_urls(html: bytes, app_url: str) -> list[str]:
    if len(html) > MAX_HTML_BYTES:
        raise BundleVerificationError("Vercel preview HTML exceeds the 2 MiB safety limit")
    try:
        text = html.decode("utf-8")
    except UnicodeDecodeError:
        raise BundleVerificationError("Vercel preview HTML is not UTF-8") from None
    app_origin = _origin(app_url, suffix="vercel.app")
    parser = _ScriptParser()
    parser.feed(text)
    parser.close()
    if len(parser.sources) > MAX_SCRIPT_ASSETS:
        raise BundleVerificationError("Vercel preview references too many script assets")
    urls: list[str] = []
    for source in parser.sources:
        if not source or any(ord(character) < 32 for character in source):
            raise BundleVerificationError("Vercel preview contains an invalid script URL")
        absolute = urljoin(f"{app_origin}/", source)
        parsed = urlsplit(absolute)
        if (
            _origin(absolute.split("?", 1)[0], suffix="vercel.app") != app_origin
            or parsed.query
            or parsed.fragment
            or not parsed.path.lower().endswith(".js")
        ):
            raise BundleVerificationError("Every remote script must be same-origin HTTPS JavaScript without query data")
        canonical = f"{app_origin}{parsed.path}"
        if canonical not in urls:
            urls.append(canonical)
    if not urls:
        raise BundleVerificationError("Vercel preview HTML contains no external JavaScript bundle")
    return urls


def verify_asset_payloads(payloads: list[bytes], api_base_url: str) -> None:
    desired_origin = _origin(api_base_url.removesuffix("/api"), suffix="onrender.com")
    desired = api_base_url.rstrip("/").encode("utf-8")
    total = 0
    contains_desired = False
    for payload in payloads:
        if len(payload) > MAX_ASSET_BYTES:
            raise BundleVerificationError("A Vercel JavaScript asset exceeds the 8 MiB safety limit")
        total += len(payload)
        if total > MAX_TOTAL_ASSET_BYTES:
            raise BundleVerificationError("Vercel JavaScript assets exceed the 32 MiB aggregate safety limit")
        contains_desired = contains_desired or desired in payload
        for match in API_ORIGIN_RE.finditer(payload):
            origin = match.group(0).decode("ascii").lower().rstrip(".")
            if origin != desired_origin:
                raise BundleVerificationError("Vercel JavaScript bundle contains a production or historical API host")
    if not contains_desired:
        raise BundleVerificationError("Vercel JavaScript bundle does not contain the exact verified api_base_url")


def _asset_entries(index: Path, app_url: str) -> list[tuple[str, str]]:
    entries = json.loads(index.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries or len(entries) > MAX_SCRIPT_ASSETS:
        raise BundleVerificationError("Asset index is invalid")
    app_origin = _origin(app_url, suffix="vercel.app")
    result: list[tuple[str, str]] = []
    for position, entry in enumerate(entries):
        expected_file = f"asset-{position}.js"
        if not isinstance(entry, dict) or entry.get("file") != expected_file:
            raise BundleVerificationError("Asset index filename is invalid")
        url = entry.get("url")
        if not isinstance(url, str) or _origin(url, suffix="vercel.app") != app_origin:
            raise BundleVerificationError("Asset index URL is not on the verified Vercel origin")
        parsed = urlsplit(url)
        if parsed.query or parsed.fragment or not parsed.path.lower().endswith(".js"):
            raise BundleVerificationError("Asset index URL is not canonical JavaScript")
        result.append((url, expected_file))
    return result


def fetch_assets(index: Path, asset_dir: Path, app_url: str) -> None:
    """Download bounded same-origin assets without following redirects."""

    entries = _asset_entries(index, app_url)
    if asset_dir.is_symlink():
        raise BundleVerificationError("Asset directory must not be a symlink")
    asset_dir.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(_NoRedirect())
    total = 0
    for url, filename in entries:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/javascript", "User-Agent": "Hotel-Chipre-PMS-preview-bundle-verifier/1.0"},
            method="GET",
        )
        try:
            with opener.open(request, timeout=30) as response:
                if response.geturl() != url:
                    raise BundleVerificationError("Vercel asset redirected away from its verified URL")
                payload = response.read(MAX_ASSET_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise BundleVerificationError(
                f"Vercel asset request failed with HTTP {error.code}"
            ) from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise BundleVerificationError("Vercel asset request failed") from None
        if len(payload) > MAX_ASSET_BYTES:
            raise BundleVerificationError("A Vercel JavaScript asset exceeds the 8 MiB safety limit")
        total += len(payload)
        if total > MAX_TOTAL_ASSET_BYTES:
            raise BundleVerificationError("Vercel JavaScript assets exceed the 32 MiB aggregate safety limit")
        destination = asset_dir / filename
        if destination.exists() or destination.is_symlink():
            raise BundleVerificationError("Asset destination already exists")
        destination.write_bytes(payload)


def _discover(args: argparse.Namespace) -> int:
    html = args.html.read_bytes()
    urls = discover_script_urls(html, args.app_url)
    args.output.write_text(
        json.dumps([{"url": url, "file": f"asset-{index}.js"} for index, url in enumerate(urls)], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Discovered {len(urls)} bounded same-origin JavaScript asset(s).")
    return 0


def _verify(args: argparse.Namespace) -> int:
    entries = _asset_entries(args.index, args.app_url)
    payloads: list[bytes] = []
    for _, filename in entries:
        payloads.append((args.asset_dir / filename).read_bytes())
    verify_asset_payloads(payloads, args.api_base_url)
    print("Remote Vercel JavaScript contains the exact preview API and no production/historical API host.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser("discover")
    discover.add_argument("--html", type=Path, required=True)
    discover.add_argument("--app-url", required=True)
    discover.add_argument("--output", type=Path, required=True)
    discover.set_defaults(handler=_discover)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--index", type=Path, required=True)
    verify.add_argument("--asset-dir", type=Path, required=True)
    verify.add_argument("--app-url", required=True)
    verify.add_argument("--api-base-url", required=True)
    verify.set_defaults(handler=_verify)
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--index", type=Path, required=True)
    fetch.add_argument("--asset-dir", type=Path, required=True)
    fetch.add_argument("--app-url", required=True)
    fetch.set_defaults(
        handler=lambda args: (fetch_assets(args.index, args.asset_dir, args.app_url), 0)[1]
    )
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (BundleVerificationError, OSError, json.JSONDecodeError) as error:
        print(f"Remote Vercel bundle verification failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
