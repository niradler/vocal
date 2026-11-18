// Mic capture, resampling, PCM16 encoding and streamed PCM playback.

/** Linear-interpolation resampler for Float32 mono audio. */
export function resampleLinear(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const outLen = Math.floor(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = pos - i0;
    out[i] = input[i0] * (1 - frac) + input[i1] * frac;
  }
  return out;
}

/** Float32 [-1,1] -> little-endian PCM16 ArrayBuffer. */
export function floatToPCM16(floats) {
  const buf = new ArrayBuffer(floats.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < floats.length; i++) {
    const s = Math.max(-1, Math.min(1, floats[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

/** Wrap raw PCM16 bytes in a WAV container (mono). */
export function encodeWav(pcm16, sampleRate) {
  const bytes = pcm16 instanceof ArrayBuffer ? new Uint8Array(pcm16) : pcm16;
  const header = new ArrayBuffer(44);
  const v = new DataView(header);
  const writeStr = (off, s) => {
    for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  v.setUint32(4, 36 + bytes.length, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); // PCM
  v.setUint16(22, 1, true); // mono
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  writeStr(36, "data");
  v.setUint32(40, bytes.length, true);
  return new Blob([header, bytes], { type: "audio/wav" });
}

export function base64FromBuffer(buf) {
  const bytes = new Uint8Array(buf);
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

export function bufferFromBase64(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

/**
 * Microphone capture. Emits ~100ms Float32 chunks at the AudioContext rate,
 * plus a 0..1 level for meters. Uses AudioWorklet with ScriptProcessor fallback.
 * deviceId selects the input source ("" = OS default); if the saved device is
 * gone, capture falls back to the default instead of failing.
 * Returns {start, stop, sampleRate, deviceId}.
 */
export function createMicCapture({ onChunk, onLevel = null, chunkMs = 100, deviceId = "" }) {
  let ctx = null;
  let stream = null;
  let node = null;
  let worklet = null;
  let pending = [];
  let pendingLen = 0;
  let stopped = false;
  let usedDeviceId = "";

  function emit(floats) {
    if (stopped) return;
    if (onLevel) {
      let sum = 0;
      for (let i = 0; i < floats.length; i++) sum += floats[i] * floats[i];
      onLevel(Math.min(1, Math.sqrt(sum / floats.length) * 3));
    }
    onChunk(floats, ctx.sampleRate);
  }

  function push(frames) {
    pending.push(frames);
    pendingLen += frames.length;
    const target = Math.floor(ctx.sampleRate * (chunkMs / 1000));
    while (pendingLen >= target) {
      const merged = new Float32Array(target);
      let off = 0;
      while (off < target) {
        const head = pending[0];
        const take = Math.min(head.length, target - off);
        merged.set(head.subarray(0, take), off);
        off += take;
        if (take === head.length) pending.shift();
        else pending[0] = head.subarray(take);
      }
      pendingLen -= target;
      emit(merged);
    }
  }

  return {
    get sampleRate() {
      return ctx ? ctx.sampleRate : 48000;
    },
    get deviceId() {
      return usedDeviceId;
    },
    async start() {
      stopped = false;
      const baseAudio = { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true };
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: deviceId ? { ...baseAudio, deviceId: { exact: deviceId } } : baseAudio,
        });
        usedDeviceId = deviceId;
      } catch (e) {
        // Saved device unplugged/renamed — fall back to the OS default.
        if (deviceId && (e.name === "OverconstrainedError" || e.name === "NotFoundError")) {
          stream = await navigator.mediaDevices.getUserMedia({ audio: baseAudio });
          usedDeviceId = "";
        } else {
          throw e;
        }
      }
      ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      if (ctx.audioWorklet) {
        try {
          // Relative to the document so the same code works when served by
          // Vocal (/ui) or from a static host (GitHub Pages subpath).
          await ctx.audioWorklet.addModule("js/pcm-worklet.js");
          worklet = new AudioWorkletNode(ctx, "pcm-capture");
          worklet.port.onmessage = (e) => push(e.data);
          source.connect(worklet);
          worklet.connect(ctx.destination); // silent passthrough keeps graph alive
          node = worklet;
          return;
        } catch {
          worklet = null; // fall through to ScriptProcessor
        }
      }
      node = ctx.createScriptProcessor(4096, 1, 1);
      node.onaudioprocess = (e) => push(new Float32Array(e.inputBuffer.getChannelData(0)));
      source.connect(node);
      node.connect(ctx.destination);
    },
    async stop() {
      stopped = true;
      try {
        if (node) {
          node.disconnect();
          if (node.port) node.port.onmessage = null;
          if (node.onaudioprocess) node.onaudioprocess = null;
        }
        if (stream) stream.getTracks().forEach((t) => t.stop());
        if (ctx && ctx.state !== "closed") await ctx.close();
      } catch {
        /* already torn down */
      }
      node = null;
      stream = null;
      ctx = null;
      pending = [];
      pendingLen = 0;
    },
  };
}

/**
 * Gapless playback queue for raw PCM16 chunks (e.g. realtime agent audio).
 * flush() drops everything not yet played — used for barge-in.
 */
export class PCMPlayer {
  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
    this.ctx = null;
    this.nextTime = 0;
    this.sources = new Set();
    this.onStateChange = null;
    // Fetch/WS chunk boundaries can split a 16-bit sample in half; carry the
    // odd trailing byte into the next chunk instead of crashing Int16Array.
    this._residual = new Uint8Array(0);
  }

  _ensure() {
    if (!this.ctx || this.ctx.state === "closed") {
      this.ctx = new AudioContext({ sampleRate: this.sampleRate });
      this.nextTime = 0;
    }
    if (this.ctx.state === "suspended") this.ctx.resume();
  }

  get playing() {
    return this.sources.size > 0;
  }

  /** enqueue PCM16 ArrayBuffer or base64 string */
  enqueue(data) {
    this._ensure();
    const incoming = typeof data === "string" ? new Uint8Array(bufferFromBase64(data)) : new Uint8Array(data);
    if (!incoming.length && !this._residual.length) return;
    let bytes;
    if (this._residual.length) {
      bytes = new Uint8Array(this._residual.length + incoming.length);
      bytes.set(this._residual, 0);
      bytes.set(incoming, this._residual.length);
    } else {
      bytes = incoming;
    }
    const usable = bytes.length - (bytes.length % 2);
    this._residual = usable < bytes.length ? bytes.slice(usable) : new Uint8Array(0);
    if (usable < 2) return;
    // Int16Array requires an even byte offset into the underlying buffer.
    if (bytes.byteOffset % 2 !== 0) bytes = bytes.slice();
    const samples = new Int16Array(bytes.buffer, bytes.byteOffset, usable / 2);
    const audio = this.ctx.createBuffer(1, samples.length, this.sampleRate);
    const channel = audio.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 0x8000;
    const src = this.ctx.createBufferSource();
    src.buffer = audio;
    src.connect(this.ctx.destination);
    const startAt = Math.max(this.ctx.currentTime + 0.02, this.nextTime);
    src.start(startAt);
    this.nextTime = startAt + audio.duration;
    this.sources.add(src);
    src.onended = () => {
      this.sources.delete(src);
      if (this.sources.size === 0 && this.onStateChange) this.onStateChange(false);
    };
    if (this.sources.size === 1 && this.onStateChange) this.onStateChange(true);
  }

  flush() {
    for (const src of this.sources) {
      try {
        src.onended = null;
        src.stop();
      } catch {
        /* already stopped */
      }
    }
    this.sources.clear();
    this.nextTime = 0;
    this._residual = new Uint8Array(0);
    if (this.onStateChange) this.onStateChange(false);
  }

  async close() {
    this.flush();
    if (this.ctx && this.ctx.state !== "closed") await this.ctx.close();
    this.ctx = null;
  }
}

/** Read a Blob as an AudioBuffer duration (for client-side validation). */
export function blobDuration(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio();
    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      const d = audio.duration;
      URL.revokeObjectURL(url);
      resolve(isFinite(d) ? d : 0);
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read audio metadata"));
    };
    audio.src = url;
  });
}
