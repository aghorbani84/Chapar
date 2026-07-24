use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::{params, Connection};
use serde::de::DeserializeOwned;
use tauri::Manager;
use uuid::Uuid;

use crate::models::{
    ApiRequest, Collection, CreateCollectionPayload, Environment, EnvironmentVariable,
    ExportBundle, HistoryEntry, HttpMethod, RequestBody, RequestBodyKind, ResponsePayload,
    SaveEnvironmentPayload, SaveRequestPayload, SecretMetadata,
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
