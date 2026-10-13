// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

package chronos

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strings"
)

// Error is every response with status 400 or above, after retries and a token
// refresh have been tried. Use errors.As to reach it:
//
//	var apiErr *chronos.Error
//	if errors.As(err, &apiErr) && apiErr.Status == 409 { ... }
type Error struct {
	// Status is the HTTP status code.
	Status int
	// Code is the server's code for what went wrong, such as "EMAIL_TAKEN",
	// for a program to branch on. A plain string rather than the generated
	// ErrorCode, so a code added after this client was built still arrives.
	// It is empty when the body had no code, for example a proxy's error page.
	Code string
	// Detail is the body's detail exactly as the server returned it: a string,
	// a map for a 409, or a list for VALIDATION_FAILED. A body that is not
	// JSON is kept as text, and an empty body leaves it nil.
	Detail any
	// Conflicts holds the clashing intervals of a 409, or is empty.
	Conflicts []map[string]any
}

func (e *Error) Error() string {
	if s, ok := e.Detail.(string); ok {
		return fmt.Sprintf("chronos: %d: %s", e.Status, s)
	}
	if m, ok := e.Detail.(map[string]any); ok {
		if s, ok := m["message"].(string); ok {
			return fmt.Sprintf("chronos: %d: %s", e.Status, s)
		}
	}
	return fmt.Sprintf("chronos: HTTP %d", e.Status)
}

// newError reads an error response body. The server sends {"detail", "code"}.
func newError(status int, body []byte) *Error {
	e := &Error{Status: status}
	var parsed any
	if err := json.NewDecoder(bytes.NewReader(body)).Decode(&parsed); err != nil {
		// Not JSON, for example an HTML page from a proxy: keep the text.
		if text := strings.TrimSpace(string(body)); text != "" {
			e.Detail = string(body)
		}
		return e
	}
	e.Detail = parsed
	if m, ok := parsed.(map[string]any); ok {
		if detail, ok := m["detail"]; ok {
			e.Detail = detail
		}
		if code, ok := m["code"].(string); ok {
			e.Code = code
		}
	}
	if m, ok := e.Detail.(map[string]any); ok {
		if list, ok := m["conflicts"].([]any); ok {
			for _, item := range list {
				if conflict, ok := item.(map[string]any); ok {
					e.Conflicts = append(e.Conflicts, conflict)
				}
			}
		}
	}
	return e
}
