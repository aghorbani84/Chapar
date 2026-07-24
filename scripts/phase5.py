#!/usr/bin/env python3
"""
Chapar Phase 5: Variable injection and environment UI.

This script:
- verifies Phase 4 files exist
- adds Rust environment CRUD commands
- adds frontend environment stores and API wrappers
- adds an Environment Manager panel
- adds a headers editor
- connects environment selection to execute_request
- runs frontend and Rust verification checks
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PHASE5_FILES: dict[str, str] = {
"src-tauri/src/db.rs": """use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::{params, Connection};
use tauri::Manager;
use uuid::Uuid;

use crate::models::{Environment, EnvironmentVariable, SaveEnvironmentPayload};

const MIGRATION: &str = include_str!("../migrations/001_initial.sql");

pub fn db_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|error| format!("failed to resolve app config directory: {error}"))?;

    fs::create_dir_all(&dir)
        .map_err(|error| format!("failed to create config directory {}: {error}", dir.display()))?;

    Ok(dir.join("chapar.db"))
}

pub fn open_connection(path: &Path) -> Result<Connection, String> {
    let connection = Connection::open(path)
        .map_err(|error| format!("failed to open database {}: {error}", path.display()))?;

    connection
        .execute_batch("PRAGMA foreign_keys = ON;")
        .map_err(|error| format!("failed to enable foreign keys: {error}"))?;

    Ok(connection)
}

pub fn migrate(connection: &Connection) -> Result<(), String> {
    connection
        .execute_batch(MIGRATION)
        .map_err(|error| format!("failed to apply database migration: {error}"))?;

    Ok(())
}

pub fn init_db_for_app(app: &tauri::AppHandle) -> Result<String, String> {
    let path = db_path(app)?;
    let connection = open_connection(&path)?;
    migrate(&connection)?;

    Ok(path.display().to_string())
}

pub fn load_enabled_environment_variables(
    app: &tauri::AppHandle,
    environment_id: &str,
) -> Result<HashMap<String, String>, String> {
    let path = db_path(app)?;
    let connection = open_connection(&path)?;

    let mut statement = connection
        .prepare(
            "SELECT key, value
             FROM environment_variables
             WHERE environment_id = ?1 AND enabled = 1
             ORDER BY rowid",
        )
        .map_err(|error| format!("failed to prepare environment query: {error}"))?;

    let rows = statement
        .query_map([environment_id], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })
        .map_err(|error| format!("failed to query environment variables: {error}"))?;

    let mut variables = HashMap::new();

    for row in rows {
        let (key, value) = row.map_err(|error| format!("failed to read environment row: {error}"))?;
        variables.insert(key, value);
    }

    Ok(variables)
}

pub fn list_environments_conn(connection: &Connection) -> Result<Vec<Environment>, String> {
    let mut statement = connection
        .prepare("SELECT id FROM environments ORDER BY name")
        .map_err(|error| format!("failed to prepare environments query: {error}"))?;

    let rows = statement
        .query_map([], |row| row.get::<_, String>(0))
        .map_err(|error| format!("failed to query environments: {error}"))?;

    let mut environments = Vec::new();

    for row in rows {
        let id = row.map_err(|error| format!("failed to read environment id: {error}"))?;
        environments.push(get_environment_conn(connection, &id)?);
    }

    Ok(environments)
}

pub fn get_environment_conn(connection: &Connection, id: &str) -> Result<Environment, String> {
    let environment_row: Result<(String, String, String, String), rusqlite::Error> =
        connection.query_row(
            "SELECT id, name, created_at, updated_at FROM environments WHERE id = ?1",
            params![id],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                ))
            },
        );

    let (id, name, created_at, updated_at) = match environment_row {
        Ok(row) => row,
        Err(rusqlite::Error::QueryReturnedNoRows) => {
            return Err("environment not found".to_string())
        }
        Err(error) => return Err(error.to_string()),
    };

    let mut statement = connection
        .prepare(
            "SELECT id, key, value, enabled
             FROM environment_variables
             WHERE environment_id = ?1
             ORDER BY rowid",
        )
        .map_err(|error| format!("failed to prepare environment variables query: {error}"))?;

    let rows = statement
        .query_map(params![id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)?,
            ))
        })
        .map_err(|error| format!("failed to query environment variables: {error}"))?;

    let mut variables = Vec::new();

    for row in rows {
        let (variable_id, key, value, enabled) =
            row.map_err(|error| format!("failed to read environment variable: {error}"))?;

        variables.push(EnvironmentVariable {
            id: variable_id,
            key,
            value,
            enabled: enabled != 0,
        });
    }

    Ok(Environment {
        id,
        name,
        variables,
        created_at,
        updated_at,
    })
}

pub fn save_environment_conn(
    connection: &Connection,
    payload: &SaveEnvironmentPayload,
) -> Result<Environment, String> {
    let environment = &payload.environment;

    if environment.name.trim().is_empty() {
        return Err("environment name must not be empty".to_string());
    }

    let id = if environment.id.trim().is_empty() {
        Uuid::new_v4().to_string()
    } else {
        environment.id.trim().to_string()
    };

    let exists: bool = connection
        .query_row(
            "SELECT COUNT(*) FROM environments WHERE id = ?1",
            params![id],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|error| format!("failed to check environment existence: {error}"))?
        > 0;

    if exists {
        connection
            .execute(
                "UPDATE environments
                 SET name = ?1,
                     updated_at = datetime('now')
                 WHERE id = ?2",
                params![environment.name, id],
            )
            .map_err(|error| format!("failed to update environment: {error}"))?;

        connection
            .execute(
                "DELETE FROM environment_variables WHERE environment_id = ?1",
                params![id],
            )
            .map_err(|error| format!("failed to clear environment variables: {error}"))?;
    } else {
        connection
            .execute(
                "INSERT INTO environments (id, name) VALUES (?1, ?2)",
                params![id, environment.name],
            )
            .map_err(|error| format!("failed to insert environment: {error}"))?;
    }

    for variable in &environment.variables {
        if variable.key.trim().is_empty() {
            continue;
        }

        let variable_id = if variable.id.trim().is_empty() {
            Uuid::new_v4().to_string()
        } else {
            variable.id.trim().to_string()
        };

        let enabled: i64 = if variable.enabled { 1 } else { 0 };

        connection
            .execute(
                "INSERT OR REPLACE INTO environment_variables
                 (id, environment_id, key, value, enabled)
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                params![variable_id, id, variable.key, variable.value, enabled],
            )
            .map_err(|error| format!("failed to save environment variable: {error}"))?;
    }

    get_environment_conn(connection, &id)
}

pub fn delete_environment_conn(connection: &Connection, id: &str) -> Result<(), String> {
    connection
        .execute("DELETE FROM environments WHERE id = ?1", params![id])
        .map_err(|error| format!("failed to delete environment: {error}"))?;

    connection
        .execute(
            "UPDATE settings
             SET value = NULL
             WHERE key = 'active_environment_id' AND value = ?1",
            params![id],
        )
        .map_err(|error| format!("failed to clear active environment: {error}"))?;

    Ok(())
}

pub fn set_active_environment_conn(
    connection: &Connection,
    id: Option<String>,
) -> Result<(), String> {
    match id {
        Some(id) => {
            let exists: bool = connection
                .query_row(
                    "SELECT COUNT(*) FROM environments WHERE id = ?1",
                    params![&id],
                    |row| row.get::<_, i64>(0),
                )
                .map_err(|error| format!("failed to check environment existence: {error}"))?
                > 0;

            if !exists {
                return Err("environment not found".to_string());
            }

            connection
                .execute(
                    "INSERT INTO settings (key, value)
                     VALUES ('active_environment_id', ?1)
                     ON CONFLICT(key) DO UPDATE SET value = ?1",
                    params![id],
                )
                .map_err(|error| format!("failed to set active environment: {error}"))?;
        }
        None => {
            connection
                .execute(
                    "INSERT INTO settings (key, value)
                     VALUES ('active_environment_id', NULL)
                     ON CONFLICT(key) DO UPDATE SET value = NULL",
                    [],
                )
                .map_err(|error| format!("failed to clear active environment: {error}"))?;
        }
    }

    Ok(())
}

pub fn get_active_environment_id_conn(connection: &Connection) -> Result<Option<String>, String> {
    let result: Result<Option<String>, rusqlite::Error> = connection.query_row(
        "SELECT value FROM settings WHERE key = 'active_environment_id'",
        [],
        |row| row.get(0),
    );

    match result {
        Ok(value) => Ok(value),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(error) => Err(error.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn migration_creates_core_tables() {
        let connection = Connection::open_in_memory().unwrap();

        migrate(&connection).unwrap();

        let collections: i64 = connection
            .query_row("SELECT COUNT(*) FROM collections", [], |row| row.get(0))
            .unwrap();

        let requests: i64 = connection
            .query_row("SELECT COUNT(*) FROM requests", [], |row| row.get(0))
            .unwrap();

        let environments: i64 = connection
            .query_row("SELECT COUNT(*) FROM environments", [], |row| row.get(0))
            .unwrap();

        let secret_metadata: i64 = connection
            .query_row("SELECT COUNT(*) FROM secret_metadata", [], |row| row.get(0))
            .unwrap();

        assert_eq!(collections, 0);
        assert_eq!(requests, 0);
        assert_eq!(environments, 0);
        assert_eq!(secret_metadata, 0);
    }

    #[test]
    fn environment_crud_and_active_state() {
        let connection = Connection::open_in_memory().unwrap();
        migrate(&connection).unwrap();

        let environment = Environment {
            id: String::new(),
            name: "Local".to_string(),
            variables: vec![EnvironmentVariable {
                id: String::new(),
                key: "base_url".to_string(),
                value: "http://localhost:8080".to_string(),
                enabled: true,
            }],
            created_at: String::new(),
            updated_at: String::new(),
        };

        let saved = save_environment_conn(
            &connection,
            &SaveEnvironmentPayload { environment },
        )
        .unwrap();

        assert_eq!(saved.name, "Local");
        assert_eq!(saved.variables.len(), 1);
        assert_eq!(saved.variables[0].key, "base_url");

        let active_before = get_active_environment_id_conn(&connection).unwrap();
        assert!(active_before.is_none());

        set_active_environment_conn(&connection, Some(saved.id.clone())).unwrap();

        let active_after = get_active_environment_id_conn(&connection).unwrap();
        assert_eq!(active_after, Some(saved.id.clone()));

        let loaded_variables =
            load_enabled_environment_variables_from_connection(&connection, &saved.id).unwrap();

        assert_eq!(
            loaded_variables.get("base_url"),
            Some(&"http://localhost:8080".to_string())
        );

        delete_environment_conn(&connection, &saved.id).unwrap();

        let active_after_delete = get_active_environment_id_conn(&connection).unwrap();
        assert!(active_after_delete.is_none());

        let environments = list_environments_conn(&connection).unwrap();
        assert!(environments.is_empty());
    }

    fn load_enabled_environment_variables_from_connection(
        connection: &Connection,
        environment_id: &str,
    ) -> Result<HashMap<String, String>, String> {
        let mut statement = connection
            .prepare(
                "SELECT key, value
                 FROM environment_variables
                 WHERE environment_id = ?1 AND enabled = 1
                 ORDER BY rowid",
            )
            .map_err(|error| format!("failed to prepare environment query: {error}"))?;

        let rows = statement
            .query_map([environment_id], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })
            .map_err(|error| format!("failed to query environment variables: {error}"))?;

        let mut variables = HashMap::new();

        for row in rows {
            let (key, value) =
                row.map_err(|error| format!("failed to read environment row: {error}"))?;
            variables.insert(key, value);
        }

        Ok(variables)
    }
}
""",

"src-tauri/src/commands/mod.rs": """pub mod db;
pub mod environments;
pub mod execute;
pub mod secrets;
""",

"src-tauri/src/commands/environments.rs": """use tauri::AppHandle;

use crate::models::{Environment, SaveEnvironmentPayload};

#[tauri::command]
pub fn list_environments(app: AppHandle) -> Result<Vec<Environment>, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::list_environments_conn(&connection)
}

#[tauri::command]
pub fn save_environment(
    app: AppHandle,
    payload: SaveEnvironmentPayload,
) -> Result<Environment, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::save_environment_conn(&connection, &payload)
}

#[tauri::command]
pub fn delete_environment(app: AppHandle, id: String) -> Result<(), String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::delete_environment_conn(&connection, &id)
}

#[tauri::command]
pub fn set_active_environment(app: AppHandle, id: Option<String>) -> Result<(), String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::set_active_environment_conn(&connection, id)
}

#[tauri::command]
pub fn get_active_environment_id(app: AppHandle) -> Result<Option<String>, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::get_active_environment_id_conn(&connection)
}
""",

"src-tauri/src/main.rs": """#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod db;
mod env;
mod error;
mod http;
mod models;
mod vault;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle().clone();

            db::init_db_for_app(&handle)
                .map(|_| ())
                .map_err(|error| -> Box<dyn std::error::Error> { error.into() })
        })
        .invoke_handler(tauri::generate_handler![
            commands::db::init_db,
            commands::secrets::store_secret,
            commands::secrets::get_secret,
            commands::secrets::secret_exists,
            commands::execute::execute_request,
            commands::environments::list_environments,
            commands::environments::save_environment,
            commands::environments::delete_environment,
            commands::environments::set_active_environment,
            commands::environments::get_active_environment_id
        ])
        .run(tauri::generate_context!())
        .expect("error while running Chapar");
}
""",

"src/lib/utils/id.ts": """export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
""",

"src/lib/services/api.ts": """import { invoke } from "@tauri-apps/api/core";
import type {
  Environment,
  RequestPayload,
  ResponsePayload,
  SaveEnvironmentPayload
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
  }
};
""",

"src/lib/stores/ui.ts": """import { writable } from "svelte/store";

export type AppView = "requests" | "environments" | "secrets";

export const appView = writable<AppView>("requests");
""",

"src/lib/stores/environments.ts": """import { writable, get } from "svelte/store";
import { api } from "$lib/services/api";
import { newId } from "$lib/utils/id";
import type { Environment } from "$lib/types/api";

export const environments = writable<Environment[]>([]);
export const activeEnvironmentId = writable<string | null>(null);
export const environmentsError = writable<string | null>(null);

export async function loadEnvironments(): Promise<void> {
  try {
    const list = await api.listEnvironments();
    const activeId = await api.getActiveEnvironmentId();

    environments.set(list);
    activeEnvironmentId.set(activeId);
    environmentsError.set(null);
  } catch (error) {
    environmentsError.set(String(error));
  }
}

export function createEmptyEnvironment(name: string): Environment {
  const now = new Date().toISOString();

  return {
    id: newId(),
    name,
    variables: [],
    createdAt: now,
    updatedAt: now
  };
}

export async function saveEnvironment(environment: Environment): Promise<Environment> {
  const saved = await api.saveEnvironment({ environment });

  environments.update((list) => {
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

export async function deleteEnvironment(id: string): Promise<void> {
  await api.deleteEnvironment(id);

  environments.update((list) => list.filter((item) => item.id !== id));

  if (get(activeEnvironmentId) === id) {
    activeEnvironmentId.set(null);
  }
}

export async function setActiveEnvironment(id: string | null): Promise<void> {
  await api.setActiveEnvironment(id);
  activeEnvironmentId.set(id);
}
""",

"src/lib/stores/requestEditor.ts": """import { writable } from "svelte/store";
import type { HttpMethod, KeyValueEntry, RequestBodyKind } from "$lib/types/api";

export interface RequestEditorState {
  method: HttpMethod;
  url: string;
  environmentId: string;
  bodyKind: RequestBodyKind;
  bodyText: string;
  timeoutMs: string;
  followRedirects: boolean;
  headers: KeyValueEntry[];
}

function createRequestEditorStore() {
  const { subscribe, set, update } = writable<RequestEditorState>({
    method: "GET",
    url: "http://localhost:8080",
    environmentId: "",
    bodyKind: "none",
    bodyText: "",
    timeoutMs: "",
    followRedirects: true,
    headers: []
  });

  return {
    subscribe,
    set,
    update,
    patch(partial: Partial<RequestEditorState>) {
      update((current) => ({
        ...current,
        ...partial
      }));
    }
  };
}

export const requestEditor = createRequestEditorStore();
""",

"src/lib/components/KeyValueEditor.svelte": """<script lang="ts">
  import { Plus, Trash2 } from "@lucide/svelte";
  import { newId } from "$lib/utils/id";
  import type { KeyValueEntry } from "$lib/types/api";

  let {
    entries = [],
    onChange
  }: {
    entries: KeyValueEntry[];
    onChange: (entries: KeyValueEntry[]) => void;
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
        class="w-1/3 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Key"
        value={entry.key}
        oninput={(event) => onKey(entry.id, event)}
      />

      <input
        class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Value"
        value={entry.value}
        oninput={(event) => onValue(entry.id, event)}
      />

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

"src/lib/components/EnvironmentsPanel.svelte": """<script lang="ts">
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
""",

"src/lib/components/Sidebar.svelte": """<script lang="ts">
  import { Database, Folder, Send, ShieldCheck } from "@lucide/svelte";
  import { appView, type AppView } from "$lib/stores/ui";

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
    }
  ];
</script>

<aside class="flex h-full w-56 flex-col border-r border-neutral-800 bg-neutral-950">
  <div class="border-b border-neutral-800 p-4">
    <p class="text-sm font-semibold tracking-wide">Chapar</p>
    <p class="mt-1 text-xs text-neutral-500">Local-first API client</p>
  </div>

  <nav class="flex-1 overflow-y-auto p-2">
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

  <div class="border-t border-neutral-800 p-3 text-xs text-neutral-600">
    Phase 5 environment UI
  </div>
</aside>
""",

"src/lib/components/RequestPane.svelte": """<script lang="ts">
  import { onMount } from "svelte";
  import { Loader2, Play } from "@lucide/svelte";
  import { get } from "svelte/store";
  import MonacoEditor from "$lib/components/MonacoEditor.svelte";
  import KeyValueEditor from "$lib/components/KeyValueEditor.svelte";
  import { requestEditor } from "$lib/stores/requestEditor";
  import { responseStore } from "$lib/stores/response";
  import {
    activeEnvironmentId,
    environments,
    loadEnvironments
  } from "$lib/stores/environments";
  import { api } from "$lib/services/api";
  import { newId } from "$lib/utils/id";
  import type {
    HttpMethod,
    KeyValueEntry,
    RequestBodyKind,
    RequestPayload
  } from "$lib/types/api";

  let method = $state<HttpMethod>("GET");
  let url = $state("http://localhost:8080");
  let environmentId = $state("");
  let bodyKind = $state<RequestBodyKind>("none");
  let bodyText = $state("");
  let timeoutMs = $state("");
  let headers = $state<KeyValueEntry[]>([]);

  onMount(() => {
    loadEnvironments();

    const unsubscribe = requestEditor.subscribe((state) => {
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
    requestEditor.set({
      method,
      url,
      environmentId,
      bodyKind,
      bodyText,
      timeoutMs,
      followRedirects: true,
      headers
    });
  }

  $effect(() => {
    bodyText;
    syncStore();
  });

  async function execute() {
    syncStore();
    responseStore.start();

    try {
      const now = new Date().toISOString();
      const timeoutValue = timeoutMs.trim() === "" ? null : Number(timeoutMs);

      const selectedEnvironmentId =
        environmentId.trim() === ""
          ? get(activeEnvironmentId)
          : environmentId.trim();

      const payload: RequestPayload = {
        request: {
          id: newId(),
          collectionId: null,
          name: "Untitled Request",
          method,
          url: url.trim(),
          params: [],
          headers,
          body: {
            kind: bodyKind,
            text: bodyText,
            form: []
          },
          allowedSecretIds: [],
          timeoutMs:
            timeoutValue !== null && Number.isFinite(timeoutValue)
              ? timeoutValue
              : null,
          followRedirects: true,
          position: 0,
          createdAt: now,
          updatedAt: now
        },
        environmentId: selectedEnvironmentId,
        timeoutMs:
          timeoutValue !== null && Number.isFinite(timeoutValue)
            ? timeoutValue
            : null,
        followRedirects: true,
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
  import { appView } from "$lib/stores/ui";
  import { loadEnvironments } from "$lib/stores/environments";

  onMount(() => {
    loadEnvironments();
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
    {:else}
      <div class="flex h-full items-center justify-center text-sm text-neutral-600">
        Secrets UI will be polished in the next security pass.
      </div>
    {/if}
  </div>
</div>
""",
}


REQUIRED_PHASE4_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src/lib/components/MonacoEditor.svelte",
    "src/lib/components/ResponsePane.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/http.rs",
    "src-tauri/src/env.rs",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def verify_phase4() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE4_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 4 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 4 skeleton detected")


def write_phase5_files() -> None:
    for relative_path, content in PHASE5_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase4()
    write_phase5_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)
    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 5 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nEnvironment test:")
    print("  1. Open Environments in sidebar")
    print("  2. Create environment: Local")
    print("  3. Add variable: base_url = http://localhost:8080")
    print("  4. Save")
    print("  5. Click the circle/check to set it active")
    print("  6. Open Requests")
    print("  7. Start server: python3 -m http.server 8080")
    print("  8. Set URL: {{base_url}}/")
    print("  9. Click Send")
    print("\nExpected:")
    print("  Completed: 200 OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())