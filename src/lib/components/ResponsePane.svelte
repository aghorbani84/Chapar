<script lang="ts">
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
