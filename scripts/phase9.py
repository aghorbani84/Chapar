#!/usr/bin/env python3
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
