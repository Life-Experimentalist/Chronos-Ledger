// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

use std::{sync::Arc, time::Duration};

use reqwest::header::HeaderValue;
use tokio::sync::Mutex;

use crate::{
    transport::{default_jitter, default_sleep, Jitter, Shared, Sleeper, TokenSink},
    Client, Error, RetryPolicy, State, Tokens,
};

/// Sets up a [`Client`].
///
/// ```ignore
/// let client = chronos_ledger_client::ClientBuilder::new("https://chronos.example.org")
///     .api_key("clk_...")
///     .build()?;
/// let users = client.users_list().send().await;
/// ```
pub struct ClientBuilder {
    base_url: String,
    api_key: Option<String>,
    acting_for: Option<String>,
    tokens: Option<Tokens>,
    on_tokens: Option<TokenSink>,
    http: Option<reqwest::Client>,
    retry: RetryPolicy,
    sleep: Sleeper,
    jitter: Jitter,
}

impl ClientBuilder {
    /// Starts a client for the server at `base_url`, for example
    /// `https://chronos.example.org`. A trailing `/api/v1` is accepted and
    /// dropped, because every generated path already carries it.
    pub fn new(base_url: impl Into<String>) -> Self {
        ClientBuilder {
            base_url: base_url.into(),
            api_key: None,
            acting_for: None,
            tokens: None,
            on_tokens: None,
            http: None,
            retry: RetryPolicy::default(),
            sleep: default_sleep(),
            jitter: default_jitter(),
        }
    }

    /// Authenticates with a scoped API key, sent as `X-API-Key`.
    pub fn api_key(mut self, key: impl Into<String>) -> Self {
        self.api_key = Some(key.into());
        self
    }

    /// Sends `user_id` as `X-Chronos-Actor` on every request, so an API key
    /// holding the `impersonate` scope speaks for that person. Needs
    /// [`api_key`](Self::api_key). A request that sets the header itself keeps its own.
    pub fn acting_for(mut self, user_id: impl Into<String>) -> Self {
        self.acting_for = Some(user_id.into());
        self
    }

    /// Authenticates with the pair from `POST /api/v1/auth/login`. On a 401 the
    /// client calls `/api/v1/auth/refresh` once and sends the request again. A
    /// refresh token works only once, so `on_tokens` must store each new pair.
    /// Callers that hit a 401 together share one refresh.
    pub fn tokens(
        mut self,
        tokens: Tokens,
        on_tokens: impl Fn(&Tokens) + Send + Sync + 'static,
    ) -> Self {
        self.tokens = Some(tokens);
        self.on_tokens = Some(Arc::new(on_tokens));
        self
    }

    /// Replaces the `reqwest::Client` the requests go through. The default has
    /// a 30 second timeout.
    pub fn http_client(mut self, client: reqwest::Client) -> Self {
        self.http = Some(client);
        self
    }

    /// Replaces [`RetryPolicy::default`].
    pub fn retry(mut self, policy: RetryPolicy) -> Self {
        self.retry = policy;
        self
    }

    /// Sends every request once.
    pub fn without_retries(self) -> Self {
        self.retry(RetryPolicy::none())
    }

    /// Replaces how the retry layer waits. Used by tests.
    #[cfg(test)]
    pub(crate) fn sleeper(mut self, sleep: Sleeper) -> Self {
        self.sleep = sleep;
        self
    }

    /// Replaces how the backoff is drawn. Used by tests.
    #[cfg(test)]
    pub(crate) fn jitter(mut self, jitter: Jitter) -> Self {
        self.jitter = jitter;
        self
    }

    /// Builds the client, or says what is wrong with the setup.
    pub fn build(self) -> Result<Client, Error> {
        let trimmed = self.base_url.trim_end_matches('/');
        let base = trimmed.strip_suffix("/api/v1").unwrap_or(trimmed);
        if base.is_empty() {
            return Err(Error::Config("base URL is required".to_string()));
        }
        if self.api_key.is_some() && self.tokens.is_some() {
            return Err(Error::Config(
                "pass an API key or tokens, not both".to_string(),
            ));
        }
        if self.acting_for.is_some() && self.api_key.is_none() {
            return Err(Error::Config("acting_for needs an API key".to_string()));
        }
        let acting_for = match self.acting_for {
            Some(user_id) => Some(HeaderValue::from_str(&user_id).map_err(|_| {
                Error::Config("the acting_for user id is not a valid header".to_string())
            })?),
            None => None,
        };
        let api_key = match self.api_key {
            Some(key) => {
                let mut value = HeaderValue::from_str(&key)
                    .map_err(|_| Error::Config("the API key is not a valid header".to_string()))?;
                value.set_sensitive(true);
                Some(value)
            }
            None => None,
        };
        let http = match self.http {
            Some(http) => http,
            None => reqwest::Client::builder()
                .timeout(Duration::from_secs(30))
                .user_agent(concat!("chronos-rust/", env!("CARGO_PKG_VERSION")))
                .build()
                .map_err(|error| Error::Config(error.to_string()))?,
        };
        let state = State(Arc::new(Shared {
            api_key,
            acting_for,
            tokens: Mutex::new(self.tokens),
            on_tokens: self.on_tokens,
            retry: RetryPolicy {
                max_attempts: self.retry.max_attempts.max(1),
                ..self.retry
            },
            sleep: self.sleep,
            jitter: self.jitter,
        }));
        Ok(Client::new_with_client(base, http, state))
    }
}
