#!/usr/bin/env python3
"""Generate reproducible, non-sensitive inventory artifacts for the knowledge vault."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "knowledge" / "_generated"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def command(*args: str) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        return f"UNAVAILABLE (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
    return result.stdout.strip()


def heading(title: str) -> str:
    return (
        f"# {title}\n\n"
        f"Generado: {datetime.now(UTC).isoformat()}\n"
        f"Commit: `{command('git', 'rev-parse', '--short', 'HEAD')}`\n\n"
    )


def fenced(value: str, language: str = "text") -> str:
    return f"```{language}\n{value}\n```\n"


def frontend_routes() -> list[str]:
    source = (ROOT / "frontend" / "src" / "router.tsx").read_text(encoding="utf-8")
    paths = re.findall(r"\bpath:\s*[\"']([^\"']+)[\"']", source)
    return list(dict.fromkeys(paths))


def write(path: str, content: str) -> None:
    (OUT / path).write_text(content, encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sha = command("git", "rev-parse", "--short", "HEAD")

    try:
        from app.main import app  # Imported only to obtain FastAPI's declared contract.

        schema = app.openapi()
        (OUT / "openapi.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        operations = sum(len(item) for item in schema.get("paths", {}).values())
        api_content = heading("Inventario OpenAPI")
        api_content += f"Contrato generado desde `app.main:app`: **{len(schema.get('paths', {}))} paths**, **{operations} operaciones**.\n\n"
        api_content += "El contrato completo está en [openapi.json](openapi.json). No editarlo a mano.\n"
        write("api-surface.md", api_content)
    except Exception as error:  # Inventory generation must reveal, not hide, import failures.
        write("api-surface.md", heading("Inventario OpenAPI") + f"Estado: **needs-verification** — no se pudo importar FastAPI: `{error!r}`.\n")

    routes = frontend_routes()
    route_lines = "\n".join(f"- `{route}`" for route in routes)
    write(
        "frontend-routes.md",
        heading("Rutas frontend")
        + f"Extraídas de `frontend/src/router.tsx` ({len(routes)} rutas declaradas). El host determina si una ruta es app o marketing.\n\n"
        + route_lines
        + "\n",
    )

    alembic = command(sys.executable, "-m", "alembic", "heads")
    write("migration-head.md", heading("Alembic head") + fenced(alembic) + "Fuente: `alembic.ini` y `alembic/versions/`.\n")

    graph_summary = command("graphify", "summary", ".graphify/graph.json")
    graph_check = command("graphify", "check-update", ".")
    write(
        "graphify-summary.md",
        heading("Resumen Graphify")
        + "`graphify summary .graphify/graph.json`:\n"
        + fenced(graph_summary)
        + "`graphify check-update .`:\n"
        + fenced(graph_check)
        + "Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.\n",
    )

    surfaces = {
        "canonical": [
            "https://app.hotels-pms.com",
            "https://hotels-pms.com",
            "https://api.hotels-pms.com",
        ],
        "preview_contract": [
            "Vercel frontend por PR (URL publicada en manifiesto de preview)",
            "Render backend QA target-bound con /health y lease exclusivo",
            "Segundo proyecto Supabase QA sin datos productivos como baseline serializada; Supabase Branch por PR al habilitar el plan",
        ],
        "historical_or_needs_verification": [
            "Cualquier host hoteles-pms.com o onrender.com citado por documentación histórica",
            "Callbacks de pagos, email, WhatsApp y OTAs: validar por contrato, no ejecutar en QA cloud",
        ],
    }
    (OUT / "cloud-surfaces.json").write_text(json.dumps({"code_sha": sha, **surfaces}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cloud = heading("Superficies cloud")
    for category, values in surfaces.items():
        cloud += f"## {category}\n\n" + "\n".join(f"- {value}" for value in values) + "\n\n"
    cloud += "Datos estructurados: [cloud-surfaces.json](cloud-surfaces.json).\n"
    write("cloud-surfaces.md", cloud)

    write(
        "README.md",
        heading("Artefactos generados")
        + "Estos archivos se regeneran con `.venv/bin/python scripts/knowledge/generate_inventories.py`. Las notas curadas deben enlazarlos en vez de copiar listados completos.\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
