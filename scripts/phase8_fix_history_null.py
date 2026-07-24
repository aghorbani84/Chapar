#!/usr/bin/env python3
"""
Fix HistoryPanel TypeScript null narrowing issue.

TypeScript does not preserve Svelte template narrowing inside closures.

This replaces:

    onclick={() => loadIntoEditor(selected)}

with:

    onclick={() => {
      if (selected) {
        loadIntoEditor(selected);
      }
    }}
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OLD_HANDLER = "onclick={() => loadIntoEditor(selected)}"

NEW_HANDLER = """onclick={() => {
      if (selected) {
        loadIntoEditor(selected);
      }
    }}"""

TARGETS = [
    "scripts/phase8.py",
    "src/lib/components/HistoryPanel.svelte",
]


def patch_file(relative_path: str) -> None:
    path = ROOT / relative_path

    if not path.exists():
        print(f"SKIP  {relative_path} not found")
        return

    text = path.read_text(encoding="utf-8")

    if OLD_HANDLER in text:
        text = text.replace(OLD_HANDLER, NEW_HANDLER)
        path.write_text(text, encoding="utf-8")
        print(f"PATCH {relative_path}")
    else:
        print(f"OK    {relative_path} already patched or handler not found")


def main() -> int:
    print(f"Project root: {ROOT}")

    for target in TARGETS:
        patch_file(target)

    print("RUN  python3 scripts/phase8.py")

    subprocess.run(
        ["python3", str(ROOT / "scripts" / "phase8.py")],
        check=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
