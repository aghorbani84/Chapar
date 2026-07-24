#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${ROOT}"

REPO_NAME="${REPO_NAME:-$(basename "${ROOT}")}"

echo "Project root: ${ROOT}"
echo "Repository name: ${REPO_NAME}"

python3 - <<'PY'
from pathlib import Path

workflow = Path(".github/workflows/release.yml")

if workflow.exists():
    text = workflow.read_text(encoding="utf-8")
    original = text

    text = text.replace(
        "--bundles deb,rpm,appimage",
        "--bundles deb,rpm",
    )

    lines = text.splitlines()
    lines = [
        line
        for line in lines
        if "appimage/*.AppImage" not in line
    ]

    text = "\n".join(lines) + "\n"

    if text != original:
        workflow.write_text(text, encoding="utf-8")
        print("PATCH .github/workflows/release.yml")
    else:
        print("OK    .github/workflows/release.yml already has no AppImage")
else:
    print("SKIP  .github/workflows/release.yml not found")
PY

python3 - <<'PY'
from pathlib import Path

build_script = Path("scripts/build_release_packages.sh")

if build_script.exists():
    text = build_script.read_text(encoding="utf-8")
    original = text

    text = text.replace(
        'BUNDLES="${BUNDLES:-deb,rpm,appimage}"',
        'BUNDLES="${BUNDLES:-deb,rpm}"',
    )

    if text != original:
        build_script.write_text(text, encoding="utf-8")
        print("PATCH scripts/build_release_packages.sh")
    else:
        print("OK    scripts/build_release_packages.sh already defaults to deb,rpm")
else:
    print("SKIP  scripts/build_release_packages.sh not found")
PY

if [ -n "$(git status --porcelain)" ]; then
  echo "Committing current changes..."
  git add -A
  git commit -m "Release Chapar v0.1.0 (DEB/RPM only)"
else
  echo "OK    working tree clean"
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI is required."
  echo "Install it with:"
  echo ""
  echo "  sudo dnf install -y gh"
  echo ""
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "You are not logged in to GitHub CLI."
  echo "Run:"
  echo ""
  echo "  gh auth login"
  echo ""
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  if [ "${CREATE_REPO:-}" = "private" ] || [ "${CREATE_REPO:-}" = "public" ]; then
    echo "Creating GitHub repository: ${REPO_NAME} (${CREATE_REPO})"
    gh repo create "${REPO_NAME}" --"${CREATE_REPO}" --source=. --remote=origin --push
  else
    echo "No git remote named origin found."
    echo ""
    echo "Run one of these:"
    echo ""
    echo "  CREATE_REPO=private ./scripts/push_github_no_appimage.sh"
    echo "  CREATE_REPO=public ./scripts/push_github_no_appimage.sh"
    echo ""
    echo "Or add a remote manually:"
    echo ""
    echo "  git remote add origin https://github.com/YOUR_USERNAME/chapar.git"
    echo "  git push -u origin master"
    echo ""
    exit 1
  fi
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "Pushing branch: ${BRANCH}"
git push -u origin "${BRANCH}"

shopt -s nullglob

assets=(
  src-tauri/target/release/bundle/deb/*.deb
  src-tauri/target/release/bundle/rpm/*.rpm
)

if [ ${#assets[@]} -eq 0 ]; then
  echo "No DEB/RPM artifacts found. Building them now..."
  BUNDLES=deb,rpm ./scripts/build_release_packages.sh --skip-checks

  assets=(
    src-tauri/target/release/bundle/deb/*.deb
    src-tauri/target/release/bundle/rpm/*.rpm
  )
fi

if [ ${#assets[@]} -eq 0 ]; then
  echo "ERROR: no DEB or RPM artifacts found after build."
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

echo "Creating GitHub release: ${tag}"

gh release create "${tag}" --generate-notes --title "${tag}" || true

echo "Uploading artifacts:"
printf '%s\n' "${assets[@]}"

gh release upload "${tag}" "${assets[@]}" --clobber

echo ""
echo "Done."
echo "GitHub release ${tag} now contains DEB and RPM packages."
