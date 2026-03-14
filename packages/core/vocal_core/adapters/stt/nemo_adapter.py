import asyncio
import importlib.util
import io
import logging
import os
import subprocess
import sys
import tempfile
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from ...config import optional_dependency_install_hint, vocal_settings
from .base import STTAdapter, TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

_NEMO_NOISY_LOGGERS = [
    "nemo",
    "nemo_logger",
    "nemo.collections",
    "nemo.core",
    "nemo.utils",
    "pytorch_lightning",
    "lightning",
    "lightning.pytorch",
    "omegaconf",
    "hydra",
    "torch",
    "torch.distributed",
    "torch.distributed.elastic",
    "torch.distributed.elastic.multiprocessing",
    "torch.distributed.elastic.multiprocessing.redirects",
]

_NOISE_PATTERNS = (
    "megatron_init",
    "num_microbatches_calculator",
    "Redirects are currently not supported",
    "OneLogger",
    "error_handling_strategy",
    "No exporters were provided",
    "flash-attn is not installed",
    "sox",
    "SoX could not be found",
    "http://sox.sourceforge.net",
    "path variables",
)


def _is_nemo_noise(line: str) -> bool:
    return any(pat in line for pat in _NOISE_PATTERNS)


def _redirect_fd(fd: int, devnull_fd: int) -> int | None:
    try:
        old = os.dup(fd)
        os.dup2(devnull_fd, fd)
        return old
    except OSError:
        return None


def _restore_fd(fd: int, old: int | None) -> None:
    if old is not None:
        try:
            os.dup2(old, fd)
            os.close(old)
        except OSError:
            pass


def _patch_subprocess_quiet(subprocess_mod):
    orig_run = subprocess_mod.run
    orig_popen = subprocess_mod.Popen

    def _quiet_run(*args, **kw):
        kw.setdefault("stdout", subprocess_mod.DEVNULL)
        kw.setdefault("stderr", subprocess_mod.DEVNULL)
        return orig_run(*args, **kw)

    class _QuietPopen(orig_popen):
        def __init__(self, *args, **kw):
            kw.setdefault("stdout", subprocess_mod.DEVNULL)
            kw.setdefault("stderr", subprocess_mod.DEVNULL)
            super().__init__(*args, **kw)

    subprocess_mod.run = _quiet_run
    subprocess_mod.Popen = _QuietPopen
    return orig_run, orig_popen


# TODO: fix root causes — megatron/apex init, torch distributed redirects on Windows,
# OneLogger telemetry, flash-attn missing, SoX not found — suppressed for now
@contextmanager
def _suppress_nemo_noise():
    saved_levels = {}
    for name in _NEMO_NOISY_LOGGERS:
        lg = logging.getLogger(name)
        saved_levels[name] = lg.level
        lg.setLevel(logging.ERROR)

    old_stdout, old_stderr = sys.stdout, sys.stderr
    buf_out, buf_err = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = buf_out, buf_err

    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        devnull_fd = None

    old_fd1 = _redirect_fd(1, devnull_fd) if devnull_fd is not None else None
    old_fd2 = _redirect_fd(2, devnull_fd) if devnull_fd is not None else None
    if devnull_fd is not None:
        os.close(devnull_fd)

    import subprocess as _subprocess

    _orig_run, _orig_popen = _patch_subprocess_quiet(_subprocess)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", category=FutureWarning)
        try:
            yield
        finally:
            _subprocess.run = _orig_run
            _subprocess.Popen = _orig_popen  # type: ignore[assignment]

            sys.stdout.flush()
            sys.stderr.flush()
            _restore_fd(1, old_fd1)
            _restore_fd(2, old_fd2)
            sys.stdout, sys.stderr = old_stdout, old_stderr

            for name, level in saved_levels.items():
                logging.getLogger(name).setLevel(level)

            for buf, stream in ((buf_out, sys.stdout), (buf_err, sys.stderr)):
                captured = buf.getvalue()
                if captured:
                    for line in captured.splitlines():
                        if line.strip() and not _is_nemo_noise(line):
                            print(line, file=stream)


NEMO_AVAILABLE: bool = importlib.util.find_spec("nemo") is not None


class NemoSTTAdapter(STTAdapter):
    """
    NVIDIA NeMo STT adapter for Parakeet-TDT, Canary, and other NeMo ASR models.

    Models are distributed as .nemo checkpoint files on HuggingFace.
    Requires: pip install nemo_toolkit[asr]
    """

    def __init__(self) -> None:
        self.model: Any = None
        self.model_path: Path | None = None
        self.device: str = "cpu"

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        if not NEMO_AVAILABLE:
            raise ImportError(optional_dependency_install_hint("nemo", "nemo_toolkit[asr]"))
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync, model_path, device)

    def _load_sync(self, model_path: Path, device: str) -> None:
        import torch

        with _suppress_nemo_noise():
            from nemo.collections.asr.models import ASRModel

        resolved = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.device = resolved

        nemo_file = next(model_path.glob("*.nemo"), None)
        with _suppress_nemo_noise():
            if nemo_file is not None:
                logger.info("Loading NeMo STT model from %s on %s", nemo_file, resolved)
                self.model = ASRModel.restore_from(str(nemo_file), map_location=resolved)
            else:
                dir_name = model_path.name
                if "--" in dir_name:
                    model_name = dir_name.replace("--", "/", 1)
                else:
                    model_name = str(model_path)
                logger.info("Loading NeMo STT model %s via from_pretrained on %s", model_name, resolved)
                self.model = ASRModel.from_pretrained(model_name=model_name, map_location=resolved)

            self.model.eval()
        self.model_path = model_path
        logger.info("NeMo STT model loaded on %s", resolved)

    async def unload_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None
            if self.device == "cuda":
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
            "backend": "nemo",
        }

    _LHOTSE_UNSUPPORTED = {".m4a", ".aac", ".wma", ".amr"}

    @staticmethod
    def _to_wav(src: str) -> str:
        dst = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
            check=True,
            capture_output=True,
        )
        return dst

    async def transcribe(
        self,
        audio: str | Path | BinaryIO,
        language: str | None = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        **kwargs,
    ) -> TranscriptionResult:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")

        temp_path: str | None = None
        converted_path: str | None = None
        try:
            if isinstance(audio, (str, Path)):
                audio_path = str(audio)
                if Path(audio_path).suffix.lower() in self._LHOTSE_UNSUPPORTED:
                    converted_path = self._to_wav(audio_path)
                    audio_path = converted_path
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(audio.read())
                    temp_path = tmp.name
                audio_path = temp_path

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._run_transcribe, audio_path, language, word_timestamps)
            return result
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
            if converted_path:
                Path(converted_path).unlink(missing_ok=True)

    def _run_transcribe(self, audio_path: str, language: str | None, word_timestamps: bool) -> TranscriptionResult:
        resolved_language = language or vocal_settings.STT_DEFAULT_LANGUAGE or vocal_settings.NEMO_DEFAULT_LANGUAGE or vocal_settings.DEFAULT_LANGUAGE

        if word_timestamps:
            output = self.model.transcribe([audio_path], timestamps=True)
            if isinstance(output, tuple):
                hypotheses, ts_list = output
                text = hypotheses[0] if hypotheses else ""
                segments = self._build_segments(ts_list[0] if ts_list else None)
            else:
                text = str(output[0]) if output else ""
                segments = None
        else:
            output = self.model.transcribe([audio_path])
            logger.debug("NeMo transcribe output type=%s len=%s", type(output).__name__, len(output) if hasattr(output, "__len__") else "?")
            if isinstance(output, tuple):
                hypotheses = output[0]
                text = str(hypotheses[0]) if hypotheses else ""
            elif output:
                item = output[0]
                # NeMo Hypothesis objects expose .text directly
                text = getattr(item, "text", None) or str(item)
            else:
                text = ""
            segments = None

        return TranscriptionResult(
            text=text.strip(),
            language=resolved_language,
            duration=0.0,
            segments=segments,
        )

    def _build_segments(self, ts_data: Any) -> list[TranscriptionSegment] | None:
        if ts_data is None:
            return None
        try:
            words = getattr(ts_data, "word", None) or []
            if not words:
                return None
            return [
                TranscriptionSegment(
                    id=i,
                    start=float(getattr(w, "start_offset", 0.0)),
                    end=float(getattr(w, "end_offset", 0.0)),
                    text=str(getattr(w, "word", w)),
                )
                for i, w in enumerate(words)
            ]
        except Exception:
            return None
