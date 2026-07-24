#!/usr/bin/env python3
"""
Add a default User-Agent header to Chapar's Rust HTTP engine.

GitHub API often returns 403 Forbidden when no User-Agent header is present.
This patch makes Chapar send:

    User-Agent: Chapar/0.1

unless the user explicitly provides their own User-Agent header.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


OLD_IMPORT = "use reqwest::header::{HeaderMap, HeaderName, HeaderValue, CONTENT_TYPE};"
NEW_IMPORT = "use reqwest::header::{HeaderMap, HeaderName, HeaderValue, CONTENT_TYPE, USER_AGENT};"

OLD_MARKER = "    let mut body_text: Option<String> = None;"
NEW_BLOCK = """    if !header_map.contains_key(USER_AGENT) {
        header_map.insert(USER_AGENT, HeaderValue::from_static("Chapar/0.1"));
    }

    let mut body_text: Option<String> = None;"""


def patch_text(text: str) -> str:
    text = text.replace(OLD_IMPORT, NEW_IMPORT)

    if NEW_BLOCK not in text:
        text = text.replace(OLD_MARKER, NEW_BLOCK)

    return text


def patch_file(relative_path: str) -> None:
    path = ROOT / relative_path

    if not path.exists():
        print(f"SKIP  {relative_path} not found")
        return

    original = path.read_text(encoding="utf-8")
    updated = patch_text(original)

    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"PATCH {relative_path}")
    else:
        print(f"OK    {relative_path} already patched or no changes needed")


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

    patch_file("src-tauri/src/http.rs")
    patch_file("scripts/phase3.py")

    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nUser-Agent fix applied.")
    print("\nRestart the app:")
    print("  npm run tauri dev")
    print("\nThen test:")
    print("  https://api.github.com/repos/tauri-apps/tauri")
    print("\nExpected:")
    print("  Completed: 200")
    print("  Body Kind: json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())