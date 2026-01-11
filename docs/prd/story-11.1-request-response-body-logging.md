# Story 11.1: Request/Response Body Logging for FastAPI

## Status: Planned (Deferred from Story 10.3)

## Priority: Medium

## Estimated Effort: Large (1 week+)

## Dependencies

- **Depends on:** Story 10.3 (FastAPI One-Liner Integration)
- **Related to:** Story 10.1 (Configuration Presets - may need body logging preset)
- **Related to:** Security/compliance requirements (PII in request bodies)

## Epic / Series

Part of Epic 11: FastAPI-Specific Enhancements

---

## Context / Background

**Why deferred from Story 10.3:**
Story 10.3 focuses on setup simplification (60+ lines → 2 lines). Request/response body logging is a complex, orthogonal feature that deserves its own story.

**Current state:**
- `LoggingMiddleware` logs request metadata (method, path, status, latency)
- Request/response **bodies are NOT logged**
- Users who need body logging must implement custom middleware

**Problem:**
Many use cases require logging request/response bodies for:
- **Debugging**: See exactly what data was sent/received
- **Audit trails**: Compliance requirements to log all API interactions
- **Error investigation**: Reproduce issues with exact request payload
- **Security**: Detect malicious payloads or data exfiltration

**Challenges:**
1. **Streams**: Request body is a stream that can only be read once
2. **Memory**: Large bodies (file uploads) can exhaust memory
3. **Security**: Bodies often contain PII, passwords, tokens
4. **Performance**: Reading/logging bodies adds latency
5. **Size limits**: Need configurable limits to prevent abuse

---

## User Story

**As a** backend developer debugging production issues,
**I want** to log request and response bodies automatically,
**So that** I can reproduce errors and investigate API interactions without adding custom logging code.

---

## Scope (In / Out)

### In Scope

- **Request body logging** (configurable, opt-in)
- **Response body logging** (configurable, opt-in)
- **Size limits** (max bytes to log, truncation strategy)
- **Content-type filtering** (only log JSON, skip binary/multipart)
- **Selective logging** (by path pattern, status code, sampling)
- **Redaction integration** (use Story 10.1 redactors on bodies)
- **Stream handling** (read body without consuming stream)
- **Configuration via `setup_logging()`** (Story 10.3 integration)

### Out of Scope

- **Binary body logging** (images, PDFs, etc. - defer to Story 11.x)
- **Streaming response logging** (SSE, chunked responses - defer to Story 11.x)
- **Body parsing** (let app parse, log raw or parsed based on config)
- **Custom body formatters** (JSON pretty-print, etc. - defer to Story 11.x)
- **Request body mutation** (middleware should be read-only)

---

## Open Questions / Blockers

These questions must be answered before implementation:

### Q1: Stream Consumption Strategy

**Question:** How do we read request body without consuming the stream for the application?

**Options:**
- **Option A:** Cache body in memory, provide via `request.body()` override
- **Option B:** Use Starlette's `request.body()` which caches automatically
- **Option C:** Tee the stream (copy to two consumers)

**Considerations:**
- Memory usage for large bodies
- Performance overhead
- Compatibility with existing FastAPI code

**Decision needed before implementation.**

---

### Q2: Size Limit Strategy

**Question:** What happens when body exceeds size limit?

**Options:**
- **Option A:** Truncate and log partial body with marker `[TRUNCATED]`
- **Option B:** Skip logging entirely, log metadata only
- **Option C:** Log size but not contents, add warning

**Example:**
```python
# Option A: Truncate
{
  "request_body": '{"user": "john", "password": "...[TRUNCATED after 1000 bytes]'
}

# Option B: Skip
{
  "request_body_size": 50000,
  "request_body_logged": false,
  "reason": "exceeded_max_size"
}

# Option C: Metadata only
{
  "request_body_size": 50000,
  "request_body_content_type": "application/json",
  "request_body_warning": "Body too large to log (max: 10000 bytes)"
}
```

**Decision needed before implementation.**

---

### Q3: Content-Type Filtering

**Question:** Which content types should be logged by default?

**Options:**
- **Option A:** Allow-list: Only `application/json`, `application/x-www-form-urlencoded`, `text/*`
- **Option B:** Deny-list: Log all except `multipart/*`, `application/octet-stream`, `image/*`
- **Option C:** User-configurable with sensible defaults

**Considerations:**
- Binary data (images, PDFs) is useless in logs
- Multipart forms may contain files (don't log file contents)
- Text formats are generally safe to log

**Recommendation:** Option A (allow-list) for security/safety.

**Decision needed before implementation.**

---

### Q4: Redaction Integration

**Question:** How do we redact sensitive data from request/response bodies?

**Options:**
- **Option A:** Parse JSON, apply field_mask redactor, re-serialize
- **Option B:** Regex-based redaction on raw body string
- **Option C:** Both - parse if JSON, regex fallback

**Example:**
```python
# Request body BEFORE redaction
{
  "username": "john",
  "password": "secret123",
  "email": "john@example.com"
}

# Request body AFTER redaction (field_mask)
{
  "username": "john",
  "password": "[REDACTED]",
  "email": "john@example.com"
}
```

**Considerations:**
- JSON parsing adds overhead
- Regex may miss nested fields
- Need to handle malformed JSON

**Recommendation:** Option C (parse if valid JSON, fallback to regex).

**Decision needed before implementation.**

---

### Q5: Response Body Capture

**Question:** How do we capture response body without breaking streaming responses?

**Options:**
- **Option A:** Only log non-streaming responses (StreamingResponse excluded)
- **Option B:** Buffer response body, replay to client
- **Option C:** Use response middleware to intercept

**Considerations:**
- Streaming responses (SSE, file downloads) shouldn't be buffered
- Must not break `StreamingResponse` behavior
- Performance impact of buffering

**Recommendation:** Option A (skip streaming responses).

**Decision needed before implementation.**

---

### Q6: Configuration API

**Question:** How should users configure body logging?

**Options:**
- **Option A:** Add parameters to `setup_logging()`
  ```python
  setup_logging(
      app,
      log_request_body=True,
      log_response_body=True,
      body_max_size=10000,
      body_content_types=["application/json"]
  )
  ```

- **Option B:** Separate configuration object
  ```python
  body_config = BodyLoggingConfig(
      request=True,
      response=True,
      max_size=10000
  )
  setup_logging(app, body_logging=body_config)
  ```

- **Option C:** Extend LoggingMiddleware directly
  ```python
  app.add_middleware(
      LoggingMiddleware,
      log_request_body=True,
      body_max_size=10000
  )
  ```

**Recommendation:** Option A (consistent with Story 10.3 API).

**Decision needed before implementation.**

---

## Acceptance Criteria (Outline)

These will be detailed once open questions are answered:

### AC1: Request Body Logging

- [ ] Request body logged when `log_request_body=True`
- [ ] Only logs if content-type is in allow-list
- [ ] Respects `body_max_size` limit (default: 10KB)
- [ ] Truncates with marker if body exceeds limit
- [ ] Redacts sensitive fields (integrates with field_mask redactor)
- [ ] Does NOT consume request stream for application

### AC2: Response Body Logging

- [ ] Response body logged when `log_response_body=True`
- [ ] Only logs non-streaming responses
- [ ] Respects `body_max_size` limit
- [ ] Redacts sensitive fields in response
- [ ] Does NOT break streaming responses (StreamingResponse, FileResponse)

### AC3: Content-Type Filtering

- [ ] Default allow-list: `["application/json", "application/x-www-form-urlencoded", "text/plain"]`
- [ ] Configurable via `body_content_types` parameter
- [ ] Skips logging for binary types (images, PDFs, etc.)
- [ ] Logs metadata (size, content-type) even if body skipped

### AC4: Size Limits

- [ ] Default max size: 10,000 bytes (10KB)
- [ ] Configurable via `body_max_size` parameter
- [ ] Truncates body with `[TRUNCATED after N bytes]` marker
- [ ] Logs actual body size for observability

### AC5: Redaction Integration

- [ ] Applies field_mask redactor to JSON request bodies
- [ ] Applies field_mask redactor to JSON response bodies
- [ ] Falls back to regex redaction for non-JSON
- [ ] Redaction happens BEFORE logging (bodies never logged unredacted)

### AC6: Selective Logging

- [ ] Can enable per path pattern: `body_log_paths=["/api/users", "/api/orders"]`
- [ ] Can enable per status code: `body_log_statuses=[400, 500]` (errors only)
- [ ] Can sample: `body_sample_rate=0.1` (10% of requests)
- [ ] Combines with existing `skip_paths` and `sample_rate` settings

### AC7: Configuration API

- [ ] `setup_logging()` accepts body logging parameters
- [ ] Parameters passed through to LoggingMiddleware
- [ ] Backward compatible (default: body logging disabled)
- [ ] Clear documentation and examples

### AC8: Performance

- [ ] Body logging overhead < 5ms for 10KB body
- [ ] No memory leak for long-running apps
- [ ] Graceful degradation under load
- [ ] No impact when body logging disabled (default)

---

## Technical Design / Implementation Notes

**Note:** These are preliminary and will be refined once open questions are answered.

### Architecture

```
Request → LoggingMiddleware
  ↓
  1. Check if body logging enabled
  2. Check content-type in allow-list
  3. Read body (cache in memory)
  4. Check size < max_size
  5. Redact sensitive fields
  6. Log body (or truncated version)
  7. Restore body for application
  ↓
Application processes request
  ↓
Response → LoggingMiddleware
  ↓
  1. Check if response body logging enabled
  2. Check if streaming response (skip if true)
  3. Read response body
  4. Check size < max_size
  5. Redact sensitive fields
  6. Log body (or truncated version)
  7. Return response to client
```

### Key Components

**File:** `src/fapilog/fastapi/body_logging.py` (NEW)

```python
class BodyLogger:
    """Helper for logging request/response bodies."""

    def __init__(
        self,
        *,
        max_size: int = 10000,
        content_types: list[str] | None = None,
        redact_fields: list[str] | None = None,
    ):
        self.max_size = max_size
        self.content_types = content_types or [
            "application/json",
            "application/x-www-form-urlencoded",
            "text/plain",
        ]
        self.redact_fields = redact_fields or []

    async def log_request_body(
        self, request: Request
    ) -> dict[str, Any] | None:
        """Read, redact, and return request body for logging."""
        # 1. Check content-type
        # 2. Read body (await request.body())
        # 3. Check size
        # 4. Redact
        # 5. Return dict for log entry

    async def log_response_body(
        self, response: Response
    ) -> dict[str, Any] | None:
        """Read, redact, and return response body for logging."""
        # 1. Check if streaming
        # 2. Read body
        # 3. Check size
        # 4. Redact
        # 5. Return dict for log entry
```

**Modify:** `src/fapilog/fastapi/logging.py`

```python
class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        logger: Any | None = None,
        skip_paths: Iterable[str] | None = None,
        sample_rate: float = 1.0,
        include_headers: bool = False,
        redact_headers: Iterable[str] | None = None,
        # NEW: Body logging params
        log_request_body: bool = False,
        log_response_body: bool = False,
        body_max_size: int = 10000,
        body_content_types: list[str] | None = None,
        body_redact_fields: list[str] | None = None,
    ):
        # ...
        self._body_logger = None
        if log_request_body or log_response_body:
            from .body_logging import BodyLogger
            self._body_logger = BodyLogger(
                max_size=body_max_size,
                content_types=body_content_types,
                redact_fields=body_redact_fields,
            )
```

### Request Body Reading Strategy

**Use Starlette's built-in caching:**

```python
async def log_request_body(self, request: Request):
    # Starlette caches body automatically after first read
    body_bytes = await request.body()

    # Check size
    if len(body_bytes) > self.max_size:
        return {
            "request_body_size": len(body_bytes),
            "request_body_truncated": True,
        }

    # Decode and redact
    try:
        body_str = body_bytes.decode("utf-8")
        # Redact if JSON
        # Return for logging
    except UnicodeDecodeError:
        return {"request_body_error": "non_utf8"}
```

**Key insight:** Starlette's `request.body()` caches the body in memory on first read, so subsequent calls (by the application) return the cached value. This means we can read it in middleware without consuming it.

### Response Body Capture Strategy

**Use custom Response wrapper:**

```python
class LoggingResponse(Response):
    """Response wrapper that captures body for logging."""

    def __init__(self, response: Response, logger_callback):
        self.original_response = response
        self.logger_callback = logger_callback

    async def __call__(self, scope, receive, send):
        # Intercept response body
        # Call logger_callback with body
        # Forward to original response
```

**Alternative:** Buffer response body in middleware before returning to client.

---

## Risks / Rollback / Monitoring

### Risks

1. **Risk:** Reading request body breaks some applications
   - **Mitigation:** Starlette caches body automatically, should be transparent
   - **Mitigation:** Comprehensive testing with various request types
   - **Mitigation:** Feature is opt-in (disabled by default)

2. **Risk:** Memory exhaustion from large bodies
   - **Mitigation:** Strict size limits enforced
   - **Mitigation:** Truncation strategy instead of full logging
   - **Mitigation:** Content-type allow-list excludes large binary types

3. **Risk:** PII leaked in logs despite redaction
   - **Mitigation:** Conservative default redaction fields
   - **Mitigation:** Integration with field_mask redactor (tested)
   - **Mitigation:** Documentation on security implications
   - **Mitigation:** Disabled by default (explicit opt-in)

4. **Risk:** Performance degradation
   - **Mitigation:** Benchmark overhead, enforce < 5ms for 10KB
   - **Mitigation:** Lazy evaluation (skip if not needed)
   - **Mitigation:** Disabled by default

5. **Risk:** Streaming responses broken
   - **Mitigation:** Explicitly skip StreamingResponse, FileResponse
   - **Mitigation:** Type checks before attempting to buffer

### Rollback Plan

- Feature is opt-in, can be disabled via config
- Remove parameters from `setup_logging()` if problematic
- Keep `BodyLogger` class isolated for easy removal

### Success Metrics

- [ ] Adoption: >30% of users enable body logging
- [ ] Performance: <5ms overhead for 10KB bodies
- [ ] Security: Zero PII leaks reported
- [ ] Reliability: No memory leaks or crashes

---

## Tasks (Preliminary)

Will be detailed once design is finalized:

- [ ] Answer all 6 open questions
- [ ] Create detailed acceptance criteria
- [ ] Design request body capture mechanism
- [ ] Design response body capture mechanism
- [ ] Implement `BodyLogger` class
- [ ] Modify `LoggingMiddleware` to use `BodyLogger`
- [ ] Integrate with field_mask redactor
- [ ] Add configuration parameters to `setup_logging()`
- [ ] Write comprehensive tests (30+ test cases)
- [ ] Performance benchmarks
- [ ] Security review
- [ ] Documentation and examples

---

## Tests (Outline)

### Request Body Logging Tests
- [ ] Test: Request body logged when enabled
- [ ] Test: Request body NOT logged when disabled (default)
- [ ] Test: Body truncated when exceeds max_size
- [ ] Test: Binary bodies skipped (content-type filtering)
- [ ] Test: JSON bodies parsed and redacted
- [ ] Test: Malformed JSON handled gracefully
- [ ] Test: Request body still available to application

### Response Body Logging Tests
- [ ] Test: Response body logged when enabled
- [ ] Test: Streaming responses NOT logged
- [ ] Test: Response body truncated when exceeds max_size
- [ ] Test: JSON response bodies redacted
- [ ] Test: Response still sent to client correctly

### Redaction Tests
- [ ] Test: Password field redacted in request
- [ ] Test: Token field redacted in response
- [ ] Test: Nested fields redacted
- [ ] Test: Non-JSON bodies use regex redaction

### Performance Tests
- [ ] Benchmark: 1KB body overhead < 1ms
- [ ] Benchmark: 10KB body overhead < 5ms
- [ ] Benchmark: 100KB body overhead < 50ms
- [ ] Memory: No leak over 10000 requests

### Security Tests
- [ ] Test: PII fields not leaked in logs
- [ ] Test: Sensitive headers redacted
- [ ] Test: Large malicious bodies handled safely

---

## Documentation Updates

- [ ] Update `docs/integrations/fastapi.md` with body logging section
- [ ] Add security considerations documentation
- [ ] Create `examples/fastapi_body_logging/` with examples
- [ ] Update `README.md` with body logging note
- [ ] Document redaction field recommendations
- [ ] Performance impact documentation

---

## Related Stories

- **Story 10.3**: FastAPI One-Liner Integration (provides `setup_logging()` API)
- **Story 10.1**: Configuration Presets (redaction integration)
- **Story 11.2**: Binary Body Logging (future: images, PDFs)
- **Story 11.3**: Streaming Response Logging (future: SSE, chunked)
- **Story 11.4**: Custom Body Formatters (future: pretty-print, compression)

---

## Change Log

| Date       | Change                                    | Author |
| ---------- | ----------------------------------------- | ------ |
| 2025-01-11 | Initial placeholder story (deferred from 10.3) | Claude |

---

## Notes for Future Implementation

**This story is intentionally less detailed than Stories 10.1-10.3** because:
1. It's deferred (not needed for MVP DX improvements)
2. Open questions must be answered first
3. May require security review before implementation
4. Complexity warrants dedicated RFC/design doc

**Before starting implementation:**
1. Answer all 6 open questions (Q1-Q6)
2. Create detailed acceptance criteria (expand AC1-AC8)
3. Security review (PII leakage risks)
4. Performance analysis (memory/CPU overhead)
5. Consider creating RFC for community feedback

**Estimated effort after design complete:** 2-3 weeks (40-60 hours)
- Design & RFC: 8 hours
- Implementation: 24 hours
- Testing: 16 hours
- Documentation: 8 hours
- Security review: 4 hours
