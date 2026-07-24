use tauri::AppHandle;

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
