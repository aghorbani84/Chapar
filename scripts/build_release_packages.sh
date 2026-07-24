#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${ROOT}"

UPLOAD=0
SKIP_CHECKS=0
BUNDLES="${BUNDLES:-deb,rpm}"

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
export APPIMAGE_EXTRACT_AND_RUN="${APPIMAGE_EXTRACT_AND_RUN:-1}"

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
