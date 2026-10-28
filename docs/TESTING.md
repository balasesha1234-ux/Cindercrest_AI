# Cindercrest 2.0 Testing Specification

## 1. Testing Philosophy
* **Tests Before Code (TDD):** Logic, state transitions, security boundaries, and error handlers are tested with automated tests before implementation.
* **Real Implementation Law:** Mocks are permitted **only** inside tests and must be explicitly labeled (e.g. `mock_audio_stream`). Production runtime never executes mock fallbacks.
* **Honest Outcomes:** Tests assert the exact behavior and error payload contracts.

## 2. Test Suites
1. **Security & Authentication Tests:**
   * Rejection of requests lacking the Bearer token.
   * Rejection of invalid tokens with HTTP 401.
   * Acceptance of valid tokens.
   * Public accessibility of `/health` without token.
2. **Secret Redaction Tests:**
   * Structured logs mask `sk-...`, `Bearer ...`, and password fields with `[REDACTED]`.
3. **Configuration & Validation Tests:**
   * Invalid ports or bad host formats fail validation.
   * Environment variable parsing and default settings.
4. **Health Probe Tests:**
   * Verification of `/health` schema, database connectivity, and diagnostic indicators.
5. **State Machine Tests:**
   * Transitions between `IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, and `INTERRUPTED`.
   * Rejection of illegal state transitions.

## 3. Execution Commands
To run the one-command verification check:
```powershell
powershell -ExecutionPolicy Bypass -File .\check.ps1
```

To run individual pytest suites:
```powershell
.\.venv\Scripts\pytest -v backend/tests
```
