// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

package chronos

import (
	"context"
	"iter"
)

// Page is one response of a list route.
type Page[T any] struct {
	Rows []T
	// Total is X-Total-Count, or nil if the response had none. The generated
	// list responses carry it as Headers200.XTotalCount.
	Total *int
}

// Paginate walks a list route page by page. fetch makes one call with the
// given limit and offset. The walk ends once Total rows have been seen, when a
// page comes back empty, or after the first error, which is yielded last.
//
//	users := chronos.Paginate(ctx, 100, func(ctx context.Context, limit, offset int) (chronos.Page[generated.UserResponse], error) {
//		res, err := c.UsersListWithResponse(ctx, &generated.UsersListParams{Limit: &limit, Offset: &offset})
//		if err != nil || res.JSON200 == nil {
//			return chronos.Page[generated.UserResponse]{}, err
//		}
//		return chronos.Page[generated.UserResponse]{Rows: *res.JSON200, Total: res.Headers200.XTotalCount}, nil
//	})
//	for user, err := range users { ... }
//
// A page size of zero or less means 100.
func Paginate[T any](ctx context.Context, pageSize int, fetch func(ctx context.Context, limit, offset int) (Page[T], error)) iter.Seq2[T, error] {
	if pageSize <= 0 {
		pageSize = 100
	}
	return func(yield func(T, error) bool) {
		offset := 0
		for {
			page, err := fetch(ctx, pageSize, offset)
			if err != nil {
				var zero T
				yield(zero, err)
				return
			}
			for _, row := range page.Rows {
				if !yield(row, nil) {
					return
				}
			}
			offset += len(page.Rows)
			if len(page.Rows) == 0 || page.Total == nil || offset >= *page.Total {
				return
			}
		}
	}
}
