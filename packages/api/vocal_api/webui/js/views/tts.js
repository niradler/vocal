// TTS Studio — synthesize speech with any installed model.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, toast, field, select, badge, downloadBlob, fmtSeconds } from "../ui.js";
import { PCMPlayer } from "../audio.js";

const SAMPLE = "Vocal turns text into speech on your own hardware. No cloud, no waiting, no per-character billing.";
const FORMATS = ["mp3", "wav", "opus", "flac", "aac", "pcm"];

export function render(container, params = {}) {
  let busy = false;
  let player = null;
  let objectUrl = null;

  const modelSelect = select([], { onchange: () => { loadVoices(); syncFormats(); } });
  const voiceSelect = select([{ value: "", label: "Model default voice" }]);
  const speedRange = el("input", { type: "range", min: "0.25", max: "4", step: "0.05", value: "1", "aria-label": "Speech speed" });
  const speedValue = el("span", { class: "text-xs text-accent", text: "1.00×" });
  speedRange.addEventListener("input", () => { speedValue.textContent = `${parseFloat(speedRange.value).toFixed(2)}×`; });
  const formatSelect = select(FORMATS, { value: "mp3" });
  const formatHint = el("p", { class: "field-hint" });
  const streamCheck = el("input", { type: "checkbox", id: "tts-stream", class: "h-4 w-4 cursor-pointer accent-[#76B900]" });
  const textArea = el("textarea", { class: "textarea", rows: "6", placeholder: "Type or paste the text to synthesize…", maxlength: "5000" });
  const charCount = el("span", { class: "text-[10px] text-[#8a8a8a]", text: "0 / 5000" });
  textArea.addEventListener("input", () => { charCount.textContent = `${textArea.value.length} / 5000`; });

  const generateBtn = el("button", { class: "btn btn-primary w-full", onclick: generate }, el("span", { html: iconSvg("speaker", 16) }), "Generate speech");
  const resultPanel = el("div", { class: "panel" });
  const errorPanel = el("div", { class: "hidden" });

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "TTS Studio" }),
      el("p", { text: "OpenAI-compatible /v1/audio/speech. Pick an installed model, choose a voice, and synthesize." })
    ),
    el("div", { class: "grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)]" },
      el("div", { class: "panel" },
        el("div", { class: "panel-title", html: iconSvg("sliders", 15) + "<span>Synthesis parameters</span>" }),
        el("div", { class: "form-grid" },
          field("Model", modelSelect, "Installed TTS models. Pull more from the catalog."),
          field("Voice", voiceSelect),
          el("div", {},
            el("div", { class: "flex items-center justify-between" }, el("label", { class: "label", text: "Speed" }), speedValue),
            speedRange
          ),
          el("div", { class: "form-grid cols-2" },
            el("div", {}, field("Format", formatSelect), formatHint),
            el("div", {},
              el("label", { class: "label", text: "Transfer" }),
              el("label", { class: "flex cursor-pointer items-center gap-2 rounded-lg border border-[#3a3a3a] bg-coal px-3 py-2.5 text-xs text-lightgrey transition-all hover:border-accent" },
                streamCheck, "Stream chunks")
            )
          ),
          el("div", {},
            el("div", { class: "flex items-center justify-between" },
              el("label", { class: "label", text: "Input text" }),
              el("button", { class: "cursor-pointer text-[10px] uppercase tracking-widest text-accent transition-all hover:underline", onclick: () => { textArea.value = SAMPLE; textArea.dispatchEvent(new Event("input")); }, text: "Insert sample" })
            ),
            textArea,
            el("div", { class: "mt-1 flex justify-end" }, charCount)
          ),
          generateBtn
        )
      ),
      el("div", { class: "flex flex-col gap-4" }, resultPanel, errorPanel)
    )
  );

  function syncFormats() {
    const m = store.findModel(modelSelect.value);
    const supported = m && m.output_formats && m.output_formats.length ? m.output_formats : FORMATS;
    const current = formatSelect.value;
    clear(formatSelect);
    for (const f of FORMATS) {
      const ok = supported.includes(f);
      formatSelect.append(el("option", { value: f, text: ok ? f : `${f} — unsupported`, disabled: !ok }));
    }
    formatSelect.value = supported.includes(current) ? current : supported.includes("mp3") ? "mp3" : supported[0];
    formatHint.textContent = supported.length < FORMATS.length ? `This model only outputs: ${supported.join(", ")}.` : "";
  }

  function fillModels() {
    const tts = store.byTask("tts");
    const opts = [{ value: "pyttsx3", label: "pyttsx3 — system voices (no download)" }];
    for (const m of tts) opts.push({ value: m.id, label: `${m.name} (${m.size_readable || ""})` });
    clear(modelSelect);
    for (const o of opts) modelSelect.append(el("option", { value: o.value, text: o.label }));
    const wanted = params.get("model");
    modelSelect.value = wanted && opts.some((o) => o.value === wanted) ? wanted : opts[0].value;
    loadVoices();
    syncFormats();
  }

  async function loadVoices() {
    const model = modelSelect.value;
    const previousVoice = voiceSelect.value;
    clear(voiceSelect).append(el("option", { value: "", label: "Model default voice" }));
    if (!model) return;
    try {
      const data = await api.listVoices(model);
      for (const v of data.voices || []) {
        voiceSelect.append(el("option", { value: v.id, text: `${v.name} · ${v.language}${v.gender ? ` · ${v.gender}` : ""}` }));
      }
      if (!(data.voices || []).length) {
        voiceSelect.append(el("option", { value: "", label: "No selectable voices for this model", disabled: true }));
      }
      // Keep the user's choice when the voice still exists for this model.
      if (previousVoice && [...voiceSelect.options].some((o) => o.value === previousVoice)) {
        voiceSelect.value = previousVoice;
      }
    } catch (e) {
      toast(`Could not load voices: ${e.message}`, "error");
    }
  }

  function showResult({ blob, duration, sampleRate, format, elapsedMs, streamedBytes }) {
    clear(resultPanel);
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(blob);
    const audio = el("audio", { controls: true, src: objectUrl, class: "w-full" });
    resultPanel.append(
      el("div", { class: "panel-title", html: iconSvg("check", 15) + "<span>Output</span>" }),
      el("div", { class: "audio-result" }, audio),
      el("div", { class: "chip-row mt-4" },
        badge(format, "accent"),
        duration ? badge(fmtSeconds(duration), "blue") : null,
        sampleRate ? badge(`${sampleRate} Hz`, "") : null,
        badge(`${(blob.size / 1024).toFixed(1)} KB`, ""),
        elapsedMs != null ? badge(`generated in ${(elapsedMs / 1000).toFixed(2)}s`, "green") : null,
        streamedBytes != null ? badge(`streamed ${(streamedBytes / 1024).toFixed(1)} KB`, "blue") : null
      ),
      el("button", { class: "btn btn-ghost btn-sm mt-4", onclick: () => downloadBlob(blob, `speech.${format === "pcm" ? "raw" : format}`) },
        el("span", { html: iconSvg("download", 14) }), "Download audio")
    );
    audio.play().catch(() => {});
  }

  function showError(msg) {
    clear(errorPanel);
    errorPanel.classList.remove("hidden");
    errorPanel.append(
      el("div", { class: "rounded-lg border border-[rgba(255,92,92,0.4)] bg-[rgba(255,92,92,0.07)] p-4" },
        el("p", { class: "flex items-center gap-2 text-xs font-semibold text-[#ff5c5c]" }, el("span", { html: iconSvg("alert", 14) }), "Synthesis failed"),
        el("p", { class: "mt-2 text-xs leading-relaxed text-lightgrey", text: msg })
      )
    );
  }

  async function generate() {
    if (busy) return;
    const input = textArea.value.trim();
    if (!input) return toast("Enter some text first", "info");
    busy = true;
    generateBtn.disabled = true;
    clear(generateBtn).append(el("span", { class: "spinner-inline" }), "Synthesizing…");
    errorPanel.classList.add("hidden");
    // Don't leave the previous take on screen while a new one is generating.
    clear(resultPanel).append(
      el("div", { class: "empty-state", style: { padding: "2rem 1rem" } },
        el("span", { class: "spinner-inline" }),
        el("p", { class: "text-xs", text: "Synthesizing…" })
      )
    );
    const started = performance.now();
    const format = formatSelect.value;
    const stream = streamCheck.checked;

    try {
      if (stream && format === "pcm") {
        // Live playback: play PCM chunks as they arrive at the server's rate.
        player = null;
        const result = await api.speech({
          model: modelSelect.value,
          input,
          voice: voiceSelect.value || null,
          speed: parseFloat(speedRange.value),
          response_format: "pcm",
          stream: true,
          onChunk: (bytes, _received, rate) => {
            if (!player) player = new PCMPlayer(rate || 24000);
            player.enqueue(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
          },
        });
        showResult({ ...result, format: "pcm", elapsedMs: performance.now() - started, streamedBytes: result.bytes });
      } else {
        const result = await api.speech({
          model: modelSelect.value,
          input,
          voice: voiceSelect.value || null,
          speed: parseFloat(speedRange.value),
          response_format: format,
          stream,
        });
        showResult({ ...result, elapsedMs: performance.now() - started, streamedBytes: stream ? result.blob.size : null });
      }
    } catch (e) {
      showError(e.message);
      toast(e.message, "error", 6500);
    } finally {
      busy = false;
      generateBtn.disabled = false;
      clear(generateBtn).append(el("span", { html: iconSvg("speaker", 16) }), "Generate speech");
    }
  }

  clear(resultPanel).append(
    el("div", { class: "empty-state", style: { padding: "2rem 1rem" } },
      el("span", { html: iconSvg("speaker", 40) }),
      el("p", { class: "text-sm font-semibold text-white", text: "Output appears here" }),
      el("p", { class: "text-xs", text: "Generate speech to play and download it." })
    )
  );

  fillModels();
  let lastDataVersion = store.dataVersion;
  const unsub = store.subscribe(() => {
    if (store.dataVersion === lastDataVersion) return;
    lastDataVersion = store.dataVersion;
    const current = modelSelect.value;
    fillModels();
    if ([...modelSelect.options].some((o) => o.value === current)) modelSelect.value = current;
    syncFormats();
  });

  return () => {
    unsub();
    if (player) player.close();
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  };
}
