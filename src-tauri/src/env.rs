use std::collections::HashMap;

pub fn push_unique(list: &mut Vec<String>, value: String) {
    if !list.iter().any(|item| item == &value) {
        list.push(value);
    }
}

fn resolve_token(
    token: &str,
    environment: &HashMap<String, String>,
    allowed_secret_ids: &[String],
    secret_cache: &mut HashMap<String, Option<String>>,
    unresolved: &mut Vec<String>,
) -> Option<String> {
    if let Some(secret_id) = token.strip_prefix("secret:") {
        let secret_id = secret_id.trim();

        if secret_id.is_empty() {
            push_unique(unresolved, "secret:".to_string());
            return None;
        }

        let allowed = allowed_secret_ids
            .iter()
            .any(|allowed_id| allowed_id == secret_id);

        if !allowed {
            push_unique(
                unresolved,
                format!("unauthorized-secret:{}", secret_id),
            );
            return None;
        }

        let cached = match secret_cache.get(secret_id) {
            Some(existing) => existing.clone(),
            None => {
                let loaded = crate::vault::get_secret(secret_id).ok();
                secret_cache.insert(secret_id.to_string(), loaded.clone());
                loaded
            }
        };

        return match cached {
            Some(value) => Some(value),
            None => {
                push_unique(unresolved, format!("secret:{}", secret_id));
                None
            }
        };
    }

    let key = token.trim();

    match environment.get(key) {
        Some(value) => Some(value.clone()),
        None => {
            push_unique(unresolved, key.to_string());
            None
        }
    }
}

pub fn replace_text(
    input: &str,
    environment: &HashMap<String, String>,
    allowed_secret_ids: &[String],
    secret_cache: &mut HashMap<String, Option<String>>,
    unresolved: &mut Vec<String>,
) -> String {
    let mut output = String::new();
    let mut remaining = input;

    while let Some(start) = remaining.find("{{") {
        output.push_str(&remaining[..start]);

        let after_start = &remaining[start + 2..];

        match after_start.find("}}") {
            Some(end) => {
                let token = after_start[..end].trim();

                match resolve_token(
                    token,
                    environment,
                    allowed_secret_ids,
                    secret_cache,
                    unresolved,
                ) {
                    Some(value) => output.push_str(&value),
                    None => {
                        if token.starts_with("secret:") {
                            output.push_str("");
                        } else {
                            output.push_str("{{");
                            output.push_str(token);
                            output.push_str("}}");
                        }
                    }
                }

                remaining = &after_start[end + 2..];
            }
            None => {
                output.push_str("{{");
                output.push_str(after_start);
                remaining = "";
                break;
            }
        }
    }

    output.push_str(remaining);
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn replaces_environment_variables() {
        let mut environment = HashMap::new();
        environment.insert(
            "base_url".to_string(),
            "https://api.example.com".to_string(),
        );

        let allowed_secret_ids: Vec<String> = Vec::new();
        let mut secret_cache = HashMap::new();
        let mut unresolved = Vec::new();

        let output = replace_text(
            "{{base_url}}/users",
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        assert_eq!(output, "https://api.example.com/users");
        assert!(unresolved.is_empty());
    }

    #[test]
    fn tracks_missing_environment_variables() {
        let environment = HashMap::new();
        let allowed_secret_ids: Vec<String> = Vec::new();
        let mut secret_cache = HashMap::new();
        let mut unresolved = Vec::new();

        let output = replace_text(
            "{{missing}}/users",
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        assert_eq!(output, "{{missing}}/users");
        assert_eq!(unresolved, vec!["missing".to_string()]);
    }

    #[test]
    fn rejects_unauthorized_secret_variables() {
        let environment = HashMap::new();
        let allowed_secret_ids: Vec<String> = Vec::new();
        let mut secret_cache = HashMap::new();
        let mut unresolved = Vec::new();

        let output = replace_text(
            "Bearer {{secret:prod-api-key}}",
            &environment,
            &allowed_secret_ids,
            &mut secret_cache,
            &mut unresolved,
        );

        assert_eq!(output, "Bearer ");
        assert_eq!(
            unresolved,
            vec!["unauthorized-secret:prod-api-key".to_string()]
        );
    }
}
