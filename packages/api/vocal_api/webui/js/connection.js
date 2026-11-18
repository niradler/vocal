// API base management — lets the same UI run served by Vocal itself
// (same-origin) or from a static host like GitHub Pages, in which case it
// talks to the user's local Vocal server directly from the browser.
import { el, modal, toast, iconSvg } from "./ui.js";

const STORAGE_KEY = "vocal.apiBase";
export const DEFAULT_REMOTE_BASE = "http://localhost:8000";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", ""]);

/** True when the page is NOT served by a local Vocal instance (Pages, file://, LAN static host). */
export function isHosted() {
  return !LOCAL_HOSTS.has(location.hostname);
}

/** "" means same-origin (UI served by Vocal itself). */
export function getApiBase() {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved == null ? "" : saved.replace(/\/+$/, "");
}

export function setApiBase(base) {
  localStorage.setItem(STORAGE_KEY, base.replace(/\/+$/, ""));
}

export function clearApiBase() {
  localStorage.removeItem(STORAGE_KEY);
}

function fetchWithTimeout(url, ms = 4000) {
  const opts = { cache: "no-store" };
  if (typeof AbortSignal !== "undefined" && AbortSignal.timeout) opts.signal = AbortSignal.timeout(ms);
  return fetch(url, opts);
}

/** Probe /health at a candidate base. Returns the health JSON or throws. */
export async function testBase(base) {
  const resp = await fetchWithTimeout(`${base}/health`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

/**
 * Boot-time detection: prefer an explicit saved choice, then same-origin
 * (Vocal serving the UI), then the conventional local server address.
 */
export async function detectApiBase() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved != null) return getApiBase();
  if (!isHosted()) {
    try {
      await testBase("");
      return "";
    } catch {
      /* fall through to the default local address */
    }
  }
  return DEFAULT_REMOTE_BASE;
}

export function describeBase(base) {
  return base === "" ? `${location.origin} (this server)` : base;
}

/** Server connection dialog: address input, live test, save + reload. */
export function openConnectionModal() {
  const current = getApiBase();
  const input = el("input", {
    class: "input",
    type: "url",
    value: current || DEFAULT_REMOTE_BASE,
    placeholder: DEFAULT_REMOTE_BASE,
    "aria-label": "Vocal server address",
  });
  const resultLine = el("p", { class: "field-hint", text: "The console talks to this address directly from your browser." });

  const testBtn = el("button", {
    class: "btn btn-ghost btn-sm",
    onclick: async () => {
      testBtn.disabled = true;
      resultLine.textContent = "Testing…";
      resultLine.style.color = "";
      try {
        const health = await testBase(input.value.replace(/\/+$/, ""));
        resultLine.textContent = `Connected — Vocal API v${health.api_version}`;
        resultLine.style.color = "var(--circuit-green)";
      } catch (e) {
        resultLine.textContent = `No answer: ${e.message}. Is Vocal running? Start it with: vocal serve`;
        resultLine.style.color = "var(--danger)";
      } finally {
        testBtn.disabled = false;
      }
    },
  }, el("span", { html: iconSvg("zap", 14) }), "Test connection");

  modal({
    title: "Vocal server",
    body: el("div", { class: "form-grid" },
      el("div", {},
        el("label", { class: "label", text: "Server address" }),
        input,
        el("p", { class: "field-hint", text: "Leave the default if Vocal runs on this machine. For a remote box, use its address (CORS must allow this origin)." })
      ),
      el("div", { class: "flex items-center gap-3" }, testBtn),
      resultLine,
      isHosted()
        ? el("p", { class: "rounded-lg border border-[rgba(0,191,255,0.3)] bg-[rgba(0,191,255,0.06)] p-3 text-xs leading-relaxed text-lightgrey", text: "This console is hosted on GitHub Pages. Your audio never goes through GitHub — every request goes straight from your browser to the Vocal server above. Start it locally with: pip install vocal-ai && vocal serve" })
        : null
    ),
    actions: [
      { label: "Use default", kind: "btn-ghost", onclick: (close) => { clearApiBase(); close(); location.reload(); } },
      { label: "Cancel", kind: "btn-ghost", onclick: (close) => close() },
      {
        label: "Save & reconnect",
        kind: "btn-primary",
        onclick: (close) => {
          const value = input.value.trim().replace(/\/+$/, "");
          if (!/^https?:\/\//.test(value)) {
            toast("Address must start with http:// or https://", "error");
            return;
          }
          setApiBase(value === location.origin ? "" : value);
          close();
          location.reload();
        },
      },
    ],
  });
}
