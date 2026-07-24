<script lang="ts">
  import { onMount } from "svelte";
  import { Check, Plus, Save, Trash2 } from "@lucide/svelte";
  import {
    activeEnvironmentId,
    createEmptyEnvironment,
    deleteEnvironment,
    environments,
    loadEnvironments,
    saveEnvironment,
    setActiveEnvironment
  } from "$lib/stores/environments";
  import { newId } from "$lib/utils/id";
  import type { Environment, EnvironmentVariable } from "$lib/types/api";

  let newName = $state("");
  let draft = $state<Environment | null>(null);
  let saveStatus = $state("");

  onMount(() => {
    loadEnvironments();
  });

  function selectEnvironment(environment: Environment) {
    draft = structuredClone(environment);
    saveStatus = "";
  }

  async function createEnvironment() {
    if (!newName.trim()) {
      return;
    }

    try {
      const environment = createEmptyEnvironment(newName.trim());
      const saved = await saveEnvironment(environment);

      newName = "";
      draft = structuredClone(saved);
      saveStatus = "Environment created.";
    } catch (error) {
      saveStatus = String(error);
    }
  }

  async function removeEnvironment(id: string) {
    if (typeof window !== "undefined" && !window.confirm("Delete this environment?")) {
      return;
    }

    try {
      await deleteEnvironment(id);

      if (draft?.id === id) {
        draft = null;
      }

      saveStatus = "";
    } catch (error) {
      saveStatus = String(error);
    }
  }

  async function makeActive(id: string) {
    try {
      await setActiveEnvironment(id);
      saveStatus = "Active environment updated.";
    } catch (error) {
      saveStatus = String(error);
    }
  }

  function addVariable() {
    if (!draft) {
      return;
    }

    draft.variables = [
      ...draft.variables,
      {
        id: newId(),
        key: "",
        value: "",
        enabled: true
      }
    ];
  }

  function removeVariable(id: string) {
    if (!draft) {
      return;
    }

    draft.variables = draft.variables.filter((variable) => variable.id !== id);
  }

  function updateVariable(id: string, patch: Partial<EnvironmentVariable>) {
    if (!draft) {
      return;
    }

    draft.variables = draft.variables.map((variable) =>
      variable.id === id
        ? {
            ...variable,
            ...patch
          }
        : variable
    );
  }

  function onDraftName(event: Event) {
    if (!draft) {
      return;
    }

    draft.name = (event.currentTarget as HTMLInputElement).value;
  }

  function onVariableKey(id: string, event: Event) {
    updateVariable(id, {
      key: (event.currentTarget as HTMLInputElement).value
    });
  }

  function onVariableValue(id: string, event: Event) {
    updateVariable(id, {
      value: (event.currentTarget as HTMLInputElement).value
    });
  }

  function onVariableEnabled(id: string, event: Event) {
    updateVariable(id, {
      enabled: (event.currentTarget as HTMLInputElement).checked
    });
  }

  async function saveDraft() {
    if (!draft) {
      return;
    }

    try {
      const saved = await saveEnvironment(draft);
      draft = structuredClone(saved);
      saveStatus = "Environment saved.";
      await loadEnvironments();
    } catch (error) {
      saveStatus = String(error);
    }
  }
</script>

<div class="flex h-full overflow-hidden">
  <div class="w-72 overflow-y-auto border-r border-neutral-800 p-3">
    <div class="flex gap-2">
      <input
        class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="New environment"
        bind:value={newName}
      />

      <button
        class="rounded bg-emerald-600 px-3 py-2 text-white"
        onclick={createEnvironment}
      >
        <Plus size={16} />
      </button>
    </div>

    <div class="mt-4">
      {#each $environments as environment (environment.id)}
        <div
          class="mt-2 flex items-center gap-1 rounded border border-neutral-800 px-2 py-1 {draft?.id ===
          environment.id
            ? "bg-neutral-900"
            : ""}"
        >
          <button
            class="flex-1 truncate text-left text-sm"
            onclick={() => selectEnvironment(environment)}
          >
            {environment.name}
          </button>

          <button
            class="p-1 text-neutral-400 hover:text-emerald-400"
            title="Set active"
            onclick={() => makeActive(environment.id)}
          >
            {#if $activeEnvironmentId === environment.id}
              <Check size={14} />
            {:else}
              <span class="block h-3 w-3 rounded-full border border-neutral-600"></span>
            {/if}
          </button>

          <button
            class="p-1 text-neutral-500 hover:text-red-400"
            title="Delete"
            onclick={() => removeEnvironment(environment.id)}
          >
            <Trash2 size={14} />
          </button>
        </div>
      {:else}
        <p class="mt-3 text-xs text-neutral-600">No environments yet.</p>
      {/each}
    </div>
  </div>

  <div class="flex-1 overflow-y-auto p-4">
    {#if draft}
      <div class="flex items-center gap-2">
        <input
          class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          value={draft.name}
          oninput={onDraftName}
        />

        <button
          class="flex items-center gap-2 rounded bg-emerald-600 px-4 py-2 text-sm text-white"
          onclick={saveDraft}
        >
          <Save size={14} />
          Save
        </button>
      </div>

      <p class="mt-6 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Variables
      </p>

      <div class="mt-3 space-y-2">
        {#each draft.variables as variable (variable.id)}
          <div class="flex items-center gap-2">
            <input
              type="checkbox"
              class="h-4 w-4"
              checked={variable.enabled}
              onchange={(event) => onVariableEnabled(variable.id, event)}
            />

            <input
              class="w-1/3 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
              placeholder="key"
              value={variable.key}
              oninput={(event) => onVariableKey(variable.id, event)}
            />

            <input
              class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
              placeholder="value"
              value={variable.value}
              oninput={(event) => onVariableValue(variable.id, event)}
            />

            <button
              class="rounded border border-neutral-800 p-2 text-neutral-400 hover:text-red-400"
              onclick={() => removeVariable(variable.id)}
            >
              <Trash2 size={14} />
            </button>
          </div>
        {:else}
          <p class="text-xs text-neutral-600">No variables yet.</p>
        {/each}
      </div>

      <button
        class="mt-3 flex items-center gap-1 rounded border border-neutral-800 px-3 py-1 text-xs text-neutral-300 hover:bg-neutral-900"
        onclick={addVariable}
      >
        <Plus size={14} />
        Add Variable
      </button>

      <p class="mt-4 text-xs text-neutral-400">{saveStatus}</p>
    {:else}
      <div class="flex h-full items-center justify-center text-sm text-neutral-600">
        Select or create an environment.
      </div>
    {/if}
  </div>
</div>
