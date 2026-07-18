#!/usr/bin/env python3
"""Keep deployed-domain defaults aligned with the canonical cloud manifest."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SITE = "https://hotels-pms.com"
CANONICAL_APP = "https://app.hotels-pms.com"
LIVE_FILES = (
    ".env.example",
    ".env.render",
    "render.yaml",
    "frontend/src/config/publicUrls.ts",
    "frontend/index.html",
    "frontend/public/robots.txt",
    "frontend/public/sitemap.xml",
)
HISTORICAL_HOST = "hoteles-pms.com"


def main() -> int:
    errors: list[str] = []
    for relative in LIVE_FILES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if HISTORICAL_HOST in text:
            errors.append(f"historical host in current configuration: {relative}")
    expected = {
        ".env.example": (CANONICAL_SITE, CANONICAL_APP),
        ".env.render": (CANONICAL_SITE, CANONICAL_APP),
        "render.yaml": (CANONICAL_SITE, CANONICAL_APP),
        "frontend/src/config/publicUrls.ts": ("app.hotels-pms.com",),
        "frontend/index.html": (CANONICAL_SITE, "app.hotels-pms.com"),
        "frontend/public/robots.txt": (CANONICAL_SITE,),
        "frontend/public/sitemap.xml": (CANONICAL_SITE,),
    }
    for relative, fragments in expected.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                errors.append(f"missing canonical host fragment in {relative}: {fragment}")
    if errors:
        print("Cloud surface configuration validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Cloud surface configuration uses the canonical hotels-pms.com hosts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
