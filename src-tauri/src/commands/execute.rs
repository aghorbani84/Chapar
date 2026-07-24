use tauri::AppHandle;

use crate::models::{RequestPayload, ResponsePayload};

#[tauri::command]
pub async fn execute_request(
    app: AppHandle,
    payload: RequestPayload,
) -> Result<ResponsePayload, String> {
    crate::http::execute_request(&app, payload).await
}
