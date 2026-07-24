use keyring::Entry;

const SERVICE: &str = "app.chapar.desktop";
const MAX_SECRET_ID_LEN: usize = 255;
const MAX_SECRET_VALUE_LEN: usize = 4096;

fn normalize_id(id: &str) -> Result<String, String> {
    let id = id.trim();

    if id.is_empty() {
        return Err("secret id must not be empty".to_string());
    }

    if id.len() > MAX_SECRET_ID_LEN {
        return Err(format!(
            "secret id must be {} characters or fewer",
            MAX_SECRET_ID_LEN
        ));
    }

    let allowed = id
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.' | ':'));

    if !allowed {
        return Err(
            "secret id may only contain letters, numbers, '-', '_', '.', or ':'".to_string(),
        );
    }

    Ok(id.to_string())
}

fn validate_value(value: &str) -> Result<(), String> {
    if value.is_empty() {
        return Err("secret value must not be empty".to_string());
    }

    if value.len() > MAX_SECRET_VALUE_LEN {
        return Err(format!(
            "secret value must be {} characters or fewer",
            MAX_SECRET_VALUE_LEN
        ));
    }

    if value.chars().any(char::is_control) {
        return Err("secret value must not contain control characters".to_string());
    }

    Ok(())
}

fn entry_for(id: &str) -> Result<Entry, String> {
    let id = normalize_id(id)?;

    Entry::new(SERVICE, &id).map_err(|_| "secret store is unavailable".to_string())
}

pub fn store_secret(id: &str, value: &str) -> Result<(), String> {
    validate_value(value)?;

    let entry = entry_for(id)?;

    entry
        .set_password(value)
        .map_err(|_| "failed to store secret".to_string())
}

pub fn get_secret(id: &str) -> Result<String, String> {
    let entry = entry_for(id)?;

    entry.get_password().map_err(|error| match error {
        keyring::Error::NoEntry => "secret not found".to_string(),
        _ => "failed to retrieve secret".to_string(),
    })
}

pub fn secret_exists(id: &str) -> Result<bool, String> {
    let entry = entry_for(id)?;

    match entry.get_password() {
        Ok(_) => Ok(true),
        Err(keyring::Error::NoEntry) => Ok(false),
        Err(_) => Err("failed to check secret".to_string()),
    }
}

pub fn delete_secret(id: &str) -> Result<(), String> {
    let entry = entry_for(id)?;

    match entry.delete_credential() {
        Ok(_) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(_) => Err("failed to delete secret".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_id_accepts_valid_ids() {
        assert!(normalize_id("prod-api-key").is_ok());
        assert!(normalize_id("prod_api_key").is_ok());
        assert!(normalize_id("prod.api.key").is_ok());
        assert!(normalize_id("prod:api:key").is_ok());
        assert!(normalize_id("  prod-api-key  ").is_ok());
    }

    #[test]
    fn normalize_id_rejects_invalid_ids() {
        assert!(normalize_id("").is_err());
        assert!(normalize_id("   ").is_err());
        assert!(normalize_id("bad id").is_err());
        assert!(normalize_id("bad/id").is_err());
        assert!(normalize_id("bad\nid").is_err());
        assert!(normalize_id(&"a".repeat(300)).is_err());
    }

    #[test]
    fn validate_value_accepts_normal_values() {
        assert!(validate_value("super-secret-token").is_ok());
        assert!(validate_value("Bearer abc123").is_ok());
        assert!(validate_value("value with spaces").is_ok());
    }

    #[test]
    fn validate_value_rejects_invalid_values() {
        assert!(validate_value("").is_err());
        assert!(validate_value("bad\nvalue").is_err());
        assert!(validate_value("bad\u{0000}value").is_err());
        assert!(validate_value(&"a".repeat(5000)).is_err());
    }
}
