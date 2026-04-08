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
    except ImportError:
        return
    except (RuntimeError, OSError) as exc:
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
        # Truncate the error — torchcodec dumps multi-KB tracebacks for
        # every FFmpeg version it tries, which can fill subprocess PIPE
        # buffers and hang the server.
        short = str(exc).split("\n", 1)[0][:200]
        logger.warning(
            "torchcodec installed but broken (%s). Inserted stub; voice cloning uses standard audio path. Fix: install FFmpeg shared libs or pip uninstall torchcodec.",
            short,
        )


def _shim_qwen25_omni_talker() -> None:
    """Fix Qwen2.5-Omni talker positional arg mismatch with transformers 5.x.

    The talker's ``prepare_inputs_for_generation`` calls ``super()`` with
    positional args that mapped to 4.x's signature. In 5.x,
    ``next_sequence_length`` was inserted as the 2nd positional arg, so
    ``past_key_values`` lands in the wrong slot. This patch rewrites the
    super call to use keyword args.
    """
    try:
        from transformers.models.qwen2_5_omni.modeling_qwen2_5_omni import Qwen2_5OmniTalkerForConditionalGeneration as _Talker
    except ImportError:
        return

    if getattr(_Talker.prepare_inputs_for_generation, "_vocal_patched", False):
        return

    _orig = _Talker.prepare_inputs_for_generation

    def _patched_prepare(
        self,
        input_ids,
        input_text_ids=None,
        past_key_values=None,
        attention_mask=None,
        inputs_embeds=None,
        thinker_reply_part=None,
        cache_position=None,
        position_ids=None,
        use_cache=True,
        pixel_values=None,
        pixel_values_videos=None,
        image_grid_thw=None,
        video_grid_thw=None,
        input_audio_features=None,
        audio_feature_attention_mask=None,
        audio_feature_lengths=None,
        use_audio_in_video=False,
        video_second_per_grid=None,
        **kwargs,
    ):
        # Call super with keyword args to avoid positional mismatch
        model_inputs = super(_Talker, self).prepare_inputs_for_generation(
            input_ids,
            past_key_values=past_key_values,
            attention_mask=attention_mask,
            inputs_embeds=inputs_embeds,
            cache_position=cache_position,
            use_cache=use_cache,
            thinker_reply_part=thinker_reply_part,
            input_text_ids=input_text_ids,
            image_grid_thw=image_grid_thw,
            video_grid_thw=video_grid_thw,
            use_audio_in_video=use_audio_in_video,
            audio_feature_lengths=audio_feature_lengths,
            video_second_per_grid=video_second_per_grid,
            **kwargs,
        )
        model_inputs["position_ids"] = None
        return model_inputs

    _patched_prepare._vocal_patched = True
    _Talker.prepare_inputs_for_generation = _patched_prepare
    logger.debug("Patched Qwen2_5OmniTalkerForConditionalGeneration.prepare_inputs_for_generation")


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

    for shim_fn in (_shim_check_model_inputs, _shim_rope_init_default, _shim_fix_mistral_regex, _shim_torchcodec_stub, _shim_qwen25_omni_talker):
        try:
            shim_fn()
        except Exception as exc:
            logger.warning("Shim %s failed: %s", shim_fn.__name__, exc)
