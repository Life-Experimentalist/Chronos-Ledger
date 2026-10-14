// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! A typed client for the Chronos Ledger REST API.
//!
//! The calls are generated from `openapi.yaml` by progenitor, in `build.rs`.
//! This crate adds what a generator cannot know: how to authenticate, when a
//! retry is safe, how to page, and one error type.
//!
//! ```ignore
//! use chronosledger_client::{ClientBuilder, Error};
//!
//! let client = ClientBuilder::new("https://chronos.example.org")
//!     .api_key("clk_...")
//!     .build()?;
//! let users = client.users_list().send().await.map_err(Error::from)?;
//! ```
//!
//! Every operation is a method on [`Client`] named after its operation id, for
//! example `users_list`. A call returns `progenitor_client::Error<()>`; convert
//! it with `Error::from` to get an [`ApiError`] for any status of 400 or above.

#![forbid(unsafe_code)]
// `Error::Client` holds the generator's error as it is, so callers can match on it.
#![allow(clippy::result_large_err)]

mod builder;
mod error;
mod page;
mod transport;

#[cfg(test)]
mod tests;

#[allow(
    clippy::all,
    clippy::pedantic,
    unused_imports,
    unused_variables,
    dead_code,
    missing_docs
)]
mod generated {
    include!(concat!(env!("OUT_DIR"), "/codegen.rs"));
}

pub use builder::ClientBuilder;
pub use error::{ApiError, Error};
pub use generated::{types, Client};
pub use page::{paginate, Page};
pub use transport::{new_idempotency_key, RetryPolicy, State, Tokens};

use progenitor_client::{ClientHooks, ClientInfo, OperationInfo};

/// Every generated call goes through `State::execute`, which adds auth and an
/// idempotency key, retries, and attaches the parsed error body.
impl ClientHooks<State> for Client {
    async fn exec(
        &self,
        request: reqwest::Request,
        _info: &OperationInfo,
    ) -> reqwest::Result<reqwest::Response> {
        self.inner()
            .execute(self.client(), self.baseurl(), request)
            .await
    }
}

impl Client {
    /// `POST /api/v1/ingestion/upload-csv`. progenitor cannot send
    /// `multipart/form-data`, so this call is written by hand. The body is a
    /// stream, so the file is sent once and never retried.
    pub async fn ingestion_upload_csv(
        &self,
        cycle_id: i64,
        filename: impl Into<String>,
        contents: Vec<u8>,
    ) -> Result<types::CsvImportResult, Error> {
        let part = reqwest::multipart::Part::bytes(contents)
            .file_name(filename.into())
            .mime_str("text/csv")
            .map_err(|error| Error::Config(error.to_string()))?;
        let request = self
            .client()
            .post(format!("{}/api/v1/ingestion/upload-csv", self.baseurl()))
            .query(&[("cycle_id", cycle_id)])
            .multipart(reqwest::multipart::Form::new().part("file", part))
            .build()
            .map_err(|error| Error::Client(error.into()))?;
        let response = self
            .inner()
            .execute(self.client(), self.baseurl(), request)
            .await
            .map_err(|error| Error::Client(error.into()))?;
        if let Some(api) = response.extensions().get::<ApiError>() {
            return Err(Error::Api(api.clone()));
        }
        response
            .json()
            .await
            .map_err(|error| Error::Client(error.into()))
    }
}
