// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

use std::fmt;

use serde_json::Value;

/// What the server said when it refused a request: a status of 400 or above,
/// after the retries the policy allows. Every error body is
/// `{"detail", "code"}`.
#[derive(Clone, Debug, PartialEq)]
pub struct ApiError {
    /// The HTTP status.
    pub status: u16,
    /// The server's code, such as `EMAIL_TAKEN`, for a program to branch on.
    /// A string rather than an enum, so a code added after this client was
    /// built still arrives. `None` when the body had no code, for example an
    /// error page from a proxy.
    pub code: Option<String>,
    /// The body's `detail` as the server sent it: a string, an object for a
    /// 409, or a list for `VALIDATION_FAILED`. A body that is not JSON is kept
    /// as text, and an empty body leaves this `None`.
    pub detail: Option<Value>,
    /// The clashing intervals of a 409, or empty.
    pub conflicts: Vec<Value>,
}

impl ApiError {
    /// Reads an error response body.
    pub fn from_body(status: u16, body: &[u8]) -> Self {
        let mut error = ApiError {
            status,
            code: None,
            detail: None,
            conflicts: Vec::new(),
        };
        match serde_json::from_slice::<Value>(body) {
            Ok(Value::Object(mut map)) => {
                if let Some(Value::String(code)) = map.remove("code") {
                    error.code = Some(code);
                }
                error.detail = match map.remove("detail") {
                    Some(detail) => Some(detail),
                    None => Some(Value::Object(map)),
                };
            }
            Ok(other) => error.detail = Some(other),
            Err(_) => {
                let text = String::from_utf8_lossy(body);
                if !text.trim().is_empty() {
                    error.detail = Some(Value::String(text.into_owned()));
                }
            }
        }
        if let Some(Value::Object(detail)) = &error.detail {
            if let Some(Value::Array(list)) = detail.get("conflicts") {
                error.conflicts = list.iter().filter(|c| c.is_object()).cloned().collect();
            }
        }
        error
    }

    fn message(&self) -> Option<&str> {
        match &self.detail {
            Some(Value::String(text)) => Some(text),
            Some(Value::Object(map)) => map.get("message").and_then(Value::as_str),
            _ => None,
        }
    }
}

impl fmt::Display for ApiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.message() {
            Some(message) => write!(f, "chronos: {}: {}", self.status, message),
            None => write!(f, "chronos: HTTP {}", self.status),
        }
    }
}

impl std::error::Error for ApiError {}

/// Every way a call can fail.
#[derive(Debug)]
pub enum Error {
    /// The server answered with a status of 400 or above.
    Api(ApiError),
    /// The request never got an answer, or the answer could not be read.
    Client(progenitor_client::Error<()>),
    /// The client was set up wrongly.
    Config(String),
}

impl Error {
    /// The HTTP status, when the server answered.
    pub fn status(&self) -> Option<u16> {
        match self {
            Error::Api(api) => Some(api.status),
            Error::Client(error) => error.status().map(|s| s.as_u16()),
            Error::Config(_) => None,
        }
    }

    /// The server's error code, when it sent one.
    pub fn code(&self) -> Option<&str> {
        match self {
            Error::Api(api) => api.code.as_deref(),
            _ => None,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Api(api) => api.fmt(f),
            Error::Client(error) => write!(f, "chronos: {error}"),
            Error::Config(message) => write!(f, "chronos: {message}"),
        }
    }
}

impl std::error::Error for Error {}

/// A generated call returns `progenitor_client::Error<()>`. A refusal from the
/// server arrives as `UnexpectedResponse`, with the parsed body attached by the
/// retry layer, and becomes `Error::Api` here:
///
/// ```ignore
/// let users = client.users_list().send().await.map_err(chronos_ledger_client::Error::from)?;
/// ```
impl From<progenitor_client::Error<()>> for Error {
    fn from(error: progenitor_client::Error<()>) -> Self {
        if let progenitor_client::Error::UnexpectedResponse(response) = &error {
            if let Some(api) = response.extensions().get::<ApiError>() {
                return Error::Api(api.clone());
            }
        }
        Error::Client(error)
    }
}
