"""Check dependency boundaries without importing application code."""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_boundaries(root: Path) -> list[str]:
    errors: list[str] = []
    frontend = root / "frontend"
    for path in (frontend / "src").rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        content = path.read_text()
        imports = re.findall(r"(?:from\s*|import\s*\(|require\s*\()\s*['\"]([^'\"]+)", content)
        for source in imports:
            if "backend" in source.split("/") or source.startswith(
                ("pg", "postgres", "@prisma/", "mysql", "sqlite", "sequelize")
            ):
                errors.append(f"{path.relative_to(root)}: forbidden frontend import {source}")
    package_file = frontend / "package.json"
    if package_file.exists():
        dependencies = json.loads(package_file.read_text()).get("dependencies", {})
        for name in dependencies:
            if name in {"pg", "postgres", "mysql2", "sqlite3", "sequelize", "@prisma/client"}:
                errors.append(f"frontend/package.json: database dependency {name}")
    for path in (root / "backend" / "app" / "domain").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if name.startswith(
                    ("fastapi", "starlette", "sqlalchemy", "psycopg", "boto3", "app.adapters")
                ):
                    errors.append(f"{path.relative_to(root)}: forbidden domain import {name}")
    return errors


if __name__ == "__main__":
    violations = check_boundaries(ROOT)
    if violations:
        raise SystemExit("\n".join(violations))
    print("Architecture boundaries OK")
