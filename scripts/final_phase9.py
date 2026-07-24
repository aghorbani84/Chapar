#!/usr/bin/env python3
"""
Chapar Phase 9 Final: Production hardening, docs, README, icons, and release scripts.

This script is designed to avoid copy corruption:
- README.md is generated from safe HTML-style blocks.
- docs/chapar.html is generated as local documentation.
- No nested Markdown triple backticks are used inside this script.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


FINAL_CHECK_SCRIPT = r'''#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


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

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)
    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nFINAL CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


RELEASE_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "${SCRIPT_DIR}")"

python3 "${ROOT}/scripts/final_check.py"

cd "${ROOT}"

echo "Starting Tauri production build..."
npm run tauri build -- "$@"
'''


PHASE9_WRAPPER_PY = r'''#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "phase9_final.py")] + sys.argv[1:],
        check=False,
    )

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
'''


PHASE9_WRAPPER_SH = r'''#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 "${SCRIPT_DIR}/phase9_final.py" "$@"
'''


README_CONTENT = r'''# Chapar

Chapar is a local-first, security-focused desktop API client.

## Tech Stack

- Tauri v2
- Rust
- SvelteKit
- TypeScript
- Tailwind CSS
- Monaco Editor
- SQLite
- OS keychain via keyring

## Security Model

- HTTP requests are executed only from the Rust backend.
- Secrets are stored in the OS keychain.
- Secret values are not stored in SQLite.
- Secret values are not exported.
- Secret values are not returned to the normal frontend UI.
- Requests using unresolved or unauthorized variables are blocked before sending.

## Features

- Collections and saved requests
- SQLite persistence
- Environment variables
- Secret vault backed by OS keychain
- Secret injection into headers
- Request execution from Rust using reqwest
- Response inspector with Monaco Editor
- Request history
- Export and import for collections, requests, environments, and secret metadata

## Development

Start the app in development mode:

<pre>
npm run tauri dev
</pre>

## Final Verification

Run automated checks:

<pre>
python3 scripts/final_check.py
</pre>

## Production Build

Create a production bundle:

<pre>
./scripts/release.sh
</pre>

Create a faster debug bundle:

<pre>
./scripts/release.sh -- --debug
</pre>

## Production Secret Commands

The diagnostic commands get_secret and store_secret are not exposed to the frontend in production mode.

Secrets are managed through:

<pre>
save_secret
delete_secret
secret_exists
list_secret_metadata
</pre>

Secret values are injected only inside Rust during request execution.

## Documentation

A local HTML documentation file is generated at:

<pre>
docs/chapar.html
</pre>

Open it in a browser.
'''


HTML_CONTENT = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chapar Documentation</title>
  <style>
    body {
      margin: 0;
      background: #0a0a0a;
      color: #e5e5e5;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }

    main {
      max-width: 900px;
      margin: 0 auto;
      padding: 40px 20px;
    }

    h1, h2, h3 {
      color: #34d399;
    }

    pre {
      background: #171717;
      border: 1px solid #262626;
      border-radius: 8px;
      padding: 12px;
      overflow-x: auto;
      color: #d4d4d4;
    }

    code {
      color: #34d399;
    }

    .card {
      border: 1px solid #262626;
      border-radius: 12px;
      padding: 20px;
      margin: 20px 0;
      background: #111111;
    }

    .warning {
      border-color: #7c2d12;
      background: #1c1008;
      color: #fdba74;
    }
  </style>
</head>
<body>
  <main>
    <h1>Chapar</h1>

    <p>
      Chapar is a local-first, security-focused desktop API client built with
      Tauri v2, Rust, SvelteKit, TypeScript, Tailwind CSS, Monaco Editor, SQLite,
      and the OS keychain.
    </p>

    <div class="card">
      <h2>Security Model</h2>
      <ul>
        <li>HTTP requests are executed only from the Rust backend.</li>
        <li>Secrets are stored in the OS keychain.</li>
        <li>Secret values are not stored in SQLite.</li>
        <li>Secret values are not exported.</li>
        <li>Secret values are not returned to the normal frontend UI.</li>
        <li>Requests using unresolved or unauthorized variables are blocked before sending.</li>
      </ul>
    </div>

    <div class="card">
      <h2>Features</h2>
      <ul>
        <li>Collections and saved requests</li>
        <li>SQLite persistence</li>
        <li>Environment variables</li>
        <li>Secret vault backed by OS keychain</li>
        <li>Secret injection into headers</li>
        <li>Request execution from Rust using reqwest</li>
        <li>Response inspector with Monaco Editor</li>
        <li>Request history</li>
        <li>Export and import for collections, requests, environments, and secret metadata</li>
      </ul>
    </div>

    <div class="card">
      <h2>Development</h2>
      <p>Start the app in development mode:</p>
      <pre>npm run tauri dev</pre>
    </div>

    <div class="card">
      <h2>Final Verification</h2>
      <p>Run automated checks:</p>
      <pre>python3 scripts/final_check.py</pre>
    </div>

    <div class="card">
      <h2>Production Build</h2>
      <p>Create a production bundle:</p>
      <pre>./scripts/release.sh</pre>

      <p>Create a faster debug bundle:</p>
      <pre>./scripts/release.sh -- --debug</pre>
    </div>

    <div class="card warning">
      <h2>Production Secret Commands</h2>
      <p>
        The diagnostic commands <code>get_secret</code> and <code>store_secret</code>
        are not exposed to the frontend in production mode.
      </p>

      <p>Secrets are managed through:</p>
      <pre>save_secret
delete_secret
secret_exists
list_secret_metadata</pre>

      <p>
        Secret values are injected only inside Rust during request execution.
      </p>
    </div>
  </main>
</body>
</html>
'''


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def verify_phase8() -> None:
    required = [
        "package.json",
        "src/routes/+page.svelte",
        "src/lib/components/HistoryPanel.svelte",
        "src/lib/components/DataPanel.svelte",
        "src-tauri/src/main.rs",
        "src-tauri/src/db.rs",
        "src-tauri/src/http.rs",
        "src-tauri/src/commands/history.rs",
        "src-tauri/src/commands/data.rs",
    ]

    missing = []

    for relative_path in required:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 8 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 8 skeleton detected")


def remove_diagnostic_commands() -> None:
    path = ROOT / "src-tauri" / "src" / "main.rs"

    if not path.exists():
        print("SKIP  src-tauri/src/main.rs not found")
        return

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    filtered = [
        line
        for line in lines
        if "commands::secrets::store_secret" not in line
        and "commands::secrets::get_secret" not in line
    ]

    updated = "".join(filtered)

    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print("PATCH src-tauri/src/main.rs")
        print("      Removed public diagnostic commands: store_secret, get_secret")
    else:
        print("OK    src-tauri/src/main.rs already has diagnostic commands removed")


def make_png(path: Path, size: int = 1024) -> None:
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

    raw = bytearray()

    start = (10, 10, 10)
    end = (6, 95, 70)

    for y in range(size):
        t = y / max(1, size - 1)

        r = int(start[0] + (end[0] - start[0]) * t)
        g = int(start[1] + (end[1] - start[1]) * t)
        b = int(start[2] + (end[2] - start[2]) * t)

        raw.append(0)
        raw.extend(bytes((r, g, b, 255)) * size)

    compressed = zlib.compress(bytes(raw), 9)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr_data)
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    print(f"WRITE {path}")


def ensure_fallback_icons() -> None:
    icons_dir = ROOT / "src-tauri" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    make_png(icons_dir / "32x32.png", 32)
    make_png(icons_dir / "128x128.png", 128)
    make_png(icons_dir / "512x512.png", 512)
    make_png(icons_dir / "icon.png", 512)


def generate_icons(skip_icons: bool) -> None:
    if skip_icons:
        print("SKIP  icon generation")
        ensure_fallback_icons()
        return

    icon_source = ROOT / "app-icon.png"
    make_png(icon_source, 1024)

    try:
        run(["npx", "--no-install", "tauri", "icon", "app-icon.png"], cwd=ROOT)
    except Exception as error:
        print(f"WARN  Tauri icon generation failed: {error}")
        print("WARN  Falling back to generated PNG icons.")
        ensure_fallback_icons()


def update_tauri_config() -> None:
    config_path = ROOT / "src-tauri" / "tauri.conf.json"

    if not config_path.exists():
        print("SKIP  src-tauri/tauri.conf.json not found")
        return

    config = json.loads(config_path.read_text(encoding="utf-8"))

    bundle = config.setdefault("bundle", {})
    bundle["active"] = True

    icons_dir = ROOT / "src-tauri" / "icons"

    icons = []

    if icons_dir.exists():
        icons = sorted(
            f"icons/{item.name}"
            for item in icons_dir.iterdir()
            if item.suffix in {".png", ".ico", ".icns"}
        )

    if not icons:
        ensure_fallback_icons()

        icons = sorted(
            f"icons/{item.name}"
            for item in icons_dir.iterdir()
            if item.suffix in {".png", ".ico", ".icns"}
        )

    if icons:
        bundle["icon"] = icons

    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("WRITE src-tauri/tauri.conf.json")


def write_file(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    if executable:
        path.chmod(path.stat().st_mode | 0o111)

    print(f"WRITE {path.relative_to(ROOT)}")


def write_static_files() -> None:
    write_file(ROOT / "scripts" / "final_check.py", FINAL_CHECK_SCRIPT, True)
    write_file(ROOT / "scripts" / "release.sh", RELEASE_SCRIPT, True)
    write_file(ROOT / "scripts" / "phase9.py", PHASE9_WRAPPER_PY, True)
    write_file(ROOT / "scripts" / "phase9.sh", PHASE9_WRAPPER_SH, True)
    write_file(ROOT / "README.md", README_CONTENT)
    write_file(ROOT / "docs" / "chapar.html", HTML_CONTENT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chapar Phase 9 final production hardening script."
    )

    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip npm/cargo final checks.",
    )

    parser.add_argument(
        "--skip-icons",
        action="store_true",
        help="Skip Tauri icon generation and use fallback PNG icons.",
    )

    args = parser.parse_args()

    print(f"Project root: {ROOT}")

    verify_phase8()
    remove_diagnostic_commands()
    generate_icons(args.skip_icons)
    update_tauri_config()
    write_static_files()

    if not args.skip_checks:
        run([sys.executable, str(ROOT / "scripts" / "final_check.py")])
    else:
        print("SKIP  final checks")

    print("\nPHASE 9 FINAL PASSED")
    print("\nDevelopment mode:")
    print("  npm run tauri dev")
    print("\nFinal check:")
    print("  python3 scripts/final_check.py")
    print("\nProduction build:")
    print("  ./scripts/release.sh")
    print("\nDebug production bundle:")
    print("  ./scripts/release.sh -- --debug")
    print("\nDocumentation:")
    print("  docs/chapar.html")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
