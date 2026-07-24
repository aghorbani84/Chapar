#!/usr/bin/env python3
"""
Create GitHub Release build pipeline for Chapar.

This writes:
- .github/workflows/release.yml
- scripts/build_release_packages.sh

The workflow builds DEB, RPM, and AppImage packages on Ubuntu
and uploads them to GitHub Releases when a tag is pushed.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


WORKFLOW = r'''name: Release

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  linux:
    runs-on: ubuntu-22.04

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install Rust stable
        run: |
          rustup toolchain install stable --profile minimal
          rustup default stable
          rustc --version
          cargo --version

      - name: Cache Cargo artifacts
        uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            src-tauri/target
          key: ${{ runner.os }}-cargo-${{ hashFiles('src-tauri/Cargo.lock') }}
          restore-keys: |
            ${{ runner.os }}-cargo-

      - name: Install Linux dependencies
        run: |
          sudo apt update
          sudo apt install -y \
            build-essential \
            curl \
            wget \
            file \
            pkg-config \
            libssl-dev \
            libgtk-3-dev \
            librsvg2-dev \
            patchelf \
            libfuse2 \
            dpkg \
            rpm \
            libwebkit2gtk-4.1-dev \
            libjavascriptcoregtk-4.1-dev \
            libsoup-3.0-dev

      - name: Install Node dependencies
        run: |
          if [ -f package-lock.json ]; then
            npm ci
          else
            npm install
          fi

      - name: Prepare Tauri icons and production config
        run: |
          python3 scripts/phase9_final.py --skip-checks

      - name: Build Linux bundles
        run: |
          npm run tauri build -- --bundles deb,rpm,appimage

      - name: Create GitHub release and upload assets
        if: github.ref_type == 'tag'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          shopt -s nullglob

          tag="${GITHUB_REF_NAME}"

          gh release create "$tag" --generate-notes --title "$tag" || true

          assets=(
            src-tauri/target/release/bundle/deb/*.deb
            src-tauri/target/release/bundle/rpm/*.rpm
            src-tauri/target/release/bundle/appimage/*.AppImage
          )

          if [ ${#assets[@]} -gt 0 ]; then
            gh release upload "$tag" "${assets[@]}" --clobber
          else
            echo "No bundle artifacts found."
            exit 1
          fi
'''


BUILD_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${ROOT}"

UPLOAD=0
SKIP_CHECKS=0
BUNDLES="${BUNDLES:-deb,rpm,appimage}"

for arg in "$@"; do
  case "$arg" in
    --upload)
      UPLOAD=1
      ;;
    --skip-checks)
      SKIP_CHECKS=1
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: ./scripts/build_release_packages.sh [--skip-checks] [--upload]"
      exit 1
      ;;
  esac
done

if [ "${SKIP_CHECKS}" -eq 0 ]; then
  python3 scripts/final_check.py
fi

echo "Building bundles: ${BUNDLES}"
npm run tauri build -- --bundles "${BUNDLES}"

echo ""
echo "Generated artifacts:"
find src-tauri/target/release/bundle \
  -type f \
  \( \
    -name "*.deb" \
    -o -name "*.rpm" \
    -o -name "*.AppImage" \
  \)

if [ "${UPLOAD}" -eq 1 ]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI is required for --upload."
    echo "Install it with:"
    echo "  sudo dnf install gh"
    echo "Then run:"
    echo "  gh auth login"
    exit 1
  fi

  if ! gh auth status >/dev/null 2>&1; then
    echo "You are not authenticated with GitHub CLI."
    echo "Run:"
    echo "  gh auth login"
    exit 1
  fi

  version="$(python3 - <<'PY'
import json
from pathlib import Path

tauri_conf = Path("src-tauri/tauri.conf.json")
package_conf = Path("package.json")

if tauri_conf.exists():
    data = json.loads(tauri_conf.read_text(encoding="utf-8"))
    version = data.get("version")
    if version:
        print(version)
        raise SystemExit(0)

if package_conf.exists():
    data = json.loads(package_conf.read_text(encoding="utf-8"))
    version = data.get("version")
    if version:
        print(version)
        raise SystemExit(0)

print("0.0.0")
PY
)"

  tag="v${version}"

  echo ""
  echo "Preparing GitHub release: ${tag}"

  gh release create "${tag}" --generate-notes --title "${tag}" || true

  shopt -s nullglob

  assets=(
    src-tauri/target/release/bundle/deb/*.deb
    src-tauri/target/release/bundle/rpm/*.rpm
    src-tauri/target/release/bundle/appimage/*.AppImage
  )

  if [ ${#assets[@]} -gt 0 ]; then
    gh release upload "${tag}" "${assets[@]}" --clobber
    echo ""
    echo "Uploaded artifacts to GitHub release ${tag}."
  else
    echo ""
    echo "No DEB, RPM, or AppImage artifacts found to upload."
    exit 1
  fi
fi
'''


def write_file(relative_path: str, content: str, executable: bool = False) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    if executable:
        path.chmod(path.stat().st_mode | 0o111)

    print(f"WRITE {relative_path}")


def main() -> int:
    print(f"Project root: {ROOT}")

    write_file(".github/workflows/release.yml", WORKFLOW)
    write_file("scripts/build_release_packages.sh", BUILD_SCRIPT, True)

    print("\nRelease pipeline files created.")
    print("\nNext steps:")
    print("  1. Commit the new files.")
    print("  2. Build locally:")
    print("       ./scripts/build_release_packages.sh")
    print("  3. Upload locally:")
    print("       ./scripts/build_release_packages.sh --upload")
    print("  4. Or create a GitHub release using Actions:")
    print("       git tag v0.1.0")
    print("       git push origin v0.1.0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
