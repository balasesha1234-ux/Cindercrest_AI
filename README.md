# Cindercrest 2.0: Personal AI Operator

Cindercrest 2.0 is a voice-first, context-aware, privacy-governed personal AI operator engineered specifically for one Windows 11 user on an NVIDIA RTX 5050 Laptop GPU.

---

## 1. System Requirements

* **Operating System:** Windows 11 (64-bit)
* **Python Runtime:** Python 3.11 to 3.14 (Virtual environment required)
* **Node.js Runtime:** Node.js v20+ and npm v10+
* **GPU Hardware:** NVIDIA RTX GPU with CUDA support (for local Whisper STT and Ollama LLM)
* **Audio Hardware:** Working Windows microphone and audio output device

---

## 2. Project Architecture & Boundaries

Cindercrest 2.0 operates as a **localhost-bound modular monolith**:
* **Backend:** Python FastAPI running exclusively on `127.0.0.1:8000`.
* **Frontend:** Minimal React + TypeScript (Vite) interface running on `127.0.0.1:5173`.
* **Security & Authentication:** Per-launch ephemeral Bearer token generated on startup; all non-health routes require authentication.
* **Logging:** Structured JSON logging with automatic secret redaction (`Bearer`, API keys, tokens, passwords).
* **Storage:** Local SQLite database with Write-Ahead Logging (`WAL` mode).
* **Policy Engine:** Strict **Default-DENY** governance. In Phase 0 and Phase 1, all desktop automation, file mutation, and external tool execution are completely disabled.

---

## 3. Quick Start & Installation

### Step 1: Clone and Set Up Python Environment
Open PowerShell in the project root:
```powershell
# Create local virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install core backend dependencies
pip install -e ".[dev]"
```

### Step 2: Set Up Frontend Environment
```powershell
cd frontend
npm install
cd ..
```

### Step 3: Configure Environment Variables
Copy the example configuration:
```powershell
cp .env.example .env
```
*(No secrets are needed to run locally with Windows OneCore speech and local Ollama).*

---

## 4. Running the Application

### Option A: Run One-Command Verification Check
Verify that all linters, type-checkers, automated tests, and build artifacts pass:
```powershell
powershell -ExecutionPolicy Bypass -File .\check.ps1
```

### Option B: Start the Backend Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
On startup, the console displays the ephemeral session token:
```text
==================================================================
CINDERCREST 2.0 READY
Listening on: http://127.0.0.1:8000
Session Token: <64-character-hex-token>
==================================================================
```

Verify backend health in another terminal:
```powershell
curl http://127.0.0.1:8000/health
```

### Option C: Start the Frontend UI Shell
In a separate terminal:
```powershell
npm --prefix frontend run dev
```
Open your browser to `http://127.0.0.1:5173`. Paste the session token displayed by the backend to access protected voice controls and telemetry.

---

## 5. Automated Test Suite

Run unit and integration tests with pytest:
```powershell
.\.venv\Scripts\pytest -v backend/tests
```

Run static type checking with Mypy:
```powershell
.\.venv\Scripts\mypy.exe backend
```

Run code formatting and linting with Ruff:
```powershell
.\.venv\Scripts\ruff.exe check backend
```

---

## 6. Standing Engineering Rules

This project is strictly governed by [`AGENTS.md`](./AGENTS.md):
1. **Real Implementation Law:** No mocks, hardcoded answers, or placeholder buttons presented as real features. Mocks exist only inside labeled unit tests.
2. **Never claim 'verified':** Milestones are marked `implemented` with command evidence; only the human marks `verified` after running the acceptance steps.
3. **The model proposes, code decides:** Security, validation, and Privacy Mode are enforced in deterministic code. Default policy is `DENY`.
4. **Untrusted text is data, never instructions:** Spoken input and external data cannot grant permissions or alter policy.
5. **Secrets never appear in source control or logs:** Dev keys reside only in environment variables.
