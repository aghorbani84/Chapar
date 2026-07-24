#!/usr/bin/env python3
"""
Chapar Phase 7: Secure Vault UI and secret header injection.

This script:
- verifies Phase 6 files exist
- adds secret metadata persistence to Rust
- adds secret delete support to the vault
- adds secret Tauri commands
- adds a Secrets panel UI
- updates the header editor to support secret selection
- automatically computes allowedSecretIds from headers and templates
- runs frontend and Rust verification checks
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


SECRET_DB_FUNCTIONS = """
fn normalize_secret_id(id: &str) -> Result<String, String> {
    let id = id.trim();

    if id.is_empty() {
        return Err("secret id must not be empty".to_string());
    }

    if id.len() > 255 {
        return Err("secret id must be 255 characters or fewer".to_string());
    }

    let allowed = id
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.' | ':'));

    if !allowed {
        return Err(
            "secret id may only contain letters, numbers, '-', '_', '.', or ':'".to_string(),
        );
    }

    Ok(id.to_string())
}

pub fn list_secret_metadata_conn(connection: &Connection) -> Result<Vec<SecretMetadata>, String> {
    let mut statement = connection
        .prepare("SELECT id, label, created_at FROM secret_metadata ORDER BY label")
        .map_err(|error| format!("failed to prepare secret metadata query: {error}"))?;

    let rows = statement
        .query_map([], |row| {
            Ok(SecretMetadata {
                id: row.get(0)?,
                label: row.get(1)?,
                created_at: row.get(2)?,
            })
        })
        .map_err(|error| format!("failed to query secret metadata: {error}"))?;

    let mut metadata = Vec::new();

    for row in rows {
        metadata.push(row.map_err(|error| format!("failed to read secret metadata: {error}"))?);
    }

    Ok(metadata)
}

pub fn get_secret_metadata_conn(
    connection: &Connection,
    id: &str,
) -> Result<SecretMetadata, String> {
    let result = connection.query_row(
        "SELECT id, label, created_at FROM secret_metadata WHERE id = ?1",
        params![id],
        |row| {
            Ok(SecretMetadata {
                id: row.get(0)?,
                label: row.get(1)?,
                created_at: row.get(2)?,
            })
        },
    );

    match result {
        Ok(metadata) => Ok(metadata),
        Err(rusqlite::Error::QueryReturnedNoRows) => Err("secret metadata not found".to_string()),
        Err(error) => Err(error.to_string()),
    }
}

pub fn save_secret_metadata_conn(
    connection: &Connection,
    metadata: &SecretMetadata,
) -> Result<SecretMetadata, String> {
    let id = normalize_secret_id(&metadata.id)?;

    let label = if metadata.label.trim().is_empty() {
        id.clone()
    } else {
        metadata.label.trim().to_string()
    };

    let exists: bool = connection
        .query_row(
            "SELECT COUNT(*) FROM secret_metadata WHERE id = ?1",
            params![id],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|error| format!("failed to check secret metadata existence: {error}"))?
        > 0;

    if exists {
        connection
            .execute(
                "UPDATE secret_metadata SET label = ?1 WHERE id = ?2",
                params![label, id],
            )
            .map_err(|error| format!("failed to update secret metadata: {error}"))?;
    } else {
        connection
            .execute(
                "INSERT INTO secret_metadata (id, label) VALUES (?1, ?2)",
                params![id, label],
            )
            .map_err(|error| format!("failed to insert secret metadata: {error}"))?;
    }

    get_secret_metadata_conn(connection, &id)
}

pub fn delete_secret_metadata_conn(connection: &Connection, id: &str) -> Result<(), String> {
    connection
        .execute("DELETE FROM secret_metadata WHERE id = ?1", params![id])
        .map_err(|error| format!("failed to delete secret metadata: {error}"))?;

    Ok(())
}
"""


SECRET_DB_TEST = """
    #[test]
    fn secret_metadata_crud() {
        let connection = Connection::open_in_memory().unwrap();
        migrate(&connection).unwrap();

        let metadata = SecretMetadata {
            id: "prod-api-key".to_string(),
            label: "Prod API Key".to_string(),
            created_at: String::new(),
        };

        let saved = save_secret_metadata_conn(&connection, &metadata).unwrap();

        assert_eq!(saved.id, "prod-api-key");
        assert_eq!(saved.label, "Prod API Key");

        let list = list_secret_metadata_conn(&connection).unwrap();
        assert_eq!(list.len(), 1);

        delete_secret_metadata_conn(&connection, &saved.id).unwrap();

        let list_after_delete = list_secret_metadata_conn(&connection).unwrap();
        assert!(list_after_delete.is_empty());
    }

"""


PHASE7_FILES: dict[str, str] = {
"src-tauri/src/vault.rs": """use keyring::Entry;

const SERVICE: &str = "app.chapar.desktop";
const MAX_SECRET_ID_LEN: usize = 255;
const MAX_SECRET_VALUE_LEN: usize = 4096;

fn normalize_id(id: &str) -> Result<String, String> {
    let id = id.trim();

    if id.is_empty() {
        return Err("secret id must not be empty".to_string());
    }

    if id.len() > MAX_SECRET_ID_LEN {
        return Err(format!(
            "secret id must be {} characters or fewer",
            MAX_SECRET_ID_LEN
        ));
    }

    let allowed = id
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.' | ':'));

    if !allowed {
        return Err(
            "secret id may only contain letters, numbers, '-', '_', '.', or ':'".to_string(),
        );
    }

    Ok(id.to_string())
}

fn validate_value(value: &str) -> Result<(), String> {
    if value.is_empty() {
        return Err("secret value must not be empty".to_string());
    }

    if value.len() > MAX_SECRET_VALUE_LEN {
        return Err(format!(
            "secret value must be {} characters or fewer",
            MAX_SECRET_VALUE_LEN
        ));
    }

    if value.chars().any(char::is_control) {
        return Err("secret value must not contain control characters".to_string());
    }

    Ok(())
}

fn entry_for(id: &str) -> Result<Entry, String> {
    let id = normalize_id(id)?;

    Entry::new(SERVICE, &id).map_err(|_| "secret store is unavailable".to_string())
}

pub fn store_secret(id: &str, value: &str) -> Result<(), String> {
    validate_value(value)?;

    let entry = entry_for(id)?;

    entry
        .set_password(value)
        .map_err(|_| "failed to store secret".to_string())
}

pub fn get_secret(id: &str) -> Result<String, String> {
    let entry = entry_for(id)?;

    entry.get_password().map_err(|error| match error {
        keyring::Error::NoEntry => "secret not found".to_string(),
        _ => "failed to retrieve secret".to_string(),
    })
}

pub fn secret_exists(id: &str) -> Result<bool, String> {
    let entry = entry_for(id)?;

    match entry.get_password() {
        Ok(_) => Ok(true),
        Err(keyring::Error::NoEntry) => Ok(false),
        Err(_) => Err("failed to check secret".to_string()),
    }
}

pub fn delete_secret(id: &str) -> Result<(), String> {
    let entry = entry_for(id)?;

    match entry.delete_credential() {
        Ok(_) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(_) => Err("failed to delete secret".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_id_accepts_valid_ids() {
        assert!(normalize_id("prod-api-key").is_ok());
        assert!(normalize_id("prod_api_key").is_ok());
        assert!(normalize_id("prod.api.key").is_ok());
        assert!(normalize_id("prod:api:key").is_ok());
        assert!(normalize_id("  prod-api-key  ").is_ok());
    }

    #[test]
    fn normalize_id_rejects_invalid_ids() {
        assert!(normalize_id("").is_err());
        assert!(normalize_id("   ").is_err());
        assert!(normalize_id("bad id").is_err());
        assert!(normalize_id("bad/id").is_err());
        assert!(normalize_id("bad\\nid").is_err());
        assert!(normalize_id(&"a".repeat(300)).is_err());
    }

    #[test]
    fn validate_value_accepts_normal_values() {
        assert!(validate_value("super-secret-token").is_ok());
        assert!(validate_value("Bearer abc123").is_ok());
        assert!(validate_value("value with spaces").is_ok());
    }

    #[test]
    fn validate_value_rejects_invalid_values() {
        assert!(validate_value("").is_err());
        assert!(validate_value("bad\\nvalue").is_err());
        assert!(validate_value("bad\\u{0000}value").is_err());
        assert!(validate_value(&"a".repeat(5000)).is_err());
    }
}
""",

"src-tauri/src/commands/secrets.rs": """use tauri::AppHandle;

use crate::models::{SecretMetadata, StoreSecretPayload};

#[tauri::command]
pub fn store_secret(id: String, value: String) -> Result<(), String> {
    crate::vault::store_secret(&id, &value)
}

#[tauri::command]
pub fn get_secret(id: String) -> Result<String, String> {
    crate::vault::get_secret(&id)
}

#[tauri::command]
pub fn secret_exists(id: String) -> Result<bool, String> {
    crate::vault::secret_exists(&id)
}

#[tauri::command]
pub fn list_secret_metadata(app: AppHandle) -> Result<Vec<SecretMetadata>, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::list_secret_metadata_conn(&connection)
}

#[tauri::command]
pub fn save_secret(
    app: AppHandle,
    payload: StoreSecretPayload,
) -> Result<SecretMetadata, String> {
    crate::vault::store_secret(&payload.id, &payload.value)?;

    let label = match payload.label {
        Some(label) if !label.trim().is_empty() => label.trim().to_string(),
        _ => payload.id.trim().to_string(),
    };

    let metadata = SecretMetadata {
        id: payload.id.trim().to_string(),
        label,
        created_at: String::new(),
    };

    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::save_secret_metadata_conn(&connection, &metadata)
}

#[tauri::command]
pub fn delete_secret(app: AppHandle, id: String) -> Result<(), String> {
    crate::vault::delete_secret(&id)?;

    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::delete_secret_metadata_conn(&connection, &id)
}
""",

"src/lib/services/api.ts": """import { invoke } from "@tauri-apps/api/core";
import type {
  ApiRequest,
  Collection,
  CreateCollectionPayload,
  Environment,
  RequestPayload,
  ResponsePayload,
  SaveEnvironmentPayload,
  SaveRequestPayload,
  SecretMetadata,
  StoreSecretPayload
} from "$lib/types/api";

export const api = {
  listEnvironments() {
    return invoke<Environment[]>("list_environments");
  },

  saveEnvironment(payload: SaveEnvironmentPayload) {
    return invoke<Environment>("save_environment", { payload });
  },

  deleteEnvironment(id: string) {
    return invoke<void>("delete_environment", { id });
  },

  setActiveEnvironment(id: string | null) {
    return invoke<void>("set_active_environment", { id });
  },

  getActiveEnvironmentId() {
    return invoke<string | null>("get_active_environment_id");
  },

  executeRequest(payload: RequestPayload) {
    return invoke<ResponsePayload>("execute_request", { payload });
  },

  listCollections() {
    return invoke<Collection[]>("list_collections");
  },

  createCollection(payload: CreateCollectionPayload) {
    return invoke<Collection>("create_collection", { payload });
  },

  deleteCollection(id: string) {
    return invoke<void>("delete_collection", { id });
  },

  listRequests(collectionId: string | null) {
    return invoke<ApiRequest[]>("list_requests", { collectionId });
  },

  saveRequest(payload: SaveRequestPayload) {
    return invoke<ApiRequest>("save_request", { payload });
  },

  deleteRequest(id: string) {
    return invoke<void>("delete_request", { id });
  },

  listSecretMetadata() {
    return invoke<SecretMetadata[]>("list_secret_metadata");
  },

  saveSecret(payload: StoreSecretPayload) {
    return invoke<SecretMetadata>("save_secret", { payload });
  },

  deleteSecret(id: string) {
    return invoke<void>("delete_secret", { id });
  },

  secretExists(id: string) {
    return invoke<boolean>("secret_exists", { id });
  }
};
""",

"src/lib/stores/secrets.ts": """import { writable } from "svelte/store";
import { api } from "$lib/services/api";
import type { SecretMetadata } from "$lib/types/api";

export const secretMetadata = writable<SecretMetadata[]>([]);
export const secretsError = writable<string | null>(null);

export async function loadSecrets(): Promise<void> {
  try {
    const list = await api.listSecretMetadata();
    secretMetadata.set(list);
    secretsError.set(null);
  } catch (error) {
    secretsError.set(String(error));
  }
}

export async function saveSecret(
  id: string,
  label: string,
  value: string
): Promise<SecretMetadata> {
  const saved = await api.saveSecret({
    id,
    value,
    label: label.trim() === "" ? undefined : label.trim()
  });

  secretMetadata.update((list) => {
    const index = list.findIndex((item) => item.id === saved.id);

    if (index >= 0) {
      const next = [...list];
      next[index] = saved;
      return next;
    }

    return [...list, saved];
  });

  return saved;
}

export async function deleteSecretById(id: string): Promise<void> {
  await api.deleteSecret(id);
  secretMetadata.update((list) => list.filter((item) => item.id !== id));
}
""",

"src/lib/stores/requestEditor.ts": """import { writable } from "svelte/store";
import { newId } from "$lib/utils/id";
import type {
  ApiRequest,
  HttpMethod,
  KeyValueEntry,
  RequestBodyKind
} from "$lib/types/api";

export interface RequestEditorState {
  id: string;
  name: string;
  collectionId: string | null;
  method: HttpMethod;
  url: string;
  environmentId: string;
  bodyKind: RequestBodyKind;
  bodyText: string;
  timeoutMs: string;
  followRedirects: boolean;
  headers: KeyValueEntry[];
  allowedSecretIds: string[];
  position: number;
  createdAt: string;
  updatedAt: string;
}

export function newRequestDraft(collectionId: string | null): RequestEditorState {
  const now = new Date().toISOString();

  return {
    id: newId(),
    name: "New Request",
    collectionId,
    method: "GET",
    url: "http://localhost:8080",
    environmentId: "",
    bodyKind: "none",
    bodyText: "",
    timeoutMs: "",
    followRedirects: true,
    headers: [],
    allowedSecretIds: [],
    position: 0,
    createdAt: now,
    updatedAt: now
  };
}

export function requestToEditor(request: ApiRequest): RequestEditorState {
  return {
    id: request.id,
    name: request.name,
    collectionId: request.collectionId,
    method: request.method,
    url: request.url,
    environmentId: "",
    bodyKind: request.body.kind,
    bodyText: request.body.text,
    timeoutMs:
      request.timeoutMs === null || request.timeoutMs === undefined
        ? ""
        : String(request.timeoutMs),
    followRedirects: request.followRedirects,
    headers: request.headers,
    allowedSecretIds: request.allowedSecretIds,
    position: request.position,
    createdAt: request.createdAt,
    updatedAt: request.updatedAt
  };
}

function extractSecretIds(input: string): string[] {
  const ids: string[] = [];

  const regex = /{{\\s*secret:\\s*([A-Za-z0-9_:.-]+)\\s*}}/g;

  let match: RegExpExecArray | null;

  while ((match = regex.exec(input)) !== null) {
    const id = match[1];

    if (id) {
      ids.push(id.trim());
    }
  }

  return ids;
}

function computeAllowedSecretIds(state: RequestEditorState): string[] {
  const allowed = new Set<string>(state.allowedSecretIds);

  for (const header of state.headers) {
    if (header.secretId) {
      allowed.add(header.secretId);
    }

    for (const id of extractSecretIds(header.key)) {
      allowed.add(id);
    }

    for (const id of extractSecretIds(header.value)) {
      allowed.add(id);
    }
  }

  for (const id of extractSecretIds(state.url)) {
    allowed.add(id);
  }

  for (const id of extractSecretIds(state.bodyText)) {
    allowed.add(id);
  }

  return Array.from(allowed);
}

export function editorToRequest(state: RequestEditorState): ApiRequest {
  const timeoutValue = state.timeoutMs.trim() === "" ? null : Number(state.timeoutMs);

  return {
    id: state.id,
    collectionId: state.collectionId,
    name: state.name.trim() === "" ? "Untitled" : state.name.trim(),
    method: state.method,
    url: state.url,
    params: [],
    headers: state.headers,
    body: {
      kind: state.bodyKind,
      text: state.bodyText,
      form: []
    },
    allowedSecretIds: computeAllowedSecretIds(state),
    timeoutMs:
      timeoutValue !== null && Number.isFinite(timeoutValue) ? timeoutValue : null,
    followRedirects: state.followRedirects,
    position: state.position,
    createdAt: state.createdAt,
    updatedAt: new Date().toISOString()
  };
}

function createRequestEditorStore() {
  const { subscribe, set, update } = writable<RequestEditorState>(
    newRequestDraft(null)
  );

  return {
    subscribe,
    set,
    update
  };
}

export const requestEditor = createRequestEditorStore();
""",

"src/lib/components/KeyValueEditor.svelte": """<script lang="ts">
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
""",

"src/lib/components/SecretsPanel.svelte": """<script lang="ts">
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
""",

"src/lib/components/RequestPane.svelte": """<script lang="ts">
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
""",

"src/routes/+page.svelte": """<script lang="ts">
  import { onMount } from "svelte";
  import Sidebar from "$lib/components/Sidebar.svelte";
  import RequestPane from "$lib/components/RequestPane.svelte";
  import ResponsePane from "$lib/components/ResponsePane.svelte";
  import EnvironmentsPanel from "$lib/components/EnvironmentsPanel.svelte";
  import SecretsPanel from "$lib/components/SecretsPanel.svelte";
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
    {:else}
      <div class="flex h-full items-center justify-center text-sm text-neutral-600">
        Unknown view.
      </div>
    {/if}
  </div>
</div>
""",
}


REQUIRED_PHASE6_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src/lib/components/Sidebar.svelte",
    "src/lib/components/RequestPane.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/db.rs",
    "src-tauri/src/vault.rs",
    "src-tauri/src/commands/secrets.rs",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def verify_phase6() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE6_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 6 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 6 skeleton detected")


def patch_db() -> None:
    path = ROOT / "src-tauri" / "src" / "db.rs"
    text = path.read_text(encoding="utf-8")

    old_import = """use crate::models::{
    ApiRequest, Collection, CreateCollectionPayload, Environment, EnvironmentVariable, HttpMethod,
    RequestBody, RequestBodyKind, SaveEnvironmentPayload, SaveRequestPayload,
};"""

    new_import = """use crate::models::{
    ApiRequest, Collection, CreateCollectionPayload, Environment, EnvironmentVariable, HttpMethod,
    RequestBody, RequestBodyKind, SaveEnvironmentPayload, SaveRequestPayload, SecretMetadata,
};"""

    if new_import not in text:
        text = text.replace(old_import, new_import)

    if "pub fn list_secret_metadata_conn" not in text:
        text = text.replace("#[cfg(test)]", SECRET_DB_FUNCTIONS + "\n#[cfg(test)]", 1)

    if "fn secret_metadata_crud" not in text:
        text = text.replace(
            "    fn load_enabled_environment_variables_from_connection(",
            SECRET_DB_TEST + "    fn load_enabled_environment_variables_from_connection(",
            1,
        )

    path.write_text(text, encoding="utf-8")
    print("PATCH src-tauri/src/db.rs")


def patch_main() -> None:
    path = ROOT / "src-tauri" / "src" / "main.rs"
    text = path.read_text(encoding="utf-8")

    if "commands::secrets::list_secret_metadata" not in text:
        text = text.replace(
            """            commands::requests::delete_request
        ])""",
            """            commands::requests::delete_request,
            commands::secrets::list_secret_metadata,
            commands::secrets::save_secret,
            commands::secrets::delete_secret
        ])""",
            1,
        )

    path.write_text(text, encoding="utf-8")
    print("PATCH src-tauri/src/main.rs")


def write_phase7_files() -> None:
    for relative_path, content in PHASE7_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase6()
    patch_db()
    patch_main()
    write_phase7_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)
    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 7 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nTest:")
    print("  1. Open Secrets")
    print("  2. Store secret id: test-api-key")
    print("  3. Store secret value: super-secret-123")
    print("  4. Open Requests")
    print("  5. Add header key: X-Api-Key")
    print("  6. Select secret: test-api-key")
    print("  7. Send request to https://httpbin.org/headers")
    print("\nExpected:")
    print("  X-Api-Key header is injected by Rust from OS keychain")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
