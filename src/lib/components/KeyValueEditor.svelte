<script lang="ts">
  import { Plus, Trash2 } from "@lucide/svelte";
  import { newId } from "$lib/utils/id";
  import type { KeyValueEntry, SecretMetadata } from "$lib/types/api";

  let {
    entries = [],
    onChange,
    secrets = []
  }: {
    entries: KeyValueEntry[];
    onChange: (entries: KeyValueEntry[]) => void;
    secrets?: SecretMetadata[];
  } = $props();

  function addEntry() {
    onChange([
      ...entries,
      {
        id: newId(),
        key: "",
        value: "",
        enabled: true,
        secretId: null
      }
    ]);
  }

  function removeEntry(id: string) {
    onChange(entries.filter((entry) => entry.id !== id));
  }

  function updateEntry(id: string, patch: Partial<KeyValueEntry>) {
    onChange(
      entries.map((entry) =>
        entry.id === id
          ? {
              ...entry,
              ...patch
            }
          : entry
      )
    );
  }

  function onKey(id: string, event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    updateEntry(id, { key: target.value });
  }

  function onValue(id: string, event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    updateEntry(id, { value: target.value });
  }

  function onEnabled(id: string, event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    updateEntry(id, { enabled: target.checked });
  }

  function onSecret(id: string, event: Event) {
    const target = event.currentTarget as HTMLSelectElement;
    const value = target.value;

    updateEntry(id, {
      secretId: value === "" ? null : value
    });
  }
</script>

<div class="space-y-2">
  {#each entries as entry (entry.id)}
    <div class="flex items-center gap-2">
      <input
        type="checkbox"
        class="h-4 w-4"
        checked={entry.enabled}
        onchange={(event) => onEnabled(entry.id, event)}
      />

      <input
        class="w-1/4 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Key"
        value={entry.key}
        oninput={(event) => onKey(entry.id, event)}
      />

      <input
        class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm disabled:opacity-50"
        placeholder={entry.secretId ? "Injected from secret" : "Value"}
        value={entry.value}
        disabled={entry.secretId !== null}
        oninput={(event) => onValue(entry.id, event)}
      />

      <select
        class="w-44 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        value={entry.secretId ?? ""}
        onchange={(event) => onSecret(entry.id, event)}
      >
        <option value="">No secret</option>

        {#if entry.secretId && !secrets.some((secret) => secret.id === entry.secretId)}
          <option value={entry.secretId}>{entry.secretId}</option>
        {/if}

        {#each secrets as secret (secret.id)}
          <option value={secret.id}>{secret.label}</option>
        {/each}
      </select>

      <button
        class="rounded border border-neutral-800 p-2 text-neutral-400 hover:text-red-400"
        onclick={() => removeEntry(entry.id)}
      >
        <Trash2 size={14} />
      </button>
    </div>
  {:else}
    <p class="text-xs text-neutral-600">No entries.</p>
  {/each}

  <button
    class="flex items-center gap-1 rounded border border-neutral-800 px-3 py-1 text-xs text-neutral-300 hover:bg-neutral-900"
    onclick={addEntry}
  >
    <Plus size={14} />
    Add
  </button>
</div>
