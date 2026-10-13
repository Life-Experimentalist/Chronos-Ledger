// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

package chronos

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"io"
	"math"
	mathrand "math/rand/v2"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/Life-Experimentalist/Chronos-Ledger/sdks/go/generated"
)

const (
	idempotencyKeyHeader = "Idempotency-Key"
	codeKeyInProgress    = "IDEMPOTENCY_KEY_IN_PROGRESS"
	// An error body is read to find its code. A server does not send more.
	maxErrorBody = 1 << 20
)

// Tokens is an access token and the single-use refresh token that came with it.
type Tokens struct {
	AccessToken  string
	RefreshToken string
}

// RetryPolicy says when and how often a failed request is sent again.
//
// A request is retried when no response arrived, or the status was 429, 502,
// 503 or 504, or a 409 with code IDEMPOTENCY_KEY_IN_PROGRESS. Other 4xx
// statuses are never retried. A read is always retried; a write only when it
// carries an Idempotency-Key, which the client makes for every write unless the
// caller sends one. The key is the same on every attempt.
//
// The wait before attempt n+1 is a random time between zero and
// min(MaxDelay, BaseDelay * 2^n) ("full jitter"), or the server's Retry-After
// when it sent one.
type RetryPolicy struct {
	// MaxAttempts counts the first try. One means no retries.
	MaxAttempts int
	// BaseDelay is the backoff ceiling before the first retry.
	BaseDelay time.Duration
	// MaxDelay caps the backoff. It does not cap a Retry-After.
	MaxDelay time.Duration
	// Deadline is the most time one call spends, counted from its first
	// attempt, before it stops retrying and returns the last failure. Zero
	// means no deadline.
	Deadline time.Duration
}

// DefaultRetryPolicy is 4 attempts, 0.25 s base, 8 s cap and a 30 s deadline.
func DefaultRetryPolicy() RetryPolicy {
	return RetryPolicy{
		MaxAttempts: 4,
		BaseDelay:   250 * time.Millisecond,
		MaxDelay:    8 * time.Second,
		Deadline:    30 * time.Second,
	}
}

// transport sits under the generated client as its HttpRequestDoer. It adds
// auth, makes idempotency keys, retries, and turns status 400 and above into
// *Error, so a generated call returns that error instead of a typed 4xx body.
type transport struct {
	inner     generated.HttpRequestDoer
	baseURL   string
	userAgent string
	apiKey    string
	onTokens  func(Tokens)
	retry     RetryPolicy

	// mu guards tokens, and is held across a refresh: a refresh token is spent
	// on first use, so callers that see a 401 together must not each refresh.
	mu     sync.Mutex
	tokens *Tokens

	makeKeys bool
	sleep    func(ctx context.Context, d time.Duration) error
	now      func() time.Time
	jitter   func(ceiling time.Duration) time.Duration
}

func (t *transport) currentTokens() *Tokens {
	t.mu.Lock()
	defer t.mu.Unlock()
	return t.tokens
}

// Do sends req, retrying as the RetryPolicy allows.
func (t *transport) Do(req *http.Request) (*http.Response, error) {
	ctx := req.Context()
	write := !isRead(req.Method)
	if write && t.makeKeys && req.Header.Get(idempotencyKeyHeader) == "" {
		req.Header.Set(idempotencyKeyHeader, newKey())
	}
	retryable := !write || req.Header.Get(idempotencyKeyHeader) != ""
	// A body that cannot be read again (no GetBody) can be sent only once.
	replayable := req.Body == nil || req.Body == http.NoBody || req.GetBody != nil
	if !replayable {
		retryable = false
	}

	start := t.now()
	refreshed := false
	for attempt := 0; ; {
		sentWith := t.currentTokens()
		out, err := t.send(req, sentWith, attempt > 0 || refreshed)
		if err != nil {
			if ctx.Err() != nil || !retryable || attempt+1 >= t.retry.MaxAttempts {
				return nil, err
			}
			if !t.pause(ctx, start, t.backoff(attempt)) {
				return nil, err
			}
			attempt++
			continue
		}
		if out.StatusCode < 400 {
			return out, nil
		}

		body, _ := io.ReadAll(io.LimitReader(out.Body, maxErrorBody))
		_ = out.Body.Close()
		apiErr := newError(out.StatusCode, body)

		if out.StatusCode == http.StatusUnauthorized && sentWith != nil && t.apiKey == "" && !refreshed && replayable {
			refreshed = true
			if t.refresh(ctx, sentWith) {
				continue
			}
		}
		if retryable && attempt+1 < t.retry.MaxAttempts && retryableResponse(apiErr) {
			wait, ok := retryAfter(out.Header, t.now())
			if !ok {
				wait = t.backoff(attempt)
			}
			if t.pause(ctx, start, wait) {
				attempt++
				continue
			}
		}
		return nil, apiErr
	}
}

// send makes one attempt with its own copy of the request. On every attempt
// after the first the body is made again, because the last one was read.
func (t *transport) send(req *http.Request, tokens *Tokens, again bool) (*http.Response, error) {
	r := req.Clone(req.Context())
	if again && req.GetBody != nil {
		body, err := req.GetBody()
		if err != nil {
			return nil, err
		}
		r.Body = body
	}
	r.Header.Set("User-Agent", t.userAgent)
	if t.apiKey != "" {
		r.Header.Set("X-API-Key", t.apiKey)
	} else if tokens != nil {
		r.Header.Set("Authorization", "Bearer "+tokens.AccessToken)
	}
	return t.inner.Do(r)
}

// refresh trades the refresh token for a new pair, once for every caller that
// saw the same 401. It reports whether the request is worth sending again.
func (t *transport) refresh(ctx context.Context, sentWith *Tokens) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.tokens != sentWith {
		return true // another caller already refreshed
	}
	payload, _ := json.Marshal(map[string]string{"refresh_token": sentWith.RefreshToken})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.baseURL+"/api/v1/auth/refresh", bytes.NewReader(payload))
	if err != nil {
		return false
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", t.userAgent)
	resp, err := t.inner.Do(req)
	if err != nil {
		return false
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		return false
	}
	var pair struct {
		AccessToken  string `json:"access_token"`
		RefreshToken string `json:"refresh_token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&pair); err != nil || pair.AccessToken == "" {
		return false
	}
	t.tokens = &Tokens{AccessToken: pair.AccessToken, RefreshToken: pair.RefreshToken}
	if t.onTokens != nil {
		t.onTokens(*t.tokens)
	}
	return true
}

// backoff is full jitter: a random time up to min(MaxDelay, BaseDelay * 2^attempt).
func (t *transport) backoff(attempt int) time.Duration {
	ceiling := float64(t.retry.BaseDelay) * math.Pow(2, float64(attempt))
	if ceiling > float64(t.retry.MaxDelay) {
		ceiling = float64(t.retry.MaxDelay)
	}
	if ceiling <= 0 {
		return 0
	}
	return t.jitter(time.Duration(ceiling))
}

// pause waits d before the next attempt. It reports false, without waiting,
// when the wait would pass the deadline, and false when the context ends.
func (t *transport) pause(ctx context.Context, start time.Time, d time.Duration) bool {
	if t.retry.Deadline > 0 && t.now().Add(d).Sub(start) > t.retry.Deadline {
		return false
	}
	return t.sleep(ctx, d) == nil
}

func isRead(method string) bool {
	return method == http.MethodGet || method == http.MethodHead || method == http.MethodOptions
}

func retryableResponse(e *Error) bool {
	switch e.Status {
	case http.StatusTooManyRequests, http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
		return true
	case http.StatusConflict:
		return e.Code == codeKeyInProgress
	}
	return false
}

// retryAfter reads a Retry-After header, given in seconds or as an HTTP date.
func retryAfter(h http.Header, now time.Time) (time.Duration, bool) {
	value := strings.TrimSpace(h.Get("Retry-After"))
	if value == "" {
		return 0, false
	}
	if seconds, err := strconv.ParseFloat(value, 64); err == nil {
		if seconds < 0 || math.IsNaN(seconds) {
			return 0, false
		}
		return time.Duration(min(seconds, 1e9) * float64(time.Second)), true
	}
	if when, err := http.ParseTime(value); err == nil {
		return max(0, when.Sub(now)), true
	}
	return 0, false
}

// newKey makes a version 4 UUID for an Idempotency-Key.
func newKey() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err) // the system random source failed; Go documents that this does not happen
	}
	b[6] = b[6]&0x0f | 0x40
	b[8] = b[8]&0x3f | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

func sleepContext(ctx context.Context, d time.Duration) error {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-timer.C:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func randomUpTo(ceiling time.Duration) time.Duration {
	return time.Duration(mathrand.Int64N(int64(ceiling) + 1))
}
