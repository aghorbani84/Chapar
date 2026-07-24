#!/usr/bin/env python3
"""
Chapar Phase 4: Frontend UI and state.

This script:
- verifies Phase 3 files exist
- installs Monaco Editor and Lucide icons
- creates Svelte stores
- creates Monaco setup
- creates UI components
- replaces the temporary test page with the real Chapar layout
- runs frontend and Rust verification checks

This script uses only the Python standard library.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PHASE4_FILES: dict[str, str] = {
"src/lib/monaco/setup.ts": """import * as monaco from "monaco-editor";

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
""",

"src/lib/components/MonacoEditor.svelte": """<script lang="ts">
  import { onMount } from "svelte";
  import type { editor as MonacoEditor } from "monaco-editor";

  let {
    value = $bindable(""),
    language = "json",
    readOnly = false,
    height = "300px"
  }: {
    value: string;
    language?: string;
    readOnly?: boolean;
    height?: string;
  } = $props();

  let container = $state<HTMLDivElement | null>(null);
  let editor: MonacoEditor.IStandaloneCodeEditor | null = null;
  let monacoRef: any = null;
  let ignoreNextChange = false;

  onMount(() => {
    let disposed = false;
    let localEditor: MonacoEditor.IStandaloneCodeEditor | null = null;

    import("$lib/monaco/setup").then(({ monaco, setupMonaco }) => {
      monacoRef = monaco;
      setupMonaco();

      if (disposed || !container) {
        return;
      }

      localEditor = monaco.editor.create(container, {
        value,
        language,
        theme: "chapar-dark",
        readOnly,
        automaticLayout: true,
        minimap: {
          enabled: false
        },
        fontSize: 13,
        scrollBeyondLastLine: false,
        renderWhitespace: "boundary",
        tabSize: 2
      });

      editor = localEditor;

      localEditor.onDidChangeModelContent(() => {
        if (!localEditor) {
          return;
        }

        if (ignoreNextChange) {
          ignoreNextChange = false;
          return;
        }

        value = localEditor.getValue();
      });
    });

    return () => {
      disposed = true;
      localEditor?.dispose();
      editor = null;
      monacoRef = null;
    };
  });

  $effect(() => {
    if (!editor) {
      return;
    }

    if (editor.getValue() !== value) {
      ignoreNextChange = true;
      editor.setValue(value);
    }
  });

  $effect(() => {
    if (!editor || !monacoRef) {
      return;
    }

    const model = editor.getModel();

    if (model) {
      monacoRef.editor.setModelLanguage(model, language);
    }
  });

  $effect(() => {
    if (!editor) {
      return;
    }

    editor.updateOptions({
      readOnly
    });
  });
</script>

<div
  class="overflow-hidden rounded border border-neutral-800 bg-neutral-950"
  style="height: {height}"
  bind:this={container}
></div>
""",

"src/lib/stores/requestEditor.ts": """import { writable } from "svelte/store";
import type { HttpMethod, RequestBodyKind } from "$lib/types/api";

export interface RequestEditorState {
  method: HttpMethod;
  url: string;
  environmentId: string;
  bodyKind: RequestBodyKind;
  bodyText: string;
  timeoutMs: string;
  followRedirects: boolean;
}

function createRequestEditorStore() {
  const { subscribe, set, update } = writable<RequestEditorState>({
    method: "GET",
    url: "https://api.github.com/repos/tauri-apps/tauri",
    environmentId: "",
    bodyKind: "none",
    bodyText: "",
    timeoutMs: "",
    followRedirects: true
  });

  return {
    subscribe,
    set,
    update,
    patch(partial: Partial<RequestEditorState>) {
      update((current) => ({
        ...current,
        ...partial
      }));
    }
  };
}

export const requestEditor = createRequestEditorStore();
""",

"src/lib/stores/response.ts": """import { writable } from "svelte/store";
import type { ResponsePayload } from "$lib/types/api";

export interface ResponseState {
  busy: boolean;
  statusText: string;
  response: ResponsePayload | null;
}

function createResponseStore() {
  const { subscribe, set, update } = writable<ResponseState>({
    busy: false,
    statusText: "Idle",
    response: null
  });

  return {
    subscribe,
    set,
    update,
    start() {
      update((current) => ({
        ...current,
        busy: true,
        statusText: "Executing request..."
      }));
    },
    success(response: ResponsePayload) {
      update((current) => ({
        ...current,
        busy: false,
        response,
        statusText: response.error
          ? `Completed with error: ${response.error}`
          : `Completed: ${response.status} ${response.statusText}`
      }));
    },
    failure(error: unknown) {
      update((current) => ({
        ...current,
        busy: false,
        response: null,
        statusText: `Execution failed: ${String(error)}`
      }));
    },
    reset() {
      set({
        busy: false,
        statusText: "Idle",
        response: null
      });
    }
  };
}

export const responseStore = createResponseStore();
""",

"src/lib/stores/sidebar.ts": """import { writable } from "svelte/store";

export interface SidebarState {
  open: boolean;
}

function createSidebarStore() {
  const { subscribe, set, update } = writable<SidebarState>({
    open: true
  });

  return {
    subscribe,
    set,
    toggle() {
      update((current) => ({
        ...current,
        open: !current.open
      }));
    }
  };
}

export const sidebarStore = createSidebarStore();
""",

"src/lib/components/Sidebar.svelte": """<script lang="ts">
  import { Folder, Database, ShieldCheck, Send } from "@lucide/svelte";
  import { sidebarStore } from "$lib/stores/sidebar";

  let activeView = $state("requests");

  const items = [
    {
      id: "requests",
      label: "Requests",
      icon: Send
    },
    {
      id: "collections",
      label: "Collections",
      icon: Folder
    },
    {
      id: "environments",
      label: "Environments",
      icon: Database
    },
    {
      id: "secrets",
      label: "Secrets",
      icon: ShieldCheck
    }
  ];
</script>

<aside class="flex h-full w-56 flex-col border-r border-neutral-800 bg-neutral-950">
  <div class="border-b border-neutral-800 p-4">
    <p class="text-sm font-semibold tracking-wide">Chapar</p>
    <p class="mt-1 text-xs text-neutral-500">Local-first API client</p>
  </div>

  <nav class="flex-1 overflow-y-auto p-2">
    {#each items as item}
      <button
        class="mt-1 flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm transition-colors {activeView ===
        item.id
          ? "bg-neutral-800 text-white"
          : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"}"
        onclick={() => {
          activeView = item.id;
        }}
      >
        <item.icon size={16} />
        <span>{item.label}</span>
      </button>
    {/each}
  </nav>

  <div class="border-t border-neutral-800 p-3 text-xs text-neutral-600">
    Phase 4 UI skeleton
  </div>
</aside>
""",

"src/lib/components/RequestPane.svelte": """<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { Play, Loader2 } from "@lucide/svelte";
  import { get } from "svelte/store";
  import MonacoEditor from "$lib/components/MonacoEditor.svelte";
  import { requestEditor } from "$lib/stores/requestEditor";
  import { responseStore } from "$lib/stores/response";
  import type { HttpMethod, RequestBodyKind, RequestPayload, ResponsePayload } from "$lib/types/api";

  let method = $state<HttpMethod>("GET");
  let url = $state("https://api.github.com/repos/tauri-apps/tauri");
  let environmentId = $state("");
  let bodyKind = $state<RequestBodyKind>("none");
  let bodyText = $state("");
  let timeoutMs = $state("");

  requestEditor.subscribe((state) => {
    method = state.method;
    url = state.url;
    environmentId = state.environmentId;
    bodyKind = state.bodyKind;
    bodyText = state.bodyText;
    timeoutMs = state.timeoutMs;
  });

  function newId(): string {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
      return crypto.randomUUID();
    }

    return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function syncStore() {
    requestEditor.set({
      method,
      url,
      environmentId,
      bodyKind,
      bodyText,
      timeoutMs,
      followRedirects: true
    });
  }

  async function execute() {
    syncStore();
    responseStore.start();

    try {
      const now = new Date().toISOString();
      const timeoutValue = timeoutMs.trim() === "" ? null : Number(timeoutMs);

      const payload: RequestPayload = {
        request: {
          id: newId(),
          collectionId: null,
          name: "Untitled Request",
          method,
          url: url.trim(),
          params: [],
          headers: [],
          body: {
            kind: bodyKind,
            text: bodyText,
            form: []
          },
          allowedSecretIds: [],
          timeoutMs:
            timeoutValue !== null && Number.isFinite(timeoutValue)
              ? timeoutValue
              : null,
          followRedirects: true,
          position: 0,
          createdAt: now,
          updatedAt: now
        },
        environmentId: environmentId.trim() === "" ? null : environmentId.trim(),
        timeoutMs:
          timeoutValue !== null && Number.isFinite(timeoutValue)
            ? timeoutValue
            : null,
        followRedirects: true,
        maxRedirects: 10
      };

      const response = await invoke<ResponsePayload>("execute_request", {
        payload
      });

      responseStore.success(response);
    } catch (error) {
      responseStore.failure(error);
    }
  }
</script>

<section class="flex h-full flex-col">
  <div class="border-b border-neutral-800 p-4">
    <div class="flex gap-2">
      <select
        class="w-32 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        bind:value={method}
        onchange={syncStore}
      >
        <option>GET</option>
        <option>POST</option>
        <option>PUT</option>
        <option>PATCH</option>
        <option>DELETE</option>
        <option>HEAD</option>
        <option>OPTIONS</option>
      </select>

      <input
        class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="https://api.example.com"
        bind:value={url}
        onchange={syncStore}
      />

      <button
        class="flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={execute}
        disabled={url.trim() === ""}
      >
        {#if get(responseStore).busy}
          <Loader2 size={16} class="animate-spin" />
          Sending
        {:else}
          <Play size={16} />
          Send
        {/if}
      </button>
    </div>

    <div class="mt-3 grid gap-3 md:grid-cols-3">
      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Environment ID, optional"
        bind:value={environmentId}
        onchange={syncStore}
      />

      <select
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        bind:value={bodyKind}
        onchange={syncStore}
      >
        <option value="none">No Body</option>
        <option value="json">JSON</option>
        <option value="text">Text</option>
        <option value="raw">Raw</option>
      </select>

      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Timeout ms, optional"
        bind:value={timeoutMs}
        onchange={syncStore}
      />
    </div>
  </div>

  <div class="flex-1 overflow-hidden p-4">
    {#if bodyKind === "none"}
      <div class="flex h-full items-center justify-center rounded border border-dashed border-neutral-800 text-sm text-neutral-600">
        This request has no body.
      </div>
    {:else}
      <MonacoEditor
        bind:value={bodyText}
        language={bodyKind === "json" ? "json" : "plaintext"}
        height="100%"
      />
    {/if}
  </div>
</section>
""",

"src/lib/components/ResponsePane.svelte": """<script lang="ts">
  import { Clock, HardDrive, Activity, AlertTriangle } from "@lucide/svelte";
  import MonacoEditor from "$lib/components/MonacoEditor.svelte";
  import { responseStore } from "$lib/stores/response";

  let busy = $state(false);
  let statusText = $state("Idle");
  let response = $state<import("$lib/types/api").ResponsePayload | null>(null);

  responseStore.subscribe((state) => {
    busy = state.busy;
    statusText = state.statusText;
    response = state.response;
  });

  let responseBodyText = $derived(response?.body.text ?? response?.body.base64 ?? "");
  let responseLanguage = $derived(response?.body.kind === "json" ? "json" : "plaintext");
</script>

<section class="flex h-full flex-col border-t border-neutral-800 bg-neutral-950">
  <div class="flex flex-wrap items-center gap-4 border-b border-neutral-800 px-4 py-3 text-xs">
    <p class="font-semibold uppercase tracking-wide text-neutral-500">Response</p>

    <p class="flex items-center gap-1 text-neutral-300">
      <Activity size={14} />
      {statusText}
    </p>

    {#if response}
      <p class="flex items-center gap-1 text-neutral-400">
        <Clock size={14} />
        {response.latencyMs} ms
      </p>

      <p class="flex items-center gap-1 text-neutral-400">
        <HardDrive size={14} />
        {response.sizeBytes} bytes
      </p>
    {/if}
  </div>

  {#if response?.error}
    <div class="flex items-center gap-2 border-b border-red-900 bg-red-950/40 px-4 py-2 text-xs text-red-300">
      <AlertTriangle size={14} />
      {response.error}
    </div>
  {/if}

  {#if response && response.unresolvedVariables.length > 0}
    <div class="border-b border-amber-900 bg-amber-950/30 px-4 py-2 text-xs text-amber-300">
      Unresolved variables: {response.unresolvedVariables.join(", ")}
    </div>
  {/if}

  <div class="flex-1 overflow-hidden p-4">
    {#if busy}
      <div class="flex h-full items-center justify-center text-sm text-neutral-500">
        Waiting for response...
      </div>
    {:else if response}
      <MonacoEditor
        value={responseBodyText}
        language={responseLanguage}
        readOnly={true}
        height="100%"
      />
    {:else}
      <div class="flex h-full items-center justify-center text-sm text-neutral-600">
        Send a request to see the response.
      </div>
    {/if}
  </div>
</section>
""",

"src/routes/+page.svelte": """<script lang="ts">
  import Sidebar from "$lib/components/Sidebar.svelte";
  import RequestPane from "$lib/components/RequestPane.svelte";
  import ResponsePane from "$lib/components/ResponsePane.svelte";
</script>

<div class="flex h-screen w-screen overflow-hidden bg-neutral-950 text-neutral-100">
  <Sidebar />

  <div class="flex flex-1 flex-col overflow-hidden">
    <div class="flex-1 overflow-hidden">
      <RequestPane />
    </div>

    <div class="h-[38%] min-h-52">
      <ResponsePane />
    </div>
  </div>
</div>
""",
}


REQUIRED_PHASE3_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/http.rs",
    "src-tauri/src/env.rs",
    "src-tauri/src/commands/execute.rs",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def verify_phase3() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE3_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 3 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 3 skeleton detected")


def install_frontend_dependencies() -> None:
    run(
        [
            "npm",
            "install",
            "--no-audit",
            "--no-fund",
            "--save-exact",
            "monaco-editor@latest",
            "@lucide/svelte@latest",
        ],
        cwd=ROOT,
    )


def write_phase4_files() -> None:
    for relative_path, content in PHASE4_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase3()
    install_frontend_dependencies()
    write_phase4_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 4 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nExpected UI:")
    print("  - Left sidebar")
    print("  - Request editor in main panel")
    print("  - Response inspector in bottom panel")
    print("\nTest:")
    print("  1. Set URL to http://localhost:8080")
    print("  2. Start local server: python3 -m http.server 8080")
    print("  3. Click Send")
    print("  4. Confirm response appears in Monaco response panel")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())