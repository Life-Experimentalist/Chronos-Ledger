// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! What sits under the generated client: auth, idempotency keys, retries.
//!
//! The generated client sends every request through `ClientHooks::exec`.
//! `impl ClientHooks<State> for Client` in lib.rs hands that to
//! `State::execute`, so every call gets the same behaviour without a wrapper
//! around each one.

use std::{
    fmt,
    sync::Arc,
    time::{Duration, Instant, SystemTime},
};

use futures::future::BoxFuture;
use reqwest::{
    header::{HeaderMap, HeaderValue, AUTHORIZATION, RETRY_AFTER},
    Method, StatusCode,
};
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::error::ApiError;

const IDEMPOTENCY_KEY: &str = "idempotency-key";
const KEY_IN_PROGRESS: &str = "IDEMPOTENCY_KEY_IN_PROGRESS";

/// An access token and the single-use refresh token that came with it.
#[derive(Clone)]
pub struct Tokens {
    pub access_token: String,
    pub refresh_token: String,
}

impl fmt::Debug for Tokens {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Tokens").finish_non_exhaustive()
    }
}

/// When and how often a failed request is sent again.
///
/// A request is retried when no response arrived, or the status was 429, 502,
/// 503 or 504, or a 409 with code `IDEMPOTENCY_KEY_IN_PROGRESS`. Other 4xx
/// statuses are never retried. A read is always retried; a write only when it
/// carries an `Idempotency-Key`, which the client makes for every write unless
/// the caller sends one. The key is the same on every attempt.
///
/// The wait before attempt n+1 is a random time between zero and
/// `min(max_delay, base_delay * 2^n)` ("full jitter"), or the server's
/// `Retry-After` when it sent one.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RetryPolicy {
    /// Counts the first try. One means no retries.
    pub max_attempts: u32,
    /// The backoff ceiling before the first retry.
    pub base_delay: Duration,
    /// Caps the backoff. It does not cap a `Retry-After`.
    pub max_delay: Duration,
    /// The most time one call spends waiting, counted from its first attempt.
    /// A wait that would pass it is skipped and the last failure returned.
    pub deadline: Option<Duration>,
}

impl Default for RetryPolicy {
    /// 4 attempts, 0.25 s base, 8 s cap and a 30 s deadline.
    fn default() -> Self {
        RetryPolicy {
            max_attempts: 4,
            base_delay: Duration::from_millis(250),
            max_delay: Duration::from_secs(8),
            deadline: Some(Duration::from_secs(30)),
        }
    }
}

impl RetryPolicy {
    /// Every request is sent once.
    pub fn none() -> Self {
        RetryPolicy {
            max_attempts: 1,
            ..RetryPolicy::default()
        }
    }
}

pub(crate) type Sleeper = Arc<dyn Fn(Duration) -> BoxFuture<'static, ()> + Send + Sync>;
pub(crate) type Jitter = Arc<dyn Fn(Duration) -> Duration + Send + Sync>;
pub(crate) type TokenSink = Arc<dyn Fn(&Tokens) + Send + Sync>;

pub(crate) struct Shared {
    pub(crate) api_key: Option<HeaderValue>,
    pub(crate) tokens: Mutex<Option<Tokens>>,
    pub(crate) on_tokens: Option<TokenSink>,
    pub(crate) retry: RetryPolicy,
    pub(crate) sleep: Sleeper,
    pub(crate) jitter: Jitter,
}

/// The state behind a client: credentials and the retry policy. It is the
/// "inner" type of the generated client and is cloned with it.
#[derive(Clone)]
pub struct State(pub(crate) Arc<Shared>);

impl fmt::Debug for State {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("State").finish_non_exhaustive()
    }
}

/// A fresh version 4 UUID, the shape of key the server expects.
pub fn new_idempotency_key() -> String {
    Uuid::new_v4().to_string()
}

pub(crate) fn default_sleep() -> Sleeper {
    Arc::new(|duration| Box::pin(tokio::time::sleep(duration)))
}

/// A random time from zero up to and including `ceiling`.
pub(crate) fn default_jitter() -> Jitter {
    Arc::new(|ceiling| {
        let nanos = ceiling.as_nanos().min(u128::from(u64::MAX));
        let pick = Uuid::new_v4().as_u128() % (nanos + 1);
        Duration::from_nanos(u64::try_from(pick).unwrap_or(u64::MAX))
    })
}

impl State {
    /// Sends `request`, retrying as the policy allows. A status of 400 or
    /// above comes back as `Ok(response)` with the parsed body attached as an
    /// `ApiError` extension, so the generated call reports it.
    pub(crate) async fn execute(
        &self,
        http: &reqwest::Client,
        base: &str,
        mut request: reqwest::Request,
    ) -> reqwest::Result<reqwest::Response> {
        let write = !matches!(
            *request.method(),
            Method::GET | Method::HEAD | Method::OPTIONS
        );
        if write && !request.headers().contains_key(IDEMPOTENCY_KEY) {
            if let Ok(key) = HeaderValue::from_str(&new_idempotency_key()) {
                request.headers_mut().insert(IDEMPOTENCY_KEY, key);
            }
        }
        let policy = self.0.retry;
        // A streaming body cannot be sent twice, so it is sent once.
        let can_repeat = request.try_clone().is_some();
        let retryable = can_repeat && (!write || request.headers().contains_key(IDEMPOTENCY_KEY));
        let mut spare = Some(request);

        let start = Instant::now();
        let mut attempt: u32 = 0;
        let mut refreshed = false;
        loop {
            let current = match spare.as_ref().and_then(reqwest::Request::try_clone) {
                Some(copy) => copy,
                None => spare.take().expect("an unrepeatable request is sent once"),
            };
            let (result, token_used) = self.send(http, current).await;
            let last = attempt + 1 >= policy.max_attempts;

            let response = match result {
                Ok(response) => response,
                Err(error) => {
                    if !retryable || last {
                        return Err(error);
                    }
                    let wait = self.backoff(attempt);
                    if !self.pause(start, wait).await {
                        return Err(error);
                    }
                    attempt += 1;
                    continue;
                }
            };
            if response.status().as_u16() < 400 {
                return Ok(response);
            }

            let (response, api_error) = buffer_error(response).await;
            if response.status() == StatusCode::UNAUTHORIZED && can_repeat && !refreshed {
                if let Some(used) = &token_used {
                    refreshed = true;
                    if self.refresh(http, base, used).await {
                        continue;
                    }
                }
            }
            if retryable && !last && retryable_status(&api_error) {
                let wait = retry_after(response.headers()).unwrap_or_else(|| self.backoff(attempt));
                if self.pause(start, wait).await {
                    attempt += 1;
                    continue;
                }
            }
            return Ok(response);
        }
    }

    /// One attempt. Returns the access token it sent, if any.
    async fn send(
        &self,
        http: &reqwest::Client,
        mut request: reqwest::Request,
    ) -> (reqwest::Result<reqwest::Response>, Option<String>) {
        let used = self.authorize(request.headers_mut()).await;
        (http.execute(request).await, used)
    }

    async fn authorize(&self, headers: &mut HeaderMap) -> Option<String> {
        if let Some(key) = &self.0.api_key {
            headers.insert("x-api-key", key.clone());
            return None;
        }
        let guard = self.0.tokens.lock().await;
        let tokens = guard.as_ref()?;
        if let Ok(mut value) = HeaderValue::from_str(&format!("Bearer {}", tokens.access_token)) {
            value.set_sensitive(true);
            headers.insert(AUTHORIZATION, value);
        }
        Some(tokens.access_token.clone())
    }

    /// Trades the refresh token for a new pair, once for every caller that saw
    /// the same 401: the lock is held across the call, and a caller that finds
    /// the access token already changed does not refresh again. Reports whether
    /// the request is worth sending again.
    async fn refresh(&self, http: &reqwest::Client, base: &str, sent_with: &str) -> bool {
        let mut guard = self.0.tokens.lock().await;
        let Some(current) = guard.clone() else {
            return false;
        };
        if current.access_token != sent_with {
            return true;
        }
        let call = http
            .post(format!("{base}/api/v1/auth/refresh"))
            .json(&serde_json::json!({ "refresh_token": current.refresh_token }))
            .send()
            .await;
        let Ok(response) = call else {
            return false;
        };
        if response.status() != StatusCode::OK {
            return false;
        }
        let Ok(body) = response.json::<serde_json::Value>().await else {
            return false;
        };
        let (Some(access), Some(refresh)) = (
            body["access_token"].as_str(),
            body["refresh_token"].as_str(),
        ) else {
            return false;
        };
        let fresh = Tokens {
            access_token: access.to_string(),
            refresh_token: refresh.to_string(),
        };
        if let Some(sink) = &self.0.on_tokens {
            sink(&fresh);
        }
        *guard = Some(fresh);
        true
    }

    /// Full jitter: a random time up to `min(max_delay, base_delay * 2^attempt)`.
    fn backoff(&self, attempt: u32) -> Duration {
        let policy = &self.0.retry;
        let factor = 2u32.checked_pow(attempt).unwrap_or(u32::MAX);
        let ceiling = policy
            .base_delay
            .checked_mul(factor)
            .unwrap_or(policy.max_delay)
            .min(policy.max_delay);
        (self.0.jitter)(ceiling)
    }

    /// Waits `wait`. Reports false, without waiting, when that would pass the
    /// deadline.
    async fn pause(&self, start: Instant, wait: Duration) -> bool {
        if let Some(deadline) = self.0.retry.deadline {
            if start.elapsed() + wait > deadline {
                return false;
            }
        }
        (self.0.sleep)(wait).await;
        true
    }
}

fn retryable_status(error: &ApiError) -> bool {
    match error.status {
        429 | 502 | 503 | 504 => true,
        409 => error.code.as_deref() == Some(KEY_IN_PROGRESS),
        _ => false,
    }
}

/// Reads an error response's body and puts the response back together with the
/// parsed `ApiError` attached, because the body can be read only once.
async fn buffer_error(response: reqwest::Response) -> (reqwest::Response, ApiError) {
    let status = response.status();
    let headers = response.headers().clone();
    let body = response.bytes().await.unwrap_or_default();
    let error = ApiError::from_body(status.as_u16(), &body);
    let mut rebuilt = http::Response::new(body);
    *rebuilt.status_mut() = status;
    *rebuilt.headers_mut() = headers;
    rebuilt.extensions_mut().insert(error.clone());
    (reqwest::Response::from(rebuilt), error)
}

/// Reads a `Retry-After` header, given in seconds or as an HTTP date.
pub(crate) fn retry_after(headers: &HeaderMap) -> Option<Duration> {
    let value = headers.get(RETRY_AFTER)?.to_str().ok()?.trim();
    if let Ok(seconds) = value.parse::<f64>() {
        if seconds.is_finite() && seconds >= 0.0 {
            return Some(Duration::from_secs_f64(seconds.min(1e9)));
        }
        return None;
    }
    let when = httpdate::parse_http_date(value).ok()?;
    Some(when.duration_since(SystemTime::now()).unwrap_or_default())
}
