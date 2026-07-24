use tauri::AppHandle;

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
