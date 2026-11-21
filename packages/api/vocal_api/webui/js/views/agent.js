// Voice Agent — realtime loop: mic → VAD → STT → LLM → pipelined TTS.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, toast, field, select, badge, fmtMs } from "../ui.js";
import { createMicCapture, base64FromBuffer, floatToPCM16, PCMPlayer } from "../audio.js";
import { createMicPicker, createLevelMeter, createVoiceIndicator, getSavedMic } from "../mic.js";

const LANGUAGES = [["", "Auto-detect"], ["en", "English"], ["es", "Spanish"], ["fr", "French"], ["de", "German"], ["zh", "Chinese"], ["ja", "Japanese"]];

export function render(container) {
  let ws = null;
  let mic = null;
  let player = new PCMPlayer(24000);
  let active = false;
  let assistantBubble = null;
  let assistantText = "";
  let partialUserLine = null;
  let responseGotContent = false;

  const sttSelect = select([]);
  const ttsSelect = select([]);
  const voiceSelect = select([{ value: "", label: "Model default voice" }]);
  const langSelect = select(LANGUAGES.map(([value, label]) => ({ value, label })));
  const promptArea = el("textarea", { class: "textarea", rows: "3", placeholder: "System prompt for the voice agent" });

  const sessionBtn = el("button", { class: "btn btn-primary w-full", onclick: toggle }, el("span", { html: iconSvg("bot", 16) }), "Start session");
  const cancelBtn = el("button", { class: "btn btn-danger btn-sm hidden", onclick: () => send({ type: "response.cancel" }) }, el("span", { html: iconSvg("stop", 14) }), "Interrupt");
  const statusBadge = el("span", {}, badge("idle", ""));
  const micPicker = createMicPicker();
  const meter = createLevelMeter(12);
  const voiceInd = createVoiceIndicator();

  const convoBox = el("div", { class: "transcript-box", style: { maxHeight: "440px", minHeight: "300px" } });
  const convoHint = el("p", { class: "text-xs text-[#8a8a8a]", text: "Start a session and speak. Your words are transcribed, answered by the configured LLM, and spoken back — interrupt anytime by talking." });
  convoBox.append(convoHint);

  function setStatus(text, kind) {
    clear(statusBadge).append(badge(text, kind));
  }

  function setLevel(level) {
    const voice = meter.set(level, active);
    voiceInd.set(active ? (voice ? "voice" : "listening") : "idle");
  }

  function scrollConvo() {
    convoBox.scrollTop = convoBox.scrollHeight;
  }

  function addUserMessage(text) {
    convoHint.classList.add("hidden");
    if (partialUserLine) {
      partialUserLine.remove();
      partialUserLine = null;
    }
    convoBox.append(el("div", { class: "msg msg-user", text }));
    scrollConvo();
  }

  function ensureAssistantBubble() {
    if (!assistantBubble) {
      assistantText = "";
      assistantBubble = el("div", { class: "msg msg-assistant" }, el("span", { class: "text-white" }));
      convoBox.append(assistantBubble);
    }
    return assistantBubble;
  }

  function appendAssistant(delta) {
    const bubble = ensureAssistantBubble();
    assistantText += delta;
    bubble.firstChild.textContent = assistantText;
    scrollConvo();
  }

  function finishAssistant(transcript) {
    if (transcript && assistantBubble) {
      assistantText = transcript;
      assistantBubble.firstChild.textContent = transcript;
    }
    assistantBubble = null;
    assistantText = "";
    scrollConvo();
  }

  function addMetrics(metrics) {
    const chips = el("div", { class: "msg-meta" },
      badge(`stt ${fmtMs(metrics.stt_ms)}`, "blue"),
      metrics.llm_first_token_ms != null ? badge(`llm ${fmtMs(metrics.llm_first_token_ms)}`, "") : null,
      metrics.ttfa_ms >= 0 ? badge(`first audio ${fmtMs(metrics.ttfa_ms)}`, "accent") : null,
      badge(`total ${fmtMs(metrics.response_total_ms)}`, "green")
    );
    convoBox.append(chips);
    scrollConvo();
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }

  async function loadVoices() {
    const model = ttsSelect.value;
    const current = voiceSelect.value;
    clear(voiceSelect).append(el("option", { value: "", label: "Model default voice" }));
    if (!model) return;
    try {
      const data = await api.listVoices(model);
      for (const v of data.voices || []) {
        voiceSelect.append(el("option", { value: v.id, text: `${v.name} · ${v.language}${v.gender ? ` · ${v.gender}` : ""}` }));
      }
      if ([...voiceSelect.options].some((o) => o.value === current)) voiceSelect.value = current;
    } catch {
      /* voices optional */
    }
  }

  function fillModels() {
    const stt = store.byTask("stt");
    const tts = store.byTask("tts");
    const curStt = sttSelect.value;
    const curTts = ttsSelect.value;
    clear(sttSelect);
    clear(ttsSelect);
    for (const m of stt) sttSelect.append(el("option", { value: m.id, text: m.name }));
    ttsSelect.append(el("option", { value: "pyttsx3", text: "pyttsx3 — system voices" }));
    for (const m of tts) {
      // The realtime pipeline streams PCM; WAV-only models cannot speak here.
      const canPcm = !m.output_formats || !m.output_formats.length || m.output_formats.includes("pcm");
      ttsSelect.append(el("option", { value: m.id, text: `${m.name}${canPcm ? "" : " — no PCM output"}`, disabled: !canPcm }));
    }
    sttSelect.value = curStt && stt.some((m) => m.id === curStt) ? curStt : (stt[0] ? stt[0].id : "");
    const settingsTts = store.settings && store.settings.TTS_DEFAULT_MODEL;
    const usable = (v) => [...ttsSelect.options].some((o) => o.value === v && !o.disabled);
    ttsSelect.value = curTts && usable(curTts) ? curTts : settingsTts && usable(settingsTts) ? settingsTts : "pyttsx3";
    if (store.settings && !promptArea.value) promptArea.value = store.settings.CHAT_SYSTEM_PROMPT || "";
    sessionBtn.disabled = !stt.length;
    if (!stt.length) toast("Install an STT model to use the voice agent", "info");
  }

  async function start() {
    active = true;
    sessionBtn.disabled = true;
    clear(sessionBtn).append(el("span", { class: "spinner-inline" }), "Connecting…");
    setStatus("connecting", "amber");
    sttSelect.disabled = ttsSelect.disabled = voiceSelect.disabled = langSelect.disabled = promptArea.disabled = micPicker.disabled = true;

    player = new PCMPlayer(24000);
    player.onStateChange = (playing) => {
      if (!active) return;
      if (playing) setStatus("speaking", "accent");
      else setStatus("listening", "green");
    };

    ws = new WebSocket(api.wsUrl("/v1/realtime", { model: sttSelect.value }));

    ws.onopen = async () => {
      send({
        type: "session.update",
        session: {
          type: "realtime",
          model: sttSelect.value,
          language: langSelect.value || null,
          tts_model: ttsSelect.value,
          tts_voice: voiceSelect.value || null,
          system_prompt: promptArea.value,
          input_sample_rate: mic ? mic.sampleRate : 48000,
        },
      });
      try {
        const wantedDevice = getSavedMic();
        mic = createMicCapture({
          chunkMs: 100,
          deviceId: wantedDevice,
          onChunk: (floats, rate) => {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            send({ type: "input_audio_buffer.append", audio: base64FromBuffer(floatToPCM16(floats)) });
          },
          onLevel: setLevel,
        });
        await mic.start();
        micPicker.refresh();
        if (wantedDevice && !mic.deviceId) {
          toast("Selected microphone unavailable — using system default", "info", 4000);
        }
        voiceInd.set("listening");
        // Correct the declared rate now that the AudioContext exists.
        send({ type: "session.update", session: { input_sample_rate: mic.sampleRate } });
        setStatus("listening", "green");
        clear(sessionBtn).append(el("span", { html: iconSvg("stop", 16) }), "End session");
        sessionBtn.disabled = false;
        sessionBtn.classList.remove("btn-primary");
        sessionBtn.classList.add("btn-danger");
        cancelBtn.classList.remove("hidden");
      } catch (e) {
        toast(`Microphone unavailable: ${e.message}`, "error", 6500);
        stop();
      }
    };

    ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      switch (msg.type) {
        case "ping":
          send({ type: "pong" });
          break;
        case "session.created":
        case "session.resumed":
        case "session.updated":
          break;
        case "input_audio_buffer.speech_started":
          player.flush(); // barge-in: stop the agent immediately
          setStatus("listening", "green");
          cancelBtn.classList.add("hidden");
          if (!partialUserLine) {
            partialUserLine = el("div", { class: "msg msg-user", style: { opacity: "0.6", fontStyle: "italic" } });
            convoHint.classList.add("hidden");
            convoBox.append(partialUserLine);
          }
          partialUserLine.textContent = "…";
          scrollConvo();
          break;
        case "input_audio_buffer.speech_stopped":
          setStatus("transcribing", "blue");
          break;
        case "conversation.item.input_audio_transcription.delta":
          if (partialUserLine && msg.partial_transcript) {
            partialUserLine.textContent = msg.partial_transcript;
            scrollConvo();
          }
          break;
        case "conversation.item.input_audio_transcription.completed":
          if (msg.transcript && msg.transcript.trim()) addUserMessage(msg.transcript.trim());
          else if (partialUserLine) {
            partialUserLine.remove();
            partialUserLine = null;
          }
          break;
        case "response.created":
          setStatus("thinking", "amber");
          cancelBtn.classList.remove("hidden");
          responseGotContent = false;
          ensureAssistantBubble();
          break;
        case "response.output_audio_transcript.delta":
          if (msg.delta) responseGotContent = true;
          appendAssistant(msg.delta || "");
          break;
        case "response.output_audio_transcript.done":
          finishAssistant(msg.transcript);
          break;
        case "response.output_audio.delta":
          responseGotContent = true;
          player.enqueue(msg.delta);
          break;
        case "response.output_audio.done":
          break;
        case "response.metrics":
          addMetrics(msg.metrics || {});
          break;
        case "response.done":
          cancelBtn.classList.add("hidden");
          if (!responseGotContent) {
            if (assistantBubble) {
              assistantBubble.remove();
              assistantBubble = null;
              assistantText = "";
            }
            convoBox.append(
              el("div", { class: "msg msg-assistant", style: { borderLeftColor: "var(--warning)", color: "var(--warning)" } },
                "The LLM returned an empty response. Check the LLM endpoint and model in Settings (the default expects Ollama at localhost:11434).")
            );
            scrollConvo();
          }
          if (active && !player.playing) setStatus("listening", "green");
          break;
        case "response.cancelled":
          player.flush();
          cancelBtn.classList.add("hidden");
          finishAssistant(assistantText ? `${assistantText} …` : "");
          if (active) setStatus("listening", "green");
          break;
        case "error": {
          const err = msg.error || {};
          toast(err.message || "Realtime error", "error", 6500);
          if (err.code === "response_failed") {
            // The pipeline aborted mid-response: reset turn state and explain.
            cancelBtn.classList.add("hidden");
            if (assistantBubble) {
              assistantBubble.remove();
              assistantBubble = null;
              assistantText = "";
            }
            convoBox.append(
              el("div", { class: "msg msg-assistant", style: { borderLeftColor: "var(--warning)", color: "var(--warning)" } },
                "The voice response failed — usually the LLM endpoint is unreachable. Check Settings → Voice agent LLM.")
            );
            scrollConvo();
            if (active) setStatus("listening", "green");
          }
          break;
        }
        default:
          break;
      }
    };

    ws.onerror = () => {
      if (active) toast("WebSocket error — is the server running?", "error");
    };
    ws.onclose = () => {
      if (active) stop();
    };
  }

  async function stop() {
    active = false;
    setStatus("idle", "");
    setLevel(0);
    cancelBtn.classList.add("hidden");
    sttSelect.disabled = ttsSelect.disabled = voiceSelect.disabled = langSelect.disabled = promptArea.disabled = micPicker.disabled = false;
    sessionBtn.disabled = false;
    sessionBtn.classList.add("btn-primary");
    sessionBtn.classList.remove("btn-danger");
    clear(sessionBtn).append(el("span", { html: iconSvg("bot", 16) }), "Start session");
    if (mic) {
      const m = mic;
      mic = null;
      await m.stop();
    }
    if (ws) {
      const sock = ws;
      ws = null;
      sock.onclose = null;
      try {
        sock.close();
      } catch {
        /* already closed */
      }
    }
    await player.close();
    if (partialUserLine) {
      partialUserLine.remove();
      partialUserLine = null;
    }
    assistantBubble = null;
  }

  function toggle() {
    if (active) stop();
    else start();
  }

  const llmHint = el("p", { class: "field-hint" });
  function drawLlmHint() {
    const s = store.settings;
    llmHint.textContent = s
      ? `LLM backend: ${s.LLM_BASE_URL} · model ${s.LLM_MODEL}. Change it in Settings.`
      : "The agent answers through the LLM endpoint configured in Settings.";
  }

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Voice Agent" }),
      el("p", { text: "Full realtime conversation over /v1/realtime: server VAD, streaming STT, LLM reasoning and sentence-pipelined TTS with barge-in." })
    ),
    el("div", { class: "grid gap-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,5fr)]" },
      el("div", { class: "panel" },
        el("div", { class: "panel-title", html: iconSvg("sliders", 15) + "<span>Pipeline</span>" }),
        el("div", { class: "form-grid" },
          field("STT model", sttSelect),
          field("TTS model", ttsSelect),
          field("TTS voice", voiceSelect),
          field("Language", langSelect),
          field("Microphone source", micPicker),
          field("System prompt", promptArea),
          llmHint,
          sessionBtn,
          el("div", { class: "flex items-center justify-between gap-4 pt-1" },
            el("div", { class: "flex flex-col gap-2" },
              el("div", { class: "flex items-center gap-2" }, statusBadge, voiceInd.el),
              meter.el
            ),
            cancelBtn
          )
        )
      ),
      el("div", { class: "panel" },
        el("div", { class: "panel-title", html: iconSvg("bot", 15) + "<span>Conversation</span>" }),
        convoBox
      )
    )
  );

  ttsSelect.addEventListener("change", loadVoices);
  fillModels();
  loadVoices();
  drawLlmHint();
  let lastDataVersion = store.dataVersion;
  const unsub = store.subscribe(() => {
    if (active || store.dataVersion === lastDataVersion) return;
    lastDataVersion = store.dataVersion;
    fillModels();
    drawLlmHint();
  });
  if (!store.settings) store.refreshSettings().catch(() => {});

  return () => {
    unsub();
    stop();
    micPicker.destroy();
  };
}
