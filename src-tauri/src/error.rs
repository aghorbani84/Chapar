#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("validation error: {0}")]
    Validation(String),

    #[error("database error")]
    Database(String),

    #[error("secret store error")]
    Secret(String),

    #[error("http error")]
    Http(String),

    #[error("serialization error")]
    Serialization(String),

    #[error("not found")]
    NotFound,
}

impl From<AppError> for String {
    fn from(error: AppError) -> Self {
        error.to_string()
    }
}
