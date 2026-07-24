#!/usr/bin/env python3
"""
Fix Phase 3 Svelte placeholder syntax error.

Svelte treats raw curly braces inside attributes as expressions.
This replaces the problematic JSON example placeholder with a safe placeholder,
patches scripts/phase3.py, patches the generated +page.svelte, and reruns Phase 3.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OLD_MARKER = "placeholder='Example JSON:"
NEW_LINE = 'placeholder="Example JSON: hello world"'

TARGETS = [
    "scripts/phase3.py",
    "src/routes/+page.svelte",
]


def patch_file(relative_path: str) -> bool:
    path = ROOT / relative_path

    if not path.exists():
        print(f"SKIP  {relative_path} not found")
        return False

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False

    for index, line in enumerate(lines):
        if OLD_MARKER in line:
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f"{indent}{NEW_LINE}\n"
            changed = True

    if changed:
        path.write_text("".join(lines), encoding="utf-8")
        print(f"PATCH {relative_path}")
    else:
        print(f"OK    {relative_path} already patched or marker not found")

    return changed


def main() -> int:
    print(f"Project root: {ROOT}")

    for target in TARGETS:
        patch_file(target)

    print("RUN  python3 scripts/phase3.py")

    subprocess.run(
        ["python3", str(ROOT / "scripts" / "phase3.py")],
        check=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())