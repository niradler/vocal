// DOM helpers — all dynamic text goes through textContent (XSS-safe).
import { iconSvg, iconEl } from "./icons.js";

export { iconSvg, iconEl };

/** Create an element: el("div", {class: "card", onclick: fn}, ...children) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v; // trusted static markup only (icons)
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else if (v === true) node.setAttribute(k, "");
    else node.setAttribute(k, String(v));
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function fmtBytes(n) {
  if (!n || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtSeconds(s) {
  if (s == null || isNaN(s)) return "—";
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${(s - m * 60).toFixed(0)}s`;
}

export function fmtMs(ms) {
  if (ms == null || isNaN(ms) || ms < 0) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}

export function timestamp() {
  return new Date().toLocaleTimeString([], { hour12: false });
}

export function debounce(fn, ms = 250) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

/* ---------------- toasts ---------------- */
export function toast(message, kind = "ok", timeout = 4200) {
  const region = document.getElementById("toast-region");
  const iconName = kind === "error" ? "alert" : kind === "info" ? "info" : "check";
  const color = kind === "error" ? "var(--danger)" : kind === "info" ? "var(--electric-blue)" : "var(--circuit-green)";
  // Long server errors (e.g. a 54-voice id list) belong in the details panel,
  // not a wall of text in the corner.
  const text = String(message);
  const shown = text.length > 280 ? `${text.slice(0, 280)}…` : text;
  const t = el(
    "div",
    { class: `toast ${kind === "error" ? "toast-error" : kind === "info" ? "toast-info" : ""}`, role: "status" },
    el("span", { html: iconSvg(iconName, 16), style: { color, flex: "none", marginTop: "2px" } }),
    el("span", { text: shown })
  );
  region.append(t);
  setTimeout(() => {
    t.classList.add("leaving");
    setTimeout(() => t.remove(), 220);
  }, timeout);
}

/* ---------------- modal ---------------- */
export function modal({ title, body, actions = [], wide = false }) {
  const root = document.getElementById("modal-root");
  const overlay = el("div", { class: "modal-overlay", role: "dialog", "aria-modal": "true" });
  const box = el("div", { class: "modal", style: wide ? { maxWidth: "52rem" } : {} });
  const close = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => e.key === "Escape" && close();
  overlay.addEventListener("click", (e) => e.target === overlay && close());
  document.addEventListener("keydown", onKey);

  box.append(
    el(
      "div",
      { class: "flex items-center justify-between border-b border-[#3a3a3a] px-6 py-4" },
      el("h3", { class: "text-base font-bold", text: title }),
      el("button", { class: "btn btn-ghost btn-icon", "aria-label": "Close", onclick: close, html: iconSvg("x", 16) })
    ),
    el("div", { class: "px-6 py-5" }, body),
    actions.length
      ? el("div", { class: "flex flex-wrap justify-end gap-3 border-t border-[#3a3a3a] px-6 py-4" }, actions.map((a) => el("button", { class: `btn ${a.kind || "btn-ghost"}`, onclick: () => a.onclick(close), text: a.label })))
      : null
  );
  overlay.append(box);
  root.append(overlay);
  return { close, overlay };
}

export function confirmModal({ title, message, confirmLabel = "Confirm", danger = false, onConfirm }) {
  modal({
    title,
    body: el("p", { class: "text-sm text-lightgrey", text: message }),
    actions: [
      { label: "Cancel", kind: "btn-ghost", onclick: (close) => close() },
      {
        label: confirmLabel,
        kind: danger ? "btn-danger" : "btn-primary",
        onclick: async (close) => {
          close();
          await onConfirm();
        },
      },
    ],
  });
}

/* ---------------- small builders ---------------- */
export function badge(text, kind = "") {
  return el("span", { class: `badge ${kind ? `badge-${kind}` : ""}`, text });
}

export function field(labelText, input, hint = null) {
  return el("div", {}, el("label", { class: "label", text: labelText }), input, hint ? el("p", { class: "field-hint", text: hint }) : null);
}

export function select(options, { value = "", onchange = null, id = "" } = {}) {
  const s = el("select", { class: "select", id, onchange: (e) => onchange && onchange(e.target.value) });
  for (const opt of options) {
    const o = typeof opt === "string" ? { value: opt, label: opt } : opt;
    const option = el("option", { value: o.value, text: o.label });
    if (o.disabled) option.disabled = true;
    s.append(option);
  }
  s.value = value;
  return s;
}

export function skeletonBlock(h = "1rem", w = "100%") {
  return el("div", { class: "skeleton", style: { height: h, width: w } });
}

export function emptyState(iconName, title, subtitle, action = null) {
  return el(
    "div",
    { class: "empty-state" },
    el("span", { html: iconSvg(iconName, 40) }),
    el("p", { class: "text-sm font-semibold text-white", text: title }),
    subtitle ? el("p", { class: "text-xs", text: subtitle }) : null,
    action
  );
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard", "info", 1800);
  } catch {
    toast("Clipboard unavailable in this browser", "error");
  }
}
