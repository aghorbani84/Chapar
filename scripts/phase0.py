#!/usr/bin/env python3
"""
Fix Phase 3 reqwest feature selection.

reqwest 0.13 no longer supports the old rustls-tls feature name.
It also requires explicit query and form features for .query() and .form().

This script patches scripts/phase3.py and reruns Phase 3.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def openssl_available() -> bool:
    if shutil.which("pkg-config") is None:
        return False

    result = subprocess.run(
        ["pkg-config", "--exists", "openssl"],
        capture_output=True,
        check=False,
    )

    return result.returncode == 0


def choose_features() -> str:
    forced = os.environ.get("CHAPAR_REQWEST_TLS", "auto").strip().lower()

    if forced == "rustls":
        return "json,query,form,rustls"

    if forced == "native-tls":
        return "json,query,form,native-tls"

    if openssl_available():
        return "json,query,form,native-tls"

    return "json,query,form,rustls"


def patch_phase3(features: str) -> None:
    phase3 = ROOT / "scripts" / "phase3.py"

    if not phase3.exists():
        print("ERROR: scripts/phase3.py not found", file=sys.stderr)
        raise SystemExit(1)

    text = phase3.read_text(encoding="utf-8")
    replacement = f'"{features}",'

    candidates = [
        '"json,rustls-tls",',
        '"json,native-tls",',
        '"json,rustls",',
        '"json,query,form,native-tls",',
        '"json,query,form,rustls",',
    ]

    patched = False

    for candidate in candidates:
        if candidate in text:
            text = text.replace(candidate, replacement)
            patched = True
            break

    if not patched:
        new_text = re.sub(
            r'"json,[^"]*",',
            replacement,
            text,
            count=1,
        )

        if new_text != text:
            text = new_text
            patched = True

    if not patched:
        print("ERROR: could not find reqwest feature line in scripts/phase3.py", file=sys.stderr)
        raise SystemExit(1)

    phase3.write_text(text, encoding="utf-8")
    print(f"PATCH scripts/phase3.py now uses reqwest features: {features}")


def main() -> int:
    features = choose_features()

    print(f"Selected reqwest features: {features}")

    if "native-tls" in features:
        print("Using native-tls. OpenSSL development files are required.")
        print("If the build fails, install libssl-dev or equivalent.")
    else:
        print("Using rustls.")
        print("If the build fails while compiling aws-lc-rs, install cmake and perl.")

    patch_phase3(features)

    print("RUN  python3 scripts/phase3.py")
    subprocess.run(
        ["python3", str(ROOT / "scripts" / "phase3.py")],
        check=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())