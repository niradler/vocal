# Vocal — Project Management

**Version:** 0.3.5 | **Status:** Pre-release

---

## Open Questions

### Should `vocal listen` default to stream or chunk mode?

**Context:** `listen` has two modes:
- **Chunk mode** (current default) — records until a pause, sends full utterance to REST API. Latency ~1-2s. Better accuracy, works without WebSocket.
- **Stream mode** (`--stream`) — pumps audio frames over WebSocket, words appear as you speak. Latency ~200ms.

**The question:** Should stream be the default since "listen" implies real-time? Or keep chunk as default for accuracy and broader server compatibility?

**Options considered:**
1. Make stream the default; chunk mode becomes `--accurate` opt-in
2. Keep chunk as default; stream stays as `--stream` opt-in
3. Drop chunk mode from `listen` entirely — always stream

**Leaning toward:** Option 1 — flip default to stream, rename flags to `--accurate` for chunk path.

**Blocked on:** Decision from team.

---

### Expand beyond STT/TTS — support more voice model tasks

**Context:** Vocal currently supports two task types: `stt` and `tts`. The voice AI ecosystem has more model categories that fit naturally into Vocal's pull/serve/use workflow:

| Task | What it does | Example models |
|------|-------------|----------------|
| `vad` | Neural Voice Activity Detection — detect speech regions with high accuracy | `pyannote/segmentation-3.0`, Silero VAD |
| `diarization` | Speaker diarization — *who* spoke *when* | `pyannote/speaker-diarization-3.1` |
| `speaker-id` | Speaker embedding / verification — is this the same person? | `pyannote/embedding`, `speechbrain/spkrec-ecapa-voxceleb` |
| `audio-classification` | Classify audio events (speech vs music vs noise, emotions) | `MIT/ast-finetuned-audioset` |
| `language-id` | Identify spoken language from audio | `speechbrain/lang-id-voxlingua107-ecapa` |

**Why `pyannote/segmentation-3.0` is a good first candidate:**
- Replaces current energy/RMS-based VAD in `/v1/realtime` with a proper neural VAD
- Enables speaker-aware transcription (diarization pipeline builds on top of it)
- Well-maintained, MIT-licensed, works with HuggingFace `Model.from_pretrained`
- Small model (~5MB), fast inference, no GPU required

**What needs to change:**
1. Add new `ModelTask` variants (currently only `stt` | `tts`)
2. New adapter base class per task (e.g. `VADAdapter`, `DiarizationAdapter`)
3. New API endpoints (e.g. `/v1/audio/vad`, `/v1/audio/diarize`)
4. Decide: should VAD be a standalone endpoint, or an enhancement to existing STT endpoints (e.g. `vad_model` param on `/v1/audio/transcriptions`)?
5. `pyannote.audio` as optional dependency (like `torch` / `transformers`)

**Open sub-questions:**
- Should diarization be a separate endpoint or a flag on transcription (`?diarize=true` returning speaker-labeled segments)?
- How to handle pipeline models (diarization needs segmentation + embedding models together)?
- Naming: keep `ModelTask` as flat enum or introduce task hierarchy?

**Priority:** Medium — current RMS VAD works for demos, but neural VAD would be a significant quality upgrade for the realtime endpoint.

---

### TransformersSTTAdapter streaming support

**Context:** `FasterWhisperAdapter` supports `transcribe_stream` because `faster-whisper`'s `.transcribe()` returns a lazy segment generator — each segment (phrase/sentence chunk with timestamps) is yielded as it's decoded. `TransformersSTTAdapter` uses the HuggingFace `pipeline` API which returns the full result at once, so it falls back to the base class `NotImplementedError`.

**Options:**

**Option 1 — Fake streaming (segment yield from chunks)**
Override `transcribe_stream` in `TransformersSTTAdapter` to run the full pipeline, then yield the resulting `chunks` as `TranscriptionSegment` objects one by one. Same granularity as faster-whisper (segment-level, not token-level). Simple, achieves feature parity, same CLI UX.

**Option 2 — True streaming via `model.generate()` + `TextIteratorStreamer`**
Bypass `pipeline`, call `model.generate()` directly with HuggingFace's `TextIteratorStreamer` to get token-by-token output. Problem: Whisper embeds timestamps as special tokens (`<|0.00|>`) in the sequence — you'd need to parse and align them manually to produce `TranscriptionSegment` objects. Significantly more complex, same segment-level granularity result, minimal real-world latency benefit over option 1 for file transcription.

**The real performance win (future work):** Live mic chunking — processing audio in rolling real-time windows (e.g. 2–5s) as they arrive from the mic, rather than buffering the whole recording. This is a separate architectural feature that changes the adapter interface and requires VAD + overlap handling. Both adapters would benefit equally.

**Plan:** Implement option 1 now for feature parity. Revisit option 2 only as part of the live chunked mic streaming feature.

**Status:** Pending implementation.
