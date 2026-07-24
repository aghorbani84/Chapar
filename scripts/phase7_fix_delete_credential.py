#!/usr/bin/env python3
"""
Fix keyring delete API for Phase 7.

Current keyring versions use:

    entry.delete_credential()

Older versions used:

    entry.delete_password()

This patch updates both the generated vault.rs and scripts/phase7.py,
then reruns Phase 7.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OLD_METHOD = "entry.delete_password()"
NEW_METHOD = "entry.delete_credential()"

TARGETS = [
    "src-tauri/src/vault.rs",
    "scripts/phase7.py",
]


def patch_file(relative_path: str) -> None:
    path = ROOT / relative_path

    if not path.exists():
        print(f"SKIP  {relative_path} not found")
        return

    text = path.read_text(encoding="utf-8")

    if OLD_METHOD in text:
        text = text.replace(OLD_METHOD, NEW_METHOD)
        path.write_text(text, encoding="utf-8")
        print(f"PATCH {relative_path}")
    else:
        print(f"OK    {relative_path} already patched or target method not found")


def main() -> int:
    print(f"Project root: {ROOT}")

    for target in TARGETS:
        patch_file(target)

    print("RUN  python3 scripts/phase7.py")

    subprocess.run(
        ["python3", str(ROOT / "scripts" / "phase7.py")],
        check=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
