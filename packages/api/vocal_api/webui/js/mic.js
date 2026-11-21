// Microphone source selection + live capture feedback, shared by every
// view that records (STT, Live, Agent, Clone). Mirrors `vocal devices` /
// `--device` from the CLI: list inputs, mark the default, remember the choice.
import { el, clear } from "./ui.js";

const STORAGE_KEY = "vocal.micDevice";
// RMS level (0..1, pre-scaled by createMicCapture) above which we show
// "voice detected" rather than just room noise.
export const VOICE_LEVEL = 0.08;

export function getSavedMic() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

export function setSavedMic(deviceId) {
  localStorage.setItem(STORAGE_KEY, deviceId);
}

/** Input devices as {id, label, isDefault}. Labels need mic permission; until
 * then browsers expose anonymous placeholders, which we number sensibly. */
export async function listInputDevices() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((d) => d.kind === "audioinput")
    .map((d, i) => ({
      id: d.deviceId,
      label: d.label || `Microphone ${i + 1}`,
      isDefault: d.deviceId === "default",
    }));
}

/**
 * <select> of microphone sources. Persists the choice, refreshes on device
 * change, restores the saved device when still present. Call .destroy() on
 * view teardown to detach the devicechange listener.
 */
export function createMicPicker({ onchange = null } = {}) {
  const sel = el("select", {
    class: "select",
    "aria-label": "Microphone source",
    onchange: (e) => {
      setSavedMic(e.target.value);
      if (onchange) onchange(e.target.value);
    },
  });

  async function refresh() {
    const current = sel.value || getSavedMic();
    let devices = [];
    try {
      devices = await listInputDevices();
    } catch {
      devices = [];
    }
    clear(sel);
    sel.append(el("option", { value: "", label: "System default microphone" }));
    for (const d of devices) {
      if (d.isDefault) continue; // represented by the "" option
      sel.append(el("option", { value: d.id, text: d.label }));
    }
    sel.value = [...sel.options].some((o) => o.value === current) ? current : "";
  }

  const handler = () => refresh();
  if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
    navigator.mediaDevices.addEventListener("devicechange", handler);
  }
  sel.destroy = () => {
    if (navigator.mediaDevices && navigator.mediaDevices.removeEventListener) {
      navigator.mediaDevices.removeEventListener("devicechange", handler);
    }
  };
  // Views call this after a successful getUserMedia: permission grants reveal
  // real device labels but do not fire devicechange.
  sel.refresh = refresh;
  refresh();
  return sel;
}

/**
 * Live level meter. set(level) animates the bars and reports whether voice
 * is present so views can flip a "hearing you" indicator.
 */
export function createLevelMeter(barCount = 16) {
  const root = el("div", { class: "level-meter", "aria-hidden": "true" });
  const bars = [];
  for (let i = 0; i < barCount; i++) {
    const bar = el("div", { class: "level-bar" });
    bars.push(bar);
    root.append(bar);
  }
  return {
    el: root,
    /** Returns true when the level crosses the voice threshold. */
    set(level, active = true) {
      const voice = active && level > VOICE_LEVEL;
      bars.forEach((bar, i) => {
        const center = 1 - Math.abs(i - bars.length / 2) / (bars.length / 2);
        const h = Math.max(4, Math.min(36, level * 36 * (0.4 + center * 0.8) + (active ? Math.random() * 3 : 0)));
        bar.style.height = `${active ? h : 4}px`;
        bar.style.background = voice ? "var(--circuit-green)" : "var(--accent-green)";
      });
      return voice;
    },
  };
}

/** Small status pill: idle / listening / hearing voice. */
export function createVoiceIndicator() {
  const dot = el("span", { class: "dot dot-idle" });
  const text = el("span", { text: "mic idle" });
  const root = el("span", { class: "badge", style: { gap: "0.4rem" } }, dot, text);
  return {
    el: root,
    set(state) {
      if (state === "voice") {
        dot.className = "dot dot-live";
        text.textContent = "hearing voice";
        root.className = "badge badge-green";
      } else if (state === "listening") {
        dot.className = "dot dot-live";
        text.textContent = "listening";
        root.className = "badge badge-accent";
      } else {
        dot.className = "dot dot-idle";
        text.textContent = "mic idle";
        root.className = "badge";
      }
    },
  };
}
