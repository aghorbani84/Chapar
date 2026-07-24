<script lang="ts">
  import { onMount } from "svelte";
  import { CornerUpLeft, Trash2 } from "@lucide/svelte";
  import MonacoEditor from "$lib/components/MonacoEditor.svelte";
  import {
    clearAllHistory,
    historyEntries,
    loadHistory,
    selectedHistory
  } from "$lib/stores/history";
  import { requestEditor, requestToEditor } from "$lib/stores/requestEditor";
  import { appView } from "$lib/stores/ui";
  import type { HistoryEntry } from "$lib/types/api";

  let entries = $state<HistoryEntry[]>([]);
  let selected = $state<HistoryEntry | null>(null);
  let status = $state("");

  onMount(() => {
    loadHistory();

    const unsubscribeEntries = historyEntries.subscribe((value) => {
      entries = value;
    });

    const unsubscribeSelected = selectedHistory.subscribe((value) => {
      selected = value;
    });

    return () => {
      unsubscribeEntries();
      unsubscribeSelected();
    };
  });

  function selectEntry(entry: HistoryEntry) {
    selectedHistory.set(entry);
  }

  function loadIntoEditor(entry: HistoryEntry) {
    requestEditor.set(requestToEditor(entry.requestSnapshot));
    appView.set("requests");
  }

  async function clearHistory() {
    if (typeof window !== "undefined" && !window.confirm("Clear all history?")) {
      return;
    }

    try {
      await clearAllHistory();
      status = "History cleared.";
    } catch (error) {
      status = String(error);
    }
  }

  let responseBody = $derived(
    selected?.response?.body.text ?? selected?.response?.body.base64 ?? ""
  );

  let responseLanguage = $derived(
    selected?.response?.body.kind === "json" ? "json" : "plaintext"
  );
</script>

<div class="flex h-full overflow-hidden">
  <div class="w-96 overflow-y-auto border-r border-neutral-800 p-3">
    <div class="flex items-center justify-between">
      <p class="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        History
      </p>

      <button
        class="flex items-center gap-1 rounded border border-neutral-800 px-2 py-1 text-xs text-neutral-400 hover:text-red-400"
        onclick={clearHistory}
      >
        <Trash2 size={12} />
        Clear
      </button>
    </div>

    <p class="mt-2 text-xs text-neutral-500">{status}</p>

    <div class="mt-3">
      {#each entries as entry (entry.id)}
        <button
          class="mt-2 w-full rounded border border-neutral-800 p-3 text-left hover:bg-neutral-900 {selected?.id ===
          entry.id
            ? "bg-neutral-900"
            : ""}"
          onclick={() => selectEntry(entry)}
        >
          <div class="flex items-center gap-2">
            <span class="w-14 shrink-0 text-xs text-emerald-400">
              {entry.requestSnapshot.method}
            </span>

            <span class="text-xs text-neutral-400">
              {entry.status ?? "ERR"}
            </span>

            <span class="ml-auto text-xs text-neutral-600">
              {entry.latencyMs ?? 0} ms
            </span>
          </div>

          <p class="mt-1 truncate text-sm">
            {entry.requestSnapshot.url}
          </p>

          <p class="mt-1 text-xs text-neutral-600">
            {entry.createdAt}
          </p>
        </button>
      {:else}
        <p class="mt-3 text-xs text-neutral-600">No history yet.</p>
      {/each}
    </div>
  </div>

  <div class="flex flex-1 flex-col overflow-hidden p-4">
    {#if selected}
      <div class="flex items-center gap-2">
        <button
          class="flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white"
          onclick={() => {
      if (selected) {
        loadIntoEditor(selected);
      }
    }}
        >
          <CornerUpLeft size={14} />
          Load into Editor
        </button>

        <p class="text-xs text-neutral-500">
          {selected.requestSnapshot.method} {selected.requestSnapshot.url}
        </p>
      </div>

      {#if selected.response?.error}
        <p class="mt-3 text-xs text-red-400">
          {selected.response.error}
        </p>
      {/if}

      <div class="mt-3 flex-1 overflow-hidden">
        <MonacoEditor
          value={responseBody}
          language={responseLanguage}
          readOnly={true}
          height="100%"
        />
      </div>
    {:else}
      <div class="flex h-full items-center justify-center text-sm text-neutral-600">
        Select a history entry.
      </div>
    {/if}
  </div>
</div>
