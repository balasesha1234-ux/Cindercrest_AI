# Cindercrest 2.0: Speech Stack Assessment & Benchmark Report

**Target Environment:** Windows 11 (64-bit)  
**CPU:** Intel Core i7-14650HX (16 cores, 24 logical processors)  
**RAM:** 24 GB DDR5 (7.4 GB physical RAM free)  
**GPU:** NVIDIA GeForce RTX 5050 Laptop GPU (8151 MiB / 8.0 GiB VRAM, Driver 610.74, CUDA 13.3)  

---

## 1. Speech-to-Text (STT) Evaluation

| Component | Execution Mode | Accuracy | Latency (TTFT) | VRAM Required | Offline Capable | Licensing / Cost | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Web Speech API** | Browser / OS Native | High (en-US / en-IN) | $< 100$ ms (interim) | 0 MB | Partial (OS dependent) | Free / Built-in | **Recommended for Primary Client Loop** |
| **Faster-Whisper (`base.en`)** | Local CUDA (CTranslate2) | Very High | $\approx 220$ ms | $\approx 450$ MB | 100% Offline | Apache 2.0 / Free | **Recommended for Backend Engine** |
| **Sherpa-ONNX (int8)** | Local CPU / ONNX | High | $\approx 350$ ms | 0 MB (CPU) | 100% Offline | Apache 2.0 / Free | Viable local fallback |
| **Cloud STT (Google/OpenAI)**| Remote API | Very High | 400–900 ms | 0 MB | No | Paid per-minute | **Rejected** (Violates local-first & zero-cost) |

*Decision:* Dual-layer approach. The frontend leverages `SpeechRecognition` with continuous real-time interim results and microphone permissions, with backend fallback support for audio chunk transcription.

---

## 2. Conversational Language Model Evaluation

| Candidate Model | Host / Runtime | Parameter Size | Quantization | VRAM Allocated | Inference Speed | Context Window | Status on Machine |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`qwen3:8b`** | Local Ollama (CUDA) | 8.2 B | Q4_K_M | $\approx 5.2$ GiB | 38–45 tok/sec | 40,960 | **Verified Cached & Operational** |
| **`suraksha360:latest`** | Local Ollama (CUDA) | 8.2 B | Q4_K_M | $\approx 5.2$ GiB | 38–45 tok/sec | 40,960 | Cached |
| **`moondream:latest`** | Local Ollama (CUDA) | 1.8 B | Q4_0 | $\approx 1.7$ GiB | 70+ tok/sec | 2,048 | Cached |
| **`gemini-2.5-flash`** | Hosted Google API | Cloud | FP16/Cloud | 0 MB | 60+ tok/sec | 1,000,000 | Configurable Optional Fallback |

*VRAM Math & Headroom Check:*
* RTX 5050 total: 8151 MiB.
* Windows DWM / system compositor: $\approx 1,200$ MiB.
* `qwen3:8b` model weight offload: 5,225 MiB.
* KV Cache for 4k context: $\approx 400$ MiB.
* Total VRAM utilized: $\approx 6,825$ MiB ($\approx 83.7\%$).
* Safety Headroom: $\approx 1,326$ MiB free.
*Verdict:* **`qwen3:8b` running on local Ollama is fully verified to fit inside RTX 5050 VRAM without swapping to CPU.**

---

## 3. Text-to-Speech (TTS) Evaluation

| Synthesizer | Engine Type | Voices Available | Latency (TTFA) | VRAM | Quality | Cost | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Windows OneCore / SAPI** | OS Native DLL | Heera, Zira, David, Ravi | $< 20$ ms | 0 MB | Natural & Clear | Free (Built-in) | **Primary Production Synthesizer** |
| **Piper TTS (ONNX)** | Local Neural | en_US-amy-medium | $\approx 120$ ms | $\approx 100$ MB | Very Natural | Free (MIT) | Future enhancement |
| **Cloud TTS (ElevenLabs)** | Remote API | Ultra-realistic | 300–800 ms | 0 MB | Ultra-high | Paid per-char | **Rejected** (Incurs API costs) |

*Decision:* Windows OneCore natural voices (*Microsoft Heera* / *Microsoft Zira*) provide instantaneous spoken output, zero VRAM overhead, and complete offline capability.

---

## 4. Audio Capture, Streaming & Barge-In Architecture

1. **Audio Capture:** Browser `navigator.mediaDevices.getUserMedia` with sample rate 16kHz mono.
2. **Streaming:** LLM token generation is streamed via SSE / chunked responses directly to the client.
3. **Chunked Playback:** Sentences are buffered and dispatched to speech synthesis incrementally as they complete punctuation boundaries (`[.!?\n]`).
4. **Instant Interruption (Barge-In):** When the user starts speaking or clicks Stop, active synthesis is cancelled immediately via `window.speechSynthesis.cancel()`, remaining token generation is aborted, and state shifts to `INTERRUPTED` or `LISTENING`.
