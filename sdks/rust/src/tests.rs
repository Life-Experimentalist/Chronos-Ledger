// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! Tests against a stub HTTP server on a local port. The stub answers each
//! request from a script and records what it was sent. The retry layer is given
//! a recording sleep and a jitter that returns the ceiling, so no test waits
//! and the waits can be compared exactly.

use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::Duration,
};

use futures::TryStreamExt;
use progenitor_client::ClientInfo;
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
};

use crate::{
    paginate,
    transport::{retry_after, Jitter, Sleeper},
    ApiError, Client, ClientBuilder, Error, Page, RetryPolicy, Tokens,
};

#[derive(Clone)]
enum Reply {
    /// Reads the request, then closes the connection without answering.
    Drop,
    Respond {
        status: u16,
        headers: Vec<(&'static str, String)>,
        body: String,
    },
}

fn respond(status: u16, body: &str) -> Reply {
    Reply::Respond {
        status,
        headers: Vec::new(),
        body: body.to_string(),
    }
}

impl Reply {
    fn header(mut self, name: &'static str, value: &str) -> Reply {
        if let Reply::Respond { headers, .. } = &mut self {
            headers.push((name, value.to_string()));
        }
        self
    }
}

#[derive(Clone, Debug)]
struct Seen {
    method: String,
    path: String,
    headers: HashMap<String, String>,
    body: String,
}

struct Stub {
    url: String,
    seen: Arc<Mutex<Vec<Seen>>>,
}

impl Stub {
    /// Answers request n with `script[n]`, and every request after the end of
    /// the script with its last entry.
    async fn start(script: Vec<Reply>) -> Stub {
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("bind");
        let url = format!("http://{}", listener.local_addr().expect("address"));
        let seen = Arc::new(Mutex::new(Vec::new()));
        let record = Arc::clone(&seen);
        tokio::spawn(async move {
            loop {
                let Ok((mut socket, _)) = listener.accept().await else {
                    return;
                };
                let Some(request) = read_request(&mut socket).await else {
                    continue;
                };
                let n = {
                    let mut all = record.lock().expect("seen");
                    all.push(request);
                    all.len() - 1
                };
                match script[n.min(script.len() - 1)].clone() {
                    Reply::Drop => drop(socket),
                    Reply::Respond {
                        status,
                        headers,
                        body,
                    } => {
                        let mut text = format!(
                            "HTTP/1.1 {status} X\r\ncontent-type: application/json\r\n\
                             content-length: {}\r\nconnection: close\r\n",
                            body.len()
                        );
                        for (name, value) in headers {
                            text.push_str(&format!("{name}: {value}\r\n"));
                        }
                        text.push_str("\r\n");
                        text.push_str(&body);
                        let _ = socket.write_all(text.as_bytes()).await;
                        let _ = socket.shutdown().await;
                    }
                }
            }
        });
        Stub { url, seen }
    }

    fn requests(&self) -> Vec<Seen> {
        self.seen.lock().expect("seen").clone()
    }
}

async fn read_request(socket: &mut TcpStream) -> Option<Seen> {
    let mut data = Vec::new();
    let mut chunk = [0u8; 4096];
    let head_end = loop {
        if let Some(at) = data.windows(4).position(|w| w == b"\r\n\r\n") {
            break at;
        }
        let n = socket.read(&mut chunk).await.ok()?;
        if n == 0 {
            return None;
        }
        data.extend_from_slice(&chunk[..n]);
    };
    let head = String::from_utf8_lossy(&data[..head_end]).to_string();
    let mut lines = head.split("\r\n");
    let mut first = lines.next()?.split(' ');
    let method = first.next()?.to_string();
    let path = first.next()?.to_string();
    let headers: HashMap<String, String> = lines
        .filter_map(|line| line.split_once(':'))
        .map(|(name, value)| (name.trim().to_lowercase(), value.trim().to_string()))
        .collect();
    let length: usize = headers
        .get("content-length")
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);
    let mut body = data[head_end + 4..].to_vec();
    while body.len() < length {
        let n = socket.read(&mut chunk).await.ok()?;
        if n == 0 {
            return None;
        }
        body.extend_from_slice(&chunk[..n]);
    }
    Some(Seen {
        method,
        path,
        headers,
        body: String::from_utf8_lossy(&body).to_string(),
    })
}

type Sleeps = Arc<Mutex<Vec<Duration>>>;

fn recording_sleeper() -> (Sleeper, Sleeps) {
    let sleeps: Sleeps = Arc::new(Mutex::new(Vec::new()));
    let record = Arc::clone(&sleeps);
    let sleeper: Sleeper = Arc::new(move |duration| {
        record.lock().expect("sleeps").push(duration);
        Box::pin(async {})
    });
    (sleeper, sleeps)
}

fn full_ceiling() -> Jitter {
    Arc::new(|ceiling| ceiling)
}

fn test_client(url: &str, policy: RetryPolicy) -> (Client, Sleeps) {
    let (sleeper, sleeps) = recording_sleeper();
    let client = ClientBuilder::new(url)
        .api_key("test-key")
        .retry(policy)
        .sleeper(sleeper)
        .jitter(full_ceiling())
        .build()
        .expect("client");
    (client, sleeps)
}

/// Sends a request through the retry layer, as every generated call does.
async fn send(client: &Client, request: reqwest::Request) -> reqwest::Response {
    client
        .inner()
        .execute(client.client(), client.baseurl(), request)
        .await
        .expect("a response")
}

fn post_reservation(client: &Client, key: Option<&str>) -> reqwest::Request {
    let mut request = client
        .client()
        .post(format!(
            "{}/api/v1/resources/1/reservations",
            client.baseurl()
        ))
        .json(&serde_json::json!({ "date": "2026-10-20" }));
    if let Some(key) = key {
        request = request.header("Idempotency-Key", key);
    }
    request.build().expect("request")
}

fn get(client: &Client, path: &str) -> reqwest::Request {
    client
        .client()
        .get(format!("{}{path}", client.baseurl()))
        .build()
        .expect("request")
}

fn ms(n: u64) -> Duration {
    Duration::from_millis(n)
}

#[tokio::test]
async fn dropped_first_response_creates_once_under_one_key() {
    let stub = Stub::start(vec![Reply::Drop, respond(201, "{}")]).await;
    let (client, sleeps) = test_client(&stub.url, RetryPolicy::default());

    let response = send(&client, post_reservation(&client, None)).await;

    assert_eq!(response.status(), 201);
    let seen = stub.requests();
    assert_eq!(seen.len(), 2);
    let first = seen[0].headers.get("idempotency-key").expect("a key");
    assert_eq!(seen[1].headers.get("idempotency-key"), Some(first));
    let parsed = uuid::Uuid::parse_str(first).expect("a UUID");
    assert_eq!(parsed.get_version_num(), 4);
    assert_eq!(seen[0].body, seen[1].body);
    assert_eq!(seen[0].method, "POST");
    assert_eq!(sleeps.lock().unwrap().len(), 1);
}

#[tokio::test]
async fn a_key_from_the_caller_is_kept() {
    let stub = Stub::start(vec![respond(503, "{}"), respond(201, "{}")]).await;
    let (client, _) = test_client(&stub.url, RetryPolicy::default());

    let response = send(&client, post_reservation(&client, Some("mine-1"))).await;

    assert_eq!(response.status(), 201);
    for request in stub.requests() {
        assert_eq!(request.headers["idempotency-key"], "mine-1");
    }
}

#[tokio::test]
async fn other_client_errors_are_never_retried() {
    let cases = [
        (400, r#"{"detail":"bad","code":"BAD_REQUEST"}"#),
        (404, r#"{"detail":"missing","code":"NOT_FOUND"}"#),
        (
            409,
            r#"{"detail":{"message":"taken","conflicts":[]},"code":"RESERVATION_CONFLICT"}"#,
        ),
        (422, r#"{"detail":[],"code":"VALIDATION_FAILED"}"#),
    ];
    for (status, body) in cases {
        let stub = Stub::start(vec![respond(status, body), respond(200, "{}")]).await;
        let (client, sleeps) = test_client(&stub.url, RetryPolicy::default());

        let response = send(&client, post_reservation(&client, None)).await;

        assert_eq!(response.status(), status);
        assert_eq!(stub.requests().len(), 1, "status {status} was retried");
        assert!(sleeps.lock().unwrap().is_empty());
        let api = response.extensions().get::<ApiError>().expect("parsed");
        assert_eq!(api.status, status);
    }
}

#[tokio::test]
async fn retry_after_is_honoured() {
    let stub = Stub::start(vec![
        respond(429, r#"{"detail":"slow down","code":"RATE_LIMITED"}"#).header("Retry-After", "3"),
        respond(200, "{}"),
    ])
    .await;
    let (client, sleeps) = test_client(&stub.url, RetryPolicy::default());

    let response = send(&client, get(&client, "/api/v1/auth/me")).await;

    assert_eq!(response.status(), 200);
    assert_eq!(*sleeps.lock().unwrap(), vec![Duration::from_secs(3)]);
}

#[tokio::test]
async fn backoff_doubles_and_is_capped() {
    let stub = Stub::start(vec![respond(503, r#"{"detail":"down"}"#)]).await;
    let policy = RetryPolicy {
        max_attempts: 6,
        base_delay: ms(250),
        max_delay: ms(1000),
        deadline: None,
    };
    let (client, sleeps) = test_client(&stub.url, policy);

    let response = send(&client, get(&client, "/api/v1/auth/me")).await;

    assert_eq!(response.status(), 503);
    assert_eq!(stub.requests().len(), 6);
    assert_eq!(
        *sleeps.lock().unwrap(),
        vec![ms(250), ms(500), ms(1000), ms(1000), ms(1000)]
    );
}

#[tokio::test]
async fn default_policy_makes_four_attempts() {
    let stub = Stub::start(vec![respond(502, "{}")]).await;
    let (client, _) = test_client(&stub.url, RetryPolicy::default());

    let response = send(&client, get(&client, "/api/v1/auth/me")).await;

    assert_eq!(response.status(), 502);
    assert_eq!(stub.requests().len(), 4);
}

#[tokio::test]
async fn a_key_still_in_progress_is_retried() {
    let stub = Stub::start(vec![
        respond(
            409,
            r#"{"detail":"in flight","code":"IDEMPOTENCY_KEY_IN_PROGRESS"}"#,
        ),
        respond(201, "{}"),
    ])
    .await;
    let (client, _) = test_client(&stub.url, RetryPolicy::default());

    let response = send(&client, post_reservation(&client, None)).await;

    assert_eq!(response.status(), 201);
    let seen = stub.requests();
    assert_eq!(seen.len(), 2);
    assert_eq!(
        seen[0].headers["idempotency-key"],
        seen[1].headers["idempotency-key"]
    );
}

#[tokio::test]
async fn the_deadline_skips_a_wait_that_would_pass_it() {
    let stub = Stub::start(vec![
        respond(503, "{}").header("Retry-After", "5"),
        respond(200, "{}"),
    ])
    .await;
    let policy = RetryPolicy {
        deadline: Some(Duration::from_secs(1)),
        ..RetryPolicy::default()
    };
    let (client, sleeps) = test_client(&stub.url, policy);

    let response = send(&client, get(&client, "/api/v1/auth/me")).await;

    assert_eq!(response.status(), 503);
    assert_eq!(stub.requests().len(), 1);
    assert!(sleeps.lock().unwrap().is_empty());
}

#[tokio::test]
async fn retries_can_be_turned_off() {
    let stub = Stub::start(vec![respond(503, "{}"), respond(200, "{}")]).await;
    let client = ClientBuilder::new(&stub.url)
        .api_key("test-key")
        .without_retries()
        .build()
        .expect("client");

    let response = send(&client, get(&client, "/api/v1/auth/me")).await;

    assert_eq!(response.status(), 503);
    assert_eq!(stub.requests().len(), 1);
}

#[test]
fn an_error_body_is_parsed() {
    let body = br#"{"detail":{"message":"Room is taken","conflicts":[{"id":1},{"id":2}]},"code":"RESERVATION_CONFLICT"}"#;
    let api = ApiError::from_body(409, body);
    assert_eq!(api.status, 409);
    assert_eq!(api.code.as_deref(), Some("RESERVATION_CONFLICT"));
    assert_eq!(api.conflicts.len(), 2);
    assert_eq!(api.conflicts[0]["id"], 1);
    assert_eq!(api.to_string(), "chronos: 409: Room is taken");

    let plain = ApiError::from_body(404, br#"{"detail":"No such user","code":"USER_NOT_FOUND"}"#);
    assert_eq!(plain.detail, Some(serde_json::json!("No such user")));
    assert_eq!(plain.code.as_deref(), Some("USER_NOT_FOUND"));
    assert!(plain.conflicts.is_empty());

    let page = ApiError::from_body(502, b"<html>Bad Gateway</html>");
    assert_eq!(page.code, None);
    assert_eq!(
        page.detail,
        Some(serde_json::json!("<html>Bad Gateway</html>"))
    );
}

#[test]
fn retry_after_reads_seconds_and_dates() {
    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("retry-after", "2.5".parse().unwrap());
    assert_eq!(retry_after(&headers), Some(ms(2500)));
    headers.insert(
        "retry-after",
        "Wed, 21 Oct 2015 07:28:00 GMT".parse().unwrap(),
    );
    assert_eq!(retry_after(&headers), Some(Duration::ZERO));
    headers.insert("retry-after", "soon".parse().unwrap());
    assert_eq!(retry_after(&headers), None);
}

#[tokio::test]
async fn a_generated_call_retries_and_sends_the_key() {
    let stub = Stub::start(vec![respond(503, "{}"), respond(200, "{}")]).await;
    let (client, _) = test_client(&stub.url, RetryPolicy::default());

    let me = client.auth_get_me().send().await;

    assert!(me.is_ok());
    let seen = stub.requests();
    assert_eq!(seen.len(), 2);
    assert_eq!(seen[0].path, "/api/v1/auth/me");
    assert_eq!(seen[0].headers["x-api-key"], "test-key");
}

#[tokio::test]
async fn a_generated_call_reports_the_server_error() {
    let stub = Stub::start(vec![respond(
        422,
        r#"{"detail":[{"msg":"field required"}],"code":"VALIDATION_FAILED"}"#,
    )])
    .await;
    let (client, _) = test_client(&stub.url, RetryPolicy::default());

    let error = client.auth_get_me().send().await.expect_err("a refusal");

    match Error::from(error) {
        Error::Api(api) => {
            assert_eq!(api.status, 422);
            assert_eq!(api.code.as_deref(), Some("VALIDATION_FAILED"));
            assert!(api.detail.expect("detail").is_array());
        }
        other => panic!("expected an API error, got {other:?}"),
    }
    assert_eq!(stub.requests().len(), 1);
}

#[tokio::test]
async fn a_401_refreshes_the_tokens_once() {
    let stub = Stub::start(vec![
        respond(401, r#"{"detail":"expired","code":"TOKEN_EXPIRED"}"#),
        respond(
            200,
            r#"{"access_token":"new-access","refresh_token":"new-refresh"}"#,
        ),
        respond(200, "{}"),
    ])
    .await;
    let stored: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
    let sink = Arc::clone(&stored);
    let client = ClientBuilder::new(&stub.url)
        .tokens(
            Tokens {
                access_token: "old-access".to_string(),
                refresh_token: "old-refresh".to_string(),
            },
            move |tokens| sink.lock().unwrap().push(tokens.refresh_token.clone()),
        )
        .build()
        .expect("client");

    let me = client.auth_get_me().send().await;

    assert!(me.is_ok());
    let seen = stub.requests();
    assert_eq!(seen.len(), 3);
    assert_eq!(seen[0].headers["authorization"], "Bearer old-access");
    assert_eq!(seen[1].path, "/api/v1/auth/refresh");
    assert!(seen[1].body.contains("old-refresh"));
    assert_eq!(seen[2].headers["authorization"], "Bearer new-access");
    assert_eq!(*stored.lock().unwrap(), vec!["new-refresh".to_string()]);
}

#[test]
fn the_builder_checks_its_setup() {
    assert!(matches!(
        ClientBuilder::new("").build(),
        Err(Error::Config(_))
    ));
    let both = ClientBuilder::new("http://localhost")
        .api_key("k")
        .tokens(
            Tokens {
                access_token: "a".to_string(),
                refresh_token: "r".to_string(),
            },
            |_| {},
        )
        .build();
    assert!(matches!(both, Err(Error::Config(_))));

    let client = ClientBuilder::new("http://localhost:8000/api/v1/")
        .build()
        .expect("client");
    assert_eq!(client.baseurl(), "http://localhost:8000");
}

#[tokio::test]
async fn paging_walks_every_row_by_total_count() {
    let calls: Arc<Mutex<Vec<(u64, u64)>>> = Arc::new(Mutex::new(Vec::new()));
    let record = Arc::clone(&calls);
    let rows = paginate(2, move |limit, offset| {
        record.lock().unwrap().push((limit, offset));
        async move {
            let end = (offset + limit).min(5);
            Ok::<_, Error>(Page {
                rows: (offset..end).collect::<Vec<u64>>(),
                total: Some(5),
            })
        }
    })
    .try_collect::<Vec<u64>>()
    .await
    .expect("rows");

    assert_eq!(rows, vec![0, 1, 2, 3, 4]);
    assert_eq!(*calls.lock().unwrap(), vec![(2, 0), (2, 2), (2, 4)]);
}

#[tokio::test]
async fn paging_stops_at_an_empty_page_without_a_total() {
    let rows = paginate(0, |_, offset| async move {
        let rows = if offset == 0 { vec![7u64] } else { Vec::new() };
        Ok::<_, Error>(Page { rows, total: None })
    })
    .try_collect::<Vec<u64>>()
    .await
    .expect("rows");

    assert_eq!(rows, vec![7]);
}

#[tokio::test]
async fn paging_ends_on_the_first_error() {
    let result = paginate(1, |_, offset| async move {
        if offset == 0 {
            Ok(Page {
                rows: vec![1u64],
                total: Some(9),
            })
        } else {
            Err(Error::Config("stopped".to_string()))
        }
    })
    .try_collect::<Vec<u64>>()
    .await;

    assert!(matches!(result, Err(Error::Config(_))));
}
