#!/usr/bin/env python3
"""
Chapar Phase 1: Scaffolding and DB setup.

This script:
- verifies Phase 0 exists
- checks required tools
- checks Linux Tauri system libraries when on Linux
- installs frontend dependencies
- adds rusqlite to the Rust backend
- writes Phase 1 Rust database code
- writes a temporary frontend DB initialization test page
- generates placeholder PNG icons
- updates tauri.conf.json to use placeholder PNG icons
- runs frontend and Rust verification checks

This script uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path


PHASE1_FILES: dict[str, str] = {
"src-tauri/src/db.rs": """use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::Connection;
use tauri::Manager;

const MIGRATION: &str = include_str!("../migrations/001_initial.sql");

pub fn db_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|error| format!("failed to resolve app config directory: {error}"))?;

    fs::create_dir_all(&dir)
        .map_err(|error| format!("failed to create config directory {}: {error}", dir.display()))?;

    Ok(dir.join("chapar.db"))
}

pub fn open_connection(path: &Path) -> Result<Connection, String> {
    let connection = Connection::open(path)
        .map_err(|error| format!("failed to open database {}: {error}", path.display()))?;

    connection
        .execute_batch("PRAGMA foreign_keys = ON;")
        .map_err(|error| format!("failed to enable foreign keys: {error}"))?;

    Ok(connection)
}

pub fn migrate(connection: &Connection) -> Result<(), String> {
    connection
        .execute_batch(MIGRATION)
        .map_err(|error| format!("failed to apply database migration: {error}"))?;

    Ok(())
}

pub fn init_db_for_app(app: &tauri::AppHandle) -> Result<String, String> {
    let path = db_path(app)?;
    let connection = open_connection(&path)?;
    migrate(&connection)?;

    Ok(path.display().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn migration_creates_core_tables() {
        let connection = Connection::open_in_memory().unwrap();

        migrate(&connection).unwrap();

        let collections: i64 = connection
            .query_row("SELECT COUNT(*) FROM collections", [], |row| row.get(0))
            .unwrap();

        let requests: i64 = connection
            .query_row("SELECT COUNT(*) FROM requests", [], |row| row.get(0))
            .unwrap();

        let environments: i64 = connection
            .query_row("SELECT COUNT(*) FROM environments", [], |row| row.get(0))
            .unwrap();

        let secret_metadata: i64 = connection
            .query_row("SELECT COUNT(*) FROM secret_metadata", [], |row| row.get(0))
            .unwrap();

        assert_eq!(collections, 0);
        assert_eq!(requests, 0);
        assert_eq!(environments, 0);
        assert_eq!(secret_metadata, 0);
    }
}
""",

"src-tauri/src/commands/mod.rs": """pub mod db;
""",

"src-tauri/src/commands/db.rs": """use tauri::AppHandle;

#[tauri::command]
pub fn init_db(app: AppHandle) -> Result<String, String> {
    crate::db::init_db_for_app(&app)
}
""",

"src-tauri/src/main.rs": """#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod db;
mod error;
mod models;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle().clone();

            db::init_db_for_app(&handle)
                .map(|_| ())
                .map_err(|error| -> Box<dyn std::error::Error> { error.into() })
        })
        .invoke_handler(tauri::generate_handler![commands::db::init_db])
        .run(tauri::generate_context!())
        .expect("error while running Chapar");
}
""",

"src/routes/+page.svelte": """<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";

  let status = $state("Idle");
  let dbPath = $state<string | null>(null);
  let busy = $state(false);

  async function initDb() {
    busy = true;
    status = "Initializing database...";
    dbPath = null;

    try {
      const path = await invoke<string>("init_db");
      dbPath = path;
      status = "Database initialized.";
    } catch (error) {
      status = `Database initialization failed: ${String(error)}`;
    } finally {
      busy = false;
    }
  }
</script>

<main class="p-6">
  <h1 class="text-xl font-semibold">Chapar</h1>

  <p class="mt-2 text-sm text-neutral-400">
    Phase 1 database initialization test.
  </p>

  <button
    class="mt-4 rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
    onclick={initDb}
    disabled={busy}
  >
    Initialize DB
  </button>

  <p class="mt-4 text-sm" data-testid="status">
    {status}
  </p>

  {#if dbPath}
    <p class="mt-2 break-all text-xs text-neutral-400" data-testid="db-path">
      {dbPath}
    </p>
  {/if}
</main>
""",
}


REQUIRED_PHASE0_FILES = [
    "package.json",
    "svelte.config.js",
    "vite.config.ts",
    "tsconfig.json",
    "tailwind.config.js",
    "src/app.html",
    "src/app.css",
    "src/app.d.ts",
    "src/routes/+layout.ts",
    "src/routes/+layout.svelte",
    "src/routes/+page.svelte",
    "src/lib/types/api.ts",
    "src/lib/services/commands.ts",
    "src-tauri/Cargo.toml",
    "src-tauri/build.rs",
    "src-tauri/tauri.conf.json",
    "src-tauri/capabilities/default.json",
    "src-tauri/migrations/001_initial.sql",
    "src-tauri/src/main.rs",
    "src-tauri/src/error.rs",
    "src-tauri/src/models.rs",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = shlex.join([str(part) for part in command])
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def require_tools() -> None:
    required = [
        "node",
        "npm",
        "cargo",
        "rustc",
        "pkg-config",
    ]

    missing = []

    for tool in required:
        if shutil.which(tool) is None:
            missing.append(tool)

    has_compiler = (
        shutil.which("cc") is not None
        or shutil.which("gcc") is not None
        or shutil.which("clang") is not None
    )

    if not has_compiler:
        missing.append("C compiler: cc, gcc, or clang")

    if missing:
        print("Missing required tools:", file=sys.stderr)
        for tool in missing:
            print(f"  - {tool}", file=sys.stderr)

        print("\nOn Debian/Ubuntu, install at least:", file=sys.stderr)
        print("  sudo apt install build-essential pkg-config nodejs npm curl", file=sys.stderr)
        print("\nRust can be installed from:", file=sys.stderr)
        print("  https://rustup.rs/", file=sys.stderr)

        raise SystemExit(1)


def check_linux_tauri_system_libraries() -> None:
    if not sys.platform.startswith("linux"):
        return

    libraries = [
        "webkit2gtk-4.1",
        "gtk+-3.0",
        "libsoup-3.0",
        "javascriptcoregtk-4.1",
    ]

    missing = []

    for library in libraries:
        result = subprocess.run(
            ["pkg-config", "--exists", library],
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            missing.append(library)

    if not missing:
        print("OK    Linux Tauri system libraries detected")
        return

    print("Missing Linux Tauri system libraries:", file=sys.stderr)
    for library in missing:
        print(f"  - {library}", file=sys.stderr)

    print("\nDebian/Ubuntu:", file=sys.stderr)
    print(
        "  sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libsoup-3.0-dev libjavascriptcoregtk-4.1-dev",
        file=sys.stderr,
    )

    print("\nFedora:", file=sys.stderr)
    print(
        "  sudo dnf install webkit2gtk4.1-devel gtk3-devel libsoup3-devel javascriptcoregtk4.1-devel",
        file=sys.stderr,
    )

    print("\nArch:", file=sys.stderr)
    print(
        "  sudo pacman -S webkit2gtk gtk3 libsoup",
        file=sys.stderr,
    )

    raise SystemExit(1)


def verify_phase0(root: Path) -> None:
    missing = []

    for relative_path in REQUIRED_PHASE0_FILES:
        if not (root / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 0 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        print("\nRun Phase 0 first:", file=sys.stderr)
        print("  ./scripts/phase0.sh --root . --force", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 0 skeleton detected")


def write_phase1_files(root: Path) -> None:
    for relative_path, content in PHASE1_FILES.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def make_png(path: Path, size: int, rgba: tuple[int, int, int, int] = (15, 23, 42, 255)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        payload = chunk_type + data
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)

    ihdr_data = struct.pack(
        ">IIBBBBB",
        size,
        size,
        8,
        6,
        0,
        0,
        0,
    )

    scanline = b"\x00" + bytes(rgba) * size
    raw = scanline * size
    compressed = zlib.compress(raw, 9)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr_data)
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")

    path.write_bytes(png)
    print(f"WRITE {path}")


def generate_icons(root: Path) -> None:
    icons = root / "src-tauri" / "icons"

    make_png(icons / "32x32.png", 32)
    make_png(icons / "128x128.png", 128)
    make_png(icons / "icon.png", 512)


def update_tauri_config(root: Path) -> None:
    config_path = root / "src-tauri" / "tauri.conf.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    config.setdefault("bundle", {})
    config["bundle"]["active"] = False
    config["bundle"]["icon"] = [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/icon.png",
    ]

    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("WRITE src-tauri/tauri.conf.json")


def install_frontend_dependencies(root: Path) -> None:
    run(
        [
            "npm",
            "install",
            "--no-audit",
            "--no-fund",
            "--save-exact",
            "@tauri-apps/api@^2",
        ],
        cwd=root,
    )

    run(
        [
            "npm",
            "install",
            "--no-audit",
            "--no-fund",
            "--save-dev",
            "--save-exact",
            "@tauri-apps/cli@^2",
            "svelte@latest",
            "@sveltejs/kit@latest",
            "@sveltejs/adapter-static@latest",
            "@sveltejs/vite-plugin-svelte@latest",
            "typescript@^5.3.3",
            "svelte-check@latest",
            "vite@latest",
            "tailwindcss@latest",
            "@tailwindcss/vite@latest",
        ],
        cwd=root,
    )


def add_rust_dependencies(root: Path) -> None:
    run(
        [
            "cargo",
            "add",
            "rusqlite",
            "--features",
            "bundled",
        ],
        cwd=root / "src-tauri",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Chapar Phase 1: scaffolding and database setup."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory. Defaults to current directory.",
    )
    parser.add_argument(
        "--skip-system-check",
        action="store_true",
        help="Skip Linux Tauri system library checks.",
    )

    args = parser.parse_args()
    root = Path(args.root).resolve()

    print(f"Project root: {root}")

    require_tools()

    if not args.skip_system_check:
        check_linux_tauri_system_libraries()

    verify_phase0(root)
    install_frontend_dependencies(root)
    add_rust_dependencies(root)

    write_phase1_files(root)
    generate_icons(root)
    update_tauri_config(root)

    run(["npm", "run", "check"], cwd=root)
    run(["npm", "run", "build"], cwd=root)

    run(["cargo", "test"], cwd=root / "src-tauri")
    run(["cargo", "check"], cwd=root / "src-tauri")

    print("\nPHASE 1 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nThen click: Initialize DB")
    print("Expected UI result: Database initialized.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())