import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient, ApiError } from './api/client';
import { HealthResponse, VoiceState, ConversationTurn, ModelStatus, PersonalityMode } from './types/api';
import { Header } from './components/Header';
import { AcousticOrb } from './components/AcousticOrb';
import { ChatDrawer } from './components/ChatDrawer';
import { TaskDrawer } from './components/TaskDrawer';
import { MemoryDrawer } from './components/MemoryDrawer';
import { SettingsModal } from './components/SettingsModal';

interface IWindow extends Window {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
  AudioContext?: typeof AudioContext;
  webkitAudioContext?: typeof AudioContext;
}

export const App: React.FC = () => {
  // Connection and Session
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'probing'>('probing');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [sessionToken, setSessionToken] = useState<string>(() => sessionStorage.getItem('cindercrest_token') || '');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [models, setModels] = useState<ModelStatus[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>('ollama');
  const [personalityMode, setPersonalityMode] = useState<PersonalityMode>('adaptive');

  // Voice State & Audio Analysis
  const [voiceState, setVoiceState] = useState<VoiceState>('IDLE');
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [lastUserUtterance, setLastUserUtterance] = useState<string>('');
  const [lastAssistantReply, setLastAssistantReply] = useState<string>('');
  const [audioLevel, setAudioLevel] = useState<number>(0);

  // Speech Synthesis Settings
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceUri, setSelectedVoiceUri] = useState<string>('');
  const [speechRate, setSpeechRate] = useState<number>(1.0);
  const [speechPitch, setSpeechPitch] = useState<number>(1.0);

  // Conversation Turns & Input
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Drawers
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isTasksOpen, setIsTasksOpen] = useState<boolean>(false);
  const [isMemoryOpen, setIsMemoryOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Audio References
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef<boolean>(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Load available system voices for Windows OneCore / SAPI
  useEffect(() => {
    const updateVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      setAvailableVoices(voices);

      if (voices.length > 0 && !selectedVoiceUri) {
        const preferred =
          voices.find((v) => v.name.includes('Heera')) ||
          voices.find((v) => v.name.includes('Zira')) ||
          voices.find((v) => v.name.includes('David')) ||
          voices.find((v) => v.lang.startsWith('en')) ||
          voices[0];
        if (preferred) {
          setSelectedVoiceUri(preferred.voiceURI);
        }
      }
    };

    updateVoices();
    window.speechSynthesis.onvoiceschanged = updateVoices;
  }, [selectedVoiceUri]);

  // Backend Health Probe
  const checkHealth = useCallback(async () => {
    const start = performance.now();
    try {
      const data = await apiClient.getHealth();
      const duration = Math.round(performance.now() - start);
      setHealthData(data);
      setLatencyMs(duration);
      if (connectionStatus !== 'connected') {
        setConnectionStatus('connected');
        setErrorMessage(null);
      }
    } catch (err: unknown) {
      setConnectionStatus('disconnected');
      setLatencyMs(null);
      const msg = err instanceof ApiError ? err.message : 'Backend unreachable';
      setErrorMessage(`Backend probe failed: ${msg}`);
    }
  }, [connectionStatus]);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 4000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Session Authentication & Models Load
  const verifyToken = useCallback(async (token: string) => {
    if (!token.trim()) {
      setIsAuthenticated(false);
      return;
    }
    try {
      const auth = await apiClient.verifyAuth(token);
      setIsAuthenticated(auth.authenticated);
      sessionStorage.setItem('cindercrest_token', token.trim());

      const [modelList, history] = await Promise.all([
        apiClient.getModels(token),
        apiClient.getHistory(token),
      ]);
      setModels(modelList);
      const availableDefault =
        modelList.find((m) => m.is_default && m.is_available) ||
        modelList.find((m) => m.is_available);
      if (availableDefault) {
        setSelectedProvider(availableDefault.provider_id);
      }
      setTurns(history);

      try {
        const modeData = await apiClient.getPersonalityMode(token);
        if (modeData?.active_mode) {
          setPersonalityMode(modeData.active_mode);
        }
      } catch (err: unknown) {
        console.warn('Could not fetch personality mode:', err);
      }

      if (history.length > 0) {
        const lastUser = [...history].reverse().find((t) => t.role === 'user');
        const lastAssistant = [...history].reverse().find((t) => t.role === 'assistant');
        if (lastUser) setLastUserUtterance(lastUser.content);
        if (lastAssistant) setLastAssistantReply(lastAssistant.content);
      }
      setErrorMessage(null);
    } catch (err: unknown) {
      setIsAuthenticated(false);
      const msg = err instanceof ApiError ? err.message : 'Invalid session token';
      setErrorMessage(`Authentication error: ${msg}`);
    }
  }, []);

  useEffect(() => {
    if (connectionStatus === 'connected' && sessionToken) {
      verifyToken(sessionToken);
    }
  }, [connectionStatus, sessionToken, verifyToken]);

  // Synchronize Voice State with Backend
  const syncVoiceState = useCallback(async (newState: VoiceState, reason?: string) => {
    setVoiceState(newState);
    if (sessionToken && isAuthenticated) {
      try {
        await apiClient.transitionVoiceState(sessionToken, newState, reason);
      } catch (err) {
        // Backend validation
      }
    }
  }, [sessionToken, isAuthenticated]);

  // Real Audio Amplitude Analyser (Web Audio API)
  const startAudioAnalyser = async (stream: MediaStream) => {
    try {
      const win = window as unknown as IWindow;
      const AudioCtx = win.AudioContext || win.webkitAudioContext;
      if (!AudioCtx) return;

      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.35;
      source.connect(analyser);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const sampleLevel = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        setAudioLevel(Math.min(avg / 96, 1.0)); // Real amplitude from mic
        animFrameRef.current = requestAnimationFrame(sampleLevel);
      };

      sampleLevel();
    } catch (err) {
      setAudioLevel(0);
    }
  };

  const stopAudioAnalyser = () => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    analyserRef.current = null;
    setAudioLevel(0);
  };

  // Speak Response via Windows OneCore
  const speakResponse = useCallback((text: string) => {
    if (!text || privacyMode) return;

    window.speechSynthesis.cancel();

    const cleanText = text
      .replace(/[*_#`~[\]]/g, '')
      .replace(/\n+/g, ' ')
      .trim();

    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = speechRate;
    utterance.pitch = speechPitch;

    if (selectedVoiceUri) {
      const voice = availableVoices.find((v) => v.voiceURI === selectedVoiceUri);
      if (voice) utterance.voice = voice;
    }

    utterance.onstart = () => {
      syncVoiceState('SPEAKING', 'Text-to-speech playback started');
    };

    utterance.onend = () => {
      syncVoiceState('IDLE', 'Playback completed naturally');
    };

    utterance.onerror = () => {
      syncVoiceState('IDLE', 'Playback error or cancelled');
    };

    window.speechSynthesis.speak(utterance);
  }, [privacyMode, speechRate, speechPitch, selectedVoiceUri, availableVoices, syncVoiceState]);

  // Instant Interruption (Barge-In)
  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis.speaking || voiceState === 'SPEAKING') {
      window.speechSynthesis.cancel();
      syncVoiceState('INTERRUPTED', 'User stopped speech or barged in');
    }
  }, [voiceState, syncVoiceState]);

  // Keyboard shortcut listener (Escape to interrupt)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        stopSpeaking();
        if (isHistoryOpen) setIsHistoryOpen(false);
        if (isSettingsOpen) setIsSettingsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [stopSpeaking, isHistoryOpen, isSettingsOpen]);

  // Submit User Message
  const submitMessage = useCallback(async (text: string) => {
    const clean = text.trim();
    if (!clean || isSubmitting) return;

    stopSpeaking();
    setIsSubmitting(true);
    setInterimTranscript('');
    setLastUserUtterance(clean);
    syncVoiceState('PROCESSING', 'Dispatching user utterance to conversational model');

    const tempUserTurn: ConversationTurn = {
      turn_index: turns.length + 1,
      role: 'user',
      content: clean,
      timestamp: new Date().toISOString(),
      outcome: 'success',
    };
    setTurns((prev) => [...prev, tempUserTurn]);
    setInputText('');

    try {
      const response = await apiClient.submitChat(sessionToken, clean, selectedProvider);

      const assistantTurn: ConversationTurn = {
        turn_index: response.turn_index,
        role: 'assistant',
        content: response.reply,
        timestamp: new Date().toISOString(),
        outcome: 'success',
        latency_ms: response.latency_ms,
      };

      setTurns((prev) => [...prev, assistantTurn]);
      setLastAssistantReply(response.reply);
      speakResponse(response.reply);
      setErrorMessage(null);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Model generation failed';
      setErrorMessage(`Conversation error: ${msg}`);
      syncVoiceState('IDLE', 'Error occurred during generation');
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionToken, selectedProvider, isSubmitting, turns.length, stopSpeaking, syncVoiceState, speakResponse]);

  // Speech Recognition (Microphone Capture & STT)
  const startListening = useCallback(async () => {
    if (privacyMode) {
      setErrorMessage('Microphone is disabled in Privacy Mode.');
      return;
    }

    stopSpeaking();

    const win = window as unknown as IWindow;
    const SpeechRecognition = win.SpeechRecognition || win.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setErrorMessage('SpeechRecognition is not supported in this browser. Please use the text input below.');
      return;
    }

    try {
      // 1. Capture real audio stream for amplitude analyser
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      await startAudioAnalyser(stream);

      // 2. Initialize speech recognition
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        isListeningRef.current = true;
        setInterimTranscript('');
        syncVoiceState('LISTENING', 'Microphone recording started');
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }

        if (interim) {
          setInterimTranscript(interim);
        }

        if (final) {
          setInterimTranscript(final);
          stopAudioAnalyser();
          recognition.stop();
          submitMessage(final);
        }
      };

      recognition.onerror = (event: any) => {
        isListeningRef.current = false;
        stopAudioAnalyser();
        syncVoiceState('IDLE', `Speech recognition error: ${event.error}`);
        if (event.error === 'not-allowed') {
          setErrorMessage('Microphone access was denied. Please allow microphone permissions or use text fallback.');
        } else if (event.error !== 'no-speech') {
          setErrorMessage(`Speech recognition error: ${event.error}`);
        }
      };

      recognition.onend = () => {
        isListeningRef.current = false;
        stopAudioAnalyser();
        if (voiceState === 'LISTENING') {
          syncVoiceState('IDLE', 'Speech recognition ended');
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: unknown) {
      stopAudioAnalyser();
      setErrorMessage('Microphone access denied or hardware unavailable.');
      syncVoiceState('IDLE', 'Failed to start speech recognition');
    }
  }, [privacyMode, stopSpeaking, syncVoiceState, submitMessage, voiceState]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListeningRef.current) {
      recognitionRef.current.stop();
      isListeningRef.current = false;
      stopAudioAnalyser();
      syncVoiceState('IDLE', 'User manually stopped microphone');
    }
  }, [syncVoiceState]);

  // Privacy Mode Toggle
  const togglePrivacyMode = () => {
    const next = !privacyMode;
    setPrivacyMode(next);
    if (next) {
      stopListening();
      stopSpeaking();
    }
  };

  // Reset Session History
  const handleResetHistory = async () => {
    if (!sessionToken || !isAuthenticated) return;
    try {
      await apiClient.resetHistory(sessionToken);
      setTurns([]);
      setInterimTranscript('');
      setLastUserUtterance('');
      setLastAssistantReply('');
      stopSpeaking();
      syncVoiceState('IDLE', 'History reset');
      setIsHistoryOpen(false);
    } catch (err: unknown) {
      setErrorMessage('Failed to reset conversation history.');
    }
  };

  const handleCycleMode = async () => {
    const modes: PersonalityMode[] = ['adaptive', 'work', 'focus', 'relax', 'coach', 'quiet', 'serious'];
    const nextIdx = (modes.indexOf(personalityMode) + 1) % modes.length;
    const nextMode = modes[nextIdx];
    setPersonalityMode(nextMode);
    if (sessionToken) {
      try {
        await apiClient.setPersonalityMode(sessionToken, nextMode);
      } catch (err: unknown) {
        console.error('Failed to change personality mode:', err);
      }
    }
  };

  const handleSelectPersonalityMode = async (mode: PersonalityMode) => {
    setPersonalityMode(mode);
    if (sessionToken) {
      try {
        await apiClient.setPersonalityMode(sessionToken, mode);
      } catch (err: unknown) {
        console.error('Failed to set personality mode:', err);
      }
    }
  };

  return (
    <div className="futuristic-app-root">
      {/* Top System Navigation Bar */}
      <Header
        connectionStatus={connectionStatus}
        healthData={healthData}
        latencyMs={latencyMs}
        selectedProvider={selectedProvider}
        isMicActive={voiceState === 'LISTENING'}
        privacyMode={privacyMode}
        historyCount={turns.length}
        personalityMode={personalityMode}
        onCycleMode={handleCycleMode}
        onTogglePrivacy={togglePrivacyMode}
        onToggleHistory={() => setIsHistoryOpen(!isHistoryOpen)}
        onToggleTasks={() => setIsTasksOpen(!isTasksOpen)}
        onToggleMemory={() => setIsMemoryOpen(!isMemoryOpen)}
        onToggleSettings={() => setIsSettingsOpen(!isSettingsOpen)}
        isHistoryOpen={isHistoryOpen}
        isTasksOpen={isTasksOpen}
        isMemoryOpen={isMemoryOpen}
        isSettingsOpen={isSettingsOpen}
      />

      {/* Warning & Error Notifications */}
      {errorMessage && (
        <div className="system-banner error">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="btn-banner-close">
            ✕
          </button>
        </div>
      )}

      {healthData?.checks.ollama.status === 'unreachable' && (
        <div className="system-banner warning">
          <span>
            ⚠️ Local Ollama is offline. Run <code>ollama serve</code> in PowerShell to activate Qwen 3 (8B).
          </span>
          <button onClick={checkHealth} className="btn-banner-action">
            Probe
          </button>
        </div>
      )}

      {/* Main Experience Viewport */}
      <main className="central-stage">
        {/* State Readout Pill */}
        <div className="state-badge-container">
          <div className={`futuristic-state-pill ${privacyMode ? 'state-privacy' : voiceState.toLowerCase()}`}>
            <span className="state-pulsar" />
            <span className="state-text">
              {privacyMode
                ? 'PRIVACY MUTED'
                : voiceState === 'LISTENING'
                ? 'LISTENING TO YOU'
                : voiceState === 'PROCESSING'
                ? 'PROCESSING'
                : voiceState === 'SPEAKING'
                ? 'SPEAKING ALOUD'
                : voiceState === 'INTERRUPTED'
                ? 'INTERRUPTED'
                : 'CINDERCREST IDLE'}
            </span>
          </div>
        </div>

        {/* Central Acoustic Core */}
        <div className="acoustic-core-zone">
          <AcousticOrb
            state={voiceState}
            privacyMode={privacyMode}
            audioLevel={audioLevel}
            isSubmitting={isSubmitting}
            onClick={() => {
              if (voiceState === 'SPEAKING') {
                stopSpeaking();
              } else if (voiceState === 'LISTENING') {
                stopListening();
              } else {
                startListening();
              }
            }}
          />
        </div>

        {/* Live Conversation Exchange Readout */}
        <div className="dialogue-readout-zone">
          {/* Active Interim Voice or Last Utterance */}
          <div className="dialogue-user-panel">
            <span className="dialogue-tag">YOU SAID</span>
            <div className="dialogue-text">
              {voiceState === 'LISTENING' ? (
                <span className="live-speech-transcribing">
                  {interimTranscript ? `"${interimTranscript}"` : 'Listening for your voice...'}
                </span>
              ) : lastUserUtterance ? (
                `"${lastUserUtterance}"`
              ) : (
                <span className="dialogue-placeholder">Speak naturally or type below</span>
              )}
            </div>
          </div>

          {/* Cindercrest Spoken Reply */}
          <div className="dialogue-assistant-panel">
            <div className="assistant-panel-header">
              <span className="dialogue-tag assistant">CINDERCREST RESPONSE</span>
              {voiceState === 'SPEAKING' && (
                <button onClick={stopSpeaking} className="btn-interrupt-badge" title="Stop speech output (Escape)">
                  ⏹️ Stop Speaking
                </button>
              )}
            </div>
            <div className="dialogue-text assistant">
              {voiceState === 'PROCESSING' || isSubmitting ? (
                <span className="thinking-shimmer">Formulating spoken response...</span>
              ) : lastAssistantReply ? (
                lastAssistantReply
              ) : (
                <span className="dialogue-placeholder">
                  Press the central orb or click Start Listening to speak.
                </span>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Bottom Command & Interaction Dock */}
      <footer className="interaction-dock">
        <div className="dock-controls">
          {/* Main Voice Toggle */}
          {voiceState !== 'LISTENING' ? (
            <button
              onClick={startListening}
              disabled={privacyMode || isSubmitting}
              className="btn-dock-voice"
              title="Activate microphone speech input"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
              <span>Start Listening</span>
            </button>
          ) : (
            <button
              onClick={stopListening}
              className="btn-dock-voice active-listening"
              title="Stop listening"
            >
              <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
              <span>Stop Listening</span>
            </button>
          )}

          {/* Stop Playback Button (Highlighted when speaking) */}
          {voiceState === 'SPEAKING' && (
            <button onClick={stopSpeaking} className="btn-dock-interrupt" title="Interrupt speech playback (Escape)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              <span>Stop Audio</span>
            </button>
          )}

          {/* Text Input Fallback Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submitMessage(inputText);
            }}
            className="dock-input-form"
          >
            <input
              type="text"
              placeholder={
                privacyMode
                  ? 'Privacy Mode active (Text only)...'
                  : 'Type a message here (Text fallback)...'
              }
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isSubmitting}
              className="dock-text-input"
            />
            <button
              type="submit"
              disabled={isSubmitting || !inputText.trim()}
              className="btn-dock-send"
              title="Send message"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
        </div>
      </footer>

      {/* Flyout Drawers */}
      <ChatDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        turns={turns}
        onResetHistory={handleResetHistory}
      />

      <TaskDrawer
        isOpen={isTasksOpen}
        onClose={() => setIsTasksOpen(false)}
        sessionToken={sessionToken}
      />

      <MemoryDrawer
        isOpen={isMemoryOpen}
        onClose={() => setIsMemoryOpen(false)}
        token={sessionToken}
        privacyMode={privacyMode}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        healthData={healthData}
        models={models}
        selectedProvider={selectedProvider}
        onSelectProvider={setSelectedProvider}
        personalityMode={personalityMode}
        onSelectPersonalityMode={(mode) => handleSelectPersonalityMode(mode as PersonalityMode)}
        availableVoices={availableVoices}
        selectedVoiceUri={selectedVoiceUri}
        onSelectVoice={setSelectedVoiceUri}
        speechRate={speechRate}
        onChangeSpeechRate={setSpeechRate}
        speechPitch={speechPitch}
        onChangeSpeechPitch={setSpeechPitch}
        sessionToken={sessionToken}
        onUpdateSessionToken={(token) => {
          setSessionToken(token);
          verifyToken(token);
        }}
        isAuthenticated={isAuthenticated}
      />
    </div>
  );
};
