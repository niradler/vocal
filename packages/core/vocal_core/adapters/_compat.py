"""Shared compatibility shims for transformers 5.x API breaks.

These monkey-patches bridge gaps between transformers 5.x and downstream
packages (qwen_asr, faster_qwen3_tts, qwen_tts) that were written against
transformers 4.x.  Each shim is guarded so it only applies when the target
is actually missing — once upstream fixes land the shim becomes a no-op.

See docs/deps.md "Runtime Patches" for the full table of what changed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_shims_applied = False


def _shim_check_model_inputs() -> None:
    """Restore ``check_model_inputs`` decorator (removed in transformers 5.x)."""
    import transformers.utils.generic as _tug

    if not hasattr(_tug, "check_model_inputs"):

        def _shim(func=None, **kw):  # noqa: ARG001
            return (lambda f: f) if func is None else func

        _tug.check_model_inputs = _shim
        logger.debug("Patched transformers.utils.generic.check_model_inputs")


def _shim_rope_init_default() -> None:
    """Restore ``ROPE_INIT_FUNCTIONS["default"]`` (removed in transformers 5.x)."""
    import torch

    try:
        from transformers.modeling_rope_utils import ROPE_INIT_FUNCTIONS
    except (ImportError, AttributeError):
        return

    if "default" not in ROPE_INIT_FUNCTIONS:

        def _default_rope_init(config, device=None, seq_len=None, **kw):  # noqa: ARG001
            base = getattr(config, "rope_theta", 10000.0)
            dim = getattr(
                config,
                "head_dim",
                config.hidden_size // config.num_attention_heads,
            )
            inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2, dtype=torch.float32).to(device) / dim))
            return inv_freq, 1.0

        ROPE_INIT_FUNCTIONS["default"] = _default_rope_init
        logger.debug("Patched ROPE_INIT_FUNCTIONS['default']")


def _shim_fix_mistral_regex() -> None:
    """Fix ``fix_mistral_regex`` kwarg consumed twice (transformers 5.3.0 bug).

    ``TokenizersBackend.__init__`` uses ``kwargs.get()`` instead of
    ``kwargs.pop()``, so the key remains and triggers "unexpected keyword
    argument" downstream.
    """
    try:
        from transformers.tokenization_utils_tokenizers import TokenizersBackend
    except (ImportError, AttributeError):
        return

    if getattr(TokenizersBackend.__init__, "_vocal_patched", False):
        return

    _orig_init = TokenizersBackend.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs.pop("fix_mistral_regex", None)
        _orig_init(self, *args, **kwargs)

    _patched_init._vocal_patched = True
    TokenizersBackend.__init__ = _patched_init
    logger.debug("Patched TokenizersBackend.__init__ (fix_mistral_regex)")


def _shim_torchcodec_stub() -> None:
    """Insert a ``torchcodec`` stub when the package is installed but broken.

    On Windows without FFmpeg "full-shared" DLLs, ``torchcodec`` is importable
    as a package but crashes at load time with ``RuntimeError``.  The
    transformers ASR pipeline unconditionally does ``import torchcodec`` when
    ``is_torchcodec_available()`` returns ``True`` (which only checks the
    package exists, not that it loads).  This crashes voice-cloning flows
    that auto-transcribe reference audio.

    The stub satisfies the ``isinstance(x, torchcodec.decoders.AudioDecoder)``
    guard so the pipeline falls through to the normal dict/array path.
    """
    import sys

    # Check if torchcodec is already usable (fully loaded or already stubbed).
    _existing = sys.modules.get("torchcodec")
    if _existing is not None and hasattr(_existing, "decoders"):
        return

    # Remove any partially-loaded remnants from a prior failed import.
    for key in [k for k in sys.modules if k == "torchcodec" or k.startswith("torchcodec.")]:
        del sys.modules[key]

    try:
        import torchcodec  # noqa: F401
    except (RuntimeError, OSError):
        import importlib.util
        import types

        # Clean up any new partial entries left by the failed import.
        for key in [k for k in sys.modules if k == "torchcodec" or k.startswith("torchcodec.")]:
            del sys.modules[key]

        _stub = types.ModuleType("torchcodec")
        _stub.__spec__ = importlib.util.spec_from_loader("torchcodec", loader=None)

        _decoders = types.ModuleType("torchcodec.decoders")
        _decoders.__spec__ = importlib.util.spec_from_loader("torchcodec.decoders", loader=None)
        _decoders.AudioDecoder = type("AudioDecoder", (), {})
        _stub.decoders = _decoders

        sys.modules["torchcodec"] = _stub
        sys.modules["torchcodec.decoders"] = _decoders
        logger.debug("Inserted torchcodec stub (FFmpeg DLLs not available)")


def apply_transformers_shims() -> None:
    """Patch transformers 5.x removals that qwen_asr / qwen_tts depend on.

    Safe to call multiple times — patches are applied at most once.
    Patches: ``check_model_inputs`` decorator and ``ROPE_INIT_FUNCTIONS["default"]``.
    """
    global _shims_applied
    if _shims_applied:
        return
    _shims_applied = True

    try:
        import transformers.utils.generic as _tug  # noqa: F401
    except ImportError:
        return

    _shim_check_model_inputs()
    _shim_rope_init_default()
    _shim_fix_mistral_regex()
    _shim_torchcodec_stub()
