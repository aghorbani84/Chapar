<script lang="ts">
  import { onMount } from "svelte";
  import { ShieldCheck, Trash2 } from "@lucide/svelte";
  import {
    deleteSecretById,
    loadSecrets,
    saveSecret,
    secretMetadata
  } from "$lib/stores/secrets";

  let secretId = $state("");
  let secretLabel = $state("");
  let secretValue = $state("");
  let status = $state("");
  let busy = $state(false);

  onMount(() => {
    loadSecrets();
  });

  async function storeSecret() {
    if (!secretId.trim() || secretValue === "") {
      return;
    }

    busy = true;
    status = "Storing secret...";

    try {
      await saveSecret(secretId.trim(), secretLabel.trim(), secretValue);

      status = "Secret stored in OS keychain.";
      secretValue = "";

      await loadSecrets();
    } catch (error) {
      status = String(error);
    } finally {
      busy = false;
    }
  }

  async function removeSecret(id: string) {
    if (typeof window !== "undefined" && !window.confirm("Delete this secret?")) {
      return;
    }

    busy = true;
    status = "Deleting secret...";

    try {
      await deleteSecretById(id);
      status = "Secret deleted.";
    } catch (error) {
      status = String(error);
    } finally {
      busy = false;
    }
  }
</script>

<div class="h-full overflow-y-auto p-6">
  <div class="mx-auto max-w-2xl">
    <div class="flex items-center gap-2">
      <ShieldCheck size={18} class="text-emerald-400" />
      <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-300">
        Secure Vault
      </h2>
    </div>

    <p class="mt-2 text-xs text-neutral-500">
      Secret values are stored in your OS keychain. Only secret IDs and labels are stored in SQLite.
    </p>

    <div class="mt-4 grid gap-3 rounded border border-neutral-800 p-4">
      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Secret ID, example: prod-api-key"
        bind:value={secretId}
      />

      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Label, optional"
        bind:value={secretLabel}
      />

      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        type="password"
        placeholder="Secret value"
        bind:value={secretValue}
      />

      <button
        class="rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={storeSecret}
        disabled={busy || secretId.trim() === "" || secretValue === ""}
      >
        Store Secret
      </button>

      <p class="text-xs text-neutral-400">{status}</p>
    </div>

    <div class="mt-6">
      {#each $secretMetadata as secret (secret.id)}
        <div class="mt-2 flex items-center gap-2 rounded border border-neutral-800 px-4 py-3">
          <div class="flex-1">
            <p class="text-sm">{secret.label}</p>
            <p class="mt-1 text-xs text-neutral-500">{secret.id}</p>
          </div>

          <button
            class="rounded border border-neutral-800 p-2 text-neutral-400 hover:text-red-400"
            onclick={() => removeSecret(secret.id)}
          >
            <Trash2 size={14} />
          </button>
        </div>
      {:else}
        <p class="mt-3 text-xs text-neutral-600">No secrets stored yet.</p>
      {/each}
    </div>
  </div>
</div>
