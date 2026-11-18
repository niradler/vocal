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
    """Make ``check_model_inputs`` work both bare and called with no args.

    transformers 4.x exposed it as a decorator factory (``@check_model_inputs()``)
    and qwen_asr/qwen_tts still use that form, while 5.x changed it to a plain
    decorator (``@check_model_inputs``). Depending on the 5.x release it is
    either missing or requires the function positionally, so wrap it when needed.
    """
    import inspect

    import transformers.utils.generic as _tug

    def _accept_both(func=None, **kwargs):
        return (lambda f: f) if func is None else func

    current = getattr(_tug, "check_model_inputs", None)
    if current is None:
        _tug.check_model_inputs = _accept_both
        logger.debug("Patched transformers.utils.generic.check_model_inputs")
        return

    try:
        params = list(inspect.signature(current).parameters.values())
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return
    first_required = bool(params) and params[0].default is inspect.Parameter.empty
    if not first_required:
        return  # already accepts the no-arg form

    def _compat(func=None, **kwargs):
        # Bare use must behave exactly like the installed decorator.
        return current(func, **kwargs) if func is not None else (lambda f: f)

    _tug.check_model_inputs = _compat
    logger.debug("Wrapped transformers.utils.generic.check_model_inputs for legacy callers")


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


def _shim_create_causal_mask() -> None:
    """Accept the pre-5.2 ``create_causal_mask`` calling convention.

    transformers 5.2 renamed ``input_embeds`` to ``inputs_embeds``, and by 5.12
    the ``cache_position`` argument was removed entirely (the mask is derived
    from the cache). On 5.3.x the opposite problem exists: ``cache_position``
    is *required*, but packages written against 4.x never pass it. Both raise
    ``TypeError`` deep inside generation, so translate the call instead.
    """
    import inspect

    import transformers.masking_utils as _masking

    current = getattr(_masking, "create_causal_mask", None)
    if current is None or getattr(current, "_vocal_patched", False):
        return

    try:
        params = inspect.signature(current).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return

    accepts_old_embeds = "input_embeds" in params
    has_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    cache_param = params.get("cache_position")
    cache_required = cache_param is not None and cache_param.default is inspect.Parameter.empty
    if accepts_old_embeds and not cache_required:
        return  # already backward compatible

    def _compat(config, *args, **kwargs):
        if not accepts_old_embeds and "input_embeds" in kwargs:
            kwargs.setdefault("inputs_embeds", kwargs.pop("input_embeds"))
        if cache_required and "cache_position" not in kwargs:
            # Prefill positions, the same tensor transformers 4.x built.
            import torch

            embeds = kwargs.get("inputs_embeds")
            past = kwargs.get("past_key_values")
            if embeds is None:
                return current(config, *args, **kwargs)
            past_seen = past.get_seq_length() if past is not None else 0
            kwargs["cache_position"] = torch.arange(past_seen, past_seen + embeds.shape[1], device=embeds.device)
        elif cache_param is None and not has_kwargs:
            kwargs.pop("cache_position", None)
        return current(config, *args, **kwargs)

    _compat._vocal_patched = True
    _masking.create_causal_mask = _compat
    logger.debug("Wrapped transformers.masking_utils.create_causal_mask for legacy callers")


def _shim_config_validate_layer_type() -> None:
    """Add ``PretrainedConfig.validate_layer_type`` for 5.3.x.

    transformers 5.4 introduced it, and qwen_tts's talker config calls it
    between ``validate_rope()`` and the rest of ``__init__``. Without it those
    models raise ``AttributeError`` while loading.
    """
    try:
        from transformers.configuration_utils import PretrainedConfig
    except ImportError:
        return

    if hasattr(PretrainedConfig, "validate_layer_type"):
        return

    def validate_layer_type(self):
        for layer_type in getattr(self, "layer_types", None) or []:
            if layer_type not in ("full_attention", "sliding_attention"):
                raise ValueError(f"Invalid layer type '{layer_type}'; expected 'full_attention' or 'sliding_attention'")

    PretrainedConfig.validate_layer_type = validate_layer_type
    logger.debug("Patched PretrainedConfig.validate_layer_type for transformers 5.3.x")


def apply_transformers_shims() -> None:
    """Patch transformers 5.x breaks that qwen_asr / qwen_tts depend on.

    Safe to call multiple times — patches are applied at most once.
    Patches: ``check_model_inputs`` decorator, ``ROPE_INIT_FUNCTIONS["default"]``,
    ``create_causal_mask`` keywords, ``fix_mistral_regex`` and the torchcodec stub.
    """
    global _shims_applied
    if _shims_applied:
        return
    _shims_applied = True

    try:
        import transformers.utils.generic as _tug  # noqa: F401
    except ImportError:
        return

    for shim_fn in (
        _shim_check_model_inputs,
        _shim_rope_init_default,
        _shim_create_causal_mask,
        _shim_config_validate_layer_type,
        _shim_fix_mistral_regex,
        _shim_torchcodec_stub,
    ):
        try:
            shim_fn()
        except Exception as exc:
            logger.warning("Shim %s failed: %s", shim_fn.__name__, exc)
