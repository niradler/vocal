"""Shared compatibility shims for transformers 5.x API breaks.

These monkey-patches bridge gaps between transformers 5.x and downstream
packages (faster_qwen3_tts, qwen_tts) that were written against transformers 4.x.  Each shim is guarded so it only applies when the target
is actually missing — once upstream fixes land the shim becomes a no-op.

See docs/deps.md "Runtime Patches" for the full table of what changed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_shims_applied = False


def _shim_check_model_inputs() -> None:
    """Make ``check_model_inputs`` tolerate both decorator call styles.

    transformers 5.x turned the old decorator factory into ``check_model_inputs(func)``.
    Downstream packages (qwen_tts) still write ``@check_model_inputs()``, which now raises
    ``TypeError: missing 1 required positional argument: 'func'``.  Accept both forms and
    return the wrapped callable unchanged - the decorator only forwarded defaults.
    """
    import transformers.utils.generic as _tug

    def _shim(func=None, **_kw):
        if callable(func):
            return func
        return lambda inner: inner

    _shim._vocal_patched = True
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


def apply_transformers_shims() -> None:
    """Patch transformers 5.x removals that qwen_tts / faster_qwen3_tts depend on.

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

    for shim_fn in (_shim_check_model_inputs, _shim_rope_init_default, _shim_fix_mistral_regex):
        try:
            shim_fn()
        except Exception as exc:
            logger.warning("Shim %s failed: %s", shim_fn.__name__, exc)
