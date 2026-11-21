// Voice Clone — reference-audio cloning via /v1/audio/clone.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, toast, field, select, badge, downloadBlob, fmtSeconds } from "../ui.js";
import { createMicCapture, resampleLinear, floatToPCM16, encodeWav, blobDuration } from "../audio.js";
import { createMicPicker, createLevelMeter, createVoiceIndicator, getSavedMic } from "../mic.js";

const TARGET_RATE = 16000;
const MIN_S = 3;
const MAX_SECONDS = 30;
const LANGUAGES = [["en", "English"], ["zh", "Chinese"], ["es", "Spanish"], ["fr", "French"], ["de", "German"], ["it", "Italian"], ["pt", "Portuguese"], ["ja", "Japanese"], ["ko", "Korean"], ["ru", "Russian"]];

export function render(container) {
  let refBlob = null;
  let refName = "reference.wav";
  let refSeconds = 0;
  let mic = null;
  let recChunks = [];
  let recTimer = null;
  let recSeconds = 0;
  let busy = false;
  let resultUrl = null;

  const modelSelect = select([]);
  const modelHint = el("p", { class: "field-hint" });
  const langSelect = select(LANGUAGES.map(([value, label]) => ({ value, label })), { value: "en" });
  const formatSelect = select(["wav", "mp3", "flac", "opus"], { value: "wav" });
  const refTextInput = el("input", { class: "input", type: "text", placeholder: "Optional transcript of the reference audio" });
  const textArea = el("textarea", { class: "textarea", rows: "4", placeholder: "Text to speak in the cloned voice…" });
  const runBtn = el("button", { class: "btn btn-primary w-full", onclick: run }, el("span", { html: iconSvg("copy", 16) }), "Clone & synthesize");
  const resultPanel = el("div", { class: "panel" });

  // ---- reference source ----
  const fileInput = el("input", { type: "file", accept: "audio/*,.wav,.mp3,.m4a,.aac,.flac,.opus,.ogg", class: "hidden", onchange: (e) => e.target.files[0] && setReference(e.target.files[0], e.target.files[0].name) });
  const dropzone = el("div", { class: "dropzone", role: "button", tabindex: "0" },
    el("span", { html: iconSvg("upload", 32) }),
    el("p", { class: "text-sm font-semibold text-white", text: "Reference recording" }),
    el("p", { class: "mt-1 text-xs text-[#8a8a8a]", text: `wav · mp3 · m4a — ${MIN_S} to ${MAX_SECONDS} seconds of clean speech` })
  );
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setReference(f, f.name);
  });

  const micBtn = el("button", { class: "mic-btn", style: { width: "52px", height: "52px" }, "aria-label": "Record reference", onclick: toggleRecord }, el("span", { html: iconSvg("mic", 22) }));
  const micPicker = createMicPicker();
  const recMeter = createLevelMeter(12);
  const recVoice = createVoiceIndicator();
  const refInfo = el("div", { class: "mt-3 hidden" });

  async function setReference(blob, name) {
    let seconds = 0;
    try {
      seconds = await blobDuration(blob);
    } catch {
      seconds = 0;
    }
    if (seconds && (seconds < MIN_S || seconds > MAX_SECONDS)) {
      return toast(`Reference must be ${MIN_S}–${MAX_SECONDS}s (got ${seconds.toFixed(1)}s)`, "error", 6000);
    }
    refBlob = blob;
    refName = name || "reference.wav";
    refSeconds = seconds;
    clear(refInfo).classList.remove("hidden");
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    const url = URL.createObjectURL(blob);
    refInfo.append(
      el("div", { class: "flex items-center justify-between gap-3 rounded-lg border border-[#3a3a3a] bg-coal px-3 py-2" },
        el("div", { class: "min-w-0" },
          el("p", { class: "truncate text-xs font-semibold text-white", text: refName }),
          el("p", { class: "text-[10px] text-[#8a8a8a]", text: seconds ? `${seconds.toFixed(1)}s · ${(blob.size / 1024).toFixed(1)} KB` : `${(blob.size / 1024).toFixed(1)} KB` })
        ),
        badge("reference ready", "green")
      ),
      el("audio", { controls: true, src: url, class: "mt-2 w-full", style: { height: "36px" } })
    );
  }

  async function toggleRecord() {
    if (mic) {
      clearInterval(recTimer);
      const m = mic;
      mic = null;
      await m.stop();
      micPicker.disabled = false;
      recMeter.set(0, false);
      recVoice.set("idle");
      micBtn.classList.remove("recording");
      clear(micBtn).append(el("span", { html: iconSvg("mic", 22) }));
      const total = recChunks.reduce((n, b) => n + b.byteLength, 0);
      const seconds = total / 2 / TARGET_RATE;
      if (seconds < MIN_S) return toast(`Recording too short — need at least ${MIN_S}s`, "info");
      if (seconds > MAX_SECONDS) return toast(`Recording too long — max ${MAX_SECONDS}s`, "error");
      const merged = new Uint8Array(total);
      let off = 0;
      for (const b of recChunks) {
        merged.set(new Uint8Array(b), off);
        off += b.byteLength;
      }
      setReference(encodeWav(merged.buffer, TARGET_RATE), `reference-${Date.now()}.wav`);
      return;
    }
    try {
      recChunks = [];
      recSeconds = 0;
      const wantedDevice = getSavedMic();
      mic = createMicCapture({
        chunkMs: 100,
        deviceId: wantedDevice,
        onChunk: (floats, rate) => {
          recChunks.push(floatToPCM16(resampleLinear(floats, rate, TARGET_RATE)));
          recSeconds += floats.length / rate;
          if (recSeconds > MAX_SECONDS + 1) toggleRecord();
        },
        onLevel: (level) => {
          const voice = recMeter.set(level);
          recVoice.set(voice ? "voice" : "listening");
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
      clear(micBtn).append(el("span", { html: iconSvg("stop", 22) }));
      recTimer = setInterval(() => {}, 1000); // keep-alive; duration tracked in onChunk
      toast(`Recording reference — speak for ${MIN_S}–${MAX_SECONDS}s, then press stop`, "info", 4000);
    } catch (e) {
      mic = null;
      toast(`Microphone unavailable: ${e.message}`, "error", 6500);
    }
  }

  function fillModels() {
    const cloneModels = store.catalog.filter((m) => m.supports_voice_clone);
    const installed = store.downloadedIds();
    const current = modelSelect.value;
    clear(modelSelect);
    if (!cloneModels.length) {
      modelSelect.append(el("option", { value: "", label: "No clone-capable models in catalog" }));
      return;
    }
    for (const m of cloneModels) {
      modelSelect.append(el("option", { value: m.id, text: `${m.name}${installed.has(m.id) ? "" : " — not downloaded"}` }));
    }
    const def = store.settings && store.settings.TTS_DEFAULT_CLONE_MODEL;
    modelSelect.value = current && cloneModels.some((m) => m.id === current)
      ? current
      : (def && cloneModels.some((m) => m.id === def) ? def : cloneModels[0].id);
    drawModelHint();
  }

  function drawModelHint() {
    const m = store.findModel(modelSelect.value);
    if (!m) {
      modelHint.textContent = "";
      return;
    }
    const installed = store.downloadedIds().has(m.id);
    clear(modelHint);
    if (!installed) {
      modelHint.append(
        "Model not downloaded. ",
        el("a", { href: `#/models?task=tts`, class: "cursor-pointer text-accent hover:underline", text: "Pull it from the catalog →" })
      );
    } else {
      modelHint.textContent = m.requires_gpu ? "Installed · requires CUDA GPU." : "Installed and ready.";
    }
  }

  async function run() {
    if (busy) return;
    if (!refBlob) return toast("Provide a reference recording first", "info");
    if (!textArea.value.trim()) return toast("Enter the text to synthesize", "info");
    if (!modelSelect.value) return toast("Select a clone-capable model", "info");
    busy = true;
    runBtn.disabled = true;
    clear(runBtn).append(el("span", { class: "spinner-inline" }), "Cloning voice…");
    const started = performance.now();
    try {
      const fd = new FormData();
      fd.append("reference_audio", refBlob, refName);
      fd.append("text", textArea.value.trim());
      fd.append("model", modelSelect.value);
      if (refTextInput.value.trim()) fd.append("reference_text", refTextInput.value.trim());
      fd.append("language", langSelect.value);
      fd.append("response_format", formatSelect.value);
      const result = await api.clone(fd);
      clear(resultPanel);
      if (resultUrl) URL.revokeObjectURL(resultUrl);
      resultUrl = URL.createObjectURL(result.blob);
      const audio = el("audio", { controls: true, src: resultUrl, class: "w-full" });
      resultPanel.append(
        el("div", { class: "panel-title", html: iconSvg("check", 15) + "<span>Cloned output</span>" }),
        el("div", { class: "audio-result" }, audio),
        el("div", { class: "chip-row mt-4" },
          badge(formatSelect.value, "accent"),
          result.duration ? badge(fmtSeconds(result.duration), "blue") : null,
          result.sampleRate ? badge(`${result.sampleRate} Hz`, "") : null,
          badge(`${((performance.now() - started) / 1000).toFixed(2)}s`, "green")
        ),
        el("button", { class: "btn btn-ghost btn-sm mt-4", onclick: () => downloadBlob(result.blob, `clone.${formatSelect.value}`) },
          el("span", { html: iconSvg("download", 14) }), "Download audio")
      );
      audio.play().catch(() => {});
    } catch (e) {
      toast(e.message, "error", 7500);
      clear(resultPanel).append(
        el("div", { class: "rounded-lg border border-[rgba(255,92,92,0.4)] bg-[rgba(255,92,92,0.07)] p-4 text-xs text-lightgrey" },
          el("p", { class: "mb-1 font-semibold text-[#ff5c5c]", text: "Cloning failed" }),
          el("p", { text: e.message })
        )
      );
    } finally {
      busy = false;
      runBtn.disabled = false;
      clear(runBtn).append(el("span", { html: iconSvg("copy", 16) }), "Clone & synthesize");
    }
  }

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Voice Clone" }),
      el("p", { text: `Upload or record ${MIN_S}–${MAX_SECONDS}s of a speaker, then synthesize any text in their voice. Requires a clone-capable model (Qwen3-TTS base variants, CUDA).` })
    ),
    el("div", { class: "grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)]" },
      el("div", { class: "flex flex-col gap-4" },
        el("div", { class: "panel" },
          el("div", { class: "panel-title", html: iconSvg("mic", 15) + "<span>Reference voice</span>" }),
          dropzone, fileInput,
          el("div", { class: "mt-4" }, el("label", { class: "label", text: "Microphone source" }), micPicker),
          el("div", { class: "mt-3 flex items-center gap-4" },
            micBtn,
            el("div", { class: "flex flex-col gap-2" },
              recVoice.el,
              recMeter.el,
              el("p", { class: "text-xs text-[#8a8a8a]", text: "…or record a reference directly from the microphone." })
            )
          ),
          refInfo
        ),
        el("div", { class: "panel" },
          el("div", { class: "panel-title", html: iconSvg("sliders", 15) + "<span>Synthesis</span>" }),
          el("div", { class: "form-grid" },
            field("Clone model", modelSelect),
            modelHint,
            field("Reference transcript", refTextInput, "Optional — improves cloning accuracy when provided."),
            field("Text to speak", textArea),
            el("div", { class: "form-grid cols-2" }, field("Language", langSelect), field("Format", formatSelect)),
            runBtn
          )
        )
      ),
      resultPanel
    )
  );

  clear(resultPanel).append(
    el("div", { class: "empty-state", style: { padding: "2rem 1rem" } },
      el("span", { html: iconSvg("copy", 40) }),
      el("p", { class: "text-sm font-semibold text-white", text: "Cloned audio appears here" }),
      el("p", { class: "text-xs", text: "Cloning is hardware-intensive — first run loads the model." })
    )
  );

  modelSelect.addEventListener("change", drawModelHint);
  fillModels();
  let lastDataVersion = store.dataVersion;
  const unsub = store.subscribe(() => {
    if (store.dataVersion === lastDataVersion) return;
    lastDataVersion = store.dataVersion;
    fillModels();
  });
  if (!store.catalog.length) store.refreshModels().catch(() => {});
  if (!store.settings) store.refreshSettings().catch(() => {});

  return () => {
    unsub();
    if (mic) toggleRecord();
    clearInterval(recTimer);
    micPicker.destroy();
    if (resultUrl) URL.revokeObjectURL(resultUrl);
  };
}
