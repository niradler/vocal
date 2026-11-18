// Settings — configure Vocal defaults, VAD, realtime and the agent LLM.
import * as api from "../api.js";
import { store } from "../store.js";
import { el, clear, iconSvg, toast, field, select, badge } from "../ui.js";

const LANGS = [["", "Auto-detect"], ["en", "English"], ["es", "Spanish"], ["fr", "French"], ["de", "German"], ["it", "Italian"], ["pt", "Portuguese"], ["zh", "Chinese"], ["ja", "Japanese"], ["ko", "Korean"], ["ru", "Russian"], ["ar", "Arabic"], ["hi", "Hindi"]];
const MASK = "********";

export function render(container) {
  const form = el("div", {});
  const saveBtn = el("button", { class: "btn btn-primary", onclick: save }, el("span", { html: iconSvg("save", 16) }), "Save settings");
  const reloadBtn = el("button", { class: "btn btn-ghost", onclick: () => load(true) }, el("span", { html: iconSvg("refresh", 14) }), "Reload");
  const keyStatus = el("span", {});
  const inputs = {};

  function numInput(key, { min, max, step = 1, hint = "" }) {
    const input = el("input", { class: "input", type: "number", min, max, step, id: `set-${key}` });
    inputs[key] = input;
    return field(labelFor(key), input, hint);
  }
  function textInput(key, { placeholder = "", hint = "", list = null }) {
    const input = el("input", { class: "input", type: "text", placeholder, id: `set-${key}` });
    if (list) {
      const dl = el("datalist", { id: `dl-${key}` }, list.map((v) => el("option", { value: v })));
      input.setAttribute("list", `dl-${key}`);
      inputs[key] = input;
      return el("div", {}, field(labelFor(key), input, hint), dl);
    }
    inputs[key] = input;
    return field(labelFor(key), input, hint);
  }
  function rangeInput(key, { min, max, step, hint = "" }) {
    const wrap = el("div", {});
    const value = el("span", { class: "text-xs text-accent" });
    const input = el("input", { type: "range", min, max, step, id: `set-${key}`, "aria-label": labelFor(key) });
    input.addEventListener("input", () => { value.textContent = input.value; });
    inputs[key] = input;
    wrap.append(el("div", { class: "flex items-center justify-between" }, el("label", { class: "label", text: labelFor(key) }), value), input, hint ? el("p", { class: "field-hint", text: hint }) : null);
    return wrap;
  }

  const LABELS = {
    LLM_BASE_URL: "LLM base URL", LLM_MODEL: "LLM model", LLM_API_KEY: "LLM API key",
    STT_DEFAULT_MODEL: "Default STT model", STT_DEFAULT_LANGUAGE: "Default STT language",
    TTS_DEFAULT_MODEL: "Default TTS model", TTS_DEFAULT_VOICE: "Default TTS voice",
    TTS_DEFAULT_CLONE_MODEL: "Default clone model", DEFAULT_LANGUAGE: "Default language",
    VAD_SPEECH_THRESHOLD: "Silero speech threshold", VAD_THRESHOLD: "RMS fallback threshold",
    VAD_ONSET_MS: "Speech onset (ms)", VAD_SILENCE_MS: "Dictation silence (ms)",
    VAD_COMMIT_GRACE_MS: "Dictation grace (ms)", VAD_MIN_SPEECH_MS: "Min speech (ms)", VAD_PREROLL_MS: "Preroll (ms)",
    REALTIME_AGENT_SILENCE_MS: "Agent silence (ms)", REALTIME_AGENT_COMMIT_GRACE_MS: "Agent grace (ms)",
    REALTIME_PARTIAL_INTERVAL_S: "Partial interval (s)", REALTIME_MAX_UTTERANCE_S: "Max utterance (s)",
    CHAT_SYSTEM_PROMPT: "Agent system prompt", LOG_LEVEL: "Log level",
  };
  function labelFor(key) {
    return LABELS[key] || key;
  }

  function section(title, iconName, children, note = null) {
    return el("div", { class: "panel settings-section" },
      el("div", { class: "panel-title", html: iconSvg(iconName, 15) + `<span>${title}</span>` }),
      note ? el("p", { class: "mb-4 text-xs text-[#8a8a8a]", text: note }) : null,
      el("div", { class: "settings-grid" }, children)
    );
  }

  function buildForm(s) {
    clear(form);
    const sttIds = store.catalogByTask("stt").map((m) => m.id);
    const ttsIds = ["pyttsx3", ...store.catalogByTask("tts").map((m) => m.id)];
    const cloneIds = store.catalog.filter((m) => m.supports_voice_clone).map((m) => m.id);

    // API key (secret)
    const keyInput = el("input", { class: "input", type: "password", placeholder: s.llm_api_key_set ? "Key is set — type to replace" : "No key set", autocomplete: "new-password", id: "set-LLM_API_KEY" });
    inputs.LLM_API_KEY = keyInput;
    clear(keyStatus).append(s.llm_api_key_set ? badge("key configured", "green") : badge("no key", "amber"));

    // language selects
    const sttLang = select(LANGS.map(([value, label]) => ({ value, label })), { value: s.STT_DEFAULT_LANGUAGE || "" });
    inputs.STT_DEFAULT_LANGUAGE = sttLang;
    const defLang = select(LANGS.filter(([v]) => v).map(([value, label]) => ({ value, label })), { value: s.DEFAULT_LANGUAGE || "en" });
    inputs.DEFAULT_LANGUAGE = defLang;

    const logSelect = select(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], { value: s.LOG_LEVEL || "INFO" });
    inputs.LOG_LEVEL = logSelect;

    const promptArea = el("textarea", { class: "textarea", rows: "3", id: "set-CHAT_SYSTEM_PROMPT" });
    promptArea.value = s.CHAT_SYSTEM_PROMPT || "";
    inputs.CHAT_SYSTEM_PROMPT = promptArea;

    form.append(
      section("Voice agent LLM", "bot", [
        textInput("LLM_BASE_URL", { placeholder: "http://localhost:11434/v1", hint: "OpenAI-compatible endpoint used by the voice agent." }),
        textInput("LLM_MODEL", { placeholder: "gemma3n:latest" }),
        el("div", { class: "span-2" }, field("LLM API key", keyInput, "Stored in the server's settings file; never shown again after saving."), el("div", { class: "mt-2" }, keyStatus)),
      ], "The realtime voice agent sends transcripts to this endpoint to generate answers."),
      section("Model defaults", "box", [
        textInput("STT_DEFAULT_MODEL", { list: sttIds, hint: "Used when a request omits the model." }),
        field(labelFor("STT_DEFAULT_LANGUAGE"), sttLang),
        textInput("TTS_DEFAULT_MODEL", { list: ttsIds }),
        textInput("TTS_DEFAULT_VOICE", { placeholder: "Model default", hint: "Empty = model default voice." }),
        textInput("TTS_DEFAULT_CLONE_MODEL", { list: cloneIds }),
        field(labelFor("DEFAULT_LANGUAGE"), defLang),
      ]),
      section("VAD & turn detection", "activity", [
        rangeInput("VAD_SPEECH_THRESHOLD", { min: "0.1", max: "0.9", step: "0.05", hint: "Silero speech probability cutoff." }),
        numInput("VAD_THRESHOLD", { min: 1, max: 5000, hint: "RMS energy threshold when Silero is unavailable." }),
        numInput("VAD_ONSET_MS", { min: 0, max: 5000 }),
        numInput("VAD_SILENCE_MS", { min: 100, max: 10000, hint: "Dictation: silence before committing a turn." }),
        numInput("VAD_COMMIT_GRACE_MS", { min: 0, max: 5000 }),
        numInput("VAD_MIN_SPEECH_MS", { min: 0, max: 5000 }),
        numInput("VAD_PREROLL_MS", { min: 0, max: 5000, hint: "Audio kept before speech onset." }),
      ]),
      section("Realtime pipeline", "zap", [
        numInput("REALTIME_AGENT_SILENCE_MS", { min: 100, max: 10000, hint: "Voice agent: longer pauses keep sentences intact." }),
        numInput("REALTIME_AGENT_COMMIT_GRACE_MS", { min: 0, max: 5000 }),
        numInput("REALTIME_PARTIAL_INTERVAL_S", { min: 0, max: 10, step: 0.1, hint: "0 disables live partial transcripts." }),
        numInput("REALTIME_MAX_UTTERANCE_S", { min: 1, max: 300 }),
      ]),
      section("System", "settings", [
        el("div", { class: "span-2" }, field(labelFor("CHAT_SYSTEM_PROMPT"), promptArea, "Empty disables the system prompt.")),
        field(labelFor("LOG_LEVEL"), logSelect),
      ])
    );

    // fill plain values
    for (const key of ["LLM_BASE_URL", "LLM_MODEL", "STT_DEFAULT_MODEL", "TTS_DEFAULT_MODEL", "TTS_DEFAULT_VOICE", "TTS_DEFAULT_CLONE_MODEL"]) {
      inputs[key].value = s[key] || "";
    }
    for (const key of ["VAD_THRESHOLD", "VAD_ONSET_MS", "VAD_SILENCE_MS", "VAD_COMMIT_GRACE_MS", "VAD_MIN_SPEECH_MS", "VAD_PREROLL_MS", "REALTIME_AGENT_SILENCE_MS", "REALTIME_AGENT_COMMIT_GRACE_MS", "REALTIME_PARTIAL_INTERVAL_S", "REALTIME_MAX_UTTERANCE_S"]) {
      inputs[key].value = s[key];
    }
    inputs.VAD_SPEECH_THRESHOLD.value = s.VAD_SPEECH_THRESHOLD;
    inputs.VAD_SPEECH_THRESHOLD.dispatchEvent(new Event("input"));
  }

  async function load(notify = false) {
    try {
      const s = await store.refreshSettings();
      buildForm(s);
      if (notify) toast("Settings reloaded", "info", 1800);
    } catch (e) {
      toast(`Failed to load settings: ${e.message}`, "error");
    }
  }

  async function save() {
    const payload = {};
    for (const [key, input] of Object.entries(inputs)) {
      if (key === "LLM_API_KEY") {
        if (input.value && input.value !== MASK) payload[key] = input.value;
        continue;
      }
      if (input.type === "number" || input.type === "range") {
        if (input.value === "") continue;
        payload[key] = parseFloat(input.value);
      } else {
        payload[key] = input.value; // "" => unset for nullable fields server-side
      }
    }
    saveBtn.disabled = true;
    clear(saveBtn).append(el("span", { class: "spinner-inline" }), "Saving…");
    try {
      const s = await api.updateSettings(payload);
      store.settings = s;
      store.emit();
      buildForm(s);
      toast("Settings saved and applied", "ok");
    } catch (e) {
      toast(`Save failed: ${e.message}`, "error", 7000);
    } finally {
      saveBtn.disabled = false;
      clear(saveBtn).append(el("span", { html: iconSvg("save", 16) }), "Save settings");
    }
  }

  container.append(
    el("div", { class: "view-head" },
      el("h2", { class: "text-xl font-bold tracking-tight", text: "Settings" }),
      el("p", { text: "Configuration is applied immediately to new requests and sessions, and persisted to the server's settings file across restarts." })
    ),
    el("div", { class: "mb-5 flex flex-wrap items-center gap-3" }, saveBtn, reloadBtn),
    form
  );

  load();
  if (!store.catalog.length) store.refreshModels().then(() => store.settings && buildForm(store.settings)).catch(() => {});

  return () => {};
}
