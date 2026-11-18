// Transcribe — upload or record audio, run STT/translation, view segments.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, toast, field, select, badge, downloadBlob, copyText, fmtSeconds, emptyState } from "../ui.js";
import { createMicCapture, resampleLinear, floatToPCM16, encodeWav } from "../audio.js";
import { createMicPicker, createLevelMeter, createVoiceIndicator, getSavedMic } from "../mic.js";

const LANGUAGES = [
  ["", "Auto-detect"], ["en", "English"], ["es", "Spanish"], ["fr", "French"], ["de", "German"],
  ["it", "Italian"], ["pt", "Portuguese"], ["nl", "Dutch"], ["ru", "Russian"], ["zh", "Chinese"],
  ["ja", "Japanese"], ["ko", "Korean"], ["ar", "Arabic"], ["hi", "Hindi"], ["tr", "Turkish"],
  ["pl", "Polish"], ["uk", "Ukrainian"], ["he", "Hebrew"], ["sv", "Swedish"], ["cs", "Czech"],
];
const STT_FORMATS = [
  { value: "verbose_json", label: "verbose_json — text + segments" },
  { value: "json", label: "json — full JSON payload" },
  { value: "text", label: "text — plain text" },
  { value: "srt", label: "srt — subtitles" },
  { value: "vtt", label: "vtt — web subtitles" },
];
const TARGET_RATE = 16000;

export function render(container, params = {}) {
  let sourceBlob = null;
  let sourceName = "audio.wav";
  let mic = null;
  let recChunks = [];
  let recRate = TARGET_RATE;
  let recTimer = null;
  let recSeconds = 0;
  let busy = false;
  let previewUrl = null;

  const modelSelect = select([]);
  const langSelect = select(LANGUAGES.map(([value, label]) => ({ value, label })));
  const formatSelect = select(STT_FORMATS, { value: "verbose_json" });
  const tempRange = el("input", { type: "range", min: "0", max: "1", step: "0.1", value: "0", "aria-label": "Temperature" });
  const tempValue = el("span", { class: "text-xs text-accent", text: "0.0" });
  tempRange.addEventListener("input", () => { tempValue.textContent = parseFloat(tempRange.value).toFixed(1); });
  const promptInput = el("input", { class: "input", type: "text", placeholder: "Optional style/vocabulary prompt" });
  const modeTranscribe = el("button", { class: "tab active", text: "Transcribe", onclick: () => setMode("transcribe") });
  const modeTranslate = el("button", { class: "tab", text: "Translate → EN", onclick: () => setMode("translate") });
  let mode = "transcribe";

  const runBtn = el("button", { class: "btn btn-primary w-full", onclick: run }, el("span", { html: iconSvg("file", 16) }), "Run transcription");
  const resultPanel = el("div", { class: "panel" });

  // ---- source tabs ----
  const uploadTab = el("button", { class: "tab active", text: "Upload file", onclick: () => setSourceTab("upload") });
  const recordTab = el("button", { class: "tab", text: "Record mic", onclick: () => setSourceTab("record") });
  const uploadZone = el("div", {});
  const recordZone = el("div", { class: "hidden" });
  const fileInput = el("input", { type: "file", accept: "audio/*,.mp3,.mp4,.wav,.m4a,.flac,.ogg,.webm", class: "hidden", onchange: (e) => e.target.files[0] && setFile(e.target.files[0], e.target.files[0].name) });

  const dropzone = el("div", { class: "dropzone", role: "button", tabindex: "0", "aria-label": "Upload audio file" },
    el("span", { html: iconSvg("upload", 32) }),
    el("p", { class: "text-sm font-semibold text-white", text: "Drop audio here or click to browse" }),
    el("p", { class: "mt-1 text-xs text-[#8a8a8a]", text: "mp3 · mp4 · wav · m4a · flac · ogg · webm — max 25 MB" })
  );
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setFile(f, f.name);
  });
  const fileInfo = el("div", { class: "mt-3 hidden" });
  uploadZone.append(dropzone, fileInput, fileInfo);

  // ---- record zone ----
  const micBtn = el("button", { class: "mic-btn", "aria-label": "Start recording", onclick: toggleRecord }, el("span", { html: iconSvg("mic", 28) }));
  const recStatus = el("p", { class: "text-xs text-lightgrey", text: "Press to record. Press again to stop." });
  const recTime = el("p", { class: "text-lg font-bold text-accent", text: "0.0s" });
  const recPreview = el("div", { class: "mt-3 hidden w-full" });
  const micPicker = createMicPicker();
  const recMeter = createLevelMeter(16);
  const recVoice = createVoiceIndicator();
  recordZone.append(
    el("div", { class: "mb-2" }, el("label", { class: "label", text: "Microphone source" }), micPicker),
    el("div", { class: "flex flex-col items-center gap-3 py-4" },
      micBtn,
      recTime,
      el("div", { class: "flex items-center gap-4" }, recVoice.el, recMeter.el),
      recStatus
    ),
    recPreview
  );

  function setSourceTab(which) {
    uploadTab.classList.toggle("active", which === "upload");
    recordTab.classList.toggle("active", which === "record");
    uploadZone.classList.toggle("hidden", which !== "upload");
    recordZone.classList.toggle("hidden", which !== "record");
    if (which === "upload" && mic) stopRecording();
  }

  function setFile(blob, name = null) {
    if (blob.size > 25 * 1024 * 1024) return toast("File exceeds the 25 MB limit", "error");
    sourceBlob = blob;
    sourceName = name || "recording.wav";
    clear(fileInfo).classList.remove("hidden");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    fileInfo.append(
      el("div", { class: "flex items-center justify-between gap-3 rounded-lg border border-[#3a3a3a] bg-coal px-3 py-2" },
        el("div", { class: "min-w-0" },
          el("p", { class: "truncate text-xs font-semibold text-white", text: sourceName }),
          el("p", { class: "text-[10px] text-[#8a8a8a]", text: `${(blob.size / 1024).toFixed(1)} KB` })
        ),
        badge("ready", "green")
      ),
      el("audio", { controls: true, src: previewUrl, class: "mt-2 w-full", style: { height: "36px" } })
    );
    runBtn.disabled = false;
  }

  async function toggleRecord() {
    if (mic) return stopRecording();
    try {
      recChunks = [];
      recSeconds = 0;
      const wantedDevice = getSavedMic();
      mic = createMicCapture({
        chunkMs: 100,
        deviceId: wantedDevice,
        onChunk: (floats, rate) => {
          recRate = rate;
          const resampled = resampleLinear(floats, rate, TARGET_RATE);
          recChunks.push(floatToPCM16(resampled));
        },
        onLevel: (level) => {
          const voice = recMeter.set(level);
          recVoice.set(voice ? "voice" : "listening");
          recStatus.textContent = voice ? "Recording — voice detected." : "Recording… waiting for voice.";
        },
      });
      await mic.start();
      micPicker.refresh();
      if (wantedDevice && !mic.deviceId) {
        toast("Selected microphone unavailable — using system default", "info", 4000);
      }
      micPicker.disabled = true;
      recVoice.set("listening");
      micBtn.classList.add("recording");
      micBtn.setAttribute("aria-label", "Stop recording");
      clear(micBtn).append(el("span", { html: iconSvg("stop", 28) }));
      recStatus.textContent = "Recording… press to stop.";
      recTimer = setInterval(() => {
        recSeconds += 0.1;
        recTime.textContent = `${recSeconds.toFixed(1)}s`;
      }, 100);
    } catch (e) {
      mic = null;
      toast(`Microphone unavailable: ${e.message}`, "error", 6500);
    }
  }

  async function stopRecording() {
    if (!mic) return;
    clearInterval(recTimer);
    const m = mic;
    mic = null;
    await m.stop();
    micPicker.disabled = false;
    recMeter.set(0, false);
    recVoice.set("idle");
    micBtn.classList.remove("recording");
    micBtn.setAttribute("aria-label", "Start recording");
    clear(micBtn).append(el("span", { html: iconSvg("mic", 28) }));
    recStatus.textContent = "Press to record. Press again to stop.";
    const total = recChunks.reduce((n, b) => n + b.byteLength, 0);
    if (total < 3200) return toast("Recording too short", "info");
    const merged = new Uint8Array(total);
    let off = 0;
    for (const b of recChunks) {
      merged.set(new Uint8Array(b), off);
      off += b.byteLength;
    }
    const wav = encodeWav(merged.buffer, TARGET_RATE);
    setFile(wav, `recording-${Date.now()}.wav`);
    clear(recPreview).classList.remove("hidden");
    recPreview.append(el("p", { class: "text-center text-[10px] uppercase tracking-widest text-[#8a8a8a]", text: "recording captured — ready to transcribe" }));
  }

  function setMode(m) {
    mode = m;
    modeTranscribe.classList.toggle("active", m === "transcribe");
    modeTranslate.classList.toggle("active", m === "translate");
    clear(runBtn).append(el("span", { html: iconSvg("file", 16) }), m === "translate" ? "Translate to English" : "Run transcription");
  }

  function fillModels() {
    const stt = store.byTask("stt");
    const current = modelSelect.value;
    clear(modelSelect);
    if (!stt.length) {
      modelSelect.append(el("option", { value: "", label: "No STT models installed — pull one first" }));
      runBtn.disabled = true;
      return;
    }
    for (const m of stt) modelSelect.append(el("option", { value: m.id, text: `${m.name} (${m.backend})` }));
    const wanted = params.get("model");
    modelSelect.value = current && stt.some((m) => m.id === current)
      ? current
      : wanted && stt.some((m) => m.id === wanted)
        ? wanted
        : stt[0].id;
  }

  function renderResult(data, format, elapsedMs) {
    clear(resultPanel);
    const isText = typeof data === "string";
    const text = isText ? data : data.text || "";
    const ext = format === "verbose_json" || format === "json" ? "json" : format === "text" ? "txt" : format;
    const payload = isText ? data : JSON.stringify(data, null, 2);

    resultPanel.append(
      el("div", { class: "panel-title", html: iconSvg("check", 15) + "<span>Result</span>" }),
      el("div", { class: "chip-row mb-3" },
        badge(mode === "translate" ? "translation" : "transcription", "accent"),
        !isText && data.language ? badge(`lang: ${data.language}`, "blue") : null,
        !isText && data.duration ? badge(fmtSeconds(data.duration), "") : null,
        badge(`${(elapsedMs / 1000).toFixed(2)}s`, "green")
      ),
      el("div", { class: "transcript-box", style: { minHeight: "120px" } },
        el("p", { class: "whitespace-pre-wrap", text: text || "(empty transcript)" })
      ),
      el("div", { class: "mt-3 flex flex-wrap gap-2" },
        el("button", { class: "btn btn-ghost btn-sm", onclick: () => copyText(text) }, el("span", { html: iconSvg("copy", 14) }), "Copy text"),
        el("button", { class: "btn btn-ghost btn-sm", onclick: () => downloadBlob(new Blob([payload], { type: "text/plain" }), `transcript.${ext}`) }, el("span", { html: iconSvg("download", 14) }), `Download .${ext}`)
      )
    );

    const segments = !isText && data.segments;
    if (segments && segments.length) {
      const table = el("table", { class: "seg-table mt-5" },
        el("thead", {}, el("tr", {}, el("th", { text: "#" }), el("th", { text: "Start" }), el("th", { text: "End" }), el("th", { text: "Text" }))),
        el("tbody", {}, segments.map((s, i) =>
          el("tr", {},
            el("td", { text: String(i + 1) }),
            el("td", { text: fmtSeconds(s.start) }),
            el("td", { text: fmtSeconds(s.end) }),
            el("td", { text: s.text })
          )
        ))
      );
      resultPanel.append(el("p", { class: "label mt-5", text: `Segments (${segments.length})` }), el("div", { class: "overflow-x-auto" }, table));
    }
  }

  async function run() {
    if (busy) return;
    if (!sourceBlob) return toast("Upload or record audio first", "info");
    if (!modelSelect.value) return toast("Install an STT model first", "info");
    busy = true;
    runBtn.disabled = true;
    clear(runBtn).append(el("span", { class: "spinner-inline" }), "Processing…");
    const started = performance.now();
    const format = mode === "translate" ? "json" : formatSelect.value;
    try {
      const fd = new FormData();
      fd.append("file", sourceBlob, sourceName);
      fd.append("model", modelSelect.value);
      let data;
      if (mode === "translate") {
        data = await api.translate(fd);
      } else {
        if (langSelect.value) fd.append("language", langSelect.value);
        if (promptInput.value.trim()) fd.append("prompt", promptInput.value.trim());
        fd.append("response_format", format);
        fd.append("temperature", tempRange.value);
        data = await api.transcribe(fd, format === "text" || format === "srt" || format === "vtt");
      }
      renderResult(data, format, performance.now() - started);
    } catch (e) {
      toast(e.message, "error", 7000);
      clear(resultPanel).append(
        el("div", { class: "rounded-lg border border-[rgba(255,92,92,0.4)] bg-[rgba(255,92,92,0.07)] p-4 text-xs text-lightgrey" },
          el("p", { class: "mb-1 font-semibold text-[#ff5c5c]", text: "Transcription failed" }),
          el("p", { text: e.message })
        )
      );
    } finally {
      busy = false;
      runBtn.disabled = false;
      setMode(mode);
    }
  }

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Transcribe" }),
      el("p", { text: "OpenAI-compatible /v1/audio/transcriptions. Upload a file or record from the microphone." })
    ),
    el("div", { class: "grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)]" },
      el("div", { class: "flex flex-col gap-4" },
        el("div", { class: "panel" },
          el("div", { class: "mb-4 flex items-center justify-between gap-3" },
            el("div", { class: "panel-title mb-0", html: iconSvg("upload", 15) + "<span>Audio source</span>" }),
            el("div", { class: "tab-row" }, uploadTab, recordTab)
          ),
          uploadZone, recordZone
        ),
        el("div", { class: "panel" },
          el("div", { class: "panel-title", html: iconSvg("sliders", 15) + "<span>Parameters</span>" }),
          el("div", { class: "form-grid" },
            el("div", { class: "form-grid cols-2" }, field("Model", modelSelect), field("Language", langSelect)),
            el("div", { class: "form-grid cols-2" },
              field("Output format", formatSelect),
              el("div", {}, el("div", { class: "flex items-center justify-between" }, el("label", { class: "label", text: "Temperature" }), tempValue), tempRange)
            ),
            field("Prompt", promptInput, "Biases the decoder toward specific vocabulary or style."),
            el("div", {},
              el("label", { class: "label", text: "Task" }),
              el("div", { class: "tab-row" }, modeTranscribe, modeTranslate)
            ),
            runBtn
          )
        )
      ),
      resultPanel
    )
  );

  clear(resultPanel).append(emptyState("file", "Transcript appears here", "Results include plain text, JSON or subtitles with segment timing."));
  fillModels();
  let lastDataVersion = store.dataVersion;
  const unsub = store.subscribe(() => {
    if (store.dataVersion === lastDataVersion) return;
    lastDataVersion = store.dataVersion;
    fillModels();
  });

  return () => {
    unsub();
    if (mic) stopRecording();
    clearInterval(recTimer);
    micPicker.destroy();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  };
}
