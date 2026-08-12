from __future__ import annotations

import json
from pathlib import Path

from scripts.agent_ops.check_release_evidence import SUMMARY_PATH_RE


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_formal_catalog_has_exact_v2_matrix_without_observations() -> None:
    catalog = _load("qa/regression-catalog.json")

    assert catalog["schema_version"] == 2
    assert catalog["catalog_type"] == "certified-isolated-preview-regression"
    assert len(catalog["cases"]) == 45
    assert sum(len(case["personas"]) for case in catalog["cases"]) == 173
    assert sum(
        len(case["personas"]) * len(case["devices"])
        for case in catalog["cases"]
    ) == 335
    assert all("scenario" not in case for case in catalog["cases"])
    assert all("observed" not in case for case in catalog["cases"])
    assert all("receptionist" not in case["personas"] for case in catalog["cases"])
    assert catalog["policy"]["persona_runtime_roles"]["reception"] == "receptionist"


def test_historical_observations_are_archived_and_non_certifiable() -> None:
    local = _load("qa/history/observations/non-certified-local-preview-static.json")
    shared = _load("qa/history/observations/shared-production-20260724.json")

    assert local["record_count"] == len(local["records"]) == 90
    assert shared["record_count"] == len(shared["records"]) == 9
    assert local["release_gate_eligible"] is False
    assert shared["release_gate_eligible"] is False


def test_operational_catalog_cannot_look_like_formal_release_evidence() -> None:
    operational = _load("qa/operational/shared-sandbox-catalog.json")

    assert operational["release_gate_eligible"] is False
    assert operational["status_values"] == [
        "PASS",
        "FAIL",
        "BLOCKED",
        "NOT_APPLICABLE",
    ]
    assert len(operational["cases"]) == 45
    assert not SUMMARY_PATH_RE.fullmatch(
        "qa/operational/runs/example/run-metadata.json"
    )
    assert not SUMMARY_PATH_RE.fullmatch(
        "qa/operational/runs/example/observations.json"
    )
