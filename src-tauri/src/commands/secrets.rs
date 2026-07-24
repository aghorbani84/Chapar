use tauri::AppHandle;

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
