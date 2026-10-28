# Cindercrest 2.0 Security Specification

## 1. Threat Model & Security Boundaries

Cindercrest operates as an autonomous executive agent on a personal Windows 11 machine. Its attack surfaces and protective boundaries are:

1. **Localhost Network Isolation:**
   * Backend binds strictly to `127.0.0.1`.
   * Cross-Origin Resource Sharing (CORS) whitelist is restricted to `http://localhost:5173` (Vite dev) and `http://127.0.0.1:8000`.
   * All non-health endpoints require the per-launch cryptographic Bearer token.
2. **Untrusted Data Isolation:**
   * Transcripts, file contents, web content, and tool outputs are treated as **data, never instructions**.
   * Spoken user input cannot modify system permissions or bypass policy rules.
3. **Secret Redaction:**
   * Centralized logging filter scrubs Bearer tokens, passwords, and API key patterns before writing to disk or terminal.
   * Real keys are loaded from system environment variables only; `.env` is ignored by Git.
4. **Default-DENY Policy Engine:**
   * Any action attempting external side effects (file mutation, shell execution, network requests) is denied by default.
   * In Phase 0 and Phase 1, the tool registry is completely disabled.
5. **Privacy Mode:**
   * Disables microphone audio recording stream and purges audio buffers immediately upon activation.
