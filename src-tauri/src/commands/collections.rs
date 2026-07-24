use tauri::AppHandle;

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
