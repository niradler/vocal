// Vocal API client — fetch wrappers for every console capability.
// Requests go to the configured API base: same-origin when Vocal serves this
// UI, or the user's local/remote server when hosted statically (GitHub Pages).
import { getApiBase } from "./connection.js";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function parseError(resp) {
  let detail = `${resp.status} ${resp.statusText}`;
  try {
    const body = await resp.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ");
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(detail, resp.status);
}

async function request(path, { method = "GET", json = null, formData = null, signal = null } = {}) {
  const headers = {};
  let body = null;
  if (json != null) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (formData) {
    body = formData; // browser sets multipart boundary
  }
  const resp = await fetch(getApiBase() + path, { method, headers, body, signal });
  if (!resp.ok) throw await parseError(resp);
  return resp;
}

async function json(path, opts = {}) {
  const resp = await request(path, opts);
  return resp.json();
}

/* ---------------- system ---------------- */
export const health = () => json("/health");
export const device = () => json("/v1/system/device");

/* ---------------- settings ---------------- */
export const getSettings = () => json("/v1/settings");
export const updateSettings = (payload) => json("/v1/settings", { method: "PUT", json: payload });

/* ---------------- models ---------------- */
export const listModels = (task = null) => json(`/v1/models${task ? `?task=${task}` : ""}`);
export const listCatalog = (task = null) => json(`/v1/models/catalog${task ? `?task=${task}` : ""}`);
export const getModel = (id) => json(`/v1/models/${encodeURIComponent(id)}`);
export const deleteModel = (id) => json(`/v1/models/${encodeURIComponent(id)}`, { method: "DELETE" });
export const downloadStatus = (id) => json(`/v1/models/${encodeURIComponent(id)}/download/status`);

/** Pull a model, streaming NDJSON progress. Resolves with the final progress object. */
export async function pullModel(id, onProgress = null, signal = null) {
  const resp = await request("/v1/models/pull", { method: "POST", json: { model: id, stream: true }, signal });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let last = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (!line) continue;
      try {
        last = JSON.parse(line);
        onProgress && onProgress(last);
      } catch {
        /* partial line */
      }
    }
  }
  if (buffer.trim()) {
    try {
      last = JSON.parse(buffer.trim());
      onProgress && onProgress(last);
    } catch {
      /* ignore */
    }
  }
  if (last && last.status === "error") throw new ApiError(last.message || "Download failed", 500);
  return last;
}

/* ---------------- audio ---------------- */
export const listVoices = (model = null) => json(`/v1/audio/voices${model ? `?model=${encodeURIComponent(model)}` : ""}`);

/** TTS synthesis. Returns {blob, duration, sampleRate, format}. */
export async function speech({ model, input, voice = null, speed = 1.0, response_format = "mp3", stream = false, onChunk = null, signal = null }) {
  const resp = await request("/v1/audio/speech", {
    method: "POST",
    json: { model, input, voice, speed, response_format, stream },
    signal,
  });
  const duration = parseFloat(resp.headers.get("X-Duration") || "0");
  const sampleRate = parseInt(resp.headers.get("X-Sample-Rate") || "0", 10);

  if (stream && onChunk && resp.body) {
    const reader = resp.body.getReader();
    const chunks = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.length;
      onChunk(value, received, sampleRate);
    }
    return { blob: new Blob(chunks, { type: resp.headers.get("Content-Type") || "audio/mpeg" }), duration, sampleRate, format: response_format, bytes: received };
  }
  return { blob: await resp.blob(), duration, sampleRate, format: response_format };
}

/** Transcription/translation. Returns parsed JSON or raw text depending on format. */
export async function transcribe(formData, expectText = false) {
  const resp = await request("/v1/audio/transcriptions", { method: "POST", formData });
  return expectText ? resp.text() : resp.json();
}

export async function translate(formData) {
  const resp = await request("/v1/audio/translations", { method: "POST", formData });
  return resp.json();
}

/** Voice cloning synthesis. Returns {blob, duration, sampleRate}. */
export async function clone(formData) {
  const resp = await request("/v1/audio/clone", { method: "POST", formData });
  return {
    blob: await resp.blob(),
    duration: parseFloat(resp.headers.get("X-Duration") || "0"),
    sampleRate: parseInt(resp.headers.get("X-Sample-Rate") || "0", 10),
  };
}

/* ---------------- websockets ---------------- */
export function wsUrl(path, params = {}) {
  const base = getApiBase();
  const root = base ? new URL(base) : new URL(location.href);
  const proto = root.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL(`${proto}//${root.host}${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") url.searchParams.set(k, String(v));
  }
  return url.toString();
}
