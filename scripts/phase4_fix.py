#!/usr/bin/env python3
"""
Fix Monaco worker resolution for Vite 8 / Rolldown by using explicit relative
worker paths from src/lib/monaco/setup.ts to node_modules.

This script:
- rewrites src/lib/monaco/setup.ts
- patches scripts/phase4.py so future Phase 4 runs remain fixed
- reruns Phase 4 checks
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


NEW_MONACO_SETUP = """import * as monaco from "monaco-editor";

import editorWorker from "../../../node_modules/monaco-editor/esm/vs/editor/editor.worker.js?worker";
import jsonWorker from "../../../node_modules/monaco-editor/esm/vs/language/json/json.worker.js?worker";

let configured = false;

export function setupMonaco(): void {
  if (configured) {
    return;
  }

  (globalThis as any).MonacoEnvironment = {
    getWorker(_: unknown, label: string) {
      if (label === "json") {
        return new jsonWorker();
      }

      return new editorWorker();
    }
  };

  monaco.editor.defineTheme("chapar-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#0a0a0a",
      "editor.lineHighlightBackground": "#171717",
      "editorLineNumber.foreground": "#525252",
      "editorCursor.foreground": "#34d399"
    }
  });

  configured = true;
}

export { monaco };
"""


MONACO_TYPE_DECLARATIONS = """declare module "*?worker" {
  const workerConstructor: {
    new (): Worker;
  };

  export default workerConstructor;
}

declare module "monaco-editor/min/vs/editor/editor.main.css";
"""


def patch_phase4_script() -> bool:
    path = ROOT / "scripts" / "phase4.py"

    if not path.exists():
        print("SKIP  scripts/phase4.py not found")
        return False

    text = path.read_text(encoding="utf-8")

    pattern = re.compile(
        r'"src/lib/monaco/setup\.ts": """.*?""",\n\n"src/lib/components/MonacoEditor\.svelte"',
        re.DOTALL,
    )

    replacement = (
        '"src/lib/monaco/setup.ts": """'
        + NEW_MONACO_SETUP
        + '""",\n\n"src/lib/components/MonacoEditor.svelte"'
    )

    updated = pattern.sub(lambda _: replacement, text, count=1)

    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print("PATCH scripts/phase4.py")
    else:
        print("OK    scripts/phase4.py already patched or pattern not found")

    return (
        "../../../node_modules/monaco-editor/esm/vs/editor/editor.worker.js?worker"
        in updated
    )


def patch_generated_files() -> None:
    setup_path = ROOT / "src" / "lib" / "monaco" / "setup.ts"
    setup_path.parent.mkdir(parents=True, exist_ok=True)
    setup_path.write_text(NEW_MONACO_SETUP, encoding="utf-8")
    print("WRITE src/lib/monaco/setup.ts")

    declarations_path = ROOT / "src" / "monaco.d.ts"
    declarations_path.write_text(MONACO_TYPE_DECLARATIONS, encoding="utf-8")
    print("WRITE src/monaco.d.ts")


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

    phase4_fixed = patch_phase4_script()
    patch_generated_files()

    if phase4_fixed:
        print("RUN  python3 scripts/phase4.py")
        subprocess.run(
            ["python3", str(ROOT / "scripts" / "phase4.py")],
            check=True,
        )
    else:
        print("WARN  scripts/phase4.py could not be fully patched.")
        print("WARN  Running checks against the patched generated files only.")

        run(["npm", "run", "check"], cwd=ROOT)
        run(["npm", "run", "build"], cwd=ROOT)
        run(["cargo", "check"], cwd=ROOT / "src-tauri")

        print("\nPHASE 4 Monaco relative-worker fix checks passed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())