#!/usr/bin/env python3
"""
Fix Phase 5 Svelte placeholder syntax error.

Svelte treats raw curly braces inside attributes as expressions.
This replaces the problematic placeholder text in both the generated
RequestPane.svelte and scripts/phase5.py, then reruns Phase 5.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OLD_PLACEHOLDER = 'placeholder="https://api.example.com or {{base_url}}/path"'
NEW_PLACEHOLDER = 'placeholder="https://api.example.com or use environment variables"'

TARGETS = [
    "scripts/phase5.py",
    "src/lib/components/RequestPane.svelte",
]


def patch_file(relative_path: str) -> None:
    path = ROOT / relative_path

    if not path.exists():
        print(f"SKIP  {relative_path} not found")
        return

    text = path.read_text(encoding="utf-8")

    if OLD_PLACEHOLDER in text:
        text = text.replace(OLD_PLACEHOLDER, NEW_PLACEHOLDER)
        path.write_text(text, encoding="utf-8")
        print(f"PATCH {relative_path}")
    else:
        print(f"OK    {relative_path} already patched or placeholder not found")


def main() -> int:
    print(f"Project root: {ROOT}")

    for target in TARGETS:
        patch_file(target)

    print("RUN  python3 scripts/phase5.py")

    subprocess.run(
        ["python3", str(ROOT / "scripts" / "phase5.py")],
        check=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())