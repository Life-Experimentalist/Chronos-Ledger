// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

package chronos

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/Life-Experimentalist/Chronos-Ledger/sdks/go/generated"
	openapi_types "github.com/oapi-codegen/runtime/types"
)

// fakeClock stands in for time, so a retry test neither waits nor flakes.
// Sleeping moves the clock, which is how the deadline sees it.
type fakeClock struct {
	mu    sync.Mutex
	t     time.Time
	slept []time.Duration
}

func newFakeClock() *fakeClock { return &fakeClock{t: time.Unix(1_700_000_000, 0)} }

func (f *fakeClock) now() time.Time {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.t
}

func (f *fakeClock) sleep(_ context.Context, d time.Duration) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.slept = append(f.slept, d)
	f.t = f.t.Add(d)
	return nil
}

func (f *fakeClock) sleeps() []time.Duration {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]time.Duration(nil), f.slept...)
}

// withClock swaps the clock and makes the jitter its own ceiling, so the wait
// before each retry is the largest the policy allows.
func withClock(f *fakeClock) Option {
	return func(c *config) {
		c.sleep = f.sleep
		c.now = f.now
		c.jitter = func(ceiling time.Duration) time.Duration { return ceiling }
	}
}

// stub is a local server that records every request it receives.
type stub struct {
	*httptest.Server
	mu       sync.Mutex
	requests []recorded
}

type recorded struct {
	Method string
	Path   string
	Query  string
	Header http.Header
	Body   string
}

func newStub(t *testing.T, handler func(n int, w http.ResponseWriter, r *http.Request)) *stub {
	t.Helper()
	s := &stub{}
	s.Server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		s.mu.Lock()
		s.requests = append(s.requests, recorded{r.Method, r.URL.Path, r.URL.RawQuery, r.Header.Clone(), string(body)})
		n := len(s.requests)
		s.mu.Unlock()
		handler(n, w, r)
	}))
	t.Cleanup(s.Close)
	return s
}

func (s *stub) seen() []recorded {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]recorded(nil), s.requests...)
}

func writeJSON(w http.ResponseWriter, status int, body any, headers ...string) {
	w.Header().Set("Content-Type", "application/json")
	for i := 0; i+1 < len(headers); i += 2 {
		w.Header().Set(headers[i], headers[i+1])
	}
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func newClient(t *testing.T, s *stub, opts ...Option) *Client {
	t.Helper()
	c, err := New(s.URL, opts...)
	if err != nil {
		t.Fatal(err)
	}
	return c
}

func asError(t *testing.T, err error) *Error {
	t.Helper()
	var e *Error
	if !errors.As(err, &e) {
		t.Fatalf("want *chronos.Error, got %T: %v", err, err)
	}
	return e
}

var uuidV4 = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

var booking = generated.ReservationCreate{
	Date:    openapi_types.Date{Time: time.Date(2026, 1, 6, 0, 0, 0, 0, time.UTC)},
	Start:   "14:00",
	End:     "15:00",
	Purpose: "Viva",
}

func TestAPIKeyGoesOutAsXAPIKeyWithTheUserAgent(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) { writeJSON(w, 200, []any{}) })
	c := newClient(t, s, WithAPIKey("k1"))
	if _, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{}); err != nil {
		t.Fatal(err)
	}
	got := s.seen()
	if len(got) != 1 {
		t.Fatalf("want 1 request, got %d", len(got))
	}
	if got[0].Path != "/api/v1/resources/" {
		t.Errorf("path %q", got[0].Path)
	}
	if got[0].Header.Get("X-API-Key") != "k1" {
		t.Errorf("X-API-Key %q", got[0].Header.Get("X-API-Key"))
	}
	if got[0].Header.Get("User-Agent") != "chronos-go/"+Version {
		t.Errorf("User-Agent %q", got[0].Header.Get("User-Agent"))
	}
	if got[0].Header.Get("Authorization") != "" {
		t.Errorf("Authorization %q", got[0].Header.Get("Authorization"))
	}
	if got[0].Header.Get("Idempotency-Key") != "" {
		t.Errorf("a read must not carry an Idempotency-Key")
	}
}

func TestActingForGoesOutAsXChronosActorBesideTheKey(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) { writeJSON(w, 200, []any{}) })
	c := newClient(t, s, WithAPIKey("k1"), WithActingFor("STU001"))
	if _, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{}); err != nil {
		t.Fatal(err)
	}
	got := s.seen()[0]
	if got.Header.Get("X-API-Key") != "k1" {
		t.Errorf("X-API-Key %q", got.Header.Get("X-API-Key"))
	}
	if got.Header.Get("X-Chronos-Actor") != "STU001" {
		t.Errorf("X-Chronos-Actor %q", got.Header.Get("X-Chronos-Actor"))
	}
}

func TestNoActorHeaderWithoutActingFor(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) { writeJSON(w, 200, []any{}) })
	c := newClient(t, s, WithAPIKey("k1"))
	if _, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{}); err != nil {
		t.Fatal(err)
	}
	if got := s.seen()[0].Header.Get("X-Chronos-Actor"); got != "" {
		t.Errorf("X-Chronos-Actor %q", got)
	}
}

func TestActingForNeedsAnAPIKey(t *testing.T) {
	if _, err := New("https://c.test", WithActingFor("STU001")); err == nil {
		t.Error("acting for without an API key must be refused")
	}
	if _, err := New("https://c.test", WithTokens(Tokens{"a", "r"}, nil), WithActingFor("STU001")); err == nil {
		t.Error("acting for with tokens must be refused")
	}
}

func TestBaseURLMayEndInAPIV1(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) { writeJSON(w, 200, []any{}) })
	c, err := New(s.URL+"/api/v1/", WithAPIKey("k"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{}); err != nil {
		t.Fatal(err)
	}
	if got := s.seen()[0].Path; got != "/api/v1/resources/" {
		t.Errorf("path %q", got)
	}
}

func TestNewRefusesABadSetup(t *testing.T) {
	if _, err := New(""); err == nil {
		t.Error("an empty base URL must be refused")
	}
	if _, err := New("https://c.test", WithAPIKey("k"), WithTokens(Tokens{"a", "r"}, nil)); err == nil {
		t.Error("an API key and tokens together must be refused")
	}
}

// The create test from C-5: the first response is lost after the server acted.
func TestCreateReservationSurvivesALostResponseWithOneEffect(t *testing.T) {
	var mu sync.Mutex
	effects := 0
	byKey := map[string]int{}
	var keys []string
	s := newStub(t, func(n int, w http.ResponseWriter, r *http.Request) {
		key := r.Header.Get("Idempotency-Key")
		mu.Lock()
		keys = append(keys, key)
		id, replay := byKey[key]
		if !replay {
			effects++
			id = effects
			byKey[key] = id
		}
		mu.Unlock()
		if n == 1 {
			// The effect happened, but the answer never reaches the caller.
			conn, _, err := w.(http.Hijacker).Hijack()
			if err != nil {
				t.Error(err)
				return
			}
			_ = conn.Close()
			return
		}
		writeJSON(w, 201, map[string]any{"id": id, "resource_id": 3})
	})
	clock := newFakeClock()
	c := newClient(t, s, WithAPIKey("k"), withClock(clock))

	got, err := c.CreateReservation(context.Background(), 3, booking, "")
	if err != nil {
		t.Fatal(err)
	}
	if got.Id == nil || *got.Id != 1 {
		t.Fatalf("want reservation 1, got %+v", got)
	}
	mu.Lock()
	defer mu.Unlock()
	if effects != 1 {
		t.Errorf("want one effect, got %d", effects)
	}
	if len(keys) < 2 {
		t.Fatalf("want a retry, got %d requests", len(keys))
	}
	if !uuidV4.MatchString(keys[0]) {
		t.Errorf("key %q is not a UUIDv4", keys[0])
	}
	for _, k := range keys {
		if k != keys[0] {
			t.Errorf("the key changed between attempts: %q then %q", keys[0], k)
		}
	}
	for _, r := range s.seen() {
		if r.Body == "" {
			t.Error("a retry must send the body again")
		}
	}
}

func TestACallerSuppliedKeyIsKept(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) { writeJSON(w, 201, map[string]any{"id": 1}) })
	c := newClient(t, s, WithAPIKey("k"))
	if _, err := c.CreateReservation(context.Background(), 3, booking, "my-own-key-1"); err != nil {
		t.Fatal(err)
	}
	if got := s.seen()[0].Header.Get("Idempotency-Key"); got != "my-own-key-1" {
		t.Errorf("key %q", got)
	}
}

func TestEveryWriteGetsAKey(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) { writeJSON(w, 201, map[string]any{"id": 1}) })
	c := newClient(t, s, WithAPIKey("k"))
	if _, err := c.ResourcesCreateWithResponse(context.Background(), &generated.ResourcesCreateParams{}, generated.ResourceCreate{}); err != nil {
		t.Fatal(err)
	}
	got := s.seen()[0]
	if got.Method != http.MethodPost {
		t.Fatalf("method %s", got.Method)
	}
	if !uuidV4.MatchString(got.Header.Get("Idempotency-Key")) {
		t.Errorf("key %q is not a UUIDv4", got.Header.Get("Idempotency-Key"))
	}
}

func TestA400Or422IsNeverRetried(t *testing.T) {
	for _, status := range []int{400, 422} {
		t.Run(strconv.Itoa(status), func(t *testing.T) {
			s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
				writeJSON(w, status, map[string]any{"detail": "bad window", "code": "INVALID_VALUE"})
			})
			clock := newFakeClock()
			c := newClient(t, s, WithAPIKey("k"), withClock(clock))
			_, err := c.CreateReservation(context.Background(), 3, booking, "")
			e := asError(t, err)
			if e.Status != status || e.Code != "INVALID_VALUE" || e.Detail != "bad window" {
				t.Errorf("error %+v", e)
			}
			if n := len(s.seen()); n != 1 {
				t.Errorf("want 1 request, got %d", n)
			}
			if len(clock.sleeps()) != 0 {
				t.Errorf("slept %v", clock.sleeps())
			}
		})
	}
}

func TestRetryAfterIsHonouredThenTheCallSucceeds(t *testing.T) {
	s := newStub(t, func(n int, w http.ResponseWriter, _ *http.Request) {
		if n == 1 {
			writeJSON(w, 429, map[string]any{"detail": "slow down", "code": "RATE_LIMITED"}, "Retry-After", "3")
			return
		}
		writeJSON(w, 200, []any{})
	})
	clock := newFakeClock()
	c := newClient(t, s, WithAPIKey("k"), withClock(clock))
	res, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode() != 200 {
		t.Errorf("status %d", res.StatusCode())
	}
	if got := clock.sleeps(); len(got) != 1 || got[0] != 3*time.Second {
		t.Errorf("slept %v, want [3s]", got)
	}
}

func TestBackoffDoublesFromTheBaseUpToTheCap(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 503, map[string]any{"detail": "unavailable"})
	})
	clock := newFakeClock()
	policy := RetryPolicy{MaxAttempts: 7, BaseDelay: 250 * time.Millisecond, MaxDelay: time.Second}
	c := newClient(t, s, WithAPIKey("k"), withClock(clock), WithRetry(policy))
	_, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	if e := asError(t, err); e.Status != 503 {
		t.Errorf("status %d", e.Status)
	}
	want := []time.Duration{250 * time.Millisecond, 500 * time.Millisecond, time.Second, time.Second, time.Second, time.Second}
	got := clock.sleeps()
	if len(got) != len(want) {
		t.Fatalf("slept %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("sleep %d is %v, want %v", i, got[i], want[i])
		}
	}
	if n := len(s.seen()); n != 7 {
		t.Errorf("want 7 requests, got %d", n)
	}
}

func TestFullJitterStaysBetweenZeroAndTheCeiling(t *testing.T) {
	tr := &transport{retry: DefaultRetryPolicy(), jitter: randomUpTo}
	for attempt := 0; attempt < 12; attempt++ {
		ceiling := min(250*time.Millisecond<<attempt, 8*time.Second)
		for i := 0; i < 50; i++ {
			if d := tr.backoff(attempt); d < 0 || d > ceiling {
				t.Fatalf("attempt %d: %v is outside 0 to %v", attempt, d, ceiling)
			}
		}
	}
}

func TestDefaultsAreFourAttemptsAndAThirtySecondDeadline(t *testing.T) {
	p := DefaultRetryPolicy()
	if p.MaxAttempts != 4 || p.BaseDelay != 250*time.Millisecond || p.MaxDelay != 8*time.Second || p.Deadline != 30*time.Second {
		t.Errorf("%+v", p)
	}
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 502, map[string]any{"detail": "bad gateway"})
	})
	c := newClient(t, s, WithAPIKey("k"), withClock(newFakeClock()))
	_, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	asError(t, err)
	if n := len(s.seen()); n != 4 {
		t.Errorf("want 4 attempts, got %d", n)
	}
}

func TestARetryAfterPastTheDeadlineEndsTheCall(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 429, map[string]any{"detail": "slow down"}, "Retry-After", "60")
	})
	clock := newFakeClock()
	c := newClient(t, s, WithAPIKey("k"), withClock(clock))
	_, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	if e := asError(t, err); e.Status != 429 {
		t.Errorf("status %d", e.Status)
	}
	if n := len(s.seen()); n != 1 {
		t.Errorf("want 1 request, got %d", n)
	}
	if len(clock.sleeps()) != 0 {
		t.Errorf("slept %v", clock.sleeps())
	}
}

func TestRetriesCanBeTurnedOff(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 503, map[string]any{"detail": "down"})
	})
	c := newClient(t, s, WithAPIKey("k"), withClock(newFakeClock()), WithoutRetries())
	_, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	asError(t, err)
	if n := len(s.seen()); n != 1 {
		t.Errorf("want 1 request, got %d", n)
	}
}

func TestAWriteWithoutAKeyIsNeverRetried(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 503, map[string]any{"detail": "down"})
	})
	c := newClient(t, s, WithAPIKey("k"), withClock(newFakeClock()), func(c *config) { c.makeKeys = false })
	_, err := c.ResourcesCreateWithResponse(context.Background(), &generated.ResourcesCreateParams{}, generated.ResourceCreate{})
	asError(t, err)
	if n := len(s.seen()); n != 1 {
		t.Errorf("want 1 request, got %d", n)
	}
}

func TestA409KeyInProgressIsRetriedButOtherConflictsAreNot(t *testing.T) {
	s := newStub(t, func(n int, w http.ResponseWriter, _ *http.Request) {
		if n == 1 {
			writeJSON(w, 409, map[string]any{"detail": "still running", "code": "IDEMPOTENCY_KEY_IN_PROGRESS"}, "Retry-After", "1")
			return
		}
		writeJSON(w, 201, map[string]any{"id": 9})
	})
	clock := newFakeClock()
	c := newClient(t, s, WithAPIKey("k"), withClock(clock))
	got, err := c.CreateReservation(context.Background(), 3, booking, "")
	if err != nil {
		t.Fatal(err)
	}
	if got.Id == nil || *got.Id != 9 {
		t.Errorf("reservation %+v", got)
	}
	if s := clock.sleeps(); len(s) != 1 || s[0] != time.Second {
		t.Errorf("slept %v", s)
	}

	busy := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 409, map[string]any{"detail": "taken", "code": "IDEMPOTENCY_KEY_REUSED"})
	})
	_, err = newClient(t, busy, WithAPIKey("k"), withClock(newFakeClock())).CreateReservation(context.Background(), 3, booking, "")
	if e := asError(t, err); e.Code != "IDEMPOTENCY_KEY_REUSED" {
		t.Errorf("code %q", e.Code)
	}
	if n := len(busy.seen()); n != 1 {
		t.Errorf("want 1 request, got %d", n)
	}
}

func TestA409CarriesTheConflictsItNames(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 409, map[string]any{
			"code": "RESERVATION_CONFLICT",
			"detail": map[string]any{
				"message":   "the resource is already taken for part of that window",
				"conflicts": []any{map[string]any{"start": "14:00", "end": "15:00"}},
			},
		})
	})
	c := newClient(t, s, WithAPIKey("k"))
	_, err := c.CreateReservation(context.Background(), 3, booking, "")
	e := asError(t, err)
	if e.Status != 409 || e.Code != "RESERVATION_CONFLICT" {
		t.Errorf("error %+v", e)
	}
	if len(e.Conflicts) != 1 || e.Conflicts[0]["start"] != "14:00" {
		t.Errorf("conflicts %v", e.Conflicts)
	}
	detail, ok := e.Detail.(map[string]any)
	if !ok || detail["message"] == nil {
		t.Errorf("detail %v", e.Detail)
	}
	if want := "chronos: 409: the resource is already taken for part of that window"; e.Error() != want {
		t.Errorf("message %q", e.Error())
	}
	if n := len(s.seen()); n != 1 {
		t.Errorf("a conflict must not be retried, got %d requests", n)
	}
}

func TestErrorParsing(t *testing.T) {
	t.Run("a string detail", func(t *testing.T) {
		e := newError(404, []byte(`{"detail":"Not found.","code":"NOT_FOUND"}`))
		if e.Detail != "Not found." || e.Code != "NOT_FOUND" || len(e.Conflicts) != 0 {
			t.Errorf("%+v", e)
		}
		if e.Error() != "chronos: 404: Not found." {
			t.Errorf("message %q", e.Error())
		}
	})
	t.Run("a list detail", func(t *testing.T) {
		e := newError(422, []byte(`{"detail":[{"loc":["body","date"],"msg":"bad"}],"code":"VALIDATION_FAILED"}`))
		if list, ok := e.Detail.([]any); !ok || len(list) != 1 {
			t.Errorf("detail %v", e.Detail)
		}
		if e.Error() != "chronos: HTTP 422" {
			t.Errorf("message %q", e.Error())
		}
	})
	t.Run("a body that is not JSON is kept as text", func(t *testing.T) {
		e := newError(502, []byte("<html>Bad gateway</html>"))
		if e.Detail != "<html>Bad gateway</html>" || e.Code != "" {
			t.Errorf("%+v", e)
		}
	})
	t.Run("an empty body leaves no detail", func(t *testing.T) {
		e := newError(504, nil)
		if e.Detail != nil || e.Code != "" {
			t.Errorf("%+v", e)
		}
	})
	t.Run("a code newer than this client still arrives", func(t *testing.T) {
		e := newError(400, []byte(`{"detail":"x","code":"SOMETHING_ADDED_LATER"}`))
		if e.Code != "SOMETHING_ADDED_LATER" {
			t.Errorf("code %q", e.Code)
		}
	})
}

func TestRetryAfterReadsSecondsAndHTTPDates(t *testing.T) {
	now := time.Date(2026, 1, 6, 12, 0, 0, 0, time.UTC)
	cases := []struct {
		header string
		want   time.Duration
		ok     bool
	}{
		{"", 0, false},
		{"2", 2 * time.Second, true},
		{"0.5", 500 * time.Millisecond, true},
		{"-4", 0, false},
		{"soon", 0, false},
		{now.Add(10 * time.Second).Format(http.TimeFormat), 10 * time.Second, true},
		{now.Add(-10 * time.Second).Format(http.TimeFormat), 0, true},
	}
	for _, tc := range cases {
		h := http.Header{}
		if tc.header != "" {
			h.Set("Retry-After", tc.header)
		}
		got, ok := retryAfter(h, now)
		if got != tc.want || ok != tc.ok {
			t.Errorf("Retry-After %q: got %v %v, want %v %v", tc.header, got, ok, tc.want, tc.ok)
		}
	}
}

func TestAConnectionThatNeverAnswersIsRetriedForReads(t *testing.T) {
	s := newStub(t, func(n int, w http.ResponseWriter, _ *http.Request) {
		if n < 3 {
			conn, _, _ := w.(http.Hijacker).Hijack()
			_ = conn.Close()
			return
		}
		writeJSON(w, 200, []any{})
	})
	clock := newFakeClock()
	c := newClient(t, s, WithAPIKey("k"), withClock(clock))
	res, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode() != 200 || len(s.seen()) != 3 || len(clock.sleeps()) != 2 {
		t.Errorf("status %d, %d requests, slept %v", res.StatusCode(), len(s.seen()), clock.sleeps())
	}
}

func TestA401RefreshesOnceStoresThePairAndRepeatsTheCall(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v1/auth/refresh" {
			writeJSON(w, 200, map[string]any{"access_token": "a2", "refresh_token": "r2", "token_type": "bearer"})
			return
		}
		if r.Header.Get("Authorization") == "Bearer a2" {
			writeJSON(w, 200, []any{})
			return
		}
		writeJSON(w, 401, map[string]any{"detail": "expired"})
	})
	var stored []Tokens
	c := newClient(t, s, WithTokens(Tokens{"a1", "r1"}, func(t Tokens) { stored = append(stored, t) }))
	res, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode() != 200 {
		t.Errorf("status %d", res.StatusCode())
	}
	if len(stored) != 1 || stored[0] != (Tokens{"a2", "r2"}) {
		t.Errorf("stored %v", stored)
	}
	got := s.seen()
	if len(got) != 3 {
		t.Fatalf("want 3 requests, got %d", len(got))
	}
	var refresh struct {
		RefreshToken string `json:"refresh_token"`
	}
	if err := json.Unmarshal([]byte(got[1].Body), &refresh); err != nil || refresh.RefreshToken != "r1" {
		t.Errorf("refresh body %q", got[1].Body)
	}
}

func TestARefusedRefreshEndsInTheOriginal401(t *testing.T) {
	s := newStub(t, func(_ int, w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, 401, map[string]any{"detail": "Not authorized."})
	})
	c := newClient(t, s, WithTokens(Tokens{"a", "r"}, nil))
	_, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
	e := asError(t, err)
	if e.Status != 401 || e.Detail != "Not authorized." {
		t.Errorf("error %+v", e)
	}
	if n := len(s.seen()); n != 2 {
		t.Errorf("want 2 requests, got %d", n)
	}
}

func TestCallersThatSeeA401TogetherSpendTheRefreshTokenOnce(t *testing.T) {
	var mu sync.Mutex
	refreshes := 0
	s := newStub(t, func(_ int, w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v1/auth/refresh" {
			mu.Lock()
			refreshes++
			mu.Unlock()
			time.Sleep(20 * time.Millisecond)
			writeJSON(w, 200, map[string]any{"access_token": "a2", "refresh_token": "r2"})
			return
		}
		if r.Header.Get("Authorization") == "Bearer a2" {
			writeJSON(w, 200, []any{})
			return
		}
		writeJSON(w, 401, map[string]any{"detail": "expired"})
	})
	c := newClient(t, s, WithTokens(Tokens{"a1", "r1"}, nil))
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			res, err := c.ResourcesListWithResponse(context.Background(), &generated.ResourcesListParams{})
			if err != nil || res.StatusCode() != 200 {
				t.Errorf("status %v, error %v", res, err)
			}
		}()
	}
	wg.Wait()
	mu.Lock()
	defer mu.Unlock()
	if refreshes != 1 {
		t.Errorf("want 1 refresh, got %d", refreshes)
	}
}

func TestPaginateWalksLimitAndOffsetUntilXTotalCount(t *testing.T) {
	ids := []string{"u1", "u2", "u3", "u4", "u5"}
	s := newStub(t, func(_ int, w http.ResponseWriter, r *http.Request) {
		limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
		offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
		end := min(offset+limit, len(ids))
		rows := []map[string]any{}
		for _, id := range ids[offset:end] {
			rows = append(rows, map[string]any{"id": id})
		}
		writeJSON(w, 200, rows, "X-Total-Count", strconv.Itoa(len(ids)))
	})
	c := newClient(t, s, WithAPIKey("k"))
	users := Paginate(context.Background(), 2, func(ctx context.Context, limit, offset int) (Page[generated.UserResponse], error) {
		res, err := c.UsersListWithResponse(ctx, &generated.UsersListParams{Limit: &limit, Offset: &offset})
		if err != nil || res.JSON200 == nil {
			return Page[generated.UserResponse]{}, err
		}
		return Page[generated.UserResponse]{Rows: *res.JSON200, Total: res.Headers200.XTotalCount}, nil
	})
	var got []string
	for user, err := range users {
		if err != nil {
			t.Fatal(err)
		}
		got = append(got, *user.Id)
	}
	if len(got) != 5 || got[0] != "u1" || got[4] != "u5" {
		t.Errorf("rows %v", got)
	}
	queries := []string{}
	for _, r := range s.seen() {
		queries = append(queries, r.Query)
	}
	if len(queries) != 3 || queries[0] != "limit=2&offset=0" || queries[1] != "limit=2&offset=2" || queries[2] != "limit=2&offset=4" {
		t.Errorf("queries %v", queries)
	}
}

func TestPaginateStopsOnAnEmptyPageAndOnAnError(t *testing.T) {
	calls := 0
	empty := Paginate(context.Background(), 10, func(context.Context, int, int) (Page[int], error) {
		calls++
		return Page[int]{}, nil
	})
	for range empty {
		t.Fatal("no rows expected")
	}
	if calls != 1 {
		t.Errorf("want 1 call, got %d", calls)
	}

	boom := errors.New("boom")
	failing := Paginate(context.Background(), 10, func(context.Context, int, int) (Page[int], error) {
		return Page[int]{}, boom
	})
	n := 0
	for _, err := range failing {
		n++
		if !errors.Is(err, boom) {
			t.Errorf("error %v", err)
		}
	}
	if n != 1 {
		t.Errorf("want the error once, got %d", n)
	}

	total := 100
	early := Paginate(context.Background(), 2, func(_ context.Context, limit, offset int) (Page[int], error) {
		return Page[int]{Rows: []int{offset, offset + 1}, Total: &total}, nil
	})
	seen := 0
	for range early {
		seen++
		if seen == 3 {
			break
		}
	}
	if seen != 3 {
		t.Errorf("seen %d", seen)
	}
}
