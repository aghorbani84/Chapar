#!/usr/bin/env python3
"""
Fix Rust compile error in list_requests_conn.

The original code used a match expression with two different closures:

    Some(collection_id) => statement.query_map(params![collection_id], |row| ...)
    None => statement.query_map([], |row| ...)

Rust closures have unique types, so those match arms are incompatible.

This patch replaces that logic with a single nullable-parameter query:

    WHERE (?1 IS NULL OR collection_id = ?1)
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


OLD_BLOCK = '''    let sql = match collection_id {
        Some(_) => "SELECT id FROM requests WHERE collection_id = ?1 ORDER BY position, name",
        None => "SELECT id FROM requests ORDER BY position, name",
    };

    let mut statement = connection
        .prepare(sql)
        .map_err(|error| format!("failed to prepare requests query: {error}"))?;

    let rows = match collection_id {
        Some(collection_id) => statement.query_map(params![collection_id], |row| {
            row.get::<_, String>(0)
        }),
        None => statement.query_map([], |row| row.get::<_, String>(0)),
    }
    .map_err(|error| format!("failed to query requests: {error}"))?;
'''


NEW_BLOCK = '''    let mut statement = connection
        .prepare(
            "SELECT id FROM requests
             WHERE (?1 IS NULL OR collection_id = ?1)
             ORDER BY position, name",
        )
        .map_err(|error| format!("failed to prepare requests query: {error}"))?;

    let rows = statement
        .query_map(params![collection_id], |row| row.get::<_, String>(0))
        .map_err(|error| format!("failed to query requests: {error}"))?;
'''


TARGETS = [
    "src-tauri/src/db.rs",
    "scripts/phase6.py",
]


def patch_file(relative_path: str) -> None:
    path = ROOT / relative_path

    if not path.exists():
        print(f"SKIP  {relative_path} not found")
        return

    text = path.read_text(encoding="utf-8")

    if OLD_BLOCK in text:
        text = text.replace(OLD_BLOCK, NEW_BLOCK)
        path.write_text(text, encoding="utf-8")
        print(f"PATCH {relative_path}")
    else:
        print(f"OK    {relative_path} already patched or target block not found")


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def main() -> int:
    print(f"Project root: {ROOT}")

    for target in TARGETS:
        patch_file(target)

    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nRust list_requests fix passed.")
    print("\nNow rerun Phase 7:")
    print("  ./scripts/phase7.sh")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
