use tauri::AppHandle;

#[tauri::command]
pub fn init_db(app: AppHandle) -> Result<String, String> {
    crate::db::init_db_for_app(&app)
}
