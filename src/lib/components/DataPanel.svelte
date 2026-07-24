<script lang="ts">
  import { Copy, Download, Upload } from "@lucide/svelte";
  import { api } from "$lib/services/api";
  import type { ExportBundle } from "$lib/types/api";

  let exportedJson = $state("");
  let importText = $state("");
  let status = $state("");
  let busy = $state(false);

  async function exportData() {
    busy = true;
    status = "Exporting...";

    try {
      const bundle = await api.exportData();
      exportedJson = JSON.stringify(bundle, null, 2);
      status = "Export ready. Copy it and store it somewhere safe.";
    } catch (error) {
      status = String(error);
    } finally {
      busy = false;
    }
  }

  async function copyExport() {
    if (!exportedJson) {
      return;
    }

    try {
      await navigator.clipboard.writeText(exportedJson);
      status = "Copied to clipboard.";
    } catch {
      status = "Clipboard failed. Select and copy manually.";
    }
  }

  async function importData() {
    busy = true;
    status = "Importing...";

    try {
      const bundle = JSON.parse(importText) as ExportBundle;
      const summary = await api.importData(bundle);

      status = summary;
      importText = "";
    } catch (error) {
      status = String(error);
    } finally {
      busy = false;
    }
  }
</script>

<div class="h-full overflow-y-auto p-6">
  <div class="mx-auto max-w-3xl">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-300">
      Data Management
    </h2>

    <p class="mt-2 text-xs text-neutral-500">
      Export includes collections, requests, environments, and secret metadata. Secret values are not exported.
    </p>

    <div class="mt-4 rounded border border-neutral-800 p-4">
      <div class="flex gap-2">
        <button
          class="flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
          onclick={exportData}
          disabled={busy}
        >
          <Download size={14} />
          Export
        </button>

        <button
          class="flex items-center gap-2 rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-200 disabled:opacity-50"
          onclick={copyExport}
          disabled={busy || exportedJson === ""}
        >
          <Copy size={14} />
          Copy Export
        </button>
      </div>

      <textarea
        readonly
        class="mt-3 h-52 w-full rounded border border-neutral-700 bg-neutral-900 p-3 font-mono text-xs"
        placeholder="Exported JSON will appear here."
        value={exportedJson}
      ></textarea>
    </div>

    <div class="mt-6 rounded border border-neutral-800 p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Import
      </p>

      <textarea
        class="mt-3 h-52 w-full rounded border border-neutral-700 bg-neutral-900 p-3 font-mono text-xs"
        placeholder="Paste exported JSON here."
        bind:value={importText}
      ></textarea>

      <button
        class="mt-3 flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        onclick={importData}
        disabled={busy || importText.trim() === ""}
      >
        <Upload size={14} />
        Import
      </button>
    </div>

    <p class="mt-4 text-xs text-neutral-400">{status}</p>
  </div>
</div>
