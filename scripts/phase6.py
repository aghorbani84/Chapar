#!/usr/bin/env python3
"""
Chapar Phase 6: Collections and request persistence.

This script:
- verifies Phase 5 files exist
- adds Rust collection CRUD commands
- adds Rust request CRUD commands
- adds frontend collection and request stores
- updates the sidebar to manage collections and requests
- updates the request panel with Save / New / Delete controls
- runs frontend and Rust verification checks
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PHASE6_FILES: dict[str, str] = {
"src-tauri/src/db.rs": """use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::{params, Connection};
use serde::de::DeserializeOwned;
use tauri::Manager;
use uuid::Uuid;

use crate::models::{
    ApiRequest, Collection, CreateCollectionPayload, Environment, EnvironmentVariable, HttpMethod,
    RequestBody, RequestBodyKind, SaveEnvironmentPayload, SaveRequestPayload,
};

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

fn parse_json_or_default<T>(value: &str) -> T
where
    T: DeserializeOwned + Default,
{
    serde_json::from_str(value).unwrap_or_default()
}

fn parse_body(value: &str) -> RequestBody {
    serde_json::from_str(value).unwrap_or(RequestBody {
        kind: RequestBodyKind::None,
        text: String::new(),
        form: Vec::new(),
    })
}

fn method_to_str(method: HttpMethod) -> &'static str {
    match method {
        HttpMethod::Get => "GET",
        HttpMethod::Post => "POST",
        HttpMethod::Put => "PUT",
        HttpMethod::Patch => "PATCH",
        HttpMethod::Delete => "DELETE",
        HttpMethod::Head => "HEAD",
        HttpMethod::Options => "OPTIONS",
    }
}

fn str_to_method(value: &str) -> Result<HttpMethod, String> {
    match value.to_ascii_uppercase().as_str() {
        "GET" => Ok(HttpMethod::Get),
        "POST" => Ok(HttpMethod::Post),
        "PUT" => Ok(HttpMethod::Put),
        "PATCH" => Ok(HttpMethod::Patch),
        "DELETE" => Ok(HttpMethod::Delete),
        "HEAD" => Ok(HttpMethod::Head),
        "OPTIONS" => Ok(HttpMethod::Options),
        other => Err(format!("unsupported HTTP method: {other}")),
    }
}

pub fn list_collections_conn(connection: &Connection) -> Result<Vec<Collection>, String> {
    let mut statement = connection
        .prepare(
            "SELECT id, name, parent_id, position, created_at, updated_at
             FROM collections
             ORDER BY position, name",
        )
        .map_err(|error| format!("failed to prepare collections query: {error}"))?;

    let rows = statement
        .query_map([], |row| {
            Ok(Collection {
                id: row.get(0)?,
                name: row.get(1)?,
                parent_id: row.get(2)?,
                position: row.get(3)?,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            })
        })
        .map_err(|error| format!("failed to query collections: {error}"))?;

    let mut collections = Vec::new();

    for row in rows {
        collections.push(row.map_err(|error| format!("failed to read collection: {error}"))?);
    }

    Ok(collections)
}

pub fn get_collection_conn(connection: &Connection, id: &str) -> Result<Collection, String> {
    let result = connection.query_row(
        "SELECT id, name, parent_id, position, created_at, updated_at
         FROM collections
         WHERE id = ?1",
        params![id],
        |row| {
            Ok(Collection {
                id: row.get(0)?,
                name: row.get(1)?,
                parent_id: row.get(2)?,
                position: row.get(3)?,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            })
        },
    );

    match result {
        Ok(collection) => Ok(collection),
        Err(rusqlite::Error::QueryReturnedNoRows) => Err("collection not found".to_string()),
        Err(error) => Err(error.to_string()),
    }
}

pub fn create_collection_conn(
    connection: &Connection,
    payload: &CreateCollectionPayload,
) -> Result<Collection, String> {
    if payload.name.trim().is_empty() {
        return Err("collection name must not be empty".to_string());
    }

    let id = Uuid::new_v4().to_string();
    let position = payload.position.unwrap_or(0);

    connection
        .execute(
            "INSERT INTO collections (id, name, parent_id, position)
             VALUES (?1, ?2, ?3, ?4)",
            params![id, payload.name, payload.parent_id, position],
        )
        .map_err(|error| format!("failed to insert collection: {error}"))?;

    get_collection_conn(connection, &id)
}

pub fn delete_collection_conn(connection: &Connection, id: &str) -> Result<(), String> {
    connection
        .execute("DELETE FROM collections WHERE id = ?1", params![id])
        .map_err(|error| format!("failed to delete collection: {error}"))?;

    Ok(())
}

pub fn list_requests_conn(
    connection: &Connection,
    collection_id: Option<&str>,
) -> Result<Vec<ApiRequest>, String> {
    let mut statement = connection
        .prepare(
            "SELECT id FROM requests
             WHERE (?1 IS NULL OR collection_id = ?1)
             ORDER BY position, name",
        )
        .map_err(|error| format!("failed to prepare requests query: {error}"))?;

    let rows = statement
        .query_map(params![collection_id], |row| row.get::<_, String>(0))
        .map_err(|error| format!("failed to query requests: {error}"))?;

    let mut requests = Vec::new();

    for row in rows {
        let id = row.map_err(|error| format!("failed to read request id: {error}"))?;
        requests.push(get_request_conn(connection, &id)?);
    }

    Ok(requests)
}

pub fn get_request_conn(connection: &Connection, id: &str) -> Result<ApiRequest, String> {
    let result: Result<
        (
            String,
            Option<String>,
            String,
            String,
            String,
            String,
            String,
            String,
            String,
            Option<i64>,
            i64,
            i64,
            String,
            String,
        ),
        rusqlite::Error,
    > = connection.query_row(
        "SELECT id, collection_id, name, method, url, params_json, headers_json, body_json,
                allowed_secret_ids_json, timeout_ms, follow_redirects, position, created_at, updated_at
         FROM requests
         WHERE id = ?1",
        params![id],
        |row| {
            Ok((
                row.get(0)?,
                row.get(1)?,
                row.get(2)?,
                row.get(3)?,
                row.get(4)?,
                row.get(5)?,
                row.get(6)?,
                row.get(7)?,
                row.get(8)?,
                row.get(9)?,
                row.get(10)?,
                row.get(11)?,
                row.get(12)?,
                row.get(13)?,
            ))
        },
    );

    let (
        id,
        collection_id,
        name,
        method,
        url,
        params_json,
        headers_json,
        body_json,
        allowed_secret_ids_json,
        timeout_ms,
        follow_redirects,
        position,
        created_at,
        updated_at,
    ) = match result {
        Ok(row) => row,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Err("request not found".to_string()),
        Err(error) => return Err(error.to_string()),
    };

    Ok(ApiRequest {
        id,
        collection_id,
        name,
        method: str_to_method(&method)?,
        url,
        params: parse_json_or_default(&params_json),
        headers: parse_json_or_default(&headers_json),
        body: parse_body(&body_json),
        allowed_secret_ids: parse_json_or_default(&allowed_secret_ids_json),
        timeout_ms: timeout_ms.map(|value| value as u64),
        follow_redirects: follow_redirects != 0,
        position,
        created_at,
        updated_at,
    })
}

pub fn save_request_conn(
    connection: &Connection,
    payload: &SaveRequestPayload,
) -> Result<ApiRequest, String> {
    let request = &payload.request;

    let id = if request.id.trim().is_empty() {
        Uuid::new_v4().to_string()
    } else {
        request.id.trim().to_string()
    };

    let name = if request.name.trim().is_empty() {
        "Untitled".to_string()
    } else {
        request.name.trim().to_string()
    };

    let collection_id = match &request.collection_id {
        Some(collection_id) => {
            let exists: bool = connection
                .query_row(
                    "SELECT COUNT(*) FROM collections WHERE id = ?1",
                    params![collection_id],
                    |row| row.get::<_, i64>(0),
                )
                .map_err(|error| format!("failed to check collection existence: {error}"))?
                > 0;

            if exists {
                Some(collection_id.clone())
            } else {
                None
            }
        }
        None => None,
    };

    let params_json =
        serde_json::to_string(&request.params).map_err(|error| error.to_string())?;
    let headers_json =
        serde_json::to_string(&request.headers).map_err(|error| error.to_string())?;
    let body_json = serde_json::to_string(&request.body).map_err(|error| error.to_string())?;
    let allowed_secret_ids_json = serde_json::to_string(&request.allowed_secret_ids)
        .map_err(|error| error.to_string())?;

    let method = method_to_str(request.method);
    let timeout_ms = request.timeout_ms.map(|value| value as i64);
    let follow_redirects: i64 = if request.follow_redirects { 1 } else { 0 };

    let exists: bool = connection
        .query_row(
            "SELECT COUNT(*) FROM requests WHERE id = ?1",
            params![id],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|error| format!("failed to check request existence: {error}"))?
        > 0;

    if exists {
        connection
            .execute(
                "UPDATE requests
                 SET collection_id = ?1,
                     name = ?2,
                     method = ?3,
                     url = ?4,
                     params_json = ?5,
                     headers_json = ?6,
                     body_json = ?7,
                     allowed_secret_ids_json = ?8,
                     timeout_ms = ?9,
                     follow_redirects = ?10,
                     position = ?11,
                     updated_at = datetime('now')
                 WHERE id = ?12",
                params![
                    collection_id,
                    name,
                    method,
                    request.url,
                    params_json,
                    headers_json,
                    body_json,
                    allowed_secret_ids_json,
                    timeout_ms,
                    follow_redirects,
                    request.position,
                    id
                ],
            )
            .map_err(|error| format!("failed to update request: {error}"))?;
    } else {
        connection
            .execute(
                "INSERT INTO requests
                 (id, collection_id, name, method, url, params_json, headers_json, body_json,
                  allowed_secret_ids_json, timeout_ms, follow_redirects, position)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
                params![
                    id,
                    collection_id,
                    name,
                    method,
                    request.url,
                    params_json,
                    headers_json,
                    body_json,
                    allowed_secret_ids_json,
                    timeout_ms,
                    follow_redirects,
                    request.position
                ],
            )
            .map_err(|error| format!("failed to insert request: {error}"))?;
    }

    get_request_conn(connection, &id)
}

pub fn delete_request_conn(connection: &Connection, id: &str) -> Result<(), String> {
    connection
        .execute("DELETE FROM requests WHERE id = ?1", params![id])
        .map_err(|error| format!("failed to delete request: {error}"))?;

    Ok(())
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

    #[test]
    fn collections_and_requests_crud() {
        let connection = Connection::open_in_memory().unwrap();
        migrate(&connection).unwrap();

        let collection = create_collection_conn(
            &connection,
            &CreateCollectionPayload {
                name: "APIs".to_string(),
                parent_id: None,
                position: Some(0),
            },
        )
        .unwrap();

        let collections = list_collections_conn(&connection).unwrap();
        assert_eq!(collections.len(), 1);

        let request = ApiRequest {
            id: String::new(),
            collection_id: Some(collection.id.clone()),
            name: "Test Request".to_string(),
            method: HttpMethod::Get,
            url: "https://example.com".to_string(),
            params: Vec::new(),
            headers: Vec::new(),
            body: RequestBody {
                kind: RequestBodyKind::None,
                text: String::new(),
                form: Vec::new(),
            },
            allowed_secret_ids: Vec::new(),
            timeout_ms: None,
            follow_redirects: true,
            position: 0,
            created_at: String::new(),
            updated_at: String::new(),
        };

        let saved_request = save_request_conn(
            &connection,
            &SaveRequestPayload { request },
        )
        .unwrap();

        assert!(!saved_request.id.is_empty());

        let all_requests = list_requests_conn(&connection, None).unwrap();
        assert_eq!(all_requests.len(), 1);

        let collection_requests =
            list_requests_conn(&connection, Some(&collection.id)).unwrap();
        assert_eq!(collection_requests.len(), 1);

        delete_request_conn(&connection, &saved_request.id).unwrap();

        let requests_after_delete = list_requests_conn(&connection, None).unwrap();
        assert!(requests_after_delete.is_empty());

        delete_collection_conn(&connection, &collection.id).unwrap();

        let collections_after_delete = list_collections_conn(&connection).unwrap();
        assert!(collections_after_delete.is_empty());
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

"src-tauri/src/commands/mod.rs": """pub mod collections;
pub mod db;
pub mod environments;
pub mod execute;
pub mod requests;
pub mod secrets;
""",

"src-tauri/src/commands/collections.rs": """use tauri::AppHandle;

use crate::models::{Collection, CreateCollectionPayload};

#[tauri::command]
pub fn list_collections(app: AppHandle) -> Result<Vec<Collection>, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::list_collections_conn(&connection)
}

#[tauri::command]
pub fn create_collection(
    app: AppHandle,
    payload: CreateCollectionPayload,
) -> Result<Collection, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::create_collection_conn(&connection, &payload)
}

#[tauri::command]
pub fn delete_collection(app: AppHandle, id: String) -> Result<(), String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::delete_collection_conn(&connection, &id)
}
""",

"src-tauri/src/commands/requests.rs": """use tauri::AppHandle;

use crate::models::{ApiRequest, SaveRequestPayload};

#[tauri::command]
pub fn list_requests(
    app: AppHandle,
    collection_id: Option<String>,
) -> Result<Vec<ApiRequest>, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::list_requests_conn(&connection, collection_id.as_deref())
}

#[tauri::command]
pub fn save_request(
    app: AppHandle,
    payload: SaveRequestPayload,
) -> Result<ApiRequest, String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::save_request_conn(&connection, &payload)
}

#[tauri::command]
pub fn delete_request(app: AppHandle, id: String) -> Result<(), String> {
    let path = crate::db::db_path(&app)?;
    let connection = crate::db::open_connection(&path)?;

    crate::db::delete_request_conn(&connection, &id)
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
            commands::environments::get_active_environment_id,
            commands::collections::list_collections,
            commands::collections::create_collection,
            commands::collections::delete_collection,
            commands::requests::list_requests,
            commands::requests::save_request,
            commands::requests::delete_request
        ])
        .run(tauri::generate_context!())
        .expect("error while running Chapar");
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
  SaveRequestPayload
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
  }
};
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
    allowedSecretIds: state.allowedSecretIds,
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

"src/lib/stores/collections.ts": """import { writable, get } from "svelte/store";
import { api } from "$lib/services/api";
import type { Collection } from "$lib/types/api";

export const collections = writable<Collection[]>([]);
export const selectedCollectionId = writable<string | null>(null);
export const collectionsError = writable<string | null>(null);

export async function loadCollections(): Promise<void> {
  try {
    const list = await api.listCollections();
    collections.set(list);
    collectionsError.set(null);
  } catch (error) {
    collectionsError.set(String(error));
  }
}

export async function createCollection(name: string): Promise<void> {
  const trimmed = name.trim();

  if (!trimmed) {
    return;
  }

  const saved = await api.createCollection({
    name: trimmed,
    parentId: null,
    position: 0
  });

  collections.update((list) => [...list, saved]);
  selectedCollectionId.set(saved.id);
}

export async function deleteCollectionById(id: string): Promise<void> {
  await api.deleteCollection(id);

  if (get(selectedCollectionId) === id) {
    selectedCollectionId.set(null);
  }

  await loadCollections();
}
""",

"src/lib/stores/requests.ts": """import { writable, get } from "svelte/store";
import { api } from "$lib/services/api";
import type { ApiRequest } from "$lib/types/api";
import { selectedCollectionId } from "$lib/stores/collections";
import {
  newRequestDraft,
  requestEditor,
  requestToEditor
} from "$lib/stores/requestEditor";

export const requests = writable<ApiRequest[]>([]);
export const selectedRequestId = writable<string | null>(null);
export const requestsError = writable<string | null>(null);

export async function loadRequests(collectionId: string | null): Promise<void> {
  try {
    const list = await api.listRequests(collectionId);
    requests.set(list);
    requestsError.set(null);
  } catch (error) {
    requestsError.set(String(error));
  }
}

export function selectRequest(request: ApiRequest): void {
  selectedRequestId.set(request.id);
  requestEditor.set(requestToEditor(request));
}

export function selectRequestById(id: string): void {
  const found = get(requests).find((request) => request.id === id);

  if (found) {
    selectRequest(found);
  }
}

export function newRequest(): void {
  requestEditor.set(newRequestDraft(get(selectedCollectionId)));
  selectedRequestId.set(null);
}

export async function deleteRequestById(id: string): Promise<void> {
  await api.deleteRequest(id);

  if (get(selectedRequestId) === id) {
    selectedRequestId.set(null);
    requestEditor.set(newRequestDraft(get(selectedCollectionId)));
  }

  await loadRequests(get(selectedCollectionId));
}
""",

"src/lib/components/Sidebar.svelte": """<script lang="ts">
  import { onMount } from "svelte";
  import {
    Database,
    FileText,
    Folder,
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
}


REQUIRED_PHASE5_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src/lib/components/EnvironmentsPanel.svelte",
    "src/lib/components/ResponsePane.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/db.rs",
    "src-tauri/src/commands/environments.rs",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def verify_phase5() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE5_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 5 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 5 skeleton detected")


def write_phase6_files() -> None:
    for relative_path, content in PHASE6_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase5()
    write_phase6_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)
    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 6 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nTest:")
    print("  1. Create collection: APIs")
    print("  2. Click New Request")
    print("  3. Name it: Local Home")
    print("  4. Set URL: {{base_url}}/")
    print("  5. Click Save")
    print("  6. Select it from sidebar")
    print("  7. Click Send")
    print("\nExpected:")
    print("  Completed: 200 OK")
    print("  Request persists after app restart")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
