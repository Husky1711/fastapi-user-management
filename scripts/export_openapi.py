#!/usr/bin/env python3
"""Export OpenAPI schema for frontend codegen."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import app  # noqa: E402

OUTPUT = ROOT / "openapi.json"
FRONTEND_OUTPUT = ROOT / "frontend" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")

    FRONTEND_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_OUTPUT.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {FRONTEND_OUTPUT}")


if __name__ == "__main__":
    main()
