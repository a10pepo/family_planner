"""Export/check the API contract without connecting to a database or identity provider."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api import create_app  # noqa: E402


def export(check: bool = False) -> None:
    contract = create_app("postgresql+psycopg://unused:unused@localhost/unused").openapi()
    content = json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path = ROOT / "docs" / "openapi.json"
    if check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit("El contrato OpenAPI cambió. Regenera con scripts/export_openapi.py.")
        print("OpenAPI contract OK")
    else:
        path.write_text(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    export(parser.parse_args().check)
