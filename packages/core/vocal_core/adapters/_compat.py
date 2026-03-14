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
        import torch
        import transformers.utils.generic as _tug
    except ImportError:
        return

    # --- check_model_inputs decorator (removed in transformers 5.x) ----------
    if not hasattr(_tug, "check_model_inputs"):

        def _shim(func=None, **kw):  # noqa: ARG001
            return (lambda f: f) if func is None else func

        _tug.check_model_inputs = _shim
        logger.debug("Patched transformers.utils.generic.check_model_inputs")

    # --- ROPE_INIT_FUNCTIONS["default"] (removed in transformers 5.x) --------
    try:
        from transformers.modeling_rope_utils import ROPE_INIT_FUNCTIONS

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
    except (ImportError, AttributeError):
        pass
