use tauri::AppHandle;

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
