#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

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
            commands::requests::delete_request,
            commands::secrets::list_secret_metadata,
            commands::secrets::save_secret,
            commands::secrets::delete_secret,
            commands::history::list_history,
            commands::history::clear_history,
            commands::data::export_data,
            commands::data::import_data
        ])
        .run(tauri::generate_context!())
        .expect("error while running Chapar");
}
