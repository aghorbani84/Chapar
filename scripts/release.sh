#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "${SCRIPT_DIR}")"

python3 "${ROOT}/scripts/final_check.py"

cd "${ROOT}"

echo "Starting Tauri production build..."
npm run tauri build -- "$@"
