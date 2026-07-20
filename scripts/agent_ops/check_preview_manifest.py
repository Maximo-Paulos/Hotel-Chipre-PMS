#!/usr/bin/env python3
"""Compatibility entry point for the provider-evidence preview validator.

The schema-v1 self-attestation contract was intentionally retired.  Keep this
filename as a fail-safe shim so old local commands receive the schema-v2 checks
instead of silently accepting a weak manifest.
"""

from validate_preview_manifest import main


if __name__ == "__main__":
    raise SystemExit(main())
