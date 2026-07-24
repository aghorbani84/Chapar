<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "$lib/components/Sidebar.svelte";
  import RequestPane from "$lib/components/RequestPane.svelte";
  import ResponsePane from "$lib/components/ResponsePane.svelte";
  import EnvironmentsPanel from "$lib/components/EnvironmentsPanel.svelte";
  import SecretsPanel from "$lib/components/SecretsPanel.svelte";
  import HistoryPanel from "$lib/components/HistoryPanel.svelte";
  import DataPanel from "$lib/components/DataPanel.svelte";
  import { appView } from "$lib/stores/ui";
  import { loadEnvironments } from "$lib/stores/environments";
  import { loadSecrets } from "$lib/stores/secrets";

  onMount(() => {
    loadEnvironments();
    loadSecrets();
  });
</script>

<div class="flex h-screen w-screen overflow-hidden bg-neutral-950 text-neutral-100">
  <Sidebar />

  <div class="flex flex-1 flex-col overflow-hidden">
    {#if $appView === "requests"}
      <div class="flex-1 overflow-hidden">
        <RequestPane />
      </div>

      <div class="h-[38%] min-h-52">
        <ResponsePane />
      </div>
    {:else if $appView === "environments"}
      <EnvironmentsPanel />
    {:else if $appView === "secrets"}
      <SecretsPanel />
    {:else if $appView === "history"}
      <HistoryPanel />
    {:else if $appView === "data"}
      <DataPanel />
    {:else}
      <div class="flex h-full items-center justify-center text-sm text-neutral-600">
        Unknown view.
      </div>
    {/if}
  </div>
</div>
