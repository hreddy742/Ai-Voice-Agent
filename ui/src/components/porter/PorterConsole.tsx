"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Gauge,
  Headphones,
  Loader2,
  Mic,
  PhoneCall,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TimerReset,
  Volume2,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { client } from "@/client/client.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { resolveBrowserBackendUrl } from "@/lib/apiClient";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type TranscriptTurn = {
  speaker?: string;
  role?: string;
  text?: string;
  content?: string;
  latency_ms?: number;
  audio_seconds?: number;
};

type PorterSummary = {
  call_session_id?: number;
  lead_id?: number;
  outcome?: string;
  disposition?: string;
  state?: string;
  evaluation_score?: number;
  policy_status?: string;
  latency_ms?: number;
  ttfw_ms?: number;
  duration_seconds?: number;
  objections_handled?: number;
};

type PorterOutcomeDetails = {
  disposition?: string;
  call_summary?: string;
  objections?: string[];
  next_action?: string;
  human_handoff_reason?: string;
  created_at?: string;
};

type SimulationResponse = {
  summary: PorterSummary;
  assistant_audio_count: number;
  transcript: TranscriptTurn[];
  telephony_enabled: boolean;
  crm_sync_enabled: boolean;
  email_enabled: boolean;
  sms_enabled: boolean;
};

type LiveVoiceResponse = {
  call_session_id: number;
  lead_id: number;
  user_text: string;
  assistant_text: string;
  assistant_audio_base64: string;
  assistant_audio_content_type: string;
  audio_streamed: boolean;
  vad: Record<string, unknown>;
  stt: Record<string, unknown>;
  tts: {
    adapter_name?: string;
    voice?: string;
    duration_seconds?: number;
    sample_rate?: number;
    metadata?: Record<string, unknown>;
  };
  llm: {
    model?: string;
    allowed?: boolean;
    policy_violation_count?: number;
  };
  timings_ms?: Record<string, number>;
  transcript: TranscriptTurn[];
  should_close: boolean;
};

type VoiceOpenerResponse = {
  call_session_id: number;
  lead_id: number;
  assistant_text: string;
  assistant_audio_base64: string;
  assistant_audio_content_type: string;
  tts: Record<string, unknown>;
  transcript: TranscriptTurn[];
};

type RuntimeComponent = {
  name: string;
  provider: string;
  model: string;
  ready: boolean;
  production_recommended: boolean;
  details: Record<string, unknown>;
};

type RuntimeReadiness = {
  ready: boolean;
  fast_voice_mode: boolean;
  default_voice: string;
  recommended_target_ms: number;
  notes: string[];
  components: RuntimeComponent[];
};

type RuntimePrewarmResponse = {
  voice: string;
  warmed_count: number;
  cache_hit_count: number;
  total_elapsed_ms: number;
  scripts: Array<{
    script_name: string;
    cache_hit: boolean;
    elapsed_ms: number;
  }>;
};

type PorterSession = PorterSummary & {
  id?: number;
  created_at?: string;
  transcript?: TranscriptTurn[];
  summary?: PorterSummary;
  outcome_details?: PorterOutcomeDetails;
};

const DEMO_TRANSCRIPT: TranscriptTurn[] = [
  {
    speaker: "assistant",
    text: "Hi Asha, this is Porter calling about the demo request from your operations team.",
    latency_ms: 420,
    audio_seconds: 4.8,
  },
  {
    speaker: "user",
    text: "I only have a minute. Can you tell me why this matters?",
  },
  {
    speaker: "assistant",
    text: "Absolutely. The goal is to qualify urgent requests, capture the right context, and hand clean notes to your team.",
    latency_ms: 510,
    audio_seconds: 6.2,
  },
  {
    speaker: "user",
    text: "Send the details and have someone follow up tomorrow.",
  },
];

const DEMO_SESSIONS: PorterSession[] = [
  {
    id: 8012,
    lead_id: 41,
    outcome: "qualified_follow_up",
    disposition: "interested",
    state: "completed",
    evaluation_score: 92,
    latency_ms: 486,
    ttfw_ms: 238,
    duration_seconds: 146,
    objections_handled: 1,
    created_at: new Date().toISOString(),
    transcript: DEMO_TRANSCRIPT,
  },
  {
    id: 8011,
    lead_id: 37,
    outcome: "needs_nurture",
    disposition: "callback",
    state: "completed",
    evaluation_score: 81,
    latency_ms: 612,
    ttfw_ms: 309,
    duration_seconds: 214,
    objections_handled: 2,
    created_at: new Date(Date.now() - 1000 * 60 * 33).toISOString(),
    transcript: DEMO_TRANSCRIPT.slice(0, 3),
  },
  {
    id: 8010,
    lead_id: 22,
    outcome: "not_qualified",
    disposition: "no_fit",
    state: "review",
    evaluation_score: 68,
    latency_ms: 744,
    ttfw_ms: 361,
    duration_seconds: 98,
    objections_handled: 0,
    created_at: new Date(Date.now() - 1000 * 60 * 87).toISOString(),
    transcript: DEMO_TRANSCRIPT.slice(1),
  },
];

const LATENCY_DATA = [
  { window: "09:00", p50: 318, p90: 612, ttfw: 214 },
  { window: "10:00", p50: 344, p90: 650, ttfw: 236 },
  { window: "11:00", p50: 306, p90: 588, ttfw: 205 },
  { window: "12:00", p50: 372, p90: 692, ttfw: 248 },
  { window: "13:00", p50: 336, p90: 636, ttfw: 226 },
  { window: "14:00", p50: 329, p90: 604, ttfw: 219 },
];

const OUTCOME_COLORS = ["#34d399", "#fbbf24", "#60a5fa", "#f87171"];

const PORTER_PCM_WORKLET = `
class PorterPCMCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.offset = 0;
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input?.length) return true;
    const ratio = sampleRate / 16000;
    const output = new Int16Array(Math.ceil((input.length - this.offset) / ratio));
    let position = this.offset;
    let index = 0;
    while (position < input.length) {
      const sample = Math.max(-1, Math.min(1, input[Math.floor(position)] || 0));
      output[index++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      position += ratio;
    }
    this.offset = position - input.length;
    const chunk = output.buffer.slice(0, index * 2);
    this.port.postMessage(chunk, [chunk]);
    return true;
  }
}
registerProcessor("porter-pcm-capture", PorterPCMCapture);
`;

function normaliseSession(session: PorterSession): PorterSession {
  const merged = {
    ...session,
    ...(session.summary ?? {}),
  };
  const rawOutcome = (merged as Omit<PorterSession, "outcome"> & { outcome?: unknown }).outcome;
  const outcomeDetails = (
    typeof rawOutcome === "object" && rawOutcome !== null
      ? rawOutcome as PorterOutcomeDetails
      : undefined
  );
  const disposition = [
    typeof rawOutcome === "string" ? rawOutcome : undefined,
    outcomeDetails?.disposition,
    merged.disposition,
  ].find((value): value is string => typeof value === "string" && value.trim().length > 0);

  return {
    ...merged,
    outcome: disposition,
    disposition,
    outcome_details: outcomeDetails ?? session.outcome_details,
    id: session.id ?? session.call_session_id ?? session.summary?.call_session_id,
  };
}

function formatMs(value?: number) {
  return typeof value === "number" ? `${Math.round(value)} ms` : "n/a";
}

const LIVE_TIMING_STAGES = ["vad", "stt", "db_context", "llm", "tts", "persist"] as const;

function formatDuration(value?: number) {
  if (typeof value !== "number") return "n/a";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function humanise(value?: unknown) {
  if (typeof value === "string" && value.trim()) {
    return value.replaceAll("_", " ");
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "unknown";
}

function scoreTone(score?: number) {
  if (typeof score !== "number") return "text-muted-foreground";
  if ((score ?? 0) >= 85) return "text-emerald-400";
  if ((score ?? 0) >= 70) return "text-amber-300";
  return "text-red-300";
}

function integrationIcon(enabled: boolean) {
  return enabled ? CheckCircle2 : XCircle;
}

async function parseApiResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail || data?.message || response.statusText;
    const error = new Error(typeof detail === "string" ? detail : "Request failed");
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
  return data as T;
}

function base64ToBlob(base64: string, contentType: string) {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: contentType });
}

function audioBufferToWav(audioBuffer: AudioBuffer, startSeconds = 0) {
  const channelCount = Math.min(audioBuffer.numberOfChannels, 2);
  const sampleRate = audioBuffer.sampleRate;
  const startSample = Math.min(audioBuffer.length, Math.floor(startSeconds * sampleRate));
  const samples = audioBuffer.length - startSample;
  const bytesPerSample = 2;
  const blockAlign = channelCount * bytesPerSample;
  const buffer = new ArrayBuffer(44 + samples * blockAlign);
  const view = new DataView(buffer);

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples * blockAlign, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channelCount, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples * blockAlign, true);

  let offset = 44;
  for (let index = 0; index < samples; index += 1) {
    for (let channel = 0; channel < channelCount; channel += 1) {
      const sample = Math.max(-1, Math.min(1, audioBuffer.getChannelData(channel)[startSample + index] ?? 0));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += bytesPerSample;
    }
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

async function recordedBlobToWav(blob: Blob, startSeconds = 0) {
  if (blob.type.includes("wav") && startSeconds === 0) {
    return blob;
  }
  const AudioContextCtor = window.AudioContext ?? (
    window as typeof window & { webkitAudioContext?: typeof AudioContext }
  ).webkitAudioContext;
  if (!AudioContextCtor) {
    throw new Error("This browser cannot convert microphone audio to WAV.");
  }
  const context = new AudioContextCtor();
  try {
    const audioBuffer = await context.decodeAudioData(await blob.arrayBuffer());
    return audioBufferToWav(audioBuffer, startSeconds);
  } finally {
    await context.close().catch(() => undefined);
  }
}

export default function PorterConsole() {
  const auth = useAuth();
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const voiceSocketRef = useRef<WebSocket | null>(null);
  const pcmWorkletRef = useRef<AudioWorkletNode | null>(null);
  const streamingCaptureRef = useRef(false);
  const pcmPreRollRef = useRef<ArrayBuffer[]>([]);
  const recordedChunksRef = useRef<BlobPart[]>([]);
  const callActiveRef = useRef(false);
  const callAttemptRef = useRef(0);
  const suppressNextSubmitRef = useRef(false);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const activeAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const streamedAudioSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const streamedPlaybackPromiseRef = useRef<Promise<void> | null>(null);
  const streamedPlaybackResolveRef = useRef<(() => void) | null>(null);
  const streamedPlaybackEndedRef = useRef(false);
  const streamedPlaybackCancelledRef = useRef(false);
  const nextStreamPlaybackTimeRef = useRef(0);
  const finishPlaybackRef = useRef<(() => void) | null>(null);
  const agentSpeakingRef = useRef(false);
  const playbackInterruptedRef = useRef(false);
  const bargeInArmedAtRef = useRef(0);
  const bargeInFrameCountRef = useRef(0);
  const speechStartedAtRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserFrameRef = useRef<number | null>(null);
  const silenceStartedAtRef = useRef<number | null>(null);
  const heardSpeechRef = useRef(false);
  const turnStartedAtRef = useRef<number | null>(null);
  const speechFrameCountRef = useRef(0);
  const peakRmsRef = useRef(0);
  const [sessions, setSessions] = useState<PorterSession[]>(DEMO_SESSIONS);
  const [selectedId, setSelectedId] = useState<number>(DEMO_SESSIONS[0].id ?? 0);
  const [apiState, setApiState] = useState<"checking" | "live" | "offline">("checking");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [recording, setRecording] = useState(false);
  const [callActive, setCallActive] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("Ready to start a live local call.");
  const [liveCallSessionId, setLiveCallSessionId] = useState<number | null>(null);
  const [lastLiveTurn, setLastLiveTurn] = useState<LiveVoiceResponse | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [runtimeReadiness, setRuntimeReadiness] = useState<RuntimeReadiness | null>(null);
  const [prewarming, setPrewarming] = useState(false);
  const [lastPrewarm, setLastPrewarm] = useState<RuntimePrewarmResponse | null>(null);
  const [leadId, setLeadId] = useState("");
  const [voiceMode, setVoiceMode] = useState("mock");
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [firstTurn, setFirstTurn] = useState("I am interested, but I need to know how this integrates with our CRM.");
  const [secondTurn, setSecondTurn] = useState("That sounds useful. Send me the details and book a follow up.");

  const selectedSession = useMemo(
    () => sessions.find((session) => (session.id ?? session.call_session_id) === selectedId) ?? sessions[0],
    [selectedId, sessions],
  );

  const transcript = selectedSession?.transcript ?? [];

  const metrics = useMemo(() => {
    const total = sessions.length || 1;
    const scores = sessions
      .map((session) => session.evaluation_score)
      .filter((score): score is number => typeof score === "number");
    const latencies = sessions
      .map((session) => session.latency_ms)
      .filter((latency): latency is number => typeof latency === "number");
    const averageScore = scores.length
      ? Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length)
      : undefined;
    const avgLatency = latencies.length
      ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length)
      : undefined;
    const qualified = sessions.filter((session) =>
      ["qualified_follow_up", "interested"].includes(session.outcome || session.disposition || ""),
    ).length;
    return {
      total,
      averageScore,
      avgLatency,
      conversion: Math.round((qualified / total) * 100),
    };
  }, [sessions]);

  const outcomeData = useMemo(() => {
    const counts = sessions.reduce<Record<string, number>>((acc, session) => {
      const key = humanise(session.outcome || session.disposition);
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [sessions]);

  const loadSessions = async () => {
    if (!auth.isAuthenticated) return;
    try {
      const token = await auth.getAccessToken();
      const response = await fetch("/api/v1/porter-local/call-sessions?limit=25", {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      const data = await parseApiResponse<{ sessions: PorterSession[] }>(response);
      const nextSessions = data.sessions.map(normaliseSession);
      if (nextSessions.length > 0) {
        setSessions(nextSessions);
        setSelectedId(nextSessions[0].id ?? nextSessions[0].call_session_id ?? 0);
      }
      setApiState("live");
      setError(null);
    } catch (err) {
      setApiState("offline");
      setError(err instanceof Error ? err.message : "Porter API is unavailable");
    }
  };

  const loadRuntimeReadiness = async () => {
    if (!auth.isAuthenticated) return;
    try {
      const token = await auth.getAccessToken();
      const response = await fetch("/api/v1/porter-local/voice-runtime/readiness", {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      setRuntimeReadiness(await parseApiResponse<RuntimeReadiness>(response));
      setApiState("live");
    } catch (err) {
      setRuntimeReadiness(null);
      setError(err instanceof Error ? err.message : "Porter voice runtime is unavailable");
    }
  };

  useEffect(() => {
    loadSessions();
    loadRuntimeReadiness();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isAuthenticated]);

  useEffect(() => {
    if (!auth.isAuthenticated || apiState !== "live" || selectedId <= 0) return;
    const selected = sessions.find(
      (session) => (session.id ?? session.call_session_id) === selectedId,
    );
    if (!selected || selected.transcript !== undefined) return;

    let cancelled = false;
    setReviewLoading(true);
    void (async () => {
      try {
        const token = await auth.getAccessToken();
        const response = await fetch(`/api/v1/porter-local/call-sessions/${selectedId}`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        const data = await parseApiResponse<{ session: PorterSession }>(response);
        if (cancelled) return;
        const review = normaliseSession(data.session);
        setSessions((current) => current.map((session) => (
          (session.id ?? session.call_session_id) === selectedId ? review : session
        )));
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Porter call review is unavailable");
        }
      } finally {
        if (!cancelled) setReviewLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [apiState, auth, selectedId, sessions]);

  useEffect(() => () => {
    callAttemptRef.current += 1;
    callActiveRef.current = false;
    try {
      activeAudioSourceRef.current?.stop();
      streamedAudioSourcesRef.current.forEach((source) => source.stop());
      streamedAudioSourcesRef.current.clear();
      streamedPlaybackCancelledRef.current = true;
      streamedPlaybackResolveRef.current?.();
    } catch {
      // The source already ended.
    }
    voiceSocketRef.current?.close();
    playbackContextRef.current?.close().catch(() => undefined);
    cleanupRecorderResources();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const processLiveVoiceResponse = async (data: LiveVoiceResponse) => {
    setLiveCallSessionId(data.call_session_id);
    setLastLiveTurn(data);
    setVoiceStatus("Playing Porter reply...");
    const interrupted = data.audio_streamed
      ? await finishStreamedAssistantAudio()
      : await playAssistantAudio(
        data.assistant_audio_base64,
        data.assistant_audio_content_type,
        "Porter reply audio playback failed.",
      );
    const newSession = normaliseSession({
      id: data.call_session_id,
      call_session_id: data.call_session_id,
      lead_id: data.lead_id,
      state: data.should_close ? "completed" : "in_progress",
      transcript: data.transcript,
      created_at: new Date().toISOString(),
    });
    setSessions((current) => [newSession, ...current.filter((session) => (session.id ?? session.call_session_id) !== data.call_session_id)].slice(0, 25));
    setSelectedId(data.call_session_id);
    setApiState("live");
    if (data.should_close) {
      callActiveRef.current = false;
      setCallActive(false);
      await stopTurnRecording(false);
      voiceSocketRef.current?.close(1000, "Porter call completed");
      setVoiceStatus("Call completed.");
      return;
    }
    setVoiceStatus(callActiveRef.current ? "Listening..." : "Ready to start a live local call.");
    if (callActiveRef.current && !interrupted) await startTurnRecording();
  };

  const submitLiveVoiceBlob = async (recordedBlob: Blob, trimStartSeconds = 0) => {
    setVoiceBusy(true);
    setVoiceStatus("Transcribing your audio...");
    setError(null);
    try {
      const wavBlob = await recordedBlobToWav(recordedBlob, trimStartSeconds);
      const token = await auth.getAccessToken();
      const body = new FormData();
      body.append("audio", wavBlob, "caller.wav");
      if (liveCallSessionId) {
        body.append("call_session_id", String(liveCallSessionId));
      }
      if (leadId) {
        body.append("lead_id", leadId);
      }

      setVoiceStatus("Generating Porter response...");
      const response = await fetch("/api/v1/porter-local/voice-turns", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body,
      });
      const data = await parseApiResponse<LiveVoiceResponse>(response);
      await processLiveVoiceResponse(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Live voice turn failed";
      const status = (err as Error & { status?: number }).status;
      const isNoSpeech = status === 422 || /empty text|no speech|no usable speech/i.test(message);
      if (isNoSpeech && callActiveRef.current) {
        setError(null);
        setVoiceStatus("I did not catch that. Listening...");
        await startTurnRecording();
        return;
      }
      setError(message);
      setVoiceStatus(message);
      callActiveRef.current = false;
      setCallActive(false);
    } finally {
      setVoiceBusy(false);
    }
  };

  const playAssistantAudio = async (base64: string, contentType: string, failureMessage: string) => {
    const audioBlob = base64ToBlob(base64, contentType);
    const context = await ensurePlaybackContext();
    let audioBuffer: AudioBuffer;
    try {
      audioBuffer = await context.decodeAudioData(await audioBlob.arrayBuffer());
    } catch {
      throw new Error(failureMessage);
    }
    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(context.destination);
    activeAudioSourceRef.current = source;
    agentSpeakingRef.current = true;
    playbackInterruptedRef.current = false;
    bargeInArmedAtRef.current = performance.now() + 800;
    setVoiceStatus("Aiva is speaking — you can interrupt.");

    try {
      await new Promise<void>((resolve, reject) => {
        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          resolve();
        };
        finishPlaybackRef.current = finish;
        source.onended = finish;
        try {
          source.start();
          void startTurnRecording();
        } catch {
          reject(new Error(failureMessage));
        }
      });
      return playbackInterruptedRef.current;
    } finally {
      agentSpeakingRef.current = false;
      bargeInArmedAtRef.current = 0;
      finishPlaybackRef.current = null;
      activeAudioSourceRef.current = null;
      if (!playbackInterruptedRef.current) {
        await stopTurnRecording(false);
      }
    }
  };

  const interruptAssistantPlayback = () => {
    if (!agentSpeakingRef.current || playbackInterruptedRef.current) return;
    playbackInterruptedRef.current = true;
    agentSpeakingRef.current = false;
    try {
      activeAudioSourceRef.current?.stop();
      streamedAudioSourcesRef.current.forEach((source) => source.stop());
    } catch {
      // The source may have ended between VAD detection and cancellation.
    }
    streamedAudioSourcesRef.current.clear();
    streamedPlaybackEndedRef.current = true;
    streamedPlaybackCancelledRef.current = true;
    streamedPlaybackResolveRef.current?.();
    finishPlaybackRef.current?.();
    setVoiceStatus("Interrupted — listening...");
  };

  const resolveStreamedPlaybackIfFinished = () => {
    if (streamedPlaybackEndedRef.current && streamedAudioSourcesRef.current.size === 0) {
      streamedPlaybackResolveRef.current?.();
    }
  };

  const queueStreamedAssistantAudio = async (pcm16Base64: string, sampleRate: number) => {
    if (!pcm16Base64 || !Number.isFinite(sampleRate) || sampleRate <= 0) {
      throw new Error("Porter sent an invalid audio chunk.");
    }
    const context = await ensurePlaybackContext();
    if (streamedPlaybackCancelledRef.current) return;
    if (!agentSpeakingRef.current) {
      agentSpeakingRef.current = true;
      playbackInterruptedRef.current = false;
      streamedPlaybackEndedRef.current = false;
      streamedPlaybackCancelledRef.current = false;
      nextStreamPlaybackTimeRef.current = context.currentTime;
      streamedPlaybackPromiseRef.current = new Promise<void>((resolve) => {
        streamedPlaybackResolveRef.current = resolve;
      });
      bargeInArmedAtRef.current = performance.now() + 800;
      setVoiceStatus("Aiva is speaking — you can interrupt.");
      void startTurnRecording();
    }

    const binary = window.atob(pcm16Base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const pcm16 = new Int16Array(bytes.buffer);
    const audioBuffer = context.createBuffer(1, pcm16.length, sampleRate);
    const channel = audioBuffer.getChannelData(0);
    for (let index = 0; index < pcm16.length; index += 1) channel[index] = pcm16[index] / 32768;

    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(context.destination);
    streamedAudioSourcesRef.current.add(source);
    source.onended = () => {
      streamedAudioSourcesRef.current.delete(source);
      resolveStreamedPlaybackIfFinished();
    };
    const startAt = Math.max(context.currentTime + 0.02, nextStreamPlaybackTimeRef.current);
    nextStreamPlaybackTimeRef.current = startAt + audioBuffer.duration;
    source.start(startAt);
  };

  const finishStreamedAssistantAudio = async () => {
    const playback = streamedPlaybackPromiseRef.current;
    if (!playback) return playbackInterruptedRef.current;
    streamedPlaybackEndedRef.current = true;
    resolveStreamedPlaybackIfFinished();
    await playback;
    const interrupted = playbackInterruptedRef.current;
    agentSpeakingRef.current = false;
    bargeInArmedAtRef.current = 0;
    nextStreamPlaybackTimeRef.current = 0;
    streamedPlaybackPromiseRef.current = null;
    streamedPlaybackResolveRef.current = null;
    streamedPlaybackEndedRef.current = false;
    streamedPlaybackCancelledRef.current = false;
    if (!interrupted) await stopTurnRecording(false);
    return interrupted;
  };

  const connectVoiceStream = async (token: string) => new Promise<VoiceOpenerResponse>((resolve, reject) => {
    const baseUrl = client.getConfig().baseUrl || resolveBrowserBackendUrl();
    const wsUrl = baseUrl.replace(/^http/, "ws");
    const params = new URLSearchParams({ token });
    if (leadId) params.set("lead_id", leadId);
    const socket = new WebSocket(`${wsUrl}/api/v1/porter-local/voice-stream?${params}`);
    voiceSocketRef.current = socket;
    let opened = false;
    const timeout = window.setTimeout(() => {
      socket.close();
      reject(new Error("Porter voice stream timed out."));
    }, 15_000);

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as {
        type: string;
        payload: VoiceOpenerResponse | LiveVoiceResponse | { pcm16_base64?: string; sample_rate?: number; message?: string };
      };
      if (message.type === "opener") {
        opened = true;
        window.clearTimeout(timeout);
        resolve(message.payload as VoiceOpenerResponse);
        return;
      }
      if (message.type === "turn") {
        setVoiceBusy(true);
        setVoiceStatus("Generating Porter response...");
        void processLiveVoiceResponse(message.payload as LiveVoiceResponse)
          .catch((error) => setError(error instanceof Error ? error.message : "Streaming voice turn failed."))
          .finally(() => setVoiceBusy(false));
        return;
      }
      if (message.type === "audio-chunk") {
        const payload = message.payload as { pcm16_base64?: string; sample_rate?: number };
        void queueStreamedAssistantAudio(payload.pcm16_base64 ?? "", payload.sample_rate ?? 0)
          .catch((error) => setError(error instanceof Error ? error.message : "Streaming audio playback failed."));
        return;
      }
      const messageText = (message.payload as { message?: string }).message || "Porter voice stream failed.";
      if (!opened) {
        window.clearTimeout(timeout);
        reject(new Error(messageText));
      } else {
        setVoiceBusy(false);
        setError(messageText);
        setVoiceStatus(messageText);
        if (callActiveRef.current) void startTurnRecording();
      }
    };
    socket.onerror = () => {
      // The close event carries the usable handshake code and reason.
    };
    socket.onclose = (event) => {
      window.clearTimeout(timeout);
      voiceSocketRef.current = null;
      if (!opened) {
        if (event.code === 1008 || /invalid|expired|authentication/i.test(event.reason)) {
          reject(new Error("Your local session is no longer valid. Sign in again, then start the Porter call."));
          return;
        }
        const reason = event.reason ? `: ${event.reason}` : "";
        reject(new Error(`Porter voice stream closed (${event.code || "unknown"})${reason}`));
        return;
      }
      if (callActiveRef.current) {
        callActiveRef.current = false;
        setCallActive(false);
        setVoiceStatus("Voice stream disconnected.");
      }
    };
  });

  const ensurePlaybackContext = async () => {
    let context = playbackContextRef.current;
    if (!context || context.state === "closed") {
      const AudioContextCtor = window.AudioContext ?? (
        window as typeof window & { webkitAudioContext?: typeof AudioContext }
      ).webkitAudioContext;
      if (!AudioContextCtor) throw new Error("This browser does not support voice playback.");
      context = new AudioContextCtor();
      playbackContextRef.current = context;
    }
    if (context.state === "suspended") {
      let resumeTimeout: number | undefined;
      try {
        await Promise.race([
          context.resume(),
          new Promise<never>((_, reject) => {
            resumeTimeout = window.setTimeout(
              () => reject(new Error("Browser audio did not start. Check this tab's sound permission.")),
              5_000,
            );
          }),
        ]);
      } finally {
        if (resumeTimeout !== undefined) window.clearTimeout(resumeTimeout);
      }
    }
    if (context.state !== "running") {
      throw new Error("Browser audio playback is not available. Check this tab's sound permission.");
    }
    return context;
  };

  const prewarmRuntime = async () => {
    if (!auth.isAuthenticated || prewarming) return;
    setPrewarming(true);
    setError(null);
    setVoiceStatus("Prewarming approved Porter voice scripts...");
    try {
      const token = await auth.getAccessToken();
      const response = await fetch("/api/v1/porter-local/voice-runtime/prewarm", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      const data = await parseApiResponse<RuntimePrewarmResponse>(response);
      setLastPrewarm(data);
      setVoiceStatus(`Prewarmed ${data.warmed_count} scripts for ${data.voice}.`);
      await loadRuntimeReadiness();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Prewarm failed";
      setError(message);
      setVoiceStatus(message);
    } finally {
      setPrewarming(false);
    }
  };

  const startCall = async () => {
    if (!auth.isAuthenticated || callActive || voiceBusy) return;
    const callAttempt = ++callAttemptRef.current;
    callActiveRef.current = true;
    streamedPlaybackCancelledRef.current = false;
    setCallActive(true);
    setError(null);
    setVoiceBusy(true);
    setVoiceStatus("Aiva is opening the call...");
    try {
      await ensurePlaybackContext();
      if (callAttempt !== callAttemptRef.current) return;
      const token = await auth.getAccessToken();
      const data = await connectVoiceStream(token);
      if (callAttempt !== callAttemptRef.current) return;
      setLiveCallSessionId(data.call_session_id);
      const newSession = normaliseSession({
        id: data.call_session_id,
        call_session_id: data.call_session_id,
        lead_id: data.lead_id,
        state: "in_progress",
        transcript: data.transcript,
        created_at: new Date().toISOString(),
      });
      setSessions((current) => [
        newSession,
        ...current.filter((session) => (session.id ?? session.call_session_id) !== data.call_session_id),
      ].slice(0, 25));
      setSelectedId(data.call_session_id);

      const interrupted = await playAssistantAudio(
        data.assistant_audio_base64,
        data.assistant_audio_content_type,
        "Aiva opener playback failed.",
      );
      setVoiceStatus(callActiveRef.current ? "Listening..." : "Call ended.");
      if (callActiveRef.current && !interrupted) await startTurnRecording();
    } catch (err) {
      if (callAttempt !== callAttemptRef.current) return;
      const message = err instanceof Error ? err.message : "Aiva could not start the call.";
      setError(message);
      setVoiceStatus(message);
      callActiveRef.current = false;
      setCallActive(false);
    } finally {
      if (callAttempt === callAttemptRef.current) setVoiceBusy(false);
    }
  };

  const endCall = () => {
    callAttemptRef.current += 1;
    callActiveRef.current = false;
    setCallActive(false);
    setVoiceBusy(false);
    setVoiceStatus("Call ended.");
    try {
      activeAudioSourceRef.current?.stop();
      streamedAudioSourcesRef.current.forEach((source) => source.stop());
    } catch {
      // The source already ended.
    }
    streamedAudioSourcesRef.current.clear();
    streamedPlaybackCancelledRef.current = true;
    streamedPlaybackResolveRef.current?.();
    finishPlaybackRef.current?.();
    if (voiceSocketRef.current?.readyState === WebSocket.OPEN) {
      voiceSocketRef.current.send(JSON.stringify({ type: "end-call" }));
    }
    voiceSocketRef.current?.close();
    voiceSocketRef.current = null;
    streamingCaptureRef.current = false;
    suppressNextSubmitRef.current = true;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    cleanupRecorderResources();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    setRecording(false);
  };

  const startTurnRecording = async () => {
    if (
      !auth.isAuthenticated
      || !callActiveRef.current
      || streamingCaptureRef.current
      || mediaRecorderRef.current?.state === "recording"
    ) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser does not expose microphone capture.");
      callActiveRef.current = false;
      setCallActive(false);
      return;
    }
    try {
      if (voiceSocketRef.current?.readyState === WebSocket.OPEN) {
        await startPCMStreamRecording();
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;
      recordedChunksRef.current = [];
      suppressNextSubmitRef.current = false;
      silenceStartedAtRef.current = null;
      heardSpeechRef.current = false;
      turnStartedAtRef.current = performance.now();
      speechFrameCountRef.current = 0;
      peakRmsRef.current = 0;
      bargeInFrameCountRef.current = 0;
      speechStartedAtRef.current = null;
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        cleanupRecorderResources();
        setRecording(false);
        const shouldSkipSubmit = suppressNextSubmitRef.current || !callActiveRef.current;
        suppressNextSubmitRef.current = false;
        if (shouldSkipSubmit) {
          return;
        }
        const turnDurationMs = turnStartedAtRef.current === null ? 0 : performance.now() - turnStartedAtRef.current;
        const hasUsableSpeech = (
          turnDurationMs >= 1000
          && speechFrameCountRef.current >= 8
          && peakRmsRef.current >= 0.035
        );
        if (!hasUsableSpeech) {
          setVoiceStatus("Listening...");
          if (callActiveRef.current) {
            void startTurnRecording();
          }
          return;
        }
        const blob = new Blob(recordedChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const speechStartedAt = speechStartedAtRef.current;
        const recordingStartedAt = turnStartedAtRef.current;
        const trimStartSeconds = speechStartedAt === null || recordingStartedAt === null
          ? 0
          : Math.max(0, (speechStartedAt - recordingStartedAt) / 1000 - 0.25);
        void submitLiveVoiceBlob(blob, trimStartSeconds);
      };
      recorder.start(250);
      setRecording(true);
      if (!agentSpeakingRef.current) setVoiceStatus("Listening...");
      startSilenceMonitor(stream, recorder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microphone permission failed");
      setVoiceStatus("Microphone permission failed.");
      callActiveRef.current = false;
      setCallActive(false);
    }
  };

  const startPCMStreamRecording = async () => {
    const AudioContextCtor = window.AudioContext ?? (
      window as typeof window & { webkitAudioContext?: typeof AudioContext }
    ).webkitAudioContext;
    if (!AudioContextCtor) throw new Error("This browser does not support streaming microphone audio.");

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const context = new AudioContextCtor();
    const moduleUrl = URL.createObjectURL(new Blob([PORTER_PCM_WORKLET], { type: "text/javascript" }));
    try {
      await context.audioWorklet.addModule(moduleUrl);
    } catch (error) {
      stream.getTracks().forEach((track) => track.stop());
      await context.close().catch(() => undefined);
      throw error;
    } finally {
      URL.revokeObjectURL(moduleUrl);
    }
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    const worklet = new AudioWorkletNode(context, "porter-pcm-capture");
    const silentOutput = context.createGain();
    silentOutput.gain.value = 0;
    source.connect(analyser);
    source.connect(worklet);
    worklet.connect(silentOutput).connect(context.destination);

    mediaStreamRef.current = stream;
    audioContextRef.current = context;
    pcmWorkletRef.current = worklet;
    pcmPreRollRef.current = [];
    streamingCaptureRef.current = true;
    silenceStartedAtRef.current = null;
    heardSpeechRef.current = false;
    turnStartedAtRef.current = performance.now();
    speechFrameCountRef.current = 0;
    peakRmsRef.current = 0;
    bargeInFrameCountRef.current = 0;
    speechStartedAtRef.current = null;

    worklet.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
      const socket = voiceSocketRef.current;
      if (!streamingCaptureRef.current || socket?.readyState !== WebSocket.OPEN) return;
      if (agentSpeakingRef.current) {
        if (performance.now() >= bargeInArmedAtRef.current) {
          pcmPreRollRef.current.push(event.data);
          pcmPreRollRef.current = pcmPreRollRef.current.slice(-20);
        }
        return;
      }
      for (const chunk of pcmPreRollRef.current) socket.send(chunk);
      pcmPreRollRef.current = [];
      socket.send(event.data);
    };
    setRecording(true);
    if (!agentSpeakingRef.current) setVoiceStatus("Listening...");
    monitorSilence(analyser, () => streamingCaptureRef.current);
  };

  const stopTurnRecording = (submit = true) => new Promise<void>((resolve) => {
    if (streamingCaptureRef.current) {
      streamingCaptureRef.current = false;
      pcmPreRollRef.current = [];
      pcmWorkletRef.current?.disconnect();
      pcmWorkletRef.current = null;
      cleanupRecorderResources();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      setRecording(false);
      if (voiceSocketRef.current?.readyState === WebSocket.OPEN) {
        voiceSocketRef.current.send(JSON.stringify({ type: submit ? "commit-turn" : "cancel-turn" }));
      }
      if (submit) {
        setVoiceBusy(true);
        setVoiceStatus("Processing streaming audio...");
      }
      resolve();
      return;
    }
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      resolve();
      return;
    }
    suppressNextSubmitRef.current = !submit;
    recorder.addEventListener("stop", () => resolve(), { once: true });
    setRecording(false);
    if (submit) setVoiceStatus("Processing...");
    recorder.stop();
  });

  function cleanupRecorderResources() {
    if (analyserFrameRef.current !== null) {
      cancelAnimationFrame(analyserFrameRef.current);
      analyserFrameRef.current = null;
    }
    audioContextRef.current?.close().catch(() => undefined);
    audioContextRef.current = null;
  }

  function startSilenceMonitor(stream: MediaStream, recorder: MediaRecorder) {
    const AudioContextCtor = window.AudioContext ?? (
      window as typeof window & { webkitAudioContext?: typeof AudioContext }
    ).webkitAudioContext;
    if (!AudioContextCtor) return;

    const context = new AudioContextCtor();
    audioContextRef.current = context;
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);
    monitorSilence(analyser, () => recorder.state !== "inactive");
  }

  function monitorSilence(analyser: AnalyserNode, isCapturing: () => boolean) {
    const samples = new Uint8Array(analyser.fftSize);
    const startedAt = performance.now();
    const minTurnMs = 350;
    const silenceMs = 400;
    const maxTurnMs = 15000;
    const noSpeechTimeoutMs = 6500;
    const speechThreshold = 0.03;

    const tick = () => {
      if (!isCapturing() || !callActiveRef.current) return;
      analyser.getByteTimeDomainData(samples);
      let total = 0;
      for (const sample of samples) {
        const centered = (sample - 128) / 128;
        total += centered * centered;
      }
      const rms = Math.sqrt(total / samples.length);
      const now = performance.now();
      peakRmsRef.current = Math.max(peakRmsRef.current, rms);

      const bargeInArmed = !agentSpeakingRef.current || now >= bargeInArmedAtRef.current;
      const activeThreshold = agentSpeakingRef.current ? 0.075 : speechThreshold;
      if (bargeInArmed && rms >= activeThreshold) {
        if (speechStartedAtRef.current === null) speechStartedAtRef.current = now;
        heardSpeechRef.current = true;
        speechFrameCountRef.current += 1;
        bargeInFrameCountRef.current += 1;
        silenceStartedAtRef.current = null;
        if (agentSpeakingRef.current && bargeInFrameCountRef.current >= 8) {
          interruptAssistantPlayback();
        }
      } else {
        bargeInFrameCountRef.current = 0;
        if (heardSpeechRef.current && silenceStartedAtRef.current === null) {
          silenceStartedAtRef.current = now;
        }
      }

      const speechStartedAt = speechStartedAtRef.current ?? startedAt;
      const hasMinimumTurn = now - speechStartedAt >= minTurnMs;
      const hasSilence = silenceStartedAtRef.current !== null && now - silenceStartedAtRef.current >= silenceMs;
      const hitMaxTurn = heardSpeechRef.current && now - speechStartedAt >= maxTurnMs;
      const hitNoSpeechTimeout = (
        !agentSpeakingRef.current
        && !heardSpeechRef.current
        && now - startedAt >= noSpeechTimeoutMs
      );
      if (hitNoSpeechTimeout && voiceSocketRef.current?.readyState === WebSocket.OPEN) {
        void stopTurnRecording(false).then(() => {
          if (voiceSocketRef.current?.readyState === WebSocket.OPEN) {
            setVoiceBusy(true);
            setVoiceStatus("Checking the connection...");
            voiceSocketRef.current.send(JSON.stringify({ type: "silence-turn" }));
          }
        });
        return;
      }
      if ((hasMinimumTurn && heardSpeechRef.current && hasSilence) || hitMaxTurn) {
        void stopTurnRecording();
        return;
      }
      analyserFrameRef.current = requestAnimationFrame(tick);
    };

    analyserFrameRef.current = requestAnimationFrame(tick);
  }

  const runSimulation = async () => {
    setRunning(true);
    setError(null);
    try {
      const token = await auth.getAccessToken();
      const response = await fetch("/api/v1/porter-local/web-call-simulations", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          lead_id: Number(leadId) || undefined,
          user_turns: [firstTurn, secondTurn].filter(Boolean),
          synthesize_audio: audioEnabled,
          use_live_llm: voiceMode === "live",
          mock_llm_response: "I can capture this and send it to the Porter team for review.",
        }),
      });
      const data = await parseApiResponse<SimulationResponse>(response);
      const newSession = normaliseSession({
        ...data.summary,
        id: data.summary.call_session_id ?? Date.now(),
        transcript: data.transcript,
        created_at: new Date().toISOString(),
      });
      setSessions((current) => [newSession, ...current].slice(0, 25));
      setSelectedId(newSession.id ?? newSession.call_session_id ?? 0);
      setApiState("live");
    } catch (err) {
      setApiState("offline");
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 lg:px-8">
      <section className="flex flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1 border-cta/40 text-cta">
              <Headphones className="h-3.5 w-3.5" />
              Porter voice ops
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "gap-1",
                apiState === "live" && "border-emerald-500/50 text-emerald-300",
                apiState === "offline" && "border-amber-500/50 text-amber-300",
              )}
            >
              {apiState === "checking" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
              {apiState === "live" ? "API live" : apiState === "offline" ? "Demo data" : "Checking API"}
            </Badge>
          </div>
          <div>
            <h1 className="text-3xl font-semibold tracking-normal md:text-4xl">
              Porter command console
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Run local web-call simulations, inspect transcripts, watch latency and quality signals, and keep production-readiness checks visible while the knowledge base stays in placeholder mode.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="icon" onClick={loadSessions} disabled={apiState === "checking"}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Refresh call sessions</TooltipContent>
          </Tooltip>
          <Button className="gap-2 bg-cta text-cta-foreground hover:bg-cta/90" onClick={runSimulation} disabled={running || !auth.isAuthenticated}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run simulation
          </Button>
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error.replace(/[.\s]+$/, "")}. Showing local demo data so the console remains testable.</span>
        </div>
      )}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile icon={PhoneCall} label="Reviewed sessions" value={String(metrics.total)} sublabel="Live and test call history" />
        <MetricTile icon={Gauge} label="Evaluation score" value={metrics.averageScore === undefined ? "n/a" : `${metrics.averageScore}%`} sublabel="Policy, outcome, and handoff quality" tone={scoreTone(metrics.averageScore)} />
        <MetricTile icon={TimerReset} label="Avg latency" value={formatMs(metrics.avgLatency)} sublabel="Assistant response pipeline" />
        <MetricTile icon={CheckCircle2} label="Qualified rate" value={`${metrics.conversion}%`} sublabel="Interested or follow-up outcomes" tone="text-emerald-300" />
      </section>

      <Tabs defaultValue="operate" className="gap-5">
        <TabsList className="w-full justify-start overflow-x-auto rounded-md bg-muted/70 md:w-fit">
          <TabsTrigger value="operate" className="gap-2"><Mic className="h-4 w-4" />Operate</TabsTrigger>
          <TabsTrigger value="observability" className="gap-2"><BarChart3 className="h-4 w-4" />Observability</TabsTrigger>
          <TabsTrigger value="readiness" className="gap-2"><ShieldCheck className="h-4 w-4" />Readiness</TabsTrigger>
        </TabsList>

        <TabsContent value="operate" className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
          <section className="space-y-5">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Mic className="h-4 w-4 text-emerald-300" />
                  Live local voice
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Button
                    className="gap-2 bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
                    onClick={startCall}
                    disabled={callActive || voiceBusy || !auth.isAuthenticated}
                  >
                    {callActive ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />}
                    Start call
                  </Button>
                  <Button
                    variant="outline"
                    className="gap-2"
                    onClick={endCall}
                    disabled={!callActive && !recording && !voiceBusy}
                  >
                    <XCircle className="h-4 w-4" />
                    End call
                  </Button>
                </div>
                <div className="rounded-md border border-border/70 p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">{voiceStatus}</span>
                    {(voiceBusy || recording) && <Loader2 className="h-4 w-4 animate-spin text-cta" />}
                  </div>
                  {liveCallSessionId && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      Session {liveCallSessionId}
                    </div>
                  )}
                </div>
                {lastLiveTurn && (
                  <div className="space-y-3 rounded-md border border-border/70 p-3">
                    <div>
                      <div className="mb-1 text-xs uppercase text-muted-foreground">Heard</div>
                      <p className="text-sm leading-6">{lastLiveTurn.user_text}</p>
                    </div>
                    <div>
                      <div className="mb-1 text-xs uppercase text-muted-foreground">Reply</div>
                      <p className="text-sm leading-6">{lastLiveTurn.assistant_text}</p>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">STT {String(lastLiveTurn.stt.adapter_name ?? "unknown")}</Badge>
                      <Badge variant="outline">TTS {lastLiveTurn.tts.adapter_name ?? "unknown"}</Badge>
                      <Badge variant="outline">LLM {lastLiveTurn.llm.model ?? "unknown"}</Badge>
                      {LIVE_TIMING_STAGES.map((stage) => {
                        const elapsed = lastLiveTurn.timings_ms?.[stage];
                        return typeof elapsed === "number" ? (
                          <Badge key={stage} variant="outline">{stage} {formatMs(elapsed)}</Badge>
                        ) : null;
                      })}
                      {typeof lastLiveTurn.timings_ms?.total === "number" && (
                        <Badge variant="outline">Total {Math.round(lastLiveTurn.timings_ms.total)} ms</Badge>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Bot className="h-4 w-4 text-cta" />
                  Simulation setup
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="porter-lead-id">Lead ID</Label>
                    <Input
                      id="porter-lead-id"
                      value={leadId}
                      onChange={(event) => setLeadId(event.target.value)}
                      inputMode="numeric"
                      placeholder="Auto-load mock lead"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Model mode</Label>
                    <Select value={voiceMode} onValueChange={setVoiceMode}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="mock">Deterministic mock</SelectItem>
                        <SelectItem value="live">Local Ollama</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2">
                  <div className="flex items-center gap-2 text-sm">
                    <Volume2 className="h-4 w-4 text-muted-foreground" />
                    TTS audio synthesis
                  </div>
                  <Switch checked={audioEnabled} onCheckedChange={setAudioEnabled} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="porter-turn-one">Caller turn 1</Label>
                  <Textarea id="porter-turn-one" value={firstTurn} onChange={(event) => setFirstTurn(event.target.value)} className="min-h-24 resize-none" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="porter-turn-two">Caller turn 2</Label>
                  <Textarea id="porter-turn-two" value={secondTurn} onChange={(event) => setSecondTurn(event.target.value)} className="min-h-24 resize-none" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Database className="h-4 w-4 text-sky-300" />
                  Integration gates
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                <IntegrationRow label="Telephony outbound" enabled={false} detail="Blocked until real provider credentials are connected." />
                <IntegrationRow label="CRM sync" enabled={false} detail="Salesforce adapter is designed, not enabled." />
                <IntegrationRow label="Email follow-up" enabled={false} detail="Placeholder only until provider approval." />
                <IntegrationRow label="SMS follow-up" enabled={false} detail="Placeholder only until provider approval." />
                <IntegrationRow label="Knowledge base" enabled={false} detail="Placeholder corpus; retrieval surface is ready." />
              </CardContent>
            </Card>
          </section>

          <section className="grid min-w-0 gap-5 2xl:grid-cols-[minmax(0,1fr)_380px]">
            <Card className="min-w-0">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4 text-emerald-300" />
                  Transcript review
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant="outline">Session {selectedSession?.id ?? "demo"}</Badge>
                  <span>{humanise(selectedSession?.outcome || selectedSession?.disposition)}</span>
                  <span>{formatDuration(selectedSession?.duration_seconds)}</span>
                </div>
                <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                  {reviewLoading && (
                    <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading transcript...
                    </div>
                  )}
                  {!reviewLoading && transcript.length === 0 && (
                    <p className="py-8 text-sm text-muted-foreground">No transcript is available for this session.</p>
                  )}
                  {!reviewLoading && transcript.map((turn, index) => {
                    const speaker = turn.speaker || turn.role || "assistant";
                    const isAssistant = speaker.toLowerCase().includes("assistant");
                    return (
                      <div
                        key={`${speaker}-${index}`}
                        className={cn(
                          "rounded-md border p-3",
                          isAssistant
                            ? "border-emerald-500/20 bg-emerald-500/5"
                            : "border-sky-500/20 bg-sky-500/5",
                        )}
                      >
                        <div className="mb-2 flex items-center justify-between gap-3 text-xs uppercase text-muted-foreground">
                          <span className="font-medium tracking-wide">{isAssistant ? "Porter" : "Caller"}</span>
                          <span>{turn.latency_ms ? formatMs(turn.latency_ms) : turn.audio_seconds ? `${turn.audio_seconds}s audio` : ""}</span>
                        </div>
                        <p className="text-sm leading-6">{turn.text || turn.content || "No transcript text captured."}</p>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Clock3 className="h-4 w-4 text-amber-300" />
                  Recent calls
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Call</TableHead>
                      <TableHead>Outcome</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sessions.map((session) => {
                      const id = session.id ?? session.call_session_id ?? 0;
                      return (
                        <TableRow
                          key={id}
                          className={cn("cursor-pointer", selectedId === id && "bg-muted/70")}
                          onClick={() => setSelectedId(id)}
                        >
                          <TableCell>
                            <div className="font-medium">#{id}</div>
                            <div className="text-xs text-muted-foreground">Lead {session.lead_id ?? "n/a"}</div>
                          </TableCell>
                          <TableCell className="capitalize">{humanise(session.outcome || session.disposition)}</TableCell>
                          <TableCell className={cn("text-right font-semibold", scoreTone(session.evaluation_score))}>
                            {session.evaluation_score ?? "n/a"}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </section>
        </TabsContent>

        <TabsContent value="observability" className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Gauge className="h-4 w-4 text-sky-300" />
                Latency windows
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[340px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={LATENCY_DATA} margin={{ left: -20, right: 18, top: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                  <XAxis dataKey="window" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12} />
                  <ChartTooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                  <Line type="monotone" dataKey="p50" stroke="#34d399" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="p90" stroke="#fbbf24" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="ttfw" stroke="#60a5fa" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-emerald-300" />
                Outcomes
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[340px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={outcomeData} margin={{ left: -20, right: 18, top: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} />
                  <ChartTooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {outcomeData.map((entry, index) => (
                      <Cell key={entry.name} fill={OUTCOME_COLORS[index % OUTCOME_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-cta" />
                Quality trend
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sessions.map((session, index) => ({ name: `Call ${sessions.length - index}`, score: session.evaluation_score ?? 0 }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis domain={[0, 100]} tickLine={false} axisLine={false} fontSize={12} />
                  <ChartTooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                  <Area type="monotone" dataKey="score" stroke="#fbbf24" fill="#fbbf24" fillOpacity={0.18} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="readiness" className="grid gap-5 lg:grid-cols-3">
          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-3 text-base">
                <span className="flex items-center gap-2">
                  <Headphones className="h-4 w-4 text-emerald-300" />
                  Voice runtime
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={prewarmRuntime}
                  disabled={!auth.isAuthenticated || prewarming}
                >
                  {prewarming ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Prewarm
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="grid gap-3 md:grid-cols-3">
                {(runtimeReadiness?.components ?? []).map((component) => (
                  <div key={component.name} className="rounded-md border border-border/70 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-sm font-medium uppercase">{component.name}</div>
                      {component.ready ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-amber-300" />
                      )}
                    </div>
                    <div className="text-sm">{component.provider}</div>
                    <div className="truncate text-xs text-muted-foreground">{component.model}</div>
                    <Badge variant="outline" className="mt-3">
                      {component.production_recommended ? "Production path" : "Test/demo path"}
                    </Badge>
                  </div>
                ))}
              </div>
              <div className="rounded-md border border-border/70 p-3 text-sm">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="font-medium">Latency target</span>
                  <Badge variant="outline">{runtimeReadiness?.recommended_target_ms ?? 500} ms</Badge>
                </div>
                <div className="text-muted-foreground">
                  Default voice: {runtimeReadiness?.default_voice ?? "unknown"}
                </div>
                <div className="mt-1 text-muted-foreground">
                  Fast mode: {runtimeReadiness?.fast_voice_mode ? "on" : "off"}
                </div>
                {lastPrewarm && (
                  <div className="mt-3 rounded-md bg-muted/50 p-2 text-xs text-muted-foreground">
                    {lastPrewarm.cache_hit_count}/{lastPrewarm.warmed_count} scripts served from cache in{" "}
                    {Math.round(lastPrewarm.total_elapsed_ms)} ms.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
          <ReadinessPanel title="Runtime" icon={Bot} items={[
            ["Local LLM", "Ollama opt-in", true],
            ["Deterministic tests", "Default path", true],
            ["Interruption path", "VAD module ready", true],
          ]} />
          <ReadinessPanel title="Safety" icon={ShieldCheck} items={[
            ["Policy checks", "No unsupported claims", true],
            ["PII handling", "No external sync by default", true],
            ["Provider actions", "Require approval", false],
          ]} />
          <ReadinessPanel title="Data" icon={Database} items={[
            ["Mock lead set", "Loaded locally", true],
            ["Knowledge base", "Placeholder", false],
            ["CRM writeback", "Design only", false],
          ]} />
        </TabsContent>
      </Tabs>
    </main>
  );
}

function MetricTile({
  icon: Icon,
  label,
  value,
  sublabel,
  tone = "text-foreground",
}: {
  icon: typeof PhoneCall;
  label: string;
  value: string;
  sublabel: string;
  tone?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border/70 bg-muted/40">
          <Icon className="h-5 w-5 text-cta" />
        </div>
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className={cn("text-2xl font-semibold", tone)}>{value}</div>
          <div className="truncate text-xs text-muted-foreground">{sublabel}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function IntegrationRow({ label, enabled, detail }: { label: string; enabled: boolean; detail: string }) {
  const Icon = integrationIcon(enabled);
  return (
    <div className="flex items-start gap-3 rounded-md border border-border/70 p-3">
      <Icon className={cn("mt-0.5 h-4 w-4", enabled ? "text-emerald-300" : "text-amber-300")} />
      <div className="min-w-0">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs leading-5 text-muted-foreground">{detail}</div>
      </div>
    </div>
  );
}

function ReadinessPanel({
  title,
  icon: Icon,
  items,
}: {
  title: string;
  icon: typeof Bot;
  items: Array<[string, string, boolean]>;
}) {
  const complete = items.filter((item) => item[2]).length;
  const progress = Math.round((complete / items.length) * 100);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3 text-base">
          <span className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-cta" />
            {title}
          </span>
          <span className="text-sm text-muted-foreground">{progress}%</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={progress} className="[&_[data-slot=progress-indicator]]:bg-cta" />
        <div className="space-y-3">
          {items.map(([name, detail, done]) => (
            <div key={name} className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium">{name}</div>
                <div className="text-xs text-muted-foreground">{detail}</div>
              </div>
              {done ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <AlertTriangle className="h-4 w-4 text-amber-300" />}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
