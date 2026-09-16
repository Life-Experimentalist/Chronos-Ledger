// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Walk a list route page by page. `fetchPage` makes one call with the given
 * `limit` and `offset`. The walk ends once `X-Total-Count` rows have been
 * seen, or when a page comes back empty.
 *
 *     for await (const user of paginate((limit, offset) =>
 *       chronos.GET("/api/v1/users/", { params: { query: { limit, offset } } }))) { ... }
 */
export async function* paginate<T>(
  fetchPage: (limit: number, offset: number) => Promise<{ data?: T[]; response: Response }>,
  pageSize = 100,
): AsyncGenerator<T> {
  let offset = 0;
  for (;;) {
    const { data, response } = await fetchPage(pageSize, offset);
    const rows = data ?? [];
    yield* rows;
    offset += rows.length;
    const header = response.headers.get("X-Total-Count");
    if (rows.length === 0 || header === null || offset >= Number(header)) return;
  }
}
