use tauri::AppHandle;

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
