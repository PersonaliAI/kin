"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Room,
  RoomEvent,
  Track,
  type RemoteTrack,
  type RemoteParticipant,
  ConnectionState,
  type TranscriptionSegment,
  type Participant,
} from "livekit-client";
import { Mic, MicOff, PhoneOff, Loader2, AlertCircle, PhoneCall } from "lucide-react";
import { cn } from "@/lib/utils";
import { Dialog } from "./dialog";
import { voiceAgentsApi, type VoiceAgent } from "@/lib/backend";

type CallStatus = "connecting" | "requesting-mic" | "connected" | "listening" | "agent-speaking" | "error" | "ended";

interface TranscriptEntry {
  id: string;
  speaker: "you" | "agent";
  text: string;
  final: boolean;
}

/**
 * "Test in browser" — joins the same LiveKit room/worker agent a real phone
 * call would, but from the dashboard's own mic/speaker via livekit-client,
 * no phone number or telephony provider required. This is what makes a
 * voice agent testable the moment it's created; the phone-based Test Call
 * button needs a provisioned number first, which needs Twilio/Telnyx
 * configured — a real barrier most users hit before ever hearing their
 * agent talk. Mirrors chatty's voice-call-widget.tsx (same LiveKit
 * primitives, same call-state machine), simplified for this dashboard's
 * shadcn-style design system instead of chatty's per-preset theming.
 */
export function VoiceAgentTestCallDialog({ agent, open, onClose }: { agent: VoiceAgent | null; open: boolean; onClose: () => void }) {
  const t = useTranslations("dashboard.voiceAgents.testCallDialog");
  const [status, setStatus] = useState<CallStatus>("connecting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);

  const roomRef = useRef<Room | null>(null);
  const audioElRef = useRef<HTMLMediaElement | null>(null);
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open || !agent) return;
    mountedRef.current = true;
    let cancelled = false;
    setStatus("connecting");
    setErrorMessage(null);
    setDuration(0);
    setTranscript([]);

    async function start() {
      let room: Room | null = null;
      try {
        const { token, url } = await voiceAgentsApi.webCall(agent!.id);

        room = new Room();
        roomRef.current = room;

        room.on(RoomEvent.Disconnected, () => {
          if (!cancelled && mountedRef.current) setStatus((s) => (s === "error" ? s : "ended"));
        });

        room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
          if (cancelled || !mountedRef.current) return;
          if (state === ConnectionState.Connected) {
            setStatus((s) => (s === "agent-speaking" ? s : "connected"));
          }
        });

        room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _pub, participant: RemoteParticipant) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            el.autoplay = true;
            audioElRef.current = el;
            document.body.appendChild(el);
            void participant;
          }
        });

        room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
          track.detach().forEach((el) => el.remove());
        });

        // Segments carry no explicit role — attribute by participant: no
        // participant (or the local one) means it's your own speech-to-text.
        room.on(
          RoomEvent.TranscriptionReceived,
          (segments: TranscriptionSegment[], participant?: Participant) => {
            if (cancelled || !mountedRef.current) return;
            const speaker: "you" | "agent" =
              !participant || participant.identity === room?.localParticipant?.identity ? "you" : "agent";
            setTranscript((prev) => {
              const next = [...prev];
              for (const seg of segments) {
                const idx = next.findIndex((e) => e.id === seg.id);
                const entry: TranscriptEntry = { id: seg.id, speaker, text: seg.text, final: seg.final };
                if (idx >= 0) next[idx] = entry;
                else next.push(entry);
              }
              return next;
            });
          },
        );

        room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
          if (cancelled || !mountedRef.current) return;
          const localIdentity = room?.localParticipant?.identity;
          let remoteSpeaking = false;
          let localSpeaking = false;
          for (const p of speakers) {
            if (p.identity === localIdentity) localSpeaking = true;
            else remoteSpeaking = true;
          }
          setStatus((prev) => {
            if (prev === "connecting" || prev === "requesting-mic" || prev === "error" || prev === "ended") return prev;
            if (remoteSpeaking) return "agent-speaking";
            if (localSpeaking) return "listening";
            return "connected";
          });
        });

        await room.connect(url, token);
        if (cancelled) {
          room.disconnect();
          return;
        }
        if (!cancelled && mountedRef.current) setStatus("requesting-mic");
        try {
          await room.localParticipant.setMicrophoneEnabled(true);
        } catch (micErr) {
          console.error("Microphone permission failed:", micErr);
          if (!cancelled && mountedRef.current) {
            setErrorMessage(t("micDenied"));
            setStatus("error");
          }
          room.disconnect();
          return;
        }
        if (!cancelled && mountedRef.current) setStatus("connected");
      } catch (err) {
        console.error("Voice agent test call failed to start:", err);
        if (!cancelled && mountedRef.current) {
          setErrorMessage(err instanceof Error ? err.message : t("startFailed"));
          setStatus("error");
        }
        room?.disconnect();
      }
    }

    start();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      const room = roomRef.current;
      roomRef.current = null;
      if (room) {
        room.localParticipant.setMicrophoneEnabled(false).catch(() => {});
        room.disconnect();
      }
      if (audioElRef.current) {
        audioElRef.current.remove();
        audioElRef.current = null;
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    };
  }, [open, agent]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript]);

  useEffect(() => {
    if (status === "connecting" || status === "requesting-mic" || status === "error") return;
    if (status === "ended") {
      if (durationIntervalRef.current) clearInterval(durationIntervalRef.current);
      return;
    }
    if (!durationIntervalRef.current) {
      durationIntervalRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
    }
    return () => {
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
    };
  }, [status]);

  async function toggleMute() {
    const room = roomRef.current;
    if (!room) return;
    const next = !muted;
    await room.localParticipant.setMicrophoneEnabled(!next);
    setMuted(next);
  }

  function handleHangup() {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) {
      room.localParticipant.setMicrophoneEnabled(false).catch(() => {});
      room.disconnect();
    }
    onClose();
  }

  const mm = String(Math.floor(duration / 60)).padStart(2, "0");
  const ss = String(duration % 60).padStart(2, "0");

  const statusLabel: Record<CallStatus, string> = {
    connecting: t("statusConnecting"),
    "requesting-mic": t("statusRequestingMic"),
    connected: t("statusConnected"),
    listening: t("statusListening"),
    "agent-speaking": t("statusAgentSpeaking"),
    error: t("statusError"),
    ended: t("statusEnded"),
  };

  if (!agent) return null;

  return (
    <Dialog open={open} onClose={handleHangup} title={t("title", { name: agent.name })} size="md">
      <div className="px-5 pb-5 space-y-4">
        <div className="flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3 py-2.5">
          <div className="flex items-center gap-2 text-sm">
            {status === "error" ? (
              <AlertCircle className="size-4 text-destructive" />
            ) : status === "connecting" || status === "requesting-mic" ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            ) : (
              <span className={cn("size-2 rounded-full", status === "agent-speaking" ? "bg-emerald-500 animate-pulse" : "bg-emerald-500")} />
            )}
            <span className={status === "error" ? "text-destructive" : "text-foreground"}>{statusLabel[status]}</span>
          </div>
          {status !== "connecting" && status !== "requesting-mic" && status !== "error" && (
            <span className="text-xs text-muted-foreground font-mono">{mm}:{ss}</span>
          )}
        </div>

        {errorMessage && (
          <div className="text-xs text-destructive flex items-start gap-1.5 bg-destructive/10 border border-destructive/20 rounded-xl p-3">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div className="h-64 overflow-y-auto rounded-xl border border-border bg-muted/20 p-3 space-y-2">
          {transcript.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground text-center px-6">
              {status === "connecting" || status === "requesting-mic" ? t("waitingForCall") : t("startTalking")}
            </div>
          ) : (
            transcript.map((entry) => (
              <div key={entry.id} className={cn("flex", entry.speaker === "you" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-3 py-1.5 text-sm",
                    entry.speaker === "you" ? "bg-foreground text-background" : "bg-card border border-border",
                    !entry.final && "opacity-60",
                  )}
                >
                  {entry.text}
                </div>
              </div>
            ))
          )}
          <div ref={transcriptEndRef} />
        </div>

        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={toggleMute}
            disabled={status === "connecting" || status === "requesting-mic" || status === "error" || status === "ended"}
            className="flex items-center justify-center size-11 rounded-full border border-border bg-card hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            aria-label={muted ? t("unmute") : t("mute")}
            title={muted ? t("unmute") : t("mute")}
          >
            {muted ? <MicOff className="size-4.5" /> : <Mic className="size-4.5" />}
          </button>
          <button
            type="button"
            onClick={handleHangup}
            className="flex items-center justify-center size-11 rounded-full bg-destructive text-destructive-foreground hover:opacity-90 transition-opacity cursor-pointer"
            aria-label={t("hangup")}
            title={t("hangup")}
          >
            <PhoneOff className="size-4.5" />
          </button>
        </div>
      </div>
    </Dialog>
  );
}

/** Small trigger button — drop next to the existing phone-based Test Call
 * action in the voice agent card. */
export function TestInBrowserButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  const t = useTranslations("dashboard.voiceAgents");
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-border text-xs font-medium hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
    >
      <PhoneCall className="size-3.5" />
      {t("testInBrowser")}
    </button>
  );
}
