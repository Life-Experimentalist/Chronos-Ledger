// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

use std::future::Future;

use futures::{stream, Stream, TryStreamExt};

use crate::Error;

/// One response of a list route.
#[derive(Clone, Debug, PartialEq)]
pub struct Page<T> {
    /// The rows of this page.
    pub rows: Vec<T>,
    /// `X-Total-Count`: how many rows matched before `limit` and `offset` cut
    /// the page. `None` when the response had no such header.
    pub total: Option<u64>,
}

impl<T> From<progenitor_client::ResponseValue<Vec<T>>> for Page<T> {
    fn from(response: progenitor_client::ResponseValue<Vec<T>>) -> Self {
        let total = response
            .headers()
            .get("x-total-count")
            .and_then(|value| value.to_str().ok())
            .and_then(|text| text.parse().ok());
        Page {
            rows: response.into_inner(),
            total,
        }
    }
}

/// Walks a list route one row at a time. `fetch` makes one call with the given
/// `limit` and `offset`. The walk ends once `total` rows have been seen, when
/// a page comes back empty, or after the first error, which is yielded last.
///
/// ```ignore
/// let users = chronos_ledger_client::paginate(100, |limit, offset| {
///     let client = client.clone();
///     async move {
///         let page = client.users_list().limit(limit).offset(offset).send().await?;
///         Ok(page.into())
///     }
/// });
/// ```
///
/// A page size of zero means 100.
pub fn paginate<T, F, Fut>(page_size: u64, fetch: F) -> impl Stream<Item = Result<T, Error>>
where
    F: FnMut(u64, u64) -> Fut,
    Fut: Future<Output = Result<Page<T>, Error>>,
{
    let limit = if page_size == 0 { 100 } else { page_size };
    let mut fetch = fetch;
    stream::try_unfold(Some(0u64), move |next| {
        let pending = next.map(|offset| (offset, fetch(limit, offset)));
        async move {
            let Some((offset, call)) = pending else {
                return Ok::<_, Error>(None);
            };
            let page = call.await?;
            let seen = offset + page.rows.len() as u64;
            let done = page.rows.is_empty() || page.total.is_some_and(|total| seen >= total);
            let following = if done { None } else { Some(seen) };
            Ok(Some((page.rows, following)))
        }
    })
    .map_ok(|rows| stream::iter(rows.into_iter().map(Ok::<T, Error>)))
    .try_flatten()
}
