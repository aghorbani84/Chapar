import * as monaco from "monaco-editor";

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
