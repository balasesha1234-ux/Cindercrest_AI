# Architecture Decision Records (ADRs)

This document records key architectural decisions, rationale, trade-offs, and alternatives for Cindercrest 2.0.

---

## ADR-001: Python Modular Monolith with Localhost Binding

* **Status:** PROPOSED
* **Context:** Cindercrest is a personal AI operator designed for one user on a Windows 11 machine. Distributed microservices introduce deployment complexity, port conflict, serialization overhead, and attack surface.
* **Decision:** Build Cindercrest as a Python modular monolith running on FastAPI and Uvicorn, strictly bound to `127.0.0.1`. The application consists of explicit modules: `api`, `core`, `voice`, `orchestrator`, `model`, `policy`, and `store`.
* **Consequences:** Simple single-process lifecycle, zero external network listener vulnerability, sub-millisecond in-process communication. External network binding is prohibited.

---

## ADR-002: Voice-First Interaction Priority

* **Status:** PROPOSED
* **Context:** Previous iterations accumulated desktop tools, file operators, and email clients before having a reliable voice loop, leading to mock voice fallbacks.
* **Decision:** The foundational product spine is a natural voice conversation loop (Microphone $\rightarrow$ VAD $\rightarrow$ STT $\rightarrow$ Conversational Engine $\rightarrow$ TTS $\rightarrow$ Speaker, with instant barge-in interruption). Tools and computer control are strictly out of scope until the voice loop is proven.
* **Consequences:** Ensures the core product promise (natural voice assistant) is real, responsive, and verifiable before complex external side effects are introduced.

---

## ADR-003: Local-First Speech Synthesis via Windows OneCore

* **Status:** PROPOSED
* **Context:** Neural cloud TTS APIs incur per-character costs, introduce network latency (200–800ms), and require internet access. Heavy local PyTorch TTS models (XTTS, Bark) consume 2–4 GB of VRAM.
* **Decision:** Utilize Windows 11 native OneCore / SAPI speech synthesis (*Microsoft Heera*, *Microsoft Zira*, *Microsoft David*) via direct WinRT / COM bindings as the default voice synthesizer.
* **Consequences:** Zero VRAM usage, zero cloud cost, zero latency to first audio chunk, works 100% offline. Higher-tier neural TTS (e.g. Kokoro / Piper) can be plugged in later as an optional add-on.

---

## ADR-004: Local Speech-to-Text via Faster-Whisper (CUDA)

* **Status:** PROPOSED
* **Context:** Speech transcription requires high accuracy, robustness against background noise, and low latency. Sending continuous audio streams to cloud providers leaks privacy and incurs bandwidth/API costs.
* **Decision:** Deploy `faster-whisper` (`base.en` / `small.en`) using CTranslate2 CUDA acceleration on the NVIDIA RTX 5050 Laptop GPU.
* **Consequences:** Transcriptions complete in 150–300ms locally, consuming $<500$ MB of VRAM. Audio never leaves the machine.

---

## ADR-005: Deterministic Secret Redaction in Structured Logging

* **Status:** PROPOSED
* **Context:** API keys, tokens, session IDs, and authorization headers must never be leaked into log files, consoles, or event streams (`AGENTS.md` Rule 7).
* **Decision:** Implement a centralized logging filter that inspects every log message and structured record against regex patterns matching Bearer tokens, API keys (`sk-...`, `AIza...`), passwords, and session tokens, replacing matches with `[REDACTED]`.
* **Consequences:** Guarantees that even if an exception or debug payload prints raw headers, secrets are scrubbed before reaching disk or stdout.

---

## ADR-006: Ephemeral Per-Launch Token Authentication

* **Status:** PROPOSED
* **Context:** While the backend binds to `127.0.0.1`, any process on the local machine could potentially connect to an unauthenticated HTTP port.
* **Decision:** At startup, the backend generates a cryptographically secure 32-byte hex token (or reads a pre-configured `CINDERCREST_SESSION_TOKEN`). All API endpoints (except `/health`) require `Authorization: Bearer <token>`.
* **Consequences:** Prevents unauthorized local processes or browser tabs from making requests to Cindercrest endpoints.

---

## ADR-007: SQLite with Write-Ahead Logging (WAL) and Honest State Machine

* **Status:** PROPOSED
* **Context:** The system needs persistent storage for conversation history, turn events, and session states without the operational overhead of Postgres or Redis.
* **Decision:** Use SQLite with WAL mode (`PRAGMA journal_mode=WAL`) and `PRAGMA synchronous=NORMAL`. State transitions follow an honest state machine with a separate `outcome` field (`success`, `failure`, `unknown`). On startup, any task found in `running` or `verifying` is moved to `unknown`.
* **Consequences:** Fast concurrent reads, transactional integrity, crash recovery, zero mock states.

---

## ADR-008: Read-Only Filesystem Sandboxing and Document Tool Intelligence

* **Status:** PROPOSED
* **Context:** An autonomous agent with arbitrary file access risks unauthorized inspection, data leakage, path traversal, symlink escapes, and exposing local environment secrets or credentials (`AGENTS.md` Hard Rules 4, 5, 6, 7).
* **Decision:** Implement a deterministic `FilesystemGuard` enforcing: (1) strict canonical path resolution; (2) whitelist containment verification against configured `approved_directories` (default `docs/`); (3) allowed read extensions whitelist (`.txt`, `.md`, `.json`, `.csv`, `.log`, `.py`, `.yaml`, `.yml`, `.toml`, `.rst`); (4) file size limit (500 KB max); (5) character truncation bounds (default 20,000, hard max 100,000). All filesystem tools (`fs.search`, `fs.read_text`) are registered under `ToolSafetyTier.READ` and governed by default-DENY policy evaluation.
* **Consequences:** Zero direct or unvalidated file access; complete immunity to path traversal (`../../`) and symlink attacks; sensitive files and arbitrary OS locations remain unreachable. Tool output is treated purely as data.

---

## ADR-009: Controlled Memory with Provenance, Corrections, and Privacy Mode

* **Status:** PROPOSED
* **Context:** Long-term AI operators require persistent episodic and semantic context (user preferences, explicit facts, project states). Uncontrolled memory architectures risk hallucinated memories, uncorrected stale facts, indefinite retention of transient sensor states, or data leakage when Privacy Mode is enabled (`AGENTS.md` Hard Rules 1, 4, 6, 7).
* **Decision:** Implement a deterministic `MemoryStore` on SQLite (`memories` table) storing typed `MemoryItem` records with: (1) explicit classification (`explicit_fact`, `preference`, `project_state`, `inference`, `temporary_observation`, `conversation_context`); (2) mandatory provenance tracking; (3) confidence scoring; (4) deterministic conflict resolution and correction chains (`status='corrected'`, `superseded_by=<id>`); (5) TTL expiration with `purge_expired()`; (6) Privacy Mode enforcement in plain code (blocking writes and zeroing prompt context); (7) deterministic secret redaction on keys and content before database writes.
* **Consequences:** Honest, auditable, and user-correctable memory graph. Zero secret leakage and zero context leakage in Privacy Mode.

---

## ADR-010: Groq Model Provider Migration for Ultra-Fast Conversational Inference

* **Status:** ACCEPTED
* **Context:** The system required a high-speed cloud model fallback when local Ollama is offline or when the user requires sub-second conversational latency. Gemini API was previously evaluated, but replaced with Groq to leverage native LPU speed and OpenAI-compatible SSE streaming without introducing heavy SDK dependencies.
* **Decision:** Replace `GeminiProvider` with `GroqProvider` in `backend/app/model/groq.py` utilizing the OpenAI-compatible endpoint (`https://api.groq.com/openai/v1/chat/completions`) with `qwen/qwen3.8-27b` (aligning with Cindercrest's local Qwen family) over existing async `httpx`. Groq keys (`gsk_...`) are strictly loaded via `.env` (gitignored), hardcoded secrets are forbidden (`AGENTS.md` Rule 7), and regex-based redaction (`[REDACTED_GROQ_KEY]`) is applied to all log records and database writes.
* **Consequences:** Sub-300ms time-to-first-token (TTFT) and >500 tok/sec generation; zero new package dependencies added; complete secret isolation.
