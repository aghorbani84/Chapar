<script lang="ts">
  import { onMount } from "svelte";
  import {
    Database,
    FileText,
    Folder,
    HardDrive,
    History,
    Plus,
    Send,
    ShieldCheck,
    Trash2
  } from "@lucide/svelte";
  import { appView, type AppView } from "$lib/stores/ui";
  import {
    collections,
    createCollection,
    deleteCollectionById,
    loadCollections,
    selectedCollectionId
  } from "$lib/stores/collections";
  import {
    deleteRequestById,
    loadRequests,
    newRequest,
    requests,
    selectRequestById,
    selectedRequestId
  } from "$lib/stores/requests";

  let newCollectionName = $state("");

  const items: Array<{
    id: AppView;
    label: string;
    icon: any;
  }> = [
    {
      id: "requests",
      label: "Requests",
      icon: Send
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
    },
    {
      id: "history",
      label: "History",
      icon: History
    },
    {
      id: "data",
      label: "Data",
      icon: HardDrive
    }
  ];

  onMount(() => {
    loadCollections();

    const unsubscribe = selectedCollectionId.subscribe((collectionId) => {
      loadRequests(collectionId);
    });

    return unsubscribe;
  });

  async function onCreateCollection() {
    await createCollection(newCollectionName);
    newCollectionName = "";
  }

  async function onDeleteCollection(id: string) {
    if (typeof window !== "undefined" && !window.confirm("Delete this collection?")) {
      return;
    }

    await deleteCollectionById(id);
  }

  async function onDeleteRequest(id: string) {
    if (typeof window !== "undefined" && !window.confirm("Delete this request?")) {
      return;
    }

    await deleteRequestById(id);
  }
</script>

<aside class="flex h-full w-72 flex-col border-r border-neutral-800 bg-neutral-950">
  <div class="border-b border-neutral-800 p-4">
    <p class="text-sm font-semibold tracking-wide">Chapar</p>
    <p class="mt-1 text-xs text-neutral-500">Local-first API client</p>
  </div>

  <nav class="border-b border-neutral-800 p-2">
    {#each items as item}
      <button
        class="mt-1 flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm transition-colors {$appView ===
        item.id
          ? "bg-neutral-800 text-white"
          : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"}"
        onclick={() => appView.set(item.id)}
      >
        <item.icon size={16} />
        <span>{item.label}</span>
      </button>
    {/each}
  </nav>

  {#if $appView === "requests"}
    <div class="flex-1 overflow-y-auto p-3">
      <div class="flex gap-2">
        <input
          class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          placeholder="New collection"
          bind:value={newCollectionName}
        />

        <button
          class="rounded bg-emerald-600 px-3 py-2 text-white"
          onclick={onCreateCollection}
        >
          <Plus size={16} />
        </button>
      </div>

      <button
        class="mt-3 flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm {$selectedCollectionId ===
        null
          ? "bg-neutral-800 text-white"
          : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"}"
        onclick={() => selectedCollectionId.set(null)}
      >
        <FileText size={14} />
        All Requests
      </button>

      {#each $collections as collection (collection.id)}
        <div
          class="mt-1 flex items-center gap-1 rounded {$selectedCollectionId ===
          collection.id
            ? "bg-neutral-800"
            : "hover:bg-neutral-900"}"
        >
          <button
            class="flex flex-1 items-center gap-2 px-3 py-2 text-left text-sm"
            onclick={() => selectedCollectionId.set(collection.id)}
          >
            <Folder size={14} />
            <span class="truncate">{collection.name}</span>
          </button>

          <button
            class="p-2 text-neutral-500 hover:text-red-400"
            onclick={() => onDeleteCollection(collection.id)}
          >
            <Trash2 size={13} />
          </button>
        </div>
      {:else}
        <p class="mt-3 text-xs text-neutral-600">No collections yet.</p>
      {/each}

      <button
        class="mt-4 flex w-full items-center justify-center gap-2 rounded border border-neutral-700 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-900"
        onclick={newRequest}
      >
        <Plus size={14} />
        New Request
      </button>

      <div class="mt-3">
        {#each $requests as request (request.id)}
          <div
            class="mt-1 flex items-center gap-1 rounded {$selectedRequestId ===
            request.id
              ? "bg-neutral-800"
              : "hover:bg-neutral-900"}"
          >
            <button
              class="flex flex-1 items-center gap-2 px-3 py-2 text-left text-sm"
              onclick={() => selectRequestById(request.id)}
            >
              <span class="w-12 shrink-0 text-xs text-emerald-400">
                {request.method}
              </span>
              <span class="truncate">{request.name}</span>
            </button>

            <button
              class="p-2 text-neutral-500 hover:text-red-400"
              onclick={() => onDeleteRequest(request.id)}
            >
              <Trash2 size={13} />
            </button>
          </div>
        {:else}
          <p class="mt-3 text-xs text-neutral-600">No requests yet.</p>
        {/each}
      </div>
    </div>
  {:else}
    <div class="flex-1 p-3 text-xs text-neutral-600">
      Use the main panel for this section.
    </div>
  {/if}
</aside>
