#!/usr/bin/env python3
"""
Chapar Phase 8: Request history, export/import, and final polish.

This script:
- verifies Phase 7 files exist
- adds Rust history persistence
- automatically saves executed requests into history
- adds export/import commands
- adds History and Data panels
- updates navigation
- runs frontend and Rust verification checks
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


DB_HISTORY_FUNCTIONS = '''
pub fn save_history_conn(
    connection: &Connection,
    request: &ApiRequest,
    environment_id: Option<String>,
    response: &ResponsePayload,
) -> Result<(), String> {
    let id = Uuid::new_v4().to_string();

    let request_snapshot_json =
        serde_json::to_string(request).map_err(|error| error.to_string())?;

    let response_json =
        serde_json::to_string(response).map_err(|error| error.to_string())?;

    let status = response.status as i64;
    let latency_ms = response.latency_ms as i64;
    let size_bytes = response.size_bytes as i64;

    connection
        .execute(
            "INSERT INTO request_history
             (id, request_id, environment_id, request_snapshot_json, status, latency_ms, size_bytes, response_json)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                id,
                request.id,
                environment_id,
                request_snapshot_json,
                status,
                latency_ms,
                size_bytes,
                response_json
            ],
        )
        .map_err(|error| format!("failed to insert history entry: {error}"))?;

    connection
        .execute(
            "DELETE FROM request_history
             WHERE id NOT IN (
                 SELECT id
                 FROM request_history
                 ORDER BY created_at DESC, rowid DESC
                 LIMIT 200
             )",
            [],
        )
        .map_err(|error| format!("failed to prune history: {error}"))?;

    Ok(())
}

pub fn save_history_for_app(
    app: &tauri::AppHandle,
    request: &ApiRequest,
    environment_id: Option<String>,
    response: &ResponsePayload,
) -> Result<(), String> {
    let path = db_path(app)?;
    let connection = open_connection(&path)?;

    save_history_conn(&connection, request, environment_id, response)
}

pub fn list_history_conn(
    connection: &Connection,
    limit: Option<i64>,
) -> Result<Vec<HistoryEntry>, String> {
    let limit = limit.unwrap_or(100).clamp(1, 500);

    let mut statement = connection
        .prepare(
            "SELECT id, request_id, environment_id, request_snapshot_json, status, latency_ms, size_bytes, response_json, created_at
             FROM request_history
             ORDER BY created_at DESC, rowid DESC
             LIMIT ?1",
        )
        .map_err(|error| format!("failed to prepare history query: {error}"))?;

    let rows = statement
        .query_map(params![limit], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, Option<String>>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, Option<i64>>(4)?,
                row.get::<_, Option<i64>>(5)?,
                row.get::<_, Option<i64>>(6)?,
                row.get::<_, Option<String>>(7)?,
                row.get::<_, String>(8)?,
            ))
        })
        .map_err(|error| format!("failed to query history: {error}"))?;

    let mut entries = Vec::new();

    for row in rows {
        let (
            id,
            request_id,
            environment_id,
            request_snapshot_json,
            status,
            latency_ms,
            size_bytes,
            response_json,
            created_at,
        ) = row.map_err(|error| format!("failed to read history row: {error}"))?;

        let request_snapshot: ApiRequest = match serde_json::from_str(&request_snapshot_json) {
            Ok(snapshot) => snapshot,
            Err(_) => continue,
        };

        let response: Option<ResponsePayload> =
            response_json.and_then(|json| serde_json::from_str(&json).ok());

        entries.push(HistoryEntry {
            id,
            request_id,
            environment_id,
            request_snapshot,
            status,
            latency_ms,
            size_bytes,
            response,
            created_at,
        });
    }

    Ok(entries)
}

pub fn clear_history_conn(connection: &Connection) -> Result<(), String> {
    connection
        .execute("DELETE FROM request_history", [])
        .map_err(|error| format!("failed to clear history: {error}"))?;

    Ok(())
}

pub fn export_bundle_conn(connection: &Connection) -> Result<ExportBundle, String> {
    let exported_at: String = connection
        .query_row("SELECT datetime('now')", [], |row| row.get(0))
        .map_err(|error| format!("failed to read export timestamp: {error}"))?;

    let collections = list_collections_conn(connection)?;
    let requests = list_requests_conn(connection, None)?;
    let environments = list_environments_conn(connection)?;
    let secret_metadata = list_secret_metadata_conn(connection)?;

    Ok(ExportBundle {
        exported_at,
        collections,
        requests,
        environments,
        secret_metadata,
    })
}

pub fn import_bundle_conn(
    connection: &Connection,
    bundle: &ExportBundle,
) -> Result<String, String> {
    let mut collections_count = 0;
    let mut requests_count = 0;
    let mut environments_count = 0;
    let mut secret_metadata_count = 0;

    for collection in &bundle.collections {
        let result = connection.execute(
            "INSERT OR REPLACE INTO collections
             (id, name, parent_id, position, created_at, updated_at)
             VALUES (
                 ?1,
                 ?2,
                 ?3,
                 ?4,
                 COALESCE(NULLIF(?5, ''), datetime('now')),
                 COALESCE(NULLIF(?6, ''), datetime('now'))
             )",
            params![
                collection.id,
                collection.name,
                collection.parent_id,
                collection.position,
                collection.created_at,
                collection.updated_at
            ],
        );

        if result.is_ok() {
            collections_count += 1;
        }
    }

    for request in &bundle.requests {
        let result = save_request_conn(
            connection,
            &SaveRequestPayload {
                request: request.clone(),
            },
        );

        if result.is_ok() {
            requests_count += 1;
        }
    }

    for environment in &bundle.environments {
        let result = save_environment_conn(
            connection,
            &SaveEnvironmentPayload {
                environment: environment.clone(),
            },
        );

        if result.is_ok() {
            environments_count += 1;
        }
    }

    for metadata in &bundle.secret_metadata {
        let result = save_secret_metadata_conn(connection, metadata);

        if result.is_ok() {
            secret_metadata_count += 1;
        }
    }

    Ok(format!(
        "Imported {} collections, {} requests, {} environments, {} secret metadata entries.",
        collections_count, requests_count, environments_count, secret_metadata_count
    ))
}
'''


MODELS_APPEND = '''
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HistoryEntry {
    pub id: String,
    pub request_id: String,
    pub environment_id: Option<String>,
    pub request_snapshot: ApiRequest,
    pub status: Option<i64>,
    pub latency_ms: Option<i64>,
    pub size_bytes: Option<i64>,
    pub response: Option<ResponsePayload>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportBundle {
    pub exported_at: String,
    pub collections: Vec<Collection>,
    pub requests: Vec<ApiRequest>,
    pub environments: Vec<Environment>,
    pub secret_metadata: Vec<SecretMetadata>,
}
'''


TS_TYPES_APPEND = '''
export interface HistoryEntry {
  id: string;
  requestId: string;
  environmentId: string | null;
  requestSnapshot: ApiRequest;
  status: number | null;
  latencyMs: number | null;
  sizeBytes: number | null;
  response: ResponsePayload | null;
  createdAt: string;
}

export interface ExportBundle {
  exportedAt: string;
  collections: Collection[];
  requests: ApiRequest[];
  environments: Environment[];
  secretMetadata: SecretMetadata[];
}
'''


PHASE8_FILES: dict[str, str] = {
"src-tauri/src/commands/history.rs": """use tauri::AppHandle;

use crate::models::HistoryEntry;

#[tauri::command]
pub fn list_history(app: AppHandle, limit: Option<i64>) -> Result<Vec<HistoryEntry>, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::list_history_conn(&connection, limit)
}

#[tauri::command]
pub fn clear_history(app: AppHandle) -> Result<(), String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::clear_history_conn(&connection)
}
""",

"src-tauri/src/commands/data.rs": """use tauri::AppHandle;

use crate::models::ExportBundle;

#[tauri::command]
pub fn export_data(app: AppHandle) -> Result<ExportBundle, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::export_bundle_conn(&connection)
}

#[tauri::command]
pub fn import_data(app: AppHandle, bundle: ExportBundle) -> Result<String, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::import_bundle_conn(&connection, &bundle)
}
""",

"src/lib/services/api.ts": """import { invoke } from "@tauri-apps/api/core";
import type {
  ApiRequest,
  Collection,
  CreateCollectionPayload,
  Environment,
  ExportBundle,
  HistoryEntry,
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
  },

  listHistory(limit?: number) {
    return invoke<HistoryEntry[]>("list_history", {
      limit: limit ?? null
    });
  },

  clearHistory() {
    return invoke<void>("clear_history");
  },

  exportData() {
    return invoke<ExportBundle>("export_data");
  },

  importData(bundle: ExportBundle) {
    return invoke<string>("import_data", { bundle });
  }
};
""",

"src/lib/stores/ui.ts": """import { writable } from "svelte/store";

export type AppView =
  | "requests"
  | "environments"
  | "secrets"
  | "history"
  | "data";

export const appView = writable<AppView>("requests");
""",

"src/lib/stores/history.ts": """import { writable } from "svelte/store";
import { api } from "$lib/services/api";
import type { HistoryEntry } from "$lib/types/api";

export const historyEntries = writable<HistoryEntry[]>([]);
export const selectedHistory = writable<HistoryEntry | null>(null);
export const historyError = writable<string | null>(null);

export async function loadHistory(limit = 100): Promise<void> {
  try {
    const entries = await api.listHistory(limit);
    historyEntries.set(entries);
    historyError.set(null);
  } catch (error) {
    historyError.set(String(error));
  }
}

export async function clearAllHistory(): Promise<void> {
  await api.clearHistory();
  historyEntries.set([]);
  selectedHistory.set(null);
}
""",

"src/lib/components/HistoryPanel.svelte": """<script lang="ts">
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
""",

"src/lib/components/DataPanel.svelte": """<script lang="ts">
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
""",

"src/lib/components/Sidebar.svelte": """<script lang="ts">
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
""",

"src/routes/+page.svelte": """<script lang="ts">
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
""",
}


REQUIRED_PHASE7_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src/lib/components/SecretsPanel.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/db.rs",
    "src-tauri/src/http.rs",
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


def verify_phase7() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE7_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 7 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 7 skeleton detected")


def patch_models() -> None:
    path = ROOT / "src-tauri" / "src" / "models.rs"
    text = path.read_text(encoding="utf-8")

    if "pub struct HistoryEntry" not in text:
        text = text.rstrip() + "\n" + MODELS_APPEND
        path.write_text(text, encoding="utf-8")
        print("PATCH src-tauri/src/models.rs")
    else:
        print("OK    src-tauri/src/models.rs already has HistoryEntry")


def patch_ts_types() -> None:
    path = ROOT / "src" / "lib" / "types" / "api.ts"
    text = path.read_text(encoding="utf-8")

    if "export interface HistoryEntry" not in text:
        text = text.rstrip() + "\n" + TS_TYPES_APPEND
        path.write_text(text, encoding="utf-8")
        print("PATCH src/lib/types/api.ts")
    else:
        print("OK    src/lib/types/api.ts already has HistoryEntry")


def patch_db() -> None:
    path = ROOT / "src-tauri" / "src" / "db.rs"
    text = path.read_text(encoding="utf-8")

    old_import = """use crate::models::{
    ApiRequest, Collection, CreateCollectionPayload, Environment, EnvironmentVariable, HttpMethod,
    RequestBody, RequestBodyKind, SaveEnvironmentPayload, SaveRequestPayload, SecretMetadata,
};"""

    new_import = """use crate::models::{
    ApiRequest, Collection, CreateCollectionPayload, Environment, EnvironmentVariable,
    ExportBundle, HistoryEntry, HttpMethod, RequestBody, RequestBodyKind, ResponsePayload,
    SaveEnvironmentPayload, SaveRequestPayload, SecretMetadata,
};"""

    if new_import not in text:
        text = text.replace(old_import, new_import)

    if "pub fn save_history_conn" not in text:
        text = text.replace("#[cfg(test)]", DB_HISTORY_FUNCTIONS + "\n#[cfg(test)]", 1)

    path.write_text(text, encoding="utf-8")
    print("PATCH src-tauri/src/db.rs")


def patch_http() -> None:
    path = ROOT / "src-tauri" / "src" / "http.rs"
    text = path.read_text(encoding="utf-8")

    if "environment_id_for_history" not in text:
        text = text.replace(
            "    let environment = match environment_id {",
            """    let environment_id_for_history = environment_id.clone();

    let environment = match environment_id {""",
            1,
        )

    old_return = """    Ok(ResponsePayload {
        request_id: request.id,
        status: status.as_u16(),
        status_text,
        http_version,
        latency_ms,
        size_bytes,
        headers,
        body,
        unresolved_variables: unresolved,
        error: None,
    })
}"""

    new_return = """    let response_payload = ResponsePayload {
        request_id: request.id.clone(),
        status: status.as_u16(),
        status_text,
        http_version,
        latency_ms,
        size_bytes,
        headers,
        body,
        unresolved_variables: unresolved,
        error: None,
    };

    let _ = crate::db::save_history_for_app(
        app,
        &request,
        environment_id_for_history,
        &response_payload,
    );

    Ok(response_payload)
}"""

    if "save_history_for_app" not in text:
        text = text.replace(old_return, new_return, 1)

    path.write_text(text, encoding="utf-8")
    print("PATCH src-tauri/src/http.rs")


def patch_commands_mod() -> None:
    path = ROOT / "src-tauri" / "src" / "commands" / "mod.rs"
    text = path.read_text(encoding="utf-8")

    if "pub mod history;" not in text:
        text = text.replace(
            "pub mod secrets;",
            "pub mod secrets;\npub mod history;\npub mod data;",
            1,
        )

    path.write_text(text, encoding="utf-8")
    print("PATCH src-tauri/src/commands/mod.rs")


def patch_main() -> None:
    path = ROOT / "src-tauri" / "src" / "main.rs"
    text = path.read_text(encoding="utf-8")

    if "commands::history::list_history" not in text:
        text = text.replace(
            """            commands::secrets::delete_secret
        ])""",
            """            commands::secrets::delete_secret,
            commands::history::list_history,
            commands::history::clear_history,
            commands::data::export_data,
            commands::data::import_data
        ])""",
            1,
        )

    path.write_text(text, encoding="utf-8")
    print("PATCH src-tauri/src/main.rs")


def write_phase8_files() -> None:
    for relative_path, content in PHASE8_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase7()
    patch_models()
    patch_ts_types()
    patch_db()
    patch_http()
    patch_commands_mod()
    patch_main()
    write_phase8_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)
    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 8 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nTest history:")
    print("  1. Send a request")
    print("  2. Open History")
    print("  3. Select the entry")
    print("  4. Click Load into Editor")
    print("\nTest export/import:")
    print("  1. Open Data")
    print("  2. Click Export")
    print("  3. Copy export JSON")
    print("  4. Paste into Import and click Import")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
