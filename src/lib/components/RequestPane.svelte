<script lang="ts">
  import { onMount } from "svelte";
  import { Loader2, Play, Plus, Save, Trash2 } from "@lucide/svelte";
  import { get } from "svelte/store";
  import MonacoEditor from "$lib/components/MonacoEditor.svelte";
  import KeyValueEditor from "$lib/components/KeyValueEditor.svelte";
  import { requestEditor, editorToRequest, newRequestDraft } from "$lib/stores/requestEditor";
  import { responseStore } from "$lib/stores/response";
  import {
    activeEnvironmentId,
    environments,
    loadEnvironments
  } from "$lib/stores/environments";
  import { selectedCollectionId } from "$lib/stores/collections";
  import { loadRequests, selectedRequestId } from "$lib/stores/requests";
  import { loadSecrets, secretMetadata } from "$lib/stores/secrets";
  import { api } from "$lib/services/api";
  import type {
    HttpMethod,
    KeyValueEntry,
    RequestBodyKind,
    RequestPayload
  } from "$lib/types/api";

  let name = $state("New Request");
  let method = $state<HttpMethod>("GET");
  let url = $state("http://localhost:8080");
  let environmentId = $state("");
  let bodyKind = $state<RequestBodyKind>("none");
  let bodyText = $state("");
  let timeoutMs = $state("");
  let headers = $state<KeyValueEntry[]>([]);
  let saveStatus = $state("");

  onMount(() => {
    loadEnvironments();
    loadSecrets();

    const unsubscribe = requestEditor.subscribe((state) => {
      name = state.name;
      method = state.method;
      url = state.url;
      environmentId = state.environmentId;
      bodyKind = state.bodyKind;
      bodyText = state.bodyText;
      timeoutMs = state.timeoutMs;
      headers = state.headers;
    });

    return unsubscribe;
  });

  function syncStore() {
    requestEditor.update((current) => ({
      ...current,
      name,
      method,
      url,
      environmentId,
      bodyKind,
      bodyText,
      timeoutMs,
      headers
    }));
  }

  $effect(() => {
    bodyText;
    syncStore();
  });

  function newDraft() {
    requestEditor.set(newRequestDraft(get(selectedCollectionId)));
    selectedRequestId.set(null);
    saveStatus = "";
  }

  async function save() {
    syncStore();

    try {
      const state = get(requestEditor);
      const request = editorToRequest(state);

      const saved = await api.saveRequest({ request });

      requestEditor.update((current) => ({
        ...current,
        id: saved.id,
        name: saved.name,
        collectionId: saved.collectionId,
        position: saved.position,
        createdAt: saved.createdAt,
        updatedAt: saved.updatedAt
      }));

      selectedRequestId.set(saved.id);
      await loadRequests(saved.collectionId);

      saveStatus = "Saved.";
    } catch (error) {
      saveStatus = String(error);
    }
  }

  async function remove() {
    syncStore();

    const state = get(requestEditor);

    if (!state.id) {
      return;
    }

    if (typeof window !== "undefined" && !window.confirm("Delete this request?")) {
      return;
    }

    try {
      await api.deleteRequest(state.id);

      if (get(selectedRequestId) === state.id) {
        selectedRequestId.set(null);
      }

      requestEditor.set(newRequestDraft(get(selectedCollectionId)));
      await loadRequests(get(selectedCollectionId));

      saveStatus = "Deleted.";
    } catch (error) {
      saveStatus = String(error);
    }
  }

  async function execute() {
    syncStore();
    responseStore.start();

    try {
      const state = get(requestEditor);
      const request = editorToRequest(state);

      const selectedEnvironmentId =
        state.environmentId.trim() === ""
          ? get(activeEnvironmentId)
          : state.environmentId.trim();

      const payload: RequestPayload = {
        request,
        environmentId: selectedEnvironmentId,
        timeoutMs: request.timeoutMs,
        followRedirects: request.followRedirects,
        maxRedirects: 10
      };

      const response = await api.executeRequest(payload);
      responseStore.success(response);
    } catch (error) {
      responseStore.failure(error);
    }
  }
</script>

<section class="flex h-full flex-col">
  <div class="border-b border-neutral-800 p-4">
    <div class="flex gap-2">
      <input
        class="w-64 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Request name"
        bind:value={name}
        onchange={syncStore}
      />

      <button
        class="flex items-center gap-2 rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-200 hover:bg-neutral-900"
        onclick={newDraft}
      >
        <Plus size={14} />
        New
      </button>

      <button
        class="flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white"
        onclick={save}
      >
        <Save size={14} />
        Save
      </button>

      <button
        class="flex items-center gap-2 rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:text-red-400"
        onclick={remove}
      >
        <Trash2 size={14} />
        Delete
      </button>

      <p class="ml-auto self-center text-xs text-neutral-500">{saveStatus}</p>
    </div>

    <div class="mt-3 flex gap-2">
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
        placeholder="https://api.example.com or use environment variables"
        bind:value={url}
        onchange={syncStore}
      />

      <button
        class="flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={execute}
        disabled={url.trim() === "" || $responseStore.busy}
      >
        {#if $responseStore.busy}
          <Loader2 size={16} class="animate-spin" />
          Sending
        {:else}
          <Play size={16} />
          Send
        {/if}
      </button>
    </div>

    <div class="mt-3 grid gap-3 md:grid-cols-3">
      <select
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        bind:value={environmentId}
        onchange={syncStore}
      >
        <option value="">Active environment</option>
        {#each $environments as environment (environment.id)}
          <option value={environment.id}>{environment.name}</option>
        {/each}
      </select>

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

    {#if $activeEnvironmentId}
      <p class="mt-2 text-xs text-neutral-500">
        Active environment ID: {$activeEnvironmentId}
      </p>
    {/if}
  </div>

  <div class="border-b border-neutral-800 p-4">
    <p class="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
      Headers
    </p>

    <KeyValueEditor
      entries={headers}
      secrets={$secretMetadata}
      onChange={(next) => {
        headers = next;
        syncStore();
      }}
    />
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
