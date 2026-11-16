"""Regenerate everything derived from schema.graphql; run through scripts/generate.sh."""

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TYPES = ROOT / "keitaro_contracts" / "types.py"
PACKAGE_JSON = ROOT / "package.json"
ROOT_OPERATIONS = {"Query", "Mutation", "Subscription"}
HEADER = '''"""Strawberry types of the contract.

GENERATED from schema.graphql by scripts/generate.sh — do not edit by hand.
Root operations are left out: the backend writes Query and Mutation itself.
"""

'''


def tool(name: str) -> str:
    return str(Path(sys.executable).parent / name)


def strawberry_types() -> str:
    """Let Strawberry translate the schema, then drop what belongs to the backend."""
    generated = subprocess.run(
        [tool("strawberry"), "schema-codegen", "schema.graphql"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    lines = generated.splitlines()
    for node in reversed(ast.parse(generated).body):
        is_root = isinstance(node, ast.ClassDef) and node.name in ROOT_OPERATIONS
        is_schema = isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "schema" for target in node.targets
        )
        if is_root or is_schema:
            first = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
            del lines[first - 1 : node.end_lineno]
    return HEADER + "\n".join(lines).strip() + "\n"


def sync_npm_version() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    manifest["version"] = version
    PACKAGE_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", "utf-8")


if __name__ == "__main__":
    TYPES.write_text(strawberry_types(), encoding="utf-8")
    subprocess.run([tool("ruff"), "format", "--quiet", str(TYPES)], cwd=ROOT, check=True)
    sync_npm_version()
    print(f"generated {TYPES.relative_to(ROOT)} and synced {PACKAGE_JSON.name}")
