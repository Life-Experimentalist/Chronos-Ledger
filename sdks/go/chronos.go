// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

// Package chronos is a typed client for the Chronos Ledger REST API.
//
// The calls are generated from docs/openapi.yaml by oapi-codegen and live in
// the generated package. This package adds what a generator cannot know: how to
// authenticate, when a retry is safe, how to page, and one error type.
//
//	c, err := chronos.New("https://chronos.example.org", chronos.WithAPIKey(key))
//	res, err := c.ResourcesListWithResponse(ctx, &generated.ResourcesListParams{})
//
// Every status of 400 or above comes back as a *chronos.Error in err, so the
// typed JSON4xx fields of a generated response are never filled.
package chronos

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/Life-Experimentalist/Chronos-Ledger/sdks/go/generated"
)

// Client is the generated client with the transport this package adds. Every
// operation is a method, named after its operationId, for example
// ResourcesListWithResponse.
type Client struct {
	*generated.ClientWithResponses
	transport *transport
}

type config struct {
	apiKey   string
	tokens   *Tokens
	onTokens func(Tokens)
	http     generated.HttpRequestDoer
	retry    RetryPolicy
	sleep    func(ctx context.Context, d time.Duration) error
	now      func() time.Time
	jitter   func(ceiling time.Duration) time.Duration
	makeKeys bool
}

// Option changes how New builds a client.
type Option func(*config)

// WithAPIKey authenticates with a scoped API key, sent as X-API-Key.
func WithAPIKey(key string) Option {
	return func(c *config) { c.apiKey = key }
}

// WithTokens authenticates with the pair from POST /api/v1/auth/login. On a 401
// the client calls /api/v1/auth/refresh once and sends the request again. A
// refresh token works only once, so onTokens must store each new pair.
// Callers that hit a 401 together share one refresh. onTokens may be nil.
func WithTokens(tokens Tokens, onTokens func(Tokens)) Option {
	return func(c *config) {
		c.tokens = &tokens
		c.onTokens = onTokens
	}
}

// WithHTTPClient replaces the http.Client the requests go through. The default
// has a 30 second timeout.
func WithHTTPClient(client generated.HttpRequestDoer) Option {
	return func(c *config) { c.http = client }
}

// WithRetry replaces DefaultRetryPolicy.
func WithRetry(policy RetryPolicy) Option {
	return func(c *config) { c.retry = policy }
}

// WithoutRetries sends every request once.
func WithoutRetries() Option {
	return func(c *config) { c.retry = RetryPolicy{MaxAttempts: 1} }
}

// New returns a client for the server at baseURL, for example
// https://chronos.example.org. A trailing /api/v1 is accepted and dropped,
// because every generated path already carries it.
func New(baseURL string, opts ...Option) (*Client, error) {
	cfg := config{
		retry:    DefaultRetryPolicy(),
		sleep:    sleepContext,
		now:      time.Now,
		jitter:   randomUpTo,
		makeKeys: true,
	}
	for _, opt := range opts {
		opt(&cfg)
	}
	baseURL = strings.TrimSuffix(strings.TrimRight(baseURL, "/"), "/api/v1")
	if baseURL == "" {
		return nil, errors.New("chronos: base URL is required")
	}
	if cfg.apiKey != "" && cfg.tokens != nil {
		return nil, errors.New("chronos: pass an API key or tokens, not both")
	}
	if cfg.http == nil {
		cfg.http = &http.Client{Timeout: 30 * time.Second}
	}
	if cfg.retry.MaxAttempts < 1 {
		cfg.retry.MaxAttempts = 1
	}
	t := &transport{
		inner:     cfg.http,
		baseURL:   baseURL,
		userAgent: "chronos-go/" + Version,
		apiKey:    cfg.apiKey,
		onTokens:  cfg.onTokens,
		retry:     cfg.retry,
		tokens:    cfg.tokens,
		makeKeys:  cfg.makeKeys,
		sleep:     cfg.sleep,
		now:       cfg.now,
		jitter:    cfg.jitter,
	}
	generatedClient, err := generated.NewClientWithResponses(baseURL, generated.WithHTTPClient(t))
	if err != nil {
		return nil, fmt.Errorf("chronos: %w", err)
	}
	return &Client{ClientWithResponses: generatedClient, transport: t}, nil
}

// CreateReservation holds a resource. The route needs an Idempotency-Key, so
// one is made when idempotencyKey is empty, and the same key goes out on every
// retry: a retry never takes a second hold. Pass your own key when a retry can
// come from outside the process, for example after a crash.
func (c *Client) CreateReservation(ctx context.Context, resourceID int, body generated.ReservationCreate, idempotencyKey string) (*generated.ReservationResponse, error) {
	if idempotencyKey == "" {
		idempotencyKey = newKey()
	}
	res, err := c.ResourcesCreateReservationWithResponse(ctx, resourceID, &generated.ResourcesCreateReservationParams{IdempotencyKey: idempotencyKey}, body)
	if err != nil {
		return nil, err
	}
	switch {
	case res.JSON201 != nil:
		return res.JSON201, nil
	case res.JSON200 != nil:
		return res.JSON200, nil
	}
	return nil, &Error{Status: res.StatusCode(), Detail: string(res.Body)}
}
