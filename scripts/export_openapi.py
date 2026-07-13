#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file (CI / internal portal).

Production disables ``/openapi.json`` and ``/docs`` for attack-surface reduction.
Operators still need the contract — generate it in CI and upload as an artifact.

Usage:
    python scripts/export_openapi.py
    python scripts/export_openapi.py artifacts/openapi.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Non-production so app construction enables the OpenAPI schema routes in settings.
os.environ.setdefault("APP__ENVIRONMENT", "development")


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else project_root / "artifacts" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    from main import app

    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote OpenAPI schema to {out} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
