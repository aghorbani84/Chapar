use std::collections::HashMap;
use std::time::{Duration, Instant};

use base64::{engine::general_purpose::STANDARD, Engine as _};
use reqwest::header::{HeaderMap, HeaderName, HeaderValue, CONTENT_TYPE, USER_AGENT};
use reqwest::redirect::Policy;
use reqwest::{Client, Method};
use serde_json::Value;
use url::Url;

use crate::env::{push_unique, replace_text};
use crate::models::{
    HttpMethod, RequestBodyKind, RequestPayload, ResponseBody, ResponseBodyKind, ResponseHeader,
    ResponsePayload,
};

fn convert_method(method: HttpMethod) -> Method {
    match method {
        HttpMethod::Get => Method::GET,
        HttpMethod::Post => Method::POST,
        HttpMethod::Put => Method::PUT,
        HttpMethod::Patch => Method::PATCH,
        HttpMethod::Delete => Method::DELETE,
        HttpMethod::Head => Method::HEAD,
        HttpMethod::Options => Method::OPTIONS,
    }
}

fn error_response(
    request_id: &str,
    unresolved_variables: Vec<String>,
    message: &str,
) -> ResponsePayload {
    ResponsePayload {
        request_id: request_id.to_string(),
        status: 0,
        status_text: String::new(),
        http_version: String::new(),
        latency_ms: 0,
        size_bytes: 0,
        headers: Vec::new(),
        body: ResponseBody {
            kind: ResponseBodyKind::Text,
            text: Some(message.to_string()),
            base64: None,
        },
        unresolved_variables,
        error: Some(message.to_string()),
    }
}

pub async fn execute_request(
    app: &tauri::AppHandle,
    payload: RequestPayload,
) -> Result<ResponsePayload, String> {
    let RequestPayload {
        request,
        environment_id,
        timeout_ms,
        follow_redirects,
        max_redirects,
    } = payload;

    let environment_id_for_history = environment_id.clone();

    let environment = match environment_id {
        Some(environment_id) => {
            crate::db::load_enabled_environment_variables(app, &environment_id)?
        }
        None => HashMap::new(),
    };

    let allowed_secret_ids = request.allowed_secret_ids.clone();
    let mut secret_cache: HashMap<String, Option<String>> = HashMap::new();
    let mut unresolved: Vec<String> = Vec::new();

    let url_text = replace_text(
        &request.url,
        &environment,
        &allowed_secret_ids,
        &mut secret_cache,
        &mut unresolved,
    );

    let mut query_pairs: Vec<(String, String)> = Vec::new();

    for parameter in &request.params {
        if !parameter.enabled {
            continue;
        }

        let key = replace_text(
            &parameter.key,
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        let value = replace_text(
            &parameter.value,
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        if key.trim().is_empty() {
            continue;
        }

        query_pairs.push((key, value));
    }

    let mut header_map = HeaderMap::new();

    for header in &request.headers {
        if !header.enabled {
            continue;
        }

        let key = replace_text(
            &header.key,
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        let key = key.trim().to_string();

        if key.is_empty() {
            continue;
        }

        let value = match &header.secret_id {
            Some(secret_id) => {
                let secret_id = secret_id.trim();

                if secret_id.is_empty() {
                    push_unique(&mut unresolved, "secret:".to_string());
                    String::new()
                } else if !allowed_secret_ids
                    .iter()
                    .any(|allowed_id| allowed_id == secret_id)
                {
                    push_unique(
                        &mut unresolved,
                        format!("unauthorized-secret:{}", secret_id),
                    );
                    String::new()
                } else {
                    let cached = match secret_cache.get(secret_id) {
                        Some(existing) => existing.clone(),
                        None => {
                            let loaded = crate::vault::get_secret(secret_id).ok();
                            secret_cache.insert(secret_id.to_string(), loaded.clone());
                            loaded
                        }
                    };

                    match cached {
                        Some(value) => value,
                        None => {
                            push_unique(
                                &mut unresolved,
                                format!("secret:{}", secret_id),
                            );
                            String::new()
                        }
                    }
                }
            }
            None => replace_text(
                &header.value,
                &environment,
                &allowed_secret_ids,
                &mut secret_cache,
                &mut unresolved,
            ),
        };

        let header_name = match HeaderName::from_bytes(key.as_bytes()) {
            Ok(header_name) => header_name,
            Err(_) => {
                return Ok(error_response(
                    &request.id,
                    unresolved,
                    "invalid header name",
                ))
            }
        };

        let header_value = match HeaderValue::from_str(&value) {
            Ok(header_value) => header_value,
            Err(_) => {
                return Ok(error_response(
                    &request.id,
                    unresolved,
                    "invalid header value",
                ))
            }
        };

        header_map.insert(header_name, header_value);
    }

    if !header_map.contains_key(USER_AGENT) {
        header_map.insert(USER_AGENT, HeaderValue::from_static("Chapar/0.1"));
    }

    let mut body_text: Option<String> = None;
    let mut form_pairs: Vec<(String, String)> = Vec::new();

    match request.body.kind {
        RequestBodyKind::None => {}
        RequestBodyKind::FormUrlEncoded => {
            for entry in &request.body.form {
                if !entry.enabled {
                    continue;
                }

                let key = replace_text(
                    &entry.key,
                    &environment,
                    &allowed_secret_ids,
                    &mut secret_cache,
                    &mut unresolved,
                );

                let value = replace_text(
                    &entry.value,
                    &environment,
                    &allowed_secret_ids,
                    &mut secret_cache,
                    &mut unresolved,
                );

                if key.trim().is_empty() {
                    continue;
                }

                form_pairs.push((key, value));
            }
        }
        RequestBodyKind::Json | RequestBodyKind::Text | RequestBodyKind::Raw => {
            let replaced = replace_text(
                &request.body.text,
                &environment,
                &allowed_secret_ids,
                &mut secret_cache,
                &mut unresolved,
            );

            if !replaced.is_empty() {
                body_text = Some(replaced);
            }
        }
    }

    if !header_map.contains_key(CONTENT_TYPE) {
        match request.body.kind {
            RequestBodyKind::Json => {
                if body_text.is_some() {
                    header_map.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
                }
            }
            RequestBodyKind::Text | RequestBodyKind::Raw => {
                if body_text.is_some() {
                    header_map.insert(
                        CONTENT_TYPE,
                        HeaderValue::from_static("text/plain; charset=utf-8"),
                    );
                }
            }
            RequestBodyKind::None | RequestBodyKind::FormUrlEncoded => {}
        }
    }

    if !unresolved.is_empty() {
        return Ok(error_response(
            &request.id,
            unresolved,
            "request contains unresolved or unauthorized variables",
        ));
    }

    let url = match Url::parse(&url_text) {
        Ok(url) => url,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "invalid URL",
            ))
        }
    };

    let mut client_builder = Client::builder();

    if follow_redirects {
        client_builder =
            client_builder.redirect(Policy::limited(max_redirects.unwrap_or(10)));
    } else {
        client_builder = client_builder.redirect(Policy::none());
    }

    if let Some(timeout_ms) = timeout_ms.or(request.timeout_ms) {
        if timeout_ms > 0 {
            client_builder = client_builder.timeout(Duration::from_millis(timeout_ms));
        }
    }

    let client = match client_builder.build() {
        Ok(client) => client,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "failed to create HTTP client",
            ))
        }
    };

    let mut request_builder = client.request(convert_method(request.method), url);

    if !query_pairs.is_empty() {
        request_builder = request_builder.query(&query_pairs);
    }

    request_builder = request_builder.headers(header_map);

    match request.body.kind {
        RequestBodyKind::FormUrlEncoded => {
            if !form_pairs.is_empty() {
                request_builder = request_builder.form(&form_pairs);
            }
        }
        RequestBodyKind::Json | RequestBodyKind::Text | RequestBodyKind::Raw => {
            if let Some(text) = body_text {
                request_builder = request_builder.body(text);
            }
        }
        RequestBodyKind::None => {}
    }

    let started = Instant::now();

    let response = match request_builder.send().await {
        Ok(response) => response,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "request failed to complete",
            ))
        }
    };

    let status = response.status();
    let status_text = status.canonical_reason().unwrap_or("").to_string();
    let http_version = format!("{:?}", response.version());

    let headers: Vec<ResponseHeader> = response
        .headers()
        .iter()
        .map(|(name, value)| ResponseHeader {
            name: name.as_str().to_string(),
            value: value
                .to_str()
                .unwrap_or("[binary header value]")
                .to_string(),
        })
        .collect();

    let bytes = match response.bytes().await {
        Ok(bytes) => bytes,
        Err(_) => {
            return Ok(error_response(
                &request.id,
                unresolved,
                "failed to read response body",
            ))
        }
    };

    let latency_ms = started.elapsed().as_millis() as u64;
    let size_bytes = bytes.len() as u64;

    let body = if bytes.is_empty() {
        ResponseBody {
            kind: ResponseBodyKind::Text,
            text: Some(String::new()),
            base64: None,
        }
    } else if let Ok(json) = serde_json::from_slice::<Value>(&bytes) {
        let pretty = serde_json::to_string_pretty(&json)
            .unwrap_or_else(|_| String::from_utf8_lossy(&bytes).into_owned());

        ResponseBody {
            kind: ResponseBodyKind::Json,
            text: Some(pretty),
            base64: None,
        }
    } else if let Ok(text) = String::from_utf8(bytes.to_vec()) {
        ResponseBody {
            kind: ResponseBodyKind::Text,
            text: Some(text),
            base64: None,
        }
    } else {
        ResponseBody {
            kind: ResponseBodyKind::Binary,
            text: None,
            base64: Some(STANDARD.encode(&bytes)),
        }
    };

    let response_payload = ResponsePayload {
        request_id: request.id.clone(),
        status: status.as_u16(),
        status_text,
        http_version,
        latency_ms,
        size_bytes,
        headers,
        body,
        unresolved_variables: unresolved,
        error: None,
    };

    let _ = crate::db::save_history_for_app(
        app,
        &request,
        environment_id_for_history,
        &response_payload,
    );

    Ok(response_payload)
}
