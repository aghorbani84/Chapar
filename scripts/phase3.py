#!/usr/bin/env python3
"""
Chapar Phase 3: HTTP engine.

This script:
- verifies Phase 2 files exist
- adds reqwest, base64, and url crates
- implements environment and secret variable replacement
- implements the execute_request Tauri command
- updates the frontend with an HTTP request test panel
- runs frontend and Rust verification checks

This script uses only the Python standard library.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PHASE3_FILES: dict[str, str] = {
"src-tauri/src/db.rs": """use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::Connection;
use tauri::Manager;

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
}
""",

"src-tauri/src/env.rs": """use std::collections::HashMap;

pub fn push_unique(list: &mut Vec<String>, value: String) {
    if !list.iter().any(|item| item == &value) {
        list.push(value);
    }
}

fn resolve_token(
    token: &str,
    environment: &HashMap<String, String>,
    allowed_secret_ids: &[String],
    secret_cache: &mut HashMap<String, Option<String>>,
    unresolved: &mut Vec<String>,
) -> Option<String> {
    if let Some(secret_id) = token.strip_prefix("secret:") {
        let secret_id = secret_id.trim();

        if secret_id.is_empty() {
            push_unique(unresolved, "secret:".to_string());
            return None;
        }

        let allowed = allowed_secret_ids
            .iter()
            .any(|allowed_id| allowed_id == secret_id);

        if !allowed {
            push_unique(
                unresolved,
                format!("unauthorized-secret:{}", secret_id),
            );
            return None;
        }

        let cached = match secret_cache.get(secret_id) {
            Some(existing) => existing.clone(),
            None => {
                let loaded = crate::vault::get_secret(secret_id).ok();
                secret_cache.insert(secret_id.to_string(), loaded.clone());
                loaded
            }
        };

        return match cached {
            Some(value) => Some(value),
            None => {
                push_unique(unresolved, format!("secret:{}", secret_id));
                None
            }
        };
    }

    let key = token.trim();

    match environment.get(key) {
        Some(value) => Some(value.clone()),
        None => {
            push_unique(unresolved, key.to_string());
            None
        }
    }
}

pub fn replace_text(
    input: &str,
    environment: &HashMap<String, String>,
    allowed_secret_ids: &[String],
    secret_cache: &mut HashMap<String, Option<String>>,
    unresolved: &mut Vec<String>,
) -> String {
    let mut output = String::new();
    let mut remaining = input;

    while let Some(start) = remaining.find("{{") {
        output.push_str(&remaining[..start]);

        let after_start = &remaining[start + 2..];

        match after_start.find("}}") {
            Some(end) => {
                let token = after_start[..end].trim();

                match resolve_token(
                    token,
                    environment,
                    allowed_secret_ids,
                    secret_cache,
                    unresolved,
                ) {
                    Some(value) => output.push_str(&value),
                    None => {
                        if token.starts_with("secret:") {
                            output.push_str("");
                        } else {
                            output.push_str("{{");
                            output.push_str(token);
                            output.push_str("}}");
                        }
                    }
                }

                remaining = &after_start[end + 2..];
            }
            None => {
                output.push_str("{{");
                output.push_str(after_start);
                remaining = "";
                break;
            }
        }
    }

    output.push_str(remaining);
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn replaces_environment_variables() {
        let mut environment = HashMap::new();
        environment.insert(
            "base_url".to_string(),
            "https://api.example.com".to_string(),
        );

        let allowed_secret_ids: Vec<String> = Vec::new();
        let mut secret_cache = HashMap::new();
        let mut unresolved = Vec::new();

        let output = replace_text(
            "{{base_url}}/users",
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        assert_eq!(output, "https://api.example.com/users");
        assert!(unresolved.is_empty());
    }

    #[test]
    fn tracks_missing_environment_variables() {
        let environment = HashMap::new();
        let allowed_secret_ids: Vec<String> = Vec::new();
        let mut secret_cache = HashMap::new();
        let mut unresolved = Vec::new();

        let output = replace_text(
            "{{missing}}/users",
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        assert_eq!(output, "{{missing}}/users");
        assert_eq!(unresolved, vec!["missing".to_string()]);
    }

    #[test]
    fn rejects_unauthorized_secret_variables() {
        let environment = HashMap::new();
        let allowed_secret_ids: Vec<String> = Vec::new();
        let mut secret_cache = HashMap::new();
        let mut unresolved = Vec::new();

        let output = replace_text(
            "Bearer {{secret:prod-api-key}}",
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        assert_eq!(output, "Bearer ");
        assert_eq!(
            unresolved,
            vec!["unauthorized-secret:prod-api-key".to_string()]
        );
    }
}
""",

"src-tauri/src/http.rs": """use std::collections::HashMap;
use std::time::{Duration, Instant};

use base64::{engine::general_purpose::STANDARD, Engine as _};
use reqwest::header::{HeaderMap, HeaderName, HeaderValue, CONTENT_TYPE, USER_AGENT};
use reqwest::redirect::Policy;
use reqwest::{Client, Method};
use serde_json::Value;
use url::Url;

use crate::env::{push_unique, replace_text};
use crate::models::{
    HttpMethod, RequestBodyKind, RequestPayload, ResponseBody, ResponseBodyKind, ResponseHeader,
    ResponsePayload,
};

fn convert_method(method: HttpMethod) -> Method {
    match method {
        HttpMethod::Get => Method::GET,
        HttpMethod::Post => Method::POST,
        HttpMethod::Put => Method::PUT,
        HttpMethod::Patch => Method::PATCH,
        HttpMethod::Delete => Method::DELETE,
        HttpMethod::Head => Method::HEAD,
        HttpMethod::Options => Method::OPTIONS,
    }
}

fn error_response(
    request_id: &str,
    unresolved_variables: Vec<String>,
    message: &str,
) -> ResponsePayload {
    ResponsePayload {
        request_id: request_id.to_string(),
        status: 0,
        status_text: String::new(),
        http_version: String::new(),
        latency_ms: 0,
        size_bytes: 0,
        headers: Vec::new(),
        body: ResponseBody {
            kind: ResponseBodyKind::Text,
            text: Some(message.to_string()),
            base64: None,
        },
        unresolved_variables,
        error: Some(message.to_string()),
    }
}

pub async fn execute_request(
    app: &tauri::AppHandle,
    payload: RequestPayload,
) -> Result<ResponsePayload, String> {
    let RequestPayload {
        request,
        environment_id,
        timeout_ms,
        follow_redirects,
        max_redirects,
    } = payload;

    let environment = match environment_id {
        Some(environment_id) => {
            crate::db::load_enabled_environment_variables(app, &environment_id)?
        }
        None => HashMap::new(),
    };

    let allowed_secret_ids = request.allowed_secret_ids.clone();
    let mut secret_cache: HashMap<String, Option<String>> = HashMap::new();
    let mut unresolved: Vec<String> = Vec::new();

    let url_text = replace_text(
        &request.url,
        &environment,
        &allowed_secret_ids,
        &mut secret_cache,
        &mut unresolved,
    );

    let mut query_pairs: Vec<(String, String)> = Vec::new();

    for parameter in &request.params {
        if !parameter.enabled {
            continue;
        }

        let key = replace_text(
            &parameter.key,
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        let value = replace_text(
            &parameter.value,
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        if key.trim().is_empty() {
            continue;
        }

        query_pairs.push((key, value));
    }

    let mut header_map = HeaderMap::new();

    for header in &request.headers {
        if !header.enabled {
            continue;
        }

        let key = replace_text(
            &header.key,
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        let key = key.trim().to_string();

        if key.is_empty() {
            continue;
        }

        let value = match &header.secret_id {
            Some(secret_id) => {
                let secret_id = secret_id.trim();

                if secret_id.is_empty() {
                    push_unique(&mut unresolved, "secret:".to_string());
                    String::new()
                } else if !allowed_secret_ids
                    .iter()
                    .any(|allowed_id| allowed_id == secret_id)
                {
                    push_unique(
                        &mut unresolved,
                        format!("unauthorized-secret:{}", secret_id),
                    );
                    String::new()
                } else {
                    let cached = match secret_cache.get(secret_id) {
                        Some(existing) => existing.clone(),
                        None => {
                            let loaded = crate::vault::get_secret(secret_id).ok();
                            secret_cache.insert(secret_id.to_string(), loaded.clone());
                            loaded
                        }
                    };

                    match cached {
                        Some(value) => value,
                        None => {
                            push_unique(
                                &mut unresolved,
                                format!("secret:{}", secret_id),
                            );
                            String::new()
                        }
                    }
                }
            }
            None => replace_text(
                &header.value,
                &environment,
                &allowed_secret_ids,
                &mut secret_cache,
                &mut unresolved,
            ),
        };

        let header_name = match HeaderName::from_bytes(key.as_bytes()) {
            Ok(header_name) => header_name,
            Err(_) => {
                return Ok(error_response(
                    &request.id,
                    unresolved,
                    "invalid header name",
                ))
            }
        };

        let header_value = match HeaderValue::from_str(&value) {
            Ok(header_value) => header_value,
            Err(_) => {
                return Ok(error_response(
                    &request.id,
                    unresolved,
                    "invalid header value",
                ))
            }
        };

        header_map.insert(header_name, header_value);
    }

    if !header_map.contains_key(USER_AGENT) {
        header_map.insert(USER_AGENT, HeaderValue::from_static("Chapar/0.1"));
    }

    let mut body_text: Option<String> = None;
    let mut form_pairs: Vec<(String, String)> = Vec::new();

    match request.body.kind {
        RequestBodyKind::None => {}
        RequestBodyKind::FormUrlEncoded => {
            for entry in &request.body.form {
                if !entry.enabled {
                    continue;
                }

                let key = replace_text(
                    &entry.key,
                    &environment,
                    &allowed_secret_ids,
                    &mut secret_cache,
                    &mut unresolved,
                );

                let value = replace_text(
                    &entry.value,
                    &environment,
                    &allowed_secret_ids,
                    &mut secret_cache,
                    &mut unresolved,
                );

                if key.trim().is_empty() {
                    continue;
                }

                form_pairs.push((key, value));
            }
        }
        RequestBodyKind::Json | RequestBodyKind::Text | RequestBodyKind::Raw => {
            let replaced = replace_text(
                &request.body.text,
                &environment,
                &allowed_secret_ids,
                &mut secret_cache,
                &mut unresolved,
            );

            if !replaced.is_empty() {
                body_text = Some(replaced);
            }
        }
    }

    if !header_map.contains_key(CONTENT_TYPE) {
        match request.body.kind {
            RequestBodyKind::Json => {
                if body_text.is_some() {
                    header_map.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
                }
            }
            RequestBodyKind::Text | RequestBodyKind::Raw => {
                if body_text.is_some() {
                    header_map.insert(
                        CONTENT_TYPE,
                        HeaderValue::from_static("text/plain; charset=utf-8"),
                    );
                }
            }
            RequestBodyKind::None | RequestBodyKind::FormUrlEncoded => {}
        }
    }

    if !unresolved.is_empty() {
        return Ok(error_response(
            &request.id,
            unresolved,
            "request contains unresolved or unauthorized variables",
        ));
    }

    let url = match Url::parse(&url_text) {
        Ok(url) => url,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "invalid URL",
            ))
        }
    };

    let mut client_builder = Client::builder();

    if follow_redirects {
        client_builder =
            client_builder.redirect(Policy::limited(max_redirects.unwrap_or(10)));
    } else {
        client_builder = client_builder.redirect(Policy::none());
    }

    if let Some(timeout_ms) = timeout_ms.or(request.timeout_ms) {
        if timeout_ms > 0 {
            client_builder = client_builder.timeout(Duration::from_millis(timeout_ms));
        }
    }

    let client = match client_builder.build() {
        Ok(client) => client,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "failed to create HTTP client",
            ))
        }
    };

    let mut request_builder = client.request(convert_method(request.method), url);

    if !query_pairs.is_empty() {
        request_builder = request_builder.query(&query_pairs);
    }

    request_builder = request_builder.headers(header_map);

    match request.body.kind {
        RequestBodyKind::FormUrlEncoded => {
            if !form_pairs.is_empty() {
                request_builder = request_builder.form(&form_pairs);
            }
        }
        RequestBodyKind::Json | RequestBodyKind::Text | RequestBodyKind::Raw => {
            if let Some(text) = body_text {
                request_builder = request_builder.body(text);
            }
        }
        RequestBodyKind::None => {}
    }

    let started = Instant::now();

    let response = match request_builder.send().await {
        Ok(response) => response,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "request failed to complete",
            ))
        }
    };

    let status = response.status();
    let status_text = status.canonical_reason().unwrap_or("").to_string();
    let http_version = format!("{:?}", response.version());

    let headers: Vec<ResponseHeader> = response
        .headers()
        .iter()
        .map(|(name, value)| ResponseHeader {
            name: name.as_str().to_string(),
            value: value
                .to_str()
                .unwrap_or("[binary header value]")
                .to_string(),
        })
        .collect();

    let bytes = match response.bytes().await {
        Ok(bytes) => bytes,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "failed to read response body",
            ))
        }
    };

    let latency_ms = started.elapsed().as_millis() as u64;
    let size_bytes = bytes.len() as u64;

    let body = if bytes.is_empty() {
        ResponseBody {
            kind: ResponseBodyKind::Text,
            text: Some(String::new()),
            base64: None,
        }
    } else if let Ok(json) = serde_json::from_slice::<Value>(&bytes) {
        let pretty = serde_json::to_string_pretty(&json)
            .unwrap_or_else(|_| String::from_utf8_lossy(&bytes).into_owned());

        ResponseBody {
            kind: ResponseBodyKind::Json,
            text: Some(pretty),
            base64: None,
        }
    } else if let Ok(text) = String::from_utf8(bytes.to_vec()) {
        ResponseBody {
            kind: ResponseBodyKind::Text,
            text: Some(text),
            base64: None,
        }
    } else {
        ResponseBody {
            kind: ResponseBodyKind::Binary,
            text: None,
            base64: Some(STANDARD.encode(&bytes)),
        }
    };

    Ok(ResponsePayload {
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
}
""",

"src-tauri/src/commands/mod.rs": """pub mod db;
pub mod execute;
pub mod secrets;
""",

"src-tauri/src/commands/execute.rs": """use tauri::AppHandle;

use crate::models::{RequestPayload, ResponsePayload};

#[tauri::command]
pub async fn execute_request(
    app: AppHandle,
    payload: RequestPayload,
) -> Result<ResponsePayload, String> {
    crate::http::execute_request(&app, payload).await
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
            commands::execute::execute_request
        ])
        .run(tauri::generate_context!())
        .expect("error while running Chapar");
}
""",

"src/routes/+page.svelte": """<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import type {
    HttpMethod,
    RequestBodyKind,
    RequestPayload,
    ResponsePayload
  } from "$lib/types/api";

  let dbStatus = $state("Idle");
  let dbPath = $state<string | null>(null);
  let dbBusy = $state(false);

  let secretId = $state("");
  let secretValue = $state("");
  let secretStatus = $state("Idle");
  let retrievedSecret = $state<string | null>(null);
  let secretExists = $state<boolean | null>(null);
  let secretBusy = $state(false);

  let requestMethod = $state("GET");
  let requestUrl = $state("https://api.github.com/repos/tauri-apps/tauri");
  let environmentId = $state("");
  let bodyKind = $state("none");
  let bodyText = $state("");
  let timeoutMs = $state("");

  let httpStatus = $state("Idle");
  let httpBusy = $state(false);
  let response = $state<ResponsePayload | null>(null);

  function newId(): string {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
      return crypto.randomUUID();
    }

    return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function initDb() {
    dbBusy = true;
    dbStatus = "Initializing database...";
    dbPath = null;

    try {
      const path = await invoke<string>("init_db");
      dbPath = path;
      dbStatus = "Database initialized.";
    } catch (error) {
      dbStatus = `Database initialization failed: ${String(error)}`;
    } finally {
      dbBusy = false;
    }
  }

  async function storeSecret() {
    secretBusy = true;
    secretStatus = "Storing secret...";
    retrievedSecret = null;
    secretExists = null;

    try {
      await invoke("store_secret", {
        id: secretId.trim(),
        value: secretValue
      });

      secretStatus = `Secret stored: ${secretId.trim()}`;
      secretValue = "";
    } catch (error) {
      secretStatus = `Store failed: ${String(error)}`;
    } finally {
      secretBusy = false;
    }
  }

  async function getSecret() {
    secretBusy = true;
    secretStatus = "Retrieving secret...";
    retrievedSecret = null;
    secretExists = null;

    try {
      const value = await invoke<string>("get_secret", {
        id: secretId.trim()
      });

      retrievedSecret = value;
      secretStatus = "Secret retrieved. Diagnostic use only.";
    } catch (error) {
      secretStatus = `Retrieve failed: ${String(error)}`;
    } finally {
      secretBusy = false;
    }
  }

  async function checkSecretExists() {
    secretBusy = true;
    secretStatus = "Checking secret...";
    retrievedSecret = null;
    secretExists = null;

    try {
      const exists = await invoke<boolean>("secret_exists", {
        id: secretId.trim()
      });

      secretExists = exists;
      secretStatus = "Secret existence checked.";
    } catch (error) {
      secretStatus = `Exists check failed: ${String(error)}`;
    } finally {
      secretBusy = false;
    }
  }

  function clearSecretTest() {
    secretId = "";
    secretValue = "";
    secretStatus = "Idle";
    retrievedSecret = null;
    secretExists = null;
  }

  async function executeRequest() {
    httpBusy = true;
    httpStatus = "Executing request...";
    response = null;

    try {
      const now = new Date().toISOString();
      const timeoutValue =
        timeoutMs.trim() === "" ? null : Number(timeoutMs);

      const payload: RequestPayload = {
        request: {
          id: newId(),
          collectionId: null,
          name: "Phase 3 Test Request",
          method: requestMethod as HttpMethod,
          url: requestUrl.trim(),
          params: [],
          headers: [],
          body: {
            kind: bodyKind as RequestBodyKind,
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
        environmentId:
          environmentId.trim() === "" ? null : environmentId.trim(),
        timeoutMs:
          timeoutValue !== null && Number.isFinite(timeoutValue)
            ? timeoutValue
            : null,
        followRedirects: true,
        maxRedirects: 10
      };

      const result = await invoke<ResponsePayload>("execute_request", {
        payload
      });

      response = result;

      if (result.error) {
        httpStatus = `Completed with error: ${result.error}`;
      } else {
        httpStatus = `Completed: ${result.status} ${result.statusText}`;
      }
    } catch (error) {
      httpStatus = `Execution failed: ${String(error)}`;
    } finally {
      httpBusy = false;
    }
  }
</script>

<main class="p-6">
  <h1 class="text-xl font-semibold">Chapar</h1>

  <section class="mt-6 rounded border border-neutral-800 p-4">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-400">
      Phase 1: Database
    </h2>

    <button
      class="mt-3 rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
      onclick={initDb}
      disabled={dbBusy}
    >
      Initialize DB
    </button>

    <p class="mt-3 text-sm" data-testid="db-status">
      {dbStatus}
    </p>

    {#if dbPath}
      <p class="mt-2 break-all text-xs text-neutral-400" data-testid="db-path">
        {dbPath}
      </p>
    {/if}
  </section>

  <section class="mt-6 rounded border border-neutral-800 p-4">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-400">
      Phase 2: Secret Vault Diagnostic
    </h2>

    <p class="mt-2 text-xs text-amber-400">
      Warning: Get Secret returns the raw secret to the frontend. This is for testing only.
    </p>

    <div class="mt-4 grid gap-3">
      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Secret ID, for example: prod-api-key"
        bind:value={secretId}
        data-testid="secret-id"
      />

      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        type="password"
        placeholder="Secret value"
        bind:value={secretValue}
        data-testid="secret-value"
      />
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <button
        class="rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={storeSecret}
        disabled={secretBusy || secretId.trim() === "" || secretValue === ""}
        data-testid="store-secret"
      >
        Store Secret
      </button>

      <button
        class="rounded bg-neutral-700 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={getSecret}
        disabled={secretBusy || secretId.trim() === ""}
        data-testid="get-secret"
      >
        Get Secret
      </button>

      <button
        class="rounded bg-neutral-700 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={checkSecretExists}
        disabled={secretBusy || secretId.trim() === ""}
        data-testid="secret-exists"
      >
        Exists
      </button>

      <button
        class="rounded bg-neutral-800 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={clearSecretTest}
        disabled={secretBusy}
        data-testid="clear-secret"
      >
        Clear
      </button>
    </div>

    <p class="mt-3 text-sm" data-testid="secret-status">
      {secretStatus}
    </p>

    {#if secretExists !== null}
      <p class="mt-2 text-xs text-neutral-400" data-testid="secret-exists-result">
        Secret exists: {secretExists ? "yes" : "no"}
      </p>
    {/if}

    {#if retrievedSecret !== null}
      <p class="mt-2 break-all text-xs text-red-400" data-testid="retrieved-secret">
        {retrievedSecret}
      </p>
    {/if}
  </section>

  <section class="mt-6 rounded border border-neutral-800 p-4">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-400">
      Phase 3: HTTP Engine
    </h2>

    <div class="mt-4 grid gap-3">
      <div class="flex gap-2">
        <select
          class="w-32 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          bind:value={requestMethod}
          data-testid="http-method"
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
          placeholder="Example: http://localhost:8080"
          bind:value={requestUrl}
          data-testid="http-url"
        />
      </div>

      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Environment ID, optional"
        bind:value={environmentId}
        data-testid="http-environment-id"
      />

      <div class="flex gap-2">
        <select
          class="w-40 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          bind:value={bodyKind}
          data-testid="http-body-kind"
        >
          <option value="none">No Body</option>
          <option value="json">JSON</option>
          <option value="text">Text</option>
          <option value="raw">Raw</option>
        </select>

        <input
          class="w-40 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          placeholder="Timeout ms, optional"
          bind:value={timeoutMs}
          data-testid="http-timeout"
        />
      </div>

      {#if bodyKind !== "none"}
        <textarea
          class="h-40 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 font-mono text-sm"
          placeholder="Example JSON: hello world"
          bind:value={bodyText}
          data-testid="http-body-text"
        ></textarea>
      {/if}
    </div>

    <button
      class="mt-4 rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
      onclick={executeRequest}
      disabled={httpBusy || requestUrl.trim() === ""}
      data-testid="http-execute"
    >
      Execute Request
    </button>

    <p class="mt-3 text-sm" data-testid="http-status">
      {httpStatus}
    </p>

    {#if response}
      <div class="mt-4 grid gap-2 text-xs text-neutral-300">
        <p>Status: {response.status} {response.statusText}</p>
        <p>Latency: {response.latencyMs} ms</p>
        <p>Size: {response.sizeBytes} bytes</p>
        <p>HTTP Version: {response.httpVersion}</p>

        {#if response.error}
          <p class="text-red-400">Error: {response.error}</p>
        {/if}

        {#if response.unresolvedVariables.length > 0}
          <p class="text-amber-400">
            Unresolved: {response.unresolvedVariables.join(", ")}
          </p>
        {/if}

        <details class="mt-2">
          <summary class="cursor-pointer text-neutral-400">Headers</summary>
          <div class="mt-2 grid gap-1">
            {#each response.headers as header}
              <p class="break-all">
                <span class="text-neutral-500">{header.name}:</span>
                {header.value}
              </p>
            {/each}
          </div>
        </details>

        <div class="mt-2">
          <p class="text-neutral-400">Body Kind: {response.body.kind}</p>

          <pre class="mt-2 max-h-72 overflow-auto rounded bg-neutral-900 p-3 text-xs">{response.body.text ?? response.body.base64 ?? ""}</pre>
        </div>
      </div>
    {/if}
  </section>
</main>
""",
}


REQUIRED_PHASE2_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/db.rs",
    "src-tauri/src/vault.rs",
    "src-tauri/src/commands/mod.rs",
    "src-tauri/src/commands/db.rs",
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


def verify_phase2() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE2_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 2 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 2 skeleton detected")


def write_phase3_files() -> None:
    for relative_path, content in PHASE3_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def add_rust_dependencies() -> None:
    run(
        [
            "cargo",
            "add",
            "reqwest",
            "--no-default-features",
            "--features",
            "json,query,form,native-tls",
        ],
        cwd=ROOT / "src-tauri",
    )

    run(["cargo", "add", "base64"], cwd=ROOT / "src-tauri")
    run(["cargo", "add", "url"], cwd=ROOT / "src-tauri")


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase2()
    add_rust_dependencies()
    write_phase3_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)

    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 3 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nTest 1: local HTTP server")
    print("  python3 -m http.server 8080")
    print("  App URL: http://localhost:8080")
    print("  Method: GET")
    print("  Execute Request")
    print("\nExpected:")
    print("  Status: 200 OK")
    print("  Body Kind: text")
    print("\nTest 2: JSON API")
    print("  App URL: https://api.github.com/repos/tauri-apps/tauri")
    print("  Method: GET")
    print("  Execute Request")
    print("\nExpected:")
    print("  Status: 200")
    print("  Body Kind: json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())