"""Regression coverage for portable Graphify artifact normalization."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.agent_ops import normalize_graphify_portability


def test_normalizes_generated_instruction_paths_without_touching_external_paths(
    tmp_path: Path, monkeypatch
) -> None:
    """Embedded worktree paths must become repository-relative instructions."""
    graphify = tmp_path / ".graphify"
    description_instructions = graphify / "description-instructions"
    label_instructions = graphify / "label-instructions"
    description_instructions.mkdir(parents=True)
    label_instructions.mkdir()
    graph = graphify / "graph.json"
    flows = graphify / "flows.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [
                    {"label": "/api/reservations"},
                    {"label": "/opt/graphify/external.json"},
                ]
            }
        ),
        encoding="utf-8",
    )
    flows.write_text(
        json.dumps({"graphPath": str(graph), "flow": "kept"}), encoding="utf-8"
    )
    description = description_instructions / "batch.md"
    description.write_text(
        f"Write output to: {description_instructions / 'batch.json'}\n"
        "Keep external reference: /opt/graphify/template.json\n",
        encoding="utf-8",
    )
    label = label_instructions / "communities.md"
    label.write_text(
        f"Write output to: {label_instructions / 'communities.json'}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(normalize_graphify_portability, "ROOT", tmp_path)
    monkeypatch.setattr(normalize_graphify_portability, "GRAPH", graph)
    monkeypatch.setattr(normalize_graphify_portability, "FLOWS", flows)

    assert normalize_graphify_portability.main() == 0

    labels = [node["label"] for node in json.loads(graph.read_text(encoding="utf-8"))["nodes"]]
    assert labels == ["api/reservations", "/opt/graphify/external.json"]
    assert json.loads(flows.read_text(encoding="utf-8"))["graphPath"] == ".graphify/graph.json"
    assert description.read_text(encoding="utf-8") == (
        "Write output to: .graphify/description-instructions/batch.json\n"
        "Keep external reference: /opt/graphify/template.json\n"
    )
    assert label.read_text(encoding="utf-8") == (
        "Write output to: .graphify/label-instructions/communities.json\n"
    )


def test_does_not_follow_instruction_symlink_outside_generated_directory(
    tmp_path: Path, monkeypatch
) -> None:
    """A generated-instruction symlink must not allow writes outside the repository."""
    description_instructions = tmp_path / ".graphify" / "description-instructions"
    description_instructions.mkdir(parents=True)
    external_instruction = tmp_path.parent / f"{tmp_path.name}-external.md"
    external_content = f"Keep path: {tmp_path / '.graphify' / 'graph.json'}\n"
    external_instruction.write_text(external_content, encoding="utf-8")
    (description_instructions / "external.md").symlink_to(external_instruction)
    monkeypatch.setattr(normalize_graphify_portability, "ROOT", tmp_path)

    assert normalize_graphify_portability.normalize_instruction_paths() == 0

    assert external_instruction.read_text(encoding="utf-8") == external_content


def test_does_not_follow_instruction_directory_symlink_outside_generated_directory(
    tmp_path: Path, monkeypatch
) -> None:
    """A symlinked instruction directory must not allow external files to be rewritten."""
    description_instructions = tmp_path / ".graphify" / "description-instructions"
    description_instructions.mkdir(parents=True)
    external_directory = tmp_path.parent / f"{tmp_path.name}-external"
    external_directory.mkdir()
    external_instruction = external_directory / "external.md"
    external_content = f"Keep path: {tmp_path / '.graphify' / 'graph.json'}\n"
    external_instruction.write_text(external_content, encoding="utf-8")
    (description_instructions / "external").symlink_to(
        external_directory, target_is_directory=True
    )
    monkeypatch.setattr(normalize_graphify_portability, "ROOT", tmp_path)

    assert normalize_graphify_portability.normalize_instruction_paths() == 0

    assert external_instruction.read_text(encoding="utf-8") == external_content


def test_is_idempotent_after_generated_paths_are_normalized(tmp_path: Path, monkeypatch) -> None:
    """A second normalizer run must leave already-portable artifacts unchanged."""
    graphify = tmp_path / ".graphify"
    instructions = graphify / "description-instructions"
    instructions.mkdir(parents=True)
    graph = graphify / "graph.json"
    flows = graphify / "flows.json"
    instruction = instructions / "batch.md"
    graph.write_text('{"label":"/api/reservations"}\n', encoding="utf-8")
    flows.write_text(json.dumps({"graphPath": str(graph)}), encoding="utf-8")
    instruction.write_text(
        f"Write output to: {instructions / 'batch.json'}\n", encoding="utf-8"
    )
    monkeypatch.setattr(normalize_graphify_portability, "ROOT", tmp_path)
    monkeypatch.setattr(normalize_graphify_portability, "GRAPH", graph)
    monkeypatch.setattr(normalize_graphify_portability, "FLOWS", flows)

    assert normalize_graphify_portability.main() == 0
    after_first_run = {path: path.read_bytes() for path in (graph, flows, instruction)}

    assert normalize_graphify_portability.main() == 0

    assert {path: path.read_bytes() for path in (graph, flows, instruction)} == after_first_run
