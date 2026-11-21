// Live Dictation — streaming microphone transcription over /v1/audio/stream.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, toast, field, select, badge, copyText, timestamp } from "../ui.js";
import { createMicCapture, resampleLinear, floatToPCM16 } from "../audio.js";
import { createMicPicker, createLevelMeter, createVoiceIndicator, getSavedMic } from "../mic.js";

const TARGET_RATE = 16000;
const LANGUAGES = [["", "Auto-detect"], ["en", "English"], ["es", "Spanish"], ["fr", "French"], ["de", "German"], ["it", "Italian"], ["pt", "Portuguese"], ["zh", "Chinese"], ["ja", "Japanese"], ["ko", "Korean"], ["ru", "Russian"], ["ar", "Arabic"], ["hi", "Hindi"]];

export function render(container) {
  let ws = null;
  let mic = null;
  let active = false;
  let finalized = [];
  let currentParts = [];
  let partialText = "";

  const modelSelect = select([]);
  const langSelect = select(LANGUAGES.map(([value, label]) => ({ value, label })));
  const thresholdRange = el("input", { type: "range", min: "0.1", max: "0.9", step: "0.05", value: "0.5", "aria-label": "Speech threshold" });
  const thresholdValue = el("span", { class: "text-xs text-accent", text: "0.50" });
  thresholdRange.addEventListener("input", () => { thresholdValue.textContent = parseFloat(thresholdRange.value).toFixed(2); });
  const silenceRange = el("input", { type: "range", min: "0.2", max: "3", step: "0.1", value: "0.8", "aria-label": "Silence duration" });
  const silenceValue = el("span", { class: "text-xs text-accent", text: "0.8s" });
  silenceRange.addEventListener("input", () => { silenceValue.textContent = `${parseFloat(silenceRange.value).toFixed(1)}s`; });

  const micBtn = el("button", { class: "mic-btn", "aria-label": "Start live transcription", onclick: toggle }, el("span", { html: iconSvg("mic", 28) }));
  const statusBadge = el("span", {}, badge("idle", ""));
  const micPicker = createMicPicker();
  const meter = createLevelMeter(16);
  const voiceInd = createVoiceIndicator();

  const transcriptBox = el("div", { class: "transcript-box", style: { maxHeight: "380px" } });
  const partialLine = el("p", { class: "partial-line hidden" });
  const currentLine = el("p", { class: "hidden text-white" });
  const emptyHint = el("p", { class: "text-xs text-[#8a8a8a]", text: "Start the microphone and speak. Finalized utterances appear here; blue italics are live partial hypotheses." });
  transcriptBox.append(emptyHint, currentLine, partialLine);

  const copyBtn = el("button", { class: "btn btn-ghost btn-sm", onclick: () => copyText(finalized.join("\n")) }, el("span", { html: iconSvg("copy", 14) }), "Copy all");
  const clearBtn = el("button", { class: "btn btn-ghost btn-sm", onclick: () => { finalized = []; redraw(); } }, el("span", { html: iconSvg("trash", 14) }), "Clear");

  function setStatus(text, kind) {
    clear(statusBadge).append(badge(text, kind));
  }

  function redraw() {
    for (const node of [...transcriptBox.querySelectorAll(".transcript-line")]) node.remove();
    const frag = document.createDocumentFragment();
    for (const line of finalized) {
      frag.append(el("p", { class: "transcript-line" }, el("span", { class: "transcript-time", text: line.time }), line.text));
    }
    transcriptBox.insertBefore(frag, currentLine);
    emptyHint.classList.toggle("hidden", finalized.length > 0 || currentParts.length > 0 || !!partialText);
    currentLine.classList.toggle("hidden", currentParts.length === 0);
    currentLine.textContent = currentParts.join(" ");
    partialLine.classList.toggle("hidden", !partialText);
    partialLine.textContent = partialText;
    transcriptBox.scrollTop = transcriptBox.scrollHeight;
  }

  function setLevel(level) {
    const voice = meter.set(level, active);
    voiceInd.set(active ? (voice ? "voice" : "listening") : "idle");
  }

  function fillModels() {
    const stt = store.byTask("stt");
    const current = modelSelect.value;
    clear(modelSelect);
    if (!stt.length) {
      modelSelect.append(el("option", { value: "", label: "No STT models installed" }));
      micBtn.disabled = true;
      return;
    }
    micBtn.disabled = false;
    for (const m of stt) {
      modelSelect.append(el("option", { value: m.id, text: `${m.name}${m.supports_live_streaming ? " · live" : ""}` }));
    }
    modelSelect.value = current && stt.some((m) => m.id === current) ? current : stt[0].id;
  }

  async function start() {
    if (!modelSelect.value) return toast("Install an STT model first", "info");
    active = true;
    micBtn.classList.add("live");
    clear(micBtn).append(el("span", { html: iconSvg("stop", 28) }));
    setStatus("connecting", "amber");
    modelSelect.disabled = langSelect.disabled = thresholdRange.disabled = silenceRange.disabled = micPicker.disabled = true;

    ws = new WebSocket(api.wsUrl("/v1/audio/stream", {
      model: modelSelect.value,
      language: langSelect.value || null,
      silence_duration: silenceRange.value,
      threshold: thresholdRange.value,
    }));
    ws.binaryType = "arraybuffer";

    ws.onopen = async () => {
      setStatus("listening", "green");
      try {
        const wantedDevice = getSavedMic();
        mic = createMicCapture({
          chunkMs: 100,
          deviceId: wantedDevice,
          onChunk: (floats, rate) => {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            const resampled = resampleLinear(floats, rate, TARGET_RATE);
            ws.send(floatToPCM16(resampled));
          },
          onLevel: setLevel,
        });
        await mic.start();
        micPicker.refresh();
        if (wantedDevice && !mic.deviceId) {
          toast("Selected microphone unavailable — using system default", "info", 4000);
        }
        voiceInd.set("listening");
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
      if (msg.type === "transcript.delta") {
        if (msg.partial) {
          partialText = msg.text || "";
        } else if (msg.text) {
          currentParts.push(msg.text);
          partialText = "";
        }
        redraw();
      } else if (msg.type === "transcript.done") {
        const text = (msg.text || currentParts.join(" ")).trim();
        if (text) finalized.push({ time: timestamp(), text });
        currentParts = [];
        partialText = "";
        redraw();
      } else if (msg.type === "error") {
        toast(msg.message || "Stream error", "error", 6500);
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
    micBtn.classList.remove("live");
    clear(micBtn).append(el("span", { html: iconSvg("mic", 28) }));
    setStatus("idle", "");
    setLevel(0);
    modelSelect.disabled = langSelect.disabled = thresholdRange.disabled = silenceRange.disabled = micPicker.disabled = false;
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
    // Flush any in-progress utterance into the log.
    const text = currentParts.join(" ").trim();
    if (text) finalized.push({ time: timestamp(), text });
    currentParts = [];
    partialText = "";
    redraw();
  }

  function toggle() {
    if (active) stop();
    else start();
  }

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Live Dictation" }),
      el("p", { text: "Server-side VAD segments your speech and transcribes each utterance over a WebSocket. Partial hypotheses stream while you talk." })
    ),
    el("div", { class: "grid gap-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,5fr)]" },
      el("div", { class: "panel" },
        el("div", { class: "panel-title", html: iconSvg("sliders", 15) + "<span>Session</span>" }),
        el("div", { class: "form-grid" },
          field("Model", modelSelect, "Models marked “live” decode chunk-by-chunk; others commit on silence."),
          field("Language", langSelect),
          field("Microphone source", micPicker),
          el("div", {}, el("div", { class: "flex items-center justify-between" }, el("label", { class: "label", text: "Speech threshold" }), thresholdValue), thresholdRange),
          el("div", {}, el("div", { class: "flex items-center justify-between" }, el("label", { class: "label", text: "Silence commit" }), silenceValue), silenceRange),
          el("div", { class: "flex items-center gap-5 pt-2" },
            micBtn,
            el("div", { class: "flex flex-col gap-2" },
              el("div", { class: "flex items-center gap-2" }, statusBadge, voiceInd.el),
              meter.el
            )
          )
        )
      ),
      el("div", { class: "panel" },
        el("div", { class: "flex items-center justify-between" },
          el("div", { class: "panel-title mb-0", html: iconSvg("activity", 15) + "<span>Transcript</span>" }),
          el("div", { class: "flex gap-2" }, copyBtn, clearBtn)
        ),
        el("div", { class: "mt-4" }, transcriptBox)
      )
    )
  );

  fillModels();
  let lastDataVersion = store.dataVersion;
  const unsub = store.subscribe(() => {
    if (store.dataVersion === lastDataVersion) return;
    lastDataVersion = store.dataVersion;
    fillModels();
  });

  return () => {
    unsub();
    stop();
    micPicker.destroy();
  };
}
