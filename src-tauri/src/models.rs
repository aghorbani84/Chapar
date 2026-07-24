use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Collection {
    pub id: String,
    pub name: String,
    pub parent_id: Option<String>,
    pub position: i64,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum HttpMethod {
    Get,
    Post,
    Put,
    Patch,
    Delete,
    Head,
    Options,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum RequestBodyKind {
    None,
    Json,
    Text,
    FormUrlEncoded,
    Raw,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KeyValueEntry {
    pub id: String,
    pub key: String,
    pub value: String,
    pub enabled: bool,
    pub secret_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestBody {
    pub kind: RequestBodyKind,
    pub text: String,
    #[serde(default)]
    pub form: Vec<KeyValueEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ApiRequest {
    pub id: String,
    pub collection_id: Option<String>,
    pub name: String,
    pub method: HttpMethod,
    pub url: String,
    #[serde(default)]
    pub params: Vec<KeyValueEntry>,
    #[serde(default)]
    pub headers: Vec<KeyValueEntry>,
    pub body: RequestBody,
    #[serde(default)]
    pub allowed_secret_ids: Vec<String>,
    pub timeout_ms: Option<u64>,
    pub follow_redirects: bool,
    pub position: i64,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EnvironmentVariable {
    pub id: String,
    pub key: String,
    pub value: String,
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Environment {
    pub id: String,
    pub name: String,
    pub variables: Vec<EnvironmentVariable>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SecretMetadata {
    pub id: String,
    pub label: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestPayload {
    pub request: ApiRequest,
    pub environment_id: Option<String>,
    pub timeout_ms: Option<u64>,
    pub follow_redirects: bool,
    pub max_redirects: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResponseHeader {
    pub name: String,
    pub value: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum ResponseBodyKind {
    Json,
    Text,
    Binary,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResponseBody {
    pub kind: ResponseBodyKind,
    pub text: Option<String>,
    pub base64: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResponsePayload {
    pub request_id: String,
    pub status: u16,
    pub status_text: String,
    pub http_version: String,
    pub latency_ms: u64,
    pub size_bytes: u64,
    pub headers: Vec<ResponseHeader>,
    pub body: ResponseBody,
    pub unresolved_variables: Vec<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateCollectionPayload {
    pub name: String,
    pub parent_id: Option<String>,
    pub position: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateCollectionPayload {
    pub id: String,
    pub name: String,
    pub position: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveRequestPayload {
    pub request: ApiRequest,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SaveEnvironmentPayload {
    pub environment: Environment,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StoreSecretPayload {
    pub id: String,
    pub value: String,
    pub label: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HistoryEntry {
    pub id: String,
    pub request_id: String,
    pub environment_id: Option<String>,
    pub request_snapshot: ApiRequest,
    pub status: Option<i64>,
    pub latency_ms: Option<i64>,
    pub size_bytes: Option<i64>,
    pub response: Option<ResponsePayload>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportBundle {
    pub exported_at: String,
    pub collections: Vec<Collection>,
    pub requests: Vec<ApiRequest>,
    pub environments: Vec<Environment>,
    pub secret_metadata: Vec<SecretMetadata>,
}
