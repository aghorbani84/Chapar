#!/usr/bin/env python3
"""
Attempt to fix local AppImage bundling for Chapar.

This script:
- patches build_release_packages.sh to use APPIMAGE_EXTRACT_AND_RUN=1
- removes possibly corrupted cached linuxdeploy tools
- makes any found linuxdeploy tools executable
- checks required Linux packaging tools
- rebuilds only the AppImage bundle with debug logging
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def patch_build_script() -> None:
    path = ROOT / "scripts" / "build_release_packages.sh"

    if not path.exists():
        print("SKIP  scripts/build_release_packages.sh not found")
        return

    text = path.read_text(encoding="utf-8")

    marker = 'npm run tauri build -- --bundles "${BUNDLES}"'

    replacement = """export APPIMAGE_EXTRACT_AND_RUN="${APPIMAGE_EXTRACT_AND_RUN:-1}"

npm run tauri build -- --bundles "${BUNDLES}"
"""

    if "APPIMAGE_EXTRACT_AND_RUN" in text:
        print("OK    build_release_packages.sh already exports APPIMAGE_EXTRACT_AND_RUN")
        return

    if marker not in text:
        print("SKIP  build command marker not found in build_release_packages.sh")
        return

    text = text.replace(marker, replacement)
    path.write_text(text, encoding="utf-8")

    print("PATCH scripts/build_release_packages.sh")


def clean_cached_tools() -> None:
    cache_dirs = [
        Path.home() / ".cache" / "tauri",
        ROOT / "src-tauri" / "target" / "tauri-tools",
    ]

    removed = False

    for cache_dir in cache_dirs:
        if not cache_dir.exists():
            continue

        for pattern in [
            "linuxdeploy*",
            "*linuxdeploy*",
            "AppRun",
            "*.AppImage",
            "linuxdeploy-plugin-gtk.sh",
            "linuxdeploy-plugin-gstreamer.sh",
        ]:
            for item in cache_dir.glob(pattern):
                if item.is_file():
                    item.unlink()
                    print(f"REMOVE {item}")
                    removed = True

    if not removed:
        print("OK    no cached linuxdeploy tools found to remove")


def chmod_cached_tools() -> None:
    search_roots = [
        Path.home() / ".cache",
        ROOT / "src-tauri" / "target",
    ]

    found = False

    for search_root in search_roots:
        if not search_root.exists():
            continue

        for item in search_root.rglob("linuxdeploy*"):
            if item.is_file():
                item.chmod(0o755)
                print(f"CHMOD  {item}")
                found = True

    if not found:
        print("OK    no existing linuxdeploy files found to chmod")


def check_tools() -> None:
    required = {
        "mksquashfs": "squashfs-tools",
        "desktop-file-validate": "desktop-file-utils",
        "patchelf": "patchelf",
        "file": "file",
    }

    missing = []

    for command, package in required.items():
        if shutil.which(command) is None:
            missing.append(package)

    if missing:
        print("Missing tools detected.")
        print("Install them with:")
        print()
        print("sudo dnf install -y " + " ".join(sorted(set(missing))))
        print()
    else:
        print("OK    required packaging tools detected")


def build_appimage() -> None:
    env = os.environ.copy()

    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    env["RUST_LOG"] = "tauri_bundler=debug"

    print("RUN  npm run tauri build -- --bundles appimage")

    result = subprocess.run(
        ["npm", "run", "tauri", "build", "--", "--bundles", "appimage"],
        cwd=ROOT,
        env=env,
        check=False,
    )

    if result.returncode == 0:
        print("\nAppImage build succeeded.")
        print("Artifact should be under:")
        print("  src-tauri/target/release/bundle/appimage/")
        return

    print("\nAppImage build failed.", file=sys.stderr)
    print("\nIf the log shows a missing library, install the corresponding package.", file=sys.stderr)
    print("\nYou can still publish DEB and RPM without AppImage:", file=sys.stderr)
    print("  ./scripts/upload_packages.sh", file=sys.stderr)
    print("\nOr rebuild/upload only DEB/RPM:", file=sys.stderr)
    print("  BUNDLES=deb,rpm ./scripts/build_release_packages.sh --skip-checks --upload", file=sys.stderr)

    raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix local AppImage bundling for Chapar."
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove cached linuxdeploy tools before rebuilding.",
    )

    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Patch and check tools, but do not rebuild AppImage.",
    )

    args = parser.parse_args()

    print(f"Project root: {ROOT}")

    patch_build_script()

    if args.clean:
        clean_cached_tools()

    chmod_cached_tools()
    check_tools()

    if args.skip_build:
        print("\nSkipping AppImage build.")
        return 0

    build_appimage()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
